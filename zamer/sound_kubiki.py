"""Звук для сцены «кубики» по таймлайну обработчика: своя музыка и свои эффекты, всё синтезом в коде.

    python3 sound_kubiki.py scene.json out.wav [--fps 12]

Музыка своя (написана здесь же): погоня в ля миноре, 132 удара в минуту, бас, барабаны, щипковая тема.
Эффекты ставятся на моменты сцены: шаги по шипам на каждый шаг походки (та же частота, что в рендере),
свист на прыжок и перелезание, удар на приземление и падение, сирена на alarm, хлопок пыли, удар на склейке.
Пишет out.wav и out.events.json (что и когда поставлено).
"""
import json
import math
import sys
import wave

import numpy as np

SR = 48000
rng = np.random.default_rng(5)


def env(n, a, d):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d)
    return e


def tone(f, dur, kind='sine'):
    t = np.arange(int(dur * SR)) / SR
    ph = 2 * np.pi * np.cumsum(np.full(len(t), f) if np.isscalar(f) else f) / SR
    if kind == 'saw':
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if kind == 'square':
        return np.sign(np.sin(ph))
    return np.sin(ph)


def lp(x, fc):
    a = math.exp(-2 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def bp_noise(n, lo, hi):
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, n)


def norm(x):
    m = np.max(np.abs(x)) or 1.0
    return x / m


# ---------- эффекты ----------
def sfx_step(soft=False):
    n = int(0.06 * SR)
    x = norm(bp_noise(n, 2500, 7000)) * env(n, 0.001, 0.012)
    x += 0.5 * tone(1900, 0.06) * env(n, 0.0005, 0.008)
    return x * (0.25 if soft else 0.5)


def sfx_whoosh(dur=0.6):
    n = int(dur * SR)
    t = np.arange(n) / n
    sh = np.sin(np.pi * t) ** 2
    x = norm(bp_noise(n, 300, 3000)) * sh
    return 0.45 * x


def sfx_thump():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 120 * np.exp(-t * 18) + 45
    x = tone(f, 0.35) * env(n, 0.002, 0.09)
    x += 0.4 * norm(bp_noise(n, 1500, 5000)) * env(n, 0.001, 0.02)
    return 0.9 * x


def sfx_clatter():
    out = np.zeros(int(0.5 * SR))
    for k in range(6):
        s = sfx_step() * rng.uniform(0.4, 1.0)
        i = int(rng.uniform(0, 0.35) * SR)
        out[i:i + len(s)] += s[:len(out) - i]
    return out


def sfx_puff():
    n = int(0.7 * SR)
    return 0.35 * norm(lp(bp_noise(n, 80, 2000), 900)) * env(n, 0.03, 0.2)


def sfx_zing():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    return 0.3 * tone(2400 + 1800 * t, 0.5) * env(n, 0.002, 0.12)


