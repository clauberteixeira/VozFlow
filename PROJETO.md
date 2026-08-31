# VozFlow — visão geral do projeto

Ditado por voz **offline** para Windows. Você aperta uma tecla, fala, e o texto
vai sendo escrito no campo em foco enquanto você ainda está falando. Nada sai da
máquina: o modelo roda local, na sua GPU.

Versão atual: **1.1.0** · Projeto em `C:\Users\Clauber Regis\Desktop\a`

---

## Como funciona por dentro

O caminho de uma frase falada até o texto colado:

```
microfone ──> Recorder ──> VAD ──> buffer do trecho ──> Whisper ──> limpeza ──> entrega
 16 kHz      blocos de     detecta   fecha no          faster-      anti-       cola no
 mono        100 ms        fala      silêncio          whisper      alucinação  campo
```

O detalhe que dá a sensação de tempo real está no meio: **enquanto um trecho
está aberto, ele é retranscrito inteiro a cada `partial_interval` segundos**
(0,45 s por padrão) e o resultado vai para a janela flutuante como texto
provisório. Quando o silêncio fecha o trecho — `silence_ms`, 700 ms — ele é
transcrito uma última vez e vira texto definitivo, escrito no campo em foco.

Retranscrever o trecho inteiro, em vez de só o pedaço novo, é o que faz o texto
sair liso: o Whisper corrige o que ele mesmo escreveu antes conforme o contexto
cresce. O custo é reprocessar áudio já visto, e é por isso que `max_segment_s`
(20 s) fecha o trecho à força — sem esse teto, cada retranscrição ficaria
progressivamente mais cara.

**A detecção de fala (VAD)** usa o WebRTC quando disponível, com queda para um
limiar de energia com piso de ruído adaptativo. Além dele há dois cortes por
nível, calibráveis: `nivel_minimo` (abaixo disso o áudio nem vai ao modelo) e
`nivel_fala` (abaixo disso é som de fundo, não você). Esses números dependem do
microfone e de quão perto você fala — a tela de configurações tem um
**"Calibrar com a minha voz"** que mede o ambiente e a sua voz e escolhe o
limiar entre os dois, em vez de você chutar.

**A limpeza** (`texto.py`) é a última linha de defesa antes de colar, contra as
duas falhas clássicas do Whisper: o loop de repetição (o decoder trava e repete
a mesma palavra centenas de vezes) e o eco do prompt (com áudio curto ou baixo
ele transcreve o próprio `initial_prompt` como se fosse fala).

---

## Stack

| Camada | O que usa |
|---|---|
| Transcrição | `faster-whisper` (CTranslate2), modelo `large-v3-turbo` |
| Aceleração | CUDA float16 numa RTX 4060 — cai para CPU sozinho se faltar |
| Áudio | `sounddevice` (PortAudio) + `webrtcvad` |
| Interface | PySide6 — ícone na bandeja, janela flutuante sem foco |
| Teclado | `keyboard` (ganchos globais de baixo nível) |
| Entrega | `pyperclip` + `keyboard.write` + `requests` (webhook) |
| Empacotamento | PyInstaller (`VozFlow.spec`) + Inno Setup (`instalador.iss`) |

Python 3.12. Dependências em `requirements.txt`; as de GPU em
`requirements-gpu.txt`.

---

## Estrutura

| Arquivo | Linhas | Papel |
|---|---|---|
| `main.py` | 57 | Ponto de entrada. Mutex de instância única, checa a bandeja |
| `vozflow/app.py` | 672 | Bandeja, atalhos globais, orquestração, sons |
| `vozflow/transcriber.py` | 458 | Motor: thread própria, trechos, parciais, Whisper |
| `vozflow/configuracoes.py` | 451 | Janela única de ajustes, com medidor ao vivo |
| `vozflow/audio.py` | 274 | Captura, VAD, resolução do microfone |
| `vozflow/atalhos.py` | 222 | Captura e validação de combinações de teclas |
| `vozflow/overlay.py` | 190 | Janela flutuante que nunca rouba o foco |
| `vozflow/calibracao.py` | 172 | Mede ambiente e voz, calcula o limiar |
| `vozflow/modelo.py` | 138 | Download do modelo com progresso visível |
| `vozflow/config.py` | 128 | `config.json`, padrões e migrações |
| `vozflow/inserter.py` | 117 | Colar, digitar, copiar ou mandar por webhook |
| `vozflow/janela.py` | 130 | Prende a escrita na janela onde a ditada começou |
| `vozflow/texto.py` | 82 | Anti-repetição e anti-eco do prompt |
| `vozflow/diagnostico.py` | 64 | `python -m vozflow.diagnostico` |

**Onde ficam os dados:**

