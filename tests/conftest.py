"""Ambiente de teste do VozFlow: nada de microfone, teclado global ou Enter real.

O CONTRIBUTING explica por que: um teste com o microfone real e "apertar Enter"
ligado ja captou voz da sala e mandou mensagem no terminal. Aqui todo efeito
colateral do app (teclas, clipboard, foco de janela, motor Whisper) e trocado
por um duble que so anota o que teria acontecido.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

# Antes de importar qualquer modulo do vozflow: config.py le a variavel na
# importacao, e sem ela o teste gravaria por cima da config real do usuario.
_PASTA_CONFIG = tempfile.mkdtemp(prefix="vozflow-testes-")
atexit.register(shutil.rmtree, _PASTA_CONFIG, True)
os.environ["VOZFLOW_CONFIG_DIR"] = _PASTA_CONFIG
# Atribuido, nao setdefault: com QT_QPA_PLATFORM=windows no ambiente cada
# teste poria um icone real na bandeja e soltaria balao de "Pronto".
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Com VOZFLOW_DEBUG herdado, o app gravaria o texto dos testes em %TEMP%.
os.environ.pop("VOZFLOW_DEBUG", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6 import QtCore, QtWidgets  # noqa: E402

from vozflow import config  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture(autouse=True)
def timers_terminam_dentro_do_teste(monkeypatch):
    """Espera os threading.Timer do teste antes de desfazer os dubles.

    O colar() agenda a restauracao do clipboard para 0,8 s depois. Se o teste
    acabasse antes, o monkeypatch ja teria devolvido o pyperclip real e o
    Timer escreveria na area de transferencia de verdade do usuario.
    (Depende de monkeypatch para ser desmontada ANTES dele.)
    """
    antes = set(threading.enumerate())
    yield
    for t in threading.enumerate():
        if t not in antes and isinstance(t, threading.Timer):
            t.join(timeout=5)


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Nenhum teste fala com a internet. O atualizador consulta o GitHub: um
    teste que esquecesse de trocar a consulta por um duble acessava a API de
    verdade (aconteceu) - agora falha na hora. pytest.fail e BaseException:
    o `except Exception` do atualizador nao consegue engolir."""
    import socket

    def bloqueada(*_a, **_k):
        pytest.fail("teste tentou acessar a rede")

    monkeypatch.setattr(socket.socket, "connect", bloqueada)
    monkeypatch.setattr(socket, "create_connection", bloqueada)


