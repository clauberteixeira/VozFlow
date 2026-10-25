"""Reconhecer so a sua voz: ignora quem conversa ao fundo enquanto voce dita.

Na calibracao, ~20 s da sua fala viram uma "impressao da voz" (256 numeros)
guardada so neste PC. Durante a ditada, o audio do trecho aberto e conferido
em janelas de 1 s: as que tem voz de OUTRA pessoa e chegam mais baixas que a
sua sao silenciadas antes do Whisper.

Medido (reports/estudo-so-minha-voz do Harness): com a pessoa de fundo falando
nas suas pausas, a frase dela sumia do texto e as suas ficavam intactas. A
regra exige as duas coisas - voz alheia E volume abaixo do seu - porque, com
voces dois falando JUNTOS, a nota cai na mesma faixa de "so a outra pessoa";
o que separa os casos e o volume (voce esta colado no microfone). Na duvida
nao corta: apagar palavra sua e pior que deixar passar o fundo.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import numpy as np

from . import config

SR = 16000
JANELA = SR            # 1 s: o minimo em que o modelo ja separa bem as vozes
PASSO = SR // 2        # 0,5 s entre janelas: ~90 ms de CPU por segundo de fala
LIMIAR = 0.58          # abaixo disto a voz e de outra pessoa (sua: ~0,75-0,97)
FATOR_NIVEL = 0.85     # e so corta se chegar abaixo de 85% do seu volume
MIN_JANELAS = 2        # ~1,5 s seguidos: uma janela solta pode ser engano
RMS_SILENCIO = 0.003   # silencio nao entra na conta

ARQUIVO_IMPRESSAO = "minha_voz.json"

# Modelo WeSpeaker ResNet34 (VoxCeleb, licenca CC BY 4.0), 26,5 MB. Revisao
# fixa e hash conferido: um arquivo trocado no repositorio nao entra no app.
MODELO_REPO = "csukuangfj/speaker-embedding-models"
MODELO_ARQUIVO = "wespeaker_en_voxceleb_resnet34.onnx"
MODELO_REVISAO = "0743f301363dec56491a490f6d6cbc9d67f9a3bf"
MODELO_SHA256 = "5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94"
MODELO_MB = 26.5


TEXTO_CADASTRO = (
    "Vou ler este texto para o VozFlow aprender a minha voz. Hoje eu preciso organizar "
    "a agenda da semana, responder os e-mails que ficaram pendentes e revisar o orcamento "
    "do projeto. Amanha cedo tenho uma reuniao com a equipe e, a tarde, quero ligar para "
    "o cliente para confirmar os prazos. Depois do almoco vou ao mercado comprar cafe, "
    "pao, leite e frutas para a semana."
)


class ModeloInvalido(Exception):
    """O arquivo baixado nao e o modelo esperado (hash diferente)."""


@dataclass
class Impressao:
    vetor: np.ndarray      # normalizado
    nivel: float           # RMS tipico da sua fala, no seu microfone


# ----------------------------------------------------------------------
# regra de corte (pura, sem modelo)
# ----------------------------------------------------------------------
def trechos_alheios(janelas, nivel_voce: float, limiar: float = LIMIAR,
                    fator_nivel: float = FATOR_NIVEL,
                    min_janelas: int = MIN_JANELAS) -> list[tuple[int, int]]:
    """Intervalos (inicio, fim) em amostras a silenciar.

    `janelas`: (inicio, nota, rms) de janelas consecutivas de `JANELA`
    amostras, espacadas de `PASSO`. So entra numa corrida a janela com voz
    alheia (nota < limiar) E volume abaixo do seu; so corta corrida com pelo
    menos `min_janelas` janelas seguidas.
    """
    cortes: list[tuple[int, int]] = []
    corrida: list[int] = []

    def fechar():
        if len(corrida) >= min_janelas:
            cortes.append((corrida[0], corrida[-1] + JANELA))

    teto = fator_nivel * nivel_voce
    for inicio, nota, rms in janelas:
        alheia = nota < limiar and rms < teto
        if alheia and (not corrida or inicio - corrida[-1] == PASSO):
            corrida.append(inicio)
            continue
        fechar()
        corrida = [inicio] if alheia else []
    fechar()
    return cortes


def aplicar(audio: np.ndarray, cortes) -> np.ndarray:
    """Copia do audio com os trechos silenciados (o original fica intacto)."""
    if not cortes:
        return audio
    saida = audio.copy()
    for ini, fim in cortes:
        saida[ini:fim] = 0.0
    return saida


def nivel_da_fala(audio: np.ndarray) -> float:
    """RMS tipico da fala (mediana dos blocos de 100 ms que nao sao silencio)."""
    bloco = SR // 10
    niveis = [float(np.sqrt(np.mean(np.square(audio[i:i + bloco]))))
              for i in range(0, len(audio) - bloco + 1, bloco)]
    fala = [n for n in niveis if n > max(RMS_SILENCIO, 0.2 * max(niveis, default=0))]
    return float(np.median(fala)) if fala else 0.0


# ----------------------------------------------------------------------
# impressao da voz: so neste PC
# ----------------------------------------------------------------------
def _caminho():
    return config.CONFIG_DIR / ARQUIVO_IMPRESSAO


def salvar_impressao(vetor, nivel: float) -> None:
    v = np.asarray(vetor, dtype=np.float32)
    v = v / (np.linalg.norm(v) or 1.0)
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _caminho().with_name(ARQUIVO_IMPRESSAO + ".tmp")
    tmp.write_text(json.dumps({"versao": 1, "modelo": MODELO_ARQUIVO, "nivel": float(nivel),
                               "vetor": [round(float(x), 6) for x in v]}), encoding="utf-8")
    os.replace(tmp, _caminho())


def carregar_impressao() -> Impressao | None:
    try:
        d = json.loads(_caminho().read_text(encoding="utf-8"))
        v = np.asarray(d["vetor"], dtype=np.float32)
        nivel = float(d["nivel"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if v.size == 0 or not np.isfinite(v).all() or not np.isfinite(nivel):
        return None
    return Impressao(v / (np.linalg.norm(v) or 1.0), nivel)


def esquecer() -> None:
    """Apaga a impressao da voz (dado biometrico)."""
    try:
        _caminho().unlink(missing_ok=True)
    except OSError:
        pass


# ----------------------------------------------------------------------
# modelo
# ----------------------------------------------------------------------
def _hf_hub_download(**kw):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(**kw)


def _sha256(caminho) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def garantir_modelo() -> str:
    """Caminho local do modelo de voz, baixando uma vez (revisao fixa + hash)."""
    caminho = _hf_hub_download(repo_id=MODELO_REPO, filename=MODELO_ARQUIVO,
                               revision=MODELO_REVISAO)
    if _sha256(caminho) != MODELO_SHA256:
        raise ModeloInvalido("o modelo de voz baixado nao confere (hash diferente)")
    return caminho


def modelo_ja_baixado() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        c = try_to_load_from_cache(MODELO_REPO, MODELO_ARQUIVO, revision=MODELO_REVISAO)
        return isinstance(c, str) and os.path.isfile(c)
    except Exception:  # noqa: BLE001
        return False


def gravar(dispositivo, segundos: float) -> np.ndarray:
    """Grava `segundos` do microfone escolhido (o mesmo que a ditada usa)."""
    import time

    import sounddevice as sd

    from .audio import resolver_dispositivo

    blocos: list[np.ndarray] = []
    with sd.InputStream(samplerate=SR, blocksize=SR // 10, channels=1, dtype="float32",
                        device=resolver_dispositivo(dispositivo),
                        callback=lambda i, f, t, st: blocos.append(i[:, 0].copy())):
        time.sleep(segundos)
    return np.concatenate(blocos) if blocos else np.zeros(1, np.float32)


class Verificador:
    """Extrai a impressao de um audio e compara com a sua (sherpa-onnx, CPU)."""

    def __init__(self, caminho_modelo: str):
        import sherpa_onnx

        cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=caminho_modelo, num_threads=1)
        self._ext = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
        self.referencia: np.ndarray | None = None

    def impressao(self, audio: np.ndarray) -> np.ndarray:
        s = self._ext.create_stream()
        s.accept_waveform(SR, np.ascontiguousarray(audio, dtype=np.float32))
        s.input_finished()
        v = np.asarray(self._ext.compute(s), dtype=np.float32)
        return v / (np.linalg.norm(v) or 1.0)

    def nota(self, trecho: np.ndarray) -> float:
        return float(np.dot(self.referencia, self.impressao(trecho)))
