# VozFlow

Ditado por voz para Windows com atalhos globais. Você clica no campo onde quer
escrever — bloco de notas, WhatsApp Web, VS Code, Gmail, campo de busca —, aperta
o atalho e começa a falar. **O texto vai sendo escrito ali, enquanto você fala.**
Aperta o outro atalho e a ditada encerra.

A janelinha flutuante mostra o que está sendo entendido no momento, incluindo as
palavras ainda provisórias. Ela nunca rouba o foco, então o cursor continua no
seu campo o tempo todo.

Roda **100% offline** na sua máquina (faster-whisper + GPU NVIDIA). Sem chave de
API, sem custo por minuto, sem mandar áudio para lugar nenhum.

---

## Instalação

```
instalar.bat        (duplo clique)
```

Ele cria o ambiente `.venv`, instala as dependências, detecta a GPU NVIDIA e
baixa o modelo de transcrição (~1,6 GB na primeira vez).

Depois, para usar:

```
VozFlow.vbs         (duplo clique — roda sem janela de console)
VozFlow-debug.bat   (se quiser ver os logs)
```

O ícone de microfone aparece na bandeja do sistema, ao lado do relógio.

---

## Atalhos

| Atalho | O que faz |
|---|---|
| `Ctrl + Alt + G` | Começa a ditar. O texto vai sendo escrito no campo em foco conforme você fala. |
| `Ctrl + Alt + S` | Encerra a ditada e escreve o que faltava do último trecho. |
| `Ctrl + Alt + X` | Cancela. O que já foi escrito no campo continua lá — o resto é descartado. |

Clicar no ícone da bandeja também alterna entre gravar e parar.

### Trocar os atalhos

Botão direito no ícone da bandeja → **Configurações... → aba Atalhos**. Clique no
campo, pressione a combinação que quiser e salve. Vale na hora, sem reiniciar.

Regras que a janela valida para você:

- **Combinação com modificador** (`Ctrl`, `Alt`, `Shift`, `Win`) passa sem aviso.
  É a escolha segura.
- **Tecla de navegação sozinha** (`PgUp`, `PgDn`, `Home`, `End`, setas) recebe
  aviso: você aperta essas o tempo todo para rolar a página, e o VozFlow ligaria
  sozinho. Só vale se a tecla vier de um controle remoto que não serve para
  mais nada. *(Aprendi isso da forma difícil — a primeira pessoa a usar o app
  escolheu `PgDn` e ele "ligava do nada" a cada rolagem.)*
- **Tecla de digitação sozinha** (letra, número, espaço) recebe aviso mais forte:
  dispararia no meio de qualquer texto.
- Praticamente sem uso e portanto seguras sozinhas: `Pause`, `Scroll Lock`,
  teclas de mídia.
- **Os sons** são senoides curtas geradas em memória (`SONS` em `app.py`), não
  `winsound.Beep`. O `Beep` gera onda *quadrada* pelo emulador do alto-falante
  do PC — áspera, e como liga e desliga na amplitude cheia, estala nas duas
  pontas; num fone Bluetooth virava chiado. Com envelope de 6 ms de ataque e
  queda longa, o sinal parte do zero e volta ao zero. O toque de "iniciar"
  ainda *termina* antes de o microfone abrir, porque o fone Bluetooth troca de
  A2DP para HFP nesse instante e a troca corta o som pela metade. Desligue tudo
  em Configurações → Geral.
- Tecla sem modificador continua fazendo a função normal dela ao mesmo tempo.
  Marque **"Reservar a tecla para o VozFlow"** para o app consumir a tecla.
- `Alt + Shift` é recusado: o Windows consome essa combinação para trocar o
  idioma do teclado e ela nunca chega até o VozFlow.
