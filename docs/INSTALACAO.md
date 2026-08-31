# Instalação

Duas formas: o **instalador pronto** (para usar) ou **rodar do código-fonte**
(para desenvolver). As duas descrevem a mesma versão do app.

---

## Requisitos

| Item | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10 (64 bits) | Windows 11 |
| Python | 3.10 (só para rodar do fonte) | **3.12** |
| Placa de vídeo | nenhuma — cai para CPU sozinho | NVIDIA com CUDA 12 (RTX 4060 é a de referência) |
| Memória | 4 GB | 8 GB |
| Disco | 2,0 GB (variante CPU + modelo) | 3,0 GB (variante GPU + modelo) |
| Internet | só no primeiro uso, para baixar o modelo (~1,6 GB) | — |

Sem GPU o VozFlow funciona: ele detecta a ausência e cai para CPU/int8
sozinho. A diferença é o tempo de transcrição — décimos de segundo na GPU,
alguns segundos na CPU.

---

## Opção 1 — instalador (uso normal)

Baixe o `VozFlow-<versão>-instalador.exe` na página de
[Releases](../../releases) e execute.

O instalador:

- **não pede administrador** — instala em `%LOCALAPPDATA%\Programs\VozFlow`;
- cria atalho no menu Iniciar (e na área de trabalho, se você marcar);
- aparece em **Aplicativos Instalados** do Windows, com desinstalador;
- oferece *"Iniciar junto com o Windows"*, que grava exatamente o mesmo
  `VozFlow.vbs` que a tela de configurações cria e remove — as duas nunca
  divergem;
- ao desinstalar, pergunta se você quer apagar também suas configurações e o
  histórico. Numa desinstalação silenciosa o padrão é **preservar**.

O modelo de transcrição **não vem no instalador**: são 1,6 GB baixados na
primeira execução e guardados em `%USERPROFILE%\.cache\huggingface`,
compartilhados entre todas as versões do VozFlow.

---

## Opção 2 — rodar do código-fonte

```bat
git clone https://github.com/clauberteixeira/VozFlow.git
cd VozFlow
instalar.bat
```

O `instalar.bat` faz tudo sozinho:

1. cria o ambiente virtual `.venv`;
2. instala as dependências do `requirements.txt`;
3. detecta a GPU NVIDIA e, se houver, instala também o `requirements-gpu.txt`;
4. dispara o download do modelo de transcrição.

Depois disso, para abrir o app:

```bat
VozFlow.vbs         :: duplo clique - roda sem janela de console
VozFlow-debug.bat   :: com console, para ver os logs e erros
```

Ou direto pelo Python do ambiente:

```bat
.venv\Scripts\pythonw.exe main.py    :: sem console
.venv\Scripts\python.exe  main.py    :: com console
```

O ícone de microfone aparece na bandeja do sistema, ao lado do relógio.

### Instalando à mão

Se preferir não usar o `.bat`:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

:: só se você tem GPU NVIDIA:
.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
```

---

## O primeiro uso: o download do modelo

Na primeira abertura o VozFlow baixa o modelo `large-v3-turbo` (1,6 GB) do
Hugging Face. Isso acontece **uma única vez**.

Enquanto baixa:

- um balão da bandeja avisa que o download começou e que ele é único;
- a janelinha flutuante aparece sozinha com o progresso — *"Baixando o modelo:
  47% (730 de 1547 MB)"* —, atualizando a cada meio segundo;
- apertar o atalho durante o download mostra o progresso, não uma mensagem
  genérica;
- se falhar, a mensagem diz **o que fazer**: sem internet, sem espaço em disco
  ou repositório recusado, em vez do erro cru da biblioteca.

Para baixar um modelo diferente depois, troque a chave `model` em
[Configuração](CONFIGURACAO.md) e reinicie o app.

---

## Conferindo se deu certo

```bat
.venv\Scripts\python.exe -m vozflow.diagnostico
```

O diagnóstico lista os microfones disponíveis, confirma se a GPU está sendo
usada e valida o modelo. É a primeira coisa a rodar quando algo não funciona —
veja [Solução de problemas](SOLUCAO-DE-PROBLEMAS.md).

---

## Onde ficam os arquivos

| Caminho | O que é |
|---|---|
| `%APPDATA%\VozFlow\config.json` | toda a configuração |
| `%APPDATA%\VozFlow\transcricoes.txt` | histórico do que foi ditado |
| `%USERPROFILE%\.cache\huggingface` | o modelo, 1,6 GB, baixado uma vez só |
| `%LOCALAPPDATA%\Programs\VozFlow\` | o app instalado |
| `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VozFlow.vbs` | o que faz iniciar com o Windows |

---

## Desinstalar

- **Instalado pelo instalador:** Configurações do Windows → Aplicativos →
  Aplicativos Instalados → VozFlow → Desinstalar.
- **Rodando do fonte:** feche o app pela bandeja e apague a pasta do projeto.

Em ambos os casos, para remover também os dados apague
`%APPDATA%\VozFlow` e, se quiser recuperar os 1,6 GB do modelo,
`%USERPROFILE%\.cache\huggingface`.
