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
    assert atl.ler_combinacao(_fila((DOWN, "ctrl"), (UP, "ctrl"), (DOWN, "page up"))) == "ctrl"


def test_modificador_sozinho_vale_como_esta():
    assert atl.ler_combinacao(_fila((DOWN, "shift"), (UP, "shift"))) == "shift"


def test_soltar_do_clique_nao_fecha_a_captura():
    """O read_hotkey fechava no primeiro "soltar" - o da tecla que abriu a captura."""
    assert atl.ler_combinacao(_fila((UP, "space"), (UP, "enter"), (DOWN, "f9"))) == "f9"


# ----------------------------------------------------------------------
# teclas presas na tabela do keyboard
# ----------------------------------------------------------------------
def _teclado_falso(apertadas):
    return SimpleNamespace(
        _pressed_events_lock=threading.Lock(),
        _pressed_events=dict.fromkeys(apertadas, object()),
        _logically_pressed_keys=dict.fromkeys(apertadas, object()),
        _listener=SimpleNamespace(active_modifiers=set(apertadas)),
    )


def test_tecla_presa_sai_da_tabela():
    teclado = _teclado_falso([68, 81])                   # F10 preso, PgDn segurada
    soltas = atl.soltar_teclas_presas(teclado, estado=lambda sc: sc == 81)
    assert soltas == [68]
    assert list(teclado._pressed_events) == [81]
    assert 68 not in teclado._logically_pressed_keys
    assert teclado._listener.active_modifiers == {81}


def test_tecla_sem_como_conferir_fica():
    teclado = _teclado_falso([-179, 70])                 # multimidia; estado desconhecido
    assert atl.soltar_teclas_presas(teclado, estado=lambda sc: None) == []
    assert sorted(teclado._pressed_events) == [-179, 70]


def test_biblioteca_diferente_nao_quebra():
    assert atl.soltar_teclas_presas(SimpleNamespace(), estado=lambda sc: False) == []
