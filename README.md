<h1 align="center">VozFlow</h1>

<p align="center">
  <b>Ditado por voz para Windows — offline, em qualquer programa, enquanto você fala.</b><br>
  Clique no campo, aperte a tecla e fale: o texto vai sendo escrito ali mesmo.
</p>

<p align="center">
  <img alt="versão" src="https://img.shields.io/badge/vers%C3%A3o-1.2.8-2ea44f">
  <img alt="plataforma" src="https://img.shields.io/badge/plataforma-Windows%2010%2F11-0078d4">
  <img alt="python" src="https://img.shields.io/badge/python-3.12-3776ab">
  <img alt="offline" src="https://img.shields.io/badge/100%25-offline-8a2be2">
  <img alt="atualização" src="https://img.shields.io/badge/atualiza-sozinho-f59e0b">
  <img alt="licença" src="https://img.shields.io/badge/licen%C3%A7a-MIT-lightgrey">
</p>

<p align="center">
  <img src="docs/vozflow-demo.svg" alt="Ilustração: o texto vai aparecendo num campo de mensagem, letra por letra, enquanto a janelinha do VozFlow mostra que está ouvindo" width="860">
</p>

<p align="center">
  <a href="https://github.com/clauberteixeira/VozFlow/releases/latest"><b>⬇ Baixar a versão mais recente</b></a>
  &nbsp;·&nbsp;
  <a href="#instalação-passo-a-passo"><b>Como instalar, passo a passo</b></a>
</p>

---

## A ideia

Digitar é o gargalo de muita coisa no computador: responder mensagem, escrever
e-mail, documentar, preencher sistema. Falar é três a quatro vezes mais rápido
— mas as ferramentas de ditado costumam exigir internet, um aplicativo
específico, ou mandar a sua voz para um servidor de terceiros.

O **VozFlow** resolve isso de um jeito simples:

- **funciona em qualquer programa** — WhatsApp Web, Gmail, VS Code, Word, campo
  de busca, sistema interno. Não precisa de integração nenhuma: ele escreve
  onde o cursor estiver;
- **escreve enquanto você fala**, não só no fim — você vê a frase se formando;
- **roda inteiro na sua máquina.** O reconhecimento de voz (Whisper) usa a sua
  placa de vídeo. Nenhum áudio sai do computador, sem conta, sem assinatura,
  sem custo por minuto;
- **fica fora do caminho:** um ícone na bandeja, uma tecla para começar e uma
  janelinha que nunca rouba o foco do seu campo.

---

## Índice

