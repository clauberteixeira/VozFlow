"""Reconhecer so a minha voz: ignora quem conversa ao fundo (vozflow/voz.py).

O modelo de voz real nao e usado aqui: um extrator falso devolve a "nota" que
o teste escolhe para cada pedaco de audio, conforme um marcador gravado nele.
"""

import json

import numpy as np
import pytest

from vozflow import config, voz

SR = 16000


# ----------------------------------------------------------------------
# regra de corte (pura)
# ----------------------------------------------------------------------
def _janelas(notas, nivel=0.05, passo=voz.PASSO):
    """Lista (inicio, nota, rms) com janelas consecutivas."""
    return [(i * passo, n, nivel) for i, n in enumerate(notas)]


def test_corta_so_sequencia_de_voz_alheia_e_mais_baixa():
    janelas = _janelas([0.9, 0.9, 0.4, 0.45, 0.5, 0.9], nivel=0.02)
    cortes = voz.trechos_alheios(janelas, nivel_voce=0.05)
    assert cortes == [(2 * voz.PASSO, 4 * voz.PASSO + voz.JANELA)]


def test_janela_isolada_nao_corta():
    """Uma janela so pode ser engano; o pior erro e apagar palavra sua."""
    assert voz.trechos_alheios(_janelas([0.9, 0.4, 0.9], nivel=0.02), nivel_voce=0.05) == []


def test_voz_alheia_no_seu_volume_nao_corta():
    """Voces dois falando juntos: o volume esta no seu nivel -> nao mexe."""
    janelas = _janelas([0.5, 0.5, 0.5, 0.5], nivel=0.05)
    assert voz.trechos_alheios(janelas, nivel_voce=0.05) == []


def test_nota_ambigua_nao_corta():
    janelas = _janelas([0.65, 0.66, 0.64], nivel=0.02)
    assert voz.trechos_alheios(janelas, nivel_voce=0.05) == []


def test_aplicar_silencia_so_os_trechos():
    x = np.ones(SR * 3, np.float32)
    y = voz.aplicar(x, [(SR, 2 * SR)])
    assert y[: SR].all() and not y[SR:2 * SR].any() and y[2 * SR:].all()
    assert x.all()                                   # original intacto


# ----------------------------------------------------------------------
# impressao da voz: so no PC, apagavel
# ----------------------------------------------------------------------
def test_salvar_carregar_e_esquecer(pasta_config):
    assert voz.carregar_impressao() is None
    voz.salvar_impressao(np.arange(4, dtype=np.float32), nivel=0.04)
    imp = voz.carregar_impressao()
    assert imp.nivel == pytest.approx(0.04)
    assert np.allclose(imp.vetor, np.arange(4) / np.linalg.norm(np.arange(4)))
    assert (pasta_config / voz.ARQUIVO_IMPRESSAO).exists()
    voz.esquecer()
    assert voz.carregar_impressao() is None
    assert not (pasta_config / voz.ARQUIVO_IMPRESSAO).exists()


def test_impressao_corrompida_e_ignorada(pasta_config):
    (pasta_config / voz.ARQUIVO_IMPRESSAO).write_text("{ quebrado", encoding="utf-8")
    assert voz.carregar_impressao() is None


def test_nivel_da_voz_ignora_silencio():
    fala = 0.05 * np.sin(np.arange(SR * 2) * 0.2).astype(np.float32)
    x = np.concatenate([np.zeros(SR * 2, np.float32), fala])
    assert voz.nivel_da_fala(x) == pytest.approx(0.05 / np.sqrt(2), rel=0.05)


# ----------------------------------------------------------------------
# modelo: revisao fixa e hash conferido
# ----------------------------------------------------------------------
def test_modelo_com_hash_errado_e_recusado(tmp_path, monkeypatch):
    falso = tmp_path / voz.MODELO_ARQUIVO
    falso.write_bytes(b"isto nao e o modelo")
    pedidos = []

    def baixar(repo_id, filename, revision):
        pedidos.append((repo_id, filename, revision))
        return str(falso)

    monkeypatch.setattr(voz, "_hf_hub_download", baixar)
    with pytest.raises(voz.ModeloInvalido):
        voz.garantir_modelo()
    assert pedidos == [(voz.MODELO_REPO, voz.MODELO_ARQUIVO, voz.MODELO_REVISAO)]


def test_modelo_certo_e_aceito(tmp_path, monkeypatch):
    arq = tmp_path / voz.MODELO_ARQUIVO
    arq.write_bytes(b"modelo de teste")
    import hashlib

    monkeypatch.setattr(voz, "_hf_hub_download", lambda **_k: str(arq))
    monkeypatch.setattr(voz, "MODELO_SHA256", hashlib.sha256(b"modelo de teste").hexdigest())
    assert voz.garantir_modelo() == str(arq)


# ----------------------------------------------------------------------
# filtro no motor
# ----------------------------------------------------------------------
class VerificadorFalso:
    """Nota pelo marcador: amplitude ~0.05 = voce, ~0.02 = outra pessoa."""

    def __init__(self):
        self.chamadas = 0

    def nota(self, trecho):
        self.chamadas += 1
        return 0.9 if np.max(np.abs(trecho)) > 0.035 else 0.4


