"""Судья без ключа ответов: модель по ОПИСАНИЮ пишет список проверок (CHECKS-kubiki.md), код сверяет с ним сцену.

    python3 judge.py extract      DeepSeek три раза пишет проверки для каждой из 10 сцен -> out/judge/checks_<сцена>_<k>.txt
    python3 judge.py validate     судья против ручной проверки (must + staging) на всех ответах DeepSeek
    python3 judge.py select       отбор из трёх попыток судьёй против одной попытки

Ручные условия (scenes.json must, staging.py) судья не видит: они только мерило.
"""
import glob
import json
import os
import sys

import kubiki_core2 as K2
import kubiki_core31 as K31
from kubiki_core import KINDS, LOOKS, MOVES, STAYS, FACES, SHOTS, FX
from staging import dist, staging_check, acts_of, path_cells, pos_at

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out', 'judge')
SC = {s['id']: s for s in json.load(open(os.path.join(HERE, 'scenes.json')))['scenes']}
SPEC = open(os.path.join(HERE, 'CHECKS-kubiki.md')).read()
NL = chr(10)


# ---------------- разбор и проверка ----------------
def parse(text):
    items, junk = [], []
    for ln in text.split(NL):
        t = [x.strip('`<>[],.:;') for x in ln.strip().strip('-*').split()]
        t = [x for x in t if x]
        if not t:
            continue
        w = t[0].lower()
        ok = (
            (w == 'brick' and len(t) == 2 and t[1] in KINDS) or
            (w == 'hero' and len(t) in (2, 3) and t[1] in LOOKS) or
            (w == 'act' and len(t) == 3 and t[1] in LOOKS and t[2] in MOVES + STAYS) or
            (w == 'face' and len(t) == 3 and t[1] in LOOKS and t[2] in FACES) or
            (w == 'cam' and len(t) == 2 and t[1] in SHOTS) or
            (w == 'shake' and len(t) == 1) or
            (w == 'fx' and len(t) == 2 and t[1] in FX) or
            (w in ('start', 'end') and len(t) == 4 and t[1] in LOOKS and t[2] in ('near', 'on')
             and (t[3] in KINDS or t[3] in LOOKS)) or
            (w in ('over', 'onto') and len(t) == 3 and t[1] in LOOKS and t[2] in KINDS) or
            (w in ('past', 'away', 'sides') and len(t) == 3 and t[1] in LOOKS and (t[2] in KINDS or t[2] in LOOKS)) or
            (w == 'chase' and len(t) == 3 and t[1] in LOOKS and t[2] in LOOKS) or
            (w == 'at' and len(t) == 4 and t[1] in LOOKS and t[2] in MOVES + STAYS and (t[3] in KINDS or t[3] in LOOKS)))
        (items if ok else junk).append(t)
    return items, junk


def heroes(S, look):
    return [nm for nm, h in S['heroes'].items() if h['look'] == look]


def kcells(S, kind):
    return [tuple(c) for b in S['bricks'] if b['kind'] == kind for c in b['cells']]


def start(S, nm):
    return tuple(S['heroes'][nm]['cell'])


def end(S, nm):
    return tuple(S['heroes'][nm].get('end') or S['heroes'][nm]['cell'])


def where(S, x, t=None, at_end=False):
    """Клетки цели x (деталь или вид) и допуск «рядом»."""
    if x in KINDS:
        return kcells(S, x), 1
    hs = heroes(S, x)
    if at_end:
        return [end(S, h) for h in hs], 2
    if t is None:
        return [start(S, h) for h in hs], 2
    return [pos_at(S, h, t) for h in hs], 2


def near(c, cells, k):
    return any(dist(c, x) <= k for x in cells)


