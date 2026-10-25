# Desempenho

Todos os números aqui foram **medidos**, não estimados, salvo onde está escrito
o contrário. Máquina de referência: RTX 4060 (8 GB), modelo `large-v3-turbo`
em float16, Windows 11.

---

## Latência até a primeira palavra

Este foi o alvo principal de otimização: quanto tempo entre você começar a
falar e a primeira palavra aparecer no campo.

| versão | 1ª palavra | depois de você começar a falar |
|---|---|---|
| esperando o silêncio fechar a frase | 8,0 s | — |
| prefixo estável, `partial_interval` 0,6 s | 3,6 s | 2,7 s |
| + comparação sem pontuação | 2,7 s | 1,8 s |
| + `partial_interval` 0,45 s | 2,4 s | 1,5 s |
| **+ só o texto novo comparado, `partial_interval` 0,3 s** | — | **1,6 s** |

Observações sobre a tabela:

- **A comparação sem pontuação sozinha valeu 0,86 s.** O Whisper trocar
  `"Bom dia!"` por `"Bom dia,"` fazia a palavra "não bater" no teste de
  estabilidade e custava uma rodada inteira antes de qualquer texto aparecer.
- **Em 0,45 s o intervalo parou na 1.2.0, e desceu para 0,3 s na 1.2.2.** Com
  a regra antiga, abaixo de 0,45 s o ganho era pequeno. Com a comparação só do
  texto novo cada transcrição a mais vira texto — ver a seção abaixo.

---

## Fluidez com fala real contínua (1.2.2)

Medido com o motor real: uma leitura contínua de 25 s gravada no microfone do
usuário (e uma fala sintética de 20 s) entra em tempo real por um microfone
falso; um teclado falso anota o instante de cada letra. O instante em que cada
palavra foi dita vem do próprio Whisper (`word_timestamps`) sobre o áudio
inteiro. Mediana de 3 rodadas por configuração, RTX 4060:

| voz real (70 palavras) | 1ª palavra | atraso típico | atraso p90 | maior engasgo | palavras diferentes |
|---|---|---|---|---|---|
| 1.2.1 (regra antiga, 0,45 s) | 2,52 s | 3,50 s | 4,08 s | 1,06 s | 6 |
| regra nova, 0,45 s | 2,14 s | 2,90 s | 3,34 s | 1,12 s | 5 |
| regra nova, 0,3 s | 1,19 s | 2,39 s | 2,81 s | 0,72 s | 4 |
| **1.2.2 (regra nova, 0,3 s, com as correções da revisão)** | **1,64 s** | **2,49 s** | **2,95 s** | **0,70 s** | **4** |

| fala sintética | 1ª palavra | atraso típico | atraso p90 | maior engasgo |
|---|---|---|---|---|
| 1.2.1 | 2,01 s | 2,80 s | 3,09 s | 0,56 s |
| **1.2.2** | **1,79 s** | **1,90 s** | **2,17 s** | **0,34 s** |

O "atraso" vai de quando a palavra termina de ser dita até a última letra dela
aparecer no campo. A última linha é o código lançado: a revisão independente
achou casos raros de palavra duplicada ou perdida com palavra repetida, e uma
palavra curta cortada ("em" de "embora") saindo cedo. A correção zerou
duplicações e perdas num fuzz de 20 mil frases, e num fuzz adversarial de
junções e separações ("porque" ↔ "por que") errou menos que a 1.2.1. Custou
cerca de 0,4 s na primeira palavra, que costuma ser curta e agora espera uma
rodada. A tabela da fala sintética é da regra antes dessas correções.

O que travava: a comparação ia desde o início do trecho, e o Whisper reescreve
à toa palavras que já estão no campo — só 10 de 25 transcrições liberavam
texto. Ressalva: em 0,3 s a GPU fica perto de 100% enquanto você fala; se o
texto atrasar numa GPU mais fraca, o intervalo já cresce sozinho, e
`partial_interval` em `0.45` volta ao comportamento anterior.

---

## Tempos do ciclo completo

