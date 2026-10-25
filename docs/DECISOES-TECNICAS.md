# Decisões técnicas

Cada item aqui custou uma sessão inteira de depuração. Nenhum deles é óbvio
lendo o código, e vários contrariam o que a documentação das bibliotecas dá a
entender. Estão registrados para que ninguém — inclusive o autor daqui a seis
meses — refaça o mesmo caminho.

---

## Teclado

### PgDn e Num 3 são o mesmo scancode (81)

Só o flag de **tecla estendida** separa os dois, e a biblioteca `keyboard` casa
atalho olhando **apenas o scancode**.

Consequência real: quem escolhia `PgDn` como atalho via o app ligar sozinho ao
digitar qualquer número no teclado numérico.

A solução foi ler o `is_keypad` do evento, numa guarda dedicada. Vale para o
bloco inteiro: `End`/`Num 1`, `Delete`/`Num .`, `Enter`/`Num Enter` e as setas.
Mesmo com "Reservar a tecla" ligado, o `Num 3` continua digitando `3`.

### Alt+Shift nunca chega ao app

O Windows consome essa combinação para trocar o idioma do teclado. Ela não
chega ao gancho de baixo nível, então um atalho `Alt+Shift` simplesmente nunca
dispararia. A tela de configurações **recusa** essa escolha em vez de deixar a
pessoa configurar algo que não vai funcionar.

### `keyboard.send()` marca `is_replaying`

O próprio listener descarta o evento — um processo não dispara os próprios
atalhos. Isso é útil (evita laço infinito), mas significa que **testes
automatizados precisam injetar via `keybd_event` do Win32**, não pela própria
biblioteca.

### Teclas de navegação sozinhas são armadilha

A primeira pessoa a usar o app escolheu `PgDn` e ele "ligava do nada" a cada
rolagem de página. A tela de configurações hoje avisa em três níveis:

| escolha | tratamento |
|---|---|
| combinação com modificador | passa sem aviso — é a escolha segura |
| tecla de navegação sozinha | aviso: você aperta essas o tempo todo |
| tecla de digitação sozinha | aviso mais forte: dispararia no meio de qualquer texto |
| `Pause`, `Scroll Lock`, mídia | seguras sozinhas, praticamente sem uso |

---

## Áudio

### O índice de dispositivo do PortAudio não é estável

A lista renumera sozinha quando qualquer aparelho entra ou sai. O índice salvo
passava a apontar para outro dispositivo — às vezes uma **saída** de áudio, com
zero canais de entrada — e a gravação morria com
`Unanticipated host error [PaErrorCode -9999]`.

Hoje a config guarda o **nome** do microfone. Configs antigas com número são
convertidas sozinhas na primeira abertura.

### O PortAudio não atualiza a lista sozinho

Ela é montada no `Pa_Initialize` e só muda com `_terminate()` +
`_initialize()`. Como o app sobe junto com o Windows e o fone Bluetooth
costuma ser ligado depois, o microfone salvo simplesmente **não existia** para
o processo — e a gravação caía no padrão do Windows, muda, sem erro nenhum.

O `Recorder` reinicia o PortAudio quando não encontra o microfone salvo. Só com
nenhum stream aberto: reiniciar com um stream vivo **derruba o processo**.

### Fone Bluetooth expõe dois perfis, e o Windows escolhe o errado

O perfil **A2DP** é estéreo mas **só reproduz**: o endpoint de microfone que
ele mostra nunca captura nada, por definição. O microfone real está no perfil
**HFP/Hands-Free** (8–16 kHz mono), que some da lista quando nenhum app o
segura.

Pior: o Windows costuma marcar o mic fantasma do A2DP como *Dispositivo
Padrão*, e o HFP só como *Dispositivo de Comunicação Padrão*.

### Aparelho Bluetooth desligado não some do Windows

Fica listado como "OK", sem mute, volume 100%, entregando **silêncio digital**
em vez de erro. Todo diagnóstico de software dá "tudo certo".

O que denuncia é a **forma do sinal**: rms constante, linha morta. Um microfone
vivo com ganho baixo ainda *oscila* quando alguém fala.

### `winsound.Beep` gera onda quadrada

Pelo emulador do alto-falante do PC, e liga/desliga na amplitude cheia: áspero
e com estalo nas duas pontas, que num fone Bluetooth virava chiado.

Trocado por **senoide sintetizada em memória com envelope** (6 ms de ataque,
queda longa): o sinal parte do zero e volta ao zero.

E o toque de "iniciar" termina **antes** de o microfone abrir, porque a troca
A2DP→HFP corta qualquer som que esteja tocando — o som saía pela metade.

---

## Escrita na janela de destino

### Não dá para escrever numa janela Chromium em segundo plano

Este foi o mais surpreendente. A ideia era continuar escrevendo no VS Code
mesmo com a pessoa noutra janela. Testado contra uma página de teste no Chrome,
com o foco fora:

