"""Обработчик языка «кубики»: разбор, проверка, раскладка сцены в JSON для рендера.

    python3 kubiki_core.py program.kub            -> печатает JSON сцены или список ошибок
    from kubiki_core import compile_program, check_must

Без регулярных выражений и без обратных слешей (так обработчик запускается и в песочнице, где они запрещены).
"""
import json
import sys

COLS = 'abcdefghij'
N = 10
KINDS = {'block': 1, 'crate': 1, 'tree': 1, 'lamp': 1, 'tower': 1, 'door': 1, 'wall': 3, 'bars': 3, 'car': 2}
STANDABLE = ('tower', 'crate')
DIRS = {'n': (0, 1), 's': (0, -1), 'e': (1, 0), 'w': (-1, 0)}
COLORS = ('red', 'blue', 'yellow', 'green', 'white', 'black', 'gray', 'tan', 'orange', 'brown')
LOOKS = ('prisoner', 'guard', 'thief', 'cop', 'kid', 'citizen')
MOVES = ('walk', 'run', 'sneak', 'climb', 'jump')
STAYS = ('stand', 'fall', 'wave', 'hide', 'push')
FACES = ('calm', 'happy', 'angry', 'scared', 'surprised', 'sly')
SHOTS = ('wide', 'medium', 'close', 'low', 'top', 'follow')
FX = ('dust', 'crash', 'flash', 'alarm')


def cell(tok):
    if len(tok) < 2 or tok[0] not in COLS or not tok[1:].isdigit():
        return None
    c, r = COLS.index(tok[0]), int(tok[1:]) - 1
    if r < 0 or r >= N:
        return None
    return (c, r)


def secs(tok):
    if not tok.endswith('s'):
        return None
    try:
        return float(tok[:-1])
    except ValueError:
        return None


