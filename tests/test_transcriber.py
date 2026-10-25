"""Motor: confirmacao de stop/cancel e alinhamento do resto final (vozflow/transcriber.py)."""

import pytest

from vozflow import config
from vozflow.transcriber import LiveTranscriber


@pytest.fixture
def motor(qapp, pasta_config):
    m = LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    m.saidas = {"segmento": [], "done": []}
    m.segmento.connect(m.saidas["segmento"].append)
    m.done.connect(m.saidas["done"].append)
    return m


def test_stop_e_cancel_sem_gravacao_sao_confirmados(motor, monkeypatch):
    """Sem confirmacao o app ficaria esperando uma entrega que nunca vem."""
    monkeypatch.setattr(motor, "_load_model", lambda: True)
    motor.cmd_cancel()
    motor.cmd_stop()
    motor.cmd_quit()
    motor.run()              # roda na thread do teste: processa a fila e sai
    assert motor.saidas["done"] == ["", ""]


@pytest.mark.parametrize("emitido,final,resto", [
    (["Ola", "mundo"], "Ola mundo bonito", "bonito"),
    (["Ola", "mundo,"], "Olá mundo. Tudo bem", "Tudo bem"),
    (["a", "b", "c"], "a bc d", "d"),
    (["eu", "quero", "cafe"], "eu quero um cafe agora", "agora"),
    (["a", "b", "c", "d"], "a b", None),
    ([], "tudo novo", "tudo novo"),
    # ultima palavra digitada mudou na versao final (parcial beam 1 x final beam 5):
    # o resto NAO pode sumir (casos da revisao independente do L4)
    (["eu", "vi", "voces"], "eu vi voce ontem a noite", "ontem a noite"),
    (["nos", "fomos", "embora"], "nos fomos embor e depois voltamos", "e depois voltamos"),
    (["tem", "tres"], "tem 3 pessoas aqui", "pessoas aqui"),
    (["ele", "falou"], "ele falo que vinha", "que vinha"),
    (["estava", "chovendo"], "estava chovend muito forte hoje", "muito forte hoje"),
    (["-"], "- e depois", "e depois"),
    (["de", "ditado"], "digitado com calma", "com calma"),
])
def test_resto_final_alinha_pelo_texto_e_nao_pela_contagem(motor, emitido, final, resto):
    """F-023: o que ja foi digitado nao se desfaz; so falta o que vem depois."""
    motor._emitido = list(emitido)
    motor._emitir_resto(final)
    assert motor.saidas["segmento"] == ([resto] if resto else [])
    assert motor._emitido == []