def holds(S, t):
    w = t[0].lower()
    if w == 'brick':
        return bool(kcells(S, t[1]))
    if w == 'hero':
        return len(heroes(S, t[1])) >= (2 if len(t) == 3 else 1)
    hs = heroes(S, t[1]) if len(t) > 1 and t[1] in LOOKS else []
    if w == 'act':
        return any(acts_of(S, h, (t[2],)) for h in hs)
    if w == 'face':
        return any(f['hero'] in hs and f['face'] == t[2] for f in S['faces'])
    if w == 'cam':
        return any(c['shot'] == t[1] and not c.get('auto') for c in S['cams'])
    if w == 'shake':
        return any(c['shake'] for c in S['cams'])
    if w == 'fx':
        return any(f['fx'] == t[1] for f in S['fx'])
    if w == 'start':
        cells, k = where(S, t[3])
        if t[2] == 'on':
            return any(start(S, h) in kcells(S, t[3]) for h in hs)
        return any(near(start(S, h), [c for c in cells if c != start(S, h)] if t[3] in LOOKS else cells, k) for h in hs)
    if w == 'end':
        cells, k = where(S, t[3], at_end=True)
        if t[2] == 'on':
            return any(end(S, h) in kcells(S, t[3]) for h in hs)
        return any(near(end(S, h), [c for c in cells if c != end(S, h)] if t[3] in LOOKS else cells, k) for h in hs)
    if w == 'over':
        cells = kcells(S, t[2])
        return any(any(c in cells for c in path_cells(a)) for h in hs for a in acts_of(S, h, ('climb', 'jump')))
    if w == 'onto':
        cells = kcells(S, t[2])
        return any(a.get('dest') and tuple(a['dest']) in cells for h in hs for a in acts_of(S, h, ('climb', 'jump')))
    if w == 'past':
        for h in hs:
            for a in acts_of(S, h, MOVES):
                cells, k = where(S, t[2], a['t0'])
                cells = [c for c in cells if c != tuple(a['from'])]
                if cells and min(dist(c, x) for c in path_cells(a) for x in cells) <= k \
                        and dist(tuple(a['from']), tuple(a['dest'])) >= 2:
                    return True
        return False
    if w == 'away':
        for h in hs:
            for a in acts_of(S, h, MOVES):
                cells, _ = where(S, t[2], a['t0'])
                cells = [c for c in cells if c != tuple(a['from'])]
                if cells and min(dist(tuple(a['dest']), x) for x in cells) > min(dist(tuple(a['from']), x) for x in cells):
                    return True
        return False
    if w == 'chase':
        hs2 = heroes(S, t[2])
        return any(acts_of(S, a, ('run', 'walk')) and dist(end(S, a), end(S, b)) < dist(start(S, a), end(S, b))
                   for a in hs for b in hs2 if a != b)
    if w == 'sides':
        cells, _ = where(S, t[2])
        if len(hs) < 2 or not cells:
            return False
        cx = sum(c[0] for c in cells) / len(cells)
        cy = sum(c[1] for c in cells) / len(cells)
        for a in hs:
            for b in hs:
                pa, pb = start(S, a), start(S, b)
                if a < b and dist(pa, pb) >= 3 and ((pa[0] - cx) * (pb[0] - cx) < 0 or (pa[1] - cy) * (pb[1] - cy) < 0):
                    return True
        return False
    if w == 'at':
        for h in hs:
            for a in acts_of(S, h, (t[2],)):
                cells, k = where(S, t[3], a['t0'])
                p = pos_at(S, h, a['t0'])
                if near(p, [c for c in cells if c != p] if t[3] in LOOKS else cells, k):
                    return True
        return False
    return True


def judge(S, items):
    return [' '.join(t) for t in items if not holds(S, t)]


# ---------------- опыты ----------------
def extract():
    from run3 import chat
    os.makedirs(OUT, exist_ok=True)
    for sid, sc in SC.items():
        for k in (1, 2, 3):
            txt, _ = chat(SPEC + NL + NL + 'ОПИСАНИЕ СЦЕНЫ: ' + sc['text'])
            open(os.path.join(OUT, 'checks_%02d_%d.txt' % (sid, k)), 'w').write(txt)
            items, junk = parse(txt)
            print('сцена %d/%d: проверок %d, непонятных строк %d' % (sid, k, len(items), len(junk)), flush=True)


