"""Historico de versoes: dentro do app (aba Versoes) e no GitHub."""

import re
import sys
from pathlib import Path

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from vozflow import __version__, atualizador, config, configuracoes, versoes

RAIZ = Path(__file__).resolve().parent.parent

EXEMPLO = """\
# Histórico de versões

Formato baseado no Keep a Changelog.

---

## [Não lançado]

- Ainda não saiu: não aparece no app.

---

## [1.2.1] — 2026-10-24

### Corrigido

- **Configurações** abrindo na frente, veja [Uso](docs/USO.md).

---

## [1.2.0] — 2026-10-23

Correções vindas de uma auditoria.

---

## Antes da 1.2.0

Não há changelog das versões anteriores.

---

[1.2.1]: https://github.com/exemplo/releases/tag/v1.2.1
"""


@pytest.fixture
def changelog(tmp_path, monkeypatch):
    arq = tmp_path / "CHANGELOG.md"
    arq.write_text(EXEMPLO, encoding="utf-8")
    monkeypatch.setattr(versoes, "caminho_changelog", lambda: arq)
    return arq


def _janela():
    return configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))


def _aba_versoes(dlg):
    nomes = [dlg.abas.tabText(i) for i in range(dlg.abas.count())]
    return dlg.abas.widget(nomes.index("Versoes"))


def test_separa_cada_versao_com_data_e_mudancas(changelog):
    assert versoes.ler_versoes() == [
        versoes.Versao("1.2.1", "24/10/2026",
                       "### Corrigido\n\n"
                       "- **Configurações** abrindo na frente, veja [Uso](docs/USO.md)."),
        versoes.Versao("1.2.0", "23/10/2026", "Correções vindas de uma auditoria."),
    ]


def test_sem_o_arquivo_nao_ha_versoes(tmp_path, monkeypatch):
    monkeypatch.setattr(versoes, "caminho_changelog", lambda: tmp_path / "nao-existe.md")
    assert versoes.ler_versoes() == []


def test_arquivo_ilegivel_nao_impede_de_abrir_as_configuracoes(tmp_path, monkeypatch):
    arq = tmp_path / "CHANGELOG.md"
    arq.write_bytes(b"\xff\xfe\x00 nao e utf-8 \xe9")
    monkeypatch.setattr(versoes, "caminho_changelog", lambda: arq)
    assert versoes.ler_versoes() == []


def test_instalado_le_o_changelog_de_dentro_do_pacote(tmp_path, monkeypatch):
    """No executavel nao existe a pasta do repositorio: o arquivo vai no bundle."""
    (tmp_path / "CHANGELOG.md").write_text(EXEMPLO, encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert versoes.ler_versoes()[0].numero == "1.2.1"


def test_aba_mostra_a_versao_instalada_e_o_que_mudou_em_cada_uma(qapp, changelog):
    aba = _aba_versoes(_janela())
    assert any(__version__ in r.text() for r in aba.findChildren(QtWidgets.QLabel))
    texto = aba.findChild(QtWidgets.QTextBrowser).toPlainText()
    assert texto.index("1.2.1") < texto.index("24/10/2026") < texto.index("abrindo na frente")
    assert texto.index("abrindo na frente") < texto.index("1.2.0") < texto.index("auditoria")
    assert "**" not in texto                     # formatado, nao o markdown cru


def test_sem_o_historico_a_aba_diz_onde_encontrar(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(versoes, "caminho_changelog", lambda: tmp_path / "nao-existe.md")
    caixa = _aba_versoes(_janela()).findChild(QtWidgets.QTextBrowser)
    assert "Nao encontrei" in caixa.toPlainText()
    assert caixa.document().toHtml().count("CHANGELOG.md") >= 1


@pytest.mark.parametrize("link, esperado", [
    ("docs/USO.md", "https://github.com/clauberteixeira/VozFlow/blob/main/docs/USO.md"),
    ("https://semver.org/lang/pt-BR/", "https://semver.org/lang/pt-BR/"),
])
def test_link_do_historico_abre_no_navegador(qapp, changelog, monkeypatch, link, esperado):
    abertos = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: abertos.append(url.toString()))
    caixa = _aba_versoes(_janela()).findChild(QtWidgets.QTextBrowser)
    fonte_antes = caixa.source()
    caixa.anchorClicked.emit(QtCore.QUrl(link))
    assert abertos == [esperado]
    assert caixa.source() == fonte_antes
    assert "abrindo na frente" in caixa.toPlainText()    # a caixa nao trocou de pagina


def test_aviso_de_atualizado_diz_onde_ver_o_que_mudou(tmp_path, qapp):
    atualizador.gravar_estado({"vista": "0.0.1"}, tmp_path)
    a = atualizador.Atualizador(config.Config(dict(config.DEFAULTS)), lambda: False,
                                lambda v, c: None, ativo=True, pasta=tmp_path)
    assert "Versoes" in a.conferir_abertura()


# ----------------------------------------------------------------------
# Travas: versao nova nao sai sem registro. Rodam no CI a cada push.
# ----------------------------------------------------------------------
def test_versao_atual_e_a_primeira_do_changelog():
    """Subiu a versao e esqueceu o CHANGELOG: a aba Versoes do app e a Release
    ficariam sem dizer o que mudou."""
    primeira = versoes.ler_versoes(RAIZ / "CHANGELOG.md")[0]
    assert primeira.numero == __version__
    assert primeira.mudancas


def test_todas_as_versoes_do_changelog_tem_link_da_release():
    texto = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    for v in versoes.ler_versoes(RAIZ / "CHANGELOG.md"):
        assert f"[{v.numero}]: https://github.com/clauberteixeira/VozFlow/releases/tag/v{v.numero}" in texto


def test_readme_acompanha_a_versao_atual():
    """A pagina do GitHub e o que quem chega le primeiro."""
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert re.search(r"badge/vers%C3%A3o-([\d.]+)-", readme).group(1) == __version__
    assert re.findall(r"^\| \*\*([\d.]+)\*\* \|", readme, re.MULTILINE)[-1] == __version__


def test_changelog_vai_dentro_do_executavel():
    """Sem esta linha no .spec a aba Versoes fica vazia so no app instalado, e o
    CI nao gera o executavel para perceber."""
    spec = (RAIZ / "VozFlow.spec").read_text(encoding="utf-8")
    assert 'datas.append((str(RAIZ / "CHANGELOG.md"), "."))' in spec
