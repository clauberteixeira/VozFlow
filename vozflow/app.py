"""Aplicacao VozFlow: icone na bandeja, atalhos globais e orquestracao."""

from __future__ import annotations

import datetime as dt
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import keyboard
from PySide6 import QtCore, QtGui, QtWidgets

from . import APP_NAME, __version__, config, janela
from .atalhos import GuardaNumerico, bonito
from .inserter import apertar_enter, copiar, digitar, entregar
from .overlay import Overlay
from .transcriber import LiveTranscriber

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None

RAIZ = Path(__file__).resolve().parent.parent

# Diagnostico temporario: VOZFLOW_DEBUG=1 grava o que acontece com a janela
# alvo num arquivo, para investigar sem console.
_DEBUG = os.environ.get("VOZFLOW_DEBUG")
_DEBUG_LOG = Path(os.environ.get("TEMP", ".")) / "vozflow-debug.txt"


_CARIMBO = re.compile(r"^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] ")


def _txt(s: str) -> str:
    """Texto ditado no log de debug: so com VOZFLOW_DEBUG=texto.

    Com VOZFLOW_DEBUG=1 (o diagnostico normal) vai so o tamanho: o arquivo fica
    esquecido em %TEMP% depois da investigacao, e ditado pode ter senha.
    """
    s = s or ""
    return repr(s) if _DEBUG == "texto" else f"<{len(s)} caracteres>"


def _nome(hwnd: int) -> str:
    """Titulo de janela no log de debug (assunto de e-mail, nome de contato...)."""
    return repr(janela.nome_curto(hwnd)) if _DEBUG == "texto" else "<titulo oculto>"


def _dbg(msg: str) -> None:
    if not _DEBUG:
        return
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            print(time.strftime("%H:%M:%S"), msg, file=f)
    except Exception:
        pass
STARTUP_DIR = (
    Path(os.environ.get("APPDATA", Path.home()))
    / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
)
STARTUP_FILE = STARTUP_DIR / (APP_NAME + ".vbs")

# Teto para esperar a ditada anterior ser entregue antes de aceitar outra. A
# transcricao final de um trecho de 20 s na CPU leva varios segundos; passar
# disto so acontece se algo travou, e ai e melhor voltar a ditar do que o app
# "parar de gravar" para sempre.
PRAZO_ENTREGA_S = 30.0

ACOES = [
    ("paste", "Colar na janela ativa"),
    ("type", "Digitar tecla a tecla"),
    ("clipboard", "So copiar (Ctrl+V manual)"),
    ("webhook", "Enviar para webhook"),
]


# ----------------------------------------------------------------------
# Utilidades de sistema
# ----------------------------------------------------------------------
# Cada som e uma sequencia de (frequencia Hz, duracao ms).
SONS = {
    "iniciar":  [(660, 55), (990, 80)],    # sobe: comecou a ouvir
    "parar":    [(880, 50), (620, 85)],    # desce: parou
    "cancelar": [(520, 60), (330, 120)],   # desce mais e mais grave: descartado
    "entregue": [(1180, 70)],              # toque curto: texto entregue
}
_TAXA_SOM = 44100
_CACHE_SOM: dict[str, bytes] = {}


