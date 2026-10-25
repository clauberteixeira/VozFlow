"""Sinais sinteticos de voz e ruido para os testes (sem microfone nem gravacao real)."""
import numpy as np


def lfilter(b, a, x):
    x = np.asarray(x, float)
    y = np.zeros_like(x)
    b = list(b) + [0] * (3 - len(b)); a = list(a) + [0] * (3 - len(a))
    x1 = x2 = y1 = y2 = 0.0
    for i in range(x.size):
        xi = x[i]
        yi = (b[0] * xi + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2) / a[0]
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return y


def banda(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(x.size, 1 / 16000)
    m = np.ones_like(f)
    if lo: m[f < lo] = 0
    if hi: m[f > hi] = 0
    return np.fft.irfft(X * m, x.size)

SR = 16000
rng = np.random.default_rng(1)


def ressoador(x, f, bw):
    r = np.exp(-np.pi * bw / SR)
    th = 2 * np.pi * f / SR
    a = [1, -2 * r * np.cos(th), r * r]
    return lfilter([1 - r], a, x)


def vogal(dur, f0=120.0, formantes=((700, 110), (1200, 120), (2600, 160)), jitter=0.0,
          aspir=0.0, amp=0.12):
    n = int(dur * SR)
    src = np.zeros(n)
    t = 0.0
    while t < n:
        src[int(t)] = 1.0
        per = SR / f0 * (1 + jitter * rng.standard_normal())
        t += max(per, 10)
    # glottal-ish lowpass
    src = lfilter([1], [1, -0.97], src)
    src = src / (np.std(src) + 1e-12)
    if aspir:
        src = (1 - aspir) * src + aspir * rng.standard_normal(n)
    y = src
    out = np.zeros(n)
    for f, bw in formantes:
        out += ressoador(y, f, bw)
    env = np.ones(n)
    k = min(n // 4, int(0.015 * SR))
    if k:
        env[:k] = np.linspace(0, 1, k)
        env[-k:] = np.linspace(1, 0, k)
    out = out * env
    return (amp * out / (np.max(np.abs(out)) + 1e-12)).astype(np.float32)


def fricativa(dur, amp=0.04):
    n = int(dur * SR)
    y = banda(rng.standard_normal(n), lo=3000)
    return (amp * y / (np.std(y) + 1e-12)).astype(np.float32)


def silencio(dur, amp=2e-4):
    return (amp * rng.standard_normal(int(dur * SR))).astype(np.float32)


def palavra_sim(**kw):
    return np.concatenate([fricativa(0.10), vogal(0.20, formantes=((300, 80), (2300, 120), (3000, 160)), **kw)])


def palavra_ok(**kw):
    return np.concatenate([vogal(0.10, formantes=((450, 80), (800, 100), (2500, 150)), **kw), silencio(0.05),
                           fricativa(0.03), vogal(0.17, formantes=((400, 80), (2100, 120), (2800, 150)), **kw)])


def palavra_obrigado(**kw):
    p = []
    for d in (0.10, 0.14, 0.12, 0.16):
        p += [vogal(d, **kw), silencio(0.04)]
    return np.concatenate(p)


def frase(dur=2.0, **kw):
    p = []
    tot = 0
    while tot < dur:
        p += [vogal(0.15, **kw), fricativa(0.05)]
        tot += 0.2
    return np.concatenate(p)


def banda_telefone(x):
    # HFP/CVSD: 300-3400 Hz (8 kHz de amostragem), reamostrado para 16 kHz
    return banda(x, lo=300, hi=3400).astype(np.float32)
