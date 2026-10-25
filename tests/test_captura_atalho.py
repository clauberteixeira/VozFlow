"""Captura de atalho e teclas presas (vozflow/atalhos.py).

Caso real: o usuario apertou so PgDn e a tela gravou "F10 + PgDn". O
read_hotkey da biblioteca keyboard monta a combinacao com tudo que ela acha
que esta apertado, e um F10 cujo "soltar" o Windows perdeu ficou preso.
Nada aqui usa o teclado real: os eventos e o estado do Windows sao falsos.
"""

import threading
from types import SimpleNamespace

from vozflow import atalhos as atl

DOWN, UP = atl.keyboard.KEY_DOWN, atl.keyboard.KEY_UP


def _fila(*eventos):
    itens = iter(SimpleNamespace(event_type=t, name=n) for t, n in eventos)
    return lambda: next(itens)


def test_tecla_sozinha_vira_so_ela():
    assert atl.ler_combinacao(_fila((DOWN, "page down"))) == "page down"


def test_tecla_presa_de_antes_nao_entra():
    """O F10 preso nao gera evento nenhum depois do clique: fica de fora."""
    assert atl.ler_combinacao(_fila((UP, "f10"), (DOWN, "page down"))) == "page down"


def test_modificador_segurado_entra():
    assert atl.ler_combinacao(_fila((DOWN, "left ctrl"), (DOWN, "alt"), (DOWN, "x"))) == "ctrl+alt+x"


def test_modificador_que_ja_foi_solto_nao_entra():
    assert atl.ler_combinacao(_fila((DOWN, "ctrl"), (UP, "ctrl"), (DOWN, "page up"))) == "page up"


def test_modificador_sozinho_nao_fecha_a_captura():
    """Ctrl + Alt sem tecla nao funciona como atalho: espera a tecla de verdade."""
    assert atl.ler_combinacao(_fila((DOWN, "ctrl"), (DOWN, "alt"), (UP, "alt"),
                                    (DOWN, "x"))) == "ctrl+x"


def test_esc_cancela_mesmo_com_modificador():
    assert atl.ler_combinacao(_fila((DOWN, "ctrl"), (DOWN, "esc"))) == "esc"


def test_repeticao_do_modificador_nao_duplica():
    assert atl.ler_combinacao(_fila((DOWN, "left windows"), (DOWN, "left windows"),
                                    (DOWN, "h"))) == "windows+h"


def test_soltar_do_clique_nao_fecha_a_captura():
    """O read_hotkey fechava no primeiro "soltar" - o da tecla que abriu a captura."""
    assert atl.ler_combinacao(_fila((UP, "space"), (UP, "enter"), (DOWN, "f9"))) == "f9"


# ----------------------------------------------------------------------
# teclas presas na tabela do keyboard
# ----------------------------------------------------------------------
AGORA = 1000.0


def _teclado_falso(apertadas, idade=10.0, segurando=None):
    return SimpleNamespace(
        _pressed_events_lock=threading.Lock(),
        _pressed_events={sc: SimpleNamespace(time=AGORA - idade) for sc in apertadas},
        _logically_pressed_keys=dict.fromkeys(apertadas, object()),
        _listener=SimpleNamespace(active_modifiers=set(apertadas),
                                  modifier_states=segurando or {}),
    )


def test_tecla_presa_sai_da_tabela():
    teclado = _teclado_falso([68, 81])                   # F10 preso, PgDn segurada
    soltas = atl.soltar_teclas_presas(teclado, estado=lambda sc: sc == 81, agora=AGORA)
    assert soltas == [68]
    assert list(teclado._pressed_events) == [81]
    assert 68 not in teclado._logically_pressed_keys
    assert teclado._listener.active_modifiers == {81}


def test_tecla_recem_apertada_nao_e_mexida():
    """O Windows leva um instante para refletir a tecla; segurada se renova."""
    teclado = _teclado_falso([29], idade=1.0)
    assert atl.soltar_teclas_presas(teclado, estado=lambda sc: False, agora=AGORA) == []


