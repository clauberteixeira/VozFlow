# Empacotamento e publicação

Como transformar o código-fonte no `VozFlow.exe` e no instalador que a pessoa
baixa e roda.

---

## Os dois comandos

```bat
gerar-exe.bat            :: com GPU  (~1,0 GB)  -> dist\VozFlow\
gerar-exe.bat cpu        :: só CPU   (~260 MB)
gerar-instalador.bat     :: -> instalador\VozFlow-<versão>-instalador.exe
```

O `gerar-instalador.bat` chama o `gerar-exe.bat` sozinho se o executável ainda
não existir, e localiza o compilador do Inno Setup (`ISCC.exe`) nos três
caminhos usuais — instalando via `winget` se não achar.

Ferramentas necessárias:

| Ferramenta | Como obter |
|---|---|
| PyInstaller | já vem no `.venv` do `instalar.bat` |
| Inno Setup 6 | `winget install --id JRSoftware.InnoSetup` (o script faz isso) |

---

## O que o `VozFlow.spec` faz

Modo **onedir** (pasta com `VozFlow.exe` + `_internal\`), não onefile. Onefile
extrairia ~1 GB para o temp a cada abertura.

O grosso do arquivo é a lista de **exclusões**. Sem elas o pacote sai com
2.306 MB, porque `--collect-all nvidia` arrasta tudo que vem nas rodas do CUDA:

| removido | tamanho | por quê |
|---|---:|---|
| cuDNN inteiro | 1.011 MB | o `ctranslate2` não usa cuDNN no caminho do Whisper |
| NVRTC | 178 MB | compilação de kernels em runtime, que o `ctranslate2` não faz |
| onnxruntime | 39 MB | só serve ao VAD Silero; aqui o VAD é o WebRTC |
| `opengl32sw.dll` | 20 MB | OpenGL por software do Qt; a interface é widgets comuns |
| nvblas | 0,3 MB | substituto de BLAS para CPU, sem uso |

Cada exclusão foi validada rodando uma transcrição de verdade na GPU depois de
remover a DLL. Resultado sem cuDNN: **texto idêntico, ainda na GPU, `1.01x` de
diferença de tempo**. Os números completos estão em
[Desempenho](DESEMPENHO.md#tamanho-do-pacote).

O motivo de cada exclusão está anotado dentro do próprio `VozFlow.spec` — se
você for mexer, leia lá antes.

---

## A armadilha do `hook-webrtcvad.py`

`hooks/hook-webrtcvad.py` existe porque o hook oficial do PyInstaller faz
`copy_metadata('webrtcvad')` e **aborta o build inteiro**.

O motivo: o módulo aqui vem da distribuição `webrtcvad-wheels` (a original não
tem wheel para Python 3.12), e o nome do pacote instalado não bate com o nome
que o hook procura. O hook local sobrepõe o oficial e resolve.

---

## O instalador (`instalador.iss`)

Inno Setup 6. As decisões que importam:

- **Não pede administrador.** Instala em `%LOCALAPPDATA%\Programs\VozFlow`.
  Um app de bandeja não precisa de privilégio, e pedir afastaria metade das
  pessoas.
- Cria atalho no menu Iniciar; na área de trabalho é opcional.
- Aparece em **Aplicativos Instalados** do Windows, com desinstalador próprio.
- A opção *"Iniciar junto com o Windows"* grava **exatamente o mesmo**
  `VozFlow.vbs` que a tela de configurações cria e remove. As duas nunca
  divergem — é o mesmo arquivo, gerado do mesmo jeito.
- Ao desinstalar, pergunta se você quer apagar também as configurações e o
  histórico. Numa **desinstalação silenciosa o padrão é preservar**.

---

## Build reprodutível

O `gerar-exe.bat` não instala "a versão do dia" de nada:

- as dependências que vão dentro do executável saem de
  **`requirements-lock.txt`**, com versão exata e hash SHA-256 de cada arquivo
  (`pip install --require-hashes`). Uma versão nova com regressão não entra
  no build sem ninguém ver, e um pacote **baixado** que não bate com o hash é
  recusado;
- o **PyInstaller** fica numa versão fixa no próprio `gerar-exe.bat`.

Limites: o pip não reconfere o hash do que **já está instalado** no `.venv`
("already satisfied") nem remove pacotes a mais. Para o build de uma Release,
use um `.venv` recém-criado (`instalar.bat` numa cópia limpa) ou rode antes
`.venv\Scripts\pip install --force-reinstall --require-hashes -r requirements-lock.txt`.

`requirements.txt` continua com intervalos (`>=`) para quem instala o ambiente
de desenvolvimento — e é o que o CI testa, de propósito, para quebras de
versões novas aparecerem cedo. O lock é o que o build usa.

**Para atualizar uma dependência:** mude o piso em `requirements.txt` se for o
caso e regenere o lock. O `pip-compile` resolve contra o PyPI (não contra o
seu `.venv`) e mantém as versões que já estão no lock; para subir uma, use
`--upgrade-package <nome>`:

```bat
.venv\Scripts\pip install pip-tools
.venv\Scripts\pip-compile --generate-hashes --strip-extras --allow-unsafe -o requirements-lock.txt requirements.txt
```

Depois **sincronize o `.venv` com o lock novo e só então teste** — senão a
versão testada pode não ser a que entrou no lock:

```bat
.venv\Scripts\pip install --require-hashes -r requirements-lock.txt
.venv\Scripts\python -m pytest -q
```

Os pacotes de GPU (`requirements-gpu.txt`) ficam **fora do lock**: o cuBLAS
(~736 MB do executável GPU) continua sem versão exata nem hash. Só os binários
dele entram no executável, copiados pelo `.spec`; fixá-lo é o próximo passo
para a versão GPU ser reprodutível também.

Ainda **não** fixado: a revisão do modelo no Hugging Face. Fixar mudaria o
snapshot no cache de quem já usa (novo download de 1,6 GB, ou falha sem
internet) e precisa do hash de cada um dos modelos oferecidos; fica para uma
versão própria, testada à parte.

---

## Publicando uma nova versão

1. **Suba a versão** em `vozflow/__init__.py` (`__version__`) e em
   `instalador.iss` (`Versao`).
2. Atualize o [CHANGELOG](../CHANGELOG.md).
3. `python -m pytest -q` passa.
4. `gerar-instalador.bat`.
5. Teste o instalador numa máquina limpa, ou pelo menos desinstale e reinstale.
6. `git tag -a v<versão> -m "VozFlow <versão>"` e `git push --tags`.
7. Crie uma **Release** no GitHub anexando o
   `instalador\VozFlow-<versão>-instalador.exe` **e** o
   `VozFlow-<versão>-instalador.exe.sha256` que o `gerar-instalador.bat` grava
   ao lado dele; cole também o hash no texto da Release. Quem baixa confere
   que o arquivo é exatamente o que você gerou.
8. Publique a **mesma Release** (mesma tag, mesmos dois anexos) no repositório
   público [VozFlow-releases](https://github.com/clauberteixeira/VozFlow-releases):

   ```bat
   gh release create v<versão> instalador\VozFlow-<versão>-instalador.exe ^
     instalador\VozFlow-<versão>-instalador.exe.sha256 ^
     --repo clauberteixeira/VozFlow-releases --title "VozFlow <versão>" --notes-file notas.md
   ```

   É dali que o VozFlow instalado se atualiza (`vozflow/atualizador.py`): ele
   só aceita um instalador `VozFlow-<versão>-instalador.exe` com o `.sha256`
   ao lado, baixados da própria Release desse repositório. Release em
   rascunho ou marcada como pré-lançamento é ignorada — use isso para testar
   antes de soltar para todo mundo.

### Assinatura do instalador (o aviso "O Windows protegeu o computador")

O instalador **não é assinado**. Sem assinatura, o SmartScreen do Windows
mostra *"O Windows protegeu o computador"* para quem baixa; a pessoa precisa
clicar em **Mais informações → Executar assim mesmo**. O aviso diminui
sozinho conforme o arquivo ganha downloads (reputação), mas volta a cada
versão nova, porque o arquivo muda.

Assinar exige um **certificado de assinatura de código**, emitido por uma
autoridade certificadora depois de verificar sua identidade. Opções vistas em
2026-10 (confira antes de decidir — preços e regras mudam):

| Opção | Custo | Observação |
|---|---|---|
| **SignPath Foundation** | grátis para open source | O VozFlow se encaixa (licença MIT, código público). Exige build automatizado no CI a partir do repositório, política de assinatura publicada na página do projeto, e o certificado sai em nome da SignPath Foundation, não no seu. Hoje o build é feito à mão (`gerar-exe.bat`), então isso pede montar o build no GitHub Actions primeiro. |
| Certificado comercial (ex.: Certum, Sectigo) | dezenas a centenas de euros/dólares por ano | Em seu nome. Certum anuncia a partir de ~49 € (versão em nuvem); exige validação de identidade. |
| Azure Artifact Signing (Microsoft) | ~US$ 10/mês | Hoje só para **pessoas físicas** nos EUA e Canadá — não atende quem está no Brasil. |

Enquanto não houver certificado, o checksum `.sha256` é o que garante a quem
baixa que o arquivo não foi trocado.

> **Os binários não vão para o repositório.** O `.gitignore` bloqueia `build/`,
> `dist/`, `instalador/` e `*.exe`. Um arquivo de 500 MB passa do limite de
> 100 MB por arquivo do GitHub e incharia o histórico para sempre. O lugar dele
> é a página de Releases.

### Atalho ao publicar só uma correção de código

Os módulos Python ficam no PYZ **dentro** do `VozFlow.exe`. Quando só o código
Python muda, o `_internal\` (587 arquivos, ~1 GB) fica idêntico e basta trocar
o `.exe`.

**Mas regere o instalador mesmo assim** — senão uma reinstalação traz os bugs
de volta.

---

## Checklist antes de soltar uma versão

- [ ] `__version__` subiu em `vozflow/__init__.py` e `Versao` em `instalador.iss`
- [ ] CHANGELOG atualizado
- [ ] `python -m pytest -q` passa
- [ ] `.sha256` anexado e hash no texto da Release
- [ ] `python -m vozflow.diagnostico` passa no ambiente de desenvolvimento
- [ ] O `.exe` gerado abre e transcreve na GPU
- [ ] O instalador instala, cria o atalho e aparece em Aplicativos Instalados
- [ ] "Iniciar com o Windows" liga e desliga sem sobrar `VozFlow.vbs` órfão
- [ ] O desinstalador remove tudo e respeita a escolha sobre os dados
- [ ] Tag criada e Release publicada com o instalador anexado
- [ ] A mesma Release publicada no VozFlow-releases (senão ninguém recebe a atualização)