| etapa | tempo |
|---|---|
| atalho pressionado → gravando | ~28 ms |
| primeira palavra escrita no campo | ~2,4 s |
| texto cresce a cada | ~0,5 a 1,5 s |
| entrega de cada trecho fechado | ~170 ms |
| transcrição de um trecho na GPU | ~0,3 s |
| transcrição de um trecho na CPU | vários segundos |

A latência **não cresce** com a duração do ditado: o que se retranscreve é
sempre o trecho aberto (no máximo 20 s), nunca a gravação inteira.

---

## Cadência da escrita: colar vs. digitar

Medido no mesmo áudio de 20 s, amostrando o campo de destino a cada 50 ms:

| | colando blocos | digitando cadenciado |
|---|---|---|
| atualizações visuais | 16 | **156** |
| letras por atualização | até 20 | **1,1** (máx. 5) |
| intervalo médio | 1,2 s | **0,12 s** |
| maior engasgo | 2,4 s | **0,58 s** |
| engasgos acima de 0,7 s | 5 | **0** |

O "engasgo" é o que o olho registra como travamento. Zerar os acima de 0,7 s é
a diferença entre um texto que **flui** e um que **salta**.

Bônus: colar sujava a área de transferência 16 vezes por ditada.

---

## Rejeição de voz de fundo

Medido com uma conversa de fundo 15× mais fraca sobreposta à voz no microfone:

| cenário | resultado |
|---|---|
| só a conversa de fundo | nada transcrito |
| só a voz no microfone | transcrita completa |
| as duas misturadas | 4/4 palavras da voz de perto, **zero** palavras do fundo |

Num headset de haste a diferença de nível entre quem fala no microfone e uma
conversa do outro lado da sala é de **10 a 50 vezes**. É essa margem que o
corte por `nivel_fala` explora.

Vale o limite honesto: é corte por nível, não separação de vozes. Alguém
falando alto e perto do seu microfone passa.

---

## Download do modelo: backend Xet vs. clássico

`vozflow/__init__.py` define `HF_HUB_DISABLE_XET=1` antes de qualquer import do
`huggingface_hub`. Medido com o modelo `small` (464 MB):

| backend | degraus de progresso | tempo |
|---|---|---|
| Xet (padrão da biblioteca) | 4 | 13,4 s |
| clássico | **14** | **11,5 s** |

O Xet baixa em blocos grandes e só descarrega no cache de vez em quando, o que
deixa a barra de progresso quase inútil. Com o modelo padrão de 1,6 GB, isso
deixaria a pessoa olhando "14%" parado por minutos. E o clássico ainda saiu
mais rápido nesta medição.

---

## Tamanho do pacote

O primeiro build saiu com **2.306 MB**, porque `--collect-all nvidia` arrasta
tudo que vem nas rodas do CUDA. Medindo DLL por DLL — removendo cada uma e
rodando uma transcrição de verdade na GPU — a maior parte nunca é tocada:

| removido | tamanho | por quê |
|---|---:|---|
| cuDNN inteiro | 1.011 MB | o `ctranslate2` não usa cuDNN no caminho do Whisper |
| NVRTC | 178 MB | compilação de kernels em runtime, que o `ctranslate2` não faz |
| onnxruntime | 39 MB | só serve ao VAD Silero do `faster-whisper`; aqui o VAD é o WebRTC |
| `opengl32sw.dll` | 20 MB | OpenGL por software do Qt; a interface é widgets comuns |
| nvblas | 0,3 MB | substituto de BLAS para CPU, sem uso |

Sozinhas, `cudnn_engines_precompiled64_9.dll` (522 MB) e `cudnn_adv64_9.dll`
(257 MB) valiam mais que o pacote final inteiro.

**Sem elas o resultado é idêntico:** mesmo texto, ainda na GPU, `1.01x` de
diferença de tempo (0,526 s contra 0,529 s em três medições).

O que sobrou é o piso real:

| item | tamanho | por que fica |
|---|---:|---|
| `cublasLt64_12.dll` | 638 MB | multiplicação de matrizes na GPU |
| `cublas64_12.dll` | 98 MB | idem |
| `av` + `av.libs` | 66 MB | o `faster_whisper` importa `av` no topo de `audio.py` |
| ctranslate2 | 59 MB | o motor de inferência |
| PySide6 | 52 MB | a interface |

### Com ou sem GPU

