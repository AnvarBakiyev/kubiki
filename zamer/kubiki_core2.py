"""Обработчик языка «кубики» v2: модель задаёт намерение, сборщик считает геометрию.

Отличия от v1 (kubiki_core.py, заморожен):
- направления north south east west (n s e w тоже принимаются); hero <вид> <имя> ...;
- угловые скобки вокруг значения снимаются;
- деталь, которая не помещается или ложится на занятые клетки, защёлкивается на ближайшее свободное место;
- персонаж на детали (кроме tower и crate) переносится на ближайшую свободную клетку;
- walk run sneak идут в обход деталей кратчайшим путём; если цель на детали, подходят вплотную;
- время обрезается по сцене, наложенные действия одного персонажа сдвигаются друг за другом;
- имя, совпадающее с видом ровно одного персонажа, понимается как этот персонаж.
Каждая такая правка записывается в S['fixes']. Ошибкой остаются: чужие слова, сломанная строка, ссылка на
несуществующего персонажа, недостижимая цель.
"""
import json
import sys

from kubiki_core import (COLS, N, KINDS, STANDABLE, COLORS, LOOKS, MOVES, STAYS, FACES, SHOTS, FX, secs, name,
                         check_must)

DIRS = {'n': (0, 1), 's': (0, -1), 'e': (1, 0), 'w': (-1, 0)}
DIRW = {'north': 'n', 'south': 's', 'east': 'e', 'west': 'w', 'n': 'n', 's': 's', 'e': 'e', 'w': 'w'}


def unbr(tok):
    return tok[1:-1] if len(tok) > 2 and tok[0] == '<' and tok[-1] == '>' else tok


def cell(tok):
    tok = unbr(tok)
    if len(tok) < 2 or tok[0] not in COLS or not tok[1:].isdigit():
        return None
    c, r = COLS.index(tok[0]), int(tok[1:]) - 1
    return (c, r) if 0 <= r < N else None


def inside(c):
    return 0 <= c[0] < N and 0 <= c[1] < N


def ring(c0):
    """Клетки плиты по возрастанию расстояния от c0."""
    out = [(x, y) for x in range(N) for y in range(N)]
    out.sort(key=lambda c: (abs(c[0] - c0[0]) + abs(c[1] - c0[1]), abs(c[0] - c0[0]), c))
    return out