def checks(sid, k):
    if k == 0:  # согласие: проверка остаётся, если её написали хотя бы 2 разбора из 3
        cnt = {}
        for kk in (1, 2, 3):
            for t in {tuple(x) for x in checks(sid, kk)}:
                cnt[t] = cnt.get(t, 0) + 1
        return [list(t) for t, n in cnt.items() if n >= 2]
    return parse(open(os.path.join(OUT, 'checks_%02d_%d.txt' % (sid, k))).read())[0]


KS = (1, 2, 3, 0)


FOLDERS = ['r3_v31_ds', 'r3_v31_ds_fix', 'r3_v31b_ds', 'r3_v31b_ds_fix',
           'r3_v32_ds', 'r3_v32_ds_fix', 'r3_v32b_ds', 'r3_v32b_ds_fix']


def label(path, sid):
    S, e = K31.compile_program(open(path).read())
    if e:
        return S, None
    return S, not K2.check_must2(S, SC[sid]['must']) and not staging_check(S, sid)


def validate():
    rows = []
    for folder in FOLDERS:
        for p in sorted(glob.glob(os.path.join(HERE, 'out', folder, '*.kub'))):
            sid = int(os.path.basename(p)[:2])
            S, hand = label(p, sid)
            if hand is None:
                continue  # сборщик не принял: судья не нужен
            for k in KS:
                fails = judge(S, checks(sid, k))
                rows.append(dict(folder=folder, file=os.path.basename(p), scene=sid, k=k, hand=hand,
                                 judge=not fails, fails=fails))
    allrows = rows
    out = {}
    for name, sel in (('один разбор', lambda r: r['k'] != 0), ('согласие 2 из 3', lambda r: r['k'] == 0)):
        rows = [r for r in allrows if sel(r)]
        out[name] = stats(rows)
    json.dump(dict(summary=out, rows=allrows), open(os.path.join(OUT, 'validate.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def stats(rows):
    tp = sum(r['hand'] and r['judge'] for r in rows)
    fp = sum(not r['hand'] and r['judge'] for r in rows)
    fn = sum(r['hand'] and not r['judge'] for r in rows)
    tn = sum(not r['hand'] and not r['judge'] for r in rows)
    return dict(pairs=len(rows), agree=tp + tn, agree_pct=round((tp + tn) / max(1, len(rows)), 3),
                judge_yes_hand_yes=tp, judge_yes_hand_no=fp, judge_no_hand_yes=fn, judge_no_hand_no=tn,
                precision=round(tp / max(1, tp + fp), 3), recall=round(tp / max(1, tp + fn), 3))


def select():
    """Три попытки = три повтора сцены в одном прогоне (только первые попытки, без исправления и с ним)."""
    out = {}
    for folder in FOLDERS:
        dec = []
        for sid in SC:
            cands = []
            for rep in (1, 2, 3):
                p = os.path.join(HERE, 'out', folder, '%02d_%d.kub' % (sid, rep))
                S, hand = label(p, sid)
                cands.append((S, hand))
            for k in KS:
                ok_j = [c for c in cands if c[1] is not None and not judge(c[0], checks(sid, k))]
                pick = ok_j[0] if ok_j else cands[0]
                dec.append(dict(scene=sid, k=k, first=bool(cands[0][1]), picked=bool(pick[1]),
                                any=any(bool(c[1]) for c in cands), judge_found=bool(ok_j)))
        one = [d for d in dec if d['k'] != 0]
        con = [d for d in dec if d['k'] == 0]
        out[folder] = dict(n=len(one), one_try=sum(d['first'] for d in one), judge_pick=sum(d['picked'] for d in one),
                           best_possible=sum(d['any'] for d in one), n_consensus=len(con),
                           consensus_pick=sum(d['picked'] for d in con), consensus_one_try=sum(d['first'] for d in con),
                           consensus_best=sum(d['any'] for d in con))
        print(folder, out[folder], flush=True)
    tot = {k: sum(v[k] for v in out.values()) for k in ('n', 'one_try', 'judge_pick', 'best_possible', 'n_consensus',
                                                         'consensus_one_try', 'consensus_pick', 'consensus_best')}
    print('всего', tot)
    json.dump(dict(per_folder=out, total=tot), open(os.path.join(OUT, 'select.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    dict(extract=extract, validate=validate, select=select)[sys.argv[1]]()
