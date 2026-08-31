"""Janela flutuante que mostra o texto sendo transcrito em tempo real.

Ela nunca recebe foco nem clique: o cursor continua na janela onde voce estava,
que e exatamente onde o texto sera colado no fim.
"""

from __future__ import annotations

import math
from collections import deque

from PySide6 import QtCore, QtGui, QtWidgets

CORES = {
    "rec": QtGui.QColor(240, 68, 68),
    "proc": QtGui.QColor(245, 166, 35),
    "done": QtGui.QColor(74, 200, 120),
    "erro": QtGui.QColor(240, 68, 68),
    "idle": QtGui.QColor(140, 140, 150),
}
MAX_CHARS = 260


class _Indicador(QtWidgets.QWidget):
    """Bolinha de status + histograma do volume do microfone."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(78, 30)
        self.estado = "idle"
        self.fase = 0.0
        self.niveis: deque[float] = deque([0.0] * 20, maxlen=20)

    def push_level(self, valor: float) -> None:
        self.niveis.append(max(0.0, min(1.0, valor)))
        self.update()

    def tick(self) -> None:
        self.fase = (self.fase + 0.18) % (2 * math.pi)
        if self.estado != "rec":
            self.niveis.append(0.0)
        self.update()

    def paintEvent(self, _evt) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        cor = CORES.get(self.estado, CORES["idle"])

        # bolinha (pulsa enquanto grava)
        raio = 5.0
        if self.estado == "rec":
            raio += 1.6 * (0.5 + 0.5 * math.sin(self.fase))
        centro = QtCore.QPointF(9, self.height() / 2)
        halo = QtGui.QColor(cor)
        halo.setAlpha(60)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(centro, raio + 4, raio + 4)
        p.setBrush(cor)
        p.drawEllipse(centro, raio, raio)

        # barrinhas de volume
        x0, largura, gap = 24.0, 2.0, 2.6
        meio = self.height() / 2
        for i, n in enumerate(self.niveis):
            alt = max(2.0, n * (self.height() - 6))
            c = QtGui.QColor(cor)
            c.setAlpha(90 + int(140 * n))
            p.setBrush(c)
            p.drawRoundedRect(
                QtCore.QRectF(x0 + i * (largura + gap), meio - alt / 2, largura, alt), 1, 1
            )
        p.end()


# (chave salva, rotulo na tela). A chave e "vertical-horizontal"; "centro"
# sozinho fica no meio da tela.
POSICOES = [
    ("inferior-centro", "Rodape, centralizado"),
    ("inferior-esquerda", "Rodape, a esquerda"),
    ("inferior-direita", "Rodape, a direita"),
    ("superior-centro", "Topo, centralizado"),
    ("superior-esquerda", "Topo, a esquerda"),
    ("superior-direita", "Topo, a direita"),
    ("centro", "Centro da tela"),
]


class Overlay(QtWidgets.QWidget):
    def __init__(self, cfg):
        super().__init__(None)
        self.cfg = cfg
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
            | QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setFixedWidth(int(cfg.get("overlay_width", 760)))

        self.indicador = _Indicador(self)
        self.rotulo = QtWidgets.QLabel("Ouvindo...", self)
        self.rotulo.setWordWrap(True)
        self.rotulo.setTextFormat(QtCore.Qt.PlainText)
        self.rotulo.setStyleSheet(
            "color:#f0f0f4; font-family:'Segoe UI',sans-serif;"
            "font-size:15px; background:transparent;"
        )

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(18, 13, 20, 13)
        lay.setSpacing(14)
        lay.addWidget(self.indicador, 0, QtCore.Qt.AlignVCenter)
        lay.addWidget(self.rotulo, 1)

        self._preaquecido = False
        self._pulso = QtCore.QTimer(self)
        self._pulso.timeout.connect(self.indicador.tick)
        self._auto_hide = QtCore.QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.timeout.connect(self.esconder)

    # ------------------------------------------------------------------
    def paintEvent(self, _evt) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QtGui.QColor(19, 19, 25, 240))
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 1))
        p.drawRoundedRect(rect, 15, 15)
        p.end()

    def aplicar_config(self) -> None:
        """Reaplica largura e posicao sem precisar reiniciar o app."""
        self.setFixedWidth(int(self.cfg.get("overlay_width", 760)))
        self.adjustSize()
        self._reposicionar()

    def _reposicionar(self) -> None:
        tela = QtGui.QGuiApplication.primaryScreen()
        if tela is None:
            return
        area = tela.availableGeometry()
        margem = int(self.cfg.get("overlay_offset_y", 90))
        lado = 24
        pos = str(self.cfg.get("overlay_posicao", "inferior-centro"))
        vertical, _, horizontal = pos.partition("-")

        if horizontal == "esquerda":
            x = area.x() + lado
        elif horizontal == "direita":
            x = area.x() + area.width() - self.width() - lado
        else:
            x = area.x() + (area.width() - self.width()) // 2

        if vertical == "superior":
            y = area.y() + margem
        elif vertical == "centro":
            y = area.y() + (area.height() - self.height()) // 2
        else:  # inferior (padrao)
            y = area.y() + area.height() - self.height() - margem

        self.move(max(area.x(), x), max(area.y() + 10, y))

    def _ajustar(self) -> None:
        self.layout().activate()
        self.setFixedHeight(max(58, self.sizeHint().height()))
        self._reposicionar()

    def preaquecer(self) -> None:
        """Exibe a janela fora da tela uma vez, ainda no boot.

        A primeira exibicao de uma janela translucida e sempre-no-topo custa
        ~2,5 s: o Qt inicializa a composicao do DWM segurando a GIL, o que
        congela ate a thread do motor. Sem isso, o pedagio cairia no primeiro
        Ctrl+Alt+G e as primeiras palavras do usuario se perderiam.
        """
        if self._preaquecido:
            return
        self._preaquecido = True
        pos = self.pos()
        self.setWindowOpacity(0.0)
        self.move(-20000, -20000)
        self.show()
        self.hide()
        self.move(pos)
        self.setWindowOpacity(1.0)

    # ------------------------------------------------------------------
    def mostrar(self, estado: str = "rec", texto: str = "Ouvindo...") -> None:
        if not self.cfg.get("show_overlay", True):
            return
        self._auto_hide.stop()
        self.set_estado(estado)
        self.set_texto(texto)
        if not self.isVisible():
            self.show()
        self._pulso.start(55)
        self._ajustar()

    def esconder(self) -> None:
        self._pulso.stop()
        self.hide()

    def set_estado(self, estado: str) -> None:
        self.indicador.estado = estado
        self.indicador.update()

    def set_texto(self, texto: str) -> None:
        texto = (texto or "").strip()
        if len(texto) > MAX_CHARS:
            texto = "..." + texto[-MAX_CHARS:]
        self.rotulo.setText(texto or "Ouvindo...")
        self._ajustar()

    def set_nivel(self, valor: float) -> None:
        self.indicador.push_level(valor)

    def flash(self, texto: str, estado: str = "done", ms: int = 1600) -> None:
        if not self.cfg.get("show_overlay", True):
            return
        self.mostrar(estado, texto)
        self._auto_hide.start(ms)
