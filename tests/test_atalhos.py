"""Validacao de atalhos e guarda do teclado numerico (vozflow/atalhos.py)."""

from vozflow import atalhos, config, configuracoes

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
    assert "PgDn" in aviso and "rolar" in aviso and "Reservar a tecla" in aviso


def test_duas_teclas_de_navegacao_saem_num_aviso_so():
    valores = _com(hotkey_start="page down", hotkey_stop="page down",
                   hotkey_start2="page up", hotkey_stop2="page up")
    _, aviso = atalhos.validar(valores)
    assert "PgDn e PgUp" in aviso
    assert aviso.count("rolar") == 1
    assert aviso.count("Reservar a tecla") == 1


def test_tecla_de_navegacao_reservada_nao_rola_mais_e_nao_avisa():
    valores = _com(hotkey_start="page down", hotkey_stop="page down")
    assert atalhos.validar(valores, True) == ("", "")


def test_tecla_de_digitacao_sozinha_gera_aviso():
    valores = _com(hotkey_start="a", hotkey_stop="a", hotkey_start2="b", hotkey_stop2="b")
    _, aviso = atalhos.validar(valores, True)
    assert "A e B" in aviso
    assert aviso.count("digitar") == 1


def test_tecla_sem_modificador_lembra_de_reservar_uma_vez_so():
    _, aviso = atalhos.validar(_com(hotkey_start="f9", hotkey_stop="f9"))
    assert aviso.count("Reservar a tecla") == 1


def _janela_com_pgdn():
    cfg = config.Config(dict(config.DEFAULTS))
    cfg.update(hotkey_start="page down", hotkey_stop="page down", suppress_hotkeys=False)
    return configuracoes.JanelaConfiguracoes(cfg)


def test_aviso_de_atalho_so_aparece_na_aba_atalhos(qapp):
    dlg = _janela_com_pgdn()
    assert "PgDn" in dlg.aviso.text()
    dlg.abas.setCurrentIndex(4)
    assert dlg.aviso.text() == ""
    dlg.abas.setCurrentIndex(0)
    assert "PgDn" in dlg.aviso.text()


def test_erro_de_atalho_aparece_em_qualquer_aba(qapp):
    """O erro impede de salvar: sumir com ele deixaria o Salvar sem explicacao."""
    dlg = _janela_com_pgdn()
    dlg.campos["hotkey_stop"].combo = ""
    dlg.abas.setCurrentIndex(4)
    assert "precisam de uma combinacao" in dlg.aviso.text()


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
