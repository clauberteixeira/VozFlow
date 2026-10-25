"""Carga, migracao e preservacao da config (vozflow/config.py)."""

import json

import pytest

from vozflow import config


def test_sem_arquivo_grava_os_padroes(pasta_config):
    cfg = config.load()
    assert cfg == config.DEFAULTS
    assert json.loads(config.CONFIG_PATH.read_text(encoding="utf-8")) == config.DEFAULTS


def test_completa_chaves_que_faltam_e_mantem_as_do_usuario(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps({"hotkey_start": "f9"}), encoding="utf-8")
    cfg = config.load()
    assert cfg["hotkey_start"] == "f9"
    assert cfg["model"] == config.DEFAULTS["model"]


def test_arquivo_com_bom_do_notepad_e_lido(pasta_config):
    config.CONFIG_PATH.write_bytes(b"\xef\xbb\xbf" + json.dumps({"language": "en"}).encode())
    assert config.load()["language"] == "en"


def test_arquivo_corrompido_vira_bak_e_usa_padroes(pasta_config):
    config.CONFIG_PATH.write_text("{ isto nao e json", encoding="utf-8")
    cfg = config.load()
    assert cfg == config.DEFAULTS
    bak = config.CONFIG_PATH.with_suffix(".json.bak")
    assert bak.read_text(encoding="utf-8") == "{ isto nao e json"


def test_indice_antigo_do_microfone_vira_nome(pasta_config, monkeypatch):
    from vozflow import audio

    monkeypatch.setattr(audio, "nome_do_indice", lambda i: "Microfone X" if i == 4 else None)
    config.CONFIG_PATH.write_text(json.dumps({"input_device": 4, "config_versao": 3}), encoding="utf-8")
    assert config.load()["input_device"] == "Microfone X"


def test_indice_invalido_do_microfone_cai_no_padrao(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps({"input_device": True, "config_versao": 3}), encoding="utf-8")
    assert config.load()["input_device"] is None


def test_acesso_por_atributo(pasta_config):
    cfg = config.load()
    assert cfg.model == cfg["model"]
    cfg.language = "es"
    assert cfg["language"] == "es"
    with pytest.raises(AttributeError):
        _ = cfg.chave_que_nao_existe
