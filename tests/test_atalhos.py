"""Validacao de atalhos e guarda do teclado numerico (vozflow/atalhos.py)."""

from vozflow import atalhos

PADRAO = {
    "hotkey_start": "ctrl+alt+g", "hotkey_stop": "ctrl+alt+s",
    "hotkey_cancel": "ctrl+alt+x", "hotkey_start2": "", "hotkey_stop2": "",
}


def _com(**mudancas):
    valores = dict(PADRAO)
    valores.update(mudancas)
    return valores


def test_padrao_e_valido_sem_aviso():
    assert atalhos.validar(PADRAO) == ("", "")


def test_iniciar_e_parar_sao_obrigatorios():
    erro, _ = atalhos.validar(_com(hotkey_stop=""))
    assert erro


def test_segundo_par_precisa_das_duas_teclas():
    erro, _ = atalhos.validar(_com(hotkey_start2="f9"))
    assert "segundo atalho" in erro


def test_pares_nao_podem_compartilhar_tecla():
    erro, _ = atalhos.validar(_com(hotkey_start2="ctrl+alt+g", hotkey_stop2="f10"))
    assert erro


def test_cancelar_diferente_dos_outros():
    erro, _ = atalhos.validar(_com(hotkey_cancel="ctrl+alt+g"))
    assert "cancelar" in erro


def test_alt_shift_e_reservado_pelo_windows():
    erro, _ = atalhos.validar(_com(hotkey_start="alt+shift+d"))
    assert "Alt + Shift" in erro


def test_tecla_unica_alterna_e_valida():
    assert atalhos.validar(_com(hotkey_start="f9", hotkey_stop="f9"), True) == ("", "")


def test_tecla_de_navegacao_sozinha_gera_aviso():
    erro, aviso = atalhos.validar(_com(hotkey_start="page down", hotkey_stop="page down"))
    assert erro == ""
    assert "rolar" in aviso and "Reservar a tecla" in aviso


def test_tecla_de_digitacao_sozinha_gera_aviso():
    _, aviso = atalhos.validar(_com(hotkey_start="a", hotkey_stop="a"), True)
    assert "usada ao digitar" in aviso


def test_bonito():
    assert atalhos.bonito("ctrl+alt+g") == "Ctrl + Alt + G"
    assert atalhos.bonito("page down") == "PgDn"
    assert atalhos.bonito("windows+space") == "Win + Espaco"
    assert atalhos.bonito("") == "(desativado)"


def test_scancode_da_tecla_que_tem_gemea_no_numerico():
    assert atalhos._scancode_principal("page down") == 81
    assert atalhos._scancode_principal("ctrl+page down") == 81
    assert 81 in atalhos.SCANCODES_NUMERICO


def test_sem_scancode_unico_nao_ha_o_que_vigiar():
    assert atalhos._scancode_principal("3") is None       # tecla de digitacao
    assert atalhos._scancode_principal("ctrl+alt") is None  # so modificadores


def test_guarda_libera_tecla_sem_gemea_e_bloqueia_evento_do_numerico():
    guarda = atalhos.GuardaNumerico()
    assert guarda.liberado(None)

    class Evento:
        is_keypad = True

    guarda._do_numerico[81] = False
    guarda._anotar(81, Evento())
    assert not guarda.liberado(81)
    Evento.is_keypad = False
    guarda._anotar(81, Evento())
    assert guarda.liberado(81)