def compile_program(text):
    errs = []
    S = dict(len=None, plate=None, bricks=[], heroes={}, acts=[], faces=[], cams=[], fx=[])
    occ = {}
    lines = [ln.strip().strip('`') for ln in text.split(chr(10))]
    for no, ln in enumerate(lines, 1):
        if not ln or ln.startswith('#') or ln.startswith('```'):
            continue
        t = ln.split()
        w = t[0].lower()

        def bad(msg):
            errs.append('строка %d «%s»: %s' % (no, ln, msg))

        if w == 'len':
            v = secs(t[1]) if len(t) == 2 else None
            if v is None or v < 3 or v > 8:
                bad('len — от 3 до 8 секунд'); continue
            if S['len'] is not None:
                bad('вторая строка len'); continue
            S['len'] = v
        elif w == 'plate':
            if len(t) != 2 or t[1] not in COLORS:
                bad('plate <цвет>'); continue
            S['plate'] = t[1]
        elif w == 'brick':
            if len(t) != 5:
                bad('brick <деталь> <клетка> <направление> <цвет>'); continue
            k, c, d, col = t[1], cell(t[2]), t[3], t[4]
            if k not in KINDS: bad('нет детали ' + k); continue
            if c is None: bad('нет клетки ' + t[2]); continue
            if d not in DIRS: bad('нет направления ' + d); continue
            if col not in COLORS: bad('нет цвета ' + col); continue
            cells = [(c[0] + DIRS[d][0] * i, c[1] + DIRS[d][1] * i) for i in range(KINDS[k])]
            if any(not (0 <= x < N and 0 <= y < N) for x, y in cells):
                bad('деталь выходит за плиту'); continue
            hit = [cc for cc in cells if cc in occ]
            if hit:
                bad('клетка %s уже занята' % name(hit[0])); continue
            for cc in cells:
                occ[cc] = k
            S['bricks'].append(dict(kind=k, cells=cells, dir=d, color=col))
        elif w == 'hero':
            if len(t) != 5:
                bad('hero <имя> <вид> <клетка> <направление>'); continue
            nm, lk, c, d = t[1], t[2], cell(t[3]), t[4]
            if nm in S['heroes']: bad('второй персонаж ' + nm); continue
            if lk not in LOOKS: bad('нет вида ' + lk); continue
            if c is None: bad('нет клетки ' + t[3]); continue
            if d not in DIRS: bad('нет направления ' + d); continue
            if c in occ and occ[c] not in STANDABLE:
                bad('персонаж стоит внутри детали ' + occ[c]); continue
            S['heroes'][nm] = dict(look=lk, cell=c, dir=d)
        elif w == 'act':
            # act <имя> <действие> [to <клетка>] from <t>s to <t>s
            if len(t) not in (7, 9) or t[-4] != 'from' or t[-2] != 'to':
                bad('act <имя> <действие> [to <клетка>] from <начало>s to <конец>s'); continue
            nm, a = t[1], t[2]
            t0, t1 = secs(t[-3]), secs(t[-1])
            dest = None
            if len(t) == 9:
                if t[3] != 'to': bad('ожидалось to <клетка>'); continue
                dest = cell(t[4])
                if dest is None: bad('нет клетки ' + t[4]); continue
            if nm not in S['heroes']: bad('нет персонажа ' + nm); continue
            if a not in MOVES + STAYS: bad('нет действия ' + a); continue
            if a in MOVES and dest is None: bad(a + ' требует to <клетка>'); continue
            if a in STAYS and dest is not None: bad(a + ' — действие на месте, без to'); continue
            if t0 is None or t1 is None or t1 <= t0: bad('время from/to'); continue
            S['acts'].append(dict(hero=nm, act=a, dest=dest, t0=t0, t1=t1, line=no, src=ln))
        elif w == 'face':
            if len(t) != 5 or t[3] != 'at':
                bad('face <имя> <лицо> at <время>s'); continue
            if t[1] not in S['heroes']: bad('нет персонажа ' + t[1]); continue
            if t[2] not in FACES: bad('нет лица ' + t[2]); continue
            v = secs(t[4])
            if v is None: bad('время'); continue
            S['faces'].append(dict(hero=t[1], face=t[2], t=v))
        elif w == 'cam':
            shake = t[-1] == 'shake'
            tt = t[:-1] if shake else t
            if len(tt) != 6 or tt[2] != 'on' or tt[4] != 'at':
                bad('cam <план> on <имя или клетка> at <время>s [shake]'); continue
            if tt[1] not in SHOTS: bad('нет плана ' + tt[1]); continue
            tgt = tt[3] if tt[3] in S['heroes'] else cell(tt[3])
            if tgt is None: bad('цель камеры не персонаж и не клетка: ' + tt[3]); continue
            v = secs(tt[5])
            if v is None: bad('время'); continue
            S['cams'].append(dict(shot=tt[1], target=tgt, t=v, shake=shake))
        elif w == 'fx':
            if len(t) != 6 or t[2] != 'on' or t[4] != 'at':
                bad('fx <эффект> on <имя или клетка> at <время>s'); continue
            if t[1] not in FX: bad('нет эффекта ' + t[1]); continue
            tgt = t[3] if t[3] in S['heroes'] else cell(t[3])
            if tgt is None: bad('цель эффекта: ' + t[3]); continue
            v = secs(t[5])
            if v is None: bad('время'); continue
            S['fx'].append(dict(fx=t[1], target=tgt, t=v))
        else:
            bad('нет команды ' + w)

    if S['len'] is None: errs.append('нет строки len')
    if S['plate'] is None: errs.append('нет строки plate')
    L = S['len'] or 0
    if not S['heroes']: errs.append('нет ни одного персонажа')
    if not S['cams']: errs.append('нет ни одной строки cam')
    elif min(c['t'] for c in S['cams']) != 0: errs.append('первая cam не at 0s')
    for item in S['faces'] + S['cams'] + S['fx']:
        if L and not (0 <= item['t'] <= L): errs.append('время %.1fs вне сцены' % item['t'])

    # действия по персонажам: время, наложение, путь
    for nm, h in S['heroes'].items():
        pos = h['cell']
        last = -1.0
        for a in sorted([a for a in S['acts'] if a['hero'] == nm], key=lambda a: a['t0']):
            pre = 'строка %d «%s»: ' % (a['line'], a['src'])
            if L and a['t1'] > L + 1e-9: errs.append(pre + 'кончается после конца сцены')
            if a['t0'] < last - 1e-9: errs.append(pre + 'накладывается на прошлое действие ' + nm)
            last = max(last, a['t1'])
            a['from'] = pos
            if a['dest'] is None:
                continue
            d = a['dest']
            if d in occ and not (a['act'] in ('climb', 'jump') and occ[d] in STANDABLE):
                errs.append(pre + 'клетка назначения %s занята деталью %s' % (name(d), occ[d])); continue
            if a['act'] in ('walk', 'run', 'sneak'):
                blk = path_block(pos, d, occ)
                if blk: errs.append(pre + 'путь идёт сквозь %s на %s' % (occ[blk], name(blk)))
            pos = d
        h['end'] = pos
    return S, errs


def name(c):
    return '%s%d' % (COLS[c[0]], c[1] + 1)


def path_block(a, b, occ):
    steps = 40
    for i in range(1, steps):
        x = a[0] + (b[0] - a[0]) * i / steps
        y = a[1] + (b[1] - a[1]) * i / steps
        c = (int(round(x)), int(round(y)))
        if c != a and c != b and c in occ:
            return c
    return None


def check_must(S, must):
    looks = {nm: h['look'] for nm, h in S['heroes'].items()}
    have = set('brick:' + b['kind'] for b in S['bricks'])
    cnt = {}
    for lk in looks.values():
        cnt[lk] = cnt.get(lk, 0) + 1
    for lk, n in cnt.items():
        have.add('look:' + lk)
        if n >= 2: have.add('look:%s*2' % lk)
    for a in S['acts']:
        if a['hero'] in looks: have.add('act:%s:%s' % (looks[a['hero']], a['act']))
    for f in S['faces']:
        if f['hero'] in looks: have.add('face:%s:%s' % (looks[f['hero']], f['face']))
    for c in S['cams']:
        have.add('cam:' + c['shot'])
        if c['shake']: have.add('shake')
    for f in S['fx']:
        have.add('fx:' + f['fx'])
    missing = [m for m in must if not any(alt in have for alt in m.split('|'))]
    return missing


if __name__ == '__main__':
    S, e = compile_program(open(sys.argv[1]).read())
    if e:
        print(chr(10).join(e)); sys.exit(1)
    print(json.dumps(S, ensure_ascii=False, indent=1, default=list))
