"""Microfone automatico (segue o padrao do Windows) e Configuracoes na frente."""

import pytest

from vozflow import audio, config, janela


# ----------------------------------------------------------------------
# microfone automatico
# ----------------------------------------------------------------------
@pytest.fixture
def portaudio(monkeypatch):
    registro = {"reinicios": 0, "abertos": []}

    class StreamFalso:
        def __init__(self, device=None, **_k):
            registro["abertos"].append(device)

        def start(self): pass
        def stop(self): pass
        def close(self): pass

    def reiniciar():
        registro["reinicios"] += 1
        return True

    monkeypatch.setattr(audio.sd, "InputStream", StreamFalso)
    monkeypatch.setattr(audio, "atualizar_lista_dispositivos", reiniciar)
    monkeypatch.setattr(audio.sd, "query_devices", lambda: [
        {"name": "Microfone (H510-PRO USB Gaming Headset)", "max_input_channels": 1}])
    monkeypatch.setattr(audio, "_abertos", 0)
    return registro


def test_automatico_recarrega_a_lista_e_usa_o_padrao_do_windows(portaudio):
    """O PortAudio so le o padrao do Windows ao iniciar; sem recarregar, um fone
    ligado depois (que vira o padrao) nunca era usado."""
    rec = audio.Recorder(device=None)
    rec.start()
    assert portaudio["reinicios"] == 1
    assert portaudio["abertos"] == [None]          # None = padrao do Windows
    assert rec.aviso is None
    rec.stop()


def test_microfone_escolhido_nao_recarrega_a_toa(portaudio):
    rec = audio.Recorder(device="Microfone (H510-PRO USB Gaming Headset)")
    rec.start()
    assert portaudio["reinicios"] == 0
    assert portaudio["abertos"] == [0]
    rec.stop()


def test_tela_oferece_o_automatico_como_recomendado(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    monkeypatch.setattr(configuracoes, "entradas_para_menu", lambda: [("Headset X", "Headset X")])
    dlg = configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))
    assert dlg.cbo_mic.itemData(0) is None
    assert "Autom" in dlg.cbo_mic.itemText(0) and "padr" in dlg.cbo_mic.itemText(0).lower()
    assert dlg.cbo_mic.currentIndex() == 0
    dlg.deleteLater()


# ----------------------------------------------------------------------
# Configuracoes abre na frente
# ----------------------------------------------------------------------
class User32Falso:
    def __init__(self, primeiro_plano=0x500):
        self.fg = primeiro_plano
        self.chamadas = []

    def GetForegroundWindow(self):
        return self.fg

    def GetWindowThreadProcessId(self, hwnd, _pid):
        return {0x500: 77, 0x600: 11}.get(hwnd, 0)

    def AttachThreadInput(self, a, b, ligar):
        self.chamadas.append(("attach", a, b, bool(ligar)))
        return 1

    def IsWindow(self, hwnd):
        return 1

    def IsIconic(self, hwnd):
        return 0

    def IsHungAppWindow(self, hwnd):
        return 0

    def ShowWindow(self, hwnd, modo):
        self.chamadas.append(("show", hwnd, modo))

    def SetForegroundWindow(self, hwnd):
        self.chamadas.append(("foreground", hwnd))
        self.fg = hwnd
        return 1

    def BringWindowToTop(self, hwnd):
        self.chamadas.append(("top", hwnd))

    def SetActiveWindow(self, hwnd):
        self.chamadas.append(("active", hwnd))


class Kernel32Falso:
    def GetCurrentThreadId(self):
        return 11


def test_trazer_para_frente_anexa_a_fila_da_janela_em_primeiro_plano(monkeypatch):
    """O Windows so deixa trazer janela para a frente quem ja esta na frente; o
    VozFlow (na bandeja) nao esta. Anexar a fila da janela em primeiro plano
    (nao a da nossa, que e a mesma thread) contorna a trava."""
    u = User32Falso()
    monkeypatch.setattr(janela, "_u32", u)
    monkeypatch.setattr(janela, "_k32", Kernel32Falso())
    assert janela.trazer_para_frente(0x600)
    assert ("attach", 11, 77, True) in u.chamadas
    assert ("foreground", 0x600) in u.chamadas
    assert u.chamadas[-1] == ("attach", 11, 77, False)     # sempre desanexa


def test_configuracoes_pedem_para_vir_para_a_frente_ao_abrir(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    pedidos = []
    monkeypatch.setattr(configuracoes, "entradas_para_menu", lambda: [])
    monkeypatch.setattr(configuracoes.janela, "trazer_para_frente", lambda h: pedidos.append(h) or True)
    monkeypatch.setattr(configuracoes, "Recorder", lambda **_k: type("R", (), {
        "start": lambda s: None, "stop": lambda s: None,
        "drain": lambda s: audio.np.empty(0, dtype="float32")})())
    dlg = configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))
    dlg.show()
    from conftest import esperar
    assert esperar(lambda: pedidos, app=qapp, timeout=2)
    assert pedidos[-1] == int(dlg.winId())
    dlg.done(0)
    dlg.deleteLater()


# ----------------------------------------------------------------------
# revisao: reiniciar o PortAudio nunca com microfone aberto
# ----------------------------------------------------------------------
def test_calibracao_conta_o_microfone_aberto(monkeypatch):
    """Sem contar, uma ditada iniciada pela bandeja durante a calibracao
    reiniciava o PortAudio com o stream vivo - o que derruba o processo."""
    from vozflow import calibracao

    visto = []

    class StreamFalso:
        def __init__(self, **_k):
            visto.append(audio._abertos)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(audio, "_abertos", 0)
    monkeypatch.setattr(audio.sd, "InputStream", StreamFalso)
    monkeypatch.setattr(calibracao.time, "sleep", lambda _s: None)
    calibracao._medir(None, segundos=0)
    assert visto == [1]
    assert audio._abertos == 0


def test_microfone_conta_antes_de_abrir_e_desconta_se_falhar(monkeypatch):
    visto = []

    class StreamQueFalha:
        def __init__(self, **_k):
            visto.append(audio._abertos)
            raise audio.sd.PortAudioError("dispositivo ocupado")

    monkeypatch.setattr(audio, "_abertos", 0)
    monkeypatch.setattr(audio.sd, "InputStream", StreamQueFalha)
    monkeypatch.setattr(audio, "atualizar_lista_dispositivos", lambda: True)
    with pytest.raises(audio.sd.PortAudioError):
        audio.Recorder(device=None).start()
    assert visto == [1]
    assert audio._abertos == 0


def test_automatico_nao_reinicia_o_portaudio_com_outro_microfone_aberto(monkeypatch):
    reinicios = []
    monkeypatch.setattr(audio, "_abertos", 1)          # calibracao gravando
    monkeypatch.setattr(audio.sd, "_terminate", lambda: reinicios.append(1))
    assert audio.atualizar_lista_dispositivos() is False
    assert reinicios == []


def test_janela_da_frente_travada_nao_e_anexada(monkeypatch):
    """AttachThreadInput com uma janela que nao responde pode travar a nossa."""
    u = User32Falso()
    u.IsHungAppWindow = lambda hwnd: 1
    monkeypatch.setattr(janela, "_u32", u)
    monkeypatch.setattr(janela, "_k32", Kernel32Falso())
    janela.trazer_para_frente(0x600)
    assert not [c for c in u.chamadas if c[0] == "attach"]
    assert ("foreground", 0x600) in u.chamadas
