"""Реплики в пузырях: модель дописывает к готовой сцене, кто что говорит и когда; код проверяет строки
и рисует пузыри поверх кадров.

Программа сцены при этом не меняется: реплики лежат отдельным файлом NN_say.json рядом с NN.json.
Где на кадре голова героя, рендер пишет в heads.json (render_kubiki.py).

Форма строки:  say <герой> "<реплика>" from <начало>s to <конец>s
"""
import json
import math
import os
import re

NL = chr(10)
MAXLEN = 28
MAXN = 2

SPEC = """Ты пишешь реплики для пузырей в мультфильме из кубиков. Сцена уже собрана, менять в ней ничего нельзя:
нужно только добавить, кто что говорит и когда. Реплика рисуется пузырём над головой героя, как в комиксе.

ФОРМА СТРОКИ:
say <герой> "<реплика>" from <начало>s to <конец>s

ПРАВИЛА:
- герой берётся только из списка героев сцены, слово в слово;
- реплика по-русски, короткая, до %d знаков; восклицание или вопрос тоже годятся; кавычек внутри реплики нет;
- реплика держится от 1.5 до 3.5 секунды и целиком внутри длины сцены;
- в сцене 1 или 2 реплики; без реплик только сцена, где героям правда нечего сказать; две реплики одного героя
  по времени не пересекаются;
- реплика — прямая речь героя, а не описание того, что он делает или как выглядит («Хитрая улыбка» — не реплика);
- реплика двигает сюжет: зовёт, предупреждает, удивляется, радуется, грозит; зритель по ней понимает, что происходит;
- реплика совпадает с тем, что герой делает и чувствует в это время (смотри действия и лица);
- кто прячется или крадётся, говорит коротко шёпотом или молчит;
- реплика — это слова героя: не многоточие вместо слов и не ремарка в скобках; если герою нечего сказать, реплики нет;
- реплики не повторяют реплики прошлых сцен.
Выведи только строки say, без пояснений. Если в сцене говорить некому, выведи одно слово none.""" % MAXLEN

LINE = re.compile(r'^say\s+(\S+)\s+"([^"]+)"\s+from\s+([0-9.]+)\s*s\s+to\s+([0-9.]+)\s*s$')


def prompt(S, scene_text, roles, note, before):
    acts = sorted({a['src'] for a in S['acts']} | {'face %s %s at %gs' % (f['hero'], f['face'], f['t']) for f in S['faces']})
    heroes = [('%s (%s)' % (h, roles.get(h, roles.get(S['heroes'][h]['look'], h)))) for h in S['heroes']]
    return (SPEC + NL + NL + 'СЮЖЕТ СЕРИИ: ' + note + NL + NL + 'СЦЕНА (%g с): ' % S['len'] + scene_text + NL +
            'ГЕРОИ СЦЕНЫ: ' + ', '.join(heroes) + NL + 'ДЕЙСТВИЯ СЦЕНЫ:' + NL + NL.join(acts) + NL + NL +
            'РЕПЛИКИ ПРОШЛЫХ СЦЕН: ' + ('; '.join(before[-12:]) if before else 'нет'))


def _key(tx):
    return ''.join(ch for ch in tx.lower() if ch.isalpha())


def parse(text, S, before=()):
    """Строки say -> список реплик и список ошибок понятным текстом."""
    out, errs = [], []
    for raw in text.strip().splitlines():
        ln = raw.strip().strip('`').strip()
        if not ln or ln.lower() == 'none':
            continue
        m = LINE.match(ln)
        if not m:
            errs.append('строка не по форме: ' + ln)
            continue
        h, tx, a, b = m.group(1), m.group(2).strip(), float(m.group(3)), float(m.group(4))
        if h not in S['heroes']:
            errs.append('нет такого героя: %s (есть %s)' % (h, ', '.join(S['heroes'])))
            continue
        if sum(ch.isalpha() for ch in tx) < 2 or '(' in tx or ')' in tx:
            errs.append('реплика без слов или с ремаркой в скобках: ' + tx)
            continue
        if _key(tx) in {_key(b.split(': ', 1)[-1]) for b in before}:
            errs.append('реплика уже была в прошлой сцене: ' + tx)
            continue
        if len(tx) > MAXLEN:
            errs.append('реплика длиннее %d знаков: %s' % (MAXLEN, tx))
            continue
        if not (0 <= a < b <= S['len'] + 1e-6) or not (1.5 - 1e-6 <= b - a <= 3.5 + 1e-6):
            errs.append('время %gs-%gs: нужно от 1.5 до 3.5 с внутри сцены' % (a, b))
            continue
        if any(o['hero'] == h and a < o['t1'] and o['t0'] < b for o in out):
            errs.append('у %s две реплики в одно время' % h)
            continue
        out.append(dict(hero=h, text=tx, t0=a, t1=b))
    if len(out) > MAXN:
        errs.append('реплик больше %d' % MAXN)
        out = out[:MAXN]
    return out, errs


