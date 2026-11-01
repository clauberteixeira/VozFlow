"""Gera docs/vozflow-demo.svg, a ilustracao animada (SMIL) do README.

Uso: python ferramentas/gerar_demo_svg.py <saida.svg> [estatico]
  estatico: tudo ja escrito, sem animacao - para conferir o layout num PNG.
"""
import math
import random
import sys

saida = sys.argv[1]
estatico = len(sys.argv) > 2

W, H = 860, 360
T_INI = 0.45                    # o texto comeca logo: espera longa parece lentidao
PASSO = 0.030                   # segundos por letra, em media
PAUSA = {" ": 0.012, ",": 0.09, "!": 0.14, ":": 0.16}   # respiro na pontuacao
LEITURA = 2.6                   # texto pronto na tela antes de recomecar

linhas = [
    "Bom dia, pessoal! Segue o resumo da reunião de hoje:",
    "o lançamento fica para sexta e o orçamento já foi aprovado.",
]
FONTE = 21
X0, Y0, DY = 64, 150, 38

# Largura de cada caractere na Segoe UI (por 1000 de em), medida no navegador.
# Cada letra vai numa posicao fixa: assim o recorte para na fronteira da letra
# e o cursor fica colado no texto, em vez de andar em passos de largura media.
LARGURA = {
    " ": 274, "!": 284, ",": 217, ".": 217, ":": 217, "B": 573, "S": 531, "a": 509,
    "c": 462, "d": 589, "e": 523, "f": 313, "g": 589, "h": 566, "i": 242, "j": 242,
    "l": 242, "m": 861, "n": 566, "o": 586, "p": 588, "r": 348, "s": 424, "t": 339,
    "u": 566, "v": 479, "x": 459, "á": 509, "ã": 509, "ç": 462,
}

random.seed(11)
# posicao x depois de cada caractere, e o instante em que ele aparece
posicoes = []
tempos = []
t = T_INI
for linha in linhas:
    x = 0.0
    xs, ts = [], []
    ritmo = 1.0
    for ch in linha:
        if ch == " ":                   # cada palavra tem o seu ritmo, como uma pessoa
            ritmo = random.uniform(0.85, 1.15)
        t += PASSO * ritmo * random.uniform(0.7, 1.3)
        x += LARGURA[ch] * FONTE / 1000
        xs.append(x)
        ts.append(t)
        t += PAUSA.get(ch, 0.0)
    posicoes.append(xs)
    tempos.append(ts)

T_FIM = tempos[-1][-1]
T_PRONTO = T_FIM + 0.25
DUR = T_PRONTO + LEITURA + 0.8
T_SAI, T_LIMPA = DUR - 0.8, DUR - 0.3   # o texto some suave antes de recomecar


def frac(t):
    return f"{t / DUR:.5f}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def ciclo(atributo, chaves, valores, modo=""):
    """Animacao que acompanha o loop inteiro."""
    return (f'<animate attributeName="{atributo}" dur="{DUR:.3f}s" repeatCount="indefinite"{modo} '
            f'values="{";".join(valores)}" keyTimes="{";".join(chaves)}"/>')


DISCRETO = ' calcMode="discrete"'

partes = []
partes.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
              f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">')
partes.append("""<defs>
  <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#1f2937"/><stop offset="1" stop-color="#0f172a"/>
  </linearGradient>
  <filter id="sombra" x="-20%" y="-20%" width="140%" height="160%">
    <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity=".45"/>
  </filter>
</defs>""")
partes.append(f'<rect width="{W}" height="{H}" rx="18" fill="url(#g)"/>')
# janela do "aplicativo" onde o texto entra
partes.append('<rect x="32" y="40" width="796" height="196" rx="12" fill="#f8fafc" filter="url(#sombra)"/>')
partes.append('<rect x="32" y="40" width="796" height="40" rx="12" fill="#e2e8f0"/>')
partes.append('<rect x="32" y="66" width="796" height="14" fill="#e2e8f0"/>')
for i, cor in enumerate(("#ef4444", "#f59e0b", "#22c55e")):
    partes.append(f'<circle cx="{58 + i * 20}" cy="60" r="6" fill="{cor}"/>')
partes.append('<text x="430" y="65" text-anchor="middle" font-size="14" fill="#475569">'
              'Nova mensagem</text>')
partes.append('<text x="64" y="112" font-size="14" fill="#94a3b8">Para: equipe</text>')

# texto e cursor saem juntos no fim do loop
if estatico:
    partes.append("<g>")
else:
    partes.append("<g>" + ciclo("opacity", ["0", frac(T_SAI), frac(T_LIMPA), "1"], ["1", "1", "0", "0"]))

# texto, revelado por recortes (um por linha) que crescem letra a letra
for li, linha in enumerate(linhas):
    y = Y0 + li * DY
    cid = f"c{li}"
    xs = posicoes[li]
    inicios = [X0] + [X0 + x for x in xs[:-1]]
    if estatico:
        partes.append(f'<clipPath id="{cid}"><rect x="{X0}" y="{y - 26}" width="{xs[-1] + 2:.1f}" height="36"/></clipPath>')
    else:
        valores = ["0"] + [f"{x + 1:.1f}" for x in xs] + ["0", "0"]
        chaves = ["0"] + [frac(t) for t in tempos[li]] + [frac(T_LIMPA), "1"]
        partes.append(f'<clipPath id="{cid}"><rect x="{X0}" y="{y - 26}" width="0" height="36">'
                      + ciclo("width", chaves, valores, DISCRETO) + "</rect></clipPath>")
    partes.append(f'<text x="{" ".join(f"{p:.1f}" for p in inicios)}" y="{y}" font-size="{FONTE}" '
                  f'fill="#0f172a" clip-path="url(#{cid})">{esc(linha)}</text>')