- Usar a **mesma** combinação em iniciar e parar vira uma tecla única que alterna.
- **A gêmea do teclado numérico não dispara.** `PgDn` e `Num 3` chegam ao Windows
  com o *mesmo* scancode (81) — o que separa as duas é o flag de tecla estendida,
  e a lib `keyboard` casa atalho olhando só o scancode. Resultado: quem escolhia
  `PgDn` via o VozFlow ligar ao digitar qualquer número no numérico. O app agora
  lê o `is_keypad` do evento e ignora a tecla do numérico. Vale para o bloco
  inteiro: `End`/`Num 1`, `Delete`/`Num .`, `Enter`/`Num Enter` e as setas.
  Mesmo com "Reservar a tecla" ligado, o `Num 3` continua digitando `3`.

> **Teclado ABNT2:** o `AltGr` é lido pelo Windows como `Ctrl+Alt`. As teclas
> `G`, `S` e `X` não têm caractere em `AltGr`, então não há conflito — mas se
> você trocar os atalhos, evite `AltGr+Q`, `W`, `C`, `1`, `2`, `3`, `4`, `5`, `6`.

---

## Como o texto vai aparecendo enquanto você fala

O problema de escrever ao vivo é que o Whisper muda de ideia: a transcrição de
"pre..." vira "preciso", que vira "preciso confirmar". Não dá para escrever cada
palpite e depois apagar.

A solução aqui é **prefixo estável**. O trecho aberto é retranscrito a cada
`partial_interval` segundos. Uma palavra que sobreviveu igual a duas
transcrições seguidas é considerada firme e vai para o campo; a última palavra
firme fica retida, porque ela ainda costuma mudar quando chega mais áudio.
Nada é escrito duas vezes e nada precisa ser apagado.

A comparação entre duas transcrições ignora pontuação e acento. Sem isso, o
Whisper trocar `"Bom dia!"` por `"Bom dia,"` fazia a palavra "não bater" e
custava uma rodada inteira antes de qualquer texto aparecer — sozinho, esse
detalhe atrasava a primeira palavra em **0,86 s**.

Evolução medida da latência até a primeira palavra aparecer no campo:

| versão | 1ª palavra | depois de você começar a falar |
|---|---|---|
| esperando o silêncio fechar a frase | 8,0 s | — |
| prefixo estável, `partial_interval` 0,6 s | 3,6 s | 2,7 s |
| + comparação sem pontuação | 2,7 s | 1,8 s |
| **+ `partial_interval` 0,45 s** | **2,4 s** | **1,5 s** |

Abaixo de 0,45 s o ganho é pequeno e o custo não: em 0,35 s a GPU passa ~80% do
tempo transcrevendo, para economizar 0,17 s.

Se preferir o comportamento antigo (nada aparece até você encerrar, aí cola tudo
de uma vez), desmarque **"Escrever no campo enquanto eu falo"** em
Configurações → Escrita.

## Por que o texto sai liso e não em blocos

O motor entrega palavras em rajadas: 2 ou 3 de uma vez a cada
`partial_interval`, com pausa maior quando a frase fecha. Escrever cada rajada
de uma vez fazia o texto **saltar**, e dava impressão de travamento.

Duas mudanças resolveram:

**Digitar em vez de colar.** Cada trecho ia por área de transferência + `Ctrl+V`
— um salto atômico de várias palavras, além de sujar o clipboard 16 vezes por
ditada. Agora usa `keyboard.write`, que digita caractere a caractere. Testei os
acentos antes de trocar: `coração, licitação, orçamento, é, à, já, você` saem
perfeitos, e ainda é mais rápido que colar palavra a palavra.

**Cadência com crédito fracionário.** As letras vão para um buffer e saem a cada
25 ms, num ritmo que espalha o buffer ao longo do intervalo em que a próxima
leva costuma chegar. Sem a parte fracionária, poucas letras saíam em 2 ou 3
ticks e o texto parava até a leva seguinte — o "engasgo no meio da frase".

Medido no mesmo áudio de 20 s, amostrando o campo de destino a cada 50 ms:

