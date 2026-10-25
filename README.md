<h1 align="center">VozFlow</h1>

<p align="center">
  <b>Ditado por voz offline para Windows, com atalho global.</b><br>
  Você clica no campo, aperta a tecla e fala — o texto vai sendo escrito ali,
  enquanto você ainda está falando.
</p>

<p align="center">
  <img alt="versão" src="https://img.shields.io/badge/vers%C3%A3o-1.2.1-2ea44f">
  <img alt="plataforma" src="https://img.shields.io/badge/plataforma-Windows%2010%2F11-0078d4">
  <img alt="python" src="https://img.shields.io/badge/python-3.12-3776ab">
  <img alt="offline" src="https://img.shields.io/badge/100%25-offline-8a2be2">
  <img alt="licença" src="https://img.shields.io/badge/licen%C3%A7a-MIT-lightgrey">
</p>

---

Bloco de notas, WhatsApp Web, VS Code, Gmail, campo de busca — tanto faz.
`Ctrl+Alt+G` começa, você fala, `Ctrl+Alt+S` encerra.

Uma janelinha flutuante mostra o que está sendo entendido no momento, incluindo
as palavras ainda provisórias. Ela **nunca rouba o foco**, então o cursor
continua no seu campo o tempo todo.

Roda **100% offline** na sua máquina (`faster-whisper` + GPU NVIDIA). Sem chave
de API, sem custo por minuto, sem mandar áudio para lugar nenhum.

```
        você fala                    o texto aparece no campo
            │                                   ▲
            ▼                                   │
  microfone ──> VAD ──> trecho ──> Whisper ──> limpeza
   16 kHz     detecta   fecha no   faster-      anti-
   mono        fala     silêncio   whisper    alucinação
```

---

## Índice

