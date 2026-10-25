"""Prende a escrita na janela onde a ditada comecou.

Por que existe: `keyboard.write` e o Ctrl+V injetam teclas via SendInput, que
por definicao vao para a janela com foco de teclado *naquele instante*. Trocar
de janela no meio da ditada levava o resto do texto junto - texto do editor
caindo no WhatsApp.

Por que nao da para escrever na janela de fundo: medido nesta maquina, contra
uma pagina de teste no Chrome (mesma classe `Chrome_WidgetWin_1` do WhatsApp),
com o foco em outra janela:

    PostMessage WM_CHAR          -> ignorado
    SendMessage WM_CHAR          -> ignorado
    KEYDOWN + CHAR + KEYUP       -> ignorado
    AttachThreadInput + SetFocus -> ignorado (e o caractere foi parar na
                                    janela que estava em foco)

O Chromium recusa input sintetico vindo de outro processo, e nele nem existe
controle filho para receber a mensagem: `hwndFocus` e a propria janela de topo
e `hwndCaret` e zero, porque o campo de texto e um elemento DOM. Como Chrome,
Edge, VS Code, WhatsApp e Discord sao todos Chromium, a familia inteira de
solucoes "escrever sem foco" esta descartada.

Sobra: segurar o texto enquanto o foco esta fora e devolver o foco a janela
certa na hora de entregar - sempre *confirmando* que ela voltou antes de
digitar. Digitar as cegas com "apertar Enter" ligado mandaria a mensagem na
janela errada.
"""

from __future__ import annotations

import ctypes
import time

try:
    _u32 = ctypes.windll.user32
    _k32 = ctypes.windll.kernel32
except AttributeError:  # pragma: no cover - fora do Windows
    _u32 = _k32 = None

SW_RESTORE = 9


def atual() -> int:
    """Janela em primeiro plano agora, ou 0."""
    if _u32 is None:
        return 0
    try:
        return int(_u32.GetForegroundWindow() or 0)
    except Exception:  # noqa: BLE001
        return 0


def existe(hwnd: int) -> bool:
    if _u32 is None or not hwnd:
        return False
    try:
        return bool(_u32.IsWindow(hwnd))
    except Exception:  # noqa: BLE001
        return False


def em_foco(hwnd: int) -> bool:
    """Custa 0,28 us - barato o bastante para o worker checar a 40 Hz."""
    if _u32 is None or not hwnd:
        return True  # sem alvo definido, qualquer janela serve
    try:
        return int(_u32.GetForegroundWindow() or 0) == int(hwnd)
    except Exception:  # noqa: BLE001
        return True


# Janelas do shell que ganham o foco quando se clica na bandeja. Nunca sao o
# destino de um ditado: travar nelas fazia o texto todo "esperar" e, no fim,
# ser digitado na barra de tarefas.
_CLASSES_DO_SHELL = {
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
    "TopLevelWindowForOverflowXamlIsland", "Progman", "WorkerW",
    # Windows 11: Iniciar, Pesquisa e paineis da barra
    "XamlExplorerHostIslandWindow", "Windows.UI.Core.CoreWindow",
}


def classe(hwnd: int) -> str:
    if _u32 is None or not existe(hwnd):
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        _u32.GetClassNameW(hwnd, buf, 256)
        return buf.value or ""
    except Exception:  # noqa: BLE001
        return ""


def alvo_valido(hwnd: int) -> bool:
    """False para a barra de tarefas/area de trabalho e janelas do proprio VozFlow
    (o menu da bandeja), que ficam em primeiro plano quando a ditada comeca pelo
    icone - o texto nao tem como ser para elas."""
    if not existe(hwnd):
        return False
    if classe(hwnd) in _CLASSES_DO_SHELL:
        return False
    try:
        pid = ctypes.c_ulong(0)
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == _k32.GetCurrentProcessId():
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def trazer_para_frente(hwnd: int) -> bool:
    """Poe uma janela do PROPRIO VozFlow na frente de tudo (ex.: Configuracoes).

    O Windows so deixa trazer janela para a frente quem ja esta em primeiro
    plano, e um app de bandeja nao esta: a janela abria ATRAS das outras e so
    aparecia no segundo clique. Anexar a fila de entrada da janela que esta na
    frente agora (nao a da nossa, que e a mesma thread) contorna a trava.
    """
    if _u32 is None or not existe(hwnd):
        return False
    try:
        if _u32.IsIconic(hwnd):
            _u32.ShowWindow(hwnd, SW_RESTORE)
        meu = _k32.GetCurrentThreadId()
        frente = _u32.GetForegroundWindow()
        dele = _u32.GetWindowThreadProcessId(frente, None) if frente else 0
        # Janela da frente travada (nao responde): anexar a fila dela pode
        # travar a nossa tambem. Sem anexar, no pior caso a janela pisca na
        # barra de tarefas - como era antes.
        travada = bool(frente and _u32.IsHungAppWindow(frente))
        anexado = bool(dele and dele != meu and not travada
                       and _u32.AttachThreadInput(meu, dele, True))
        try:
            _u32.BringWindowToTop(hwnd)
            ok = bool(_u32.SetForegroundWindow(hwnd))
            _u32.SetActiveWindow(hwnd)
        finally:
            if anexado:
                _u32.AttachThreadInput(meu, dele, False)
    except Exception:  # noqa: BLE001
        return False
    return ok


def titulo(hwnd: int) -> str:
    if _u32 is None or not existe(hwnd):
        return ""
    try:
        n = _u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        _u32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value or ""
    except Exception:  # noqa: BLE001
        return ""


def nome_curto(hwnd: int, limite: int = 38) -> str:
    """Titulo enxuto para caber no overlay."""
    t = " ".join(titulo(hwnd).split())
    return (t[: limite - 1] + "…") if len(t) > limite else t


def restaurar(hwnd: int, espera: float = 1.2) -> bool:
    """Traz a janela de volta ao foco e CONFIRMA que ela chegou la.

    O `AttachThreadInput` existe porque o Windows so deixa trazer uma janela
    para frente quem ja e o processo em primeiro plano ou recebeu o ultimo
    evento de entrada - e o VozFlow, rodando de fundo, nao e nenhum dos dois.
    Anexar a fila de entrada da thread dona da janela contorna essa trava.

    Devolve False quando nao conseguiu: nesse caso quem chamou NAO pode
    digitar, so copiar para a area de transferencia.
    """
    if _u32 is None or not existe(hwnd):
        return False
    if em_foco(hwnd):
        return True

    try:
        if _u32.IsIconic(hwnd):
            _u32.ShowWindow(hwnd, SW_RESTORE)
        meu = _k32.GetCurrentThreadId()
        dele = _u32.GetWindowThreadProcessId(hwnd, None)
        anexado = bool(_u32.AttachThreadInput(meu, dele, True))
        try:
            _u32.SetForegroundWindow(hwnd)
            _u32.BringWindowToTop(hwnd)
            _u32.SetActiveWindow(hwnd)
        finally:
            if anexado:
                _u32.AttachThreadInput(meu, dele, False)
    except Exception:  # noqa: BLE001
        return False

    fim = time.monotonic() + espera
    while time.monotonic() < fim:
        if em_foco(hwnd):
            time.sleep(0.12)   # deixa a janela assentar antes de receber texto
            return True
        time.sleep(0.02)
    return False