# ---------------- пузыри ----------------
def _wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def draw_bubbles(src, dst, items, font_path):
    """items: [(текст, (x_макушки, y_макушки), виден)] в долях кадра; y сверху вниз."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(src).convert('RGB')
    W, H = im.size
    k = H / 1080.0
    font = ImageFont.truetype(font_path, int(54 * k))
    dr = ImageDraw.Draw(im)
    pad, rad, ol, M = int(26 * k), int(34 * k), max(2, int(5 * k)), int(30 * k)
    boxes = []
    for text, (hx, hy), vis in items:
        lines = _wrap(dr, text, font, int(560 * k))
        lh = int(64 * k)
        tw = max(dr.textlength(l, font=font) for l in lines)
        bw, bh = int(tw + 2 * pad), int(len(lines) * lh + 2 * pad - 8 * k)
        on = vis and 0.0 <= hx <= 1.0 and 0.0 <= hy <= 1.0
        px, py = min(max(hx, 0.0), 1.0) * W, min(max(hy, 0.0), 1.0) * H
        tip = (px, py - 14 * k) if on else (px, py)
        cx = min(max(px, M + bw / 2), W - M - bw / 2)
        by1 = py - 80 * k  # низ пузыря над макушкой
        by0 = by1 - bh
        if by0 < M:
            by0, by1 = M, M + bh
        if on and by1 > tip[1] - 30 * k:
            # над головой места нет: пузырь сбоку от головы
            side = 1 if px < W / 2 else -1
            cx = min(max(px + side * (bw / 2 + 90 * k), M + bw / 2), W - M - bw / 2)
            by0 = min(max(py - bh / 2, M), H - M - bh)
            by1 = by0 + bh
        boxes.append([cx - bw / 2, by0, cx + bw / 2, by1, lines, lh, tip])
    # два пузыря не налезают друг на друга
    boxes.sort(key=lambda b: b[0])
    for i in range(1, len(boxes)):
        a, b = boxes[i - 1], boxes[i]
        if b[0] < a[2] + 20 * k and b[1] < a[3] and a[1] < b[3]:
            d = a[2] + 20 * k - b[0]
            if b[2] + d <= W - M:
                b[0] += d; b[2] += d
            else:
                a[0] -= d; a[2] -= d
    for x0, y0, x1, y1, lines, lh, tip in boxes:
        cx = (x0 + x1) / 2
        bx = min(max(tip[0], x0 + rad + 20 * k), x1 - rad - 20 * k)
        if tip[1] > y1:
            base = [(bx - 22 * k, y1 - 2), (bx + 22 * k, y1 - 2)]
        elif tip[1] < y0:
            base = [(bx - 22 * k, y0 + 2), (bx + 22 * k, y0 + 2)]
        else:
            sx = x1 - 2 if tip[0] > x1 else x0 + 2
            by = min(max(tip[1], y0 + rad), y1 - rad)
            base = [(sx, by - 20 * k), (sx, by + 20 * k)]
        # хвост не длиннее 120 px: дальний герой получает короткий хвост в его сторону
        bxm, bym = (base[0][0] + base[1][0]) / 2, (base[0][1] + base[1][1]) / 2
        dx, dy = tip[0] - bxm, tip[1] - bym
        dl = math.hypot(dx, dy) or 1.0
        L = min(dl, 120 * k)
        tp = (bxm + dx / dl * L, bym + dy / dl * L)
        tri = [base[0], base[1], tp]
        dr.rounded_rectangle([x0 - ol, y0 - ol, x1 + ol, y1 + ol], rad + ol, fill='#1e1e1e')
        dr.polygon(tri, fill='#1e1e1e', outline='#1e1e1e', width=ol * 2)
        dr.rounded_rectangle([x0, y0, x1, y1], rad, fill='#fbfaf5')
        dr.polygon(tri, fill='#fbfaf5')
        for i, l in enumerate(lines):
            tw = dr.textlength(l, font=font)
            dr.text((cx - tw / 2, y0 + pad - 6 * k + i * lh), l, font=font, fill='#1e1e1e')
    im.save(dst)


def bubble_frames(says, heads, fps, nfr):
    """Номер кадра -> список (текст, макушка, виден)."""
    out = {}
    for f in range(nfr):
        t = f / fps
        hd = heads.get(str(f))
        if not hd:
            continue
        cur = [(s['text'], (hd[s['hero']][0], hd[s['hero']][1]), hd[s['hero']][4])
               for s in says if s['t0'] <= t < s['t1'] and s['hero'] in hd]
        if cur:
            out[f] = cur
    return out
