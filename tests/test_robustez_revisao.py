"""Ajustes da revisao independente do L5."""

import json
import pathlib

import pytest

from conftest import esperar
from vozflow import audio, config


@pytest.mark.parametrize("valor", ["Infinity", "-Infinity", "NaN"])
def test_numero_infinito_ou_nan_volta_ao_padrao(pasta_config, valor):
    # json.loads aceita estes literais; int(inf) no overlay impedia o app de abrir
    config.CONFIG_PATH.write_text('{"overlay_width": %s}' % valor, encoding="utf-8")
    assert config.load()["overlay_width"] == config.DEFAULTS["overlay_width"]


def test_erro_de_leitura_nao_apaga_a_config_do_usuario(pasta_config, monkeypatch):
    """Arquivo travado (antivirus no boot): usar padroes nesta sessao, sem regravar."""
    original = json.dumps({"hotkey_start": "f9"})
    caminho = config.CONFIG_PATH
    caminho.write_text(original, encoding="utf-8")
    ler = pathlib.Path.read_bytes

    def travado(self, *a, **k):
        if self == caminho:
            raise PermissionError("arquivo em uso por outro processo")
        return ler(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_bytes", travado)
    cfg = config.load()
    assert cfg["hotkey_start"] == config.DEFAULTS["hotkey_start"]
    with open(caminho, encoding="utf-8") as fh:            # nao regravou
        assert fh.read() == original


@pytest.mark.parametrize("bruto", [
    '{"language": "en"}'.encode("utf-16"),          # Out-File do PowerShell 5.1
    '{"input_device": "Microfone Fácil"}'.encode("cp1252"),   # editor em ANSI
])
def test_arquivo_fora_de_utf8_vira_bak_e_o_app_abre(pasta_config, bruto):
    """Validacao final: UnicodeDecodeError nao e OSError e escapava do load()."""
    config.CONFIG_PATH.write_bytes(bruto)
    assert config.load() == config.DEFAULTS
    assert config.CONFIG_PATH.with_suffix(".json.bak").read_bytes() == bruto


def test_falha_no_replace_nao_deixa_tmp(pasta_config, monkeypatch):
    def negado(*_a):
        raise PermissionError("acesso negado")

    monkeypatch.setattr(config.os, "replace", negado)
    with pytest.raises(PermissionError):
        config.Config(dict(config.DEFAULTS)).save()
    assert not list(pasta_config.glob("*.tmp"))


def test_salvar_configuracoes_com_arquivo_travado_avisa_e_nao_fecha(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    monkeypatch.setattr(configuracoes, "nome_do_padrao", lambda: None)
    dlg = configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))
    antes = dict(dlg.cfg)

    def negado(*_a):
        raise PermissionError("em uso")

    monkeypatch.setattr(config.os, "replace", negado)
    dlg.chk_sons.setChecked(not dlg.cfg["sounds"])
    dlg._salvar()                                  # nao levanta
    assert dict(dlg.cfg) == antes                  # nada vale sem ter sido salvo
    assert "Nao consegui gravar" in dlg.aviso.text()
    assert dlg.result() == 0                       # dialogo continua aberto
    dlg.deleteLater()


def test_falha_ao_gravar_no_boot_nao_impede_o_app_de_abrir(pasta_config, monkeypatch):
    def negado(*_a):
        raise PermissionError("acesso negado")

    monkeypatch.setattr(config.os, "replace", negado)
    assert config.load() == config.DEFAULTS


def test_nomes_ambiguos_sem_o_numero_da_porta_nao_escolhem_aparelho(monkeypatch):
    """Dois aparelhos que so diferem pelo '(N- ' : nao da para saber qual e o salvo."""
    monkeypatch.setattr(audio.sd, "query_devices", lambda: [
        {"name": "Microfone (3- USB Audio Device)", "max_input_channels": 1},
        {"name": "Microfone (4- USB Audio Device)", "max_input_channels": 1},
    ])
    assert audio.resolver_dispositivo("Microfone (2- USB Audio Device)") is None


def test_erro_na_transcricao_final_mantem_o_aviso_na_tela(vozflow_app, qapp):
    """failed seguido do done("") de confirmacao nao pode apagar o aviso."""
    app, _teclado, _clip, _jan = vozflow_app()
    app.iniciar()
    app.parar()
    app.engine._recording = False
    app.engine.failed.emit("Erro inesperado no motor: x")
    app.engine.done.emit("")
    assert esperar(lambda: app.overlay.mensagens, app=qapp)
    assert app.overlay.mensagens[-1][0] == "erro"
    assert not app._entregando


def test_failed_e_done_sem_pedido_pendente(vozflow_app, qapp):
    """Motor se recuperou de um erro sozinho durante a ditada."""
    app, _teclado, _clip, _jan = vozflow_app()
    app.iniciar()
    app.engine._recording = False
    app.engine.failed.emit("Erro inesperado no motor: x")
    app.engine.done.emit("")                 # ninguem pediu: ignorado
    assert not app._entregando
    app.iniciar()
    assert app._quer_gravar


def test_saida_forcada_espera_o_worker_de_insercao(vozflow_app, qapp, monkeypatch):
    from vozflow import app as modulo_app

    app, _teclado, _clip, _jan = vozflow_app()
    vivo_na_saida = []
    monkeypatch.setattr(app.engine, "wait", lambda _ms=0: False)
    monkeypatch.setattr(modulo_app.os, "_exit",
                        lambda _c: vivo_na_saida.append(app._thread_insercao.is_alive()))
    app.encerrar()
    assert vivo_na_saida == [False]
