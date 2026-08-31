"""Captura e validacao de combinacoes de teclas, usadas na tela de configuracoes."""

from __future__ import annotations

import re
import threading

import keyboard
from PySide6 import QtCore, QtWidgets

MODIFICADORES = {"ctrl", "alt", "shift", "windows"}

# Teclas praticamente nunca usadas no dia a dia: servem bem como atalho sozinho.
SEGURAS_SOZINHAS = {
    "scroll lock", "pause", "print screen", "menu",
    "play/pause media", "next track", "previous track", "stop media",
    "browser back", "browser forward",
}

# Teclas de navegacao. Nao aparecem ao digitar texto, mas sao apertadas o tempo
# todo para rolar e mover o cursor - usar uma delas sozinha faz o VozFlow ligar
# "do nada". Foi exatamente o que aconteceu com PgDn no primeiro uso real.
NAVEGACAO = {
    "page up", "page down", "home", "end", "insert", "delete",
    "up", "down", "left", "right", "num lock",
}

BONITO = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "windows": "Win",
    "esc": "Esc", "enter": "Enter", "space": "Espaco", "tab": "Tab",
    "page up": "PgUp", "page down": "PgDn", "caps lock": "CapsLock",
}

PADROES = {
    "hotkey_start": "ctrl+alt+g",
    "hotkey_stop": "ctrl+alt+s",
    "hotkey_cancel": "ctrl+alt+x",
}


def _scancodes_do_numerico() -> set[int]:
    """Scancodes que o teclado numerico divide com o bloco de navegacao.

    PgDn e Num 3 chegam ao Windows com o MESMO scancode (81); o que separa os
    dois e o flag de tecla estendida. A lib `keyboard` casa atalho olhando so
    o scancode, entao registrar "page down" fazia o Num 3 ligar o VozFlow no
    meio de qualquer numero digitado. Vale para o bloco inteiro: End/Num 1,
    Delete/Num ., Enter/Num Enter e as setas.
    """
    try:
        from keyboard._winkeyboard import keypad_keys
    except Exception:  # noqa: BLE001 - outra plataforma: nada a vigiar
        return set()
    return {entrada[0] for entrada in keypad_keys}


SCANCODES_NUMERICO = _scancodes_do_numerico()


def _scancode_principal(combo: str) -> int | None:
    """Scancode da tecla que dispara o combo (a que nao e modificador)."""
    partes = [p for p in combo.split("+")
              if p.replace("right ", "") not in MODIFICADORES]
    if len(partes) != 1:
        return None
    try:
        codigos = keyboard.key_to_scan_codes(partes[0])
    except Exception:  # noqa: BLE001
        return None
    # 'page down' -> (81,). Nomes com mais de um scancode ('3' -> (4, 81)) sao
    # teclas de digitacao: ali o numerico disparar e o comportamento certo.
    return codigos[0] if len(codigos) == 1 else None


class GuardaNumerico:
    """Impede que a tecla gemea do teclado numerico dispare o atalho.

    O evento do Windows carrega `is_keypad`, que separa PgDn (bloco de
    navegacao) de Num 3 mesmo os dois tendo o mesmo scancode. Aqui anotamos o
    ultimo evento de cada tecla vigiada, e o atalho consulta essa anotacao
    antes de disparar.

    A ordem e garantida pela propria lib: ganchos de tecla ficam em
    `blocking_keys`, processados antes dos atalhos tanto no caminho com
    supressao quanto no sem - os dois passam por `direct_callback`.
    """

    def __init__(self) -> None:
        self._do_numerico: dict[int, bool] = {}
        self._remover: list = []

    def vigiar(self, combo: str) -> int | None:
        """Passa a observar a tecla do combo. Devolve o scancode vigiado, ou
        None quando essa tecla nao tem gemea no teclado numerico."""
        sc = _scancode_principal(combo)
        if sc is None or sc not in SCANCODES_NUMERICO:
            return None
        if sc not in self._do_numerico:
            self._do_numerico[sc] = False
            try:
                self._remover.append(keyboard.hook_key(
                    sc, lambda evt, s=sc: self._anotar(s, evt), suppress=True))
            except Exception:  # noqa: BLE001
                del self._do_numerico[sc]
                return None
        return sc

    def _anotar(self, sc: int, evento) -> bool:
        self._do_numerico[sc] = bool(getattr(evento, "is_keypad", False))
        return True  # so anota: devolver True deixa a tecla seguir normalmente

    def liberado(self, sc: int | None) -> bool:
        """True quando o ultimo evento dessa tecla NAO veio do numerico."""
        return sc is None or not self._do_numerico.get(sc, False)

    def limpar(self) -> None:
        for remover in self._remover:
            try:
                remover()
            except Exception:  # noqa: BLE001
                pass
        self._remover.clear()
        self._do_numerico.clear()


