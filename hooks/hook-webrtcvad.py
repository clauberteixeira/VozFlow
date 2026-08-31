"""Substitui o hook oficial do PyInstaller para o webrtcvad.

O modulo `webrtcvad` aqui vem da distribuicao `webrtcvad-wheels` (a original
nao tem wheel para Python 3.12). O hook que acompanha o PyInstaller faz
copy_metadata('webrtcvad') e aborta o build inteiro com PackageNotFoundError,
porque o nome da distribuicao instalada e outro.

A extensao `_webrtcvad` o PyInstaller recolhe sozinho; nada mais e necessario.
"""

hiddenimports = ["_webrtcvad"]
