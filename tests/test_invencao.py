"""Frases inventadas pelo Whisper em trecho sem fala (texto.py, transcriber.py).

Medido no modelo real (large-v3-turbo): chiado, um estalo e uma respiracao
viraram "Obrigado." e "E ai". O que separa: a proporcao do trecho com timbre
de voz (vibracao das cordas vocais) dentro do que o detector aceitou - fala
real mediana 0,72-0,75, ruido 0,00-0,26.

Os testes de integracao passam pelo motor inteiro (_pump bloco a bloco,
previa, fechamento do trecho, encerrar) com relogio simulado, microfone falso
e modelo falso. Os sinais sao sinteticos (tests/_sinais.py): nada de
microfone nem de gravacao real.
"""

from types import SimpleNamespace

import numpy as np
import pytest

import _sinais as SN
from vozflow import config, texto
from vozflow import transcriber as T
from vozflow.audio import segundos_com_timbre, tem_timbre_de_voz


# ----------------------------------------------------------------------
# regra: frase pronta + pouca proporcao de voz
# ----------------------------------------------------------------------
@pytest.mark.parametrize("frase", ["Obrigado.", "obrigada!", "Tchau.", "E aí", "Valeu!",
                                   "Legendas pela comunidade Amara.org", "Inscreva-se no canal",
                                   "Obrigado por assistir.", "E E Tchau.", "Tchau. Obrigado.", "..."])
def test_frase_pronta_em_trecho_sem_timbre_e_invencao(frase):
    assert texto.e_invencao(frase, voz_s=0.0, aceito_s=0.6)


def test_obrigado_dito_de_verdade_passa_mesmo_curto():
    """Fechar uma mensagem com "Obrigado." e comum: curto, mas quase todo voz."""
    assert not texto.e_invencao("Obrigado.", voz_s=0.45, aceito_s=0.6)


@pytest.mark.parametrize("frase", ["Obrigado pela reunião de hoje.", "Vamos lá.", "Sim.",
                                   "Tchau para quem fica, até amanhã."])
def test_fala_que_nao_e_frase_pronta_passa_mesmo_sem_timbre(frase):
    assert not texto.e_invencao(frase, voz_s=0.0, aceito_s=0.6)


def test_vazio_nao_e_invencao():
    assert not texto.e_invencao("", voz_s=0.0, aceito_s=0.0)


def test_frase_em_frances_da_lista_casa():
    assert texto.e_invencao("Sous-titres réalisés par la communauté d'Amara.org", 0.0, 1.0)


# ----------------------------------------------------------------------
# timbre de voz (audio.py)
# ----------------------------------------------------------------------
def test_voz_tem_timbre_e_ruido_nao():
    voz = SN.vogal(0.1)
    chiado = (np.random.default_rng(0).standard_normal(1600) * 0.05).astype(np.float32)
    assert tem_timbre_de_voz(voz[:1600])
    assert not tem_timbre_de_voz(chiado)
    assert not tem_timbre_de_voz(np.zeros(1600, np.float32))
    assert segundos_com_timbre(chiado) == 0.0


