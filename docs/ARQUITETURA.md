# Arquitetura

Como o áudio do microfone vira texto dentro do campo em foco, e por que cada
peça está onde está.

---

## O caminho de uma frase

```
microfone ──> Recorder ──> VAD ──> buffer do trecho ──> Whisper ──> limpeza ──> entrega
 16 kHz      blocos de     detecta   fecha no          faster-      anti-       escreve
 mono        100 ms        fala      silêncio          whisper      alucinação  no campo
```

O detalhe que dá a sensação de tempo real está no meio:

> **Enquanto um trecho está aberto, ele é retranscrito inteiro a cada
> `partial_interval` segundos** (0,45 s por padrão), e o resultado vai para a
> janela flutuante como texto provisório. Quando `silence_ms` (700 ms) de
> silêncio fecham o trecho, ele é transcrito uma última vez com mais qualidade
> (`beam_size=5`) e vira texto definitivo, escrito no campo em foco.

Retranscrever o trecho **inteiro**, em vez de só o pedaço novo, é o que faz o
texto sair liso: o Whisper corrige o que ele mesmo escreveu antes conforme o
contexto cresce. O custo é reprocessar áudio já visto, e é por isso que
`max_segment_s` (20 s) fecha o trecho à força — sem esse teto, cada
retranscrição ficaria progressivamente mais cara.

O resultado prático: a latência fica **constante** mesmo num ditado de cinco
minutos, porque o que se retranscreve é sempre um trecho curto, nunca a
gravação toda.

---

## Threads

| Thread | O que faz |
|---|---|
| Thread do Qt | interface, bandeja, janelinha flutuante |
| Thread do motor | captura + Whisper (`QThread` própria) |
| Thread de inserção | escreve o texto em doses de 25 ms |
| Hook global de teclado | atalhos (biblioteca `keyboard`, ganchos de baixo nível) |

A separação não é decorativa: **tocar em widget Qt fora da thread do Qt derruba
o processo** com `STATUS_STACK_BUFFER_OVERRUN` (0xC0000409), sem traceback
nenhum. Por isso a thread de inserção avisa a interface por *sinal*
(`sig_segurando`), nunca mexendo no overlay direto.

---

## O motor de transcrição

| Item | Escolha |
|---|---|
| Modelo | Whisper `large-v3-turbo` (OpenAI) |
| Runtime | `faster-whisper` |
| Backend | CTranslate2 — reimplementação do Whisper em C++, ~4× mais rápida que o original |
| Aceleração | CUDA float16 (referência: RTX 4060, 8 GB) |
| Fallback | cai para CPU/int8 sozinho se não houver GPU |

Parâmetros de decodificação, em `vozflow/transcriber.py`:

| Parâmetro | Valor | Por quê |
|---|---|---|
| `beam_size` | `5` no final, `1` nas prévias | qualidade onde conta, velocidade onde é descartável |
| `temperature` | `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]` | é uma **lista**, não `0.0` fixo — é isso que liga o fallback de temperatura |
| `compression_ratio_threshold` | `2.4` | detecta saída degenerada (loop de repetição) e redecodifica |
| `no_speech_threshold` | `0.6` | descarta trecho sem fala |
| `condition_on_previous_text` | `False` | prender o decoder ao próprio resultado anterior é o que o faz travar repetindo |
| `vad_filter` | `False` | o VAD é feito fora, pelo WebRTC |
| `word_timestamps` | `False` | não são usados aqui, e custam tempo |

---

## Detecção de fala (VAD) e cortes por nível

**VAD principal:** WebRTC VAD (`webrtcvad-wheels`), agressividade 3, frames de
20 ms. **Fallback:** limiar de energia com piso de ruído adaptativo, para o
caso de a biblioteca não estar disponível.

Além do VAD há **dois cortes por nível RMS**, porque o Whisper alucina em
silêncio — ele inventa frases inteiras a partir de ruído:

| corte | padrão | efeito |
|---|---|---|
| `nivel_minimo` | `0.004` | abaixo disso o áudio nem chega ao modelo |
| `nivel_fala` | `0.010` | abaixo disso é som de fundo, não você |

Esses números dependem do microfone e de quão perto a pessoa fala, então a
tela de configurações tem um **"Calibrar com a minha voz"**: mede o ambiente
em silêncio por 4 s, depois a voz por 4 s, e coloca o limiar entre os dois — em
vez de você chutar.

O corte de fala tem **histerese**, para uma sílaba fraca no meio da palavra não
picotar a frase.

---

## A limpeza do texto

`vozflow/texto.py` é a última linha de defesa antes de entregar, contra as duas
falhas clássicas do Whisper:

1. **Loop de repetição** — o decoder trava e repete a mesma palavra centenas de
   vezes. A limpeza colapsa n-gramas repetidos, mantendo repetição natural
   como "não, não".
2. **Eco do prompt** — com áudio curto ou baixo, o modelo transcreve o próprio
   `initial_prompt` como se fosse fala. A limpeza remove trechos que são eco
   literal do prompt.

Somando com o portão de energia e o fallback de temperatura, são **três
camadas** contra alucinação. Detalhes e casos reais em
[Decisões técnicas](DECISOES-TECNICAS.md).

---

## Escrita ao vivo: o prefixo estável

Escrever ao vivo esbarra num problema: o Whisper muda de ideia. "pre..." vira
"preciso", que vira "preciso confirmar". Não dá para escrever cada palpite e
depois apagar.

O algoritmo é o **prefixo estável**:

1. o trecho aberto é retranscrito a cada `partial_interval`;
2. uma palavra que sobreviveu **igual a duas transcrições seguidas** é
   considerada firme e vai para o campo;
3. a **última** palavra firme fica retida, porque ela ainda costuma mudar
   quando chega mais áudio.

Nada é escrito duas vezes e nada precisa ser apagado.

A comparação entre duas transcrições **ignora pontuação e acento**. Sem isso, o
Whisper trocar `"Bom dia!"` por `"Bom dia,"` fazia a palavra "não bater" e
custava uma rodada inteira antes de qualquer texto aparecer — sozinho, esse
detalhe atrasava a primeira palavra em 0,86 s.

---

## A cadência da escrita

O motor entrega palavras em rajadas: 2 ou 3 de uma vez a cada
`partial_interval`, com pausa maior quando a frase fecha. Escrever cada rajada
de uma vez fazia o texto **saltar**, e dava impressão de travamento.

Duas mudanças resolveram:

**Digitar em vez de colar.** Cada trecho ia por área de transferência +
`Ctrl+V` — um salto atômico de várias palavras, além de sujar o clipboard 16
vezes por ditada. A escrita ao vivo usa `keyboard.write`, que digita caractere
a caractere, e os acentos saem perfeitos (`coração, licitação, orçamento, é,
à, já, você`).

**Cadência com crédito fracionário.** As letras vão para um buffer e saem a
cada 25 ms, num ritmo que espalha o buffer ao longo do intervalo em que a
próxima leva costuma chegar. Sem a parte fracionária, poucas letras saíam em
2 ou 3 ticks e o texto parava até a leva seguinte — o "engasgo no meio da
frase".

Os números estão em [Desempenho](DESEMPENHO.md).

---

## A trava de janela

`travar_janela` (ligado por padrão) guarda a janela onde você apertou o atalho.
Se o foco sair dela no meio da fala, o VozFlow **segura o texto** em vez de
deixá-lo vazar para a janela errada. A janelinha flutuante avisa
(*"Texto segurado — volte para ..."*) e você continua acompanhando a
transcrição por ela. Ao encerrar, o app traz a janela original de volta e
entrega tudo de uma vez.

