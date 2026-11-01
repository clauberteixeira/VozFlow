"""Historico de versoes lido do CHANGELOG.md, para a aba Versoes.

O CHANGELOG vai dentro do executavel (VozFlow.spec) em vez de ser baixado: assim
o historico aparece sem internet e sempre descreve a versao que esta instalada.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

from .atualizador import REPO

URL_ARQUIVOS = f"https://github.com/{REPO}/blob/main/"

_TITULO = re.compile(r"^## \[(\d+\.\d+\.\d+)\] — (\d{4})-(\d{2})-(\d{2})\s*$", re.MULTILINE)
_SEPARADOR = re.compile(r"^---\s*$", re.MULTILINE)


class Versao(NamedTuple):
    numero: str
    data: str        # dd/mm/aaaa
    mudancas: str    # markdown


def caminho_changelog() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "") or Path(sys.executable).parent)
        return base / "CHANGELOG.md"
    return Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def ler_versoes(caminho: Path | None = None) -> list[Versao]:
    """Da mais nova para a mais antiga, na ordem do arquivo. Vazia se nao der
    para ler: o historico nunca impede as Configuracoes de abrir."""
    try:
        texto = Path(caminho or caminho_changelog()).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    achados = list(_TITULO.finditer(texto))
    versoes = []
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(texto)
        corpo = _SEPARADOR.split(texto[m.end():fim], maxsplit=1)[0].strip()
        ano, mes, dia = m.group(2, 3, 4)
        versoes.append(Versao(m.group(1), f"{dia}/{mes}/{ano}", corpo))
    return versoes


def como_markdown(versoes: list[Versao]) -> str:
    return "\n\n".join(f"## {v.numero} — {v.data}\n\n{v.mudancas}" for v in versoes)