def bfs(a, b, occ):
    """Кратчайший путь по 8 соседям в обход деталей; диагональ не срезает угол детали."""
    prev = {a: None}
    q = [a]
    i = 0
    while i < len(q):
        c = q[i]; i += 1
        if c == b:
            break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n2 = (c[0] + dx, c[1] + dy)
                if (dx or dy) and inside(n2) and n2 not in occ and n2 not in prev:
                    if dx and dy and ((c[0] + dx, c[1]) in occ or (c[0], c[1] + dy) in occ):
                        continue
                    prev[n2] = c
                    q.append(n2)
    if b not in prev:
        return None
    path = [b]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path[::-1]


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

    # первый проход: len, plate, brick, hero
    for no, ln, t in raw:
        w = t[0].lower()
        if w == 'len':
            v = secs(t[1]) if len(t) == 2 else None
            if v is None: bad(no, ln, 'len <секунды>s'); continue
            if v < 3 or v > 8:
                fixes.append('len %.1f -> в пределах 3..8' % v); v = min(8.0, max(3.0, v))
            if S['len'] is None: S['len'] = v
        elif w == 'plate':
            if len(t) != 2 or t[1] not in COLORS: bad(no, ln, 'plate <цвет>'); continue
            S['plate'] = t[1]
        elif w == 'brick':
            if len(t) != 5: bad(no, ln, 'brick <деталь> <клетка> <направление> <цвет>'); continue
            k, c, d, col = t[1], cell(t[2]), DIRW.get(t[3]), t[4]
            if k not in KINDS: bad(no, ln, 'нет детали ' + k); continue
            if c is None: bad(no, ln, 'нет клетки ' + t[2]); continue
            if d is None: bad(no, ln, 'нет направления ' + t[3]); continue
            if col not in COLORS: bad(no, ln, 'нет цвета ' + col); continue
            placed = None
            for dd in [d] + [x for x in 'nsew' if x != d]:
                for c2 in ring(c):
                    cells = [(c2[0] + DIRS[dd][0] * i, c2[1] + DIRS[dd][1] * i) for i in range(KINDS[k])]
                    if all(inside(x) and x not in occ for x in cells):
                        placed = (c2, dd, cells); break
                if placed and (placed[0] == c or dd == d):
                    break
            if not placed: bad(no, ln, 'на плите нет места'); continue
            if placed[0] != c or placed[1] != d:
                fixes.append('%s: деталь защёлкнута на %s %s' % (ln, name(placed[0]), placed[1]))
            for x in placed[2]:
                occ[x] = k
            S['bricks'].append(dict(kind=k, cells=placed[2], dir=placed[1], color=col))
        elif w == 'hero':
            if len(t) != 5: bad(no, ln, 'hero <вид> <имя> <клетка> <направление>'); continue
            lk, nm = t[1], t[2]
            if lk not in LOOKS and nm in LOOKS:
                lk, nm = nm, lk
                fixes.append(ln + ': вид и имя переставлены')
            c, d = cell(t[3]), DIRW.get(t[4])
            if lk not in LOOKS: bad(no, ln, 'нет вида ' + lk); continue
            if nm in S['heroes']: bad(no, ln, 'второй персонаж ' + nm); continue
            if c is None: bad(no, ln, 'нет клетки ' + t[3]); continue
            if d is None: bad(no, ln, 'нет направления ' + t[4]); continue
            S['heroes'][nm] = dict(look=lk, cell=c, dir=d, line=ln)
    # персонажи на деталях: после всех деталей
    for nm, h in S['heroes'].items():
        c = h['cell']
        if c in occ and occ[c] not in STANDABLE:
            taken = set(x['cell'] for x in S['heroes'].values() if x is not h)
            c2 = next(x for x in ring(c) if x not in occ and x not in taken)
            fixes.append('%s: персонаж перенесён с детали %s на %s' % (h['line'], occ[c], name(c2)))
            h['cell'] = c2

    looks = {}
    for nm, h in S['heroes'].items():
        looks.setdefault(h['look'], []).append(nm)

    def who(tok, no, ln):
        if tok in S['heroes']:
            return tok
        if tok in looks and len(looks[tok]) == 1:
            fixes.append(ln + ': %s понят как %s' % (tok, looks[tok][0]))
            return looks[tok][0]
        return None

    for no, ln, t in raw:
        w = t[0].lower()
        if w in ('len', 'plate', 'brick', 'hero'):
            continue
        if w == 'act':
            if len(t) not in (7, 9) or t[-4] != 'from' or t[-2] != 'to':
                bad(no, ln, 'act <имя> <действие> [to <клетка>] from <начало>s to <конец>s'); continue
            nm, a = who(t[1], no, ln), t[2]
            t0, t1 = secs(t[-3]), secs(t[-1])
            dest = None
            if len(t) == 9:
                dest = cell(t[4]) if t[3] == 'to' else None
                if dest is None: bad(no, ln, 'to <клетка>'); continue
            if nm is None: bad(no, ln, 'нет персонажа ' + t[1]); continue
            if a not in MOVES + STAYS: bad(no, ln, 'нет действия ' + a); continue
            if a in MOVES and dest is None: bad(no, ln, a + ' требует to <клетка>'); continue
            if a in STAYS and dest is not None:
                fixes.append(ln + ': to у действия на месте отброшено'); dest = None
            if t0 is None or t1 is None or t1 <= t0: bad(no, ln, 'время from/to'); continue
            S['acts'].append(dict(hero=nm, act=a, dest=dest, t0=t0, t1=t1, line=no, src=ln))
        elif w == 'face':
            if len(t) != 5 or t[3] != 'at': bad(no, ln, 'face <имя> <лицо> at <время>s'); continue
            nm = who(t[1], no, ln)
            if nm is None: bad(no, ln, 'нет персонажа ' + t[1]); continue
            if t[2] not in FACES: bad(no, ln, 'нет лица ' + t[2]); continue
            v = secs(t[4])
            if v is None: bad(no, ln, 'время'); continue
            S['faces'].append(dict(hero=nm, face=t[2], t=v))
        elif w in ('cam', 'fx'):
            shake = w == 'cam' and t[-1] == 'shake'
            tt = t[:-1] if shake else t
            if len(tt) != 6 or tt[2] != 'on' or tt[4] != 'at':
                bad(no, ln, '%s <...> on <имя или клетка> at <время>s' % w); continue
            if tt[1] not in (SHOTS if w == 'cam' else FX): bad(no, ln, 'нет слова ' + tt[1]); continue
            tgt = who(tt[3], no, ln) or cell(tt[3])
            if tgt is None: bad(no, ln, 'цель не персонаж и не клетка: ' + tt[3]); continue
            v = secs(tt[5])
            if v is None: bad(no, ln, 'время'); continue
            if w == 'cam':
                S['cams'].append(dict(shot=tt[1], target=tgt, t=v, shake=shake))
            else:
                S['fx'].append(dict(fx=tt[1], target=tgt, t=v))
        else:
            bad(no, ln, 'нет команды ' + w)

    if S['len'] is None: errs.append('нет строки len')
    if S['plate'] is None:
        S['plate'] = 'gray'; fixes.append('нет plate: серый пол')
    if not S['heroes']: errs.append('нет ни одного персонажа')
    L = S['len'] or 5.0
    for it in S['faces'] + S['cams'] + S['fx']:
        if it['t'] < 0 or it['t'] > L:
            fixes.append('время %.1fs обрезано по сцене' % it['t']); it['t'] = min(L, max(0.0, it['t']))
    if not S['cams']:
        S['cams'].append(dict(shot='wide', target=(4, 4), t=0.0, shake=False, auto=True))
        fixes.append('нет cam: общий план')
    first = min(S['cams'], key=lambda c: c['t'])
    if first['t'] != 0:
        fixes.append('первая cam перенесена на 0s'); first['t'] = 0.0

    keep = []
    for nm, h in S['heroes'].items():
        pos, last = h['cell'], 0.0
        for a in sorted([a for a in S['acts'] if a['hero'] == nm], key=lambda a: a['t0']):
            pre = 'строка %d «%s»: ' % (a['line'], a['src'])
            if a['t0'] < last - 1e-9:
                dur = a['t1'] - a['t0']
                a['t0'], a['t1'] = last, last + dur
                fixes.append(pre + 'сдвинуто после прошлого действия')
            if a['t1'] > L:
                if a['t0'] >= L - 0.2:
                    fixes.append(pre + 'не помещается в сцену, отброшено'); continue
                a['t1'] = L; fixes.append(pre + 'конец обрезан по сцене')
            last = a['t1']
            a['from'] = pos
            if a['dest'] is None:
                keep.append(a); continue
            d = a['dest']
            if a['act'] in ('climb', 'jump'):
                if d in occ and occ[d] not in STANDABLE:
                    d2 = next(x for x in ring(d) if x not in occ)
                    fixes.append(pre + 'приземление перенесено на ' + name(d2)); d = d2
                a['path'] = [pos, d]
            else:
                if d in occ:
                    best = None
                    for x in ring(d):
                        if x not in occ and max(abs(x[0] - d[0]), abs(x[1] - d[1])) <= 2:
                            p = bfs(pos, x, occ)
                            if p and (best is None or len(p) < len(best)):
                                best = p
                    if best is None: errs.append(pre + 'к цели не подойти'); continue
                    fixes.append(pre + 'подходит вплотную к %s на %s' % (occ[d], name(best[-1])))
                    p = best
                else:
                    start = pos if pos not in occ else None
                    p = bfs(pos, d, {k: v for k, v in occ.items() if k != pos}) if start is None else bfs(pos, d, occ)
                    if p is None: errs.append(pre + 'к цели не пройти'); continue
                    if len(p) > 2 and any(c in occ for c in line_cells(pos, d)):
                        fixes.append(pre + 'обход деталей')
                a['path'] = p
                d = p[-1]
            a['dest'] = d
            pos = d
            keep.append(a)
        h['end'] = pos
    S['acts'] = keep
    return S, errs


def line_cells(a, b):
    out = []
    for i in range(1, 40):
        out.append((int(round(a[0] + (b[0] - a[0]) * i / 40)), int(round(a[1] + (b[1] - a[1]) * i / 40))))
    return out


def check_must2(S, must):
    S2 = dict(S)
    S2['cams'] = [c for c in S['cams'] if not c.get('auto')]
    return check_must(S2, must)


if __name__ == '__main__':
    S, e = compile_program(open(sys.argv[1]).read())
    if e:
        print(chr(10).join(e)); sys.exit(1)
    print(json.dumps(S, ensure_ascii=False, indent=1, default=list))
