"""L5: config validada, microfone tolerante e calibracao que respeita o Cancelar."""

import json
import os

import pytest

from vozflow import audio, config


# ----------------------------------------------------------------------
# F-009: config
# ----------------------------------------------------------------------
@pytest.mark.parametrize("conteudo", ["5", '"texto"', "[1, 2]", "null"])
def test_json_que_nao_e_objeto_vira_bak_e_padroes(pasta_config, conteudo):
    config.CONFIG_PATH.write_text(conteudo, encoding="utf-8")
    cfg = config.load()
    assert cfg == config.DEFAULTS
    assert config.CONFIG_PATH.with_suffix(".json.bak").read_text(encoding="utf-8") == conteudo


def test_tipo_errado_volta_ao_padrao_so_naquela_chave(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps({
        "silence_ms": "700",          # texto onde vai numero
        "overlay_width": "abc",
        "sounds": "sim",              # texto onde vai bool
        "hotkey_start": 5,            # numero onde vai texto
        "partial_interval": 1,        # int onde vai float: vale
        "nivel_fala": True,           # bool NAO passa por numero
        "language": "en",             # valido
    }), encoding="utf-8")
    cfg = config.load()
    d = config.DEFAULTS
    assert cfg["silence_ms"] == d["silence_ms"]
    assert cfg["overlay_width"] == d["overlay_width"]
    assert cfg["sounds"] == d["sounds"]
    assert cfg["hotkey_start"] == d["hotkey_start"]
    assert cfg["partial_interval"] == 1
    assert cfg["nivel_fala"] == d["nivel_fala"]
    assert cfg["language"] == "en"


def test_microfone_aceita_nome_ou_nenhum(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps({"input_device": "Headset"}), encoding="utf-8")
    assert config.load()["input_device"] == "Headset"
    config.CONFIG_PATH.write_text(json.dumps({"input_device": [1]}), encoding="utf-8")
    assert config.load()["input_device"] is None


def test_chave_desconhecida_e_preservada(pasta_config):
    config.CONFIG_PATH.write_text(json.dumps({"chave_do_futuro": 1}), encoding="utf-8")
    assert config.load()["chave_do_futuro"] == 1


def test_gravacao_atomica_sem_sobra_temporaria(pasta_config):
    config.load().save()
    assert sorted(p.name for p in pasta_config.iterdir()) == ["config.json"]


def test_nao_regrava_quando_nada_mudou(pasta_config):
    config.load()
    os.utime(config.CONFIG_PATH, (1_000_000, 1_000_000))
    config.load()
    assert config.CONFIG_PATH.stat().st_mtime == 1_000_000


# ----------------------------------------------------------------------
# F-027 e F-008 (parte do microfone)
# ----------------------------------------------------------------------
def test_microfone_renomeado_pela_porta_usb(monkeypatch):
    monkeypatch.setattr(audio.sd, "query_devices", lambda: [
        {"name": "Microfone (Realtek(R) Audio)", "max_input_channels": 2},
        {"name": "Microfone (2- H510-PRO)", "max_input_channels": 1},
    ])
    assert audio.resolver_dispositivo("Microfone (H510-PRO)") == 1
    assert audio.resolver_dispositivo("Microfone (3- H510-PRO)") == 1


def test_parar_microfone_que_sumiu_nao_derruba_o_motor(monkeypatch):
    """Fone Bluetooth caiu: o stop() do PortAudio levanta erro."""
    fechados = []

    class StreamQueSumiu:
        def stop(self):
            raise audio.sd.PortAudioError("Unanticipated host error")

        def close(self):
            fechados.append(True)

    monkeypatch.setattr(audio, "_abertos", 0)
    rec = audio.Recorder()
    rec._stream = StreamQueSumiu()
    audio._contar(+1)
    rec.stop()                       # nao levanta
    assert rec._stream is None
    assert audio._abertos == 0
    assert "host error" in (rec.last_error or "")
    # sem close() o PortAudio poderia ser reiniciado com o stream vivo
    assert fechados == [True]


# ----------------------------------------------------------------------
# F-012 e F-021: calibracao
# ----------------------------------------------------------------------
@pytest.fixture
def dialogo(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    abertos = []

    class RecorderFalso:
        def __init__(self, device=None):
            abertos.append(self)

        def start(self): pass
        def stop(self): abertos.remove(self)
        def drain(self): return audio.np.empty(0, dtype="float32")

    monkeypatch.setattr(configuracoes, "Recorder", RecorderFalso)
    monkeypatch.setattr(configuracoes, "entradas_para_menu", lambda: [])
    cfg = config.Config(dict(config.DEFAULTS))
    dlg = configuracoes.JanelaConfiguracoes(cfg)
    dlg.abertos = abertos
    yield dlg
    dlg.deleteLater()


def test_calibracao_so_vale_ao_salvar(dialogo):
    antes = dialogo.cfg["nivel_fala"]
    dialogo._fim_ui(0.02, "Calibrado")
    assert dialogo.cfg["nivel_fala"] == antes         # Cancelar ainda desfaz
    dialogo._salvar()
    assert dialogo.cfg["nivel_fala"] == 0.02
    assert json.loads(config.CONFIG_PATH.read_text(encoding="utf-8"))["nivel_fala"] == 0.02


def test_calibracao_que_termina_depois_de_fechar_nao_reabre_o_microfone(dialogo):
    antes = dialogo.cfg["nivel_fala"]
    dialogo._calibrando = True
    dialogo.done(0)                                    # Cancelar no meio
    dialogo._fim_ui(0.02, "Calibrado")                 # a thread termina depois
    assert dialogo.abertos == []
    assert dialogo.cfg["nivel_fala"] == antes


# ----------------------------------------------------------------------
# F-015: instancia unica
# ----------------------------------------------------------------------
@pytest.mark.skipif(os.name != "nt", reason="mutex do Windows")
def test_segunda_instancia_e_detectada():
    import main

    nome = "Local\\VozFlow_Teste_" + str(os.getpid())
    assert main._instancia_unica(nome) is True
    assert main._instancia_unica(nome) is False
