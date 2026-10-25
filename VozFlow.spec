# -*- mode: python ; coding: utf-8 -*-
"""Receita de empacotamento do VozFlow.

Existe um .spec em vez de uma linha de comando porque o corte de gordura precisa
ser explicito e auditavel. Sem ele o pacote sai com 2306 MB; com ele, ~1000 MB
na versao GPU e ~260 MB na versao CPU.

O que foi cortado e por que (medido, nao chutado - veja o README):

  cuDNN inteiro          1011 MB  o ctranslate2 nao usa cuDNN no caminho do
                                  Whisper. Removido: texto identico, mesma
                                  velocidade (1.01x), continua na GPU.
  NVRTC                   178 MB  compilacao de kernels em tempo de execucao,
                                  que o ctranslate2 nao faz.
  nvblas                    0.3MB substituto de BLAS para CPU, sem uso aqui.
  onnxruntime              39 MB  so serve ao VAD Silero embutido no
                                  faster_whisper, e nos passamos vad_filter=False
                                  sempre (o VAD daqui e o WebRTC).
  opengl32sw.dll           20 MB  OpenGL por software do Qt; a interface e
                                  widgets comuns.

O que NAO da para cortar:

  cublasLt64_12.dll       638 MB  multiplicacao de matrizes da GPU. E o piso da
  cublas64_12.dll          98 MB  versao com GPU: as duas sao obrigatorias.
  av + av.libs             66 MB  o faster_whisper importa `av` no topo de
                                  audio.py; excluir quebra o import.

Uso:
    pyinstaller VozFlow.spec                  -> com GPU
    set VOZFLOW_CPU=1 && pyinstaller VozFlow.spec   -> so CPU
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SO_CPU = bool(os.environ.get("VOZFLOW_CPU"))
RAIZ = Path(os.getcwd())

datas, binaries, hiddenimports = [], [], []
for pacote in ("faster_whisper", "ctranslate2", "tokenizers", "sounddevice", "av",
               "sherpa_onnx"):   # traz o proprio onnxruntime.dll (so a minha voz)
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += ["keyboard", "pyperclip", "webrtcvad", "_webrtcvad"]

# --- CUDA: so o cuBLAS, e so na versao GPU -----------------------------------
CUBLAS = ["cublas64_12.dll", "cublasLt64_12.dll"]
if not SO_CPU:
    origem = RAIZ / ".venv" / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"
    for nome in CUBLAS:
        dll = origem / nome
        if dll.exists():
            binaries.append((str(dll), "nvidia/cublas/bin"))
        else:
            raise SystemExit(
                "Nao encontrei " + str(dll) + "\n"
                "Rode: .venv\\Scripts\\pip install -r requirements-gpu.txt\n"
                "ou empacote a versao CPU com  set VOZFLOW_CPU=1"
            )

# --- filtro: nada de cuDNN, NVRTC nem OpenGL por software --------------------
LIXO = ("cudnn", "nvrtc", "nvblas", "opengl32sw")


def sem_lixo(itens):
    limpos, cortado = [], 0.0
    for item in itens:
        destino = str(item[0]).lower().replace("\\", "/")
        if any(x in destino for x in LIXO):
            try:
                cortado += Path(item[1]).stat().st_size / 1024 / 1024
            except OSError:
                pass
            continue
        limpos.append(item)
    return limpos, cortado


a = Analysis(
    ["main.py"],
    pathex=[str(RAIZ)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["hooks"],
    excludes=[
        "onnxruntime",   # so o VAD Silero usa, e nao usamos
        "tkinter", "matplotlib", "PIL", "scipy", "pandas",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtOpenGL",
    ],
    noarchive=False,
)

a.binaries, corte_bin = sem_lixo(a.binaries)
a.datas, corte_dat = sem_lixo(a.datas)
print("[VozFlow] modo: " + ("CPU" if SO_CPU else "GPU"))
print("[VozFlow] gordura removida do pacote: %.0f MB" % (corte_bin + corte_dat))

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="VozFlow",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="vozflow.ico",
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="VozFlow",
)