| | colando blocos | digitando cadenciado |
|---|---|---|
| atualizações visuais | 16 | **156** |
| letras por atualização | até 20 | **1,1** (máx. 5) |
| intervalo médio | 1,2 s | **0,12 s** |
| maior engasgo | 2,4 s | **0,58 s** |
| engasgos acima de 0,7 s | 5 | **0** |

## Como funciona por dentro

A gravação é fatiada em trechos delimitados por silêncio (~0,7 s). Enquanto um
trecho está aberto, ele é retranscrito a cada 0,6 s para alimentar a janela
flutuante. Quando o silêncio fecha o trecho, ele passa por uma transcrição
final com mais qualidade (beam search) e vira texto definitivo.

Isso dá a sensação de tempo real sem o custo de retranscrever a gravação inteira
a cada atualização — e mantém a latência constante mesmo num ditado de 5 minutos.

Medido nesta máquina (RTX 4060, modelo `large-v3-turbo` em float16):

- atalho pressionado → gravando: **~28 ms**
- primeira palavra escrita no campo: **~4 s**
- texto cresce a cada **~0,5 a 1,5 s** depois disso
- colagem de cada trecho: **~170 ms**

> A janela flutuante é "pré-aquecida" escondida durante a inicialização. A
> primeira exibição de uma janela translúcida sempre-no-topo custa ~2,5 s no Qt
> (inicialização da composição do DWM, segurando a GIL). Sem esse truque, esse
> atraso cairia no seu primeiro `Ctrl+Alt+G` e comeria as primeiras palavras.

---

## Só a sua voz, não a sala

O Whisper transcreve tudo que chega no áudio — ele não sabe quem está falando.
Separar por identidade de voz exigiria cadastrar a sua, o que é pesado. O que
o VozFlow usa é **proximidade**: quem fala no microfone chega muito mais forte
que uma conversa do outro lado da sala. Num headset de haste a diferença é de
10 a 50 vezes.

Som abaixo de `nivel_fala` não abre um trecho e não vira texto. Com histerese,
para uma sílaba fraca no meio da palavra não picotar a frase.

**Rode Configurações → Microfone → "Calibrar com a minha voz" uma vez.** Ele mede o ambiente
por 4 s, depois a sua voz por 4 s, e grava o limiar no meio dos dois — mostrando
quantas vezes a sua voz fica acima do corte. Sem calibrar, o padrão `0.010`
funciona para a maioria dos headsets, mas não é o número certo para o seu.

Medido com uma conversa de fundo 15× mais fraca sobreposta à voz no microfone:

| cenário | resultado |
|---|---|
| só a conversa de fundo | nada transcrito |
| só a voz no microfone | transcrita completa |
| as duas misturadas | 4/4 palavras da voz de perto, **zero** palavras do fundo |

Se o limiar ficar alto demais para a sua voz, o app avisaria emudecendo — o pior
desfecho possível. Em vez disso, depois de ~3 s ouvindo som fraco demais ele
escreve na janelinha: *"Não estou captando sua voz — o som está fraco demais."*

**Limite honesto:** isso é um corte por nível, não separação de vozes. Alguém
falando alto e perto do seu microfone passa. Para um filtro de verdade, a sua
máquina tem o **NVIDIA Broadcast** — selecione a entrada "Microfone (NVIDIA
Broadcast)" em Configurações → Microfone e ele aplica remoção de ruído e de vozes de
fundo por IA antes do áudio chegar aqui.

## Primeiro uso: o download do modelo

O modelo não vem no instalador — são 1,6 GB baixados uma única vez e guardados
em `~/.cache/huggingface`, compartilhados entre versões.

O `faster_whisper.download_model` passa `tqdm_class=disabled_tqdm`: o download
acontece **sem nenhum sinal de vida**. Na primeira instalação em outra máquina
isso fez o app parecer travado — quem apertava o atalho só via *"Ainda
carregando o modelo, aguarde..."* por vários minutos, sem saber se estava
baixando, se tinha falhado ou se travou.

Agora `vozflow/modelo.py` cuida disso:

- assim que o app abre pela primeira vez, um balão da bandeja avisa que o
  download de 1,6 GB começou e que acontece uma única vez;
