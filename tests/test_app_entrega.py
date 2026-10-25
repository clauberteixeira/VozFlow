"""Fluxo de entrega do texto na janela certa (vozflow/app.py).

Usa o VozFlow real com teclado, clipboard, janela e motor trocados por dubles
(ver conftest.py). Nada e digitado de verdade.
"""

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


def test_acao_so_copiar_deixa_o_texto_no_clipboard(vozflow_app, qapp):
    """F-028."""
    app, _teclado, clip, _jan = vozflow_app(action_on_stop="clipboard")
    _ditar(app, "copie isto")
    esperar(lambda: any(e in ("done", "erro") for e, _ in app.overlay.mensagens), app=qapp)
    assert clip.valor == "copie isto"


# ----------------------------------------------------------------------
# L4: integridade da entrega
# ----------------------------------------------------------------------
def _mensagens(app):
    return [m for _, m in app.overlay.mensagens]


def _entregue(app):
    return any(e in ("done", "erro") for e, _ in app.overlay.mensagens)


def test_stop_normal_digita_o_resto_final(vozflow_app, qapp):
    # o ultimo trecho chega DEPOIS do parar(): nao pode ser descartado
    app, teclado, _clip, _jan = vozflow_app()
    app.iniciar()
    app.engine.segmento.emit("um")
    app.parar()
    app.engine.segmento.emit("dois")
    app.engine._recording = False
    app.engine.done.emit("um dois")
    assert esperar(lambda: teclado.texto == "um dois", app=qapp)


def test_cancelar_descarta_o_texto_pendente(vozflow_app, qapp):
    """F-020: texto segurado nao pode sair depois do cancelar."""
    app, teclado, _clip, jan = vozflow_app()
    app.iniciar()
    jan.foco = 0x200
    app.engine.segmento.emit("nao era para sair")
    app.cancelar()
    app.engine.done.emit("")
    jan.foco = 0x100                      # foco volta
    assert not esperar(lambda: teclado.texto, timeout=0.8, app=qapp)


def test_segmento_atrasado_depois_de_cancelar_e_ignorado(vozflow_app, qapp):
    app, teclado, _clip, _jan = vozflow_app()
    app.iniciar()
    app.cancelar()
    app.engine.segmento.emit("tarde demais")
    app.engine.done.emit("")
    assert not esperar(lambda: teclado.texto, timeout=0.6, app=qapp)


def test_falha_durante_a_gravacao_cancela_o_motor(vozflow_app, qapp):
    """F-019: depois do erro, microfone desligado e nada mais digitado."""
    app, teclado, _clip, _jan = vozflow_app()
    app.iniciar()
    app.engine.failed.emit("Falha ao transcrever: CUDA out of memory")
    assert "cancel" in app.engine.comandos
    app.engine.segmento.emit("depois do erro")
    app.engine.done.emit("")
    assert not esperar(lambda: teclado.texto, timeout=0.6, app=qapp)


def test_nova_ditada_espera_a_anterior_ser_entregue(vozflow_app, qapp):
    """F-010: o fim de A nao pode ir para a janela de B."""
    app, teclado, _clip, jan = vozflow_app()
    app.iniciar()
    app.engine.segmento.emit("fim de A")
    app.parar()
    jan.foco = 0x200                      # usuario ja foi para outra janela
    app.iniciar()                         # ... e tentou ditar de novo
    assert not app._quer_gravar
    assert any("anterior" in m for m in _mensagens(app))
    app.engine._recording = False
    app.engine.done.emit("fim de A")
    assert esperar(lambda: teclado.texto == "fim de A", app=qapp)
    assert jan.restauradas[-1] == 0x100
    assert esperar(lambda: _entregue(app), app=qapp)
    app.iniciar()                         # agora pode
    assert app._quer_gravar


def test_prazo_maximo_nunca_trava_o_app(vozflow_app, qapp):
    import time

    app, _teclado, _clip, _jan = vozflow_app()
    app._dones_pendentes = 1
    app._entregando_desde = time.monotonic() - 3600
    app.iniciar()
    assert app._quer_gravar


def test_modo_colar_nao_restaura_o_clipboard_antes_do_ctrl_v_ser_lido(vozflow_app, qapp):
    """F-001: logo apos a entrega o clipboard ainda tem o texto ditado."""
    app, _teclado, clip, _jan = vozflow_app(insercao_ao_vivo=False)
    _ditar(app, "texto colado")
    assert esperar(lambda: _entregue(app), app=qapp)
    assert clip.valor == "texto colado"


def test_ao_vivo_preserva_o_que_o_usuario_copiou_durante_a_ditada(vozflow_app, qapp):
    """F-011: o modo ao vivo nao usa o clipboard e nao deve mexer nele."""
    app, _teclado, clip, _jan = vozflow_app()
    app.iniciar()
    clip.copy("copiado durante a ditada")
    app.engine.segmento.emit("oi")
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("oi")
    assert esperar(lambda: _entregue(app), app=qapp)
    assert clip.valor == "copiado durante a ditada"