- [O que ele faz](#o-que-ele-faz)
- [Como funciona](#como-funciona)
- [Instalação passo a passo](#instalação-passo-a-passo)
- [Como usar](#como-usar)
- [Se algo não funcionar](#se-algo-não-funcionar)
- [Desinstalar](#desinstalar)
- [Atualização automática](#atualização-automática)
- [Como o texto aparece enquanto você fala](#como-o-texto-aparece-enquanto-você-fala)
- [Voz de fundo](#voz-de-fundo)
- [O que já foi feito](#o-que-já-foi-feito)
- [Números](#números)
- [Configuração](#configuração)
- [Documentação completa](#documentação-completa)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Licença](#licença)

---

## O que ele faz

| | |
|---|---|
| **Escrita ao vivo** | O texto entra no campo em foco enquanto você fala, sem precisar apagar nada depois |
| **100% offline** | O modelo roda na sua GPU (ou na CPU, se não houver placa NVIDIA). Nenhum áudio sai da máquina |
| **Atalho global** | Funciona em qualquer programa. Pode ser uma tecla só (`PgDn`, por exemplo) |
| **Dois pares de atalhos** | Uma tecla que só escreve, outra que escreve **e já envia** (aperta Enter) |
| **Trava de janela** | Trocou de janela no meio da fala? O texto espera, não vaza para o lugar errado |
| **Microfone automático** | Segue o microfone padrão do Windows a cada ditada — ligou o fone, ele passa a usar |
| **Calibração** | Mede o seu ambiente e a sua voz, e corta som fraco e distante |
| **Anti-alucinação** | Três camadas contra as falhas clássicas do Whisper (texto inventado no silêncio, repetição) |
| **Vocabulário próprio** | Nomes, siglas e jargão do seu contexto entram certos na transcrição |
| **Atualiza sozinho** | Versão nova é baixada, conferida e instalada sem você fazer nada |
| **Histórico opcional** | Guarda o que foi ditado (ou não, você escolhe), limpando sozinho o que é antigo |

---

## Como funciona

1. **Você aperta o atalho.** O VozFlow fica quieto na bandeja do Windows, ao
   lado do relógio, e começa a ouvir o microfone.
2. **A voz vira texto no seu computador.** O modelo de reconhecimento de voz
   (Whisper) roda na sua placa de vídeo ou, se ela não for NVIDIA, no
   processador.
3. **O texto é escrito onde o cursor está,** como se você estivesse digitando,
   em qualquer programa.
4. **Você aperta o atalho de encerrar.** O VozFlow escreve o que faltava e volta
   a ficar quieto.

A internet só é usada para baixar o modelo na primeira abertura e para procurar
versões novas. Sua voz nunca sai do computador.

---

## Instalação passo a passo

Não precisa instalar Python nem nada além do VozFlow. O download total é de
cerca de 2 GB com placa NVIDIA e 700 MB sem ela, uma vez só.

| Você vai precisar de | |
|---|---|
| **Sistema** | Windows 10 ou 11, 64 bits |
| **Espaço livre** | 3 GB |
| **Memória** | 4 GB (8 GB é melhor) |
| **Microfone** | Qualquer um: o do notebook, um fone ou um headset |
| **Placa de vídeo** | Opcional. Com placa NVIDIA o texto sai mais rápido; sem ela, o VozFlow escolhe sozinho um modelo menor, que roda no processador |

### 1. Baixe o instalador

1. Abra a **[página da versão mais recente](https://github.com/clauberteixeira/VozFlow/releases/latest)**.
2. Desça até **Assets**, no fim da página.
3. Clique em **`VozFlow-<versão>-instalador.exe`** (cerca de 520 MB) e espere o
   download terminar.

Os outros arquivos da lista não são necessários: `.sha256` e `.sig` servem para
conferir o instalador, e `Source code` é o código-fonte.

### 2. Abra o instalador

Dê dois cliques no arquivo baixado.

Se aparecer a tela azul **"O Windows protegeu o computador"**, clique em
**Mais informações** e depois em **Executar assim mesmo**. O aviso aparece
porque o instalador ainda não tem o certificado de assinatura do Windows. Se
quiser, dá para [conferir que o arquivo é o original](docs/INSTALACAO.md#opção-1--instalador-uso-normal).

### 3. Avance pelas telas

O instalador **não pede senha de administrador**: ele instala só para o seu
usuário.

1. **Local de destino:** deixe como está e clique em **Avançar**.
2. **Tarefas adicionais:** as duas opções já vêm marcadas. *Criar atalho na área
   de trabalho* e *Iniciar o VozFlow junto com o Windows*, que deixa o app
   pronto sempre que você ligar o PC. Desmarque o que não quiser e clique em
   **Avançar**.
3. Clique em **Instalar** e espere a cópia dos arquivos.
4. Na última tela, deixe **Abrir o VozFlow agora** marcado e clique em
   **Concluir**.

### 4. Espere o modelo baixar

O VozFlow **não abre uma janela**: ele fica na bandeja do sistema, ao lado do
relógio, como um ícone de microfone. Se não o encontrar, clique na setinha
**^** da barra de tarefas.

Na primeira abertura ele baixa o modelo de reconhecimento de voz (1,6 GB com
placa NVIDIA, cerca de 145 MB sem). Uma janelinha mostra o progresso. Isso só
acontece uma vez. Quando terminar, aparece um aviso começando com **"Pronto."**.

### 5. Dite o primeiro texto

1. Abra o Bloco de Notas, ou qualquer lugar onde se escreve, e clique no campo.
2. Aperte `Ctrl + Alt + G`.
3. Fale normalmente. O texto começa a aparecer em cerca de 2 segundos.
4. Aperte `Ctrl + Alt + S` para encerrar. O que faltava é escrito no campo.

Pronto: não há mais nada para instalar. As versões novas chegam sozinhas.

### 6. Ajuste ao seu microfone (opcional)

Se o VozFlow cortar palavras ou escrever sons de fundo, ensine a ele a sua voz:
clique com o botão direito no ícone da bandeja e vá em **Configurações →
Microfone → Calibrar com a minha voz**.

Para instalar à mão ou rodar a partir do código, veja
**[docs/INSTALACAO.md](docs/INSTALACAO.md)**.

---

## Como usar

O dia a dia cabe em três passos: **clique no campo, aperte o atalho e fale.**

| Atalho (padrão) | O que faz |
|---|---|
| `Ctrl + Alt + G` | Começa a ditar. O texto vai sendo escrito no campo em foco. |
| `Ctrl + Alt + S` | Encerra e escreve o que faltava. |
| `Ctrl + Alt + X` | Cancela. O que já foi escrito fica; o resto é descartado. |

Dá para trocar por **uma tecla só**, que liga e desliga: em
**Configurações → Atalhos**, clique no campo e aperte a tecla. Clicar no ícone
da bandeja também liga e desliga.

O menu da bandeja (botão direito no ícone) tem só o essencial:
**Configurações**, **Abrir histórico**, **Procurar atualização agora** e
**Sair**. Passando o mouse sobre o ícone aparecem a versão, o estado e os
atalhos.

Mais em **[docs/USO.md](docs/USO.md)**.

---

## Se algo não funcionar

| O que aconteceu | O que fazer |
|---|---|
| Não acho o ícone | Clique na setinha **^** ao lado do relógio. Ele pode estar escondido ali |
| O app parece travado na primeira abertura | Ele está baixando o modelo. Aperte `Ctrl + Alt + G` para ver o progresso |
| Apertei o atalho e nada acontece | Outro programa pode estar usando a mesma combinação. Troque em **Configurações → Atalhos** |
| Não capta a minha voz | Em **Configurações → Microfone**, fale e veja se a barra se mexe. Se ela não se mexer, use **Trocar o microfone no Windows**. Se ela se mexer e nada for escrito, use **Calibrar com a minha voz** |

Outros casos, como fone Bluetooth e texto na janela errada, estão em
**[Solução de problemas](docs/SOLUCAO-DE-PROBLEMAS.md)**.

---

## Desinstalar

Vá em **Configurações do Windows → Aplicativos → Aplicativos Instalados →
VozFlow → Desinstalar**. O desinstalador pergunta se você quer apagar também
suas configurações e o histórico.

O modelo de reconhecimento fica em `%USERPROFILE%\.cache\huggingface`. Para
liberar esse espaço, apague essa pasta.

---

## Atualização automática

Ao abrir e a cada 6 horas, o VozFlow pergunta a este repositório do GitHub se
saiu versão nova. Se saiu:

1. baixa o instalador em segundo plano;
2. **confere a assinatura digital** da versão — cada uma é assinada com uma
   chave Ed25519 que fica fora do GitHub, e o app recusa (e apaga) o que ela
   não confirmar, mesmo que alguém invada a conta;
3. espera você **não estar ditando** e o PC ficar **parado por 1 minuto**;
4. fecha, atualiza em silêncio e **abre de novo**, já na versão nova —
   avisando na bandeja.

Se algo der errado no meio, o instalador reabre a versão antiga; se o app não
conseguir fechar, a atualização desiste sem mexer em nada. Dá para desligar em
**Configurações → Geral**. Os detalhes estão em
**[docs/DECISOES-TECNICAS.md](docs/DECISOES-TECNICAS.md)**.

---

## Como o texto aparece enquanto você fala

O Whisper muda de ideia o tempo todo: "pre..." vira "preciso", que vira
"preciso confirmar". Não dá para escrever cada palpite e depois apagar.

A solução é o **prefixo estável**: o trecho aberto é retranscrito a cada 0,3 s,
e uma palavra nova só vai para o campo depois de aparecer **igual em duas
transcrições seguidas**. A última palavra fica retida, porque ainda costuma
mudar. Nada é escrito duas vezes e nada precisa ser apagado.

E o texto não sai aos saltos: as letras saem em doses de 25 ms, espalhando
cada rajada até a próxima chegar — 156 atualizações de tela contra 16, e
**zero** engasgos acima de 0,7 s.

Os detalhes do algoritmo estão em **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

---

## Voz de fundo

O Whisper transcreve tudo que chega no microfone — ele não sabe quem está
falando. Hoje o VozFlow separa pela **proximidade**: quem fala no microfone
chega muito mais forte que uma conversa do outro lado da sala, e som abaixo do
limiar não vira texto. Rode **Configurações → Microfone → Calibrar com a minha
voz** uma vez para ajustar esse limiar ao seu ambiente.

**Limite honesto:** é corte por volume, não reconhecimento de voz. Alguém
falando alto e perto do seu microfone passa. Um filtro que reconhece **a sua
voz** (você grava uma amostra e o app ignora as outras) está em estudo: funcionou
com vozes sintéticas, mas no teste com voz e microfone reais ainda não separou
com segurança, então não foi lançado. Com placa NVIDIA, o **NVIDIA Broadcast**
já remove vozes de fundo antes do áudio chegar ao VozFlow.

---

## O que já foi feito

| Versão | O que trouxe |
|---|---|
| **1.1.1** | Primeira versão: ditado ao vivo com prefixo estável, atalhos globais, janela flutuante, trava de janela, calibração, anti-alucinação, instalador |
| **1.2.0** | Auditoria completa do código: modelo automático (roda liso com ou sem GPU), histórico opcional que se limpa sozinho, texto sempre na janela certa, área de transferência preservada, build reprodutível com hashes |
| **1.2.1** | Configurações abrindo na frente; microfone automático seguindo o Windows a cada ditada |
| **1.2.2** | Escrita mais fluida: a 1ª palavra caiu de 2,5 s para 1,6 s e o atraso típico de 3,5 s para 2,5 s, medidos com voz real |
| **1.2.3** | Tela de atalhos grava só a tecla apertada; tecla "presa" no Windows não trava mais os atalhos |
| **1.2.4** | Atualização automática com assinatura digital |
| **1.2.5** | Menu da bandeja só com o essencial; o estado aparece passando o mouse no ícone |
| **1.2.6** | Fim das frases inventadas ("Obrigado.", "Tchau.") em respiração e ruído; microfone analisado em blocos de 100 ms |
| **1.2.7** | Um repositório só: o app passa a se atualizar por aqui; instalação explicada passo a passo |
| **1.2.8** | Aba Versões nas Configurações: o que mudou em cada versão, dentro do app e sem internet |

Cada mudança passou por testes automáticos (361 hoje, todos sem microfone,
teclado ou internet reais) e por revisão independente antes de sair.
O histórico completo está no **[CHANGELOG](CHANGELOG.md)** e dentro do app, em
**Configurações → Versões**.

---

## Números

Medidos numa RTX 4060 com `large-v3-turbo` em float16.

**Fluidez com fala real** (leitura contínua de 25 s, mediana de 3 rodadas):

| | 1ª palavra | atraso típico | palavras erradas (de 70) |
|---|---|---|---|
| 1.2.1 | 2,5 s | 3,5 s | 6 |
| **1.2.2 em diante** | **1,6 s** | **2,5 s** | **4** |

**Cadência da escrita** (mesmo áudio de 20 s, campo amostrado a cada 50 ms):

| | colando blocos | digitando cadenciado |
|---|---|---|
| atualizações visuais | 16 | **156** |
| maior engasgo | 2,4 s | **0,58 s** |

**Tamanho do pacote:** 2.306 MB no primeiro build, **995 MB** depois de medir
DLL por DLL — o maior corte foi o cuDNN inteiro (1.011 MB), que o caminho do
Whisper não usa. Sem placa de vídeo, a primeira palavra caiu de **43,9 s para
2,8 s** com o modelo automático.

Tudo em **[docs/DESEMPENHO.md](docs/DESEMPENHO.md)**.

---

## Configuração

Tudo pela janela de configurações (botão direito na bandeja), em cinco abas:
**Atalhos**, **Microfone** (medidor ao vivo e calibração), **Escrita**,
**Geral** e **Versões** (o que mudou em cada versão). Salvou, vale na hora.

Quem prefere o arquivo: `%APPDATA%\VozFlow\config.json`. Todas as chaves, com
exemplo comentado, em **[docs/CONFIGURACAO.md](docs/CONFIGURACAO.md)**.

---

## Documentação completa

| Documento | Assunto |
|---|---|
| **[Instalação](docs/INSTALACAO.md)** | Requisitos, instalador, rodar do código, onde ficam os arquivos |
| **[Uso](docs/USO.md)** | Atalhos, bandeja, janela flutuante, calibração, vocabulário |
| **[Configuração](docs/CONFIGURACAO.md)** | Toda chave do `config.json` |
| **[Arquitetura](docs/ARQUITETURA.md)** | Como o áudio vira texto: pipeline, threads, prefixo estável |
| **[Desempenho](docs/DESEMPENHO.md)** | Os números medidos e o que ajustar na sua máquina |
| **[Empacotamento](docs/EMPACOTAMENTO.md)** | Gerar o `.exe` e o instalador, assinar e publicar uma versão |
| **[Solução de problemas](docs/SOLUCAO-DE-PROBLEMAS.md)** | Microfone, Bluetooth, atalhos, GPU, texto no lugar errado |
| **[Decisões técnicas](docs/DECISOES-TECNICAS.md)** | **Por que o código é assim.** Leia antes de mexer |
| [Histórico de versões](CHANGELOG.md) | O que mudou em cada versão |
| [Como contribuir](CONTRIBUTING.md) | Ambiente, testes, estilo, PRs |

> Vai mexer no código? **[Decisões técnicas](docs/DECISOES-TECNICAS.md) é a
> leitura obrigatória.** Cada item de lá custou uma sessão de depuração — por
> que a config guarda o *nome* do microfone e não o índice, por que `PgDn` e
> `Num 3` são a mesma tecla para o Windows, por que cada atualização é assinada.

---

## Estrutura do projeto

```
main.py                     entrada (instância única + bandeja)
vozflow/
  app.py                    bandeja, atalhos globais, orquestração
  transcriber.py            motor faster-whisper em thread própria, prefixo estável
  audio.py                  microfone (segue o padrão do Windows) + VAD
  configuracoes.py          janela de configurações (5 abas)
  atalhos.py                captura e validação de teclas, teclas presas
  overlay.py                janela flutuante que não rouba foco
  calibracao.py             mede sua voz contra o ambiente
  atualizador.py            atualização automática pelo GitHub
  versoes.py                lê o CHANGELOG para a aba Versões
  assinatura.py             Ed25519 (RFC 8032) para conferir as versões
  modelo.py                 download do modelo com progresso visível
  config.py                 config.json, padrões e migrações
  janela.py                 prende a escrita na janela de origem
  inserter.py               colar / digitar / clipboard / webhook
  texto.py                  rede de segurança contra loop e eco do prompt
  diagnostico.py            checagem de ambiente e do modelo
ferramentas/assinar.py      assina o instalador de cada versão
hooks/hook-webrtcvad.py     hook do PyInstaller que sobrepõe o oficial
VozFlow.spec                receita do empacotamento, com o motivo de cada corte
instalador.iss              Inno Setup: instala sem administrador, atualiza em silêncio
```

Cerca de 4.900 linhas de Python e 343 testes.

**Stack:** `faster-whisper` (CTranslate2) · CUDA float16 · `sounddevice`
(PortAudio) + `webrtcvad` · PySide6 · `keyboard` · PyInstaller + Inno Setup.

### Rodar a partir do código

```bat
git clone https://github.com/clauberteixeira/VozFlow.git
cd VozFlow
instalar.bat

VozFlow.vbs          :: roda sem janela de console
VozFlow-debug.bat    :: roda com console, para ver os logs
.venv\Scripts\python.exe -m vozflow.diagnostico   :: confere microfone, GPU e modelo
```

---

## Licença

[MIT](LICENSE) — © 2025 Cláuber Regis Peres Teixeira. Pode usar, modificar e
distribuir.

O modelo Whisper é da OpenAI, sob licença MIT. As bibliotecas de terceiros
mantêm suas próprias licenças.
