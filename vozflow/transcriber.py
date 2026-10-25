"""Motor de transcricao ao vivo com faster-whisper rodando em thread propria.

A gravacao e fatiada em trechos delimitados por silencio. Enquanto um trecho
esta aberto, ele e retranscrito a cada `partial_interval` segundos para
alimentar o overlay (texto provisorio). Quando o silencio fecha o trecho, ele
e transcrito uma ultima vez com mais qualidade e vira texto definitivo.
"""

from __future__ import annotations

import difflib
import os
import queue
import sys
import time
from pathlib import Path

import numpy as np
from PySide6 import QtCore

from . import modelo as modelo_util
from . import texto as texto_util
from .audio import BLOCK, SAMPLE_RATE, Recorder, SpeechDetector, rms_level, segundos_com_timbre

# Um trecho so e fala de verdade com timbre de voz (vibracao das cordas
# vocais) suficiente: estalo, chiado e respiracao nao tem nenhum, e e em cima
# deles que o Whisper inventa "Obrigado.". Um "sim" curto mede ~0,2 s.
VOZ_MINIMA_S = 0.15
VOZ_MINIMA_PREVIA_S = 0.05
# ...ou bastante som aceito pelo detector, mesmo sem timbre: voz sussurrada
# ou muito rouca tem pouca vibracao, e sem isto sumiria sem aviso.
ACEITO_SEM_TIMBRE_S = 0.8


_cuda_preparado = False


def _prepare_cuda_dlls() -> list[str]:
    """Deixa o cuBLAS/cuDNN dos pacotes nvidia-* alcancaveis pelo ctranslate2.

    Nao basta `os.add_dll_directory`: o ctranslate2 carrega essas DLLs com
    LoadLibrary sem sinalizador de busca estendida, entao elas precisam estar
    tambem no PATH do processo.
    """
    global _cuda_preparado
    if os.name != "nt" or _cuda_preparado:
        return []

    raizes: list[str] = []

    # Empacotado: as DLLs vao para <bundle>/nvidia/... e o pacote `nvidia` pode
    # nem ser importavel, porque so os binarios sao copiados. Por isso o caminho
    # do bundle e procurado direto, antes de tentar o import.
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "") or Path(sys.executable).parent)
        raizes.append(str(base / "nvidia"))

    try:
        import nvidia

        # `nvidia` e namespace package: __file__ e None, o caminho vem do __path__
        raizes += list(getattr(nvidia, "__path__", None) or [])
        if getattr(nvidia, "__file__", None):
            raizes.append(str(Path(nvidia.__file__).parent))
    except ImportError:
        pass

    if not raizes:
        return []

    pastas: list[str] = []
    for raiz in raizes:
        for sub in sorted(Path(raiz).glob("*/bin")):
            if sub.is_dir() and str(sub) not in pastas:
                pastas.append(str(sub))
                try:
                    os.add_dll_directory(str(sub))
                except OSError:
                    pass
    if pastas:
        os.environ["PATH"] = os.pathsep.join(pastas) + os.pathsep + os.environ.get("PATH", "")
    _cuda_preparado = True
    return pastas


