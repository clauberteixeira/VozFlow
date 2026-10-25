"""Calibra o limiar que separa a sua voz no microfone do resto da sala.

Nao da para adivinhar esse numero: depende do microfone, do ganho do Windows e
de quao perto voce fala. Aqui ele e medido - primeiro o ambiente, depois a sua
voz - e o limiar fica entre os dois.
"""

from __future__ import annotations

import time

import numpy as np

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
