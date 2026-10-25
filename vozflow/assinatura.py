"""Assinatura Ed25519 das versoes publicadas (RFC 8032).

O SHA-256 publicado ao lado do instalador so prova que o arquivo chegou
inteiro: quem conseguisse subir um instalador na Release (conta ou token do
GitHub vazado) subiria junto o hash que bate com ele, e todo VozFlow o
instalaria sozinho. A assinatura e feita com uma chave que fica so no PC de
quem publica, fora do GitHub; o app tem a chave publica embutida e recusa o
que ela nao confirmar.

Implementacao de referencia da RFC 8032, secao 6 - em Python puro, para nao
acrescentar dependencia ao executavel. Lenta (dezenas de ms), mas roda uma
vez por atualizacao. Conferida com os vetores de teste da RFC.
"""

from __future__ import annotations

import hashlib

p = 2 ** 255 - 19
q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, p - 2, p)


d = -121665 * _inv(121666) % p
_raiz_m1 = pow(2, (p - 1) // 4, p)


def _sha512(s: bytes) -> bytes:
    return hashlib.sha512(s).digest()


def _sha512_modq(s: bytes) -> int:
    return int.from_bytes(_sha512(s), "little") % q


def _soma(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % p, (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C, D = 2 * P[3] * Q[3] * d % p, 2 * P[2] * Q[2] % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F, G * H, F * G, E * H)


def _mult(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _soma(Q, P)
        P = _soma(P, P)
        s >>= 1
    return Q


def _iguais(P, Q) -> bool:
    if (P[0] * Q[2] - Q[0] * P[2]) % p != 0:
        return False
    return (P[1] * Q[2] - Q[1] * P[2]) % p == 0


def _recuperar_x(y: int, sinal: int):
    if y >= p:
        return None
    x2 = (y * y - 1) * _inv(d * y * y + 1) % p     # reduzido: recusa x = p
    if x2 == 0:
        return None if sinal else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p != 0:
        x = x * _raiz_m1 % p
    if (x * x - x2) % p != 0:
        return None
    if (x & 1) != sinal:
        x = p - x
    return x


_g_y = 4 * _inv(5) % p
_g_x = _recuperar_x(_g_y, 0)
_G = (_g_x, _g_y, 1, _g_x * _g_y % p)


def _comprimir(P) -> bytes:
    zinv = _inv(P[2])
    x, y = P[0] * zinv % p, P[1] * zinv % p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _descomprimir(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sinal = y >> 255
    y &= (1 << 255) - 1
    x = _recuperar_x(y, sinal)
    return None if x is None else (x, y, 1, x * y % p)


def _expandir(secreta: bytes):
    if len(secreta) != 32:
        raise ValueError("a chave privada tem 32 bytes")
    h = _sha512(secreta)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def chave_publica(secreta: bytes) -> bytes:
    a, _ = _expandir(secreta)
    return _comprimir(_mult(a, _G))


def assinar(secreta: bytes, msg: bytes) -> bytes:
    a, prefixo = _expandir(secreta)
    A = _comprimir(_mult(a, _G))
    r = _sha512_modq(prefixo + msg)
    Rs = _comprimir(_mult(r, _G))
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % q
    return Rs + int.to_bytes(s, 32, "little")


def conferir(publica: bytes, msg: bytes, assinatura: bytes) -> bool:
    if len(publica) != 32 or len(assinatura) != 64:
        return False
    A = _descomprimir(publica)
    if not A or _iguais(_mult(8, A), (0, 1, 1, 0)):    # chave de ordem pequena
        return False
    Rs = assinatura[:32]
    R = _descomprimir(Rs)
    if not R:
        return False
    s = int.from_bytes(assinatura[32:], "little")
    if s >= q:
        return False
    h = _sha512_modq(Rs + publica + msg)
    return _iguais(_mult(s, _G), _soma(R, _mult(h, A)))


def mensagem(nome_arquivo: str, sha256_hex: str) -> bytes:
    """O que e assinado: o nome do instalador (com a versao) e o hash dele."""
    return f"{nome_arquivo}\n{sha256_hex.lower()}\n".encode("ascii")
