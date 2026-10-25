"""L5: o motor sobrevive a erro inesperado e o app nao fica 'Pronto' mudo (F-008, F-013, F-026)."""

import numpy as np
import pytest

from conftest import esperar
from vozflow import config
from vozflow.transcriber import LiveTranscriber


class RecorderFalso:
    def __init__(self, falha_no_stop=False):
        self.aberto = False
        self.aviso = None
        self.device = None
        self.falha_no_stop = falha_no_stop

    def start(self):
        self.aberto = True

    def stop(self):
        self.aberto = False
        if self.falha_no_stop:
            raise RuntimeError("Unanticipated host error")

    def drain(self):
        return np.empty(0, dtype=np.float32)


@pytest.fixture
def motor(qapp, pasta_config, monkeypatch):
    m = LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    monkeypatch.setattr(m, "_load_model", lambda: True)
    m._rec = RecorderFalso()
    m.saidas = {"done": [], "failed": []}
    m.done.connect(m.saidas["done"].append)
    m.failed.connect(m.saidas["failed"].append)
    return m


def test_erro_inesperado_na_gravacao_fecha_o_microfone_e_avisa(motor, monkeypatch):
    def quebra():
        raise TypeError("'>=' not supported between 'float' and 'str'")

    monkeypatch.setattr(motor, "_pump", quebra)
    motor.cmd_start()
    motor.cmd_quit()
    motor.run()
    assert motor.saidas["failed"] and "inesperado" in motor.saidas["failed"][0]
    assert motor.saidas["done"] == [""]      # app ignora se ninguem pediu
    assert not motor.recording
    assert not motor._rec.aberto


def test_motor_continua_vivo_depois_do_erro(motor, monkeypatch):
    chamadas = []

    def quebra_uma_vez():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("falha passageira")

    monkeypatch.setattr(motor, "_pump", quebra_uma_vez)
    motor.cmd_start()      # quebra
    motor.cmd_start()      # grava de novo normalmente
    motor.cmd_stop()
    motor.cmd_quit()
    motor.run()
    assert len(chamadas) >= 2
    # um done do erro (ignorado pelo app) + um do stop
    assert motor.saidas["done"] == ["", ""]


def test_microfone_que_some_no_stop_ainda_confirma_o_done(motor):
    motor._rec = RecorderFalso(falha_no_stop=True)
    motor.cmd_start()
    motor.cmd_stop()
    motor.cmd_quit()
    motor.run()
    assert motor.saidas["done"]              # o app nao fica esperando 30 s


def test_aviso_de_voz_fraca_aponta_onde_a_calibracao_esta():
    import inspect

    from vozflow import transcriber

    fonte = inspect.getsource(transcriber.LiveTranscriber._pump)
    assert "na bandeja" not in fonte
    assert "Configuracoes > Microfone" in fonte


# ----------------------------------------------------------------------
# lado do app
# ----------------------------------------------------------------------
def test_motor_morreu_no_meio_da_ditada_descarta_o_pendente(vozflow_app, qapp):
    app, teclado, _clip, jan = vozflow_app()
    app.iniciar()
    jan.foco = 0x200
    app.engine.segmento.emit("ficaria preso")
    app.engine._recording = False              # o motor ja se recuperou sozinho
    app.engine.failed.emit("Erro inesperado no motor: x")
    assert "cancel" not in app.engine.comandos
    jan.foco = 0x100
    assert not esperar(lambda: teclado.texto, timeout=0.6, app=qapp)
    app.iniciar()                              # proxima ditada liberada
    assert app._quer_gravar


def test_sair_com_o_motor_preso_encerra_sem_crash(vozflow_app, qapp, monkeypatch):
    from vozflow import app as modulo_app

    app, _teclado, _clip, _jan = vozflow_app()
    saidas = []
    monkeypatch.setattr(app.engine, "wait", lambda _ms=0: False)
    monkeypatch.setattr(modulo_app.os, "_exit", saidas.append)
    monkeypatch.setattr(app.app, "quit", lambda: saidas.append("quit"))
    app.encerrar()
    assert saidas == [0]