def test_timbre_conta_em_janelas_curtas():
    """Um "sim" (vogal de 0,2 s) conta o que tem, sem precisar encher blocos."""
    sim = np.concatenate([SN.silencio(0.1), SN.palavra_sim(), SN.silencio(0.1)])
    assert 0.1 <= segundos_com_timbre(sim[: sim.size // 1600 * 1600]) <= 0.3


# ----------------------------------------------------------------------
# motor inteiro, com relogio simulado
# ----------------------------------------------------------------------
class RelogioSimulado:
    def __init__(self):
        self.t = 100.0

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.t += s


class MicFalso:
    """Entrega blocos de 1600 amostras conforme o relogio anda - inclusive
    varios de uma vez depois de uma previa demorada, como o de verdade."""

    def __init__(self, sinal, relogio):
        self.sinal = sinal[: sinal.size // 1600 * 1600]
        self.relogio, self.t0, self.pos = relogio, relogio.t, 0
        self.device = self.aviso = None

    def start(self):
        pass

    def stop(self):
        pass

    def drain(self):
        disp = min(int((self.relogio.t - self.t0) * 16000) // 1600 * 1600, self.sinal.size)
        out, self.pos = self.sinal[self.pos:disp], max(self.pos, disp)
        return out.astype(np.float32)


class ModeloFalso:
    """Diz sempre `fala`; a previa (beam 1) leva `lat_previa` segundos."""

    def __init__(self, fala, relogio, lat_previa=0.35, lat_final=0.5):
        self.fala, self.relogio = fala, relogio
        self.lat_previa, self.lat_final = lat_previa, lat_final

    def transcribe(self, _audio, beam_size=1, **_kw):
        self.relogio.t += self.lat_final if beam_size > 1 else self.lat_previa
        return [SimpleNamespace(text=self.fala)], None


@pytest.fixture
def ditar(qapp, monkeypatch):
    def rodar(sinal, fala, lat_previa=0.35):
        relogio = RelogioSimulado()
        monkeypatch.setattr(T, "time", relogio)
        m = T.LiveTranscriber(config.Config(dict(config.DEFAULTS)))
        m._model = ModeloFalso(fala, relogio, lat_previa)
        digitado, finais = [], []
        m.segmento.connect(digitado.append)
        m.done.connect(finais.append)
        m._reset_buffers()
        m._rec = MicFalso(sinal, relogio)
        m._recording = True
        m._last_partial = relogio.t
        fim = relogio.t + sinal.size / 16000 + 0.05
        while relogio.t < fim:
            relogio.t += 0.02                  # o timeout da fila de comandos
            m._pump()
        m._encerrar(True)
        return digitado, finais[-1]
    return rodar


def _com_pausas(*partes):
    return np.concatenate([SN.silencio(0.4), *partes, SN.silencio(1.2)])


def _respiracao(segundos=0.7):
    ruido = SN.banda(np.random.default_rng(2).standard_normal(int(16000 * segundos)), lo=200)
    return (ruido * 0.04).astype(np.float32)


def test_respiracao_nao_vira_obrigado(ditar):
    digitado, final = ditar(_com_pausas(_respiracao(), SN.silencio(0.4), _respiracao()), "Obrigado.")
    assert digitado == [] and final == ""


def test_ruido_nao_escreve_nada_ao_vivo_mesmo_com_frase_qualquer(ditar):
    """A previa nao escreve no campo antes de o trecho se confirmar como fala."""
    digitado, final = ditar(_com_pausas(_respiracao()), "E aí, tudo bem?")
    assert digitado == [] and final == ""


def test_obrigado_isolado_de_verdade_e_escrito(ditar):
    digitado, _ = ditar(_com_pausas(SN.palavra_obrigado()), "Obrigado.")
    assert " ".join(digitado) == "Obrigado."


@pytest.mark.parametrize(("palavra", "fala", "lat"), [
    (SN.palavra_sim, "Sim.", 1.5),
    (SN.palavra_ok, "Ok.", 3.0),
])
def test_palavra_curta_com_previa_lenta_e_escrita(ditar, palavra, fala, lat):
    """Previa lenta (CPU) entrega 1,5-3 s de audio de uma vez: julgado inteiro,
    o pedaco "nao era voz" e a palavra sumia."""
    digitado, _ = ditar(np.concatenate([SN.silencio(0.4), palavra(), SN.silencio(lat + 1.0)]), fala, lat)
    assert " ".join(digitado) == fala


def test_frase_normal_com_previa_lenta(ditar):
    digitado, final = ditar(_com_pausas(SN.frase(2.0)), "Vou mandar o relatório amanhã.", 3.0)
    assert " ".join(digitado) == "Vou mandar o relatório amanhã." == final


def test_voz_sussurrada_nao_some(ditar):
    """Sussurro quase nao tem timbre de voz; com bastante som aceito pelo
    detector, vai para o modelo assim mesmo."""
    digitado, _ = ditar(_com_pausas(SN.frase(2.2, aspir=0.95)), "Vou sair agora.")
    assert " ".join(digitado) == "Vou sair agora."


def test_contagem_zera_entre_trechos(ditar):
    """Uma fala, pausa longa, depois so respiracao: o segundo trecho nao herda
    a voz do primeiro."""
    sinal = np.concatenate([SN.silencio(0.4), SN.frase(1.0), SN.silencio(1.5), _respiracao(),
                            SN.silencio(1.2)])
    digitado, _ = ditar(sinal, "Obrigado.")
    assert " ".join(digitado) == "Obrigado."           # so o do primeiro trecho, que e voz