- a janelinha flutuante aparece sozinha com o progresso: *"Baixando o modelo:
  47% (730 de 1547 MB)"*, atualizando a cada meio segundo;
- apertar o atalho durante o download mostra o progresso, não uma mensagem
  genérica;
- se falhar, a mensagem diz **o que fazer**: sem internet, sem espaço em disco,
  ou repositório recusado — em vez do erro cru da biblioteca.

O progresso é medido pelo tamanho da pasta de cache, e não pelo `tqdm` do
huggingface_hub, porque assim funciona com qualquer backend.

### Por que o backend Xet fica desligado

`vozflow/__init__.py` define `HF_HUB_DISABLE_XET=1` antes de qualquer import do
huggingface_hub. O backend Xet baixa em blocos grandes e só descarrega no cache
de vez em quando, o que deixa o progresso quase inútil. Medido com o modelo
`small` (464 MB):

| backend | degraus de progresso | tempo |
|---|---|---|
| Xet (padrão) | 4 | 13,4 s |
| clássico | **14** | **11,5 s** |

Com 1,5 GB, o Xet deixaria o usuário olhando "14%" parado por minutos. E o
clássico ainda saiu mais rápido nesta medição.

## Contra as alucinações do Whisper

O Whisper tem duas falhas clássicas, e as duas apareceram em uso real aqui.
São barradas em três camadas:

1. **Portão de energia** — áudio abaixo de `nivel_minimo` (RMS) nem chega ao
   modelo. Sem isso, o silêncio vira frase inventada: uma gravação muda chegou a
   produzir *"Descender."* do nada. Ruído de sala fica na casa de `1e-5`; fala
   fica acima de `1e-2`, então a margem é de centenas de vezes.
2. **Fallback de temperatura** — o `temperature` é uma *lista*, não `0.0` fixo.
   É isso que deixa o `compression_ratio_threshold` detectar saída degenerada e
   redecodificar. Com `0.0` fixo esse mecanismo fica desligado.
3. **`vozflow/texto.py`** — última linha de defesa antes de colar: colapsa
   n-gramas repetidos (mantendo repetição natural como "não, não") e remove
   trechos que são eco literal do `initial_prompt`.

O texto já transcrito **não** é realimentado no prompt do trecho seguinte:
prender o decoder ao próprio resultado anterior é o que o faz travar repetindo.

## Menu da bandeja

Só ações, nada de ajuste:

- **Começar a ditar / Encerrar e enviar / Cancelar** (com o atalho ao lado)
- **Configurações...**
- **Copiar última transcrição**
- **Abrir histórico de transcrições**
- **Sair**

Clicar no ícone alterna entre ditar e encerrar.

## Janela de configurações

Tudo que dá para ajustar está aqui, em quatro abas. Salvou, vale na hora — só
troca de modelo pede reiniciar.

**Atalhos** — as três teclas (começar, encerrar, cancelar) e a opção *Reservar a
tecla para o VozFlow*. Clique no campo e pressione a combinação. Usar a mesma
tecla em começar e encerrar vira um atalho único que alterna.

**Microfone** — escolha da entrada, **medidor de nível ao vivo** (você vê na hora
se o microfone está te captando) e o botão **Calibrar com a minha voz**, que mede
seu ambiente e sua voz e ajusta o corte de voz de fundo.

**Escrita** — para onde o texto vai (colar / digitar / só copiar / webhook),
escrever ao vivo enquanto fala, e apertar Enter ao encerrar.

**Geral** — modelo, idioma, vocabulário, janela flutuante, sons, iniciar com o
Windows, histórico, e um atalho para abrir o `config.json` cru.

## Configuração

`%APPDATA%\VozFlow\config.json` (também acessível pelo menu da bandeja).
Alterou? Feche e abra o VozFlow.

