"""Обработчик языка «кубики» v3.1: строки приводятся к форме v3, дальше работает kubiki_core3.

Что добавлено к v3 (по ошибкам прогона v3, до прогона v3.1):
- персонажа зовут по виду (guard, второй guard2); если модель всё же дала имя, оно работает;
- у детали клетка необязательна: сборщик раскладывает детали по своей сетке мест;
- деталь, которую упомянули (у кого-то рядом, через неё прыгают, на неё смотрит камера), но не поставили,
  ставится сама;
- скобки <...> и [...] вокруг слов снимаются;
- «act <кто> <лицо> at t» понимается как face; «act <кто> <действие> ... at t» — как from t to t+1;
- в cam/fx целью берётся первое слово, которое можно понять.
Каждая такая правка — в S['fixes'].
"""
import json
import sys

import kubiki_core3 as K3
from kubiki_core import COLS, KINDS, COLORS, LOOKS, FACES, secs
from kubiki_core2 import DIRW, check_must2  # noqa: F401

ANCHORS = [(2, 5), (6, 5), (4, 8), (4, 2), (8, 8), (1, 8), (8, 2), (1, 2), (8, 5), (0, 5)]
WHERE = ('near', 'behind', 'on', 'at')


def clean(tok):
    while len(tok) > 1 and tok[0] in '<[' and tok[-1] in '>]':
        tok = tok[1:-1]
    return tok.strip('<>[],.')


def is_cell(tok):
    return len(tok) >= 2 and tok[0] in COLS and tok[1:].isdigit() and 1 <= int(tok[1:]) <= 10


def normalize(text):
    fixes = []
    lines = []
    for ln in text.split(chr(10)):
        ln = ln.strip().strip('`').strip()
        if not ln or ln.startswith('#') or ln.startswith('```'):
            continue
        t = [clean(x) for x in ln.split()]
        t = [x for x in t if x]
        if t:
            lines.append((ln, t))
    out = []
    declared = []
    heroes = {}   # имя в программе -> вид
    count = {}
    anchor = iter(ANCHORS)

    def cellname(c):
        return '%s%d' % (COLS[c[0]], c[1] + 1)

    # детали
    for ln, t in lines:
        if t[0].lower() != 'brick' or len(t) < 2:
            continue
        kinds = [x for x in t[1:] if x in KINDS]
        if not kinds:
            out.append(ln); continue
        k = kinds[0]
        col = next((x for x in t if x in COLORS), 'gray')
        cl = next((x for x in t if is_cell(x)), None)
        d = next((DIRW[x] for x in t[2:] if x in DIRW and x not in ('s',)), 'e')
        if cl is None:
            cl = cellname(next(anchor, (4, 4)))
            fixes.append(ln + ': место детали выбрал сборщик')
        if len(kinds) > 1 or col == 'gray' and 'gray' not in t:
            fixes.append(ln + ': понято как одна деталь ' + k)
        declared.append(k)
        out.append('brick %s %s %s %s' % (k, cl, d, col))
    # детали, упомянутые, но не поставленные
    for ln, t in lines:
        if t[0].lower() in ('hero', 'act', 'cam', 'fx'):
            for x in t[1:]:
                if x in KINDS and x not in declared:
                    declared.append(x)
                    out.append('brick %s %s e gray' % (x, cellname(next(anchor, (4, 4)))))
                    fixes.append('деталь %s упомянута без brick: поставлена' % x)
    # персонажи
    for ln, t in lines:
        if t[0].lower() != 'hero':
            continue
        if len(t) < 2:
            out.append(ln); continue
        lk = t[1]
        rest = t[2:]
        if lk not in LOOKS and lk[:-1] in LOOKS and lk[-1].isdigit():
            lk = lk[:-1]; fixes.append(ln + ': вид с цифрой понят как второй персонаж этого вида')
        if lk not in LOOKS and rest and rest[0] in LOOKS:
            lk, rest = rest[0], [t[1]] + rest[1:]
        if lk not in LOOKS:
            out.append(ln); continue
        count[lk] = count.get(lk, 0) + 1
        auto = lk if count[lk] == 1 else '%s%d' % (lk, count[lk])
        if rest and rest[0] not in WHERE and not is_cell(rest[0]) and rest[0] not in DIRW:
            nm = rest[0]; rest = rest[1:]
            heroes[auto] = nm   # вид тоже ведёт к нему
        else:
            nm = auto
        heroes[nm] = nm
        where = rest if 'of' in rest else [x for x in rest if x not in DIRW or x in ('on',)]
        if where and where[0] == 'at' and len(where) > 1:
            where[0] = 'near'
        if not where:
            fixes.append(ln + ': место не указано')
        out.append('hero %s %s %s' % (lk, nm, ' '.join(where)))

    def ref(x):
        return heroes.get(x, x)

    # действия, лица, камера, эффекты
    for ln, t in lines:
        w = t[0].lower()
        if w == 'act' and len(t) >= 3:
            who, a = ref(t[1]), t[2]
            if a in FACES and 'at' in t:
                out.append('face %s %s at %s' % (who, a, t[t.index('at') + 1]))
                fixes.append(ln + ': понято как face'); continue
            body = [ref(x) for x in t[3:]]
            if 'from' not in body and 'at' in body:
                i = body.index('at')
                v = secs(body[i + 1]) if i + 1 < len(body) else None
                if v is not None:
                    body = body[:i] + ['from', '%gs' % v, 'to', '%gs' % (v + 1.0)]
                    fixes.append(ln + ': at понят как секунда действия')
            # цель из нескольких слов-деталей: первое слово
            if 'from' in body:
                i = len(body) - 1 - body[::-1].index('from')
                spec = body[:i]
                if len(spec) >= 2 and spec[0] in ('to', 'over', 'past', 'onto', 'toward', 'towards', 'into', 'through'):
                    spec = spec[:2]
                elif len(spec) >= 3 and spec[0] == 'away':
                    spec = spec[:3]
                body = spec + body[i:]
            out.append(' '.join(['act', who, a] + body))
        elif w == 'face' and len(t) >= 3:
            out.append(' '.join(['face', ref(t[1])] + t[2:]))
        elif w in ('cam', 'fx') and 'on' in t and 'at' in t:
            i, j = t.index('on'), t.index('at')
            tg = next((ref(x) for x in t[i + 1:j] if x in heroes or x in KINDS or is_cell(x)), None)
            if tg is None:
                tg = t[i + 1] if i + 1 < j else '?'
            tail = t[j:j + 2] + (['shake'] if 'shake' in t[j:] else [])
            out.append(' '.join(t[:i + 1] + [tg] + tail))
        elif w in ('len', 'plate'):
            out.append(' '.join(t))
        elif w not in ('brick', 'hero'):
            out.append(ln)
    return chr(10).join(out), fixes


def compile_program(text):
    norm, fixes = normalize(text)
    S, errs = K3.compile_program(norm)
    S['fixes'] = fixes + S.get('fixes', [])
    S['normalized'] = norm
    return S, errs


if __name__ == '__main__':
    S, e = compile_program(open(sys.argv[1]).read())
    print(S['normalized'])
    print(chr(10).join(e) if e else 'ок')
