# Guia de uso

O fluxo inteiro do VozFlow cabe em três passos: **clique no campo onde quer
escrever, aperte o atalho, fale.** O texto vai aparecendo ali enquanto você
ainda está falando.

---

## Atalhos

| Atalho | O que faz |
|---|---|
| `Ctrl + Alt + G` | Começa a ditar. O texto vai sendo escrito no campo em foco conforme você fala. |
| `Ctrl + Alt + S` | Encerra a ditada e escreve o que faltava do último trecho. |
| `Ctrl + Alt + X` | Cancela. O que já foi escrito no campo continua lá — o resto é descartado. |

Clicar no ícone da bandeja também alterna entre gravar e parar.

### Trocar os atalhos

Botão direito no ícone da bandeja → **Configurações... → aba Atalhos**. Clique
no campo, pressione a combinação que quiser e salve. Vale na hora, sem
reiniciar.

Regras que a janela valida para você:

- **Combinação com modificador** (`Ctrl`, `Alt`, `Shift`, `Win`) passa sem
  aviso. É a escolha segura.
- **Tecla de navegação sozinha** (`PgUp`, `PgDn`, `Home`, `End`, setas) recebe
  aviso: você aperta essas o tempo todo para rolar a página, e o VozFlow
  ligaria sozinho. Só vale se a tecla vier de um controle remoto que não serve
  para mais nada. *(Aprendido da forma difícil — a primeira pessoa a usar o app
  escolheu `PgDn` e ele "ligava do nada" a cada rolagem.)*
- **Tecla de digitação sozinha** (letra, número, espaço) recebe aviso mais
  forte: dispararia no meio de qualquer texto.
- Praticamente sem uso e portanto seguras sozinhas: `Pause`, `Scroll Lock`,
  teclas de mídia.
- Tecla sem modificador continua fazendo a função normal dela ao mesmo tempo.
  Marque **"Reservar a tecla para o VozFlow"** para o app consumir a tecla.
- `Alt + Shift` é recusado: o Windows consome essa combinação para trocar o
  idioma do teclado e ela nunca chega até o VozFlow.
- Usar a **mesma** combinação em iniciar e parar vira uma tecla única que
  alterna entre ditar e encerrar.
- **A gêmea do teclado numérico não dispara.** `PgDn` e `Num 3` chegam ao
  Windows com o *mesmo* scancode (81) — o que separa as duas é o flag de tecla
  estendida, e a biblioteca `keyboard` casa atalho olhando só o scancode.
  Resultado: quem escolhia `PgDn` via o VozFlow ligar ao digitar qualquer
  número no numérico. O app lê o `is_keypad` do evento e ignora a tecla do
  numérico. Vale para o bloco inteiro: `End`/`Num 1`, `Delete`/`Num .`,
  `Enter`/`Num Enter` e as setas. Mesmo com "Reservar a tecla" ligado, o
  `Num 3` continua digitando `3`.

> **Teclado ABNT2:** o `AltGr` é lido pelo Windows como `Ctrl+Alt`. As teclas
> `G`, `S` e `X` não têm caractere em `AltGr`, então não há conflito — mas se
> você trocar os atalhos, evite `AltGr+Q`, `W`, `C`, `1`, `2`, `3`, `4`, `5`,
> `6`.

### Dois pares de atalhos

Existe um **segundo par** (`hotkey_start2` / `hotkey_stop2`) com a *sua
própria* regra de Enter (`press_enter_after2`). Serve para ter uma tecla que
só escreve e outra que escreve **e já envia** — útil no WhatsApp: uma para
redigir com calma, outra para mandar a mensagem de uma vez.

---

## A janela flutuante

Enquanto você fala, uma janelinha translúcida mostra o que está sendo
entendido no momento, incluindo as palavras ainda provisórias. **Ela nunca
rouba o foco**, então o cursor continua no seu campo o tempo todo.

Ela também é onde o app fala com você: progresso do download do modelo, aviso
de microfone fraco, aviso de texto segurado.

Posição, largura e distância da borda são ajustáveis em Configurações → Geral.
São sete posições: rodapé/topo × centro/esquerda/direita, mais o centro da
tela.