def test_modificador_que_a_biblioteca_segura_nao_e_mexido():
    """Com "Reservar a tecla" a biblioteca engole o Ctrl ate saber se vem o
    atalho, e o Windows nem o ve apertado: tira-lo virava Ctrl+C em "c"."""
    teclado = _teclado_falso([29, 56], segurando={29: "pending", 56: "suppressed"})
    assert atl.soltar_teclas_presas(teclado, estado=lambda sc: False, agora=AGORA) == []


def test_tecla_sem_como_conferir_fica():
    teclado = _teclado_falso([70])
    assert atl.soltar_teclas_presas(teclado, estado=lambda sc: None, agora=AGORA) == []
    assert list(teclado._pressed_events) == [70]


def test_biblioteca_diferente_nao_quebra():
    assert atl.soltar_teclas_presas(SimpleNamespace(), estado=lambda sc: False) == []


class User32Falso:
    """MapVirtualKeyW/GetAsyncKeyState do Windows, com os valores medidos."""
    MAPA = {(0x5B, 1): 0xF1, (0x5B, 3): 0xF1, (0xE05B, 3): 0x5B,     # [ / Win esquerda
            (0x22, 1): 0x47, (0x22, 3): 0x47, (0xE022, 3): 0xB3,     # G / Play-Pause
            (0x1D, 1): 0x11, (0x1D, 3): 0xA2, (0xE01D, 3): 0xA3,     # Ctrl esq./dir.
            (0x44, 1): 0x79, (0x44, 3): 0x79}                        # F10

    def __init__(self, apertados=()):
        self.apertados = set(apertados)
        self.consultas = []

    def MapVirtualKeyW(self, cod, modo):  # noqa: N802
        self.consultas.append(cod)
        return self.MAPA.get((cod, modo), 0)

    def GetAsyncKeyState(self, vk):  # noqa: N802
        return 0x8000 if vk in self.apertados else 0


def test_win_segurada_e_reconhecida_pelo_codigo_estendido():
    assert atl._estado_no_windows(0x5B, User32Falso({0x5B})) is True
    assert atl._estado_no_windows(0x5B, User32Falso()) is False


def test_ctrl_direito_segurado_conta():
    assert atl._estado_no_windows(0x1D, User32Falso({0xA3})) is True


def test_tecla_de_midia_segurada_conta():
    assert atl._estado_no_windows(0x22, User32Falso({0xB3})) is True


def test_f10_solto_e_reconhecido():
    assert atl._estado_no_windows(0x44, User32Falso()) is False


def test_sem_codigo_conhecido_nao_decide():
    u = User32Falso()
    assert atl._estado_no_windows(-179, u) is None        # so codigo virtual
    assert atl._estado_no_windows(541, u) is None         # AltGr
    assert u.consultas == []
    assert atl._estado_no_windows(0x70, u) is None        # mapa devolve 0


def test_captura_usa_um_gancho_so_e_sempre_desengancha(qapp, monkeypatch):
    real = atl.keyboard
    registro = {"ganchos": 0, "soltos": []}

    def hook(callback, suppress=False):
        registro["ganchos"] += 1
        for t, n in ((UP, "f10"), (DOWN, "page down")):
            callback(SimpleNamespace(event_type=t, name=n))
        return "gancho"

    falso = SimpleNamespace(KEY_DOWN=real.KEY_DOWN, is_modifier=real.is_modifier,
                            get_hotkey_name=real.get_hotkey_name, hook=hook,
                            unhook=registro["soltos"].append)
    monkeypatch.setattr(atl, "keyboard", falso)
    botao = atl.CapturaAtalho("page down")
    lidos = []
    botao.capturado.disconnect()
    botao.capturado.connect(lidos.append)
    botao._ler()
    assert lidos == ["page down"]
    assert registro == {"ganchos": 1, "soltos": ["gancho"]}
    botao.deleteLater()


def test_altgr_conta_como_modificador_na_validacao():
    erro, aviso = atl.validar({"hotkey_start": "alt gr+x", "hotkey_stop": "alt gr+x"}, False)
    assert erro == "" and "usada ao digitar" not in aviso and "sem modificador" not in aviso