| Chave | Padrão | Para que serve |
|---|---|---|
| `hotkey_start` / `hotkey_stop` / `hotkey_cancel` | `ctrl+alt+g` / `ctrl+alt+s` / `ctrl+alt+x` | Atalhos globais. Use o mesmo valor em start e stop para virar um atalho único que alterna. |
| `model` | `large-v3-turbo` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`. Modelos menores são mais rápidos e menos precisos. |
| `language` | `pt` | Deixe `""` (vazio) para detecção automática. |
| `device` / `compute_type` | `auto` | Force `cpu` / `int8` se quiser poupar a GPU. |
| `initial_prompt` | `""` | Vocabulário para o modelo acertar nomes próprios, jargões e siglas do seu contexto. |
| `silence_ms` | `700` | Silêncio que fecha um trecho. Aumente se você fala com pausas longas. |
| `nivel_fala` | `0.010` | Abaixo deste nível (RMS) o som é tratado como fundo e não vira texto. Use "Calibrar microfone" em vez de chutar. `0` desliga o corte. |
| `nivel_minimo` | `0.004` | RMS abaixo disso conta como mudo e nem vai ao modelo. Aumente se ainda aparecer texto fantasma; diminua se você fala muito baixo. |
| `partial_interval` | `0.6` | Segundos entre as retranscrições do trecho aberto. Menor = texto aparece mais rápido e a GPU trabalha mais. |
| `insercao_ao_vivo` | `true` | Escreve cada trecho no campo em foco durante a fala. `false` = só cola tudo no fim. |
| `suppress_hotkeys` | `false` | `true` reserva a tecla para o VozFlow (ela para de fazer a função normal). |
| `action_on_stop` | `paste` | `paste`, `type`, `clipboard` ou `webhook`. |
| `press_enter_after` | `false` | Aperta Enter depois de colar. |
| `webhook_url` / `webhook_field` | `""` / `texto` | Para `action_on_stop: "webhook"` — manda `{"texto": "..."}` via POST. |
| `hotkey_start2` / `hotkey_stop2` / `press_enter_after2` | `""` / `""` / `false` | Segundo par de atalhos, com a **sua propria** regra de Enter. Serve para ter uma tecla que so escreve e outra que escreve e ja envia. |
| `travar_janela` | `true` | Prende a escrita na janela onde a ditada comecou. Trocando de janela no meio da fala, o texto espera em vez de vazar. |
| `overlay_posicao` | `inferior-centro` | `inferior-`/`superior-` + `centro`/`esquerda`/`direita`, ou `centro`. |
| `input_device` | `null` | **Nome** do microfone (`null` = padrão do Windows). Guardar o nome, e não o índice, é de propósito: o PortAudio renumera a lista inteira quando um fone Bluetooth conecta ou o NVIDIA Broadcast liga. Configs antigas com número são convertidas sozinhas na primeira abertura. |
| `log_transcricoes` | `true` | Grava tudo em `%APPDATA%\VozFlow\transcricoes.txt`. |

### Melhorando o reconhecimento

O jeito mais eficaz é preencher `initial_prompt` com o vocabulário que você usa:

```json
"initial_prompt": "Versaty Solar, ConnectaLink, Evolution API, Laravel, kWp, boleto, CRM."
```

**Use só uma lista de termos, nunca uma frase em prosa.** O Whisper trata o
prompt como contexto transcritível e ecoa prosa na saída — um prompt que começava
com *"Anotações de trabalho em português do Brasil."* fez uma ditada sair como
*"Teste 1, 2, 3. **Anotações de trabalho.**"*. O `texto.py` remove esse eco
quando ele escapa, mas evitar a prosa resolve na origem.

---

## Diagnóstico

```
.venv\Scripts\python.exe -m vozflow.diagnostico
```

Lista os microfones, confirma se a GPU está sendo usada e valida o modelo.

---

## Gerar o executável e o instalador

```
gerar-exe.bat            executável autônomo em dist\VozFlow\
gerar-instalador.bat     instalador em instalador\VozFlow-1.0.0-instalador.exe
```

O instalador não pede administrador: instala em `%LOCALAPPDATA%\Programs\VozFlow`,
cria atalho no menu Iniciar (e na área de trabalho, se você marcar), aparece em
**Aplicativos Instalados** do Windows e tem desinstalador.

A opção *"Iniciar junto com o Windows"* do instalador grava exatamente o mesmo
`VozFlow.vbs` que a tela de configurações cria e remove — as duas nunca divergem.
Ao desinstalar, ele pergunta se você quer apagar também suas configurações e o
histórico; numa desinstalação silenciosa o padrão é **preservar**.

### Por que era 2,3 GB, e como virou 1,0 GB

O primeiro pacote saiu com **2306 MB** porque `--collect-all nvidia` arrasta
tudo que vem nas rodas do CUDA. Medindo DLL por DLL — removendo cada uma e
rodando uma transcrição de verdade na GPU — descobri que a maior parte nunca é
tocada:

| removido | tamanho | por quê |
|---|---|---|
| cuDNN inteiro | 1011 MB | o ctranslate2 não usa cuDNN no caminho do Whisper |
| NVRTC | 178 MB | compilação de kernels em runtime, que o ctranslate2 não faz |
| onnxruntime | 39 MB | só serve ao VAD Silero do faster-whisper; aqui o VAD é o WebRTC |
| opengl32sw.dll | 20 MB | OpenGL por software do Qt; a interface é widgets comuns |
| nvblas | 0,3 MB | substituto de BLAS para CPU, sem uso |

Sozinhas, `cudnn_engines_precompiled64_9.dll` (522 MB) e `cudnn_adv64_9.dll`
(257 MB) valiam mais que o pacote final inteiro.

Sem elas o resultado é **idêntico**: mesmo texto, ainda na GPU, `1.01x` de
diferença de tempo (0,526 s contra 0,529 s em três medições).

O que sobrou é o piso real:

| item | tamanho | por quê fica |
|---|---|---|
| `cublasLt64_12.dll` | 638 MB | multiplicação de matrizes na GPU |
| `cublas64_12.dll` | 98 MB | idem |
| PySide6 | 52 MB | a interface |
| ctranslate2 | 59 MB | o motor de inferência |
| av + av.libs | 66 MB | o `faster_whisper` importa `av` no topo de `audio.py` |

### Tamanho: com ou sem GPU

| variante | comando | instalado | transcrição |
|---|---|---|---|
| com GPU | `gerar-instalador.bat` | **995 MB** | ~0,3 s |
| só CPU | `gerar-instalador.bat cpu` | **259 MB** | vários segundos |

(259 MB = 995 menos os 736 MB das duas DLLs de cuBLAS — aritmética sobre
tamanhos medidos; a variante CPU em si não foi compilada.)

O modelo (~1,6 GB) **não** vai no instalador: baixa no primeiro uso e fica em
`~/.cache/huggingface`, compartilhado entre versões.

A receita do corte está em `VozFlow.spec`, com o motivo de cada exclusão.

### Armadilha do empacotamento

O `hooks/hook-webrtcvad.py` existe porque o hook oficial do PyInstaller faz
`copy_metadata('webrtcvad')` e aborta o build inteiro: o módulo aqui vem da
distribuição `webrtcvad-wheels` (a original não tem wheel para Python 3.12), e o
nome não bate. O hook local sobrepõe o oficial.

## Problemas comuns

**"Library cublas64_12.dll is not found"** — falta o CUDA:
`.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt`.
Sem isso o app cai para CPU sozinho, só fica mais lento.

**O atalho não responde** — outro programa já registrou a mesma combinação, ou
o app em foco roda como administrador (aí o VozFlow também precisa rodar como
administrador para enxergar o teclado dele).

**Texto foi parar na janela errada** — resolvido pelo `travar_janela` (ligado
por padrão): o VozFlow guarda a janela onde você apertou a tecla e, se o foco
sair dela, **segura o texto** em vez de deixá-lo vazar. A janelinha flutuante
avisa (`Texto segurado - volte para ...`) e você continua acompanhando a
transcrição ao vivo por ela. Ao encerrar, o VozFlow traz a janela original de
volta e entrega tudo de uma vez.

Por que não escreve na janela de fundo, já que ela é conhecida: não dá. Medido
contra uma página de teste no Chrome, com o foco em outra janela, `PostMessage
WM_CHAR`, `SendMessage WM_CHAR`, a sequência `KEYDOWN`/`CHAR`/`KEYUP` e até
`AttachThreadInput` + `SetFocus` foram **todos ignorados** — o Chromium recusa
input sintético de outro processo, e nele nem existe controle filho para
receber a mensagem (`hwndFocus` é a própria janela de topo e `hwndCaret` é
zero, porque o campo é um elemento DOM). Como Chrome, Edge, VS Code, WhatsApp e
Discord são todos Chromium, a família inteira de soluções "escrever sem foco"
está descartada.

Se a janela original não voltar ao foco na hora de entregar (o Windows pode
recusar), o VozFlow **não digita às cegas**: copia o texto e avisa. Com "apertar
Enter" ligado, digitar sem confirmação mandaria a mensagem na janela errada.

**Texto sai truncado ou repetido** — aumente `silence_ms` se você faz pausas
longas no meio das frases.

**Liguei o fone depois do VozFlow e ele não acha o microfone** — resolvido, mas
vale saber por quê: o PortAudio monta a lista de dispositivos uma única vez, no
`Pa_Initialize`, e não a atualiza sozinha. Como o VozFlow sobe junto com o
Windows e um fone Bluetooth costuma ser ligado depois, o aparelho salvo
simplesmente não existia para o processo — e a gravação caía no padrão do
Windows, muda, sem erro nenhum. Hoje o `Recorder` reinicia o PortAudio quando
não encontra o microfone salvo (só com nenhum stream aberto: reiniciar com um
stream vivo derruba o processo).

**Fone Bluetooth: o microfone "existe" mas nunca grava** — um fone Bluetooth
aparece no Windows como *dois* perfis. O **A2DP** (`Fones de ouvido (...)`) é
estéreo e de alta qualidade, mas **só reproduz**: o endpoint de microfone que
ele expõe nunca captura nada, por definição. O microfone real está no perfil
**HFP/Hands-Free** (`Headset (...)`), que é 8–16 kHz mono. Pior: o Windows
costuma marcar o mic fantasma do A2DP como *Dispositivo Padrão* e o HFP só como
*Dispositivo de Comunicação Padrão*. Escolha o `Headset (...)` na aba Microfone.
E o perfil HFP some da lista quando nenhum app o está usando — não estranhe.

**"Microfone indisponível: Unanticipated host error [PaErrorCode -9999]"** — o
microfone salvo não existe mais naquela posição. Acontecia porque o `config.json`
guardava o *índice* do PortAudio, e esse índice anda sozinho: basta um fone
Bluetooth conectar para o número apontar para outro aparelho — às vezes uma
*saída* de áudio, que tem zero canais de entrada. Hoje a config guarda o nome do
microfone e, se ele não estiver conectado, o VozFlow grava pelo padrão do Windows
e avisa na janela flutuante em vez de falhar.

---

## Estrutura

```
main.py                  entrada (instância única + bandeja)
vozflow/config.py        configuração em JSON
vozflow/audio.py         captura do microfone + VAD (WebRTC)
vozflow/transcriber.py   motor faster-whisper em thread própria
vozflow/overlay.py       janela flutuante que não rouba foco
vozflow/inserter.py      colar / digitar / clipboard / webhook
vozflow/texto.py         rede de segurança contra loop e eco do prompt
vozflow/calibracao.py    mede sua voz contra o ambiente
vozflow/atalhos.py       captura e validação de combinações de teclas
vozflow/configuracoes.py  janela de configurações (4 abas)
vozflow/app.py           bandeja, atalhos globais e orquestração
vozflow/diagnostico.py   checagem de ambiente e download do modelo
```
