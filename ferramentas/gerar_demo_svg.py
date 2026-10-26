"""Gera docs/vozflow-demo.svg, a ilustracao animada (SMIL) do README.

Uso: python ferramentas/gerar_demo_svg.py <saida.svg> [estatico]
  estatico: tudo ja escrito, sem animacao - para conferir o layout num PNG.
"""
import sys

saida = sys.argv[1]
estatico = len(sys.argv) > 2

W, H = 860, 360
DUR = 11.0                      # loop inteiro
T_INI, T_FIM = 0.9, 7.2         # escrita acontece entre estes instantes

linhas = [
    "Bom dia, pessoal! Segue o resumo da reunião de hoje:",
    "o lançamento fica para sexta e o orçamento já foi aprovado.",
]
FONTE = 21
LARG_CHAR = 11.6                # largura forcada por caractere (textLength)
X0, Y0, DY = 64, 150, 38

total = sum(len(l) for l in linhas)
# instante em que cada caractere aparece, em "rajadas" de palavra, como o app
tempos = []
k = 0
for li, linha in enumerate(linhas):
    for ci, ch in enumerate(linha):
        tempos.append((li, ci))
        k += 1


def frac(t):
    return f"{t / DUR:.4f}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


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

# texto, revelado por recortes (um por linha) que crescem caractere a caractere
for li, linha in enumerate(linhas):
    n = len(linha)
    largura = n * LARG_CHAR
    y = Y0 + li * DY
    cid = f"c{li}"
    # indices globais dos caracteres desta linha
    inicio = sum(len(l) for l in linhas[:li])
    if estatico:
        partes.append(f'<clipPath id="{cid}"><rect x="{X0}" y="{y - 26}" width="{largura}" height="36"/></clipPath>')
    else:
        # palavras saem em rajadas: o tempo de cada caractere segue a palavra
        valores, chaves = ["0"], ["0"]
        palavras_fim = [i + 1 for i, ch in enumerate(linha) if ch == " "] + [n]
        for fim in palavras_fim:
            g = inicio + fim
            t = T_INI + (T_FIM - T_INI) * g / total
            valores.append(f"{fim * LARG_CHAR:.1f}")
            chaves.append(frac(t))
        valores += [f"{largura:.1f}", "0"]
        chaves += [frac(DUR - 0.6), "1"]
        # discreto: a palavra inteira aparece de uma vez, como no VozFlow
        partes.append(
            f'<clipPath id="{cid}"><rect x="{X0}" y="{y - 26}" width="0" height="36">'
            f'<animate attributeName="width" dur="{DUR}s" repeatCount="indefinite" calcMode="discrete" '
            f'values="{";".join(valores)}" keyTimes="{";".join(chaves)}"/></rect></clipPath>')
    partes.append(f'<text x="{X0}" y="{y}" font-size="{FONTE}" fill="#0f172a" textLength="{largura:.1f}" '
                  f'lengthAdjust="spacingAndGlyphs" clip-path="url(#{cid})">{esc(linha)}</text>')

# cursor piscando, que acompanha o fim do texto
if not estatico:
    xs, ys, ks = [f"{X0}"], [f"{Y0 - 20}"], ["0"]
    for li, linha in enumerate(linhas):
        inicio = sum(len(l) for l in linhas[:li])
        n = len(linha)
        for fim in [i + 1 for i, ch in enumerate(linha) if ch == " "] + [n]:
            t = T_INI + (T_FIM - T_INI) * (inicio + fim) / total
            xs.append(f"{X0 + fim * LARG_CHAR + 2:.1f}")
            ys.append(f"{Y0 + li * DY - 20}")
            ks.append(frac(t))
    xs.append(f"{X0}")
    ys.append(f"{Y0 - 20}")
    ks.append(frac(DUR - 0.6))
    partes.append(
        f'<rect x="{X0}" y="{Y0 - 20}" width="2" height="26" fill="#2563eb">'
        f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>'
        f'<animate attributeName="x" dur="{DUR}s" repeatCount="indefinite" calcMode="discrete" '
        f'values="{";".join(xs)}" keyTimes="{";".join(ks)}"/>'
        f'<animate attributeName="y" dur="{DUR}s" repeatCount="indefinite" calcMode="discrete" '
        f'values="{";".join(ys)}" keyTimes="{";".join(ks)}"/></rect>')

# janelinha flutuante (overlay) embaixo
OX, OY, OW, OHt = 230, 262, 400, 64
partes.append(f'<rect x="{OX}" y="{OY}" width="{OW}" height="{OHt}" rx="32" fill="#111827" '
              f'stroke="#374151" filter="url(#sombra)"/>')
cx, cy = OX + 34, OY + OHt / 2
if estatico:
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#ef4444"/>')
else:
    partes.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#ef4444">'
                  f'<animate attributeName="opacity" values="1;.35;1" dur="1.2s" repeatCount="indefinite"/></circle>')
partes.append(f'<text x="{cx + 22}" y="{cy - 4}" font-size="15" font-weight="600" fill="#f9fafb">Ouvindo…</text>')
partes.append(f'<text x="{cx + 22}" y="{cy + 15}" font-size="12" fill="#9ca3af">PgDn encerra e envia</text>')
# barrinhas de nivel
import random
random.seed(7)
for i in range(14):
    bx = OX + 210 + i * 12
    alturas = [random.randint(6, 30) for _ in range(6)]
    if estatico:
        h = alturas[0]
        partes.append(f'<rect x="{bx}" y="{cy - h / 2:.1f}" width="6" height="{h}" rx="3" fill="#60a5fa"/>')
    else:
        hs = ";".join(str(a) for a in alturas + alturas[:1])
        ys = ";".join(f"{cy - a / 2:.1f}" for a in alturas + alturas[:1])
        d = 1.1 + (i % 4) * 0.17
        partes.append(
            f'<rect x="{bx}" y="{cy - 9}" width="6" height="18" rx="3" fill="#60a5fa">'
            f'<animate attributeName="height" values="{hs}" dur="{d:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{ys}" dur="{d:.2f}s" repeatCount="indefinite"/></rect>')

partes.append(f'<text x="{W - 24}" y="{H - 14}" text-anchor="end" font-size="11" fill="#64748b">'
              f'ilustração — 100% offline, na sua GPU</text>')
partes.append("</svg>")
with open(saida, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(partes) + "\n")
print("ok", saida)
