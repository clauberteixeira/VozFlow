"""Ajustes da revisao independente de L3/L6."""

import datetime as dt

import numpy as np
import pytest

from conftest import esperar
from vozflow import config, inserter


# ----------------------------------------------------------------------
# bloqueante: max_new_tokens + prompt nao pode passar de 448
# ----------------------------------------------------------------------
def test_teto_de_tokens_da_previa_cabe_com_qualquer_vocabulario(qapp, pasta_config):
    """faster-whisper levanta ValueError se prompt + max_new_tokens > 448;
    o prompt do initial_prompt pode chegar a ~227 tokens."""
    from vozflow.transcriber import LiveTranscriber

    pedidos = []

    class ModeloFalso:
        def transcribe(self, _audio, **kw):
            pedidos.append(kw)
            return [], None

    motor = LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    motor._model = ModeloFalso()
    motor._na_cpu = True
    voz = (0.1 * np.sin(np.arange(16000 * 30) * 0.3)).astype(np.float32)   # 30 s
    motor._transcrever(voz, final=False)
    assert pedidos[-1]["max_new_tokens"] <= 448 - 228


# ----------------------------------------------------------------------
# historico
# ----------------------------------------------------------------------
def _linha(dias_atras, texto):
    quando = dt.datetime.now() - dt.timedelta(days=dias_atras)
    return "[" + quando.strftime("%d/%m/%Y %H:%M:%S") + "] " + texto + "\n"


def _ditar(app, texto):
    app.iniciar()
    app.engine.segmento.emit(texto)
    app.parar()
    app.engine._recording = False
    app.engine.done.emit(texto)


def test_historico_dias_absurdo_nao_quebra_a_entrega(vozflow_app, qapp, pasta_config):
    log = pasta_config / "transcricoes.txt"
    log.write_text(_linha(3, "antigo " * 40), encoding="utf-8")      # passa do limite
    app, teclado, *_ = vozflow_app(historico_max_mb=0.0001, historico_dias=10 ** 12)
    _ditar(app, "entregue mesmo assim")
    assert esperar(lambda: teclado.texto == "entregue mesmo assim", app=qapp)
    assert esperar(lambda: app.overlay.mensagens[-1][0] == "done", app=qapp)


def test_historico_em_outra_codificacao_nao_e_regravado(vozflow_app, qapp, pasta_config):
    log = pasta_config / "transcricoes.txt"
    bruto = _linha(30, "salvo em utf-16 a mao").encode("utf-16")
    log.write_bytes(bruto)
    app, *_ = vozflow_app(historico_max_mb=0.0001)
    _ditar(app, "novo")
    esperar(lambda: app.overlay.mensagens and app.overlay.mensagens[-1][0] == "done", app=qapp)
    assert log.read_bytes().startswith(bruto)          # nada apagado nem convertido


def test_falha_ao_trocar_o_historico_nao_deixa_tmp(vozflow_app, qapp, pasta_config, monkeypatch):
    from vozflow import app as modulo_app

    log = pasta_config / "transcricoes.txt"
    log.write_text(_linha(30, "velho " * 40), encoding="utf-8")     # passa do limite

    def negado(*_a):
        raise PermissionError("em uso")

    monkeypatch.setattr(modulo_app.os, "replace", negado)
    app, *_ = vozflow_app(historico_max_mb=0.0001)
    _ditar(app, "novo")
    assert esperar(lambda: app.overlay.mensagens and app.overlay.mensagens[-1][0] == "done", app=qapp)
    assert esperar(lambda: not list(pasta_config.glob("*.tmp")), app=qapp)


# ----------------------------------------------------------------------
# webhook
# ----------------------------------------------------------------------
@pytest.mark.parametrize("url,inseguro", [
    ("http://127.evil.com/x", True),
    ("http://127.0.0.1.attacker.com/", True),
    ("http://127.5.6.7/", False),
])
def test_loopback_de_verdade(url, inseguro):
    assert inserter.url_sem_criptografia(url) is inseguro


# ----------------------------------------------------------------------
# modelo automatico offline
# ----------------------------------------------------------------------
def test_sem_internet_o_automatico_usa_um_modelo_ja_baixado(qapp, pasta_config, monkeypatch):
    """CPU, offline, so o large-v3-turbo no disco: antes funcionava (lento);
    nao pode passar a nao abrir por falta do 'base'."""
    import faster_whisper

    from vozflow import transcriber

    carregados = []

    class ModeloFalso:
        def __init__(self, caminho, device, compute_type):
            carregados.append((caminho, device))

        def transcribe(self, *_a, **_k):
            return [], None

    def garantir(nome, *_a):
        if nome != "large-v3-turbo":
            raise OSError("Connection refused")
        return "/cache/" + nome

    monkeypatch.setattr(faster_whisper, "WhisperModel", ModeloFalso)
    monkeypatch.setattr(transcriber, "_prepare_cuda_dlls", lambda: [])
    monkeypatch.setattr(transcriber, "_cuda_disponivel", lambda: False)
    monkeypatch.setattr(transcriber.modelo_util, "ja_baixado", lambda n: n == "large-v3-turbo")
    monkeypatch.setattr(transcriber.modelo_util, "garantir", garantir)
    motor = transcriber.LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    assert motor._load_model()
    assert carregados[-1] == ("/cache/large-v3-turbo", "cpu")
