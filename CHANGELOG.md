# Histórico de versões

Formato baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

Correções vindas de uma auditoria do código. Nenhuma muda o visual nem os
padrões de configuração.

### Corrigido — texto na janela certa

- Uma ditada nova logo depois de encerrar outra podia levar o **fim da
  anterior para a janela nova**, com a regra de Enter da nova. Agora o atalho
  espera a entrega terminar (*"Terminando de entregar a ditada anterior..."*).
- **Cancelar** não descartava o texto que ainda esperava o foco voltar: ele
  saía depois, às vezes na ditada seguinte.
- Um erro de transcrição no meio da fala (ex.: GPU sem memória) deixava o
  **microfone gravando** e o texto saindo, com encerrar/cancelar ignorados.
- Ditada iniciada pelo **ícone da bandeja** travava na barra de tarefas;
  agora trava na janela em que você clicar.
- O fim de cada trecho podia sair com palavras **repetidas ou faltando**
  quando a versão final mudava uma palavra já escrita.

### Corrigido — área de transferência

- **"Só copiar"** não funcionava quando já havia algo copiado.
- No modo colar, o conteúdo anterior podia ser devolvido **antes** do `Ctrl+V`
  ser lido, colando o que estava copiado antes (uma senha, por exemplo).
- O VozFlow não mexe mais no que você copiar durante a ditada, nem tira a
  formatação do que já estava copiado no modo ao vivo.
- Em falha (webhook fora do ar, janela que não voltou), o texto agora é
  **mesmo** copiado — antes a mensagem dizia isso sem ter copiado.
- Webhook e "Só copiar" não dependem mais de a janela original voltar ao foco.

### Corrigido — robustez

- `config.json` editado à mão com valor de tipo errado fazia o app não abrir
  ou parar de transcrever calado; agora só aquela chave volta ao padrão.
  Arquivo travado no boot não é mais sobrescrito com os padrões.
- O motor sobrevive a erros inesperados (ex.: fone Bluetooth caindo no meio
  da gravação) em vez de ficar "Pronto" sem transcrever.
- Microfone renomeado pelo Windows ao trocar de porta USB ("(2- …)") volta a
  ser reconhecido.
- Cancelar as Configurações desfaz a calibração; fechar no meio dela não deixa
  mais o microfone aberto.
- Sair durante o download do modelo não derruba mais o processo.

### Segurança e build

- Pisos de `certifi` (raiz emSign comprometida removida), `urllib3`,
  `requests` e `filelock` acima das versões com vulnerabilidades conhecidas.
- Build reprodutível: `requirements-lock.txt` com hashes e PyInstaller em
  versão fixa.
- Suíte de testes automatizados (`pytest`) e CI no Windows.

---

## [1.1.1] — 2025-08-28

Primeira versão publicada no GitHub. As versões anteriores circularam apenas
como instalador, sem changelog registrado — o que está abaixo é o inventário do
que existe hoje no app, não um diff da 1.1.0.

### Transcrição

- Motor `faster-whisper` (CTranslate2) rodando **100% offline**, com o modelo
  `large-v3-turbo` na GPU (CUDA float16) e queda automática para CPU/int8.
- **Escrita ao vivo** no campo em foco, por prefixo estável: uma palavra só é
  escrita depois de aparecer igual em duas transcrições seguidas, e a última
  fica retida porque ainda costuma mudar.
- Comparação de estabilidade **ignorando pontuação e acento** — sozinho, esse
  detalhe cortou 0,86 s da latência até a primeira palavra.
- Escrita **cadenciada** em doses de 25 ms com crédito fracionário, em vez de
  colar blocos: zerou os engasgos acima de 0,7 s.
- Três camadas contra alucinação do Whisper: portão de energia, fallback de
  temperatura e limpeza de n-gramas repetidos / eco do prompt.
- Teto de 20 s por trecho (`max_segment_s`), que mantém a latência constante
  mesmo num ditado de cinco minutos.

### Áudio

- VAD do WebRTC (agressividade 3, frames de 20 ms), com fallback para limiar de
  energia com piso de ruído adaptativo.
- **Calibração guiada** com a própria voz: mede o ambiente por 4 s, a voz por
  4 s, e escolhe o limiar entre os dois.
- Corte de voz de fundo por proximidade — testado contra conversa 15× mais
  fraca: 4/4 palavras da voz de perto, zero do fundo.