@pytest.fixture
def pasta_config(tmp_path, monkeypatch):
    """Config isolada por teste."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "transcricoes.txt")
    return tmp_path


def esperar(condicao, timeout: float = 5.0, app=None) -> bool:
    """Roda o loop do Qt ate a condicao valer (sinais entre threads sao enfileirados)."""
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if app is not None:
            app.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    if app is not None:
        app.processEvents()
    return bool(condicao())


# ----------------------------------------------------------------------
# Dubles
# ----------------------------------------------------------------------
class TecladoFalso:
    """Substitui a lib `keyboard`: anota o que seria digitado, nunca injeta tecla."""

    def __init__(self):
        self.escrito: list[str] = []
        self.enviados: list[str] = []
        self.atalhos: list[str] = []
        self.presos: set[str] = set()
        self._trava = threading.Lock()

    def write(self, texto, delay=0):  # noqa: ARG002
        with self._trava:
            self.escrito.append(texto)

    def send(self, combo):
        with self._trava:
            self.enviados.append(combo)

    def is_pressed(self, tecla):
        return tecla in self.presos

    def release(self, _tecla):
        pass

    def add_hotkey(self, combo, _fn, suppress=False):  # noqa: ARG002
        self.atalhos.append(combo)

    def unhook_all_hotkeys(self):
        self.atalhos.clear()

    @property
    def texto(self) -> str:
        with self._trava:
            return "".join(self.escrito)


class ClipboardFalso:
    def __init__(self, inicial: str = ""):
        self.valor = inicial
        self.historico: list[str] = []

    def copy(self, texto):
        self.valor = texto
        self.historico.append(texto)

    def paste(self):
        return self.valor


class JanelaFalsa:
    """Substitui vozflow.janela. `foco` e o HWND em primeiro plano."""

    def __init__(self, foco: int = 0x100):
        self.foco = foco
        self.existentes = {0x100, 0x200, 0x300, 0x900}
        self.sistema = {0x900}             # barra de tarefas / bandeja
        self.restaurar_ok = True
        self.restauradas: list[int] = []

    def atual(self):
        return self.foco

    def alvo_valido(self, hwnd):
        return bool(hwnd) and hwnd not in self.sistema

    def existe(self, hwnd):
        return bool(hwnd) and hwnd in self.existentes

    def em_foco(self, hwnd):
        return not hwnd or hwnd == self.foco

    def restaurar(self, hwnd, espera=1.2):  # noqa: ARG002
        self.restauradas.append(hwnd)
        if not self.existe(hwnd) or not self.restaurar_ok:
            return False
        self.foco = hwnd
        return True

    def nome_curto(self, hwnd, limite=38):  # noqa: ARG002
        return {0x100: "Bloco de notas", 0x200: "Outra janela",
                0x300: "Terceira"}.get(hwnd, "")

    def titulo(self, hwnd):
        return self.nome_curto(hwnd)


class OverlayFalso:
    def __init__(self, cfg):
        self.cfg = cfg
        self.mensagens: list[tuple[str, str]] = []

    def preaquecer(self): pass
    def aplicar_config(self): pass

    def esconder(self):
        self.mensagens.append(("esconder", ""))
    def set_nivel(self, _v): pass
    def set_estado(self, _e): pass

    def set_texto(self, texto):
        self.mensagens.append(("texto", texto))

    def mostrar(self, estado="rec", texto=""):
        self.mensagens.append((estado, texto))

    def flash(self, texto, estado="done", ms=0):  # noqa: ARG002
        self.mensagens.append((estado, texto))


class MotorFalso(QtCore.QObject):
    """Mesma interface publica do LiveTranscriber, sem Whisper nem microfone."""

    ready = QtCore.Signal(str)
    status = QtCore.Signal(str)
    level = QtCore.Signal(float)
    text = QtCore.Signal(str, bool)
    segmento = QtCore.Signal(str)
    done = QtCore.Signal(str)
    dica = QtCore.Signal(str)
    baixando = QtCore.Signal(bool)
    failed = QtCore.Signal(str)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.comandos: list[str] = []
        self._recording = False

    @property
    def recording(self):
        return self._recording

    def start(self): pass
    def wait(self, _ms=0): return True

    def cmd_start(self):
        self.comandos.append("start")
        self._recording = True

    def cmd_stop(self):
        self.comandos.append("stop")

    def cmd_cancel(self):
        self.comandos.append("cancel")
        self._recording = False

    def cmd_quit(self):
        self.comandos.append("quit")


class GuardaFalsa:
    def vigiar(self, _combo): return None
    def liberado(self, _sc): return True
    def limpar(self): pass


@pytest.fixture
def vozflow_app(qapp, pasta_config, monkeypatch):
    """Instancia o VozFlow real com todos os efeitos externos trocados por dubles.

    Devolve uma fabrica: `criar(**cfg)` -> (app, teclado, clipboard, janela).
    """
    from vozflow import app as modulo_app
    from vozflow import inserter
    import pyperclip

    criados = []

    def criar(**ajustes):
        teclado = TecladoFalso()
        clip = ClipboardFalso("conteudo anterior")
        jan = JanelaFalsa()
        monkeypatch.setattr(modulo_app, "keyboard", teclado)
        monkeypatch.setattr(inserter, "keyboard", teclado)
        monkeypatch.setattr(pyperclip, "copy", clip.copy)
        monkeypatch.setattr(pyperclip, "paste", clip.paste)
        monkeypatch.setattr(modulo_app, "janela", jan)
        monkeypatch.setattr(modulo_app, "Overlay", OverlayFalso)
        monkeypatch.setattr(modulo_app, "LiveTranscriber", MotorFalso)
        monkeypatch.setattr(modulo_app, "GuardaNumerico", GuardaFalsa)
        monkeypatch.setattr(modulo_app, "_som", lambda _n: None)
        monkeypatch.setattr(modulo_app, "set_startup", lambda _a: None)

        cfg = config.Config(dict(config.DEFAULTS))
        # cadencia mais rapida para o teste nao esperar segundos por frase
        cfg.update({"sounds": False, "partial_interval": 0.15})
        cfg.update(ajustes)
        monkeypatch.setattr(modulo_app.config, "load", lambda: cfg)

        app = modulo_app.VozFlow(qapp)
        app._ao_carregar("teste / cpu / int8")
        criados.append(app)
        return app, teclado, clip, jan

    yield criar

    for app in criados:
        app._fila.put(None)
        app._thread_insercao.join(timeout=3)
        app.tray.hide()
