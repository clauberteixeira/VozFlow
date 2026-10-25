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
    motor._emitir_estavel("eu vi o carro azul na estrada")
    motor.saidas.clear()
    # a previa seguinte trocou uma palavra JA escrita ("o" -> "um")
    motor._emitir_estavel("eu vi um carro azul na estrada hoje")
    assert motor.saidas == ["carro azul na estrada"]


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
    for p in ("casa mesa sala", "casa mesa sala pato", "casa mesa sala pato gato",
              "casa mesa sala pato gato vela"):
        motor._emitir_estavel(p)
    escrito = " ".join(motor.saidas).split()
    assert escrito == ["casa", "mesa", "sala", "pato", "gato"]


def test_palavra_curta_confirmada_sai_na_rodada_seguinte(motor):
    """Curta no fim da previa anterior espera uma rodada - e nao mais que isso."""
    for p in ("a b c", "a b c d", "a b c d e", "a b c d e f"):
        motor._emitir_estavel(p)
    assert " ".join(motor.saidas).split() == ["a", "b", "c", "d"]


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


# ----------------------------------------------------------------------
# revisao: palavra repetida, palavra cortada no fim da previa
# ----------------------------------------------------------------------
def _ditar(motor, previas, final):
    for p in previas:
        motor._emitir_estavel(p)
    motor._emitir_resto(final)
    return " ".join(motor.saidas).split()


def test_repeticao_com_palavra_reescrita_nao_duplica(motor):
    """O alinhamento casava o "muito" digitado com o PRIMEIRO "muito" da
    previa, e o segundo saia de novo: "foi muitos muito muito bom..."."""
    escrito = _ditar(motor, ["foi muitos", "foi muitos muito", "foi muitos muito bom",
                             "foi muito muito bom demais", "foi muito muito bom demais mesmo"],
                     "foi muito muito bom demais mesmo")
    assert escrito == ["foi", "muitos", "muito", "bom", "demais", "mesmo"]


def test_repeticao_com_palavra_reescrita_nao_perde(motor):
    escrito = _ditar(motor, ["carro", "carro de", "carro de", "carro de d", "carro de de,",
                             "carro da de eu!", "carro da de eu rua", "carro da de eu rua che"],
                     "carro de de eu rua chegar")
    assert len(escrito) == 6


def test_palavra_curta_no_fim_da_previa_anterior_espera(motor):
    """"em" era o comeco de "embora" (o Whisper escreveu "em bora")."""
    escrito = _ditar(motor, ["eu quero em", "eu quero em bora", "eu quero embora agora",
                             "eu quero embora agora mesmo"], "eu quero embora agora mesmo")
    assert escrito == ["eu", "quero", "embora", "agora", "mesmo"]


def test_juncao_na_parte_escrita_nao_perde_palavra(motor):
    """"para o" virou "pro": a quantidade mudou, vale o alinhamento."""
    escrito = _ditar(motor, ["para o carro", "para o carro azul", "pro carro azul",
                             "pro carro azul na"], "pro carro azul na rua")
    assert escrito == ["para", "o", "carro", "azul", "na", "rua"]


# ----------------------------------------------------------------------
# revisao: a migracao marca o arquivo e nao roda de novo
# ----------------------------------------------------------------------
def test_migracao_grava_a_versao_nova_e_respeita_ajuste_posterior(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"partial_interval": 0.45, "input_device": "Mic X", "config_versao": 2}), encoding="utf-8")
    config.load()
    disco = json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))
    assert disco["config_versao"] == 3
    disco.update(partial_interval=0.45, input_device="Microfone (H510)")   # ajuste a mao
    config.CONFIG_PATH.write_text(json.dumps(disco), encoding="utf-8")
    cfg = config.load()
    assert cfg["partial_interval"] == pytest.approx(0.45)
    assert cfg["input_device"] == "Microfone (H510)"


def test_versao_gravada_como_float_vale(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"partial_interval": 0.45, "config_versao": 3.0}), encoding="utf-8")
    assert config.load()["partial_interval"] == pytest.approx(0.45)


def test_versao_futura_fica_como_esta(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"partial_interval": 0.45, "input_device": "Mic X", "config_versao": 4}), encoding="utf-8")
    cfg = config.load()
    assert (cfg["config_versao"], cfg["partial_interval"], cfg["input_device"]) == (4, 0.45, "Mic X")
