"""Resolucao do microfone salvo e nomes de dispositivo (vozflow/audio.py)."""

import pytest

from vozflow import audio

DISPOSITIVOS = [
    {"name": "Mapeador de som - Output", "max_input_channels": 0},
    {"name": "Microfone (Realtek(R) Audio)", "max_input_channels": 2},
    {"name": "Headset (@System32/drivers/bthhfenum.sys,#2;%1 Hands-Free%0 ;(AirPods))",
     "max_input_channels": 1},
    {"name": "Microfone (2- H510-PRO)", "max_input_channels": 1},
]


@pytest.fixture(autouse=True)
def lista_falsa(monkeypatch):
    monkeypatch.setattr(audio.sd, "query_devices", lambda: DISPOSITIVOS)


def test_vazio_e_none_sao_o_padrao_do_windows():
    assert audio.resolver_dispositivo(None) is None
    assert audio.resolver_dispositivo("") is None


def test_indice_antigo_so_vale_se_for_entrada():
    assert audio.resolver_dispositivo(1) == 1
    assert audio.resolver_dispositivo(0) is None   # e uma SAIDA
    assert audio.resolver_dispositivo(True) is None


def test_nome_exato_e_ignorando_caixa_e_espacos():
    assert audio.resolver_dispositivo("Microfone (Realtek(R) Audio)") == 1
    assert audio.resolver_dispositivo("  microfone  (realtek(r) audio) ") == 1


def test_nome_amigavel_tambem_resolve():
    assert audio.resolver_dispositivo("Headset AirPods") == 2


def test_aparelho_sumido_cai_no_padrao():
    assert audio.resolver_dispositivo("Microfone USB que nao existe mais") is None


def test_mesmo_aparelho_renomeado_ao_trocar_de_porta_usb():
    """F-027."""
    assert audio.resolver_dispositivo("Microfone (H510-PRO)") == 3


def test_nome_amigavel_do_bluetooth():
    cru = "Headset (@System32/drivers/bthhfenum.sys,#2;%1 Hands-Free%0 ;(AirPods))"
    assert audio.nome_amigavel(cru) == "Headset AirPods"
    assert audio.nome_amigavel("a\r\nb") == "a b"
    assert len(audio.nome_amigavel("x" * 80)) == 48


def test_nome_do_padrao_prefere_o_wasapi(monkeypatch):
    """O nome do MME vem cortado em 31 letras; o do WASAPI vem inteiro."""
    monkeypatch.setattr(audio.sd, "query_hostapis", lambda: [
        {"name": "MME", "default_input_device": 1},
        {"name": "Windows WASAPI", "default_input_device": 3}])
    assert audio.nome_do_padrao() == "Microfone (2- H510-PRO)"


def test_nome_do_padrao_sem_wasapi_usa_o_padrao_do_portaudio(monkeypatch):
    monkeypatch.setattr(audio.sd, "query_hostapis", lambda: [{"name": "MME", "default_input_device": 1}])
    monkeypatch.setattr(audio.sd.default, "device", [1, 0])
    assert audio.nome_do_padrao() == "Microfone (Realtek(R) Audio)"


def test_nome_do_padrao_sem_audio_nao_quebra(monkeypatch):
    def falha():
        raise OSError("sem PortAudio")
    monkeypatch.setattr(audio.sd, "query_hostapis", falha)
    assert audio.nome_do_padrao() is None


def test_nome_do_indice():
    assert audio.nome_do_indice(3) == "Microfone (2- H510-PRO)"
    assert audio.nome_do_indice(0) is None