def _fala(amplitude, segundos):
    return (amplitude * np.sin(np.arange(int(SR * segundos)) * 0.3)).astype(np.float32)


@pytest.fixture
def motor(qapp, pasta_config):
    from vozflow.transcriber import LiveTranscriber

    c = config.Config(dict(config.DEFAULTS))
    c["so_minha_voz"] = True
    m = LiveTranscriber(c)
    m._verificador = VerificadorFalso()
    m._impressao = voz.Impressao(np.ones(4, np.float32) / 2, nivel=0.05 / np.sqrt(2))
    return m


def test_motor_silencia_a_conversa_de_fundo_antes_do_whisper(motor):
    x = np.concatenate([_fala(0.05, 2), _fala(0.02, 3), _fala(0.05, 2)])
    y = motor._filtrar(x)
    assert np.abs(y[: SR]).max() > 0.04                     # voce, inicio
    assert np.abs(y[int(2.6 * SR): int(4.4 * SR)]).max() == 0  # fundo, silenciado
    assert np.abs(y[-SR:]).max() > 0.04                     # voce, fim


def test_motor_nao_recalcula_janelas_ja_vistas(motor):
    x = np.concatenate([_fala(0.05, 2), _fala(0.02, 3)])
    motor._filtrar(x)
    antes = motor._verificador.chamadas
    motor._filtrar(np.concatenate([x, _fala(0.05, 0.5)]))   # previa seguinte: +0,5 s
    assert motor._verificador.chamadas - antes <= 2


def test_desligado_nao_mexe_no_audio(motor):
    motor.cfg["so_minha_voz"] = False
    x = np.concatenate([_fala(0.05, 2), _fala(0.02, 3)])
    assert motor._filtrar(x) is x
    assert motor._verificador.chamadas == 0


def test_sem_impressao_nao_mexe_no_audio(motor):
    motor._impressao = None
    x = _fala(0.02, 3)
    assert motor._filtrar(x) is x


def test_cache_zera_no_proximo_trecho(motor):
    motor._filtrar(_fala(0.05, 2))
    assert motor._notas_janela
    motor._reset_buffers()
    assert not motor._notas_janela


def test_segundo_trecho_nao_herda_as_notas_do_primeiro(motor):
    """Revisao: o trecho 2 (so voce) saia cortado nas posicoes em que o trecho 1
    teve conversa de fundo, porque o cache nao era zerado ao fechar o trecho."""
    recebido = []

    class ModeloFalso:
        def transcribe(self, audio, **_k):
            recebido.append(audio)
            return [], None

    motor._model = ModeloFalso()
    motor._buf = np.concatenate([_fala(0.05, 2), _fala(0.02, 3), _fala(0.05, 2)])
    motor._fechar_trecho()                                   # trecho 1: corta o fundo
    assert np.abs(recebido[-1][int(2.6 * SR): int(4.4 * SR)]).max() == 0
    motor._buf = _fala(0.05, 7)                              # trecho 2: so voce
    motor._fechar_trecho()
    assert np.abs(recebido[-1][int(2.6 * SR): int(4.4 * SR)]).max() > 0.04


def test_transcrever_usa_o_audio_filtrado(motor):
    recebido = []

    class ModeloFalso:
        def transcribe(self, audio, **_k):
            recebido.append(audio)
            return [], None

    motor._model = ModeloFalso()
    x = np.concatenate([_fala(0.05, 2), _fala(0.02, 3), _fala(0.05, 2)])
    motor._transcrever(x, final=True)
    assert np.abs(recebido[-1][int(2.6 * SR): int(4.4 * SR)]).max() == 0


# ----------------------------------------------------------------------
# configuracao e tela
# ----------------------------------------------------------------------
def test_padrao_desligado(pasta_config):
    assert config.load()["so_minha_voz"] is False


def test_tela_so_permite_ligar_depois_de_gravar_a_voz(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    monkeypatch.setattr(configuracoes, "entradas_para_menu", lambda: [])
    dlg = configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))
    assert not dlg.chk_so_minha_voz.isEnabled()
    assert not dlg.btn_esquecer_voz.isEnabled()
    voz.salvar_impressao(np.ones(4, np.float32), nivel=0.04)
    dlg._atualizar_so_minha_voz()
    assert dlg.chk_so_minha_voz.isEnabled() and dlg.btn_esquecer_voz.isEnabled()
    dlg.chk_so_minha_voz.setChecked(True)
    dlg._salvar()
    assert json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))["so_minha_voz"] is True
    dlg.deleteLater()


def test_esquecer_na_tela_apaga_e_desliga(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    monkeypatch.setattr(configuracoes, "entradas_para_menu", lambda: [])
    voz.salvar_impressao(np.ones(4, np.float32), nivel=0.04)
    c = config.Config(dict(config.DEFAULTS))
    c["so_minha_voz"] = True
    dlg = configuracoes.JanelaConfiguracoes(c)
    assert dlg.chk_so_minha_voz.isChecked()
    dlg._esquecer_voz()
    assert voz.carregar_impressao() is None
    assert not dlg.chk_so_minha_voz.isChecked() and not dlg.chk_so_minha_voz.isEnabled()
    dlg.deleteLater()