---

## Como o texto vai aparecendo enquanto você fala

O problema de escrever ao vivo é que o Whisper muda de ideia: a transcrição de
"pre..." vira "preciso", que vira "preciso confirmar". Não dá para escrever
cada palpite e depois apagar.

A solução aqui é **prefixo estável**. O trecho aberto é retranscrito a cada
`partial_interval` segundos. Uma palavra nova que sobreviveu igual a duas
transcrições seguidas é considerada firme e vai para o campo; só a última
palavra da transcrição fica retida, porque ela ainda costuma mudar quando
chega mais áudio.
Nada é escrito duas vezes e nada precisa ser apagado.

Se preferir o comportamento antigo (nada aparece até você encerrar, aí cola
tudo de uma vez), desmarque **"Escrever no campo enquanto eu falo"** em
Configurações → Escrita.

Os números por trás disso estão em [Desempenho](DESEMPENHO.md).

---

## O texto fica na janela onde você começou

Com **"Manter o texto na janela onde comecei a ditar"** ligado (padrão), a
janela em foco no momento do atalho vira o destino. Se você troca de janela no
meio da fala, o texto **espera** e é entregue quando o foco volta — ou, no fim,
o VozFlow traz a janela de volta antes de escrever. Se ela não voltar, nada é
digitado às cegas: o texto inteiro vai para a área de transferência.

- **Começou pelo ícone ou pelo menu da bandeja?** Nesse instante o foco está na
  barra de tarefas, que não pode ser o destino. O texto espera até você clicar
  na janela onde ele deve entrar, e a trava fica nela.
- **Uma ditada por vez.** Logo depois de encerrar (ou cancelar), o VozFlow
  ainda está entregando o fim do texto. Um novo atalho nesse intervalo mostra
  *"Terminando de entregar a ditada anterior..."* e é ignorado — senão o fim da
  primeira iria para a janela da segunda, com a regra de Enter dela. Na GPU o
  intervalo é de frações de segundo.
- **Cancelar descarta na hora** o que ainda não tinha sido escrito, inclusive
  texto que estava esperando o foco voltar.
- **Limite:** a trava reconhece a *janela*, não a conversa dentro dela. No
  WhatsApp, Discord ou numa aba do navegador, trocar de conversa ou de aba no
  meio da ditada continua sendo a mesma janela — o resto do texto (e o Enter)
  vai para a conversa que estiver aberta.

---

## Só a sua voz, não a sala

O Whisper transcreve tudo que chega no áudio — ele não sabe quem está falando.
Separar por identidade de voz exigiria cadastrar a sua, o que é pesado. O que
o VozFlow usa é **proximidade**: quem fala no microfone chega muito mais forte
que uma conversa do outro lado da sala. Num headset de haste a diferença é de
10 a 50 vezes.

Som abaixo de `nivel_fala` não abre um trecho e não vira texto. Com histerese,
para uma sílaba fraca no meio da palavra não picotar a frase.

**Rode Configurações → Microfone → "Calibrar com a minha voz" uma vez.** Ele
mede o ambiente por 4 s, depois a sua voz por 4 s, e grava o limiar entre os
dois — mostrando quantas vezes a sua voz fica acima do corte. Sem calibrar, o
padrão `0.010` funciona para a maioria dos headsets, mas não é o número certo
para o seu.

Medido com uma conversa de fundo 15× mais fraca sobreposta à voz no microfone:

| cenário | resultado |
|---|---|
| só a conversa de fundo | nada transcrito |
| só a voz no microfone | transcrita completa |
| as duas misturadas | 4/4 palavras da voz de perto, **zero** palavras do fundo |

Se o limiar ficar alto demais para a sua voz, o app avisaria emudecendo — o
pior desfecho possível. Em vez disso, depois de ~3 s ouvindo som fraco demais
ele escreve na janelinha: *"Não estou captando sua voz — o som está fraco
demais."*