- Aviso na janelinha depois de ~3 s captando som fraco demais, em vez de
  emudecer calado.
- Microfone salvo **pelo nome**, não pelo índice do PortAudio, que renumera
  sozinho quando um aparelho entra ou sai.
- Reinício do PortAudio quando o microfone salvo não é encontrado — resolve o
  fone Bluetooth ligado depois do app.

### Atalhos

- Três atalhos globais: começar, encerrar, cancelar.
- **Segundo par de atalhos** com regra de Enter própria: uma tecla que só
  escreve, outra que escreve e já envia.
- Captura e validação de combinações na própria janela, com avisos graduados
  por risco (modificador / navegação / digitação).
- `Alt+Shift` recusado — o Windows consome essa combinação e ela nunca chegaria
  ao app.
- **Guarda do teclado numérico**: `Num 3` não dispara um atalho configurado
  como `PgDn`, apesar de compartilharem o scancode 81.
- Opção de **reservar a tecla** para o VozFlow (`suppress_hotkeys`).
- Mesma combinação em começar e encerrar vira um atalho único que alterna.

### Interface

- Ícone na bandeja com menu de ações e clique para alternar.
- Janela flutuante translúcida que **nunca rouba o foco**, em sete posições,
  com largura e margem configuráveis.
- Pré-aquecimento da janela flutuante na inicialização, que tira ~2,5 s do
  primeiro acionamento.
- Janela de configurações em quatro abas (Atalhos, Microfone, Escrita, Geral),
  com **medidor de nível ao vivo**.
- Sons de início/fim gerados como senoide com envelope, em vez de
  `winsound.Beep` — sem estalo e sem chiado no Bluetooth.

### Entrega do texto

- Quatro destinos: colar, digitar tecla a tecla, só copiar, ou webhook.
- **Trava de janela** (`travar_janela`): o texto é segurado se o foco sair da
  janela onde a ditada começou, em vez de vazar.
- Verificação do retorno de `SetForegroundWindow` — sem foco confirmado, o app
  copia e avisa em vez de digitar às cegas.
- Restauração da área de transferência anterior depois de colar.

### Modelo e primeira execução

- Download do modelo com **progresso visível**: balão da bandeja, barra na
  janelinha e mensagens de erro que dizem o que fazer.
- `HF_HUB_DISABLE_XET=1` — o backend clássico dá 14 degraus de progresso contra
  4 do Xet, e ainda saiu mais rápido na medição.
- Modelo guardado em `~/.cache/huggingface`, compartilhado entre versões e
  fora do instalador.

### Configuração

- `config.json` em `%APPDATA%\VozFlow`, lido como `utf-8-sig` (arquivo com BOM
  não derruba mais tudo para os padrões).
- Backup automático em `.json.bak` quando o arquivo está corrompido.
- Migração automática de `input_device` de índice para nome.
- Histórico de transcrições em `transcricoes.txt`, com opção de desligar.

### Empacotamento

- PyInstaller em modo onedir + Inno Setup, instalando **sem administrador** em
  `%LOCALAPPDATA%\Programs\VozFlow`.
- Pacote reduzido de **2.306 MB para ~995 MB**, cortando cuDNN, NVRTC,
  onnxruntime e o OpenGL por software do Qt — cada corte validado com uma
  transcrição real na GPU.
- Variante só CPU de ~259 MB (`gerar-instalador.bat cpu`).
- Hook local `hook-webrtcvad.py`, sem o qual o build aborta por causa do nome
  da distribuição `webrtcvad-wheels`.
- "Iniciar com o Windows" do instalador grava exatamente o mesmo `VozFlow.vbs`
  que a tela de configurações cria e remove.
- Desinstalador que pergunta se deve apagar configurações e histórico —
  preservando por padrão em desinstalação silenciosa.

---

## Antes da 1.1.1

Não há changelog das versões anteriores. O que se sabe: houve uma **1.0.0** e
uma **1.1.0**, distribuídas como instalador. O caminho técnico percorrido até
aqui — incluindo o que foi tentado e descartado — está registrado em
[docs/DECISOES-TECNICAS.md](docs/DECISOES-TECNICAS.md), que é a leitura útil
para entender como o app chegou ao estado atual.

---

[1.1.1]: https://github.com/clauberteixeira/VozFlow/releases/tag/v1.1.1