| tentativa | resultado |
|---|---|
| `PostMessage WM_CHAR` | ignorado |
| `SendMessage WM_CHAR` | ignorado |
| `KEYDOWN` + `CHAR` + `KEYUP` | ignorado |
| `AttachThreadInput` + `SetFocus` | ignorado — e o caractere foi parar na janela que estava em foco |

O Chromium **recusa input sintético vindo de outro processo**, e nele nem
existe controle filho para receber a mensagem: `hwndFocus` é a própria janela
de topo e `hwndCaret` é zero, porque o campo de texto é um elemento DOM.

Como Chrome, Edge, VS Code, WhatsApp e Discord são **todos Chromium**, a
família inteira de soluções "escrever sem foco" está descartada.

**A saída foi outra:** guardar a janela onde a ditada começou e, se o foco sair
dela, **segurar** o texto em vez de deixá-lo vazar. No fim, trazer a janela de
volta e entregar tudo.

### `SetForegroundWindow` tem trava

Só quem já é o processo em primeiro plano, ou recebeu o último evento de
entrada, consegue trazer uma janela para frente — e o VozFlow, de fundo, não é
nenhum dos dois. `AttachThreadInput` contorna.

E o retorno **precisa ser verificado**: digitar sem confirmar o foco, com
"apertar Enter" ligado, mandaria a mensagem na janela errada. Quando o foco não
volta, o VozFlow copia o texto e avisa — não digita às cegas.

### Digitar em vez de colar, com cadência

Cada trecho ia por área de transferência + `Ctrl+V`: um salto atômico de várias
palavras, além de sujar o clipboard 16 vezes por ditada. A escrita ao vivo usa
`keyboard.write`, que digita caractere a caractere — e os acentos foram
testados antes da troca (`coração, licitação, orçamento, é, à, já, você` saem
perfeitos).

E as letras não saem de uma vez: vão para um buffer e saem a cada 25 ms, num
ritmo que espalha o buffer ao longo do intervalo em que a próxima leva costuma
chegar. **Sem a parte fracionária do crédito**, poucas letras saíam em 2 ou 3
ticks e o texto parava até a leva seguinte — o "engasgo no meio da frase".

