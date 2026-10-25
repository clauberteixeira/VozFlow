# Configuração

Tudo que o VozFlow ajusta fica em um único arquivo:

```
%APPDATA%\VozFlow\config.json
```

Você pode editar pela **janela de configurações** (botão direito na bandeja →
Configurações...) ou abrir o arquivo cru — a própria janela tem um botão que
abre ele no editor padrão.

**Editou pela janela?** Vale na hora. Só a troca de modelo pede reiniciar.
**Editou o arquivo à mão?** Feche e abra o VozFlow.

> O arquivo é lido como `utf-8-sig` de propósito: o Notepad e o PowerShell
> gravam UTF-8 com BOM, e o BOM fazia o `json.loads` falhar — a configuração
> voltava aos padrões calada. Se o JSON estiver mesmo corrompido (ou não for
> um objeto `{...}`), o arquivo é preservado com sufixo `.bak` em vez de
> sobrescrito.
>
> Um valor com o tipo errado — `"silence_ms": "700"` (texto onde vai número),
> `"sounds": "sim"` (texto onde vai `true`/`false`) — volta ao padrão **só
> naquela chave**; o resto do arquivo vale. Antes, um valor assim fazia o app
> não abrir ou parar de transcrever sem aviso. O arquivo só é regravado quando
> falta alguma chave ou algo foi corrigido, sempre por arquivo temporário, para
> uma queda de energia nunca deixar um JSON pela metade.

---

## Atalhos

| Chave | Padrão | Para que serve |
|---|---|---|
| `hotkey_start` | `ctrl+alt+g` | Começa a ditar. |
| `hotkey_stop` | `ctrl+alt+s` | Encerra e entrega o texto. Use o **mesmo** valor de `hotkey_start` para virar um atalho único que alterna. |
| `hotkey_cancel` | `ctrl+alt+x` | Cancela. O que já foi escrito continua no campo; o resto é descartado. |
| `suppress_hotkeys` | `false` | `true` reserva a tecla para o VozFlow — ela para de fazer a função normal no app em foco. |
| `hotkey_start2` | `""` | Segundo par de atalhos: começar. |
| `hotkey_stop2` | `""` | Segundo par de atalhos: encerrar. |
| `press_enter_after2` | `false` | Regra de Enter **própria** do segundo par. É assim que se tem uma tecla que só escreve e outra que escreve e já envia. |