def bonito(combo: str) -> str:
    if not combo:
        return "(desativado)"
    return " + ".join(BONITO.get(p, p.upper() if len(p) == 1 else p.capitalize())
                      for p in combo.split("+"))


def _segura_sozinha(tecla: str) -> bool:
    return tecla in SEGURAS_SOZINHAS or bool(re.fullmatch(r"f\d{1,2}", tecla))


def validar(valores: dict, suprimir: bool = False) -> tuple[str, str]:
    """Devolve (erro, aviso). So o erro impede salvar."""
    if not valores.get("hotkey_start") or not valores.get("hotkey_stop"):
        return "Iniciar e parar precisam de uma combinacao.", ""

    ini2, fim2 = valores.get("hotkey_start2"), valores.get("hotkey_stop2")
    if bool(ini2) != bool(fim2):
        return ("O segundo atalho precisa das duas combinacoes - iniciar e "
                "encerrar - ou de nenhuma das duas."), ""

    # Um combo nao pode servir a dois papeis. Iniciar e encerrar do MESMO par
    # podem ser iguais: e assim que a tecla unica vira alterna.
    par1 = {valores["hotkey_start"], valores["hotkey_stop"]}
    par2 = {c for c in (ini2, fim2) if c}
    cancelar = valores.get("hotkey_cancel")
    if par1 & par2:
        return ("Os dois atalhos de ditar precisam ser diferentes entre si, "
                "senao nao da para saber qual deve enviar."), ""
    if cancelar and cancelar in (par1 | par2):
        return "O atalho de cancelar precisa ser diferente dos outros.", ""

    avisos = []
    tem_solta = False
    for combo in valores.values():
        if not combo:
            continue
        partes = combo.split("+")
        mods = {p for p in partes if p.replace("right ", "") in MODIFICADORES}
        teclas = [p for p in partes if p not in mods]
        tem_solta = tem_solta or not mods

        # Alt+Shift e o atalho do Windows para trocar o layout do teclado: o
        # sistema consome o evento e ele nunca chega ate o VozFlow. Isso e erro,
        # porque o atalho ficaria morto sem o usuario perceber.
        if mods == {"alt", "shift"}:
            return ("Alt + Shift e reservado pelo Windows para trocar o idioma do "
                    "teclado e nao chega ate aqui. Escolha outra combinacao."), ""

        if not mods:
            if all(t in NAVEGACAO for t in teclas):
                avisos.append(
                    "Voce usa '" + bonito(combo) + "' para rolar e mover o cursor: "
                    "o VozFlow vai ligar sozinho toda vez. So vale a pena se essa "
                    "tecla vier de um controle remoto que voce nao usa para mais nada."
                )
            elif not all(_segura_sozinha(t) for t in teclas):
                avisos.append(
                    "'" + bonito(combo) + "' e uma tecla usada ao digitar: ela vai "
                    "disparar o VozFlow no meio de qualquer texto que voce escrever."
                )

    if tem_solta and not suprimir:
        avisos.append(
            "Tecla sem modificador continua fazendo a funcao normal dela ao "
            "mesmo tempo. Marque 'Reservar a tecla' para o VozFlow ficar com ela."
        )
    unicos = list(dict.fromkeys(avisos))  # start e stop iguais = mesmo aviso
    return "", "  ".join(unicos)


class CapturaAtalho(QtWidgets.QPushButton):
    """Botao que, ao ser clicado, grava a proxima combinacao de teclas."""

    capturado = QtCore.Signal(str)

    def __init__(self, combo: str, parent=None):
        super().__init__(parent)
        self.combo = (combo or "").strip()
        self._capturando = False
        self.setMinimumWidth(230)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.clicked.connect(self._comecar)
        self.capturado.connect(self._aplicar)
        self._pintar()

    def _pintar(self) -> None:
        self.setText(bonito(self.combo))
        self.setStyleSheet("")

    def _comecar(self) -> None:
        if self._capturando:
            return
        self._capturando = True
        self.setText("Pressione a combinacao...  (Esc cancela)")
        self.setStyleSheet("font-weight:bold;")
        threading.Thread(target=self._ler, daemon=True).start()

    def _ler(self) -> None:
        try:
            combo = keyboard.read_hotkey(suppress=False)
        except Exception:  # noqa: BLE001
            combo = ""
        self.capturado.emit(combo or "")

    def _aplicar(self, combo: str) -> None:
        self._capturando = False
        if combo and combo.lower() not in ("esc", "escape"):
            self.combo = combo.lower()
        self._pintar()
