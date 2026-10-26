"""Mede a fluidez da escrita ao vivo com o VozFlow real (motor + digitacao).

Sem microfone nem teclado: um WAV entra em tempo real por um microfone falso,
e um teclado falso anota o instante de cada letra. O instante em que cada
palavra foi DITA vem do proprio Whisper (word_timestamps) sobre o audio
inteiro. E daqui que saem os numeros de docs/DESEMPENHO.md.

    .venv\\Scripts\\python -B ferramentas\\medir_fluidez.py <projeto> <audio.wav> <saida.json> [chave=valor ...]

  <projeto>     pasta do VozFlow a medir (permite comparar duas versoes, por
                exemplo uma copia de outro commit com `git worktree add`)
  <audio.wav>   16 kHz, mono, 16 bits
  chave=valor   sobrescreve a config, em JSON: partial_interval=0.3,
                nivel_fala=0.01 ...

Saida (JSON): primeira_palavra_s, atraso_mediano_s, atraso_p90_s,
atraso_max_s (de quando a palavra termina de ser dita ate a ultima letra dela
aparecer), maior_engasgo_s, palavras_diferentes_da_verdade, texto_digitado,
a linha do tempo das previas (diag) e a duracao de cada transcricao.

Usa a GPU: com outro programa usando a placa (inclusive o VozFlow instalado
ditando), os atrasos variam. Rode cada configuracao pelo menos 3 vezes e,
para comparar versoes, intercale as rodadas.
"""
import difflib
import json
import os
import sys
import tempfile
import threading
import time
import wave

os.environ["VOZFLOW_CONFIG_DIR"] = tempfile.mkdtemp(prefix="vozflow-fluidez-")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.pop("VOZFLOW_DEBUG", None)
PROJETO, WAV, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, PROJETO)

import numpy as np  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from vozflow import app as modulo_app  # noqa: E402
from vozflow import config, inserter, texto  # noqa: E402

SR = 16000
with wave.open(WAV, "rb") as w:
    fala = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
INICIO = 0.5
audio = np.concatenate([np.zeros(int(INICIO * SR), np.float32), fala, np.zeros(SR * 2, np.float32)])