def _resto_depois_do_emitido(emitido: list[str], final: list[str]) -> list[str]:
    """Palavras da versao final que vem DEPOIS do que ja foi digitado.

    A versao final (beam 5) as vezes junta, separa ou insere palavras em
    relacao as parciais. Cortar pela contagem de palavras repetia ou perdia o
    fim do trecho. Aqui as duas versoes sao alinhadas PALAVRA a palavra (sem
    acento nem pontuacao): troca de uma palavra por outra ("voces" -> "voce")
    conta 1 para 1; so quando a quantidade muda (juncao/separacao) o corte
    usa o tamanho em letras.
    """
    if not emitido:
        return final
    ja = [texto_util._chave(p) for p in emitido]
    chaves = [texto_util._chave(p) for p in final]
    fim = len(ja)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, ja, chaves, autojunk=False).get_opcodes():
        if not i1 <= fim <= i2:
            continue
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1 and all(
                difflib.SequenceMatcher(None, a, b).ratio() >= 0.5
                for a, b in zip(ja[i1:i2], chaves[j1:j2], strict=True))):
            return final[j1 + (fim - i1):]
        if tag in ("delete", "insert"):
            # delete: palavras que a final nao tem; insert so cai aqui com o
            # emitido inteiro antes dele - nos dois casos nada da final foi usado
            return final[j1:]
        # replace com quantidade diferente: quantas palavras da final cobrem
        # as letras ja digitadas? Entre os cortes dentro da folga (~20%, para
        # grafia), o MENOR - "embora" -> "embor e" nao pode engolir o "e".
        # Pelo menos uma palavra: algo do bloco ja foi digitado ("eu vi a" ->
        # "eu vi o carro" nao pode repetir o "o"). Sem nenhum corte dentro da
        # folga - numero por extenso que virou digito, "vinte" -> "20" - as
        # letras nao dizem nada, e vale a contagem de palavras do bloco.
        letras = sum(len(k) for k in ja[i1:fim])
        if not letras:
            return final[j1:]
        folga = max(1, round(letras * 0.2))
        somas = [0]
        for j in range(j1, j2):
            somas.append(somas[-1] + len(chaves[j]))
        dentro = [c for c in range(1, len(somas)) if abs(somas[c] - letras) <= folga]
        corte = dentro[0] if dentro else min(fim - i1, j2 - j1)
        return final[j1 + corte:]
    return final[fim:]


