"""Despacho da acao configurada ao encerrar (vozflow/inserter.py)."""

import sys
import types

import pytest

from vozflow import inserter


@pytest.fixture
def chamadas(monkeypatch):
    registro = []
    monkeypatch.setattr(inserter, "copiar", lambda t: registro.append(("copiar", t)) or True)
    monkeypatch.setattr(inserter, "colar",
                        lambda t, enter=False: registro.append(("colar", t, enter)) or True)
    monkeypatch.setattr(inserter, "digitar",
                        lambda t, enter=False: registro.append(("digitar", t, enter)) or True)
    return registro


@pytest.mark.parametrize("acao,esperado", [
    ("paste", ("colar", "oi", False)),
    ("type", ("digitar", "oi", False)),
    ("clipboard", ("copiar", "oi")),
    (None, ("colar", "oi", False)),
    ("PASTE", ("colar", "oi", False)),
])
def test_cada_acao_vai_para_a_funcao_certa(chamadas, acao, esperado):
    ok, _ = inserter.entregar({"action_on_stop": acao}, "oi")
    assert ok
    assert chamadas == [esperado]


def test_enter_do_atalho_manda_no_lugar_da_config(chamadas):
    inserter.entregar({"action_on_stop": "paste", "press_enter_after": True}, "oi", enter=False)
    inserter.entregar({"action_on_stop": "paste", "press_enter_after": False}, "oi", enter=True)
    inserter.entregar({"action_on_stop": "paste", "press_enter_after": True}, "oi")
    assert [c[2] for c in chamadas] == [False, True, True]


def test_webhook_sem_url_falha_com_explicacao():
    ok, detalhe = inserter.enviar_webhook("", "texto", "oi")
    assert not ok and "webhook_url" in detalhe


def test_webhook_manda_o_campo_configurado(monkeypatch):
    enviado = {}

    def post(url, json, timeout):
        enviado.update(url=url, json=json, timeout=timeout)
        return types.SimpleNamespace(status_code=204)

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=post))
    ok, detalhe = inserter.entregar(
        {"action_on_stop": "webhook", "webhook_url": "https://exemplo.invalid/h",
         "webhook_field": "msg"}, "oi")
    assert ok and detalhe == "webhook: HTTP 204"
    assert enviado["json"] == {"msg": "oi"}


def test_colar_restaura_depois_e_so_se_o_clipboard_ainda_for_nosso(monkeypatch):
    """F-001/F-011: restauracao atrasada e que nao atropela copia nova do usuario."""
    import time

    import pyperclip

    from conftest import ClipboardFalso, TecladoFalso, esperar

    teclado, clip = TecladoFalso(), ClipboardFalso("anterior")
    monkeypatch.setattr(inserter, "keyboard", teclado)
    monkeypatch.setattr(pyperclip, "copy", clip.copy)
    monkeypatch.setattr(pyperclip, "paste", clip.paste)

    assert inserter.colar("ditado")
    assert teclado.enviados == ["ctrl+v"]
    assert clip.valor == "ditado"             # nada restaurado na hora
    clip.copy("copia nova do usuario")
    time.sleep(1.2)
    assert clip.valor == "copia nova do usuario"

    clip.copy("anterior")
    assert inserter.colar("outro ditado")
    assert esperar(lambda: clip.valor == "anterior", timeout=3)


def test_webhook_com_erro_http(monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(
        post=lambda *a, **k: types.SimpleNamespace(status_code=500)))
    ok, detalhe = inserter.enviar_webhook("https://exemplo.invalid", "texto", "oi")
    assert not ok and detalhe == "HTTP 500"
