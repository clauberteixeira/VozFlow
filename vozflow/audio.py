"""Captura do microfone e deteccao de fala (VAD)."""

from __future__ import annotations

import contextlib
import queue
import re
import threading

import numpy as np
import sounddevice as sd

try:
    import webrtcvad
except ImportError:  # pragma: no cover - fallback por energia
    webrtcvad = None

SAMPLE_RATE = 16_000
BLOCK = 1600  # 100 ms


_abertos = 0                     # streams vivos neste processo
_trava_pa = threading.Lock()


def _contar(delta: int) -> None:
    global _abertos
    with _trava_pa:
        _abertos = max(0, _abertos + delta)


def atualizar_lista_dispositivos() -> bool:
    """Reinicia o PortAudio para enxergar aparelhos ligados depois do app.

    O PortAudio monta a lista de dispositivos uma unica vez, no Pa_Initialize,
    e nao a atualiza sozinho. Como o VozFlow sobe junto com o Windows e o fone
    Bluetooth costuma ser ligado depois, sem isto o microfone salvo simplesmente
    nao existe para o processo: a gravacao cai no padrao do Windows e sai muda,
    sem erro nenhum. Foi exatamente o que aconteceu quando o fone estava
    desligado na hora em que o app subiu.

    So roda com nenhum stream aberto aqui - reiniciar o PortAudio com um stream
    vivo derruba o processo.
    """
    with _trava_pa:
        if _abertos:
            return False
        try:
            sd._terminate()
            sd._initialize()
            return True
        except Exception:  # noqa: BLE001
            return False


@contextlib.contextmanager
def entrada_contada(**kw):
    """sd.InputStream que conta como microfone aberto enquanto vive.

    Gravacoes fora do Recorder (a calibracao) tambem precisam entrar na conta:
    sem isso, uma ditada iniciada pela bandeja durante a calibracao reiniciava
    o PortAudio com este stream vivo - o que derruba o processo.
    """
    _contar(+1)
    try:
        with sd.InputStream(**kw) as stream:
            yield stream
    finally:
        _contar(-1)


def _entradas() -> list[tuple[int, dict]]:
    """(indice, info) de cada dispositivo que realmente grava."""
    return [(i, d) for i, d in enumerate(sd.query_devices())
            if d.get("max_input_channels", 0) > 0]


def nome_do_indice(indice: int) -> str | None:
    """Nome cru do dispositivo, ou None se esse indice nao grava (mais)."""
    for i, d in _entradas():
        if i == indice:
            return d["name"]
    return None


def _sem_numero_de_porta(nome: str) -> str:
    """'microfone (2- h510-pro)' -> 'microfone (h510-pro)'."""
    return re.sub(r"\(\d+-\s*", "(", nome)


def resolver_dispositivo(valor) -> int | None:
    """Traduz o que esta na config para um indice atual do PortAudio.

    A config guarda o NOME do microfone, nunca o indice: o PortAudio renumera
    a lista inteira quando um fone Bluetooth conecta ou o NVIDIA Broadcast
    liga, e o indice salvo passa a apontar para outro aparelho. Foi assim que
    um "input_device: 4" foi parar no "Mapeador de som - Output", que tem zero
    canais de entrada, e toda gravacao morria com "Unanticipated host error".

    Devolve None = microfone padrao do Windows, inclusive quando o aparelho
    salvo nao esta mais conectado.
    """
    if valor is None or valor == "":
        return None
    entradas = _entradas()

    # Indice cru continua aceito (config antiga, chamada interna), mas so vale
    # se aquele numero for mesmo uma entrada agora.
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor if any(i == valor for i, _ in entradas) else None

    alvo = " ".join(str(valor).split()).casefold()
    if not alvo:
        return None
    for rotular in (lambda d: d["name"], lambda d: nome_amigavel(d["name"])):
        for i, d in entradas:
            if " ".join(rotular(d).split()).casefold() == alvo:
                return i
    # O Windows renomeia o mesmo aparelho ("Microfone (H510-PRO)" vira
    # "Microfone (2- H510-PRO)") quando ele reconecta noutra porta USB. A
    # comparacao por substring abaixo NAO pegava esse caso - o "2- " fica no
    # meio do nome -, entao primeiro compara sem o numero da porta.
    # So se o casamento for unico: o Windows poe o "N- " justamente quando dois
    # aparelhos tem o mesmo nome, e ai nao da para saber qual e o salvo -
    # melhor o padrao do Windows (com aviso) do que um microfone qualquer.
    sem_porta = _sem_numero_de_porta(alvo)
    iguais = [i for i, d in entradas
              if _sem_numero_de_porta(" ".join(d["name"].split()).casefold()) == sem_porta]
    if len(iguais) == 1:
        return iguais[0]
    if iguais:
        return None
    for i, d in entradas:
        atual = " ".join(d["name"].split()).casefold()
        if len(alvo) > 8 and (alvo in atual or atual in alvo):
            return i
    return None


