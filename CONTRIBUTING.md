# Como contribuir

Obrigado pelo interesse. Este guia é curto e direto ao ponto: o que preparar,
como testar sem quebrar nada, e o que o projeto valoriza numa contribuição.

Tudo aqui — código, comentários, commits, issues — é em **português do
Brasil**.

---

## Preparando o ambiente

```bat
git clone https://github.com/clauberteixeira/VozFlow.git
cd VozFlow
instalar.bat
```

Depois, para rodar vendo os logs:

```bat
VozFlow-debug.bat
```

E para conferir que o ambiente está sadio:

```bat
.venv\Scripts\python.exe -m vozflow.diagnostico
```

---

## Abrindo uma issue

Para **bug**, inclua:

- a saída completa de `python -m vozflow.diagnostico`;
- o seu `config.json` (remova o `webhook_url` se tiver algo sensível);
- o que você fez, o que esperava e o que aconteceu;
- o texto do console, se rodou pelo `VozFlow-debug.bat`;
- versão do Windows e modelo do microfone (Bluetooth? headset? webcam?).

Antes de abrir, dê uma olhada em
[Solução de problemas](docs/SOLUCAO-DE-PROBLEMAS.md) — boa parte dos casos de
áudio e atalho já está mapeada lá, com a explicação de *por que* acontece.

Para **sugestão**, descreva o problema que você tem, não só a solução que
imaginou. Muita coisa neste projeto foi resolvida de um jeito diferente do
óbvio porque o óbvio não funciona no Windows — veja
[Decisões técnicas](docs/DECISOES-TECNICAS.md).

---

## Antes de escrever código

**Leia [docs/DECISOES-TECNICAS.md](docs/DECISOES-TECNICAS.md).** Sério. Cada
item de lá custou uma sessão de depuração, e vários parecem "código estranho"
até você saber o motivo. Exemplos do que você provavelmente ia "consertar":

- por que o `temperature` é uma **lista** e não `0.0`;
- por que a config guarda o **nome** do microfone e não o índice;
- por que a thread de inserção fala com a interface por **sinal**;
- por que o app **não escreve** numa janela que está em segundo plano;
- por que `HF_HUB_DISABLE_XET` é definida antes de qualquer import.

Se você for mudar algum desses comportamentos, ótimo — mas venha com medição,
não com intuição.

---

## Testando

Este projeto mexe com teclado global, foco de janela e microfone. Isso torna os
testes perigosos de um jeito específico:

> **Nunca teste com o microfone real e inserção ao vivo + Enter ligados.**
> Já aconteceu: um teste captou voz da sala, colou no terminal e **enviou a
> mensagem**. Use um `Recorder` falso.

Outras duas armadilhas:

- **Use `VOZFLOW_CONFIG_DIR`.** Sem ela, qualquer teste que abra a tela de
  configurações grava por cima da configuração real de quem usa o app.
- **`keyboard.send()` não dispara os próprios atalhos** — o listener marca o
  evento como `is_replaying` e descarta. Para testar atalho, injete via
  `keybd_event` do Win32.

O mínimo antes de abrir um PR:

1. `python -m vozflow.diagnostico` passa;
2. o app abre, dita uma frase e escreve no campo;
3. o cenário que você mexeu, testado à mão;
4. se mexeu no empacotamento, `gerar-exe.bat` roda e o `.exe` transcreve.

---

## Estilo de código

O código segue o que já está lá — leia um arquivo vizinho antes de escrever.
Em resumo:

- **Português nos nomes de domínio** (`nivel_fala`, `travar_janela`,
  `calibracao`) e inglês onde é termo técnico consagrado (`Recorder`,
  `overlay`, `hotkey`).
- **Docstring em toda função não trivial**, explicando *por quê*, não *o quê*.
- **Comentário só quando explica uma decisão não óbvia.** O código deste
  projeto é denso em comentários justamente porque o Windows é cheio de
  armadilhas — mas comentário que repete o código não entra.
- `from __future__ import annotations` no topo, type hints nas assinaturas.
- Sem dependência nova sem motivo forte: cada uma engorda o instalador.

---

## Commits

Mensagens em português, no imperativo, explicando o **efeito**:

```
Ignora a tecla gemea do teclado numerico nos atalhos

PgDn e Num 3 chegam com o mesmo scancode (81) e a lib `keyboard` casa
atalho so pelo scancode, entao quem escolhia PgDn via o app ligar ao
digitar numeros. Le o `is_keypad` do evento e descarta.
```

Um commit por mudança lógica. Se você mexeu em três coisas, são três commits.

---

## Pull request

- Aponte para a `main`.
- Descreva **o que mudou e por quê**, com a medição se for algo de desempenho.
- Se mudou comportamento visível, atualize a documentação em `docs/` no mesmo
  PR.
- Se corrigiu um bug com causa não óbvia, adicione o caso em
  [docs/DECISOES-TECNICAS.md](docs/DECISOES-TECNICAS.md). É o arquivo mais
  valioso do repositório.
- Se é mudança grande, abra uma issue antes para conversar.

---

## Documentação

A documentação está em `docs/`, toda em português:

| Arquivo | Assunto |
|---|---|
| [INSTALACAO.md](docs/INSTALACAO.md) | requisitos, instalador, rodar do fonte |
| [USO.md](docs/USO.md) | atalhos, bandeja, janela flutuante, calibração |
| [CONFIGURACAO.md](docs/CONFIGURACAO.md) | toda chave do `config.json` |
| [ARQUITETURA.md](docs/ARQUITETURA.md) | como o áudio vira texto |
| [DESEMPENHO.md](docs/DESEMPENHO.md) | os números medidos |
| [EMPACOTAMENTO.md](docs/EMPACOTAMENTO.md) | gerar o `.exe` e o instalador |
| [SOLUCAO-DE-PROBLEMAS.md](docs/SOLUCAO-DE-PROBLEMAS.md) | o que fazer quando não funciona |
| [DECISOES-TECNICAS.md](docs/DECISOES-TECNICAS.md) | por que o código é assim |

Regra do projeto: **número em documentação é número medido.** Se você escrever
"ficou mais rápido", diga quanto, medido como, em qual máquina.
