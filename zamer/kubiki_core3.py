"""Обработчик языка «кубики» v3: модель называет отношения, сборщик считает клетки и пути.

Цели действий и места персонажей задаются через детали и других персонажей: near, behind, on, to, over, past,
away from, onto. Клетки модель пишет только для деталей. Всё, что сборщик поправил, записано в S['fixes'].
Выход совместим с v2 (рендер и staging.py те же).
"""
import json
import sys

from kubiki_core import KINDS, STANDABLE, COLORS, LOOKS, MOVES, STAYS, FACES, SHOTS, FX, secs, name
from kubiki_core2 import DIRS, DIRW, unbr, cell, inside, ring, bfs, check_must2  # noqa: F401


def sgn(x):
    return (x > 0) - (x < 0)


def dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def compile_program(text):
    errs, fixes = [], []
    S = dict(len=None, plate=None, bricks=[], heroes={}, acts=[], faces=[], cams=[], fx=[], fixes=fixes)
    occ = {}
    raw = []
    for no, ln in enumerate(text.split(chr(10)), 1):
        ln = ln.strip().strip('`').strip()
        if not ln or ln.startswith('#') or ln.startswith('```'):
            continue
        raw.append((no, ln, [unbr(x) for x in ln.split()]))

    def bad(no, ln, msg):
        errs.append('строка %d «%s»: %s' % (no, ln, msg))

    # ---- len, plate, brick ----
    for no, ln, t in raw:
        w = t[0].lower()
        if w == 'len':
            v = secs(t[1]) if len(t) == 2 else None
            if v is None: bad(no, ln, 'len <секунды>s'); continue
            if not 3 <= v <= 8:
                fixes.append('len в пределах 3..8'); v = min(8.0, max(3.0, v))
            S['len'] = S['len'] or v
        elif w == 'plate':
            if len(t) != 2 or t[1] not in COLORS: bad(no, ln, 'plate <цвет>'); continue
            S['plate'] = t[1]
        elif w == 'brick':
            if len(t) not in (4, 5): bad(no, ln, 'brick <деталь> <клетка> <цвет>'); continue
            k, c, col = t[1], cell(t[2]), t[-1]
            d = DIRW.get(t[3]) if len(t) == 5 else 'e'
            if k not in KINDS: bad(no, ln, 'нет детали ' + k); continue
            if c is None: bad(no, ln, 'нет клетки ' + t[2]); continue
            if d is None: d = 'e'; fixes.append(ln + ': направление по умолчанию east')
            if col not in COLORS: bad(no, ln, 'нет цвета ' + col); continue
            placed = None
            for dd in [d] + [x for x in 'ensw' if x != d]:
                for c2 in ring(c):
                    cells = [(c2[0] + DIRS[dd][0] * i, c2[1] + DIRS[dd][1] * i) for i in range(KINDS[k])]
                    if all(inside(x) and x not in occ for x in cells):
                        placed = (c2, dd, cells); break
                if placed and (placed[0] == c or dd == d):
                    break
            if not placed: bad(no, ln, 'на плите нет места'); continue
            if placed[0] != c:
                fixes.append('%s: деталь защёлкнута на %s' % (ln, name(placed[0])))
            for x in placed[2]:
                occ[x] = k
            S['bricks'].append(dict(kind=k, cells=placed[2], dir=placed[1], color=col))
    if S['plate'] is None:
        S['plate'] = 'gray'

    def brick_cells(kind):
        for b in S['bricks']:
            if b['kind'] == kind:
                return [tuple(c) for c in b['cells']], b
        return None, None

    taken = {}

    def free(c):
        return inside(c) and c not in occ and c not in taken

    def adjacent_free(cells, toward):
        cand = []
        for c in cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    x = (c[0] + dx, c[1] + dy)
                    if (dx or dy) and free(x):
                        cand.append(x)
        if not cand:
            return None
        cand.sort(key=lambda x: (min(dist(x, c) for c in cells), dist(x, toward), x))
        return cand[0]

    # ---- персонажи: несколько проходов, чтобы near <имя> находил уже поставленных ----
    hero_lines = [(no, ln, t) for no, ln, t in raw if t[0].lower() == 'hero']
    pending = list(hero_lines)
    for _ in range(3):
        rest = []
        for no, ln, t in pending:
            if len(t) < 4: bad(no, ln, 'hero <вид> <имя> <где>'); continue
            lk, nm = t[1], t[2]
            if lk not in LOOKS and nm in LOOKS:
                lk, nm = nm, lk; fixes.append(ln + ': вид и имя переставлены')
            if lk not in LOOKS: bad(no, ln, 'нет вида ' + lk); continue
            if nm in S['heroes']: bad(no, ln, 'второй персонаж ' + nm); continue
            where = [x for x in t[3:] if DIRW.get(x) is None or x in ('on',)]
            pos = None
            side = next((i for i, x in enumerate(t[3:-1]) if x in ('north', 'south', 'east', 'west')
                         and t[3 + i + 1] == 'of'), None)
            if side is not None and 3 + side + 2 < len(t):
                ref = t[3 + side + 2]
                rc = ([S['heroes'][ref]['cell']] if ref in S['heroes'] else
                      (brick_cells(ref)[0] if ref in KINDS else None))
                if rc is None:
                    if ref in LOOKS or ref not in KINDS:
                        rest.append((no, ln, t)); continue
                    bad(no, ln, 'нет детали %s на сцене' % ref); continue
                dx, dy = DIRS[DIRW[t[3 + side]]]
                c0 = rc[0]
                want = (min(9, max(0, c0[0] + dx * 3)), min(9, max(0, c0[1] + dy * 3)))
                pos = next(x for x in ring(want) if free(x))
                taken[pos] = nm
                S['heroes'][nm] = dict(look=lk, cell=pos, dir='s', line=ln)
                continue
            if where and cell(where[0]):
                pos = cell(where[0])
                if pos in occ and occ[pos] not in STANDABLE or pos in taken:
                    pos = next(x for x in ring(pos) if free(x)); fixes.append(ln + ': перенесён на свободную клетку')
            elif len(where) >= 2 and where[0] in ('near', 'behind', 'on', 'at'):
                ref = where[1]
                if ref in S['heroes']:
                    pos = adjacent_free([S['heroes'][ref]['cell']], (4, 0))
                elif ref in KINDS:
                    cells, b = brick_cells(ref)
                    if cells is None:
                        bad(no, ln, 'нет детали %s на сцене' % ref); continue
                    if where[0] == 'on' and ref in STANDABLE:
                        pos = cells[0]
                    elif where[0] == 'behind':
                        back = [(c[0], c[1] + 1) for c in cells if free((c[0], c[1] + 1))]
                        pos = back[len(back) // 2] if back else adjacent_free(cells, (4, 9))
                    else:
                        if where[0] == 'on':
                            fixes.append(ln + ': on %s понят как near' % ref)
                        pos = adjacent_free(cells, (4, 0))
                elif cell(ref):
                    pos = adjacent_free([cell(ref)], (4, 0))
                else:
                    rest.append((no, ln, t)); continue
            elif not where:
                pos = next(x for x in ring((4, 4)) if free(x)); fixes.append(ln + ': место не указано, середина')
            else:
                bad(no, ln, 'где: near/behind/on <деталь или имя>'); continue
            if pos is None: bad(no, ln, 'рядом нет свободной клетки'); continue
            taken[pos] = nm
            S['heroes'][nm] = dict(look=lk, cell=pos, dir='s', line=ln)
        pending = rest
        if not pending:
            break
    for no, ln, t in pending:
        bad(no, ln, 'не найдено, рядом с чем ставить: ' + ' '.join(t[3:]))

    looks = {}
    for nm, h in S['heroes'].items():
        looks.setdefault(h['look'], []).append(nm)

    def who(tok, ln):
        if tok in S['heroes']:
            return tok
        if tok in looks and len(looks[tok]) == 1:
            fixes.append(ln + ': %s понят как %s' % (tok, looks[tok][0]))
            return looks[tok][0]
        return None

    def tpos0(tg):
        if isinstance(tg, str): return [S['heroes'][tg]['cell']]
        return [tg]

    def target(tok, ln):
        """Имя персонажа, ('brick', kind) или клетка."""
        h = who(tok, ln)
        if h: return h
        if tok in KINDS and brick_cells(tok)[0]: return ('brick', tok)
        return cell(tok)

    # ---- действия, лица, камера, эффекты ----
    acts = []
    for no, ln, t in raw:
        w = t[0].lower()
        if w == 'act':
            if len(t) < 7 or t[-4] != 'from' or t[-2] != 'to':
                bad(no, ln, 'act <имя> <действие> <куда> from <начало>s to <конец>s'); continue
            nm, a = who(t[1], ln), t[2]
            t0, t1 = secs(t[-3]), secs(t[-1])
            spec = t[3:-4]
            if nm is None: bad(no, ln, 'нет персонажа ' + t[1]); continue
            if t0 is None or t1 is None or t1 <= t0: bad(no, ln, 'время from/to'); continue
            if a in ('trip', 'stop') or (a == 'hide' and spec[:1] == ['behind']):
                ref = spec[-1] if spec else None
                tg = target(ref, ln) if ref else None
                if tg is None: bad(no, ln, a + ' требует деталь или кого: ' + ' '.join(spec)); continue
                if a == 'hide':
                    cells = brick_cells(ref)[0] if ref in KINDS else tpos0(tg)
                    back = [(c[0], c[1] + 1) for c in cells if inside((c[0], c[1] + 1)) and (c[0], c[1] + 1) not in occ]
                    if back:
                        tg = back[len(back) // 2]
                mid = t0 + (0.6 if a != 'stop' else 0.8) * (t1 - t0)
                acts.append(dict(hero=nm, act='run', rel='to', tg=tg, t0=t0, t1=mid, line=no, src=ln))
                acts.append(dict(hero=nm, act={'trip': 'fall', 'stop': 'stand', 'hide': 'hide'}[a], rel=None, tg=None,
                                 t0=mid, t1=t1, line=no, src=ln))
                continue
            if a not in MOVES + STAYS: bad(no, ln, 'нет действия ' + a); continue
            if a in STAYS and spec:
                fixes.append(ln + ': цель у действия на месте отброшена'); spec = []
            if a in MOVES:
                if not spec: bad(no, ln, a + ' требует куда: to/over/past/away from/onto'); continue
                rel = spec[0]
                if rel == 'away' and len(spec) >= 3 and spec[1] == 'from':
                    rel, ref = 'away', spec[2]
                elif rel in ('to', 'over', 'past', 'onto', 'toward', 'towards', 'into', 'through') and len(spec) >= 2:
                    ref = spec[1]
                    rel = {'toward': 'to', 'towards': 'to', 'into': 'to', 'through': 'past'}.get(rel, rel)
                elif len(spec) == 1:
                    rel, ref = 'to', spec[0]
                else:
                    bad(no, ln, 'куда: to/over/past/away from/onto <деталь или имя>'); continue
                tg = target(ref, ln)
                if tg is None: bad(no, ln, 'нет цели ' + ref); continue
                acts.append(dict(hero=nm, act=a, rel=rel, tg=tg, t0=t0, t1=t1, line=no, src=ln))
            else:
                acts.append(dict(hero=nm, act=a, rel=None, tg=None, t0=t0, t1=t1, line=no, src=ln))
        elif w == 'face':
            if len(t) != 5 or t[3] != 'at': bad(no, ln, 'face <имя> <лицо> at <время>s'); continue
            nm = who(t[1], ln)
            if nm is None: bad(no, ln, 'нет персонажа ' + t[1]); continue
            if t[2] not in FACES: bad(no, ln, 'нет лица ' + t[2]); continue
            v = secs(t[4])
            if v is None: bad(no, ln, 'время'); continue
            S['faces'].append(dict(hero=nm, face=t[2], t=v))
        elif w in ('cam', 'fx'):
            shake = w == 'cam' and t[-1] == 'shake'
            tt = t[:-1] if shake else t
            if len(tt) != 6 or tt[2] != 'on' or tt[4] != 'at':
                bad(no, ln, '%s <...> on <имя или деталь> at <время>s' % w); continue
            if tt[1] not in (SHOTS if w == 'cam' else FX): bad(no, ln, 'нет слова ' + tt[1]); continue
            tg = target(tt[3], ln)
            if tg is None: bad(no, ln, 'цель не персонаж, не деталь и не клетка: ' + tt[3]); continue
            if isinstance(tg, tuple) and tg[0] == 'brick':
                tg = brick_cells(tg[1])[0][0]
            v = secs(tt[5])
            if v is None: bad(no, ln, 'время'); continue
            if w == 'cam':
                S['cams'].append(dict(shot=tt[1], target=tg, t=v, shake=shake))
            else:
                S['fx'].append(dict(fx=tt[1], target=tg, t=v))
        elif w not in ('len', 'plate', 'brick', 'hero'):
            bad(no, ln, 'нет команды ' + w)

    if S['len'] is None: errs.append('нет строки len')
    if not S['heroes']: errs.append('нет ни одного персонажа')
    L = S['len'] or 5.0
    for it in S['faces'] + S['cams'] + S['fx']:
        if not 0 <= it['t'] <= L:
            fixes.append('время обрезано по сцене'); it['t'] = min(L, max(0.0, it['t']))
    if not S['cams']:
        S['cams'].append(dict(shot='wide', target=(4, 4), t=0.0, shake=False, auto=True)); fixes.append('нет cam')
    first = min(S['cams'], key=lambda c: c['t'])
    if first['t'] != 0:
        first['t'] = 0.0; fixes.append('первая cam на 0s')

    # время: по персонажу друг за другом, по сцене
    keep = []
    for nm in S['heroes']:
        last = 0.0
        for a in sorted([a for a in acts if a['hero'] == nm], key=lambda a: a['t0']):
            if a['t0'] < last - 1e-9:
                d = a['t1'] - a['t0']; a['t0'], a['t1'] = last, last + d
                fixes.append(a['src'] + ': сдвинуто после прошлого действия')
            if a['t1'] > L:
                if a['t0'] >= L - 0.2:
                    fixes.append(a['src'] + ': не помещается, отброшено'); continue
                a['t1'] = L
            last = a['t1']
            keep.append(a)

    # пути: в общем порядке времени, позиции персонажей обновляются
    pos = {nm: h['cell'] for nm, h in S['heroes'].items()}
    occ_free = lambda c: inside(c) and c not in occ  # noqa: E731

    def tpos(tg):
        if isinstance(tg, str): return [pos[tg]]
        if isinstance(tg, tuple) and tg and tg[0] == 'brick': return brick_cells(tg[1])[0]
        return [tg]

    def beside(cells, me):
        cand = [(c[0] + dx, c[1] + dy) for c in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        cand = [c for c in cand if occ_free(c) and c not in cells]
        cand.sort(key=lambda c: (dist(c, me), c))
        for c in cand:
            p = bfs(me, c, {k: v for k, v in occ.items() if k != me})
            if p: return p
        return None

    final = []
    for a in sorted(keep, key=lambda a: (a['t0'], a['line'])):
        me = pos[a['hero']]
        a['from'] = me
        pre = 'строка %d «%s»: ' % (a['line'], a['src'])
        if a['rel'] is None:
            a['dest'] = None; final.append(a); continue
        tc = tpos(a['tg'])
        rel, act = a['rel'], a['act']
        occ_wo = {k: v for k, v in occ.items() if k != me}
        if rel == 'onto' or (rel == 'to' and act in ('climb', 'jump') and isinstance(a['tg'], tuple)
                             and a['tg'][0] == 'brick' and a['tg'][1] in STANDABLE):
            if not (isinstance(a['tg'], tuple) and a['tg'][0] == 'brick' and a['tg'][1] in STANDABLE):
                p = beside(tc, me)
                if not p: errs.append(pre + 'не подойти'); continue
                a['path'] = p; fixes.append(pre + 'onto не на вышку/ящик: подходит рядом')
            else:
                if act not in ('climb', 'jump'):
                    a['act'] = 'climb'; fixes.append(pre + 'забраться наверх = climb')
                a['path'] = [me, tc[0]]
        elif rel == 'over':
            if act not in ('climb', 'jump'):
                a['act'] = 'jump'; fixes.append(pre + 'через деталь = jump')
            bk = brick_cells(a['tg'][1])[1] if isinstance(a['tg'], tuple) and a['tg'][0] == 'brick' else None
            choice = None
            for b in sorted(tc, key=lambda c: (dist(c, me), c)):
                if bk and len(bk['cells']) > 1:
                    v0 = (0, sgn(b[1] - me[1]) or 1) if bk['dir'] in ('e', 'w') else (sgn(b[0] - me[0]) or 1, 0)
                else:
                    v0 = (sgn(b[0] - me[0]), sgn(b[1] - me[1]))
                    if v0 == (0, 0): v0 = (1, 0)
                for v in (v0, (-v0[0], -v0[1])):
                    st = (b[0] - v[0], b[1] - v[1])
                    if st != me and not occ_free(st):
                        continue
                    p0 = [me] if st == me else bfs(me, st, occ_wo)
                    if not p0:
                        continue
                    dest = next(((b[0] + v[0] * k, b[1] + v[1] * k) for k in (1, 2, 3)
                                 if occ_free((b[0] + v[0] * k, b[1] + v[1] * k))), None)
                    if dest:
                        choice = (p0, dest); break
                if choice: break
            if choice is None: errs.append(pre + 'через деталь не перебраться'); continue
            p0, dest = choice
            if len(p0) > 1:
                d = a['t1'] - a['t0']
                run = dict(hero=a['hero'], act='run', rel='to', t0=a['t0'], t1=a['t0'] + 0.4 * d,
                           line=a['line'], src=a['src'], **{'from': me}, path=p0, dest=p0[-1])
                final.append(run)
                a['t0'] = run['t1']
                me = p0[-1]
                a['from'] = me
                fixes.append(pre + 'разбег до детали')
            a['path'] = [me, dest]
        elif rel == 'past':
            xp = min(tc, key=lambda c: (dist(c, me), c))
            vx, vy = sgn(xp[0] - me[0]), sgn(xp[1] - me[1])
            if (vx, vy) == (0, 0): vx = 1
            beyond = None
            for k in (2, 3, 1, 4):
                c = (xp[0] + vx * k, xp[1] + vy * k)
                if occ_free(c) and c not in tc:
                    beyond = c; break
            if beyond is None:
                beyond = next((c for c in ring((xp[0] + vx * 2, xp[1] + vy * 2)) if occ_free(c) and dist(c, xp) >= 2), None)
            side = [c for c in [(x[0] + dx, x[1] + dy) for x in tc for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                    if occ_free(c) and c not in tc and c != me]
            side.sort(key=lambda c: (dist(me, c) + dist(c, beyond), c))
            p = None
            for wp in side[:6]:
                p1, p2 = bfs(me, wp, occ_wo), bfs(wp, beyond, occ)
                if p1 and p2:
                    p = p1 + p2[1:]; break
            if not p: errs.append(pre + 'мимо не пройти'); continue
            if act in ('climb', 'jump'):
                a['act'] = 'run'; fixes.append(pre + 'мимо = бег')
            a['path'] = p
        elif rel == 'away':
            xp = min(tc, key=lambda c: (dist(c, me), c))
            cand = [c for c in ring(me) if occ_free(c) and dist(c, me) <= 5]
            cand.sort(key=lambda c: (-dist(c, xp), dist(c, me), c))
            p = None
            for c in cand[:8]:
                p = bfs(me, c, occ_wo)
                if p: break
            if not p: errs.append(pre + 'некуда убежать'); continue
            a['path'] = p
        else:  # to
            if isinstance(a['tg'], tuple) and a['tg'] and a['tg'][0] != 'brick' and occ_free(a['tg']):
                p = bfs(me, a['tg'], occ_wo)
            else:
                p = beside(tc, me)
            if not p: errs.append(pre + 'к цели не подойти'); continue
            a['path'] = p
        if a['act'] in ('climb', 'jump') and rel not in ('over', 'onto'):
            a['path'] = [a['path'][0], a['path'][-1]]
        a['dest'] = a['path'][-1]
        pos[a['hero']] = a['dest']
        final.append(a)
    for nm, h in S['heroes'].items():
        h['end'] = pos[nm]
        others = [o for o in S['heroes'] if o != nm]
        if others:
            o = min(others, key=lambda o: dist(S['heroes'][o]['cell'], h['cell']))
            dx = S['heroes'][o]['cell'][0] - h['cell'][0]
            dy = S['heroes'][o]['cell'][1] - h['cell'][1]
            h['dir'] = ('e' if dx > 0 else 'w') if abs(dx) > abs(dy) else ('n' if dy > 0 else 's')
    for a in final:
        a.pop('tg', None)
    S['acts'] = final
    return S, errs


if __name__ == '__main__':
    S, e = compile_program(open(sys.argv[1]).read())
    if e:
        print(chr(10).join(e)); sys.exit(1)
    print(json.dumps(S, ensure_ascii=False, indent=1, default=list))
