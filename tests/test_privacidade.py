"""L3: retencao do historico, debug sem o texto ditado e aviso de webhook sem criptografia."""

import datetime as dt

import pytest

from conftest import esperar
from vozflow import config, inserter


def _linha(dias_atras: int, texto: str) -> str:
    quando = dt.datetime.now() - dt.timedelta(days=dias_atras)
    return "[" + quando.strftime("%d/%m/%Y %H:%M:%S") + "] " + texto + "\n"


def _ditar(app, texto):
    app.iniciar()
    app.engine.segmento.emit(texto)
    app.parar()
    app.engine._recording = False
    app.engine.done.emit(texto)


# ----------------------------------------------------------------------
# F-002 / decisao D1: guarda tudo; so se ficar grande limpa para 7 dias
# ----------------------------------------------------------------------
def test_historico_pequeno_guarda_tudo(vozflow_app, qapp, pasta_config):
    log = pasta_config / "transcricoes.txt"
    log.write_text(_linha(400, "ditado de mais de um ano"), encoding="utf-8")
    app, *_ = vozflow_app()
    _ditar(app, "ditado de hoje")
    assert esperar(lambda: "ditado de hoje" in log.read_text(encoding="utf-8"), app=qapp)
    assert "mais de um ano" in log.read_text(encoding="utf-8")


def test_historico_grande_fica_so_com_a_ultima_semana(vozflow_app, qapp, pasta_config):
    log = pasta_config / "transcricoes.txt"
    log.write_text(_linha(30, "velho um") + _linha(8, "velho dois")
                   + _linha(6, "desta semana") + _linha(0, "de hoje cedo"), encoding="utf-8")
    app, *_ = vozflow_app(historico_max_mb=0.0001)      # ~100 bytes: estourou
    _ditar(app, "ditado agora")
    assert esperar(lambda: "ditado agora" in log.read_text(encoding="utf-8"), app=qapp)
    conteudo = log.read_text(encoding="utf-8")
    assert "velho" not in conteudo
    assert "desta semana" in conteudo and "de hoje cedo" in conteudo
    assert not list(pasta_config.glob("*.tmp"))


def test_linha_sem_carimbo_acompanha_a_anterior(vozflow_app, qapp, pasta_config):
    log = pasta_config / "transcricoes.txt"
    log.write_text(_linha(30, "velho") + "continuacao do velho\n"
                   + _linha(1, "novo") + "continuacao do novo\n", encoding="utf-8")
    app, *_ = vozflow_app(historico_max_mb=0.0001)
    _ditar(app, "agora")
    assert esperar(lambda: "agora" in log.read_text(encoding="utf-8"), app=qapp)
    conteudo = log.read_text(encoding="utf-8")
    assert "continuacao do velho" not in conteudo
    assert "continuacao do novo" in conteudo


def test_historico_desligado_nao_grava(vozflow_app, qapp, pasta_config):
    app, *_ = vozflow_app(log_transcricoes=False)
    _ditar(app, "nao guardar")
    esperar(lambda: app.overlay.mensagens and app.overlay.mensagens[-1][0] == "done", app=qapp)
    assert not (pasta_config / "transcricoes.txt").exists()


# ----------------------------------------------------------------------
# F-018: modo debug nao grava o texto ditado nem titulos de janela
# ----------------------------------------------------------------------
@pytest.mark.parametrize("modo,deve_conter", [("1", False), ("texto", True)])
def test_debug_so_grava_o_texto_se_pedido(vozflow_app, qapp, tmp_path, monkeypatch, modo, deve_conter):
    from vozflow import app as modulo_app

    destino = tmp_path / "vozflow-debug.txt"
    monkeypatch.setattr(modulo_app, "_DEBUG", modo)
    monkeypatch.setattr(modulo_app, "_DEBUG_LOG", destino)
    app, teclado, *_ = vozflow_app()
    _ditar(app, "senha secreta 1234")
    assert esperar(lambda: teclado.texto == "senha secreta 1234", app=qapp)
    assert esperar(lambda: "ENVIADO" in destino.read_text(encoding="utf-8")
                   if destino.exists() else False, app=qapp)
    conteudo = destino.read_text(encoding="utf-8")
    assert ("senha secreta" in conteudo) is deve_conter
    assert ("Bloco de notas" in conteudo) is deve_conter     # titulo da janela


# ----------------------------------------------------------------------
# F-007 / decisao D2: aviso (nao bloqueio) para webhook sem criptografia
# ----------------------------------------------------------------------
@pytest.mark.parametrize("url,inseguro", [
    ("http://exemplo.com/hook", True),
    ("HTTP://Exemplo.com", True),
    ("https://exemplo.com/hook", False),
    ("http://localhost:5678/webhook", False),
    ("http://127.0.0.1/x", False),
    ("http://[::1]:8080/", False),
    ("", False),
])
def test_url_sem_criptografia(url, inseguro):
    assert inserter.url_sem_criptografia(url) is inseguro


def test_configuracoes_avisam_webhook_http_mas_salvam(qapp, pasta_config, monkeypatch):
    from vozflow import configuracoes

    monkeypatch.setattr(configuracoes, "nome_do_padrao", lambda: None)
    dlg = configuracoes.JanelaConfiguracoes(config.Config(dict(config.DEFAULTS)))
    dlg.cbo_acao.setCurrentIndex(dlg.cbo_acao.findData("webhook"))
    dlg.ed_webhook.setText("http://exemplo.com/hook")
    assert "sem criptografia" in dlg.lbl_webhook_aviso.text()
    dlg.ed_webhook.setText("https://exemplo.com/hook")
    assert dlg.lbl_webhook_aviso.text() == ""
    dlg.ed_webhook.setText("http://exemplo.com/hook")
    dlg._salvar()
    assert dlg.cfg["webhook_url"] == "http://exemplo.com/hook"     # nao bloqueia
    dlg.deleteLater()
