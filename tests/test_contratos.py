"""APIs privadas de terceiros de que o VozFlow depende (F-016).

Cada uma tem um fallback silencioso no codigo - se o nome sumir numa
atualizacao, o recurso deixa de funcionar sem erro nenhum. Estes testes fazem a
quebra aparecer no CI, antes de chegar a um usuario.
"""

import os

import pytest


def test_sounddevice_ainda_permite_reiniciar_o_portaudio():
    """audio.atualizar_lista_dispositivos: enxergar fone ligado depois do app."""
    import sounddevice

    assert callable(getattr(sounddevice, "_terminate", None))
    assert callable(getattr(sounddevice, "_initialize", None))


@pytest.mark.skipif(os.name != "nt", reason="teclado do Windows")
def test_keyboard_ainda_expoe_as_teclas_do_numerico():
    """atalhos.GuardaNumerico: PgDn nao pode disparar com o Num 3."""
    from keyboard import _winkeyboard

    from vozflow import atalhos

    assert _winkeyboard.keypad_keys
    assert 81 in atalhos.SCANCODES_NUMERICO


def test_faster_whisper_ainda_mapeia_os_modelos_oferecidos():
    """modelo.repo_do_modelo: progresso do download do modelo."""
    from vozflow import modelo
    from vozflow.configuracoes import MODELOS

    for nome in MODELOS:
        assert modelo.repo_do_modelo(nome), nome