class Recorder:
    """Le o microfone em blocos de 100 ms e empilha numa fila thread-safe."""

    def __init__(self, device=None, samplerate: int = SAMPLE_RATE):
        self.samplerate = samplerate
        self.device = device            # nome do microfone, ou None = padrao
        self.aviso: str | None = None   # preenchido quando cai para o padrao
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self.last_error: str | None = None

    # -- ciclo de vida -------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            while not self._queue.empty():          # descarta sobras
                self._queue.get_nowait()
            self.aviso = None
            if not self.device:
                # Automatico: o PortAudio so le o microfone padrao do Windows ao
                # iniciar. Sem recarregar, um fone ligado depois - que o Windows
                # passa a usar como padrao - nunca chegava aqui (medido: 0,04 s).
                atualizar_lista_dispositivos()
            indice = resolver_dispositivo(self.device)
            if indice is None and self.device and atualizar_lista_dispositivos():
                indice = resolver_dispositivo(self.device)  # ligaram o fone agora
            if indice is None and self.device:
                self.aviso = ("Microfone salvo nao esta conectado; gravando "
                              "pelo padrao do Windows.")
            # Conta ANTES de abrir: entre abrir e contar, outra thread podia
            # reiniciar o PortAudio achando que nao havia microfone aberto.
            _contar(+1)
            try:
                try:
                    self._stream = self._abrir(indice)
                except Exception:  # noqa: BLE001
                    if indice is None:
                        raise
                    # Aparelho ocupado por outro programa ou recem-desconectado:
                    # melhor ditar pelo padrao do Windows do que nao ditar.
                    self._stream = self._abrir(None)
                    self.aviso = ("Nao consegui abrir o microfone salvo; gravando "
                                  "pelo padrao do Windows.")
                self._stream.start()
            except Exception:
                if self._stream is not None:
                    try:
                        self._stream.close()   # abriu mas nao iniciou: nao deixa vivo
                    except Exception:  # noqa: BLE001
                        pass
                self._stream = None
                _contar(-1)
                raise

    def _abrir(self, indice: int | None) -> sd.InputStream:
        return sd.InputStream(
            samplerate=self.samplerate,
            blocksize=BLOCK,
            channels=1,
            dtype="float32",
            device=indice,
            callback=self._callback,
        )

    def stop(self) -> None:
        with self._lock:
            if self._stream is None:
                return
            # Fone Bluetooth que caiu no meio da gravacao: o PortAudio levanta
            # aqui. Propagar matava a thread do motor com o app ainda dizendo
            # "Pronto". O close() vai num try proprio: sem ele, o _contar(-1)
            # liberaria reiniciar o PortAudio com este stream vivo - o que
            # derruba o processo (ver atualizar_lista_dispositivos).
            try:
                self._stream.stop()
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
            try:
                self._stream.close()
            except Exception as exc:  # noqa: BLE001
                self.last_error = self.last_error or str(exc)
            finally:
                self._stream = None
                _contar(-1)

    # -- dados ---------------------------------------------------------
    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        if status:
            self.last_error = str(status)
        self._queue.put(indata[:, 0].copy())

    def drain(self) -> np.ndarray:
        """Retorna tudo que chegou desde a ultima chamada (pode vir vazio)."""
        blocks: list[np.ndarray] = []
        while True:
            try:
                blocks.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not blocks:
            return np.empty(0, dtype=np.float32)
        return np.concatenate(blocks)


class SpeechDetector:
    """Diz se um bloco de audio contem fala.

    Usa o WebRTC VAD quando disponivel; senao cai para um limiar de energia
    com piso de ruido adaptativo (funciona bem para ditado com microfone perto).
    """

    def __init__(self, samplerate: int = SAMPLE_RATE, aggressiveness: int = 3):
        self.samplerate = samplerate
        self._vad = webrtcvad.Vad(aggressiveness) if webrtcvad else None
        self._noise = 0.004
        self._frame = int(samplerate * 0.02)  # 20 ms

    @property
    def backend(self) -> str:
        return "webrtcvad" if self._vad else "energia"

    def __call__(self, chunk: np.ndarray) -> bool:
        if chunk.size == 0:
            return False
        if self._vad is not None:
            return self._vad_speech(chunk)
        return self._energy_speech(chunk)

    def _vad_speech(self, chunk: np.ndarray) -> bool:
        pcm = np.clip(chunk, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16).tobytes()
        step = self._frame * 2  # bytes por frame de 20 ms
        total = voiced = 0
        for off in range(0, len(pcm) - step + 1, step):
            total += 1
            try:
                if self._vad.is_speech(pcm[off:off + step], self.samplerate):
                    voiced += 1
            except Exception:  # frame invalido -> ignora
                total -= 1
        return total > 0 and voiced / total >= 0.3

    def _energy_speech(self, chunk: np.ndarray) -> bool:
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        speech = rms > max(self._noise * 3.0, 0.006)
        if not speech:
            self._noise = 0.95 * self._noise + 0.05 * rms
        return speech


def rms_level(chunk: np.ndarray) -> float:
    """Nivel 0..1 para a barrinha do overlay."""
    if chunk.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(chunk))))
    return min(1.0, rms * 14.0)


def nome_amigavel(nome: str) -> str:
    """Alguns drivers Bluetooth devolvem o nome cru do recurso, tipo
    "Headset (@System32/drivers/bthhfenum.sys,#2;%1 Hands-Free%0 ;(AirPods))".
    Aqui sobra so "Headset AirPods".
    """
    nome = nome.replace("\r", " ").replace("\n", " ")
    if "@" in nome and ";" in nome:
        cauda = nome.rsplit(";", 1)[-1].strip(" ()")
        prefixo = nome.split("(", 1)[0].strip()
        nome = (prefixo + " " + cauda).strip() if cauda else prefixo
    return " ".join(nome.split())[:48]


def list_input_devices() -> list[tuple[int, str]]:
    """(indice, nome) de cada dispositivo de entrada disponivel."""
    return [(i, nome_amigavel(d["name"])) for i, d in _entradas()]


def entradas_para_menu() -> list[tuple[str, str]]:
    """(rotulo da tela, nome cru para gravar na config), sem repetidos.

    O nome cru e que vai para o config.json: e o unico identificador que
    sobrevive a lista do PortAudio ser renumerada.
    """
    saida: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for _, d in _entradas():
        rotulo = nome_amigavel(d["name"])
        if rotulo in vistos:
            continue
        vistos.add(rotulo)
        saida.append((rotulo, d["name"]))
    return saida
