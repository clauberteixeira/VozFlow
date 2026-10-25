"""Download do modelo Whisper com progresso visivel.

O `faster_whisper.download_model` passa `tqdm_class=disabled_tqdm` de proposito:
os 1,5 GB descem sem nenhum sinal de vida. Numa maquina nova isso faz o app
parecer travado por dez minutos ou mais - foi exatamente o que aconteceu com o
primeiro usuario que instalou.

Aqui o download roda numa thread e o progresso e medido pelo tamanho da pasta de
cache, que funciona com qualquer backend do huggingface_hub (inclusive o xet, em
que o gancho de tqdm nao dispara).
"""

from __future__ import annotations

import threading
from pathlib import Path

# Tamanho aproximado de cada modelo em MB, so para mostrar percentual enquanto
# baixa. Se o numero estiver defasado, o progresso vira "MB baixados" sem %.
TAMANHOS_MB = {
    "tiny": 75, "tiny.en": 75,
    "base": 145, "base.en": 145,
    "small": 464, "small.en": 464,
    "medium": 1530, "medium.en": 1530,
    "large-v1": 3090, "large-v2": 3090, "large-v3": 3090, "large": 3090,
    "large-v3-turbo": 1547, "turbo": 1547,
    "distil-large-v3": 1520, "distil-large-v3.5": 1520,
    "distil-large-v2": 1520, "distil-medium.en": 790, "distil-small.en": 340,
}


# "auto": o modelo segue a maquina. Medido no mesmo audio de 17,6 s (docs/
# DESEMPENHO.md): cada previa do large-v3-turbo leva 12-14 s na CPU (int8),
# o que torna a escrita ao vivo inutilizavel; o base leva ~1 s e o small ~3 s.
# Na GPU o large-v3-turbo leva 0,3-0,45 s e segue sendo o padrao.
MODELO_GPU = "large-v3-turbo"
MODELO_CPU = "base"


def resolver_nome(nome: str, device: str) -> str:
    """Nome real do modelo para este dispositivo ("auto" vira GPU ou CPU)."""
    if (nome or "auto") != "auto":
        return nome
    return MODELO_GPU if device == "cuda" else MODELO_CPU


def repo_do_modelo(nome: str) -> str | None:
    try:
        from faster_whisper.utils import _MODELS

        return _MODELS.get(nome)
    except Exception:  # noqa: BLE001
        return None


def _pasta_cache(repo_id: str) -> Path | None:
    try:
        from huggingface_hub.constants import HF_HUB_CACHE

        return Path(HF_HUB_CACHE) / ("models--" + repo_id.replace("/", "--"))
    except Exception:  # noqa: BLE001
        return None


def _mb_em_disco(pasta: Path | None) -> float:
    if not pasta or not pasta.exists():
        return 0.0
    total = 0
    for f in pasta.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            continue
    return total / 1024 / 1024


def ja_baixado(nome: str) -> bool:
    """True se o modelo ja esta no disco e pode carregar sem internet."""
    try:
        from faster_whisper.utils import download_model

        download_model(nome, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def garantir(nome: str, progresso=None) -> str:
    """Devolve o caminho local do modelo, baixando se preciso.

    `progresso(mb_feitos, mb_total, texto)` e chamado ~2x por segundo enquanto
    baixa. `mb_total` vem de uma tabela e pode ser 0 se o modelo for desconhecido.
    """
    from faster_whisper.utils import download_model

    if ja_baixado(nome):
        return download_model(nome, local_files_only=True)

    repo = repo_do_modelo(nome) or nome
    pasta = _pasta_cache(repo)
    total = float(TAMANHOS_MB.get(nome, 0))
    ja_tinha = _mb_em_disco(pasta)  # download interrompido antes, talvez

    resultado: dict = {}
    parar = threading.Event()

    def baixar():
        try:
            resultado["caminho"] = download_model(nome)
        except Exception as exc:  # noqa: BLE001
            resultado["erro"] = exc
        finally:
            parar.set()

    th = threading.Thread(target=baixar, daemon=True)
    th.start()

    if progresso:
        progresso(0.0, total, "Conectando...")
    while not parar.wait(0.5):
        if not progresso:
            continue
        feito = max(0.0, _mb_em_disco(pasta) - ja_tinha)
        if total:
            pct = min(99, int(feito * 100 / total))
            texto = f"Baixando o modelo: {pct}%  ({feito:.0f} de {total:.0f} MB)"
        else:
            texto = f"Baixando o modelo: {feito:.0f} MB"
        progresso(feito, total, texto)

    th.join(timeout=10)
    if "erro" in resultado:
        raise resultado["erro"]
    if progresso:
        progresso(total, total, "Modelo baixado.")
    return resultado["caminho"]


def explicar_falha(exc: Exception) -> str:
    """Transforma o erro cru do download em algo acionavel."""
    texto = str(exc).lower()
    if any(p in texto for p in ("connection", "network", "timeout", "resolve",
                                "getaddrinfo", "ssl", "proxy", "temporarily")):
        return ("Nao consegui baixar o modelo: sem acesso a internet. O VozFlow "
                "precisa baixa-lo uma unica vez. Verifique a conexao (ou o "
                "firewall/proxy) e abra o app de novo.")
    if "space" in texto or "disk" in texto or "errno 28" in texto:
        return "Nao consegui baixar o modelo: espaco em disco insuficiente (precisa de ~2 GB)."
    if "401" in texto or "403" in texto or "gated" in texto:
        return "Nao consegui baixar o modelo: o repositorio recusou o acesso."
    return "Nao consegui baixar o modelo: " + str(exc)[:160]