class Mic:
    aviso = None
    device = None

    def __init__(self):
        self.t0 = None
        self.pos = 0

    def start(self):
        self.t0 = time.monotonic()

    def stop(self):
        pass

    def drain(self):
        if self.t0 is None:
            return np.empty(0, np.float32)
        ate = min(len(audio), int((time.monotonic() - self.t0) * SR) // 1600 * 1600)
        b, self.pos = audio[self.pos:ate], max(self.pos, ate)
        return b


class Teclado:
    def __init__(self):
        self.eventos = []          # (instante, texto)
        self.trava = threading.Lock()

    def write(self, t, delay=0):  # noqa: ARG002
        with self.trava:
            self.eventos.append((time.monotonic(), t))

    def send(self, _c): pass
    def is_pressed(self, _t): return False
    def release(self, _t): pass
    def add_hotkey(self, *_a, **_k): pass
    def unhook_all_hotkeys(self): pass


class Janela:
    def atual(self): return 0x100
    def alvo_valido(self, h): return True
    def existe(self, h): return True
    def em_foco(self, h): return True
    def restaurar(self, h, espera=1.2): return True
    def nome_curto(self, h, limite=38): return "teste"
    def trazer_para_frente(self, h): return True


class Overlay:
    def __init__(self, cfg): pass
    def __getattr__(self, _n): return lambda *a, **k: None


class Guarda:
    def vigiar(self, c): return None
    def liberado(self, s): return True
    def limpar(self): pass


teclado = Teclado()
modulo_app.keyboard = teclado
inserter.keyboard = teclado
modulo_app.janela = Janela()
modulo_app.Overlay = Overlay
modulo_app.GuardaNumerico = Guarda
modulo_app._som = lambda _n: None
import pyperclip  # noqa: E402

pyperclip.copy = lambda _t: None      # nunca toca a area de transferencia de verdade
pyperclip.paste = lambda: ""

cfg = config.Config(dict(config.DEFAULTS))
cfg.update(sounds=False, log_transcricoes=False, travar_janela=True, nivel_fala=0.0)
for par in sys.argv[4:]:
    k, v = par.split("=", 1)
    cfg[k] = json.loads(v)
config.load = lambda: cfg

qapp = QtWidgets.QApplication([])
vf = modulo_app.VozFlow(qapp)
mic = Mic()
vf.engine._rec = mic

# linha do tempo: cada previa (instante, palavras na previa, palavras liberadas)
# e cada fim de trecho; e quanto durou cada transcricao
diag, tempos_tr = [], []
_est, _resto, _tr = vf.engine._emitir_estavel, vf.engine._emitir_resto, vf.engine._transcrever


def est(p):
    n = len(vf.engine._emitido)
    _est(p)
    diag.append(("previa", round(time.monotonic() - mic.t0, 2), len(p.split()), len(vf.engine._emitido) - n))


def resto(t):
    n = len(vf.engine._emitido)
    diag.append(("fim_trecho", round(time.monotonic() - mic.t0, 2), len(t.split()), len(t.split()) - n))
    _resto(t)


def tr(audio_, final, **kw):
    t0 = time.monotonic()
    try:
        return _tr(audio_, final, **kw)
    finally:
        tempos_tr.append((round(t0 - (mic.t0 or t0), 1), round(time.monotonic() - t0, 2),
                          round(audio_.size / SR, 1), final))


vf.engine._emitir_estavel, vf.engine._emitir_resto, vf.engine._transcrever = est, resto, tr

estado = {"pronto": False, "fim": False}
vf.engine.ready.connect(lambda _b: estado.update(pronto=True))
vf.sig_entregue.connect(lambda *_a: estado.update(fim=True))


def esperar(cond, limite):
    fim = time.monotonic() + limite
    while time.monotonic() < fim and not cond():
        qapp.processEvents()
        time.sleep(0.005)
    return cond()


assert esperar(lambda: estado["pronto"], 180), "modelo nao carregou"
vf.iniciar()
esperar(lambda: False, len(audio) / SR)            # fala inteira, em tempo real
t_parar = time.monotonic()
vf.parar()
esperar(lambda: estado["fim"], 60)
esperar(lambda: False, 0.3)

# verdade: quando cada palavra foi dita
segs, _ = vf.engine._model.transcribe(audio, language="pt", beam_size=5, word_timestamps=True,
                                      condition_on_previous_text=False)
verdade = [(w.word.strip(), w.end) for s in segs for w in s.words if w.word.strip()]

# instante de cada palavra digitada = instante da letra que a completou
letras = [(t - mic.t0, c) for t, s in teclado.eventos for c in s]
digitadas, atual, t_ult = [], "", None
for t, c in letras + [(None, " ")]:
    if c.isspace():
        if atual:
            digitadas.append((atual, t_ult))
        atual = ""
    else:
        atual += c
        t_ult = t

kv = [texto._chave(w) for w, _ in verdade]
kd = [texto._chave(w) for w, _ in digitadas]
blocos = difflib.SequenceMatcher(None, kv, kd, autojunk=False).get_opcodes()
atrasos = [digitadas[b][1] - verdade[a][1]
           for tag, i1, i2, j1, j2 in blocos if tag == "equal"
           for a, b in zip(range(i1, i2), range(j1, j2))]
erradas = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in blocos if tag != "equal")
tempos_escrita = sorted(t for t, _ in letras)
fala_fim = INICIO + len(fala) / SR
engasgos = [b - a for a, b in zip(tempos_escrita, tempos_escrita[1:]) if a < fala_fim]
r = {
    "config_extra": sys.argv[4:],
    "palavras_ditas": len(verdade), "palavras_digitadas": len(digitadas),
    "palavras_diferentes_da_verdade": erradas,
    "primeira_palavra_s": round(digitadas[0][1] - verdade[0][1], 2) if digitadas else None,
    "atraso_mediano_s": round(float(np.median(atrasos)), 2) if atrasos else None,
    "atraso_p90_s": round(float(np.percentile(atrasos, 90)), 2) if atrasos else None,
    "atraso_max_s": round(float(max(atrasos)), 2) if atrasos else None,
    "maior_engasgo_s": round(max(engasgos), 2) if engasgos else None,
    "engasgos_acima_0_7s": sum(p > 0.7 for p in engasgos),
    "texto_digitado": "".join(t for _, t in teclado.eventos),
    "diag": diag,
    "tempos_transcricao": tempos_tr,
    "parar_ate_fim_s": round(max(t for t, _ in teclado.eventos) - t_parar, 2) if teclado.eventos else None,
}
with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(r, f, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in r.items() if k not in ("diag", "tempos_transcricao")}, ensure_ascii=False),
      flush=True)
vf._fila.put(None)
vf.engine.cmd_quit()
vf.engine.wait(5000)
os._exit(0)
