"""Звук сцены «кубики» с эффектами из банка earshot (MIT, github.com/Leonxlnx/earshot).

    <venv с earshot>/bin/python sound_earshot.py scene.json out.wav

Таймлайн, музыка и сирена те же, что в sound_kubiki.py (в банке earshot сирены нет). Остальные эффекты
рендерятся из банка earshot по id, у каждого шага свой seed, чтобы шаги не звучали одинаково.
"""
import itertools
import json
import sys
import wave

import numpy as np
from earshot.forge import bank

import sound_kubiki as K

_seed = itertools.count(1)
USED = {}


def es(sound_id, gain, **kw):
    y, meta = bank.render(sound_id, seed=next(_seed), sr=K.SR, **kw)
    y = np.asarray(y, dtype=float)
    if y.ndim == 2:
        y = y.mean(axis=1 if y.shape[1] <= 2 else 0)
    USED[sound_id] = USED.get(sound_id, 0) + 1
    return gain * y / (np.max(np.abs(y)) or 1)


K.sfx_step = lambda soft=False: es('knock/plastic', 0.22 if soft else 0.45)
K.sfx_whoosh = lambda dur=0.6: es('whoosh_fast/crisp', 0.5, dur=max(0.3, dur), apex=max(0.15, dur / 2))
K.sfx_thump = lambda: es('impact/punch', 0.85)
K.sfx_clatter = lambda: es('knock/double', 0.5)
K.sfx_puff = lambda: es('whoosh_big/thump_airy', 0.4)
K.sfx_zing = lambda: es('shimmer/m0', 0.35)
K.sfx_cut = lambda: es('cut_hit/sub', 0.6)
K.sfx_sting = lambda up=True: es('mallet/up4' if up else 'mallet/marimba', 0.35)

if __name__ == '__main__':
    S = json.load(open(sys.argv[1]))
    mix, ev = K.build(S)
    st = np.stack([mix, mix * 0.97], 1)
    with wave.open(sys.argv[2], 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(K.SR)
        w.writeframes((st * 32767).astype('<i2').tobytes())
    json.dump(dict(events=ev, earshot_ids=USED), open(sys.argv[2].rsplit('.', 1)[0] + '.events.json', 'w'), indent=0)
    print('звук: %.1f с, эффектов %d, из earshot %s' % (len(mix) / K.SR, len(ev), USED))
