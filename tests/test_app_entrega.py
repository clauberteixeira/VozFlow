"""Fluxo de entrega do texto na janela certa (vozflow/app.py).

Usa o VozFlow real com teclado, clipboard, janela e motor trocados por dubles
(ver conftest.py). Nada e digitado de verdade.
"""

import pytest

from conftest import esperar


def _ditar(app, motor_texto, *segmentos):
    app.iniciar()
    for s in segmentos:
        app.engine.segmento.emit(s)
    app.parar()
    app.engine._recording = False
    app.engine.done.emit(motor_texto)


def test_ao_vivo_escreve_na_janela_alvo(vozflow_app, qapp):
    app, teclado, _clip, _jan = vozflow_app()
    _ditar(app, "Ola mundo", "Ola mundo")
    assert esperar(lambda: teclado.texto == "Ola mundo", app=qapp)
    assert esperar(lambda: any("escrito em Bloco de notas" in m for _, m in app.overlay.mensagens),
                   app=qapp)
    assert "enter" not in teclado.enviados


def test_ao_vivo_com_enter_aperta_enter_no_fim(vozflow_app, qapp):
    app, teclado, _clip, _jan = vozflow_app(press_enter_after=True)
    app._iniciar_padrao()
    qapp.processEvents()   # sig_start e enfileirado: iniciar() roda aqui
    app.engine.segmento.emit("manda isso")
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("manda isso")
    assert esperar(lambda: teclado.enviados == ["enter"], app=qapp)
    assert teclado.texto == "manda isso"


def test_texto_espera_enquanto_o_foco_esta_em_outra_janela(vozflow_app, qapp):
    app, teclado, _clip, jan = vozflow_app()
    app.iniciar()
    jan.foco = 0x200                      # usuario trocou de janela
    app.engine.segmento.emit("segredo")
    assert not esperar(lambda: teclado.texto, timeout=0.6, app=qapp)
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("segredo")
    # no fim o foco volta para a janela original e so entao o texto sai
    assert esperar(lambda: teclado.texto == "segredo", app=qapp)
    assert jan.restauradas and jan.restauradas[-1] == 0x100


def test_sem_foco_confirmado_copia_em_vez_de_digitar(vozflow_app, qapp):
    app, teclado, clip, jan = vozflow_app(press_enter_after=True)
    app._iniciar_padrao()
    qapp.processEvents()   # sig_start e enfileirado: iniciar() roda aqui
    jan.foco = 0x200
    jan.restaurar_ok = False
    app.engine.segmento.emit("nao vaze")
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("nao vaze")
    assert esperar(lambda: any(e == "erro" for e, _ in app.overlay.mensagens), app=qapp)
    assert teclado.texto == ""
    assert "enter" not in teclado.enviados
    assert clip.valor == "nao vaze"


def test_modo_colar_usa_ctrl_v_e_devolve_o_clipboard(vozflow_app, qapp):
    app, teclado, clip, _jan = vozflow_app(insercao_ao_vivo=False)
    _ditar(app, "texto colado")
    assert esperar(lambda: "ctrl+v" in teclado.enviados, app=qapp)
    assert "texto colado" in clip.historico
    assert esperar(lambda: clip.valor == "conteudo anterior", app=qapp)


def test_historico_registra_o_texto_final(vozflow_app, qapp, pasta_config):
    app, _teclado, _clip, _jan = vozflow_app()
    _ditar(app, "linha do historico", "linha do historico")
    assert esperar(lambda: (pasta_config / "transcricoes.txt").exists(), app=qapp)
    assert "linha do historico" in (pasta_config / "transcricoes.txt").read_text(encoding="utf-8")


@pytest.mark.xfail(strict=True, reason="F-028: 'So copiar' e desfeito pela restauracao do clipboard")
def test_acao_so_copiar_deixa_o_texto_no_clipboard(vozflow_app, qapp):
    app, _teclado, clip, _jan = vozflow_app(action_on_stop="clipboard")
    _ditar(app, "copie isto")
    esperar(lambda: any(e in ("done", "erro") for e, _ in app.overlay.mensagens), app=qapp)
    assert clip.valor == "copie isto"