| variante | comando | instalado | transcrição |
|---|---|---:|---|
| com GPU | `gerar-instalador.bat` | **995 MB** | ~0,3 s |
| só CPU | `gerar-instalador.bat cpu` | **259 MB** | vários segundos |

(259 MB = 995 menos os 736 MB das duas DLLs de cuBLAS — aritmética sobre
tamanhos medidos; a variante CPU em si não foi compilada.)

O modelo (~1,6 GB com GPU, ~145 MB sem) **não** vai no instalador: baixa no primeiro uso e fica em
`~/.cache/huggingface`, compartilhado entre versões.

A receita completa do corte está em `VozFlow.spec`, com o motivo de cada
exclusão anotado no próprio arquivo.

---

## Sem GPU: o modelo automático

Medido em 2026-10-24 nesta máquina (Windows 11), com uma fala sintética em
pt-BR de 17,6 s (voz "Maria" do Windows) e os parâmetros de decodificação do
app.

**Custo de cada transcrição, isolada:**

| modelo / dispositivo | cada prévia (5–17 s de áudio) | final, beam 5 |
|---|---|---|
| `large-v3-turbo`, CPU int8 | 12,3–13,6 s | 13,8 s |
| `small`, CPU int8 | 2,8–3,7 s | 4,2 s |
| `base`, CPU int8 | 0,9–1,2 s | 1,3 s |
| `large-v3-turbo`, GPU float16 | 0,31–0,45 s | 0,6 s |

**De ponta a ponta:** o motor real recebe o WAV em tempo real, em blocos de
100 ms, por um microfone falso.

| CPU | 1ª palavra escrita | trechos escritos ao vivo | encerrar → texto final |
|---|---|---|---|
| antes (`large-v3-turbo`, padrão da 1.1.1) | 43,9 s | 1 (só no fim) | 24,1 s |
| **agora (`auto` → `base`)** | **2,8 s** | **6** | **0,02 s** |

Três mudanças fizeram isso:

- **`model: auto`.** Usa `large-v3-turbo` com GPU e `base` sem GPU. Na CPU, o
  modelo grande nunca chegava a escrever ao vivo.
- **Prévia na CPU sem fallback de temperatura e com teto de tokens.** A
  primeira prévia de cada fala (0,7 s de áudio) levava de 3 a 8 s refazendo a
  decodificação até 6 vezes sobre texto alucinado. A versão **final** de cada
  trecho continua com a proteção completa. Na GPU, nada muda.
- **Intervalo entre prévias que se adapta.** Se a prévia leva mais que
  `partial_interval`, a próxima espera 25% a mais que ela, com teto de 2 s,
  para o motor ter folga para o microfone e o comando de parar.

Ressalvas:

- Voz sintética é fácil. Com fala real e ruído, o `base` erra mais que o
  `large-v3-turbo`; numa CPU forte, `small` é o meio-termo.
- Com GPU, o caminho é o mesmo de antes: mesmo modelo, mesma decodificação, e
  o intervalo só se adapta quando uma prévia passa de `partial_interval` — na
  GPU livre elas levam 0,31–0,45 s. A comparação de ponta a ponta na GPU
  ficou **inconclusiva** nesta rodada: a placa estava ocupada por outros
  programas (31–73% de uso, ~5 GB de memória), e os resultados variaram de
  8 s a 67 s **nas duas versões**. Com a GPU livre, no início da sessão, a
  primeira palavra saiu em 2,8 s. Vale repetir com a placa ociosa.

---

## Ajustando para a sua máquina

Se a sua GPU é mais fraca ou você está na CPU:

| sintoma | o que mexer |
|---|---|
| texto demora demais a aparecer | `model` em `auto` (padrão); com GPU fraca, `medium` ou `small` |
| sem GPU, quer mais precisão e a CPU aguenta | `model` para `small` (~3 s por prévia) |
| GPU sempre em 100% | `partial_interval` para `0.6` ou `0.8` |
| frases picotadas | `silence_ms` para `900` ou `1100` |
| texto fantasma no silêncio | `nivel_minimo` um pouco acima |
| a sua fala baixa não é captada | rode **Calibrar com a minha voz** |

A tabela completa de opções está em [Configuração](CONFIGURACAO.md).