def test_falha_do_webhook_copia_o_texto_e_nao_depende_do_foco(vozflow_app, qapp, monkeypatch):
    """F-006 e F-024."""
    from vozflow import inserter

    enviados = []
    monkeypatch.setattr(inserter, "enviar_webhook",
                        lambda url, campo, texto: enviados.append(texto) or (False, "HTTP 500"))
    app, _teclado, clip, jan = vozflow_app(action_on_stop="webhook")
    jan.restaurar_ok = False
    app.iniciar()
    jan.foco = 0x200
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("para o webhook")
    assert esperar(lambda: _entregue(app), app=qapp)
    assert enviados == ["para o webhook"]
    assert clip.valor == "para o webhook"
    assert any("texto copiado" in m for m in _mensagens(app))


def test_sem_foco_no_fim_copia_o_texto_completo(vozflow_app, qapp):
    app, teclado, clip, jan = vozflow_app()
    app.iniciar()
    app.engine.segmento.emit("parte um")
    assert esperar(lambda: teclado.texto == "parte um", app=qapp)
    jan.foco = 0x200
    jan.restaurar_ok = False
    app.engine.segmento.emit("parte dois")
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("parte um parte dois")
    assert esperar(lambda: _entregue(app), app=qapp)
    assert clip.valor == "parte um parte dois"
    assert teclado.texto == "parte um"


def test_ditada_pela_bandeja_trava_na_proxima_janela_de_verdade(vozflow_app, qapp):
    """F-022: a barra de tarefas nunca vira a janela alvo."""
    app, teclado, _clip, jan = vozflow_app()
    jan.foco = 0x900                      # clicou no icone da bandeja
    app.iniciar()
    app.engine.segmento.emit("pela bandeja")
    assert not esperar(lambda: teclado.texto, timeout=0.6, app=qapp)
    jan.foco = 0x200                      # clicou na janela onde quer o texto
    assert esperar(lambda: teclado.texto == "pela bandeja", app=qapp)
    assert app._janela_alvo == 0x200


def test_bandeja_sem_texto_ao_vivo_usa_a_janela_em_foco_no_fim(vozflow_app, qapp):
    """Revisao do L4: fora do modo ao vivo a trava tambem se resolve."""
    app, teclado, clip, jan = vozflow_app(insercao_ao_vivo=False)
    jan.foco = 0x900
    app.iniciar()
    jan.foco = 0x200
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("colado pela bandeja")
    assert esperar(lambda: "ctrl+v" in teclado.enviados, app=qapp)
    assert not any("nao voltou ao foco" in m for m in _mensagens(app))


def test_bandeja_ida_e_volta_trava_na_janela_clicada_durante_a_fala(vozflow_app, qapp):
    """Re-revisao do L4 (N3): comecou e parou pela bandeja, sem texto ao vivo."""
    app, teclado, _clip, jan = vozflow_app(insercao_ao_vivo=False)
    jan.foco = 0x900
    app.iniciar()
    app.engine._recording = True
    jan.foco = 0x200                      # clicou na janela enquanto falava
    app.engine.text.emit("parcial", False)
    jan.foco = 0x900                      # ... e voltou na bandeja para parar
    app.parar()
    app.engine._recording = False
    app.engine.done.emit("ida e volta")
    assert esperar(lambda: "ctrl+v" in teclado.enviados, app=qapp)
    assert jan.restauradas[-1] == 0x200


def test_done_atrasado_de_ditada_velha_e_ignorado(vozflow_app, qapp):
    """Revisao do L4: depois do prazo, o done da ditada A nao vale para a B."""
    import time

    app, teclado, _clip, jan = vozflow_app()
    app.iniciar()
    app.parar()                               # A: motor travou, done nao vem
    app._entregando_desde = time.monotonic() - 3600
    jan.foco = 0x200
    app.iniciar()                             # B depois do prazo
    assert app._quer_gravar
    app.engine.done.emit("texto velho de A")  # chega atrasado
    app.engine.segmento.emit("texto de B")
    assert esperar(lambda: teclado.texto == "texto de B", app=qapp)
    assert not esperar(lambda: "velho" in teclado.texto, timeout=0.5, app=qapp)
    assert app._quer_gravar and not app._descartando


def test_falha_logo_depois_do_parar_nao_descarta_o_texto_final(vozflow_app, qapp):
    """Revisao do L4: a transcricao final ainda vale."""
    app, teclado, _clip, _jan = vozflow_app()
    app.iniciar()
    app.engine.segmento.emit("quase")
    app.parar()
    app.engine.failed.emit("Falha ao transcrever: erro passageiro")
    assert "cancel" not in app.engine.comandos
    app.engine._recording = False
    app.engine.done.emit("quase pronto")
    assert esperar(lambda: teclado.texto == "quase", app=qapp)
    assert esperar(lambda: _entregue(app), app=qapp)
