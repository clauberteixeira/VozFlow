"""Rede de seguranca contra as falhas classicas do Whisper.

1. Loop de repeticao: o decoder trava e repete a mesma palavra ou frase
   centenas de vezes ("19, 19, 19, ...").
2. Eco do prompt: com audio curto ou baixo, ele transcreve o proprio
   `initial_prompt` como se fosse fala.
3. Frase inventada: num trecho sem fala de verdade (chiado, estalo,
   respiracao) ele escreve as frases que mais viu em legendas de video -
   "Obrigado.", "Tchau.", "E ai".

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


# O que o Whisper escreve sozinho em trecho sem fala (medido no modelo real:
# chiado, estalo e respiracao viraram "Obrigado." e "E ai"). Comparado sem
# acento nem pontuacao, e so quando e o trecho INTEIRO.
FRASES_INVENTADAS = {
    "obrigado", "obrigada", "muito obrigado", "muito obrigada", "obrigado a todos",
    "obrigado por assistir", "obrigada por assistir", "obrigado pela atencao",
    "tchau", "tchau tchau", "e ai", "valeu", "ate a proxima", "ate mais", "ate logo",
    "inscreva-se no canal", "se inscreva no canal", "legendas pela comunidade amara.org",
    "legenda adriana zanotto", "sous-titres realises par la communaute d'amara.org",
    "thank you", "thanks for watching", "you",
}
# Proporcao do trecho com timbre de voz, dentro do que o detector aceitou.
# Medido: fala real mediana 0,72-0,75 (um "obrigado" isolado, 0,72; um "sim",
# 0,50); chiado, estalo e respiracao 0,00; ruido grave 0,09-0,26.
PROPORCAO_DE_VOZ = 0.35


def _frase_normalizada(texto: str) -> str:
    return " ".join(_chave(p) for p in texto.split() if _chave(p))


def _so_frases_prontas(texto: str) -> bool:
    """O texto inteiro e feito de frases prontas? ("E E Tchau. Obrigado.")"""
    # ponto so separa frase quando seguido de espaco ou fim: "Amara.org" fica junto
    for frase in re.split(r"[.!?…]+(?:\s+|$)", texto):
        chave = _frase_normalizada(frase)
        # "E E Tchau": o "e" solto se repete na frente - mas "e ai" e uma frase
        while chave not in FRASES_INVENTADAS and chave.startswith("e "):
            chave = chave[2:]
        if chave and chave != "e" and chave not in FRASES_INVENTADAS:
            return False
    return True


def e_invencao(texto: str, voz_s: float, aceito_s: float) -> bool:
    """Frase pronta saindo de um trecho quase sem timbre de voz.

    `voz_s`: segundos com timbre de voz; `aceito_s`: segundos que o detector e
    o portao de volume aceitaram. Decide pela PROPORCAO: um "obrigado" dito de
    verdade e curto, mas e quase todo voz, e passa; o mesmo "Obrigado." em
    cima de uma respiracao vem de um trecho sem timbre nenhum.
    """
    if not texto.strip():
        return False
    proporcao = voz_s / aceito_s if aceito_s > 0 else 0.0
    if proporcao >= PROPORCAO_DE_VOZ:
        return False
    return _so_frases_prontas(texto)


def limpar(texto: str, prompt: str = "") -> str:
    """Passa o texto pelas duas redes de seguranca."""
    if not texto:
        return texto
    limpo = remover_eco_do_prompt(texto, prompt)
    limpo = colapsar_repeticoes(limpo)
    return re.sub(r"\s+", " ", limpo).strip()