def _montar_som(notas, volume: float = 0.22) -> bytes:
    """WAV de 16 bits com senoide e envelope suave.

    Antes isto era `winsound.Beep`, que gera onda QUADRADA pelo emulador do
    alto-falante do PC: aspera por natureza (cheia de harmonicos impares) e,
    por comecar e terminar na amplitude cheia, estala nas duas pontas. Saindo
    por um fone Bluetooth o resultado era um chiado - foi a reclamacao real de
    quem usa. Senoide com ataque de 6 ms e queda longa resolve: sem estalo e
    sem harmonico sujo.
    """
    import numpy as np

    partes = []
    for freq, ms in notas:
        n = max(1, int(_TAXA_SOM * ms / 1000))
        i = np.arange(n)
        onda = np.sin(2 * np.pi * freq * i / _TAXA_SOM)
        ataque = np.minimum(i / max(1, int(_TAXA_SOM * 0.006)), 1.0)
        queda = np.minimum((n - i) / max(1, int(n * 0.45)), 1.0)
        partes.append(onda * ataque * queda)
    pcm = np.clip(np.concatenate(partes) * volume, -1.0, 1.0)

    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_TAXA_SOM)
        w.writeframes((pcm * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _duracao_som(nome: str) -> int:
    """Duracao total do som, em ms."""
    return sum(ms for _, ms in SONS.get(nome, []))


def _som(nome: str) -> None:
    """Toca um dos SONS sem travar a interface."""
    if winsound is None:
        return
    try:
        if nome not in _CACHE_SOM:
            _CACHE_SOM[nome] = _montar_som(SONS[nome])
        dados = _CACHE_SOM[nome]  # precisa continuar vivo durante o SND_ASYNC
        winsound.PlaySound(
            dados,
            winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except Exception:  # noqa: BLE001 - som e enfeite, nunca derruba o app
        pass


def _abrir(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not caminho.exists():
        caminho.write_text("", encoding="utf-8")
    if os.name == "nt":
        os.startfile(str(caminho))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(caminho)])


def _pythonw() -> str:
    exe = Path(sys.executable)
    alt = exe.with_name("pythonw.exe")
    return str(alt if alt.exists() else exe)


def startup_ativo() -> bool:
    return STARTUP_FILE.exists()


def set_startup(ativo: bool) -> None:
    if not ativo:
        STARTUP_FILE.unlink(missing_ok=True)
        return
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False):
        alvo = '"""' + sys.executable + '"""'
    else:
        alvo = '"""' + _pythonw() + '"" ""' + str(RAIZ / "main.py") + '"""'
    vbs = (
        "Set s = CreateObject(\"WScript.Shell\")\r\n"
        "s.Run " + alvo + ", 0, False\r\n"
    )
    STARTUP_FILE.write_text(vbs, encoding="utf-8")


def icone(cor: QtGui.QColor) -> QtGui.QIcon:
    """Desenha o microfone da bandeja (sem depender de arquivo externo)."""
    pm = QtGui.QPixmap(64, 64)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(cor)
    p.drawEllipse(2, 2, 60, 60)

    branco = QtGui.QColor(255, 255, 255)
    p.setBrush(branco)
    p.drawRoundedRect(QtCore.QRectF(25, 15, 14, 24), 7, 7)
    caneta = QtGui.QPen(branco, 4)
    caneta.setCapStyle(QtCore.Qt.RoundCap)
    p.setPen(caneta)
    p.setBrush(QtCore.Qt.NoBrush)
    p.drawArc(QtCore.QRectF(19, 22, 26, 24), 200 * 16, 140 * 16)
    p.drawLine(32, 46, 32, 52)
    p.end()
    return QtGui.QIcon(pm)


# ----------------------------------------------------------------------
# Aplicacao
# ----------------------------------------------------------------------
class VozFlow(QtCore.QObject):
    sig_start = QtCore.Signal()
    sig_stop = QtCore.Signal()
    sig_cancel = QtCore.Signal()
    sig_entregue = QtCore.Signal(bool, str, int)
    sig_segurando = QtCore.Signal(bool)

    def __init__(self, app: QtWidgets.QApplication):
        super().__init__()
        self.app = app
        self.cfg = config.load()
        self.overlay = Overlay(self.cfg)
        self.engine = LiveTranscriber(self.cfg)
        self.pronto = False
        self._ultimo_texto = ""
        self._dlg_config = None
        self._backend = ""
        self._ultimo_status = ""
        self._baixando = False
        # Intencao do usuario, nao o estado do motor: `engine.recording` so vira
        # False depois que a transcricao final termina, e um segundo toque na
        # tecla nesse intervalo seria engolido no modo alterna.
        self._quer_gravar = False
        self._inseriu_algo = False
        self._janela_alvo = 0      # HWND onde a ditada comecou
        # A ditada comecou com o foco na bandeja/barra de tarefas (clique no
        # icone): a trava fica na primeira janela de verdade que ganhar foco.
        self._esperar_alvo = False
        self._segurando = False    # texto esperando o foco voltar
        self._falha_foco = ""
        self._enter_pedido = False  # qual par de atalhos disparou esta ditada
        # Entre o parar/cancelar e o fim da entrega, uma nova ditada mexeria na
        # janela alvo e no Enter que a anterior ainda esta usando. Contadores
        # e nao uma flag: o motor manda exatamente um `done` por stop/cancel
        # pedido, entao um `done` que chega sem pedido pendente e de uma
        # ditada velha (ex.: depois do prazo) e e ignorado em vez de ser
        # tomado como o da ditada atual.
        self._dones_pendentes = 0
        self._entregas_ativas = 0
        self._entregando_desde = 0.0
        # Cancelada (ou falhou): o que ainda chegar do motor nao e escrito.
        self._descartando = False
        # Houve erro nesta ditada: o done("") de confirmacao que vem depois
        # nao pode esconder o aviso que acabou de aparecer.
        self._aviso_de_erro = False
        self._historico_podado = 0   # tamanho logo apos a ultima poda
        self._guarda = GuardaNumerico()
        self._fila: queue.Queue = queue.Queue()
        self._thread_insercao = threading.Thread(
            target=self._worker_insercao, daemon=True
        )
        self._thread_insercao.start()

        self._montar_tray()
        self._ligar_sinais()
        self._registrar_atalhos()
        self.engine.start()
        if self.cfg.get("show_overlay", True):
            # roda assim que o loop do Qt comeca, com o modelo ja carregando
            QtCore.QTimer.singleShot(0, self.overlay.preaquecer)

    # -- interface ------------------------------------------------------
    def _montar_tray(self) -> None:
        self.ic_idle = icone(QtGui.QColor(55, 60, 75))
        self.ic_rec = icone(QtGui.QColor(214, 48, 49))
        self.ic_proc = icone(QtGui.QColor(225, 150, 30))

        self.tray = QtWidgets.QSystemTrayIcon(self.ic_idle)
        self.menu = QtWidgets.QMenu()

        self.act_status = self.menu.addAction("Carregando modelo...")
        self.act_status.setEnabled(False)
        self.menu.addSeparator()

        self.act_rec = self.menu.addAction("Iniciar gravacao")
        self.act_rec.triggered.connect(self._iniciar_padrao)
        self.act_parar = self.menu.addAction("Parar e enviar")
        self.act_parar.triggered.connect(self.sig_stop.emit)
        self.act_cancelar = self.menu.addAction("Cancelar gravacao")
        self.act_cancelar.triggered.connect(self.sig_cancel.emit)
        self.menu.addSeparator()

        self.act_config = self.menu.addAction("Configuracoes...")
        self.act_config.triggered.connect(self.abrir_configuracoes)
        self.menu.addSeparator()

        self.menu.addAction("Copiar ultima transcricao").triggered.connect(self._copiar_ultima)
        self.menu.addAction("Abrir historico de transcricoes").triggered.connect(
            lambda: _abrir(config.LOG_PATH)
        )
        self.menu.addSeparator()
        self.menu.addAction("Sair").triggered.connect(self.encerrar)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._clique_tray)
        self._atualizar_dica_atalhos()
        self.tray.show()

    def abrir_configuracoes(self) -> None:
        """Janela unica de ajustes. Aplica tudo na hora, sem reiniciar."""
        from .configuracoes import JanelaConfiguracoes

        if getattr(self, "_dlg_config", None) is not None:
            self._dlg_config.raise_()
            self._dlg_config.activateWindow()
            janela.trazer_para_frente(int(self._dlg_config.winId()))
            return
        if self.engine.recording:
            self.sig_cancel.emit()

        # atalhos desligados durante a edicao: senao testar a tecla dentro da
        # janela comecaria uma gravacao
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        # A previa de posicao escreve direto na cfg para reusar o mesmo codigo
        # do posicionamento definitivo. Guardamos o antes para desfazer no
        # Cancelar - senao mexer no combo e desistir mudaria a config mesmo assim.
        antes_overlay = {
            k: self.cfg.get(k)
            for k in ("overlay_posicao", "overlay_width", "overlay_offset_y")
        }
        dlg = JanelaConfiguracoes(self.cfg, startup_ativo(), overlay=self.overlay)
        self._dlg_config = dlg
        try:
            salvou = dlg.exec() == QtWidgets.QDialog.Accepted
        finally:
            self._dlg_config = None
            self._registrar_atalhos()

        if not salvou:
            self.cfg.update(antes_overlay)
            self.overlay.aplicar_config()
            self.overlay.esconder()
            return
        set_startup(dlg.startup_pedido)
        self._atualizar_dica_atalhos()
        self.overlay.aplicar_config()   # largura e posicao valem na hora
        if self.cfg.get("show_overlay", True):
            self.overlay.preaquecer()
        if dlg.modelo_mudou:
            self.tray.showMessage(
                APP_NAME, "Modelo alterado. Feche e abra o VozFlow para valer.",
                QtWidgets.QSystemTrayIcon.Information, 6000,
            )
        else:
            self.tray.showMessage(
                APP_NAME,
                "Salvo. " + bonito(self.cfg.get("hotkey_start")) + " dita, "
                + bonito(self.cfg.get("hotkey_stop")) + " encerra.",
                QtWidgets.QSystemTrayIcon.Information, 4000,
            )

    def _atualizar_dica_atalhos(self) -> None:
        self.act_rec.setText("Comecar a ditar (" + bonito(self.cfg.get("hotkey_start")) + ")")
        self.act_parar.setText("Encerrar e enviar (" + bonito(self.cfg.get("hotkey_stop")) + ")")
        self.act_cancelar.setText("Cancelar (" + bonito(self.cfg.get("hotkey_cancel")) + ")")
        linhas = [APP_NAME + " " + __version__]
        if self._backend:
            linhas.append(self._backend)
        linhas.append("Ditar: " + bonito(self.cfg.get("hotkey_start"))
                      + (" (envia)" if self.cfg.get("press_enter_after") else ""))
        linhas.append("Encerrar: " + bonito(self.cfg.get("hotkey_stop")))
        if self.cfg.get("hotkey_start2"):
            linhas.append("Ditar (2o): " + bonito(self.cfg.get("hotkey_start2"))
                          + (" (envia)" if self.cfg.get("press_enter_after2") else ""))
        self.tray.setToolTip("\n".join(linhas))

    def _clique_tray(self, motivo) -> None:
        if motivo == QtWidgets.QSystemTrayIcon.Trigger:
            self._alternar()

    # -- sinais ---------------------------------------------------------
    def _ao_segurar(self, segurando: bool) -> None:
        """Worker avisou que o texto esta esperando (ou voltou a fluir).

        Vem por sinal de proposito: mexer em widget Qt fora da thread do Qt
        derruba o processo com STATUS_STACK_BUFFER_OVERRUN, sem traceback.
        """
        if not self._quer_gravar:
            return
        if segurando:
            self.overlay.set_estado("proc")
            if self._esperar_alvo:
                self.overlay.set_texto("Segurando o texto - clique na janela onde ele deve entrar")
                return
            nome = janela.nome_curto(self._janela_alvo) or "a janela original"
            self.overlay.set_texto("Segurando o texto - volte para " + nome)
        else:
            self.overlay.set_estado("rec")

    def _ligar_sinais(self) -> None:
        fila = QtCore.Qt.QueuedConnection
        self.sig_start.connect(self.iniciar, fila)
        self.sig_stop.connect(self.parar, fila)
        self.sig_cancel.connect(self.cancelar, fila)
        self.sig_entregue.connect(self._pos_entrega, fila)
        self.sig_segurando.connect(self._ao_segurar, fila)

        self.engine.ready.connect(self._ao_carregar)
        self.engine.status.connect(self._ao_status)
        self.engine.level.connect(self.overlay.set_nivel)
        self.engine.text.connect(self._ao_texto)
        self.engine.segmento.connect(self._ao_segmento)
        self.engine.done.connect(self._ao_terminar)
        self.engine.baixando.connect(self._ao_baixando)
        self.engine.dica.connect(self._ao_dica)
        self.engine.failed.connect(self._ao_falhar)

    def _registrar_atalhos(self) -> None:
        try:
            keyboard.unhook_all_hotkeys()  # idempotente: permite re-registrar
        except Exception:
            pass
        self._guarda.limpar()  # unhook_all_hotkeys nao mexe nos ganchos de tecla
        # Dois pares independentes. O segundo existe para ter uma tecla que so
        # escreve e outra que escreve e ja envia: cada par carrega a SUA regra
        # de Enter, decidida no momento em que a tecla e apertada.
        pares = []
        for sufixo in ("", "2"):
            ini = self.cfg.get("hotkey_start" + sufixo)
            fim = self.cfg.get("hotkey_stop" + sufixo)
            com_enter = bool(self.cfg.get("press_enter_after" + sufixo))
            if ini and ini == fim:
                pares.append((ini, self._alternador(com_enter)))  # tecla unica alterna
                continue
            if ini:
                pares.append((ini, self._iniciador(com_enter)))
            if fim:
                pares.append((fim, self.sig_stop.emit))
        pares.append((self.cfg.get("hotkey_cancel"), self.sig_cancel.emit))

        # suppress=True impede a tecla de chegar ao programa em foco: necessario
        # quando o atalho e uma tecla solta (PgDn rolaria a pagina junto).
        suprimir = bool(self.cfg.get("suppress_hotkeys"))
        falhas = []
        for combo, alvo in pares:
            if not combo:
                continue
            try:
                sc = self._guarda.vigiar(combo)
                keyboard.add_hotkey(
                    combo, self._acionador(alvo, sc, suprimir), suppress=suprimir
                )
            except Exception as exc:  # noqa: BLE001
                falhas.append(combo + " (" + str(exc) + ")")
        if falhas:
            self.tray.showMessage(
                APP_NAME, "Nao consegui registrar: " + ", ".join(falhas),
                QtWidgets.QSystemTrayIcon.Warning, 6000,
            )

    def _acionador(self, alvo, sc, suprimir: bool):
        """Envolve o atalho com o filtro do teclado numerico.

        O retorno decide a supressao: True deixa a tecla seguir para o programa
        em foco, False engole. Por isso o Num 3 continua digitando "3" mesmo
        com "Reservar a tecla" ligado - ele nem chega a acionar o VozFlow.
        """
        def acionar():
            if not self._guarda.liberado(sc):
                return True
            alvo()
            return not suprimir
        return acionar

    def _iniciador(self, com_enter: bool):
        """Handler que lembra se ESTE atalho deve enviar no fim."""
        def acao():
            self._enter_pedido = com_enter
            self.sig_start.emit()
        return acao

    def _alternador(self, com_enter: bool):
        """Tecla unica: primeiro toque grava, segundo encerra."""
        def acao():
            if self._quer_gravar:
                self.sig_stop.emit()
            else:
                self._enter_pedido = com_enter
                self.sig_start.emit()
        return acao

    def _iniciar_padrao(self) -> None:
        """Menu e clique na bandeja seguem a regra do atalho principal."""
        self._enter_pedido = bool(self.cfg.get("press_enter_after"))
        self.sig_start.emit()

    def _alternar(self) -> None:
        if self._quer_gravar:
            self.sig_stop.emit()
        else:
            self._iniciar_padrao()

    # -- acoes ----------------------------------------------------------
    def iniciar(self) -> None:
        if self._quer_gravar:
            return
        if not self.pronto:
            # Mostrar o progresso real, nao um "aguarde" generico: na primeira
            # vez e o modelo baixando, e sem numero nenhum o app parece travado.
            msg = self._ultimo_status or "Preparando o VozFlow..."
            if self._baixando:
                msg += "   -  so na primeira vez"
            self.overlay.flash(msg, "proc", 3500)
            return
        if self._entregando:
            # A anterior ainda usa a janela alvo e a regra de Enter: comecar
            # agora mandaria o fim dela para a janela desta (com o Enter desta).
            if time.monotonic() - self._entregando_desde < PRAZO_ENTREGA_S:
                self.overlay.flash("Terminando de entregar a ditada anterior...", "proc", 1500)
                return
            _dbg("PRAZO de entrega estourado; liberando nova ditada")
            # zerados: o que ainda vier da ditada velha passa a ser ignorado
            self._dones_pendentes = 0
            self._entregas_ativas = 0
        self._quer_gravar = True
        self._descartando = False
        self._aviso_de_erro = False
        self._inseriu_algo = False
        self._segurando = False
        self._falha_foco = ""
        # A janela tem de ser capturada AGORA, antes do som e de qualquer
        # espera: e neste instante que ela ainda e a que voce escolheu. O
        # overlay nunca rouba foco (Qt.Tool + WA_ShowWithoutActivating), entao
        # o que se captura aqui e a sua janela de verdade - exceto quando a
        # ditada sai de um clique na bandeja: ai o foco e da barra de tarefas
        # (ou do menu do proprio VozFlow), e a trava espera a proxima janela.
        alvo = janela.atual() if self.cfg.get("travar_janela", True) else 0
        self._esperar_alvo = bool(alvo) and not janela.alvo_valido(alvo)
        self._janela_alvo = 0 if self._esperar_alvo else alvo
        _dbg(f"INICIAR alvo={hex(self._janela_alvo)} {_nome(self._janela_alvo)} "
             f"travar={self.cfg.get('travar_janela')} esperar_alvo={self._esperar_alvo} "
             f"ao_vivo={self._ao_vivo} enter={self._enter_pedido}")
        if self.cfg.get("sounds"):
            _som("iniciar")
            # O fone Bluetooth troca de A2DP para HFP no instante em que o
            # microfone abre, e essa troca corta qualquer som que esteja
            # tocando - era o segundo motivo do "ruido" no comeco da gravacao.
            # Esperar o toque acabar resolve, e 145 ms nao se percebe: ninguem
            # comeca a falar tao rapido depois de apertar a tecla.
            QtCore.QTimer.singleShot(
                _duracao_som("iniciar") + 10, self._comecar_de_fato
            )
        else:
            self.engine.cmd_start()
        self.tray.setIcon(self.ic_rec)
        self.overlay.mostrar("rec", "Ouvindo...")

    def _comecar_de_fato(self) -> None:
        """Abre o microfone, se a pessoa nao desistiu durante o toque.

        Um `stop` que chegue antes disto e descartado pelo motor (ele so para
        se ja estiver gravando), entao sem esta checagem a gravacao ficaria
        ligada para sempre.
        """
        if self._quer_gravar:
            self.engine.cmd_start()

    def parar(self) -> None:
        if not self._quer_gravar:
            return
        self._quer_gravar = False
        self._pedir_done()
        if self.cfg.get("sounds"):
            _som("parar")
        self.tray.setIcon(self.ic_proc)
        self.overlay.set_estado("proc")
        self.engine.cmd_stop()

    def cancelar(self) -> None:
        if not self._quer_gravar:
            return
        self._quer_gravar = False
        self._pedir_done()
        self._descartar()
        if self.cfg.get("sounds"):
            _som("cancelar")
        self.engine.cmd_cancel()
        self.tray.setIcon(self.ic_idle)
        self.overlay.flash("Gravacao cancelada", "erro", 1200)

    @property
    def _entregando(self) -> bool:
        return self._dones_pendentes > 0 or self._entregas_ativas > 0

    def _pedir_done(self) -> None:
        """Anota um stop/cancel enviado ao motor: ele responde com um `done`."""
        if not self._entregando:
            self._entregando_desde = time.monotonic()
        self._dones_pendentes += 1

    def _descartar(self) -> None:
        """Joga fora o texto que ainda nao saiu - e o que ainda vier do motor.

        Sem isto, o texto segurado (foco fora) de uma ditada cancelada saia
        depois, ou na janela da ditada seguinte, com o Enter dela.
        """
        self._descartando = True
        self._fila.put(("", "descartar", ""))

    # -- reacoes do motor ------------------------------------------------
    def _ao_carregar(self, backend: str) -> None:
        self.pronto = True
        self._backend = backend
        self.act_status.setText("Pronto - " + backend)
        self._atualizar_dica_atalhos()
        self.tray.showMessage(
            APP_NAME,
            "Pronto. " + bonito(self.cfg.get("hotkey_start")) + " grava, "
            + bonito(self.cfg.get("hotkey_stop")) + " envia.",
            QtWidgets.QSystemTrayIcon.Information, 4000,
        )

    def _ao_status(self, msg: str) -> None:
        if self.pronto:
            return
        self._ultimo_status = msg
        self.act_status.setText(msg)
        if self._baixando:
            self.overlay.set_texto(msg + "   -  so na primeira vez")

    def _ao_baixando(self, baixando: bool) -> None:
        """Primeira execucao: o download do modelo precisa aparecer sozinho."""
        self._baixando = baixando
        if baixando:
            self.tray.showMessage(
                APP_NAME,
                "Baixando o modelo de transcricao. Isso acontece uma "
                "unica vez; o VozFlow avisa quando estiver pronto.",
                QtWidgets.QSystemTrayIcon.Information, 10000,
            )
            self.tray.setIcon(self.ic_proc)
            self.overlay.mostrar("proc", "Baixando o modelo de transcricao...")
        else:
            self.tray.setIcon(self.ic_idle)
            self.overlay.esconder()

    def _ao_texto(self, texto: str, _final: bool) -> None:
        if not self.engine.recording:
            return
        # Ditada pela bandeja: a trava pega a primeira janela de verdade que
        # ganhar foco DURANTE a fala. Sem isto, fora do modo ao vivo (o worker
        # nao roda) e parando tambem pela bandeja, o foco no fim e de novo a
        # barra de tarefas e o texto so ia para a area de transferencia.
        if self._esperar_alvo:
            self._resolver_alvo()
        # Enquanto o texto esta esperando o foco voltar, o aviso do _ao_segurar
        # era apagado pela primeira frase nova e a janelinha voltava a parecer
        # normal - dando a impressao de que a ditada tinha parado. O aviso anda
        # junto com o texto ate o foco voltar.
        if self._segurando:
            nome = ("a janela que voce clicar" if self._esperar_alvo
                    else janela.nome_curto(self._janela_alvo, 22) or "a janela original")
            texto = "[segurando p/ " + nome + "]  " + texto
        self.overlay.set_texto(texto)

    # -- insercao ao vivo -------------------------------------------------
    @property
    def _ao_vivo(self) -> bool:
        """So faz sentido escrever ao vivo quando o destino e a janela em foco."""
        return (
            bool(self.cfg.get("insercao_ao_vivo", True))
            and (self.cfg.get("action_on_stop") or "paste").lower() in ("paste", "type")
        )

    # A area de transferencia so e restaurada por inserter.colar(), o unico
    # caminho que a usa como meio de transporte. Antes o app tambem restaurava
    # ao fim de toda ditada, e isso desfazia o "So copiar", recolocava o
    # conteudo antigo antes do Ctrl+V ser lido e apagava o que a pessoa
    # copiasse durante a fala (ou a formatacao do que ja estava copiado).

    def _worker_insercao(self) -> None:
        """Escreve o texto num fluxo continuo, nao em blocos.

        O motor entrega as palavras em rajadas: 2 ou 3 de uma vez a cada
        `partial_interval`, com pausa maior quando a frase fecha. Colar cada
        rajada de uma vez fazia o texto saltar e dar impressao de travamento.

        Aqui as letras vao para um buffer e saem em doses pequenas a cada 25 ms,
        num ritmo que se adapta ao tamanho da fila: com pouco acumulado escreve
        devagar, com muito acelera, e nunca fica para tras.
        """
        TICK = 0.025
        pendente = ""
        credito = 0.0           # letras "devidas" acumuladas entre os ticks
        enviado = ""            # so com VOZFLOW_DEBUG: tudo que saiu pelo teclado

        while True:
            try:
                item = self._fila.get(timeout=TICK if pendente else None)
            except queue.Empty:
                item = ...       # nada novo: so continua escrevendo o que ha

            if item is None:
                break
            if item is not ...:
                # acao: False | "fim" | True (fim+Enter) | "descartar"
                # completo: texto final da ditada, para copiar se o foco falhar
                trecho, acao, completo = item
                if trecho:
                    pendente += trecho
                if acao == "descartar":
                    pendente = ""
                    credito = 0.0
                    enviado = ""
                elif acao:
                    # Fim da ditada: traz de volta a janela onde tudo comecou,
                    # solta o que sobrou e, se pedido, aperta Enter. O digitar()
                    # espera os modificadores do atalho serem soltos antes.
                    #
                    # Tudo protegido: este e o unico ponto que chama `task_done`,
                    # entao uma excecao solta aqui derrubava a thread inteira -
                    # o `_fila.join()` esperava para sempre e, pior, NENHUMA
                    # ditada seguinte voltava a ser escrita, porque o worker nao
                    # existia mais. Foi exatamente o "parou de gravar".
                    self._falha_foco = ""
                    try:
                        ok_foco = True
                        self._resolver_alvo()   # ditada pela bandeja sem texto ao vivo
                        if self._janela_alvo:
                            ok_foco = janela.restaurar(self._janela_alvo)
                            _dbg(f"FIM restaurar({hex(self._janela_alvo)})={ok_foco} "
                                 f"pendente={len(pendente)} acao={acao!r}")
                        elif self._esperar_alvo:
                            ok_foco = False   # nenhuma janela de verdade recebeu foco
                        if not ok_foco:
                            self._falha_foco = "a janela original nao voltou ao foco"
                            # Sem foco confirmado nao se digita as cegas: com
                            # "apertar Enter" ligado isso mandaria a mensagem na
                            # janela errada. Vai o texto INTEIRO, nao so a sobra:
                            # e o que a mensagem "texto copiado" promete.
                            copiar(completo or pendente)
                        elif pendente:
                            digitar(pendente)
                        if acao is True and ok_foco:
                            apertar_enter()
                        # Comparar isto com o texto em transcricoes.txt diz se a
                        # perda foi no envio ou no app de destino.
                        _dbg(f"ENVIADO {_txt(enviado + pendente)}")
                    except Exception as exc:  # noqa: BLE001
                        _dbg(f"FIM falhou: {exc!r}")
                        self._falha_foco = self._falha_foco or str(exc)
                    finally:
                        # Some com o resto pendente mesmo em caso de erro: sobra
                        # dele seria digitada na proxima ditada, noutra janela.
                        pendente = ""
                        credito = 0.0
                        enviado = ""
                self._fila.task_done()

            if not pendente:
                continue
            # Cancelou: vale na hora, sem esperar o marcador atravessar a fila
            # (trechos enfileirados antes dele sairiam numa rajada).
            if self._descartando:
                pendente = ""
                credito = 0.0
                continue
            # Janela travada: enquanto o foco esta fora, o texto ESPERA aqui.
            # Escrever agora jogaria o resto da ditada na janela errada - era
            # exatamente o problema. Escrever na janela de fundo nao e opcao:
            # o Chromium ignora input sintetico de outro processo (ver janela.py).
            if not self._pode_escrever():
                time.sleep(TICK)
                continue
            # Ctrl/Alt ainda presos (o usuario acabou de apertar o atalho)
            # transformariam as letras em combinacoes. Espera soltar.
            if any(keyboard.is_pressed(m) for m in ("ctrl", "alt")):
                time.sleep(TICK)
                continue
            # Espalha o buffer ao longo do intervalo em que a proxima leva de
            # palavras costuma chegar. Sem o credito fracionario, poucas letras
            # saiam em 2 ou 3 ticks e o texto parava ate a leva seguinte -
            # exatamente o "engasgo no meio da frase" que aparecia na medicao.
            # NAO chamar esta variavel de `janela`: o modulo `janela` e usado
            # nesta mesma funcao, e uma atribuicao aqui o torna local em todo o
            # corpo dela - `janela.restaurar()` la em cima vira `float.restaurar`.
            ritmo = max(6.0, float(self.cfg.get("partial_interval", 0.45)) / TICK)
            credito += len(pendente) / ritmo
            if credito >= 1.0:
                n = int(credito)
                credito -= n
                dose, pendente = pendente[:n], pendente[n:]
                try:
                    keyboard.write(dose, delay=0)
                    if _DEBUG:
                        enviado += dose
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(TICK)

    def _resolver_alvo(self) -> bool:
        """Ditada pela bandeja: trava na janela em foco agora, se for de verdade."""
        if not self._esperar_alvo:
            return True
        atual = janela.atual()
        if atual and janela.alvo_valido(atual):
            _dbg(f"TRAVOU em {hex(atual)} {_nome(atual)} (ditada pela bandeja)")
            self._janela_alvo = atual
            self._esperar_alvo = False
            return True
        return False

    def _pode_escrever(self) -> bool:
        """True quando o foco esta na janela alvo (ou nao ha alvo travado)."""
        if not self._resolver_alvo():
            if not self._segurando:
                self._segurando = True
                self.sig_segurando.emit(True)
            return False
        alvo = self._janela_alvo
        if not alvo:
            return True
        if not janela.existe(alvo):     # fecharam a janela no meio da ditada
            self._janela_alvo = 0
            return True
        if janela.em_foco(alvo):
            if self._segurando:
                _dbg("RETOMOU: foco voltou ao alvo")
                self._segurando = False
                self.sig_segurando.emit(False)
            return True
        if not self._segurando:
            _dbg(f"SEGURANDO: foco esta em {hex(janela.atual())} "
                 f"{_nome(janela.atual())}, alvo e {hex(alvo)}")
            self._segurando = True
            self.sig_segurando.emit(True)
        return False

    def _ao_segmento(self, trecho: str) -> None:
        """Trecho fechou: escreve ele no campo em foco, ainda durante a fala."""
        trecho = (trecho or "").strip()
        _dbg(f"SEGMENTO {_txt(trecho)} ao_vivo={self._ao_vivo}")
        # NAO usar _quer_gravar aqui: o parar() o desliga antes de o motor
        # mandar o ultimo trecho, e o fim de toda ditada sumiria.
        if not trecho or not self._ao_vivo or self._descartando:
            return
        self._fila.put(((" " if self._inseriu_algo else "") + trecho, False, ""))
        self._inseriu_algo = True

    # -- fim da gravacao ---------------------------------------------------
    def _ao_terminar(self, texto: str) -> None:
        if self._dones_pendentes <= 0:
            # Ninguem pediu: e de uma ditada velha (depois do prazo de entrega).
            # Trata-la como da atual a descartaria, ou entregaria o texto velho
            # na janela e com o Enter da nova.
            _dbg(f"DONE sem pedido pendente, ignorado: {_txt(texto)}")
            return
        self._dones_pendentes -= 1
        self.tray.setIcon(self.ic_idle)
        texto = (texto or "").strip()
        if self._descartando or not texto:
            # Cancelada, falhou ou nao saiu nada: o que estiver no buffer nao
            # pode escapar depois, nem na proxima ditada.
            descartada = self._descartando
            self._descartar()
            if not descartada and not self._aviso_de_erro:
                self.overlay.esconder()   # cancelar/falha deixam o aviso na tela
            return
        self._ultimo_texto = texto
        self._registrar_log(texto)
        self.overlay.mostrar("proc", texto)
        self._entregas_ativas += 1        # volta a zero no _pos_entrega

        if self._ao_vivo:
            # O texto ja foi saindo enquanto o usuario falava. Este marcador
            # esvazia o que restou no buffer e, se pedido, aperta Enter - e faz
            # o _fila.join() esperar ate a ultima letra estar na tela.
            self._fila.put(("", True if self._enter_pedido else "fim", texto))
            threading.Thread(target=self._finalizar_ao_vivo,
                             args=(len(texto),), daemon=True).start()
        else:
            threading.Thread(target=self._entregar, args=(texto,), daemon=True).start()

    def _finalizar_ao_vivo(self, tamanho: int) -> None:
        self._fila.join()          # espera a fila esvaziar
        if self._falha_foco:
            self.sig_entregue.emit(
                False, self._falha_foco + "; texto copiado", tamanho
            )
            return
        onde = janela.nome_curto(self._janela_alvo)
        self.sig_entregue.emit(
            True, "escrito em " + onde if onde else "escrito ao vivo", tamanho
        )

    def _entregar(self, texto: str) -> None:
        acao = (self.cfg.get("action_on_stop") or "paste").lower()
        # Volta para a janela onde a ditada comecou antes de colar ou digitar.
        # Sem foco confirmado nao se cola nem se aperta Enter: iria para a
        # janela errada. Webhook e "So copiar" nao escrevem em janela nenhuma,
        # entao nem dependem do foco nem o roubam.
        if acao in ("paste", "type"):
            self._resolver_alvo()   # ditada pela bandeja: vale a janela em foco agora
            sem_alvo = self._esperar_alvo or (
                self._janela_alvo and not janela.restaurar(self._janela_alvo))
            if sem_alvo:
                copiar(texto)
                self.sig_entregue.emit(
                    False, "a janela original nao voltou ao foco; texto copiado", len(texto)
                )
                return
        try:
            ok, detalhe = entregar(self.cfg, texto, enter=self._enter_pedido)
        except Exception as exc:  # noqa: BLE001
            ok, detalhe = False, str(exc)
        if not ok and acao != "clipboard" and copiar(texto):
            detalhe += "; texto copiado"
        self.sig_entregue.emit(ok, detalhe, len(texto))

    def _pos_entrega(self, ok: bool, detalhe: str, tamanho: int) -> None:
        self._entregas_ativas = max(0, self._entregas_ativas - 1)
        if ok:
            if self.cfg.get("sounds"):
                _som("entregue")
            self.overlay.flash(
                str(tamanho) + " caracteres - " + detalhe, "done", 1500
            )
        else:
            self.overlay.flash("Falhou: " + detalhe, "erro", 4000)

    def _ao_dica(self, msg: str) -> None:
        """Aviso durante a gravacao, sem interromper nada."""
        if self.engine.recording:
            self.overlay.set_estado("proc")
            self.overlay.set_texto(msg)

    def _ao_falhar(self, msg: str) -> None:
        self._aviso_de_erro = True
        if self._quer_gravar:
            # Falhou no meio da ditada. So enquanto a pessoa ainda dita: depois
            # do parar, o motor ja esta encerrando sozinho e o texto final dele
            # ainda vale. O texto pendente sai fora - sem marcador de fim, ele
            # ficaria no buffer e sairia na proxima ditada, noutra janela.
            self._descartar()
            if self.engine.recording:
                # Ex.: GPU sem memoria numa parcial: o motor seguiria gravando
                # e mandando trechos, com parar e cancelar ja ignorados aqui.
                self._pedir_done()
                self.engine.cmd_cancel()
        self._quer_gravar = False
        self._baixando = False
        self.act_status.setText("Erro: " + msg)
        self.tray.showMessage(APP_NAME, msg,
                              QtWidgets.QSystemTrayIcon.Critical, 15000)
        self.tray.setIcon(self.ic_idle)
        self.overlay.flash(msg, "erro", 5000)

    def _registrar_log(self, texto: str) -> None:
        if not self.cfg.get("log_transcricoes"):
            return
        try:
            config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            carimbo = dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            with config.LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write("[" + carimbo + "] " + texto + "\n")
        except OSError:
            return
        # Depois da entrega, nunca antes: a primeira poda de um arquivo grande
        # le linha a linha e atrasaria o texto chegando na janela.
        QtCore.QTimer.singleShot(0, self._podar_historico)

    def _podar_historico(self) -> None:
        """Passou de `historico_max_mb`: fica so com os ultimos `historico_dias`.

        Sem limite, o arquivo crescia para sempre com tudo que foi ditado. A
        regra e "guardar tudo enquanto for pequeno": 5 MB sao anos de uso, e
        so ai entra a limpeza para a ultima semana.
        """
        tmp = config.LOG_PATH.with_name(config.LOG_PATH.name + ".tmp")
        try:
            limite = float(self.cfg.get("historico_max_mb", 5)) * 1024 * 1024
            tamanho = config.LOG_PATH.stat().st_size
            # So a ultima semana ja passa do limite: nao rele e regrava o
            # arquivo inteiro a cada ditada - espera crescer 10% de novo.
            if limite <= 0 or tamanho <= max(limite, 1.1 * self._historico_podado):
                return
            # teto de 100 anos: um "nunca apagar" de 10**12 dias estourava o timedelta
            dias = min(36500, max(1, int(self.cfg.get("historico_dias", 7))))
            corte = dt.datetime.now() - dt.timedelta(days=dias)
            try:
                texto = config.LOG_PATH.read_bytes().decode("utf-8-sig")
            except UnicodeDecodeError:
                # salvo a mao em outra codificacao: nao reescreve - e nao tenta
                # de novo a cada ditada ate o arquivo crescer 10%
                self._historico_podado = tamanho
                return
            manter, guardar = [], True
            for linha in texto.splitlines(keepends=True):
                m = _CARIMBO.match(linha)
                if m:
                    try:
                        guardar = dt.datetime.strptime(
                            m.group(1), "%d/%m/%Y %H:%M:%S") >= corte
                    except ValueError:
                        guardar = True
                # linha sem carimbo e continuacao da anterior: vai junto
                if guardar:
                    manter.append(linha)
            novo = "".join(manter)
            # mesmo cuidado do config.json: dados no disco antes da troca
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write(novo)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, config.LOG_PATH)
            self._historico_podado = len(novo.encode("utf-8"))
        except (OSError, ValueError, TypeError, OverflowError):
            try:
                tmp.unlink(missing_ok=True)   # sem sobra com a ultima semana de ditados
            except OSError:
                pass

    def _copiar_ultima(self) -> None:
        if self._ultimo_texto:
            QtWidgets.QApplication.clipboard().setText(self._ultimo_texto)
            self.overlay.flash("Ultima transcricao copiada", "done", 1400)

    # -- saida -----------------------------------------------------------
    def encerrar(self) -> None:
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._guarda.limpar()
        self._fila.put(None)
        self.engine.cmd_quit()
        parou = self.engine.wait(4000)
        self.overlay.esconder()
        self.tray.hide()
        if not parou:
            # O motor nao le comandos enquanto baixa o modelo ou transcreve um
            # trecho longo. Seguir com app.quit() destruiria a QThread viva
            # ("QThread: Destroyed while thread is still running") e o processo
            # caia na saida. A config ja esta salva; o download retoma depois.
            _dbg("SAIR: motor nao parou em 4 s; encerrando o processo")
            # Antes de cortar: o worker termina o que esta digitando (um Ctrl+V
            # cortado no meio podia deixar o Ctrl logico preso) e o Timer do
            # colar() devolve a area de transferencia de quem usa.
            self._thread_insercao.join(timeout=1.5)
            for t in threading.enumerate():
                if isinstance(t, threading.Timer):
                    t.join(timeout=1.0)
            os._exit(0)
            return
        self.app.quit()
