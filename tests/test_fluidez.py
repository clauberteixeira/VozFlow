"""Escrita ao vivo mais fluida (vozflow/transcriber.py, config.py).

Medido com a voz real do usuario (leitura de 25 s): a regra antiga comparava
as previas desde o inicio do trecho, e qualquer mudanca na parte JA escrita
travava as palavras novas - so 10 de 25 previas liberavam texto e o atraso
tipico era 3,7 s.
"""

import json

import pytest

from vozflow import config
from vozflow.transcriber import LiveTranscriber


@pytest.fixture
def motor(qapp, pasta_config):
    m = LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    m.saidas = []
    m.segmento.connect(m.saidas.append)
    return m


def test_mudanca_na_parte_ja_escrita_nao_trava_as_palavras_novas(motor):
    motor._emitido = ["eu", "vi", "o"]                       # ja esta na tela
    motor._emitir_estavel("eu vi o carro azul na rua")
    motor.saidas.clear()
    # a previa seguinte trocou uma palavra JA escrita ("o" -> "um")
    motor._emitir_estavel("eu vi um carro azul na rua hoje")
    assert motor.saidas == ["carro azul na rua"]


def test_ultima_confirmada_sai_quando_ha_palavra_depois(motor):
    motor._emitir_estavel("eu quero cafe")
    motor._emitir_estavel("eu quero cafe com")
    assert motor.saidas == ["eu quero cafe"]


def test_ultima_palavra_da_previa_espera(motor):
    """A ultima da previa ainda muda quando chega mais audio ("confir"...)."""
    motor._emitir_estavel("eu quero cafe")
    motor._emitir_estavel("eu quero cafe")
    assert motor.saidas == ["eu quero"]


def test_pontuacao_diferente_nao_impede(motor):
    motor._emitir_estavel("Bom dia! Tudo")
    motor._emitir_estavel("Bom dia, tudo bem")
    assert motor.saidas == ["Bom dia, tudo"]       # na forma da previa mais recente


def test_nada_sai_duas_vezes(motor):
    for p in ("a b c", "a b c d", "a b c d e", "a b c d e f"):
        motor._emitir_estavel(p)
    escrito = " ".join(motor.saidas).split()
    assert escrito == ["a", "b", "c", "d", "e"]


def test_novo_trecho_comeca_sem_a_previa_anterior(motor):
    motor._emitir_estavel("primeiro trecho")
    motor._emitir_resto("primeiro trecho inteiro")
    motor.saidas.clear()
    motor._emitir_estavel("segundo")               # sem previa anterior deste trecho
    assert motor.saidas == []


# ----------------------------------------------------------------------
# intervalo entre previas
# ----------------------------------------------------------------------
def test_padrao_novo_do_intervalo(pasta_config):
    assert config.load()["partial_interval"] == pytest.approx(0.3)


def test_config_antiga_com_o_padrao_antigo_migra(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"partial_interval": 0.45, "config_versao": 2}), encoding="utf-8")
    assert config.load()["partial_interval"] == pytest.approx(0.3)


def test_intervalo_escolhido_a_mao_e_mantido(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"partial_interval": 0.6, "config_versao": 2}), encoding="utf-8")
    assert config.load()["partial_interval"] == pytest.approx(0.6)


def test_depois_da_migracao_045_escolhido_fica(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"partial_interval": 0.45, "config_versao": 3}), encoding="utf-8")
    assert config.load()["partial_interval"] == pytest.approx(0.45)
