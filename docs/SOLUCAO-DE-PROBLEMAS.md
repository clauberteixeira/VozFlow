# Solução de problemas

Antes de qualquer coisa, rode o diagnóstico:

```bat
.venv\Scripts\python.exe -m vozflow.diagnostico
```

Ele lista os microfones disponíveis, confirma se a GPU está sendo usada e
valida o modelo. Metade dos problemas se resolve com a informação que ele
imprime.

---

## Áudio e microfone

### O VozFlow não capta a minha voz

Abra **Configurações → Microfone**. Tem um **medidor de nível ao vivo** ali:
fale e veja se a barra se mexe.

- **A barra não se mexe** → microfone errado selecionado, ou o aparelho está
  mudo no Windows. Veja os casos de Bluetooth abaixo.
- **A barra se mexe mas nada é transcrito** → o `nivel_fala` está alto demais
  para a sua voz. Rode **Calibrar com a minha voz**.

Depois de ~3 s ouvindo som fraco demais, o VozFlow escreve na janelinha:
*"Não estou captando sua voz — o som está fraco demais."* Ele avisa em vez de
emudecer calado.

### Liguei o fone depois do VozFlow e ele não acha o microfone

**Resolvido**, mas vale saber por quê: o PortAudio monta a lista de
dispositivos uma única vez, no `Pa_Initialize`, e não a atualiza sozinha. Como
o VozFlow sobe junto com o Windows e um fone Bluetooth costuma ser ligado
depois, o aparelho salvo simplesmente não existia para o processo — e a
gravação caía no padrão do Windows, muda, sem erro nenhum.

Hoje o `Recorder` reinicia o PortAudio quando não encontra o microfone salvo
(só com nenhum stream aberto: reiniciar com um stream vivo derruba o processo).

### Fone Bluetooth: o microfone "existe" mas nunca grava

Um fone Bluetooth aparece no Windows como **dois perfis**:

| perfil | como aparece | o que faz |
|---|---|---|
| **A2DP** | `Fones de ouvido (...)` | estéreo, alta qualidade, **só reproduz** — o endpoint de microfone que ele expõe nunca captura nada, por definição |
| **HFP / Hands-Free** | `Headset (...)` | 8–16 kHz mono, é onde está o **microfone real** |

Pior: o Windows costuma marcar o mic fantasma do A2DP como *Dispositivo
Padrão* e o HFP só como *Dispositivo de Comunicação Padrão*.

**Escolha o `Headset (...)`** na aba Microfone. E não estranhe: o perfil HFP
some da lista quando nenhum app o está usando.

### "Microfone indisponível: Unanticipated host error [PaErrorCode -9999]"

O microfone salvo não existe mais naquela posição.

Isso acontecia porque o `config.json` guardava o *índice* do PortAudio, e esse
índice anda sozinho: basta um fone Bluetooth conectar para o número apontar
para outro aparelho — às vezes uma *saída* de áudio, que tem zero canais de
entrada.

Hoje a config guarda o **nome** do microfone e, se ele não estiver conectado, o
VozFlow grava pelo padrão do Windows e avisa na janela flutuante em vez de
falhar. Configs antigas com número são convertidas sozinhas na primeira
abertura.

### O aparelho aparece "OK" mas só entrega silêncio

Aparelho Bluetooth **desligado não some do Windows**. Fica na lista como "OK",
sem mute e com volume 100%, entregando silêncio digital em vez de erro. Todo
diagnóstico de software dá "tudo certo".

O sinal denuncia: **rms constante, linha morta**. Um microfone vivo com ganho
baixo ainda *oscila* quando alguém fala. Se o medidor de nível mostrar uma
linha perfeitamente reta, o aparelho está desligado — religue ou escolha
outro.

---

## Atalhos

### O atalho não responde

Três causas, nesta ordem de probabilidade:

1. **Outro programa já registrou a mesma combinação.** Troque em
   Configurações → Atalhos.
2. **O app em foco roda como administrador.** Aí o VozFlow também precisa
   rodar como administrador para enxergar o teclado dele.
3. **Você escolheu `Alt+Shift`.** O Windows consome essa combinação para trocar
   o idioma do teclado e ela nunca chega ao app — a tela de configurações
   recusa essa escolha justamente por isso.

### O VozFlow liga sozinho quando eu rolo a página

Você escolheu uma tecla de navegação sozinha (`PgDn`, `PgUp`, `Home`, `End`,
seta) como atalho. Você aperta essas o tempo todo. Escolha uma combinação com
modificador.

A janela de configurações avisa sobre isso ao salvar.

### O VozFlow liga quando eu digito no teclado numérico

**Resolvido.** `PgDn` e `Num 3` chegam ao Windows com o *mesmo* scancode (81) —
o que separa as duas é o flag de tecla estendida, e a biblioteca `keyboard`
casa atalho olhando só o scancode.

O app lê o `is_keypad` do evento e ignora a tecla do numérico. Vale para o
bloco inteiro: `End`/`Num 1`, `Delete`/`Num .`, `Enter`/`Num Enter` e as setas.
Mesmo com "Reservar a tecla" ligado, o `Num 3` continua digitando `3`.

