"""VozFlow - ditado por voz com atalhos globais no Windows."""

import os

# Precisa ficar antes de qualquer import do huggingface_hub, que le esta
# variavel uma unica vez, na importacao.
#
# O backend Xet baixa em blocos grandes e so descarrega no cache de vez em
# quando: medindo o download do modelo `small` (464 MB), ele deu 4 degraus de
# progresso em 13,4 s, contra 14 degraus em 11,5 s com o backend classico. Como
# o modelo padrao tem 1,5 GB, sem isso o usuario ficaria olhando "14%" parado
# por minutos. E o classico ainda saiu mais rapido.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

__version__ = "1.2.4"
APP_NAME = "VozFlow"