def _mesma_posicao(a: str, b: str) -> bool:
    """A mesma palavra, so com a grafia trocada ("muitos" -> "muito")?"""
    if a == b:
        return True
    return (difflib.SequenceMatcher(None, a, b).ratio() >= 0.5
            and abs(len(a) - len(b)) <= max(1, max(len(a), len(b)) // 3))


def _onde_termina_o_emitido(emitido: list[str], previa: list[str]) -> int:
    """Indice da previa logo depois do que ja foi digitado.

    Quando o comeco da previa cobre o digitado palavra por palavra (cada par
    igual ou com a grafia trocada: "muitos" -> "muito", "cum" -> "com"), o
    corte e pela posicao. O alinhamento do _resto_depois_do_emitido fica para
    quando o Whisper juntou ou separou palavras ("para o carro" -> "pro carro
    azul", "porque" -> "por que"). Sozinho, com palavra repetida, ele casava o
    "muito" digitado com o primeiro "muito" de "foi muito muito bom" e o
    segundo saia de novo na tela. Comparar so o total de letras tambem nao
    serve: "porque e" e "por que" tem as mesmas letras, e o "e" saia duas
    vezes. Medido num fuzz de 20 mil frases com previas cortadas, reescritas e
    encolhendo: so o alinhamento duplicou ou perdeu palavra em 11; assim, em
    nenhuma.
    """
    n = len(emitido)
    if n and len(previa) >= n and all(
            _mesma_posicao(texto_util._chave(a), texto_util._chave(b))
            for a, b in zip(emitido, previa, strict=False)):
        return n
    return len(previa) - len(_resto_depois_do_emitido(emitido, previa))


def _cuda_disponivel() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


class LiveTranscriber(QtCore.QThread):
    """Thread dona do microfone e do modelo Whisper."""

    ready = QtCore.Signal(str)          # modelo carregado (descricao do backend)
    status = QtCore.Signal(str)         # mensagem curta p/ overlay e tray
    level = QtCore.Signal(float)        # 0..1, volume do microfone
    text = QtCore.Signal(str, bool)     # (texto acumulado, trecho_fechado)
    segmento = QtCore.Signal(str)       # so o trecho novo, para inserir ao vivo
    done = QtCore.Signal(str)           # gravacao encerrada -> texto final
    dica = QtCore.Signal(str)          # aviso util durante a gravacao
    baixando = QtCore.Signal(bool)     # esta baixando o modelo agora?
    failed = QtCore.Signal(str)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._cmds: queue.Queue[str] = queue.Queue()
        self._model = None
        self._rec = Recorder(device=cfg.get("input_device"))
        self._vad = SpeechDetector()
        self._recording = False
        self._reset_buffers()
        self.backend = "?"
        self._intervalo = float(cfg.get("partial_interval", 0.3))
        self._na_cpu = False   # definido ao carregar o modelo

    def _proximo_intervalo(self, duracao: float) -> float:
        """Espera ate a proxima previa, conforme a maquina aguenta.

        Previa mais rapida que `partial_interval` (GPU: 0,3-0,45 s) -> nada
        muda. Mais lenta (CPU) -> folga de 25% da duracao: sem ela o motor
        passava quase o tempo todo retranscrevendo, e o silencio que fecha o
        trecho e o comando de parar demoravam a ser vistos.
        """
        base = float(self.cfg.get("partial_interval", 0.3))
        # Teto de 2 s: uma previa isolada lenta (a primeira da fala, por
        # exemplo) nao pode adiar a seguinte - e preciso duas previas seguidas
        # para uma palavra ser escrita ao vivo.
        return base if duracao <= base else min(1.25 * duracao, max(base, 2.0))

    # ------------------------------------------------------------------
    # API publica (chamada pela thread principal)
    # ------------------------------------------------------------------
    def cmd_start(self) -> None:
        self._cmds.put("start")

    def cmd_stop(self) -> None:
        self._cmds.put("stop")

    def cmd_cancel(self) -> None:
        self._cmds.put("cancel")

    def cmd_quit(self) -> None:
        self._cmds.put("quit")

    @property
    def recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    # Estado interno
    # ------------------------------------------------------------------
    def _reset_buffers(self) -> None:
        self._buf = np.empty(0, dtype=np.float32)
        self._committed: list[str] = []
        self._partial = ""
        self._silence = 0.0
        self._had_speech = False
        self._voz_trecho = 0.0              # segundos com timbre de voz no trecho aberto
        self._aceito_trecho = 0.0           # segundos aceitos pelo VAD e pelo portao
        self._last_partial = 0.0
        self._emitido: list[str] = []      # palavras ja escritas na janela
        self._palavras_ant: list[str] = []  # previa anterior do trecho aberto
        self._piso = 0.0005                # piso de ruido, recalibrado ao vivo
        self._perto = False                # esta chegando voz de perto agora?
        self._rejeitado = 0.0              # segundos de som barrado pelo portao
        self._avisou = False

    def _full_text(self) -> str:
        partes = [p for p in (*self._committed, self._partial) if p]
        # colapsa tambem repeticao que atravessa a fronteira entre trechos
        return texto_util.colapsar_repeticoes(" ".join(partes).strip())

    # ------------------------------------------------------------------
    # Modelo
    # ------------------------------------------------------------------
    def _load_model(self) -> bool:
        _prepare_cuda_dlls()  # antes de qualquer import que carregue o ctranslate2
        from faster_whisper import WhisperModel

        device = self.cfg.get("device", "auto")
        compute = self.cfg.get("compute_type", "auto")
        if device == "auto":
            device = "cuda" if _cuda_disponivel() else "cpu"
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"

        escolhido = self.cfg.get("model", "auto")
        tentativas = [(device, compute)]
        if device == "cuda":
            tentativas.append(("cpu", "int8"))  # fallback se a GPU nao servir

        ultimo_erro = None
        for dev, ct in tentativas:
            # "auto" acompanha o dispositivo: se a GPU falhar, a CPU recebe o
            # modelo leve, nao o grande (12-14 s por previa na CPU).
            nome = modelo_util.resolver_nome(escolhido, dev)
            caminho = self._baixar(nome, avisar=False) if escolhido == "auto" else self._baixar(nome)
            if caminho is None and escolhido == "auto":
                # Sem internet e o modelo ideal nao esta no disco: melhor um que
                # ja esteja (o grande na CPU e lento, mas funciona) do que o app
                # nao abrir - era assim antes do "auto".
                reserva = next((m for m in (modelo_util.MODELO_GPU, modelo_util.MODELO_CPU)
                                if m != nome and modelo_util.ja_baixado(m)), None)
                if reserva:
                    nome, caminho = reserva, self._baixar(reserva)
                else:
                    caminho = self._baixar(nome)   # tenta de novo, agora avisando
            if caminho is None:
                return False
            try:
                self.status.emit("Carregando o modelo na " + ("GPU" if dev == "cuda" else "CPU") + "...")
                self._model = WhisperModel(caminho, device=dev, compute_type=ct)
                self.backend = nome + " / " + dev + " / " + ct
                self._na_cpu = dev == "cpu"
                self._aquecer()
                self.ready.emit(self.backend)
                return True
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
                if dev == "cuda":
                    self.status.emit("GPU indisponivel, caindo para CPU...")
        self.failed.emit("Nao consegui carregar o modelo: " + str(ultimo_erro))
        return False

    def _baixar(self, nome: str, avisar: bool = True) -> str | None:
        """Caminho local do modelo, baixando se preciso (None = falhou)."""
        # Primeiro uso numa maquina nova: centenas de MB a 1,6 GB para baixar.
        # Sem mostrar isso o app parece travado - foi o que aconteceu com o
        # primeiro usuario que instalou o pacote.
        try:
            if not modelo_util.ja_baixado(nome):
                self.baixando.emit(True)
                caminho = modelo_util.garantir(
                    nome, lambda _f, _t, texto: self.status.emit(texto)
                )
                self.baixando.emit(False)
                return caminho
            return modelo_util.garantir(nome)
        except Exception as exc:  # noqa: BLE001
            self.baixando.emit(False)
            if avisar:
                self.failed.emit(modelo_util.explicar_falha(exc))
            return None

    def _aquecer(self) -> None:
        """A primeira inferencia e sempre lenta; faz ela agora e nao no primeiro uso."""
        try:
            mudo = np.zeros(SAMPLE_RATE, dtype=np.float32)
            idioma = self.cfg.get("language") or None
            list(self._model.transcribe(mudo, language=idioma)[0])
        except Exception:
            pass

    def _trecho_e_fala(self, voz: float, aceito: float, final: bool = True) -> bool:
        minimo = VOZ_MINIMA_S if final else VOZ_MINIMA_PREVIA_S
        return voz >= minimo or aceito >= ACEITO_SEM_TIMBRE_S

    def _transcrever(self, audio: np.ndarray, final: bool, voz: float | None = None,
                     aceito: float = 0.0) -> str:
        """`voz`/`aceito`: segundos do trecho com timbre de voz / aceitos pelo
        detector e pelo portao. Trecho que nao e fala nem vai para o modelo;
        frase pronta ("Obrigado.") saindo de trecho quase sem timbre e
        invencao. A previa exige menos voz que o texto final: exigir o
        minimo inteiro nela atrasava a 1a palavra em 0,4 s."""
        if self._model is None or audio.size < int(SAMPLE_RATE * 0.25):
            return ""
        if voz is not None and not self._trecho_e_fala(voz, aceito, final):
            return ""

        # Portao de energia: o Whisper inventa frases inteiras quando recebe
        # audio quase mudo ("Descender.", "Legendas pela comunidade..."), e o
        # VAD sozinho as vezes confunde ruido de sala com fala. Ruido ambiente
        # fica na casa de 1e-5 de RMS; fala fica acima de 1e-2.
        rms = float(np.sqrt(np.mean(np.square(audio))))
        pico = float(np.max(np.abs(audio)))
        # O limiar acompanha a sala: medi 0,000015 de ruido num momento e
        # 0,0039 em outro, na mesma maquina. Um numero fixo ou barra fala baixa
        # ou deixa passar chiado; 3x o piso medido se ajusta sozinho.
        limiar = max(float(self.cfg.get("nivel_minimo", 0.004)), 3.0 * self._piso)
        if rms < limiar and pico < 0.05:
            return ""
        # Nada de realimentar o texto ja transcrito aqui: prender o decoder ao
        # proprio resultado anterior e o que faz ele travar repetindo a ultima
        # palavra ate o fim do trecho.
        prompt = (self.cfg.get("initial_prompt") or "").strip()
        leve = self._na_cpu and not final
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self.cfg.get("language") or None,
                beam_size=5 if final else 1,
                # Lista de temperaturas, nao 0.0 fixo: e o que permite ao
                # faster-whisper detectar saida degenerada pelo
                # compression_ratio_threshold e redecodificar. Excecao: a
                # PREVIA na CPU. Medido: a primeira previa de uma fala (0,7 s
                # de audio) levava 3-8 s refazendo a decodificacao ate 6 vezes
                # sobre texto alucinado, e a escrita ao vivo nunca comecava. A
                # versao final do trecho segue com a lista completa; na GPU,
                # nada muda.
                temperature=[0.0] if leve else [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                # teto de tokens da previa na CPU: ~12 por segundo de audio e
                # folga - fala real fica bem abaixo; alucinacao para cedo. E
                # nunca acima de 220: o faster-whisper levanta ValueError se
                # prompt + max_new_tokens passar de 448, e o initial_prompt
                # ocupa ate ~227 tokens (a falha descartaria a ditada inteira).
                max_new_tokens=min(220, 16 + int(12 * audio.size / SAMPLE_RATE)) if leve else None,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                # repetition_penalty fica em 1.0 de proposito: medido em
                # 1.15 ele trocava palavras corretas ("de ditado" -> "digitado")
                # sem ganho contra o loop, que ja e barrado pelo fallback de
                # temperatura, pelo portao de energia e pelo texto.colapsar.
                vad_filter=False,
                condition_on_previous_text=False,
                initial_prompt=prompt or None,
                word_timestamps=False,
            )
            bruto = " ".join(s.text.strip() for s in segments).strip()
            limpo = texto_util.limpar(bruto, prompt)
            if voz is not None and texto_util.e_invencao(limpo, voz, aceito):
                return ""
            return limpo
        except Exception as exc:  # noqa: BLE001
            self.failed.emit("Falha ao transcrever: " + str(exc))
            return ""

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: C901 - maquina de estados simples
        if not self._load_model():
            return
        self.status.emit("Pronto")
        while True:
            try:
                cmd = self._cmds.get(timeout=0.02 if self._recording else 0.15)
            except queue.Empty:
                cmd = None

            if cmd == "quit":
                break
            try:
                if cmd == "start" and not self._recording:
                    self._iniciar()
                elif cmd in ("stop", "cancel"):
                    if self._recording:
                        self._encerrar(entregar=cmd == "stop")
                    else:
                        # Nada gravando (o microfone falhou ao abrir, ou o stop
                        # chegou antes do start atrasado pelo som). Confirma
                        # mesmo assim: o app espera este done para a proxima.
                        self.done.emit("")

                if self._recording:
                    self._pump()
            except Exception as exc:  # noqa: BLE001
                self._recuperar(exc)

        try:
            self._rec.stop()
        except Exception:  # noqa: BLE001 - saindo: aparelho ja sumiu
            pass

    def _recuperar(self, exc: Exception) -> None:
        """Erro que ninguem previu: fecha o microfone, avisa e segue vivo.

        Antes a excecao matava a QThread com o stream aberto - microfone ligado,
        fila do callback crescendo sem limite - e o app seguia dizendo "Pronto"
        sem transcrever mais nada ate reiniciar. (Ex.: o PortAudio levantando no
        stop quando o fone Bluetooth caiu.)
        """
        self._recording = False     # antes do sinal: o app consulta `recording`
        try:
            self._rec.stop()
        except Exception:  # noqa: BLE001
            pass
        self._reset_buffers()
        self.failed.emit("Erro inesperado no motor: " + str(exc))
        # Confirma um stop/cancel que estivesse em andamento; se ninguem pediu,
        # o app ignora este done.
        self.done.emit("")
        self.status.emit("Pronto")

    def _iniciar(self) -> None:
        self._reset_buffers()
        self._vad = SpeechDetector()
        self._rec.device = self.cfg.get("input_device")  # pode ter mudado no menu
        try:
            self._rec.start()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit("Microfone indisponivel: " + str(exc))
            return
        if self._rec.aviso:
            self.dica.emit(self._rec.aviso)
        self._recording = True
        self._last_partial = time.monotonic()
        self.status.emit("Gravando")
        self.text.emit("", False)

    def _pump(self) -> None:
        chunk = self._rec.drain()
        if chunk.size:
            self.level.emit(rms_level(chunk))
            # Bloco a bloco (100 ms), nao o pedaco inteiro: depois de uma previa
            # lenta chegam 1,5-3 s de uma vez, e julgar tudo junto fazia uma
            # palavra curta no meio de silencio sumir (o pedaco inteiro "nao era
            # voz") e o silencio ser contado de mais ou de menos por sorte.
            for i in range(0, chunk.size, BLOCK):
                self._bloco(chunk[i:i + BLOCK])
                if self._had_speech and self._deve_fechar():
                    self._fechar_trecho()      # o resto do pedaco ja e o proximo trecho
        else:
            time.sleep(0.02)

        if not self._had_speech:
            return

        if self._deve_fechar():
            self._fechar_trecho()
        elif time.monotonic() - self._last_partial >= self._intervalo:
            inicio = time.monotonic()
            self._partial = self._transcrever(self._buf, final=False, voz=self._voz_trecho,
                                              aceito=self._aceito_trecho)
            self._last_partial = time.monotonic()
            self._intervalo = self._proximo_intervalo(self._last_partial - inicio)
            # So escreve no campo depois que o trecho se confirmou como fala: a
            # previa roda antes (para a janelinha), mas o texto final ainda pode
            # descartar o trecho - e o que ja foi digitado nao volta.
            if self._partial and self._trecho_e_fala(self._voz_trecho, self._aceito_trecho):
                self._emitir_estavel(self._partial)
            self.text.emit(self._full_text(), False)

    def _deve_fechar(self) -> bool:
        return (self._silence * 1000 >= self.cfg.get("silence_ms", 700)
                or self._buf.size / SAMPLE_RATE >= self.cfg.get("max_segment_s", 20.0))

    def _bloco(self, bloco: np.ndarray) -> None:
        """Um bloco de 100 ms: portao, VAD, piso de ruido, silencio e timbre."""
        self._buf = np.concatenate([self._buf, bloco]) if self._buf.size else bloco
        nivel = float(np.sqrt(np.mean(np.square(bloco))))
        dur = bloco.size / SAMPLE_RATE

        # Portao de proximidade: quem fala no microfone chega muito mais
        # forte que uma conversa do outro lado da sala. Com histerese, para
        # uma silaba fraca no meio da palavra nao picotar a frase.
        limiar = max(float(self.cfg.get("nivel_fala", 0.0)), 4.0 * self._piso)
        if self._perto:
            limiar *= 0.45
        perto = nivel >= limiar
        eh_voz = self._vad(bloco)

        # Piso de ruido como rastreador de minimo: desce rapido, sobe
        # devagar. Uma media simples subia ate o nivel do som sustentado e
        # o absorvia como se fosse ruido - inclusive a voz fraca que o
        # portao acabara de barrar, que era justamente o que eu precisava
        # detectar para avisar o usuario.
        if nivel < self._piso:
            self._piso = 0.7 * self._piso + 0.3 * nivel
        else:
            self._piso = 0.995 * self._piso + 0.005 * nivel

        if eh_voz and perto:
            self._perto = True
            self._had_speech = True
            self._aceito_trecho += dur
            # o timbre separa voz de respiracao, estalo e chiado, que tambem
            # passam pelo VAD - e e em cima deles que o Whisper inventa
            self._voz_trecho += segundos_com_timbre(bloco)
            self._silence = 0.0
            self._rejeitado = 0.0
        else:
            self._perto = False
            self._silence += dur

            # Chega som claramente acima do ruido, mas fraco demais para o
            # portao. Ficar mudo sem explicar e o pior desfecho possivel.
            # Nao exijo o VAD aqui: com voz muito fraca ele proprio ja nao
            # a reconhece como fala.
            # Acumula com decaimento em vez de zerar: fala tem pausa entre
            # silabas o tempo todo, e zerar a cada queda fazia o contador
            # nunca alcancar o limite - o aviso jamais disparava.
            if nivel > max(3.0 * self._piso, 0.0008):
                self._rejeitado += dur
            else:
                self._rejeitado = max(0.0, self._rejeitado - dur * 0.25)

            if self._rejeitado > 1.5 and not self._had_speech and not self._avisou:
                self._avisou = True
                self.dica.emit(
                    "Nao estou captando sua voz - o som esta fraco demais. "
                    "Fale mais perto do microfone ou calibre em "
                    "Configuracoes > Microfone."
                )

        if not self._had_speech:
            # so silencio ate agora: nao deixa o buffer crescer, mas guarda um
            # respiro para nao cortar o comeco da primeira palavra
            respiro = int(SAMPLE_RATE * 0.4)
            if self._buf.size > respiro * 2:
                self._buf = self._buf[-respiro:]

    def _emitir_estavel(self, parcial: str) -> None:
        """Solta as palavras que pararam de mudar entre duas parciais.

        Esperar o silencio fechar o trecho custava ate 8 s ate a primeira
        palavra aparecer na tela. Uma palavra que sobreviveu a duas
        transcricoes seguidas do mesmo trecho ja pode ser escrita.

        Compara so o que vem DEPOIS do que ja foi escrito. A comparacao desde
        o inicio do trecho travava tudo quando a previa mudava um detalhe na
        parte ja escrita (uma virgula, uma palavra parecida) - o que nao se
        desfaz de qualquer jeito. Medido com a voz real, numa leitura
        continua de 25 s: so 10 de 25 previas liberavam texto e o atraso
        tipico era 3,7 s; assim, 20 de 25 e 2,7 s.
        """
        palavras = parcial.split()
        # Onde termina o que ja esta na tela, nesta previa e na anterior
        ini = _onde_termina_o_emitido(self._emitido, palavras)
        ant = self._palavras_ant
        ini_ant = _onde_termina_o_emitido(self._emitido, ant)
        self._palavras_ant = palavras
        # Compara sem pontuacao nem acento: o Whisper troca "Bom dia!" por
        # "Bom dia," entre duas parciais e a palavra deixaria de "bater",
        # custando uma rodada inteira antes de qualquer texto aparecer.
        agora = [texto_util._chave(p) for p in palavras[ini:]]
        antes = [texto_util._chave(p) for p in ant[ini_ant:]]
        comum = 0
        for a, b in zip(agora, antes, strict=False):
            if a != b:
                break
            comum += 1
        # A ultima palavra da previa ainda muda quando chega mais audio
        # ("confir" -> "confirmar"): fica de fora. As outras confirmadas saem.
        n = min(comum, len(agora) - 1)
        # Palavra curta que era a ULTIMA da previa anterior pode ser pedaco
        # cortado ("em" de "embora", que o Whisper escreveu "em bora"): espera
        # mais uma rodada. Palavra de 4+ letras confirmada ja sai.
        if 0 < n == len(antes) and len(antes[n - 1]) < 4:
            n -= 1
        novas = palavras[ini:ini + max(0, n)]
        if novas:
            self._emitido.extend(novas)
            self.segmento.emit(" ".join(novas))

    def _emitir_resto(self, texto: str) -> None:
        """Fim do trecho: escreve o que a versao final trouxe alem do que ja foi."""
        final = texto.split()
        resto = final[_onde_termina_o_emitido(self._emitido, final):]
        if resto:
            self.segmento.emit(" ".join(resto))
        self._emitido = []
        self._palavras_ant = []

    def _fechar_trecho(self) -> None:
        audio, self._buf = self._buf, np.empty(0, dtype=np.float32)
        voz, self._voz_trecho = self._voz_trecho, 0.0
        aceito, self._aceito_trecho = self._aceito_trecho, 0.0
        self._silence = 0.0
        self._had_speech = False
        self._partial = ""
        texto = self._transcrever(audio, final=True, voz=voz, aceito=aceito)
        if texto:
            self._committed.append(texto)
        self._emitir_resto(texto or "")
        self._last_partial = time.monotonic()
        self.text.emit(self._full_text(), True)

    def _encerrar(self, entregar: bool) -> None:
        self._recording = False
        self._rec.stop()          # para o callback primeiro...
        resto = self._rec.drain()  # ...e so entao esvazia a fila, sem perder nada
        if not entregar:
            self._reset_buffers()
            self.status.emit("Cancelado")
            self.done.emit("")
            return

        self.status.emit("Transcrevendo...")
        if resto.size:
            if self._vad(resto):  # fala nos ultimos milissegundos antes do atalho
                self._had_speech = True
                self._voz_trecho += segundos_com_timbre(resto)
                self._aceito_trecho += resto.size / SAMPLE_RATE
            self._buf = np.concatenate([self._buf, resto]) if self._buf.size else resto

        # Sem o guarda de fala, o silencio residual seria transcrito e o Whisper
        # alucinaria repetindo a ultima frase do initial_prompt.
        if self._had_speech and self._buf.size >= int(SAMPLE_RATE * 0.25):
            texto = self._transcrever(self._buf, final=True, voz=self._voz_trecho,
                                      aceito=self._aceito_trecho)
            if texto:
                self._committed.append(texto)
            self._emitir_resto(texto or "")
        self._partial = ""
        final = self._full_text()
        self._buf = np.empty(0, dtype=np.float32)
        self.text.emit(final, True)
        self.done.emit(final)
        self.status.emit("Pronto")