A sintaxe das combinações é a da biblioteca
[`keyboard`](https://github.com/boppreh/keyboard): `ctrl+alt+g`, `f9`,
`scroll lock`, `pause`.

---

## Modelo de transcrição

| Chave | Padrão | Para que serve |
|---|---|---|
| `model` | `auto` | `auto` escolhe pela máquina: `large-v3-turbo` com placa NVIDIA, `base` sem GPU. Ou fixe um: `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`. Menor = mais rápido e menos preciso. |
| `language` | `pt` | Idioma da fala. Deixe `""` (vazio) para detecção automática — custa um pouco mais. |
| `device` | `auto` | `auto`, `cuda` ou `cpu`. Force `cpu` se quiser poupar a GPU para outra coisa. |
| `compute_type` | `auto` | `auto`, `float16`, `int8_float16` ou `int8`. |
| `initial_prompt` | `""` | Vocabulário para o modelo acertar nomes próprios, jargões e siglas do seu contexto. **Só lista de termos, nunca prosa** — veja [Uso](USO.md#melhorando-o-reconhecimento). |

### Escolhendo o modelo

| modelo | tamanho | quando faz sentido |
|---|---|---|
| `tiny` / `base` | 75 MB / 145 MB | sem GPU; `base` é o que o `auto` usa na CPU (~1 s por prévia) |
| `small` | 464 MB | CPU forte, querendo mais precisão (~3 s por prévia) |
| `medium` | 1,5 GB | qualidade boa, GPU modesta |
| `large-v3` | 3,1 GB | máxima qualidade, mais lento |
| **`large-v3-turbo`** | **1,6 GB** | o que o `auto` usa **com GPU**: qualidade do large a uma fração do custo. Na CPU leva 12–14 s por prévia — inutilizável ao vivo |

Configurações antigas que tinham `large-v3-turbo` só por ser o padrão da 1.1.1
viram `auto` sozinhas (com GPU continua o mesmo modelo). Uma escolha feita
depois disso é respeitada.

Trocar de modelo dispara um novo download na primeira execução. Todos ficam em
`%USERPROFILE%\.cache\huggingface` e são compartilhados entre versões do app.

---

## Captura de áudio

| Chave | Padrão | Para que serve |
|---|---|---|
| `input_device` | `null` | **Nome** do microfone (`null` = padrão do Windows). |
| `partial_interval` | `0.45` | Intervalo **mínimo** entre as retranscrições do trecho aberto. Menor = texto aparece mais rápido e a GPU trabalha mais. Se a máquina leva mais que isso para retranscrever (CPU, GPU ocupada), o intervalo cresce sozinho para 1,25× o tempo da última prévia, até 2 s. |
| `silence_ms` | `700` | Silêncio que fecha um trecho. Aumente se você fala com pausas longas. |
| `nivel_minimo` | `0.004` | RMS abaixo disso conta como mudo e o áudio nem vai ao modelo. Aumente se ainda aparecer texto fantasma; diminua se você fala muito baixo. |
| `nivel_fala` | `0.010` | Abaixo deste nível o som é tratado como fundo e não vira texto. Use **Calibrar com a minha voz** em vez de chutar. `0` desliga o corte. |
| `max_segment_s` | `20.0` | Trecho máximo antes de fechar à força. Existe porque cada retranscrição reprocessa o trecho inteiro — sem teto, ficaria progressivamente mais cara. |

> **Por que o nome do microfone e não o índice.** O PortAudio renumera a lista
> inteira quando um fone Bluetooth conecta ou o NVIDIA Broadcast liga, e o
> índice salvo passa a apontar para outro aparelho — às vezes uma *saída* de
> áudio, com zero canais de entrada, e a gravação morre com
> `PaErrorCode -9999`. Configs antigas que guardavam número são convertidas
> sozinhas na primeira abertura.

---

## Entrega do texto

| Chave | Padrão | Para que serve |
|---|---|---|
| `action_on_stop` | `paste` | `paste`, `type`, `clipboard` ou `webhook`. |
| `insercao_ao_vivo` | `true` | Escreve cada trecho no campo em foco durante a fala. `false` = só entrega tudo no fim. |
| `press_enter_after` | `false` | Aperta Enter depois de entregar — envia a mensagem no WhatsApp, no chat, ou submete o formulário. |
| `webhook_url` | `""` | Para `action_on_stop: "webhook"`. |
| `webhook_field` | `texto` | Nome do campo no JSON enviado: `{"texto": "..."}`. |
| `travar_janela` | `true` | Prende a escrita na janela onde a ditada começou. Trocando de janela no meio da fala, o texto **espera** em vez de vazar. |

### As quatro ações

- **`paste`** — copia e manda `Ctrl+V`. O clipboard anterior é restaurado
  depois. É o padrão porque funciona em praticamente tudo.
- **`type`** — digita tecla a tecla com `keyboard.write`. Para apps que
  bloqueiam colagem.
- **`clipboard`** — só copia; você cola onde quiser.
- **`webhook`** — `POST` com `{"<webhook_field>": "<texto>"}`, timeout de 15 s.

---

## Interface

| Chave | Padrão | Para que serve |
|---|---|---|
| `show_overlay` | `true` | Mostra a janelinha flutuante durante a ditada. |
| `overlay_posicao` | `inferior-centro` | Uma das sete posições da tabela abaixo. |
| `overlay_offset_y` | `90` | Distância, em pixels, da borda de cima ou de baixo. |
| `overlay_width` | `760` | Largura da janelinha, em pixels. |
| `sounds` | `true` | Toques de início, fim e cancelamento. |
| `log_transcricoes` | `true` | Grava tudo em `%APPDATA%\VozFlow\transcricoes.txt`. |
| `historico_max_mb` | `5` | Enquanto o histórico tiver menos que isso, **nada é apagado** (5 MB são anos de ditado). Passou, ele fica só com os últimos `historico_dias`. `0` desliga a limpeza. |
| `historico_dias` | `7` | Quantos dias o histórico mantém quando passa de `historico_max_mb`. |

Posições aceitas em `overlay_posicao`:

| valor | onde aparece |
|---|---|
| `inferior-centro` | rodapé, centralizado *(padrão)* |
| `inferior-esquerda` | rodapé, à esquerda |
| `inferior-direita` | rodapé, à direita |
| `superior-centro` | topo, centralizado |
| `superior-esquerda` | topo, à esquerda |
| `superior-direita` | topo, à direita |
| `centro` | centro da tela |

> **Sobre os sons:** são senoides curtas geradas em memória, não
> `winsound.Beep`. O `Beep` gera onda *quadrada* pelo emulador do alto-falante
> do PC — áspera, e como liga e desliga na amplitude cheia, estala nas duas
> pontas; num fone Bluetooth virava chiado. Com envelope de 6 ms de ataque e
> queda longa, o sinal parte do zero e volta ao zero. O toque de "iniciar"
> ainda *termina* antes de o microfone abrir, porque o fone Bluetooth troca de
> A2DP para HFP nesse instante e a troca corta o som pela metade.

---

## Exemplo completo

Um `config.json` de quem usa headset Bluetooth, dita muito no WhatsApp e tem
vocabulário técnico próprio:

```json
{
  "hotkey_start": "ctrl+alt+g",
  "hotkey_stop": "ctrl+alt+s",
  "hotkey_cancel": "ctrl+alt+x",
  "hotkey_start2": "ctrl+alt+d",
  "hotkey_stop2": "ctrl+alt+f",
  "press_enter_after2": true,

  "model": "auto",
  "language": "pt",
  "initial_prompt": "Versaty Solar, ConnectaLink, Evolution API, Laravel, kWp, boleto, CRM.",

  "input_device": "Headset (Meu Fone BT)",
  "nivel_fala": 0.018,
  "partial_interval": 0.45,

  "action_on_stop": "paste",
  "insercao_ao_vivo": true,
  "press_enter_after": false,
  "travar_janela": true,

  "overlay_posicao": "inferior-centro",
  "sounds": true,
  "log_transcricoes": true
}
```

O segundo par de atalhos aqui (`Ctrl+Alt+D` / `Ctrl+Alt+F`) tem
`press_enter_after2: true`: dita e **já envia**. O primeiro par escreve e
deixa você revisar antes.

---

## Variável de ambiente

| Variável | Para que serve |
|---|---|
| `VOZFLOW_CONFIG_DIR` | Muda a pasta de configuração. Existe para os testes: sem ela, cada teste que abre a tela de configurações gravava por cima da configuração real de quem usa o app. |
| `VOZFLOW_DEBUG` | `1` grava em `%TEMP%\vozflow-debug.txt` o que acontece com a janela alvo e a entrega — só **tamanhos**, nunca o texto ditado nem títulos de janela. `texto` grava também o conteúdo, para comparar com o histórico; apague o arquivo depois. |
| `HF_HUB_DISABLE_XET` | Definida como `1` pelo próprio VozFlow, antes de qualquer import do `huggingface_hub`. Veja [Decisões técnicas](DECISOES-TECNICAS.md). |
