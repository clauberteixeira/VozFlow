"""Rede de seguranca contra as duas falhas classicas do Whisper.

1. Loop de repeticao: o decoder trava e repete a mesma palavra ou frase
   centenas de vezes ("19, 19, 19, ...").
2. Eco do prompt: com audio curto ou baixo, ele transcreve o proprio
   `initial_prompt` como se fosse fala.

Ambas ja acontecem menos com os parametros de decodificacao certos, mas nao
somem: aqui e a ultima linha de defesa antes do texto ser colado.
"""

from __future__ import annotations

import re
import unicodedata

PONTUACAO = ".,;:!?()[]\"'"


def _chave(palavra: str) -> str:
    """Forma comparavel: sem acento, sem pontuacao, minuscula."""
    p = unicodedata.normalize("NFKD", palavra.lower())
    p = "".join(c for c in p if not unicodedata.combining(c))
    return p.strip(PONTUACAO)


def colapsar_repeticoes(texto: str, limite: int = 2, max_n: int = 6) -> str:
    """Limita qualquer n-grama a `limite` repeticoes seguidas.

    Preserva repeticoes naturais da fala ("nao, nao", "muito muito bom") e
    corta o loop patologico.
    """
    palavras = texto.split()
    if len(palavras) < 3:
        return texto

    saida: list[str] = []
    for palavra in palavras:
        saida.append(palavra)
        for n in range(1, max_n + 1):
            if len(saida) < n * (limite + 1):
                continue
            blocos = [
                tuple(_chave(w) for w in saida[len(saida) - (k + 1) * n: len(saida) - k * n])
                for k in range(limite + 1)
            ]
            if all(b == blocos[0] for b in blocos) and any(blocos[0]):
                del saida[len(saida) - n:]
                break
    return " ".join(saida)


def remover_eco_do_prompt(texto: str, prompt: str, min_palavras: int = 3) -> str:
    """Remove frases que sao pedaco literal do initial_prompt.

    So descarta trechos com pelo menos `min_palavras` palavras, para nao comer
    uma fala legitima curta que por acaso esteja no vocabulario.
    """
    if not prompt or not texto:
        return texto
    alvo = " ".join(_chave(p) for p in prompt.split())
    if not alvo:
        return texto

    frases = re.split(r"(?<=[.!?])\s+", texto)
    mantidas = []
    for frase in frases:
        palavras = [_chave(p) for p in frase.split() if _chave(p)]
        seq = " ".join(palavras)
        if len(palavras) >= min_palavras and seq and seq in alvo:
            continue  # e o prompt vazando, nao fala do usuario
        mantidas.append(frase)
    return " ".join(m for m in mantidas if m).strip()


def limpar(texto: str, prompt: str = "") -> str:
    """Passa o texto pelas duas redes de seguranca."""
    if not texto:
        return texto
    limpo = remover_eco_do_prompt(texto, prompt)
    limpo = colapsar_repeticoes(limpo)
    return re.sub(r"\s+", " ", limpo).strip()