Os números do antes e depois estão em
[Desempenho](DESEMPENHO.md#cadência-da-escrita-colar-vs-digitar).

---

## Transcrição

### O Whisper alucina de duas formas clássicas

1. **Loop de repetição:** o decoder trava e repete a mesma palavra centenas de
   vezes.
2. **Eco do prompt:** com áudio curto ou baixo, ele transcreve o próprio
   `initial_prompt` como se fosse fala.

São barradas em **três camadas**:

- **Portão de energia** — áudio abaixo de `nivel_minimo` (RMS) nem chega ao
  modelo. Sem isso, o silêncio vira frase inventada: uma gravação muda chegou a
  produzir *"Descender."* do nada. Ruído de sala fica na casa de `1e-5`; fala
  fica acima de `1e-2`, então a margem é de centenas de vezes.
- **Fallback de temperatura** — o `temperature` é uma **lista**, não `0.0`
  fixo. É isso que deixa o `compression_ratio_threshold` detectar saída
  degenerada e redecodificar. Com `0.0` fixo esse mecanismo fica **desligado**.
- **`vozflow/texto.py`** — última linha de defesa antes de entregar: colapsa
  n-gramas repetidos (mantendo repetição natural como "não, não") e remove
  trechos que são eco literal do `initial_prompt`.

### O texto já transcrito não é realimentado no prompt

`condition_on_previous_text=False`. Prender o decoder ao próprio resultado
anterior é justamente o que o faz travar repetindo.

### O `initial_prompt` só aceita lista de termos, nunca prosa

O Whisper trata o prompt como contexto **transcritível** e ecoa prosa na saída.
Um prompt que começava com *"Anotações de trabalho em português do Brasil."*
fez uma ditada sair como *"Teste 1, 2, 3. **Anotações de trabalho.**"*

O `texto.py` remove esse eco quando ele escapa, mas evitar a prosa resolve na
origem.

### A comparação de estabilidade ignora pontuação e acento

No algoritmo de prefixo estável, uma palavra só é escrita depois de aparecer
igual em duas transcrições seguidas. Sem normalizar, o Whisper trocar
`"Bom dia!"` por `"Bom dia,"` fazia a palavra "não bater" e custava uma rodada
inteira antes de qualquer texto aparecer.

Esse detalhe sozinho atrasava a primeira palavra em **0,86 s**.

### `partial_interval` desceu para 0,3 s (1.2.2)

Na 1.2.0 ele parou em 0,45 s: em 0,35 s a GPU passava ~80% do tempo
transcrevendo para economizar só 0,17 s. O ganho era pequeno porque a regra do
prefixo estável desperdiçava as transcrições — comparava o trecho desde o
início, e qualquer mudança na parte já escrita travava as palavras novas.

Com a comparação só do texto novo, cada transcrição a mais vira texto. Medido
3 vezes com uma leitura real de 25 s: a primeira palavra caiu de 2,1 s (0,45 s)
para 1,2 s (0,3 s), e o atraso típico de 2,9 s para 2,4 s (com as correções da
revisão: 1,6 s e 2,5 s). Em 0,2 s o ganho
some (2,24 s) e a GPU fica em 98%: parou em 0,3 s. Quem tinha 0,45 s gravado
só por ser o padrão passa para 0,3 s; valor escolhido à mão fica.

### O microfone é sempre o padrão do Windows (1.2.2)

A aba Microfone listava todo aparelho que o PortAudio enxerga — e ele mostra o
mesmo microfone uma vez por driver (MME, DirectSound, WASAPI, WDM-KS), mais
entradas virtuais ("Mapeador de som", "Driver de captura primário") e a
"Mixagem estéreo", que grava o som do próprio PC. Com o modo automático
seguindo o Windows a cada ditada, a lista só confundia. Agora a aba mostra o
microfone padrão (pelo nome do WASAPI: o do MME vem cortado em 31 letras) e um
botão para as configurações de som do Windows.

---

## Interface e processo

### Tocar em widget Qt fora da thread do Qt derruba o processo

Com `STATUS_STACK_BUFFER_OVERRUN` (0xC0000409), **sem traceback nenhum** — o
que torna o diagnóstico brutal.

Por isso a thread de inserção avisa a interface por **sinal**
(`sig_segurando`), nunca mexendo no overlay direto.

### A janela flutuante é pré-aquecida escondida

A primeira exibição de uma janela translúcida sempre-no-topo custa **~2,5 s** no
Qt — inicialização da composição do DWM, segurando a GIL.

Sem o pré-aquecimento na inicialização, esse atraso cairia no primeiro
`Ctrl+Alt+G` do usuário e comeria as primeiras palavras.

### Config gravada com BOM fazia tudo voltar ao padrão

O Notepad e o PowerShell gravam UTF-8 **com BOM**, e o BOM fazia o `json.loads`
falhar — a configuração voltava aos padrões **calada**.

Lê-se com `utf-8-sig`. E se o JSON estiver mesmo corrompido, o arquivo é
preservado com sufixo `.json.bak` em vez de sobrescrito: a config da pessoa não
se perde em silêncio.

### `VOZFLOW_CONFIG_DIR` existe por causa dos testes

Sem ela, cada teste que abre a tela de configurações gravava **por cima da
configuração real** de quem usa o app — foi assim que o atalho e o "apertar
Enter" do usuário voltaram sozinhos ao padrão no meio de uma bateria de testes.

### Testar com o microfone real é perigoso

Com inserção ao vivo + Enter, um teste captou voz da sala, colou no terminal e
**enviou a mensagem**. Testes precisam de um `Recorder` falso.

---

## Download e empacotamento

### O backend Xet deixa o progresso quase inútil

`vozflow/__init__.py` define `HF_HUB_DISABLE_XET=1` **antes de qualquer import
do `huggingface_hub`** — a biblioteca lê essa variável uma única vez, na
importação.

O Xet baixa em blocos grandes e só descarrega no cache de vez em quando.
Medido com o modelo `small` (464 MB):

| backend | degraus de progresso | tempo |
|---|---|---|
| Xet (padrão) | 4 | 13,4 s |
| clássico | **14** | **11,5 s** |

Com 1,6 GB, o Xet deixaria a pessoa olhando "14%" parado por minutos. E o
clássico ainda saiu mais rápido.

### O progresso é medido pelo tamanho da pasta de cache

E não pelo `tqdm` do `huggingface_hub`, porque assim funciona com qualquer
backend. O `faster_whisper.download_model` passa `tqdm_class=disabled_tqdm`: o
download acontece **sem nenhum sinal de vida** por padrão.

Na primeira instalação em outra máquina isso fez o app parecer travado — quem
apertava o atalho só via *"Ainda carregando o modelo, aguarde..."* por vários
minutos, sem saber se estava baixando, se tinha falhado ou se travou.

### O hook oficial do `webrtcvad` aborta o build

O hook do PyInstaller faz `copy_metadata('webrtcvad')`, mas o módulo aqui vem
da distribuição **`webrtcvad-wheels`** (a original não tem wheel para Python
3.12) e o nome não bate. `hooks/hook-webrtcvad.py` sobrepõe o oficial.

### O cuDNN inteiro é 1 GB de peso morto

`--collect-all nvidia` arrasta tudo que vem nas rodas do CUDA — o primeiro
pacote saiu com 2.306 MB. Medindo DLL por DLL, removendo cada uma e rodando uma
transcrição de verdade na GPU, a maior parte nunca é tocada.

Sem o cuDNN: **texto idêntico, ainda na GPU, `1.01x` de diferença de tempo**
(0,526 s contra 0,529 s em três medições). A tabela completa está em
[Empacotamento](EMPACOTAMENTO.md#o-que-o-vozflowspec-faz).

### O `_internal\` não muda quando só o Python muda

Os módulos Python ficam no PYZ **dentro** do `VozFlow.exe`. Quando só o código
Python muda, o `_internal\` (587 arquivos, ~1 GB) fica idêntico e basta trocar
o `.exe`.

Mas **regere o instalador mesmo assim** — senão uma reinstalação traz os bugs
de volta.