def sfx_siren(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.where((t * 4).astype(int) % 2 == 0, 960.0, 770.0)
    x = 0.6 * tone(f, dur, 'square') + 0.4 * tone(f, dur)
    return 0.16 * lp(x, 3000) * np.minimum(1, t / 0.05)


def sfx_cut():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    x = tone(60 * np.exp(-t * 4) + 30, 0.4) * env(n, 0.002, 0.15)
    return 0.6 * x


def sfx_sting(up=True):
    out = np.zeros(int(0.5 * SR))
    for k, nt in enumerate((0, 4, 7) if up else (7, 3, 0)):
        f = 660 * 2 ** (nt / 12)
        n = int(0.25 * SR)
        s = tone(f, 0.25) * env(n, 0.002, 0.08) * 0.25
        i = int(k * 0.07 * SR)
        out[i:i + n] += s
    return out


# ---------- музыка ----------
def music(L):
    bpm = 132
    beat = 60 / bpm
    n = int(L * SR) + SR
    out = np.zeros(n)

    def put(x, t, g=1.0):
        i = int(t * SR)
        if i >= n:
            return
        j = min(n, i + len(x))
        out[i:j] += g * x[:j - i]

    A = 55.0
    bass = [0, 0, 3, 0, -2, 0, 7, 5]  # ля минор, восьмые
    lead = [12, None, 15, 12, None, 10, 12, None, 19, None, 17, 15, None, 12, 10, None]
    t, k = 0.0, 0
    while t < L + beat:
        f = A * 2 ** (bass[k % 8] / 12)
        nb = int(beat / 2 * SR)
        put(lp(tone(f, beat / 2, 'saw'), 600) * env(nb, 0.005, 0.12), t, 0.35)
        b = k % 8
        if b in (0, 4):
            m = int(0.25 * SR); tt = np.arange(m) / SR
            put(tone(110 * np.exp(-tt * 30) + 40, 0.25) * env(m, 0.001, 0.08), t, 0.7)
        if b in (2, 6):
            m = int(0.2 * SR)
            put(norm(bp_noise(m, 1200, 6000)) * env(m, 0.001, 0.05), t, 0.25)
        m = int(0.05 * SR)
        put(norm(bp_noise(m, 7000, 12000)) * env(m, 0.0005, 0.01), t, 0.08)
        ln = lead[k % 16]
        if ln is not None and k >= 8:
            f2 = A * 4 * 2 ** (ln / 12)
            m = int(0.3 * SR)
            put((tone(f2, 0.3) + 0.3 * tone(2 * f2, 0.3)) * env(m, 0.002, 0.1), t, 0.12)
        t += beat / 2
        k += 1
    return out[:int(L * SR)]


GAIT = dict(walk=2.0, run=3.2, sneak=1.4)
VMIN = dict(walk=1.3, sneak=0.9, run=2.4)  # как в render_kubiki.py
STEPS_PER_CELL = 1.3


def build(S, with_music=True):
    L = S['len']
    n = int(L * SR)
    fx = np.zeros(n)
    ev = []

    def put(x, t, what):
        i = int(max(0, t) * SR)
        if i >= n:
            return
        j = min(n, i + len(x))
        fx[i:j] += x[:j - i]
        ev.append(dict(t=round(t, 3), sfx=what))

    for a in S['acts']:
        d = a['t1'] - a['t0']
        if a['act'] in GAIT:
            # шаги совпадают с ногами в рендере: шаг на каждые полшага пути, путь проходится не медленнее VMIN,
            # нулевой путь — шагов нет (render_kubiki.py, _hero_state)
            pts = a.get('path') or ([a['from'], a['dest']] if a.get('dest') else [])
            plen = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) if len(pts) > 1 else 0.0
            if plen < 0.05:
                continue
            move = min(d, plen / VMIN[a['act']])
            nstep = int(plen * 2 * STEPS_PER_CELL)
            for k in range(1, nstep + 1):
                put(sfx_step(soft=a['act'] == 'sneak'), a['t0'] + move * k / (plen * 2 * STEPS_PER_CELL), 'step')
        elif a['act'] in ('climb', 'jump'):
            w = sfx_whoosh(min(0.8, d))
            put(w, a['t0'] + d / 2 - len(w) / SR / 2, 'whoosh')
            put(sfx_thump() * 0.6, a['t1'], 'land')
        elif a['act'] == 'fall':
            put(sfx_thump(), a['t0'] + 0.4 * d, 'fall')
            put(sfx_clatter() * 0.6, a['t0'] + 0.4 * d + 0.03, 'clatter')
        elif a['act'] == 'wave':
            put(sfx_sting(True), a['t0'], 'sting')
    for f in S['fx']:
        if f['fx'] == 'dust':
            put(sfx_puff(), f['t'], 'puff')
        elif f['fx'] == 'crash':
            put(sfx_thump(), f['t'], 'crash'); put(sfx_clatter(), f['t'], 'clatter')
        elif f['fx'] == 'flash':
            put(sfx_zing(), f['t'], 'zing')
        elif f['fx'] == 'alarm':
            put(sfx_siren(L - f['t']), f['t'], 'siren')
    for c in S['cams']:
        if c['t'] > 0:
            put(sfx_cut(), c['t'], 'cut')
    for fa in S['faces']:
        if fa['face'] in ('surprised', 'scared') and fa['t'] > 0:
            put(sfx_sting(False), fa['t'], 'sting')
    if not with_music:
        return fx, ev
    mus = music(L)
    # музыка уступает эффектам: проседает на 5 дБ там, где громкий эффект
    envfx = np.convolve(np.abs(fx), np.ones(2400) / 2400, mode='same')
    duck = 1 - 0.44 * np.clip(envfx / 0.08, 0, 1)
    mix = mus * duck + fx
    fade = np.ones(n)
    m = int(0.3 * SR)
    fade[-m:] = np.linspace(1, 0, m)
    mix = mix * fade
    mix = 0.89 * mix / (np.max(np.abs(mix)) or 1)
    return mix, ev


if __name__ == '__main__':
    S = json.load(open(sys.argv[1]))
    mix, ev = build(S)
    st = np.stack([mix, mix * 0.97], 1)
    with wave.open(sys.argv[2], 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype('<i2').tobytes())
    json.dump(ev, open(sys.argv[2].rsplit('.', 1)[0] + '.events.json', 'w'), indent=0)
    print('звук: %.1f с, эффектов %d' % (len(mix) / SR, len(ev)))