- `%APPDATA%\VozFlow\config.json` — toda a configuração
- `%APPDATA%\VozFlow\transcricoes.txt` — histórico do que foi ditado
- `%USERPROFILE%\.cache\huggingface` — o modelo, 1,6 GB, baixado uma vez só
- `%LOCALAPPDATA%\Programs\VozFlow\` — o app instalado
- `%APPDATA%\...\Startup\VozFlow.vbs` — o que faz iniciar com o Windows

---

## Rodar do fonte

```bat
instalar.bat                          :: cria a .venv e instala tudo
.venv\Scripts\pythonw.exe main.py     :: sem console
VozFlow-debug.bat                     :: com console, para ver erros
```

## Gerar o executável e o instalador

```bat
gerar-exe.bat            :: com GPU  (~1,0 GB)  -> dist\VozFlow\
gerar-exe.bat cpu        :: só CPU   (~260 MB)
gerar-instalador.bat     :: -> instalador\VozFlow-1.1.0-instalador.exe
```

Sem o corte de gordura documentado no `VozFlow.spec`, o pacote sairia com
2,3 GB. O maior recorte é o cuDNN inteiro (1.011 MB): o `ctranslate2` não o usa
no caminho do Whisper — medido, texto idêntico e mesma velocidade sem ele.

**Ao publicar uma correção:** os módulos Python ficam no PYZ *dentro* do
`VozFlow.exe`, então quando só o código Python muda, o `_internal\` (587
arquivos, ~1 GB) fica idêntico e basta trocar o `.exe`. E regere o instalador,
senão uma reinstalação traz os bugs de volta.

---

## Decisões que não são óbvias no código

Cada uma destas custou uma sessão de depuração:

- **`PgDn` e `Num 3` são o mesmo scancode (81).** Só o flag de tecla estendida
  separa, e a lib `keyboard` casa atalho olhando só o scancode. Escolher `PgDn`
  fazia o app ligar ao digitar números no teclado numérico. A `GuardaNumerico`
  lê o `is_keypad` do evento. Vale para o bloco todo: `End`/`Num 1`,
  `Delete`/`Num .`, `Enter`, setas.

- **O índice de dispositivo do PortAudio não é estável.** A lista renumera
  sozinha quando um aparelho entra ou sai, e o índice salvo passa a apontar
  para outro — às vezes uma *saída*, com zero canais de entrada, e a gravação
  morre com `PaErrorCode -9999`. A config guarda o **nome**.

- **O PortAudio não atualiza a lista sozinho.** Ela é montada no
  `Pa_Initialize` e só muda com `_terminate()` + `_initialize()`. Como o app
  sobe com o Windows e o fone Bluetooth é ligado depois, sem isso o microfone
  salvo não existia para o processo.

- **Fone Bluetooth expõe dois perfis.** O **A2DP** é estéreo mas *só reproduz*:
  o endpoint de microfone que ele mostra nunca captura nada. O microfone real
  está no **HFP/Hands-Free**, 8–16 kHz mono, e some da lista quando nenhum app
  o segura. Pior: o Windows costuma marcar o mic fantasma do A2DP como
  *Dispositivo Padrão*.

- **Aparelho Bluetooth desligado não some do Windows.** Fica na lista como
  "OK", sem mute e com volume 100%, entregando silêncio digital em vez de erro.
  Todo diagnóstico de software dá "tudo certo". O sinal denuncia: rms constante,
  linha morta — um mic vivo com ganho baixo ainda oscila.

- **`winsound.Beep` gera onda quadrada** pelo emulador do alto-falante do PC, e
  liga e desliga na amplitude cheia: áspero e com estalo nas pontas, que por
  Bluetooth vira chiado. Trocado por senoide com envelope. E o toque de
  "iniciar" termina *antes* de o microfone abrir, porque a troca A2DP→HFP corta
  qualquer som tocando.

- **Não dá para escrever numa janela Chromium em segundo plano.** Medido contra
  uma página de teste no Chrome, com o foco em outra janela: `PostMessage
  WM_CHAR`, `SendMessage WM_CHAR`, `KEYDOWN`/`CHAR`/`KEYUP` e
  `AttachThreadInput` + `SetFocus` foram todos ignorados — e no último o
  caractere foi parar na janela que estava em foco. O Chromium recusa input
  sintético de outro processo, e nele `hwndFocus` é a própria janela de topo,
  com `hwndCaret` zero: o campo de texto é DOM, não existe controle Win32.
  Por isso `janela.py` segura o texto em vez de tentar escrever no fundo.

- **`SetForegroundWindow` tem trava**: só quem já é o processo em primeiro
  plano ou recebeu o último evento de entrada consegue trazer uma janela para
  frente — e o VozFlow, de fundo, não é nenhum dos dois. `AttachThreadInput`
  contorna. E o retorno **precisa ser verificado**: digitar sem confirmar o
  foco, com "apertar Enter" ligado, manda a mensagem na janela errada.

- **Tocar em widget Qt fora da thread do Qt** derruba o processo com
  `STATUS_STACK_BUFFER_OVERRUN` (0xC0000409), sem traceback nenhum. É por isso
  que o worker de inserção avisa a interface por *sinal* (`sig_segurando`), e
  não mexendo no overlay direto.

- **`keyboard.send()` marca `is_replaying`** e o próprio listener descarta o
  evento — um processo não dispara os próprios atalhos. Testes precisam injetar
  via `keybd_event` do Win32.

- **`Alt+Shift` nunca chega ao app:** o Windows consome para trocar o idioma do
  teclado. A tela de configurações recusa essa combinação.

- **Config gravada com BOM** (Notepad, PowerShell) fazia o `json.loads` falhar
  e a configuração voltava aos padrões calada. Lê-se com `utf-8-sig`.

- **Testar com o microfone real é perigoso:** com inserção ao vivo + Enter, um
  teste captou voz da sala, colou no terminal e enviou a mensagem. Testes
  precisam de um `Recorder` falso.

---

Detalhes de uso, tabela completa de configuração e solução de problemas estão
no [README.md](README.md).
