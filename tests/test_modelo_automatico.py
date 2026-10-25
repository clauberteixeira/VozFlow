"""L6: modelo automatico (GPU x CPU) e prevista adaptativa (F-014, decisao D3).

Medido nesta maquina, mesmo audio de 17,6 s: cada previa do large-v3-turbo
levou 12,3-13,6 s na CPU (int8) contra 0,9-1,2 s do base; na GPU, 0,31-0,45 s.
"""

import json

import pytest

from vozflow import config, modelo


# ----------------------------------------------------------------------
# escolha do modelo
# ----------------------------------------------------------------------
@pytest.mark.parametrize("nome,device,esperado", [
    ("auto", "cuda", "large-v3-turbo"),
    ("auto", "cpu", "base"),
    ("small", "cpu", "small"),            # escolha explicita e respeitada
    ("large-v3-turbo", "cpu", "large-v3-turbo"),
])
def test_resolver_modelo(nome, device, esperado):
    assert modelo.resolver_nome(nome, device) == esperado


def test_padrao_novo_e_automatico(pasta_config):
    assert config.load()["model"] == "auto"


def test_config_antiga_com_o_padrao_antigo_vira_automatico(pasta_config):
    """Quem instalou a 1.1.1 tem "large-v3-turbo" gravado so por ser o padrao."""
    config.CONFIG_PATH.write_text(json.dumps({"model": "large-v3-turbo"}), encoding="utf-8")
    assert config.load()["model"] == "auto"


def test_escolha_explicita_depois_da_migracao_e_mantida(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps(
        {"model": "large-v3-turbo", "config_versao": 2}), encoding="utf-8")
    assert config.load()["model"] == "large-v3-turbo"


def test_config_antiga_com_outro_modelo_nao_muda(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps({"model": "small"}), encoding="utf-8")
    assert config.load()["model"] == "small"


# ----------------------------------------------------------------------
# motor
# ----------------------------------------------------------------------
@pytest.fixture
def carregar(qapp, pasta_config, monkeypatch):
    import faster_whisper

    from vozflow import transcriber

    carregados = []

    class ModeloFalso:
        def __init__(self, caminho, device, compute_type):
            if device == "cuda" and falhar_gpu[0]:
                raise RuntimeError("CUDA driver version is insufficient")
            carregados.append((caminho, device, compute_type))

        def transcribe(self, *_a, **_k):
            return [], None

    falhar_gpu = [False]
    monkeypatch.setattr(faster_whisper, "WhisperModel", ModeloFalso)
    monkeypatch.setattr(transcriber, "_prepare_cuda_dlls", lambda: [])
    monkeypatch.setattr(transcriber.modelo_util, "ja_baixado", lambda _n: True)
    monkeypatch.setattr(transcriber.modelo_util, "garantir", lambda n, *_a: "/cache/" + n)

    def rodar(gpu: bool, falha_na_gpu: bool = False, **cfg):
        falhar_gpu[0] = falha_na_gpu
        monkeypatch.setattr(transcriber, "_cuda_disponivel", lambda: gpu)
        c = config.Config(dict(config.DEFAULTS))
        c.update(cfg)
        motor = transcriber.LiveTranscriber(c)
        assert motor._load_model()
        return motor, carregados

    return rodar


def test_com_gpu_o_automatico_usa_o_modelo_grande(carregar):
    motor, carregados = carregar(gpu=True)
    assert carregados[-1] == ("/cache/large-v3-turbo", "cuda", "float16")
    assert motor.backend.startswith("large-v3-turbo / cuda")


def test_sem_gpu_o_automatico_usa_o_modelo_leve(carregar):
    motor, carregados = carregar(gpu=False)
    assert carregados[-1] == ("/cache/base", "cpu", "int8")
    assert motor.backend.startswith("base / cpu")


def test_gpu_que_falha_cai_para_cpu_com_o_modelo_leve(carregar):
    motor, carregados = carregar(gpu=True, falha_na_gpu=True)
    assert carregados[-1] == ("/cache/base", "cpu", "int8")


def test_modelo_escolhido_a_mao_vale_tambem_na_cpu(carregar):
    _motor, carregados = carregar(gpu=False, model="small")
    assert carregados[-1] == ("/cache/small", "cpu", "int8")


@pytest.mark.parametrize("intervalo,duracao,esperado", [
    (0.45, 0.30, 0.45),     # GPU: previa mais rapida que o intervalo -> nada muda
    (0.45, 0.45, 0.45),
    (0.45, 1.00, 1.25),     # CPU: previa de 1 s -> folga para o microfone e o resto
    (0.90, 0.50, 0.90),
    (0.45, 8.00, 2.00),     # um caso isolado lento nao pode travar as previas
])
def test_intervalo_da_previa_se_adapta_a_maquina(qapp, pasta_config, intervalo, duracao, esperado):
    from vozflow.transcriber import LiveTranscriber

    c = config.Config(dict(config.DEFAULTS))
    c["partial_interval"] = intervalo
    motor = LiveTranscriber(c)
    assert motor._proximo_intervalo(duracao) == pytest.approx(esperado)


@pytest.mark.parametrize("na_cpu,final,temperatura,teto", [
    (True, False, [0.0], 16 + 12 * 2),            # previa na CPU: sem fallback, teto de tokens
    (True, True, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], None),   # final: protecao completa
    (False, False, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], None),  # GPU: exatamente como antes
])
def test_previa_na_cpu_nao_paga_o_fallback_de_temperatura(qapp, pasta_config, na_cpu, final,
                                                          temperatura, teto):
    """Medido: a 1a previa (0,7 s de audio) levava 3-8 s na CPU refazendo a
    decodificacao ate 6 vezes; na GPU isso custa milissegundos."""
    import numpy as np

    from vozflow.transcriber import LiveTranscriber

    pedidos = []

    class ModeloFalso:
        def transcribe(self, _audio, **kw):
            pedidos.append(kw)
            return [], None

    motor = LiveTranscriber(config.Config(dict(config.DEFAULTS)))
    motor._model = ModeloFalso()
    motor._na_cpu = na_cpu
    voz = (0.1 * np.sin(np.arange(32000) * 0.3)).astype(np.float32)   # 2 s audivel
    motor._transcrever(voz, final=final)
    assert pedidos[-1]["temperature"] == temperatura
    assert pedidos[-1].get("max_new_tokens") == teto


# ----------------------------------------------------------------------
# tela e diagnostico
# ----------------------------------------------------------------------
def test_configuracoes_oferecem_e_salvam_o_automatico(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    monkeypatch.setattr(configuracoes, "entradas_para_menu", lambda: [])
    dlg = configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))
    assert dlg.cbo_modelo.currentData() == "auto"
    assert "Autom" in dlg.cbo_modelo.currentText()
    dlg.cbo_modelo.setCurrentIndex(dlg.cbo_modelo.findData("small"))
    dlg._salvar()
    assert dlg.cfg["model"] == "small"
    assert dlg.modelo_mudou
    dlg.deleteLater()


def test_diagnostico_resolve_o_automatico(pasta_config, monkeypatch, capsys):
    import faster_whisper

    from vozflow import diagnostico

    pedidos = []
    monkeypatch.setattr(faster_whisper, "WhisperModel",
                        lambda nome, device, compute_type: pedidos.append((nome, device)))
    monkeypatch.setattr(diagnostico, "_cuda_disponivel", lambda: False)
    monkeypatch.setattr(diagnostico, "_prepare_cuda_dlls", lambda: [])
    monkeypatch.setattr("sys.argv", ["diagnostico"])
    assert diagnostico.main() == 0
    assert pedidos == [("base", "cpu")]
