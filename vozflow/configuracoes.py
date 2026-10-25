"""Janela unica de configuracoes do VozFlow.

Tudo que da para ajustar fica aqui, em abas. O menu da bandeja so tem acoes.
"""

from __future__ import annotations

import threading

import numpy as np
from PySide6 import QtCore, QtWidgets

from . import atalhos as atl
from . import config
from .audio import Recorder, entradas_para_menu, rms_level
from .overlay import POSICOES

MODELOS = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"]
IDIOMAS = [("Portugues", "pt"), ("Ingles", "en"), ("Espanhol", "es"),
           ("Detectar sozinho", "")]
ACOES = [
    ("Colar na janela ativa", "paste"),
    ("Digitar tecla a tecla", "type"),
    ("So copiar (colo com Ctrl+V)", "clipboard"),
    ("Enviar para um webhook", "webhook"),
]


class JanelaConfiguracoes(QtWidgets.QDialog):
    def __init__(self, cfg, startup_ativo=False, parent=None, overlay=None):
        super().__init__(parent)
        self.cfg = cfg
        self._overlay = overlay   # para a previa de posicao da janelinha
        self.setWindowTitle("VozFlow - configuracoes")
        self.setMinimumWidth(600)
        self._medidor: Recorder | None = None
        self._calibrando = False
        # A calibracao so vale no Salvar: gravar direto na cfg compartilhada
        # fazia o motor usar o limiar novo mesmo depois de um Cancelar.
        self._limiar_calibrado: float | None = None
        # A thread da calibracao (8 s) pode terminar depois do dialogo fechado.
        self._fechado = False

        self.abas = QtWidgets.QTabWidget()
        self.abas.addTab(self._aba_atalhos(), "Atalhos")
        self.abas.addTab(self._aba_microfone(), "Microfone")
        self.abas.addTab(self._aba_escrita(), "Escrita")
        self.abas.addTab(self._aba_geral(startup_ativo), "Geral")

        self.aviso = QtWidgets.QLabel("")
        self.aviso.setWordWrap(True)

        botoes = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        botoes.button(QtWidgets.QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(self.abas)
        lay.addWidget(self.aviso)
        lay.addWidget(botoes)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick_medidor)
        self._refrescar()

    # ==================================================================
    # Aba: atalhos
    # ==================================================================
    def _aba_atalhos(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        self.campos = {
            c: atl.CapturaAtalho(self.cfg.get(c, ""))
            for c in ("hotkey_start", "hotkey_stop", "hotkey_cancel",
                      "hotkey_start2", "hotkey_stop2")
        }
        for campo in self.campos.values():
            campo.capturado.connect(lambda _c: self._refrescar())

        # Cada par carrega a SUA regra de Enter: e assim que da para ter uma
        # tecla que so escreve e outra que escreve e ja envia.
        self.chk_enter = QtWidgets.QCheckBox("Enviar ao encerrar (aperta Enter)")
        self.chk_enter.setChecked(bool(self.cfg.get("press_enter_after")))
        self.chk_enter2 = QtWidgets.QCheckBox("Enviar ao encerrar (aperta Enter)")
        self.chk_enter2.setChecked(bool(self.cfg.get("press_enter_after2")))

        g1 = QtWidgets.QGroupBox("Atalho 1")
        f1 = QtWidgets.QFormLayout(g1)
        f1.setSpacing(8)
        f1.addRow("Comecar a ditar", self.campos["hotkey_start"])
        f1.addRow("Encerrar", self.campos["hotkey_stop"])
        f1.addRow("", self.chk_enter)

        g2 = QtWidgets.QGroupBox("Atalho 2  (opcional)")
        f2 = QtWidgets.QFormLayout(g2)
        f2.setSpacing(8)
        f2.addRow("Comecar a ditar", self.campos["hotkey_start2"])
        f2.addRow("Encerrar", self.campos["hotkey_stop2"])
        f2.addRow("", self.chk_enter2)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.addRow("Cancelar", self.campos["hotkey_cancel"])

        self.chk_suprimir = QtWidgets.QCheckBox(
            "Reservar a tecla para o VozFlow (ela para de fazer a funcao normal)"
        )
        self.chk_suprimir.setChecked(bool(self.cfg.get("suppress_hotkeys")))
        self.chk_suprimir.toggled.connect(self._refrescar)

        btn_padrao = QtWidgets.QPushButton("Restaurar atalhos padrao")
        btn_padrao.clicked.connect(self._atalhos_padrao)

        dica = QtWidgets.QLabel(
            "Clique num campo e pressione a combinacao desejada.\n"
            "Usar a MESMA tecla em comecar e encerrar transforma numa tecla unica "
            "que alterna: aperta para ditar, aperta de novo para encerrar. "
            "O Atalho 2 serve para ter uma tecla que so escreve e outra que "
            "escreve e ja envia - marque o Enter so em uma delas."
        )
        dica.setWordWrap(True)
        dica.setStyleSheet("color:palette(mid);")

        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addWidget(g1)
        lay.addWidget(g2)
        lay.addLayout(form)
        lay.addWidget(self.chk_suprimir)
        lay.addWidget(dica)
        lay.addStretch(1)
        lay.addWidget(btn_padrao, 0, QtCore.Qt.AlignLeft)
        return w

    def _atalhos_padrao(self) -> None:
        for chave, campo in self.campos.items():
            campo.combo = atl.PADROES.get(chave, "")   # o par 2 nasce vazio
            campo._pintar()
        self._refrescar()

    # ==================================================================
    # Aba: microfone
    # ==================================================================
    def _aba_microfone(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        self.cbo_mic = QtWidgets.QComboBox()
        self.cbo_mic.addItem("Padrao do Windows", None)
        try:
            # guarda o NOME do aparelho, nao o indice: o indice do PortAudio
            # muda de posicao quando outro dispositivo entra ou sai
            for rotulo, nome_cru in entradas_para_menu():
                self.cbo_mic.addItem(rotulo, nome_cru)
        except Exception:  # noqa: BLE001
            pass
        atual = self.cfg.get("input_device")
        pos = self.cbo_mic.findData(atual)
        if pos < 0 and atual:
            # o microfone escolhido esta desligado agora: mostra assim mesmo,
            # senao abrir esta tela trocaria a escolha do usuario calada
            from .audio import nome_amigavel
            self.cbo_mic.addItem(nome_amigavel(str(atual)) + "  (desconectado)", atual)
            pos = self.cbo_mic.count() - 1
        self.cbo_mic.setCurrentIndex(max(0, pos))
        self.cbo_mic.currentIndexChanged.connect(self._trocar_medidor)

        self.barra_nivel = QtWidgets.QProgressBar()
        self.barra_nivel.setRange(0, 100)
        self.barra_nivel.setTextVisible(False)
        self.barra_nivel.setFixedHeight(16)

        self.lbl_corte = QtWidgets.QLabel()
        self.btn_calibrar = QtWidgets.QPushButton("Calibrar com a minha voz...")
        self.btn_calibrar.clicked.connect(self._calibrar)
        self.lbl_calib = QtWidgets.QLabel("")
        self.lbl_calib.setWordWrap(True)

        explica = QtWidgets.QLabel(
            "Som mais fraco que o corte e tratado como conversa de fundo e nao "
            "vira texto. A calibracao mede o seu ambiente por 4 segundos, depois "
            "a sua voz por 4 segundos, e escolhe o corte entre os dois."
        )
        explica.setWordWrap(True)
        explica.setStyleSheet("color:palette(mid);")

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.addRow("Entrada de audio", self.cbo_mic)
        form.addRow("Nivel agora", self.barra_nivel)
        form.addRow("Corte atual", self.lbl_corte)

        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addLayout(form)
        lay.addWidget(explica)
        lay.addWidget(self.btn_calibrar, 0, QtCore.Qt.AlignLeft)
        lay.addWidget(self.lbl_calib)
        lay.addStretch(1)
        self._pintar_corte()
        return w

    def _pintar_corte(self) -> None:
        v = float(self.cfg.get("nivel_fala", 0.0))
        if self._limiar_calibrado is not None:
            v = self._limiar_calibrado
        self.lbl_corte.setText(
            f"{v:.5f}" + ("  (desligado - capta qualquer som)" if v <= 0 else "")
        )

    # -- medidor ao vivo ------------------------------------------------
    def _trocar_medidor(self) -> None:
        self._parar_medidor()
        self._iniciar_medidor()

    def _iniciar_medidor(self) -> None:
        if self._calibrando or self._fechado:
            return
        try:
            self._medidor = Recorder(device=self.cbo_mic.currentData())
            self._medidor.start()
            self._timer.start(80)
        except Exception:  # noqa: BLE001
            self._medidor = None

    def _parar_medidor(self) -> None:
        self._timer.stop()
        if self._medidor is not None:
            try:
                self._medidor.stop()
            except Exception:  # noqa: BLE001
                pass
            self._medidor = None
        self.barra_nivel.setValue(0)

    def _tick_medidor(self) -> None:
        if self._medidor is None:
            return
        chunk = self._medidor.drain()
        if chunk.size:
            self.barra_nivel.setValue(int(rms_level(chunk) * 100))

    def showEvent(self, evt):  # noqa: N802
        super().showEvent(evt)
        self._iniciar_medidor()

    def closeEvent(self, evt):  # noqa: N802
        self._parar_medidor()
        super().closeEvent(evt)

    def done(self, r):  # noqa: D102
        self._fechado = True
        self._parar_medidor()
        super().done(r)

    # -- calibracao ------------------------------------------------------
    def _calibrar(self) -> None:
        if self._calibrando:
            return
        self._calibrando = True
        self._parar_medidor()
        self.btn_calibrar.setEnabled(False)
        threading.Thread(target=self._rodar_calibracao, daemon=True).start()

    def _rodar_calibracao(self) -> None:
        from .calibracao import _medir, calcular_limiar

        dev = self.cbo_mic.currentData()
        try:
            self._msg("Medindo o ambiente... NAO fale.", "#c87f0a")
            fundo = _medir(dev)
            self._msg("Agora FALE normalmente, por 4 segundos.", "#c87f0a")
            voz = _medir(dev)
        except Exception as exc:  # noqa: BLE001
            self._fim_calibracao(None, "Nao consegui gravar: " + str(exc))
            return
        limiar, aviso = calcular_limiar(fundo, voz)
        nf = float(np.percentile(fundo, 95))
        ativos = voz[voz > max(nf * 2, 1e-5)]
        nv = float(np.median(ativos)) if ativos.size else 0.0
        if aviso:
            self._fim_calibracao(None, aviso + f"\n(ambiente {nf:.5f} / voz {nv:.5f})")
            return
        self._fim_calibracao(
            limiar,
            f"Ambiente {nf:.5f}   Sua voz {nv:.5f}   ->   corte {limiar:.5f}\n"
            f"Sua voz fica {nv / limiar:.0f}x acima do corte."
        )

    def _msg(self, texto: str, cor: str) -> None:
        QtCore.QMetaObject.invokeMethod(
            self, "_msg_ui", QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, texto), QtCore.Q_ARG(str, cor),
        )

    @QtCore.Slot(str, str)
    def _msg_ui(self, texto: str, cor: str) -> None:
        self.lbl_calib.setStyleSheet("color:" + cor + ";")
        self.lbl_calib.setText(texto)

    def _fim_calibracao(self, limiar, texto: str) -> None:
        QtCore.QMetaObject.invokeMethod(
            self, "_fim_ui", QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(float, -1.0 if limiar is None else float(limiar)),
            QtCore.Q_ARG(str, texto),
        )

    @QtCore.Slot(float, str)
    def _fim_ui(self, limiar: float, texto: str) -> None:
        self._calibrando = False
        if self._fechado:
            # Salvar/Cancelar foi clicado no meio da medicao. Reabrir o medidor
            # aqui deixava o microfone ligado num dialogo invisivel pelo resto
            # da sessao (e travava a deteccao de fone novo, ver audio.py).
            return
        self.btn_calibrar.setEnabled(True)
        ok = limiar >= 0
        self.lbl_calib.setStyleSheet("color:" + ("#2d8a4e" if ok else "#c0392b") + ";")
        self.lbl_calib.setText(texto + ("\nClique em Salvar para usar este corte." if ok else ""))
        if ok:
            self._limiar_calibrado = round(limiar, 6)
            self._pintar_corte()
        self._iniciar_medidor()

    # ==================================================================
    # Aba: escrita
    # ==================================================================
    def _aba_escrita(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        self.chk_aovivo = QtWidgets.QCheckBox(
            "Escrever no campo enquanto eu falo"
        )
        self.chk_aovivo.setChecked(bool(self.cfg.get("insercao_ao_vivo", True)))
        sub = QtWidgets.QLabel(
            "Desmarcado, nada aparece ate voce encerrar - ai o texto e colado de "
            "uma vez so."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:palette(mid); margin-left:22px;")

        self.chk_travar = QtWidgets.QCheckBox(
            "Manter o texto na janela onde comecei a ditar"
        )
        self.chk_travar.setChecked(bool(self.cfg.get("travar_janela", True)))
        sub2 = QtWidgets.QLabel(
            "Trocando de janela no meio da fala, o texto espera em vez de vazar "
            "para a janela errada, e e entregue quando voce encerrar. "
            "Desmarcado, o texto vai para a janela em foco no momento."
        )
        sub2.setWordWrap(True)
        sub2.setStyleSheet("color:palette(mid); margin-left:22px;")

        self.cbo_acao = QtWidgets.QComboBox()
        for rotulo, chave in ACOES:
            self.cbo_acao.addItem(rotulo, chave)
        pos = self.cbo_acao.findData(self.cfg.get("action_on_stop", "paste"))
        self.cbo_acao.setCurrentIndex(max(0, pos))
        self.cbo_acao.currentIndexChanged.connect(self._trocar_acao)

        self.ed_webhook = QtWidgets.QLineEdit(self.cfg.get("webhook_url", ""))
        self.ed_webhook.setPlaceholderText("https://...")

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.addRow("O texto vai para", self.cbo_acao)
        self.lbl_webhook = QtWidgets.QLabel("URL do webhook")
        form.addRow(self.lbl_webhook, self.ed_webhook)

        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addLayout(form)
        lay.addWidget(self.chk_aovivo)
        lay.addWidget(sub)
        lay.addWidget(self.chk_travar)
        lay.addWidget(sub2)
        lay.addStretch(1)
        self._trocar_acao()
        return w

    def _trocar_acao(self) -> None:
        webhook = self.cbo_acao.currentData() == "webhook"
        self.ed_webhook.setVisible(webhook)
        self.lbl_webhook.setVisible(webhook)
        self.chk_aovivo.setEnabled(self.cbo_acao.currentData() in ("paste", "type"))

    # ==================================================================
    # Aba: geral
    # ==================================================================
    def _aba_geral(self, startup_ativo: bool) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        self.cbo_modelo = QtWidgets.QComboBox()
        self.cbo_modelo.addItems(MODELOS)
        self.cbo_modelo.setCurrentText(self.cfg.get("model", "large-v3-turbo"))
        self._modelo_inicial = self.cbo_modelo.currentText()

        self.cbo_idioma = QtWidgets.QComboBox()
        for rotulo, chave in IDIOMAS:
            self.cbo_idioma.addItem(rotulo, chave)
        pos = self.cbo_idioma.findData(self.cfg.get("language", "pt"))
        self.cbo_idioma.setCurrentIndex(max(0, pos))

        self.ed_vocab = QtWidgets.QPlainTextEdit(self.cfg.get("initial_prompt", ""))
        self.ed_vocab.setFixedHeight(70)
        self.ed_vocab.setPlaceholderText(
            "Nomes e termos do seu dia a dia, separados por virgula"
        )

        self.chk_overlay = QtWidgets.QCheckBox("Mostrar a janelinha flutuante")
        self.chk_overlay.setChecked(bool(self.cfg.get("show_overlay", True)))
        self.chk_overlay.toggled.connect(self._trocar_overlay)

        self.cbo_posicao = QtWidgets.QComboBox()
        for chave, rotulo in POSICOES:
            self.cbo_posicao.addItem(rotulo, chave)
        pos = self.cbo_posicao.findData(self.cfg.get("overlay_posicao", "inferior-centro"))
        self.cbo_posicao.setCurrentIndex(max(0, pos))
        self.cbo_posicao.currentIndexChanged.connect(self._previa_overlay)

        self.spin_largura = QtWidgets.QSpinBox()
        self.spin_largura.setRange(260, 1600)
        self.spin_largura.setSingleStep(20)
        self.spin_largura.setSuffix(" px")
        self.spin_largura.setValue(int(self.cfg.get("overlay_width", 760)))
        self.spin_largura.valueChanged.connect(self._previa_overlay)

        self.spin_margem = QtWidgets.QSpinBox()
        self.spin_margem.setRange(0, 600)
        self.spin_margem.setSingleStep(10)
        self.spin_margem.setSuffix(" px da borda")
        self.spin_margem.setValue(int(self.cfg.get("overlay_offset_y", 90)))
        self.spin_margem.valueChanged.connect(self._previa_overlay)
        self.chk_sons = QtWidgets.QCheckBox("Sons de aviso ao comecar e encerrar")
        self.chk_sons.setChecked(bool(self.cfg.get("sounds", True)))
        self.chk_startup = QtWidgets.QCheckBox("Iniciar junto com o Windows")
        self.chk_startup.setChecked(bool(startup_ativo))
        self.chk_log = QtWidgets.QCheckBox("Guardar historico do que foi ditado")
        self.chk_log.setChecked(bool(self.cfg.get("log_transcricoes", True)))

        nota = QtWidgets.QLabel(
            "So uma lista de termos no vocabulario, nunca uma frase: o Whisper "
            "ecoa prosa do prompt dentro da transcricao.\n"
            "Trocar o modelo so vale depois de reiniciar o VozFlow."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet("color:palette(mid);")

        btn_json = QtWidgets.QPushButton("Abrir config.json")
        btn_json.clicked.connect(self._abrir_json)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.addRow("Modelo", self.cbo_modelo)
        form.addRow("Idioma", self.cbo_idioma)
        form.addRow("Vocabulario", self.ed_vocab)
        form.addRow("Posicao da janelinha", self.cbo_posicao)
        form.addRow("Largura", self.spin_largura)
        form.addRow("Distancia da borda", self.spin_margem)

        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addLayout(form)
        lay.addWidget(self.chk_overlay)
        lay.addWidget(self.chk_sons)
        lay.addWidget(self.chk_startup)
        lay.addWidget(self.chk_log)
        lay.addWidget(nota)
        lay.addStretch(1)
        lay.addWidget(btn_json, 0, QtCore.Qt.AlignLeft)
        return w

    def _trocar_overlay(self) -> None:
        for wid in (self.cbo_posicao, self.spin_largura, self.spin_margem):
            wid.setEnabled(self.chk_overlay.isChecked())

    def _previa_overlay(self) -> None:
        """Mostra a janelinha onde ela vai ficar, enquanto voce escolhe.

        Escrever direto na cfg e proposital: o overlay le dela, e assim a
        previa usa exatamente o mesmo codigo da posicao definitiva. Se voce
        cancelar, o app recarrega a config do disco.
        """
        if not self.chk_overlay.isChecked():
            return
        ov = self._overlay
        if ov is None:
            return
        self.cfg["overlay_posicao"] = self.cbo_posicao.currentData()
        self.cfg["overlay_width"] = self.spin_largura.value()
        self.cfg["overlay_offset_y"] = self.spin_margem.value()
        try:
            ov.aplicar_config()
            ov.flash("Aqui fica a transcricao", "rec", 1400)
        except Exception:  # noqa: BLE001
            pass

    def _abrir_json(self) -> None:
        import os

        try:
            os.startfile(str(config.CONFIG_PATH))  # noqa: S606
        except Exception:  # noqa: BLE001
            pass

    # ==================================================================
    # Validacao e gravacao
    # ==================================================================
    def _valores_atalhos(self) -> dict:
        return {c: campo.combo for c, campo in self.campos.items()}

    def _refrescar(self) -> None:
        erro, aviso = atl.validar(self._valores_atalhos(), self.chk_suprimir.isChecked())
        if erro:
            self.aviso.setStyleSheet("color:#c0392b;")
            self.aviso.setText(erro)
        elif aviso:
            self.aviso.setStyleSheet("color:#c87f0a;")
            self.aviso.setText(aviso)
        else:
            self.aviso.setText("")

    def _salvar(self) -> None:
        erro, _ = atl.validar(self._valores_atalhos(), self.chk_suprimir.isChecked())
        if erro:
            self.abas.setCurrentIndex(0)
            self._refrescar()
            return

        antes = dict(self.cfg)
        self.cfg.update(self._valores_atalhos())
        self.cfg["suppress_hotkeys"] = self.chk_suprimir.isChecked()
        self.cfg["input_device"] = self.cbo_mic.currentData()
        self.cfg["insercao_ao_vivo"] = self.chk_aovivo.isChecked()
        self.cfg["press_enter_after"] = self.chk_enter.isChecked()
        self.cfg["press_enter_after2"] = self.chk_enter2.isChecked()
        self.cfg["travar_janela"] = self.chk_travar.isChecked()
        self.cfg["overlay_posicao"] = self.cbo_posicao.currentData()
        self.cfg["overlay_width"] = self.spin_largura.value()
        self.cfg["overlay_offset_y"] = self.spin_margem.value()
        self.cfg["action_on_stop"] = self.cbo_acao.currentData()
        self.cfg["webhook_url"] = self.ed_webhook.text().strip()
        self.cfg["model"] = self.cbo_modelo.currentText()
        self.cfg["language"] = self.cbo_idioma.currentData()
        self.cfg["initial_prompt"] = self.ed_vocab.toPlainText().strip()
        self.cfg["show_overlay"] = self.chk_overlay.isChecked()
        self.cfg["sounds"] = self.chk_sons.isChecked()
        self.cfg["log_transcricoes"] = self.chk_log.isChecked()
        if self._limiar_calibrado is not None:
            self.cfg["nivel_fala"] = self._limiar_calibrado
        try:
            self.cfg.save()
        except OSError as exc:
            # Arquivo travado (antivirus, sincronizacao de nuvem): antes a
            # excecao escapava do slot e o dialogo ficava aberto sem explicacao.
            # Volta a cfg em memoria para nao valer algo que nao foi salvo.
            self.cfg.clear()
            self.cfg.update(antes)
            self.aviso.setStyleSheet("color:#c0392b;")
            self.aviso.setText("Nao consegui gravar o config.json (" + str(exc)
                               + "). Feche o programa que esta usando o arquivo e tente de novo.")
            return

        self.startup_pedido = self.chk_startup.isChecked()
        self.modelo_mudou = self.cbo_modelo.currentText() != self._modelo_inicial
        self.accept()