- [O que ele faz](#o-que-ele-faz)
- [Instalação](#instalação)
- [Atalhos](#atalhos)
- [Como o texto aparece enquanto você fala](#como-o-texto-aparece-enquanto-você-fala)
- [Só a sua voz, não a sala](#só-a-sua-voz-não-a-sala)
- [Configuração](#configuração)
- [Números](#números)
- [Documentação completa](#documentação-completa)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Licença](#licença)

---

## O que ele faz

| | |
|---|---|
| **Escrita ao vivo** | O texto entra no campo em foco enquanto você fala, sem precisar apagar nada depois |
| **100% offline** | O modelo roda na sua GPU. Nenhum áudio sai da máquina |
| **Atalho global** | Funciona em qualquer programa, sem integração nenhuma |
| **Dois pares de atalhos** | Uma tecla que só escreve, outra que escreve **e já envia** |
| **Trava de janela** | Trocou de janela no meio da fala? O texto espera, não vaza |
| **Janela flutuante** | Mostra a transcrição ao vivo sem tirar o foco do seu campo |
| **Calibração de microfone** | Mede o seu ambiente e a sua voz, e corta a conversa do fundo da sala |
| **Anti-alucinação** | Três camadas contra as duas falhas clássicas do Whisper |
| **Vocabulário próprio** | Nomes, siglas e jargão do seu contexto entram na transcrição |
| **Quatro destinos** | Colar, digitar tecla a tecla, só copiar, ou mandar por webhook |

---

## Instalação

### Usar

Baixe o instalador na página de [Releases](../../releases) e execute. Ele
**não pede administrador**, instala em `%LOCALAPPDATA%\Programs\VozFlow` e
aparece em Aplicativos Instalados do Windows.

Na primeira abertura, o modelo de transcrição (1,6 GB com GPU, ~145 MB sem) é baixado uma única vez,
com progresso visível na janelinha.

### Desenvolver

```bat
git clone https://github.com/clauberteixeira/VozFlow.git
cd VozFlow
instalar.bat

VozFlow.vbs          :: roda sem janela de console
VozFlow-debug.bat    :: roda com console, para ver os logs
```

O `instalar.bat` cria a `.venv`, instala as dependências, detecta a GPU NVIDIA
e baixa o modelo. O ícone de microfone aparece na bandeja, ao lado do relógio.

> **Sem placa NVIDIA?** Funciona: o app detecta a ausência e cai para CPU
> sozinho. Só fica mais lento.

Detalhes, requisitos e instalação manual em
**[docs/INSTALACAO.md](docs/INSTALACAO.md)**.

---

## Atalhos

| Atalho | O que faz |
|---|---|
| `Ctrl + Alt + G` | Começa a ditar. O texto vai sendo escrito no campo em foco. |
| `Ctrl + Alt + S` | Encerra e escreve o que faltava do último trecho. |
| `Ctrl + Alt + X` | Cancela. O que já foi escrito continua lá; o resto é descartado. |

Clicar no ícone da bandeja também alterna entre gravar e parar. Para trocar as
teclas: botão direito na bandeja → **Configurações... → Atalhos**.

A janela valida a sua escolha e avisa quando ela é arriscada — uma tecla de
navegação sozinha, por exemplo, ligaria o app toda vez que você rolasse a
página. *(Isso não é hipótese: a primeira pessoa a usar o app escolheu `PgDn` e
ele "ligava do nada".)*

Mais em **[docs/USO.md](docs/USO.md)**.

---

## Como o texto aparece enquanto você fala

O problema de escrever ao vivo é que o Whisper muda de ideia: "pre..." vira
"preciso", que vira "preciso confirmar". Não dá para escrever cada palpite e
depois apagar.

A solução é **prefixo estável**: o trecho aberto é retranscrito a cada 0,45 s,
e uma palavra só vai para o campo depois de aparecer **igual em duas
transcrições seguidas**. A última palavra firme fica retida, porque ela ainda
costuma mudar quando chega mais áudio. Nada é escrito duas vezes e nada precisa
ser apagado.

E o texto não sai em blocos: as letras saem em doses de 25 ms, num ritmo que
espalha cada rajada ao longo do intervalo até a próxima chegar. A diferença é
visível — 156 atualizações de tela contra 16, e **zero** engasgos acima de
0,7 s.

Os detalhes do algoritmo estão em
**[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

---

## Só a sua voz, não a sala

O Whisper transcreve tudo que chega no áudio — ele não sabe quem está falando.
O VozFlow usa **proximidade**: quem fala no microfone chega de 10 a 50 vezes
mais forte que uma conversa do outro lado da sala. Som abaixo do limiar não
abre trecho e não vira texto.

**Rode Configurações → Microfone → "Calibrar com a minha voz" uma vez.** Ele
mede o ambiente por 4 s, a sua voz por 4 s, e escolhe o limiar entre os dois.

Testado com uma conversa de fundo 15× mais fraca sobreposta à voz:

| cenário | resultado |
|---|---|
| só a conversa de fundo | nada transcrito |
| só a voz no microfone | transcrita completa |
| as duas misturadas | 4/4 palavras da voz de perto, **zero** do fundo |

**Limite honesto:** é corte por nível, não separação de vozes. Alguém falando
alto e perto do seu microfone passa.

**Novo: reconhecer só a sua voz.** Em Configurações → Microfone → *Só a minha
voz*, grave 25 s lendo um texto. A partir daí, quem conversa **nas suas pausas**
é silenciado antes de virar texto — mesmo perto do microfone, desde que mais
baixo que você. Duas vozes falando **ao mesmo tempo** não são separadas.
Desligado por padrão; a impressão da voz fica só no seu computador.

---

## Configuração

Tudo pela janela de configurações (botão direito na bandeja), em quatro abas:
**Atalhos**, **Microfone** (com medidor ao vivo e calibração), **Escrita** e
**Geral**. Salvou, vale na hora — só troca de modelo pede reiniciar.

Quem prefere mexer no arquivo: `%APPDATA%\VozFlow\config.json`. As chaves mais
usadas:

| Chave | Padrão | Para que serve |
|---|---|---|
| `model` | `auto` | `large-v3-turbo` com GPU, `base` sem GPU; ou fixe `tiny` … `large-v3` |
| `language` | `pt` | `""` para detecção automática |
| `initial_prompt` | `""` | Vocabulário do seu contexto. **Só lista de termos, nunca prosa** |
| `nivel_fala` | `0.010` | Abaixo disso é som de fundo. Use a calibração em vez de chutar |
| `partial_interval` | `0.45` | Segundos entre as retranscrições do trecho aberto |
| `silence_ms` | `700` | Silêncio que fecha um trecho |
| `insercao_ao_vivo` | `true` | `false` = só entrega tudo no fim |
| `action_on_stop` | `paste` | `paste`, `type`, `clipboard` ou `webhook` |
| `travar_janela` | `true` | Segura o texto se o foco sair da janela de origem |

A tabela completa, com todas as chaves e um exemplo comentado, está em
**[docs/CONFIGURACAO.md](docs/CONFIGURACAO.md)**.

---

## Números

Medidos numa RTX 4060 com `large-v3-turbo` em float16.

**Latência até a primeira palavra aparecer no campo:**

| versão | 1ª palavra | depois de você começar a falar |
|---|---|---|
| esperando o silêncio fechar a frase | 8,0 s | — |
| prefixo estável, `partial_interval` 0,6 s | 3,6 s | 2,7 s |
| + comparação sem pontuação | 2,7 s | 1,8 s |
| **+ `partial_interval` 0,45 s** | **2,4 s** | **1,5 s** |

**Cadência da escrita**, mesmo áudio de 20 s, amostrando o campo a cada 50 ms:

| | colando blocos | digitando cadenciado |
|---|---|---|
| atualizações visuais | 16 | **156** |
| maior engasgo | 2,4 s | **0,58 s** |
| engasgos acima de 0,7 s | 5 | **0** |

**Tamanho do pacote**, depois de medir DLL por DLL:

| | tamanho |
|---|---|
| primeiro build (`--collect-all nvidia`) | 2.306 MB |
| **com GPU, depois do corte** | **995 MB** |
| só CPU | 259 MB |

O maior recorte foi o **cuDNN inteiro, 1.011 MB**: o `ctranslate2` não o usa no
caminho do Whisper. Sem ele o resultado é idêntico — mesmo texto, ainda na GPU,
`1.01x` de diferença de tempo.

Tudo em **[docs/DESEMPENHO.md](docs/DESEMPENHO.md)**.

---

## Documentação completa

| Documento | Assunto |
|---|---|
| **[Instalação](docs/INSTALACAO.md)** | Requisitos, instalador, rodar do fonte, onde ficam os arquivos |
| **[Uso](docs/USO.md)** | Atalhos, bandeja, janela flutuante, calibração, vocabulário |
| **[Configuração](docs/CONFIGURACAO.md)** | Toda chave do `config.json`, com exemplo comentado |
| **[Arquitetura](docs/ARQUITETURA.md)** | Como o áudio vira texto: pipeline, threads, prefixo estável |
| **[Desempenho](docs/DESEMPENHO.md)** | Os números medidos, e o que ajustar na sua máquina |
| **[Empacotamento](docs/EMPACOTAMENTO.md)** | Gerar o `.exe` e o instalador, publicar uma versão |
| **[Solução de problemas](docs/SOLUCAO-DE-PROBLEMAS.md)** | Microfone, Bluetooth, atalhos, GPU, texto no lugar errado |
| **[Decisões técnicas](docs/DECISOES-TECNICAS.md)** | **Por que o código é assim.** Leia antes de mexer |
| [Histórico de versões](CHANGELOG.md) | O que mudou em cada versão |
| [Como contribuir](CONTRIBUTING.md) | Ambiente, testes, estilo, PRs |

> Se você vai mexer no código, **[Decisões técnicas](docs/DECISOES-TECNICAS.md)
> é a leitura obrigatória.** Cada item de lá custou uma sessão de depuração, e
> vários parecem "código estranho" até você saber o motivo — por que a config
> guarda o *nome* do microfone e não o índice, por que o app não consegue
> escrever numa janela Chromium em segundo plano, por que `PgDn` e `Num 3` são
> a mesma tecla para o Windows.

---

## Estrutura do projeto

```
main.py                     entrada (instância única + bandeja)
vozflow/
  app.py                    bandeja, atalhos globais, orquestração, sons
  transcriber.py            motor faster-whisper em thread própria
  audio.py                  captura do microfone + VAD (WebRTC)
  configuracoes.py          janela de configurações (4 abas)
  atalhos.py                captura e validação de combinações de teclas
  overlay.py                janela flutuante que não rouba foco
  calibracao.py             mede sua voz contra o ambiente
  modelo.py                 download do modelo com progresso visível
  config.py                 config.json, padrões e migrações
  janela.py                 prende a escrita na janela de origem
  inserter.py               colar / digitar / clipboard / webhook
  texto.py                  rede de segurança contra loop e eco do prompt
  diagnostico.py            checagem de ambiente e do modelo
hooks/hook-webrtcvad.py     hook do PyInstaller que sobrepõe o oficial
VozFlow.spec                receita do empacotamento, com o motivo de cada corte
instalador.iss              Inno Setup: instala sem administrador
```

Cerca de 3.500 linhas de Python.

**Stack:** `faster-whisper` (CTranslate2) · CUDA float16 · `sounddevice`
(PortAudio) + `webrtcvad` · PySide6 · `keyboard` · PyInstaller + Inno Setup.

---

## Diagnóstico

```bat
.venv\Scripts\python.exe -m vozflow.diagnostico
```

Lista os microfones, confirma se a GPU está sendo usada e valida o modelo. É a
primeira coisa a rodar quando algo não funciona.

---

## Licença

[MIT](LICENSE) — © 2025 Cláuber Regis Peres Teixeira.

O modelo Whisper é da OpenAI, sob licença MIT. As bibliotecas de terceiros
mantêm suas próprias licenças.

O recurso *Só a minha voz* usa o [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
(Apache-2.0) e o modelo de locutor ResNet34 do
[WeSpeaker](https://github.com/wenet-e2e/wespeaker), treinado no
[VoxCeleb](https://www.robots.ox.ac.uk/~vgg/data/voxceleb/) e distribuído sob
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); o arquivo ONNX vem
de [csukuangfj/speaker-embedding-models](https://huggingface.co/csukuangfj/speaker-embedding-models).
