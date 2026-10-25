"""Frases inventadas pelo Whisper em trecho sem fala (texto.py, transcriber.py).

Medido no modelo real (large-v3-turbo): chiado, um estalo e uma respiracao
viraram "Obrigado." e "E ai". O detector de voz do app marcou 0-0,5 s de voz
nesses trechos; pedacos curtos de fala real mediram 1,1-1,8 s.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from vozflow import config, texto
from vozflow.transcriber import VOZ_MINIMA_S, LiveTranscriber


@pytest.mark.parametrize("frase", ["Obrigado.", "obrigada!", "Tchau.", "E aí", "Valeu!",
                                   "Legendas pela comunidade Amara.org", "Inscreva-se no canal",
                                   "Obrigado por assistir.", "..."])
def test_frase_pronta_com_pouca_voz_e_invencao(frase):
    assert texto.e_invencao(frase, voz_s=0.4)


def test_com_voz_de_sobra_nao_e_invencao():
    """Um "obrigado" dito de verdade, com voz no trecho, passa."""
    assert not texto.e_invencao("Obrigado.", voz_s=1.5)


@pytest.mark.parametrize("frase", ["Obrigado pela reunião de hoje.", "Vamos lá.", "Sim.",
                                   "Tchau para quem fica, até amanhã."])
def test_fala_que_nao_e_frase_pronta_passa_mesmo_curta(frase):
    assert not texto.e_invencao(frase, voz_s=0.4)


def test_vazio_nao_e_invencao():
    assert not texto.e_invencao("", voz_s=0.0)


# ----------------------------------------------------------------------
# no motor
# ----------------------------------------------------------------------
class ModeloFalso:
    def __init__(self, fala):
        self.fala = fala
        self.chamadas = 0

    def transcribe(self, _audio, **_kw):
        self.chamadas += 1
        return [SimpleNamespace(text=self.fala)], None


@pytest.fixture
def motor(qapp):
    m = LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    m.saidas = []
    m.segmento.connect(m.saidas.append)
    return m


AUDIVEL = (0.1 * np.sin(np.arange(32000) * 0.3)).astype(np.float32)   # 2 s


def test_trecho_quase_sem_voz_nem_vai_para_o_modelo(motor):
    motor._model = ModeloFalso("Obrigado.")
    assert motor._transcrever(AUDIVEL, final=True, voz=0.1) == ""
    assert motor._model.chamadas == 0


def test_invencao_com_pouca_voz_e_descartada(motor):
    motor._model = ModeloFalso("Obrigado.")
    assert motor._transcrever(AUDIVEL, final=True, voz=0.5) == ""
    assert motor._model.chamadas == 1


def test_fala_de_verdade_passa(motor):
    motor._model = ModeloFalso("Reunião com a equipe às dez.")
    assert motor._transcrever(AUDIVEL, final=True, voz=VOZ_MINIMA_S) == "Reunião com a equipe às dez."


def test_sem_informacao_de_voz_comporta_como_antes(motor):
    motor._model = ModeloFalso("Obrigado.")
    assert motor._transcrever(AUDIVEL, final=True) == "Obrigado."


def test_previa_inventada_nao_chega_a_ser_escrita(motor):
    """A invencao se repete igual em toda previa - o prefixo estavel a
    escreveria. Barrada na previa, nunca chega ao campo."""
    motor._model = ModeloFalso("Obrigado.")
    motor._buf = AUDIVEL
    motor._voz_trecho = 0.4
    for _ in range(3):
        motor._partial = motor._transcrever(motor._buf, final=False, voz=motor._voz_trecho)
        motor._emitir_estavel(motor._partial)
    assert motor.saidas == []


def test_voz_do_trecho_zera_ao_fechar(motor):
    motor._model = ModeloFalso("Bom dia a todos, vamos começar.")
    motor._buf = AUDIVEL
    motor._voz_trecho = 1.6
    motor._fechar_trecho()
    assert motor._voz_trecho == 0.0
    assert motor.saidas == ["Bom dia a todos, vamos começar."]


# ----------------------------------------------------------------------
# timbre de voz (audio.py)
# ----------------------------------------------------------------------
def test_tom_de_voz_tem_timbre_e_ruido_nao():
    from vozflow.audio import segundos_com_timbre, tem_timbre_de_voz

    rng = np.random.default_rng(0)
    t = np.arange(1600) / 16000
    voz = (0.1 * np.sin(2 * np.pi * 140 * t) + 0.05 * np.sin(2 * np.pi * 280 * t)).astype(np.float32)
    chiado = (rng.standard_normal(1600) * 0.05).astype(np.float32)
    assert tem_timbre_de_voz(voz)
    assert not tem_timbre_de_voz(chiado)
    assert not tem_timbre_de_voz(np.zeros(1600, np.float32))
    assert segundos_com_timbre(np.concatenate([voz, chiado, voz])) == pytest.approx(0.2)


def test_previa_exige_menos_voz_que_o_texto_final(motor):
    """Exigir os 0,25 s inteiros tambem na previa atrasava a 1a palavra."""
    motor._model = ModeloFalso("Bom dia")
    assert motor._transcrever(AUDIVEL, final=False, voz=0.1) == "Bom dia"
    assert motor._transcrever(AUDIVEL, final=True, voz=0.1) == ""
