# Ferramentas

Scripts de quem desenvolve e publica o VozFlow. Nenhum deles faz parte do app
instalado.

| Arquivo | Para quê |
|---|---|
| `assinar.py` | Assina o instalador de cada versão (`.sig`) — sem isso a atualização automática não aceita a versão. Ver [docs/EMPACOTAMENTO.md](../docs/EMPACOTAMENTO.md). |
| `medir_fluidez.py` | Mede a escrita ao vivo com o motor real: um WAV entra em tempo real por um microfone falso e um teclado falso anota cada letra. Dá a 1ª palavra, o atraso típico e as palavras erradas — os números de [docs/DESEMPENHO.md](../docs/DESEMPENHO.md). Também serve para conferir que só ruído não digita nada. |
| `teste_instalador/` | Confere de verdade, com o Inno Setup, o código de atualização do `instalador.iss`: espera o app fechar, reabre, desiste se ele não fechar e reabre a versão antiga se falhar. Usa um instalador descartável; não mexe no VozFlow instalado. |
| `gerar_demo_svg.py` | Gera a animação do README (`docs/vozflow-demo.svg`). `python ferramentas\gerar_demo_svg.py docs\vozflow-demo.svg` |

Os testes automáticos ficam em `tests/` e nunca usam microfone, teclado,
área de transferência nem internet de verdade. Estas ferramentas são o
complemento: medem o que só dá para medir com o modelo e o instalador reais.
