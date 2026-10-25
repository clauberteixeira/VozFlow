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
  (`pip install --require-hashes`). Um pacote trocado no PyPI ou uma versão
  nova com regressão não entram no build sem ninguém ver;
- o **PyInstaller** fica numa versão fixa no próprio `gerar-exe.bat`.

`requirements.txt` continua com intervalos (`>=`) para quem instala o ambiente
de desenvolvimento; o lock é o que o build usa.

**Para atualizar uma dependência:** mude o piso em `requirements.txt` se for o
caso, atualize o `.venv`, rode a suíte (`python -m pytest -q`) e regenere o lock
a partir dele:

```bat
.venv\Scripts\pip install pip-tools
.venv\Scripts\pip-compile --generate-hashes --strip-extras --allow-unsafe -o requirements-lock.txt requirements.txt
```

O `pip-compile` mantém as versões já presentes no lock; para subir uma, use
`--upgrade-package <nome>`. Os pacotes de GPU (`requirements-gpu.txt`) ficam
fora do lock: só os binários do cuBLAS entram no executável, copiados pelo
`.spec`.

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
   `instalador\VozFlow-<versão>-instalador.exe` e, no texto da Release, o
   SHA-256 dele (`certutil -hashfile instalador\VozFlow-<versão>-instalador.exe SHA256`),
   para quem baixa poder conferir que o arquivo é o mesmo que você gerou.

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
- [ ] SHA-256 do instalador no texto da Release
- [ ] `python -m vozflow.diagnostico` passa no ambiente de desenvolvimento
- [ ] O `.exe` gerado abre e transcreve na GPU
- [ ] O instalador instala, cria o atalho e aparece em Aplicativos Instalados
- [ ] "Iniciar com o Windows" liga e desliga sem sobrar `VozFlow.vbs` órfão
- [ ] O desinstalador remove tudo e respeita a escolha sobre os dados
- [ ] Tag criada e Release publicada com o instalador anexado
