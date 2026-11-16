"""Серия «кубики» целиком по цепочке из замера: язык v3.2, DeepSeek-V4-Flash, исправление, 3 попытки, судья.

    KUBIKI_BACKEND=api python3 series.py programs     программы сцен (out/programs/, picks.json)
    python3 series.py render                             кадры каждой сцены, Eevee 1080p, 12 к/с ($KUBIKI_FRAMES/seriya1)
    <venv earshot>/bin/python series.py sound            эффекты по сценам (earshot) + своя музыка на всю серию
    KUBIKI_BACKEND=api python3 series.py dialogue       реплики в пузырях моделью (out/programs/NN_say.json)
    python3 series.py bubbles                            пузыри поверх кадров ($FRAMES/NN_b), нужен heads.json рендера
    python3 series.py assemble                           титры, склейка, звук -> out/seriya1.mp4
    python3 series.py sheet                              контактный лист серии для проверки на глаз

Сценарий (описания сцен) — episode1.json. Программы пишет модель, руками они не правятся.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ZAMER = os.path.join(os.path.dirname(HERE), 'zamer')
sys.path.insert(0, ZAMER)
os.chdir(ZAMER)

# номер серии — второй аргумент: python3 series.py render 2 (по умолчанию 1)
NUM = sys.argv[2] if len(sys.argv) > 2 else '1'
EPDIR = HERE if NUM == '1' else os.path.join(os.path.dirname(HERE), 'seriya' + NUM)
EP = json.load(open(os.path.join(EPDIR, 'episode%s.json' % NUM)))
OUT = os.path.join(EPDIR, 'out')
NAME = 'seriya' + NUM
PROG = os.path.join(OUT, 'programs')
FRAMES = os.path.join(os.path.expanduser(os.environ.get('KUBIKI_FRAMES', '~/kubiki-frames')), NAME)
BL = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
FPS = 12
TITLE_S = 4.0
FONT = os.environ.get('KUBIKI_FONT', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
NL = chr(10)


def programs():
    import judge as J
    import kubiki_core31 as K31
    from run3 import chat, SPEC32, TASK
    os.makedirs(PROG, exist_ok=True)
    picks = {}
    pf = os.path.join(OUT, 'picks.json')
    if os.path.exists(pf):
        picks = json.load(open(pf))
    for sc in EP['scenes']:
        sid = '%02d' % sc['id']
        if sid in picks:
            continue
        ctext, _ = chat(J.SPEC + NL + NL + 'ОПИСАНИЕ СЦЕНЫ: ' + sc['text'])
        open(os.path.join(PROG, sid + '_checks.txt'), 'w').write(ctext)
        items = J.parse(ctext)[0]
        cands = []
        for k in (1, 2, 3):
            txt, _ = chat(SPEC32 + NL + TASK + NL + NL + 'СЦЕНА: ' + sc['text'])
            S, errs = K31.compile_program(txt)
            fixed = False
            if errs:
                txt, _ = chat(SPEC32 + NL + TASK + NL + NL + 'СЦЕНА: ' + sc['text'] + NL + NL + 'ТВОЯ ПРОГРАММА:' +
                              NL + txt + NL + NL + 'СБОРЩИК НЕ ПРИНЯЛ СТРОКИ:' + NL + NL.join(errs) + NL + NL +
                              'Исправь эти строки словами из языка и выведи программу целиком, только строки программы.')
                S, errs = K31.compile_program(txt)
                fixed = True
            open(os.path.join(PROG, '%s_try%d.kub' % (sid, k)), 'w').write(txt)
            fails = J.judge(S, items) if not errs else None
            cands.append(dict(k=k, errors=errs, fixed=fixed, fails=fails, S=S))
            if fails == []:
                break  # судья принял: дальше не тратим вызовы
        good = [c for c in cands if c['fails'] == []]
        okc = [c for c in cands if c['fails'] is not None]
        pick = good[0] if good else (min(okc, key=lambda c: len(c['fails'])) if okc else None)
        if pick is None:
            picks[sid] = dict(ok=False, why='сборщик не принял ни одной попытки', errors=cands[-1]['errors'][:3])
        else:
            json.dump(pick['S'], open(os.path.join(PROG, sid + '.json'), 'w'), default=list, ensure_ascii=False)
            picks[sid] = dict(ok=True, judge_ok=pick['fails'] == [], judge_fails=pick['fails'], try_=pick['k'],
                              tries=len(cands), fixed=pick['fixed'], len=pick['S']['len'])
        print(sid, picks[sid], flush=True)
        json.dump(picks, open(pf, 'w'), ensure_ascii=False, indent=1)


ROLES = dict(kid='ребёнок', citizen='прохожий', cop='полицейский', thief='вор', prisoner='заключённый',
             guard='охранник')


def dialogue():
    """Реплики: модель дописывает к готовой сцене строки say; код проверяет, при ошибках один круг исправления."""
    import dialogue as D
    from run3 import chat
    roles = dict(ROLES, **EP.get('roles', {}))
    before = []
    for sc in EP['scenes']:
        sid = '%02d' % sc['id']
        jp = os.path.join(PROG, sid + '.json')
        sp = os.path.join(PROG, sid + '_say.json')
        if not os.path.exists(jp):
            continue
        S = json.load(open(jp))
        if os.path.exists(sp):
            says = json.load(open(sp))['says']
        else:
            pr = D.prompt(S, sc['text'], roles, EP.get('note', ''), before)
            txt, _ = chat(pr)
            says, errs = D.parse(txt, S, before)
            fixed = False
            if errs:
                txt, _ = chat(pr + NL + NL + 'ТВОИ СТРОКИ:' + NL + txt + NL + NL + 'НЕ ПРИНЯТЫ:' + NL + NL.join(errs) +
                              NL + NL + 'Исправь и выведи строки say целиком.')
                says, errs = D.parse(txt, S, before)
                fixed = True
            open(os.path.join(PROG, sid + '_say.txt'), 'w').write(txt)
            json.dump(dict(says=says, errors=errs, fixed=fixed), open(sp, 'w'), ensure_ascii=False, indent=1)
        before += ['%s: %s' % (roles.get(s_['hero'], s_['hero']), s_['text']) for s_ in says]
        print(sid, ' | '.join('%s «%s» %g-%g' % (s_['hero'], s_['text'], s_['t0'], s_['t1']) for s_ in says) or '—',
              flush=True)


BUBBLE_FONT = os.environ.get('KUBIKI_BUBBLE_FONT', '/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf')


def bubbles():
    """Кадры с пузырями пишутся в $FRAMES/NN_b целиком (на кадры без реплик ставятся ссылки), исходные кадры не трогаются."""
    import dialogue as D
    for sid, p in sorted(picks().items()):
        sp = os.path.join(PROG, sid + '_say.json')
        hp = os.path.join(FRAMES, sid, 'heads.json')
        if not p['ok'] or not os.path.exists(sp) or not os.path.exists(hp):
            continue
        says = json.load(open(sp))['says']
        if not says:
            continue
        n = int(round(p['len'] * FPS))
        bf = D.bubble_frames(says, json.load(open(hp)), FPS, n)
        od = os.path.join(FRAMES, sid + '_b')
        os.makedirs(od, exist_ok=True)
        for f in range(n):
            src = os.path.join(FRAMES, sid, 'f%04d.png' % f)
            dst = os.path.join(od, 'f%04d.png' % f)
            if f in bf:
                D.draw_bubbles(src, dst, bf[f], BUBBLE_FONT)
            else:
                if os.path.lexists(dst):
                    os.remove(dst)
                os.symlink(src, dst)  # кадр без пузыря: ссылка, а не копия (кадры серии — гигабайты)
        print(sid, 'пузырей на кадрах', len(bf), flush=True)


def frames_dir(sid):
    b = os.path.join(FRAMES, sid + '_b')
    return b if os.path.exists(os.path.join(b, 'f0000.png')) else os.path.join(FRAMES, sid)


def picks():
    return json.load(open(os.path.join(OUT, 'picks.json')))


def place_arg(sid):
    sc = next(s for s in EP['scenes'] if '%02d' % s['id'] == sid)
    return ['--place', sc['place']] if sc.get('place') else []


def render():
    for sid, p in sorted(picks().items()):
        if not p['ok']:
            continue
        od = os.path.join(FRAMES, sid)
        n = int(round(p['len'] * FPS))
        if os.path.exists(os.path.join(od, 'f%04d.png' % (n - 1))):
            continue
        subprocess.run([BL, '-b', '--factory-startup', '--python', os.path.join(ZAMER, 'render_kubiki.py'), '--',
                        '--scene', os.path.join(PROG, sid + '.json'), '--out', od, '--res', '1920x1080',
                        '--samples', '32'] + place_arg(sid), capture_output=True)
        print(sid, 'кадров', n, flush=True)


def timeline():
    t, out = TITLE_S, []
    for sid, p in sorted(picks().items()):
        if p['ok']:
            mood = next(s['mood'] for s in EP['scenes'] if '%02d' % s['id'] == sid)
            L = int(round(p['len'] * FPS)) / FPS
            out.append((sid, t, L, mood))
            t += L
    return out, t + TITLE_S


def episode_music(total, segs):
    """Своя музыка на всю серию: один темп, слои по настроению сцены (calm, chase, warm)."""
    import numpy as np
    import sound_kubiki as K
    SR = K.SR
    n = int(total * SR) + SR
    out = np.zeros(n)

    def put(x, t, g):
        i = int(t * SR)
        j = min(n, i + len(x))
        if i < n:
            out[i:j] += g * x[:j - i]

    def mood_at(t):
        for sid, t0, L, m in segs:
            if t0 <= t < t0 + L:
                return m
        return 'title'

    beat = 60 / 132
    A = 55.0
    minor = [0, 0, 3, 0, -2, 0, 7, 5]
    lead = [12, None, 15, 12, None, 10, 12, None, 19, None, 17, 15, None, 12, 10, None]
    warm_prog = [3, 3, 10, 10, 8, 8, 5, 5]   # до, соль, фа, ре от ля
    t, k = 0.0, 0
    while t < total:
        m = mood_at(t)
        b8 = k % 8
        nb = int(beat / 2 * SR)
        if m in ('chase', 'calm', 'title'):
            if m == 'chase' or b8 % 2 == 0:
                f = A * 2 ** (minor[b8] / 12)
                put(K.lp(K.tone(f, beat / 2, 'saw'), 600 if m == 'chase' else 350) * K.env(nb, 0.005, 0.12), t,
                    0.33 if m == 'chase' else 0.22)
        if m == 'warm':
            f = A * 2 ** (warm_prog[(k // 8) % 8] / 12)
            if b8 % 2 == 0:
                put(K.lp(K.tone(f, beat, 'saw'), 400) * K.env(int(beat * SR), 0.01, 0.25), t, 0.22)
            arp = [0, 4, 7, 12, 7, 4, 0, 7]
            f2 = f * 4 * 2 ** (arp[b8] / 12)
            mm = int(0.4 * SR)
            put((K.tone(f2, 0.4) + 0.25 * K.tone(3 * f2, 0.4)) * K.env(mm, 0.002, 0.12), t, 0.10)
        if m == 'chase':
            if b8 in (0, 4):
                mm = int(0.25 * SR)
                tt = np.arange(mm) / SR
                put(K.tone(110 * np.exp(-tt * 30) + 40, 0.25) * K.env(mm, 0.001, 0.08), t, 0.6)
            if b8 in (2, 6):
                mm = int(0.2 * SR)
                put(K.norm(K.bp_noise(mm, 1200, 6000)) * K.env(mm, 0.001, 0.05), t, 0.22)
            ln = lead[k % 16]
            if ln is not None:
                f2 = A * 4 * 2 ** (ln / 12)
                mm = int(0.3 * SR)
                put((K.tone(f2, 0.3) + 0.3 * K.tone(2 * f2, 0.3)) * K.env(mm, 0.002, 0.1), t, 0.10)
        if m in ('chase', 'calm'):
            mm = int(0.05 * SR)
            put(K.norm(K.bp_noise(mm, 7000, 12000)) * K.env(mm, 0.0005, 0.01), t, 0.07 if m == 'chase' else 0.04)
        t += beat / 2
        k += 1
    return out[:int(total * SR)]


def sound():
    import numpy as np
    import wave
    import sound_earshot  # noqa: F401  подменяет эффекты на банк earshot
    import sound_kubiki as K
    segs, total = timeline()
    SR = K.SR
    fx = np.zeros(int(total * SR) + SR)
    events = []
    for sid, t0, L, mood in segs:
        S = json.load(open(os.path.join(PROG, sid + '.json')))
        x, ev = K.build(S, with_music=False)
        i = int(t0 * SR)
        fx[i:i + len(x)] += x[:len(fx) - i]
        events += [dict(scene=sid, t=round(t0 + e['t'], 3), sfx=e['sfx']) for e in ev]
    fx = fx[:int(total * SR)]
    mus = episode_music(total, segs)
    envfx = np.convolve(np.abs(fx), np.ones(2400) / 2400, mode='same')
    duck = 1 - 0.44 * np.clip(envfx / 0.08, 0, 1)
    mix = mus * duck + fx
    m = int(1.0 * SR)
    mix[-m:] *= np.linspace(1, 0, m)
    mix = 0.89 * mix / (np.max(np.abs(mix)) or 1)
    st = np.stack([mix, mix * 0.97], 1)
    with wave.open(os.path.join(FRAMES, NAME + '.wav'), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype('<i2').tobytes())
    json.dump(events, open(os.path.join(OUT, 'sound_events.json'), 'w'), indent=0)
    print('звук %.1f с, эффектов %d' % (total, len(events)))


def card(text, sub, path):
    vf = ("drawtext=fontfile='%s':text='%s':fontcolor=0x2b2b2b:fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2-60,"
          "drawtext=fontfile='%s':text='%s':fontcolor=0x555555:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2+70,"
          "fade=t=in:st=0:d=0.5,fade=t=out:st=%.1f:d=0.5") % (FONT, text, FONT, sub, TITLE_S - 0.5)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'color=c=0xe9e4da:s=1920x1080:d=%.1f:r=24' % TITLE_S, '-vf', vf, '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', path], check=True)


def assemble():
    segs, total = timeline()
    tmp = os.path.join(FRAMES, '_parts')
    os.makedirs(tmp, exist_ok=True)
    parts = [os.path.join(tmp, '00_title.mp4')]
    card('Кубики', EP.get('subtitle', 'Серия 1. Побег'), parts[0])
    for sid, t0, L, mood in segs:
        p = os.path.join(tmp, sid + '.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i',
                        os.path.join(frames_dir(sid), 'f%04d.png'), '-t', '%.3f' % L,
                        '-r', '24', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', p], check=True)
        parts.append(p)
    endp = os.path.join(tmp, '99_end.mp4')
    card('Конец', 'Программы сцен написал DeepSeek-V4-Flash на языке кубиков', endp)
    parts.append(endp)
    lst = os.path.join(tmp, 'list.txt')
    open(lst, 'w').write(NL.join("file '%s'" % p for p in parts))
    os.makedirs(OUT, exist_ok=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-i', os.path.join(FRAMES, NAME + '.wav'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '21',
                    '-c:a', 'aac', '-b:a', '160k', '-shortest', os.path.join(OUT, NAME + '.mp4')], check=True)
    print('серия', os.path.join(OUT, NAME + '.mp4'), '%.1f с' % total)


def sheet():
    rows = []
    for sid, t0, L, mood in timeline()[0]:
        n = int(round(L * FPS))
        rows.append([os.path.join(frames_dir(sid), 'f%04d.png' % f) for f in (int(n * 0.2), int(n * 0.55), int(n * 0.9))])
    inputs, filt = [], []
    for i, row in enumerate(rows):
        for p in row:
            inputs += ['-i', p]
        filt.append('[%d][%d][%d]hstack=3,scale=960:-1,drawtext=fontfile=%s:text=%d:x=10:y=8:fontsize=36:'
                    'fontcolor=red[r%d]' % (3 * i, 3 * i + 1, 3 * i + 2, FONT.replace(' ', '\\\\ '), i + 1, i))
    half = (len(rows) + 1) // 2
    filt.append(''.join('[r%d]' % i for i in range(half)) + 'vstack=%d[c0]' % half)
    filt.append(''.join('[r%d]' % i for i in range(half, len(rows))) + 'vstack=%d[c1]' % (len(rows) - half))
    if len(rows) % 2:
        filt[-1] = filt[-1].replace('[c1]', ',pad=iw:ih+%s:0:0:white[c1]' % 'ih/%d' % (len(rows) - half))
    filt.append('[c0][c1]hstack=2')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + inputs + ['-filter_complex', ';'.join(filt), '-q:v', '4',
                                                                     os.path.join(OUT, 'sheet.jpg')], check=True)
    print('лист', os.path.join(OUT, 'sheet.jpg'))


if __name__ == '__main__':
    dict(programs=programs, render=render, sound=sound, assemble=assemble, sheet=sheet, dialogue=dialogue,
         bubbles=bubbles)[sys.argv[1]]()