**Limite honesto:** isso é um corte por nível, não separação de vozes. Alguém
falando alto e perto do seu microfone passa. Para um filtro de verdade, se
você tem placa NVIDIA use o **NVIDIA Broadcast** — defina "Microfone (NVIDIA
Broadcast)" como microfone padrão do Windows (Configurações → Microfone →
**Trocar o microfone no Windows**) e ele aplica remoção de ruído e de vozes de
fundo por IA antes do áudio chegar aqui.

---

## Menu da bandeja

Só ações, nada de ajuste:

- **Começar a ditar / Encerrar e enviar / Cancelar** (com o atalho ao lado)
- **Configurações...**
- **Copiar última transcrição**
- **Abrir histórico de transcrições**
- **Sair**

Clicar no ícone alterna entre ditar e encerrar.

---

## Janela de configurações

Tudo que dá para ajustar está aqui, em quatro abas. Salvou, vale na hora — só
troca de modelo pede reiniciar.

**Atalhos** — as três teclas (começar, encerrar, cancelar) e a opção *Reservar
a tecla para o VozFlow*. Clique no campo e pressione a combinação. Usar a mesma
tecla em começar e encerrar vira um atalho único que alterna.

**Microfone** — o VozFlow usa sempre o **microfone padrão do Windows** e
mostra qual é; para trocar, o botão **Trocar o microfone no Windows** abre as
configurações de som. Tem também o **medidor de nível ao vivo** (você vê na
hora se o microfone está te captando) e o botão **Calibrar com a minha voz**,
que mede seu ambiente e sua voz e ajusta o corte de voz de fundo.

**Escrita** — para onde o texto vai (colar / digitar / só copiar / webhook),
escrever ao vivo enquanto fala, e apertar Enter ao encerrar.

**Geral** — modelo, idioma, vocabulário, janela flutuante, sons, iniciar com o
Windows, histórico, e um atalho para abrir o `config.json` cru.

A referência completa de cada opção está em [Configuração](CONFIGURACAO.md).

---

## Onde o texto pode ir parar

`action_on_stop` decide o destino do texto ao encerrar:

| valor | comportamento |
|---|---|
| `paste` *(padrão)* | cola na janela ativa via área de transferência (`Ctrl+V`) e devolve o conteúdo anterior ~0,8 s depois — a menos que você tenha copiado outra coisa nesse meio-tempo |
| `type` | digita tecla a tecla — para apps que bloqueiam colagem |
| `clipboard` | só copia; você cola onde quiser |
| `webhook` | manda `POST {"texto": "..."}` para a URL configurada; não depende de foco de janela |

Escrevendo ao vivo, o texto sai pelo teclado e a área de transferência não é
tocada. Se a entrega falhar (webhook fora do ar, janela que não voltou ao
foco), o texto é copiado e a mensagem de erro diz isso.

Com `press_enter_after` ligado, ele ainda aperta Enter — o que envia a
mensagem no WhatsApp, no chat, ou submete o formulário.

---

## Melhorando o reconhecimento

O jeito mais eficaz é preencher `initial_prompt` (Configurações → Geral →
Vocabulário) com os termos que você usa:

```json
"initial_prompt": "Versaty Solar, ConnectaLink, Evolution API, Laravel, kWp, boleto, CRM."
```

**Use só uma lista de termos, nunca uma frase em prosa.** O Whisper trata o
prompt como contexto transcritível e ecoa prosa na saída — um prompt que
começava com *"Anotações de trabalho em português do Brasil."* fez uma ditada
sair como *"Teste 1, 2, 3. **Anotações de trabalho.**"*. O `texto.py` remove
esse eco quando ele escapa, mas evitar a prosa resolve na origem.

---

## Histórico

Com `log_transcricoes` ligado (o padrão), tudo que você dita é gravado em
`%APPDATA%\VozFlow\transcricoes.txt`. O menu da bandeja tem **Abrir histórico
de transcrições**, que abre o arquivo direto.

O histórico guarda tudo enquanto for pequeno. Se passar de 5 MB (anos de
uso), ele passa a manter só a última semana. Os dois números estão em
`historico_max_mb` e `historico_dias`, na [Configuração](CONFIGURACAO.md).

Para desligar: Configurações → Geral → desmarque o histórico.