Por que não escrever direto na janela de fundo, já que ela é conhecida: **não
dá.** É uma das descobertas mais surpreendentes do projeto, e está detalhada em
[Decisões técnicas](DECISOES-TECNICAS.md#não-dá-para-escrever-numa-janela-chromium-em-segundo-plano).

Se a janela original não voltar ao foco na hora de entregar (o Windows pode
recusar), o VozFlow **não digita às cegas**: copia o texto e avisa. Com
"apertar Enter" ligado, digitar sem confirmar o foco mandaria a mensagem na
janela errada.

---

## O pré-aquecimento do overlay

A janela flutuante é criada e exibida **escondida** durante a inicialização.

A primeira exibição de uma janela translúcida sempre-no-topo custa ~2,5 s no Qt
— é a inicialização da composição do DWM, segurando a GIL. Sem esse truque,
esse atraso cairia no seu primeiro `Ctrl+Alt+G` e comeria as primeiras
palavras.

---

## Estrutura do código

| Arquivo | Linhas | Papel |
|---|---:|---|
| `main.py` | 69 | Ponto de entrada. Mutex de instância única, checa a bandeja. |
| `vozflow/__init__.py` | 16 | Versão, nome do app e `HF_HUB_DISABLE_XET` (antes de qualquer import do `huggingface_hub`). |
| `vozflow/app.py` | 987 | Bandeja, atalhos globais, orquestração, sons. |
| `vozflow/configuracoes.py` | 555 | Janela única de ajustes, com medidor ao vivo. |
| `vozflow/transcriber.py` | 533 | Motor: thread própria, trechos, prévias, Whisper. |
| `vozflow/audio.py` | 298 | Captura, VAD, resolução do microfone. |
| `vozflow/atalhos.py` | 235 | Captura e validação de combinações de teclas. |
| `vozflow/overlay.py` | 226 | Janela flutuante que nunca rouba o foco. |
| `vozflow/calibracao.py` | 54 | Mede ambiente e voz, calcula o limiar (usado pela aba Microfone). |
| `vozflow/modelo.py` | 137 | Download do modelo com progresso visível. |
| `vozflow/config.py` | 203 | `config.json`, padrões e migrações. |
| `vozflow/janela.py` | 169 | Prende a escrita na janela onde a ditada começou. |
| `vozflow/inserter.py` | 137 | Colar, digitar, copiar ou mandar por webhook. |
| `vozflow/texto.py` | 82 | Anti-repetição e anti-eco do prompt. |
| `vozflow/diagnostico.py` | 64 | `python -m vozflow.diagnostico`. |
| `hooks/hook-webrtcvad.py` | 11 | Hook do PyInstaller que sobrepõe o oficial. |
| `tests/` | 1474 | Suíte pytest com dublês de teclado, clipboard, janela e motor (ver CONTRIBUTING). |

Cerca de **3.800 linhas de Python** no app, mais 1.500 de testes.

---

## Stack

| Camada | O que usa |
|---|---|
| Transcrição | `faster-whisper` (CTranslate2), modelo `large-v3-turbo` |
| Aceleração | CUDA float16 — cai para CPU sozinho se faltar |
| Áudio | `sounddevice` (PortAudio) + `webrtcvad-wheels` |
| Interface | PySide6 (Qt6) — ícone na bandeja, janela flutuante sem foco |
| Teclado | `keyboard` (ganchos globais de baixo nível) |
| Entrega | `pyperclip` + `keyboard.write` + `requests` (webhook) |
| Empacotamento | PyInstaller (`VozFlow.spec`) + Inno Setup (`instalador.iss`) |

Python 3.12. Dependências em `requirements.txt`; as de GPU em
`requirements-gpu.txt`.

---

## Onde ficam os dados

| Caminho | O que é |
|---|---|
| `%APPDATA%\VozFlow\config.json` | toda a configuração |
| `%APPDATA%\VozFlow\transcricoes.txt` | histórico do que foi ditado |
| `%USERPROFILE%\.cache\huggingface` | o modelo, baixado uma vez só (1,6 GB com GPU, ~145 MB sem) |
| `%LOCALAPPDATA%\Programs\VozFlow\` | o app instalado |
| `%APPDATA%\...\Startup\VozFlow.vbs` | o que faz iniciar com o Windows |
