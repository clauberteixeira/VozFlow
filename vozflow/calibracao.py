"""Calibra o limiar que separa a sua voz no microfone do resto da sala.

Nao da para adivinhar esse numero: depende do microfone, do ganho do Windows e
de quao perto voce fala. Aqui ele e medido - primeiro o ambiente, depois a sua
voz - e o limiar fica entre os dois.
"""

from __future__ import annotations

import threading
import time

import numpy as np
from PySide6 import QtCore, QtWidgets

from .audio import BLOCK, SAMPLE_RATE, resolver_dispositivo

SEGUNDOS = 4.0


def _medir(device, segundos: float = SEGUNDOS) -> np.ndarray:
    """Grava e devolve o nivel RMS de cada bloco de 100 ms."""
    import sounddevice as sd

    blocos: list[np.ndarray] = []
    with sd.InputStream(
        samplerate=SAMPLE_RATE, blocksize=BLOCK, channels=1, dtype="float32",
        device=resolver_dispositivo(device),
        callback=lambda i, f, t, s: blocos.append(i[:, 0].copy()),
    ):
        time.sleep(segundos)
    if not blocos:
        return np.zeros(1, dtype=np.float32)
    return np.array([float(np.sqrt(np.mean(np.square(b)))) for b in blocos])


def calcular_limiar(fundo: np.ndarray, voz: np.ndarray) -> tuple[float, str]:
    """Devolve (limiar, aviso). Limiar fica na media geometrica entre os dois."""
    nivel_fundo = float(np.percentile(fundo, 95))
    # so os blocos em que a pessoa realmente falou entram na conta da voz
    ativos = voz[voz > max(nivel_fundo * 2, 1e-5)]
    if ativos.size < 5:
        return 0.0, ("Nao ouvi voz suficiente. Fale mais perto do microfone, "
                     "ou aumente o volume da entrada no Windows.")
    nivel_voz = float(np.median(ativos))

    if nivel_voz < nivel_fundo * 4:
        return 0.0, ("Sua voz ficou perto demais do nivel do ambiente para eu "
                     "separar com seguranca. Tente um microfone mais perto da "
                     "boca, ou use a entrada 'NVIDIA Broadcast'.")

    limiar = float(np.sqrt(nivel_fundo * nivel_voz))
    # nunca colado demais em nenhum dos dois lados
    limiar = max(limiar, nivel_fundo * 3.0)
    limiar = min(limiar, nivel_voz * 0.45)
    return limiar, ""


class DialogoCalibracao(QtWidgets.QDialog):
    medido = QtCore.Signal(object, object)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("VozFlow - calibrar microfone")
        self.setMinimumWidth(520)
        self._rodando = False

        self.titulo = QtWidgets.QLabel("Vamos medir a diferenca entre a sua voz e a sala.")
        self.titulo.setStyleSheet("font-size:14px;")
        self.passo = QtWidgets.QLabel(
            "Passo 1 de 2 - deixe o ambiente como fica normalmente (TV, "
            "conversa ao fundo, ventilador) e NAO fale.\n\n"
            "Passo 2 de 2 - fale normalmente, como vai ditar."
        )
        self.passo.setWordWrap(True)
        self.barra = QtWidgets.QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        self.resultado = QtWidgets.QLabel("")
        self.resultado.setWordWrap(True)

        self.btn = QtWidgets.QPushButton("Comecar")
        self.btn.clicked.connect(self._comecar)
        self.btn_fechar = QtWidgets.QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.reject)

        linha = QtWidgets.QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(self.btn)
        linha.addWidget(self.btn_fechar)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        lay.addWidget(self.titulo)
        lay.addWidget(self.passo)
        lay.addWidget(self.barra)
        lay.addWidget(self.resultado)
        lay.addLayout(linha)

        self.medido.connect(self._aplicar)

    # ------------------------------------------------------------------
    def _comecar(self) -> None:
        if self._rodando:
            return
        self._rodando = True
        self.btn.setEnabled(False)
        self.resultado.setText("")
        threading.Thread(target=self._rodar, daemon=True).start()

    def _fase(self, texto: str, pct: int) -> None:
        QtCore.QMetaObject.invokeMethod(
            self, "_ui", QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, texto), QtCore.Q_ARG(int, pct),
        )

    @QtCore.Slot(str, int)
    def _ui(self, texto: str, pct: int) -> None:
        self.titulo.setText(texto)
        self.barra.setValue(pct)

    def _rodar(self) -> None:
        dev = self.cfg.get("input_device")
        try:
            self._fase("Medindo o ambiente... NAO fale.", 10)
            fundo = _medir(dev)
            self._fase("Agora FALE normalmente, ate a barra encher.", 55)
            voz = _medir(dev)
            self._fase("Calculando...", 95)
        except Exception as exc:  # noqa: BLE001
            self.medido.emit(None, str(exc))
            return
        self.medido.emit((fundo, voz), None)

    def _aplicar(self, dados, erro) -> None:
        self._rodando = False
        self.btn.setEnabled(True)
        self.btn.setText("Refazer")
        self.barra.setValue(100)

        if erro or dados is None:
            self.titulo.setText("Nao consegui gravar.")
            self.resultado.setStyleSheet("color:#c0392b;")
            self.resultado.setText(str(erro))
            return

        fundo, voz = dados
        limiar, aviso = calcular_limiar(fundo, voz)
        nf = float(np.percentile(fundo, 95))
        nv = float(np.median(voz[voz > max(nf * 2, 1e-5)])) if voz.size else 0.0

        if aviso:
            self.titulo.setText("Calibracao nao concluida.")
            self.resultado.setStyleSheet("color:#c87f0a;")
            self.resultado.setText(
                aviso + f"\n\n(ambiente {nf:.5f} / voz {nv:.5f})"
            )
            return

        self.cfg["nivel_fala"] = round(limiar, 6)
        self.cfg.save()
        margem = nv / limiar if limiar else 0
        self.titulo.setText("Calibrado.")
        self.resultado.setStyleSheet("color:#2d8a4e;")
        self.resultado.setText(
            f"Ambiente: {nf:.5f}   Sua voz: {nv:.5f}\n"
            f"Limiar gravado: {limiar:.5f}\n\n"
            f"Sua voz fica {margem:.0f}x acima do corte, e o ambiente "
            f"{limiar / nf:.0f}x abaixo. Som mais fraco que o limiar nao vira texto."
        )