# cursor: firme enquanto escreve e piscando so depois, como num editor de texto
if not estatico:
    cx_s, cy_s, ks = [f"{X0}"], [f"{Y0 - 20}"], ["0"]
    for li in range(len(linhas)):
        for x, t in zip(posicoes[li], tempos[li]):
            cx_s.append(f"{X0 + x + 2:.1f}")
            cy_s.append(f"{Y0 + li * DY - 20}")
            ks.append(frac(t))
    cx_s += [f"{X0}", f"{X0}"]
    cy_s += [f"{Y0 - 20}", f"{Y0 - 20}"]
    ks += [frac(T_LIMPA), "1"]

    pisca_v, pisca_k = ["1"], ["0"]
    t = T_FIM + 0.5
    ligado = False
    while t < T_SAI:
        pisca_v.append("1" if ligado else "0")
        pisca_k.append(frac(t))
        ligado = not ligado
        t += 0.5
    pisca_v += ["1", "1"]
    pisca_k += [frac(T_LIMPA), "1"]

    partes.append(
        f'<rect x="{X0}" y="{Y0 - 20}" width="2" height="26" fill="#2563eb">'
        + ciclo("opacity", pisca_k, pisca_v, DISCRETO)
        + ciclo("x", ks, cx_s, DISCRETO)
        + ciclo("y", ks, cy_s, DISCRETO)
        + "</rect>")
partes.append("</g>")

# janelinha flutuante (overlay) embaixo
OX, OY, OW, OHt = 230, 262, 400, 64
partes.append(f'<rect x="{OX}" y="{OY}" width="{OW}" height="{OHt}" rx="32" fill="#111827" '
              f'stroke="#374151" filter="url(#sombra)"/>')
cx, cy = OX + 34, OY + OHt / 2

# as duas situacoes da janelinha se trocam com um fade
troca = ["0", frac(T_PRONTO), frac(T_PRONTO + 0.25), frac(T_SAI), frac(T_LIMPA), "1"]
if estatico:
    partes.append("<g>")
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#ef4444"/>')
else:
    partes.append("<g>" + ciclo("opacity", troca, ["1", "1", "0", "0", "1", "1"]))
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#ef4444">'
                  f'<animate attributeName="opacity" values="1;.35;1" dur="1.2s" repeatCount="indefinite"/></circle>')
partes.append(f'<text x="{cx + 22}" y="{cy - 4}" font-size="15" font-weight="600" fill="#f9fafb">Ouvindo…</text>')
partes.append(f'<text x="{cx + 22}" y="{cy + 15}" font-size="12" fill="#9ca3af">PgDn encerra e envia</text>')

# barrinhas de nivel: uma onda continua, mais alta no meio, em vez de saltos ao acaso
BARRAS, AMOSTRAS, VOLTA = 14, 18, 1.8
for i in range(BARRAS):
    bx = OX + 210 + i * 12
    perfil = 0.4 + 0.6 * math.sin(math.pi * (i + 0.5) / BARRAS)
    alturas = []
    for k in range(AMOSTRAS):
        a = 2 * math.pi * k / AMOSTRAS
        onda = 0.5 + 0.5 * math.sin(a + i * 0.9)
        detalhe = 0.72 + 0.28 * math.sin(2 * a - i * 0.5)
        alturas.append(round(6 + 24 * perfil * onda * detalhe, 1))
    alturas.append(alturas[0])
    if estatico:
        h = alturas[0]
        partes.append(f'<rect x="{bx}" y="{cy - h / 2:.1f}" width="6" height="{h}" rx="3" fill="#60a5fa"/>')
    else:
        hs = ";".join(str(a) for a in alturas)
        ys = ";".join(f"{cy - a / 2:.1f}" for a in alturas)
        partes.append(
            f'<rect x="{bx}" y="{cy - 9}" width="6" height="18" rx="3" fill="#60a5fa">'
            f'<animate attributeName="height" values="{hs}" dur="{VOLTA}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{ys}" dur="{VOLTA}s" repeatCount="indefinite"/></rect>')
partes.append("</g>")

if not estatico:
    partes.append('<g opacity="0">' + ciclo("opacity", troca, ["0", "0", "1", "1", "0", "0"]))
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#22c55e"/>')
    partes.append(f'<path d="M{cx - 4} {cy} l3 3 l5.5 -6" fill="none" stroke="#052e16" '
                  f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    partes.append(f'<text x="{cx + 22}" y="{cy - 4}" font-size="15" font-weight="600" fill="#f9fafb">Pronto</text>')
    partes.append(f'<text x="{cx + 22}" y="{cy + 15}" font-size="12" fill="#9ca3af">Texto escrito no campo</text>')
    partes.append("</g>")

partes.append(f'<text x="{W - 24}" y="{H - 14}" text-anchor="end" font-size="11" fill="#64748b">'
              f'ilustração — 100% offline, na sua GPU</text>')
partes.append("</svg>")
with open(saida, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(partes) + "\n")

todos = [t for ts in tempos for t in ts]
maior = max(b - a for a, b in zip(todos, todos[1:]))
print(f"ok {saida}: escreve em {T_FIM - T_INI:.1f} s, maior pausa {maior:.2f} s, loop {DUR:.1f} s")