### No teclado ABNT2 o atalho conflita com um caractere

O `AltGr` é lido pelo Windows como `Ctrl+Alt`. As teclas `G`, `S` e `X` dos
atalhos padrão não têm caractere em `AltGr`, então não há conflito — mas se
você trocar, evite `AltGr+Q`, `W`, `C`, `1`, `2`, `3`, `4`, `5`, `6`.

---

## O texto

### O texto foi parar na janela errada

**Resolvido** pelo `travar_janela` (ligado por padrão): o VozFlow guarda a
janela onde você apertou a tecla e, se o foco sair dela, **segura o texto** em
vez de deixá-lo vazar. A janelinha avisa (*"Texto segurado — volte para ..."*)
e você continua acompanhando a transcrição por ela. Ao encerrar, o app traz a
janela original de volta e entrega tudo de uma vez.

Se a janela original não voltar ao foco na hora de entregar (o Windows pode
recusar), o VozFlow **não digita às cegas**: copia o texto e avisa.

Por que ele não escreve direto na janela de fundo, já que ela é conhecida:
não dá — veja
[Decisões técnicas](DECISOES-TECNICAS.md#não-dá-para-escrever-numa-janela-chromium-em-segundo-plano).

### O texto sai truncado ou repetido

Aumente `silence_ms` se você faz pausas longas no meio das frases. O padrão de
700 ms fecha o trecho rápido demais para quem fala pausadamente.

### Aparece texto que eu não falei

É alucinação do Whisper em silêncio ou eco do `initial_prompt`. Três coisas a
fazer:

1. Aumente `nivel_minimo` um pouco (padrão `0.004`) — áudio abaixo disso nem
   chega ao modelo.
2. Verifique o `initial_prompt`: **só lista de termos, nunca prosa**. Um prompt
   que começava com *"Anotações de trabalho em português do Brasil."* fez uma
   ditada sair como *"Teste 1, 2, 3. Anotações de trabalho."*
3. Rode **Calibrar com a minha voz** para ajustar os cortes ao seu microfone.

### O texto aparece em blocos, saltando

Verifique se **"Escrever no campo enquanto eu falo"** está ligado em
Configurações → Escrita. Com `insercao_ao_vivo` desligado, o texto só é
entregue no fim, de uma vez — que é o comportamento esperado nesse modo.

### O app cola no lugar do meu conteúdo copiado

Ele restaura o clipboard anterior 0,8 s depois de colar. Se o seu app de
destino demora mais que isso para ler a área de transferência, use
`action_on_stop: "type"` — que digita tecla a tecla e não toca no clipboard.

---

## GPU e desempenho

### "Library cublas64_12.dll is not found"

Falta o CUDA:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
```

Sem isso o app **cai para CPU sozinho** — funciona, só fica mais lento.

### Está usando CPU e eu tenho placa NVIDIA

Rode o diagnóstico, que informa qual dispositivo foi escolhido. Se ele
insistir na CPU:

- confirme o `requirements-gpu.txt` instalado;
- force `"device": "cuda"` e `"compute_type": "float16"` no `config.json`;
- confira se o driver da NVIDIA suporta CUDA 12.

### Está muito lento

| o que mexer | efeito |
|---|---|
| `model` para `medium` ou `small` | transcrição mais rápida, precisão menor |
| `partial_interval` para `0.6`–`0.8` | menos retranscrições, GPU mais folgada |
| `compute_type` para `int8` | mais rápido na CPU |

---

## Instalação e modelo

### O app parece travado na primeira abertura

Está baixando o modelo (1,6 GB), uma vez só. A janelinha flutuante mostra o
progresso e um balão da bandeja avisa quando começa. Apertar o atalho durante o
download mostra o progresso, não uma mensagem genérica.

Se falhar, a mensagem diz **o que fazer**: sem internet, sem espaço em disco ou
repositório recusado.

### "O VozFlow já está rodando (veja o ícone na bandeja)"

Um mutex global impede duas cópias disputando os mesmos atalhos. Se não há
ícone na bandeja, um processo órfão ficou vivo: encerre `VozFlow.exe` (ou
`pythonw.exe`) pelo Gerenciador de Tarefas.

### "A bandeja do sistema não está disponível nesta sessão"

O VozFlow é um app de bandeja — sem ela ele não tem como funcionar. Acontece em
sessões remotas restritas ou com o Explorer derrubado. Reinicie o Explorer.

### Minhas configurações voltaram ao padrão sozinhas

Era um bug de arquivo com BOM: o Notepad e o PowerShell gravam UTF-8 com BOM, e
o BOM fazia o `json.loads` falhar em silêncio.

**Já corrigido** — o arquivo é lido como `utf-8-sig`. E se o JSON estiver mesmo
corrompido, ele é preservado com sufixo `.json.bak` em vez de sobrescrito.

---

## Ainda não resolveu?

Abra uma [issue](../../issues) com:

- a saída completa de `python -m vozflow.diagnostico`;
- o seu `config.json` (tire o `webhook_url` se tiver algo sensível);
- o que você fez, o que esperava e o que aconteceu;
- se rodou pelo `VozFlow-debug.bat`, o texto do console.
