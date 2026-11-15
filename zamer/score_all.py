"""Пересчёт всех прогонов последними версиями сборщиков и одной мерой. Пишет out/score_all.json и печатает таблицу.

Мера: форма (сборщик без ошибок), набор (все must), полностью (форма + must + расстановка из staging.py).
Сцена засчитана, если полностью верна хотя бы в 2 из 3 повторов.
"""
import glob
import json
import os

import kubiki_core as K1
import kubiki_core2 as K2
import kubiki_core3 as K3
import kubiki_core31 as K31
from staging import staging_check

HERE = os.path.dirname(os.path.abspath(__file__))
SC = {s['id']: s for s in json.load(open(os.path.join(HERE, 'scenes.json')))['scenes']}
RUNS = [('v1 (один раз)', 'main', K1, K1.check_must), ('v2 (один раз)', 'v2_main', K2, K2.check_must2),
        ('v2', 'r3_v2', K2, K2.check_must2), ('v3', 'r3_v3', K3, K2.check_must2),
        ('v3.1', 'r3_v31', K31, K2.check_must2), ('v3.1 + план', 'r3_v31plan', K31, K2.check_must2),
        ('v3.1 + исправление', 'r3_v31_fix', K31, K2.check_must2),
        ('v3.1 + план + исправление', 'r3_v31plan_fix', K31, K2.check_must2),
        ('v3.1 + план + исправление, повтор', 'r3_v31bplan_fix', K31, K2.check_must2),
        ('DeepSeek: v2', 'r3_v2_ds', K2, K2.check_must2),
        ('DeepSeek: v3.1', 'r3_v31_ds', K31, K2.check_must2),
        ('DeepSeek: v3.1 + исправление', 'r3_v31_ds_fix', K31, K2.check_must2),
        ('DeepSeek: v3.1, повтор', 'r3_v31b_ds', K31, K2.check_must2),
        ('DeepSeek: v3.1 + исправление, повтор', 'r3_v31b_ds_fix', K31, K2.check_must2),
        ('DeepSeek: v3.2', 'r3_v32_ds', K31, K2.check_must2),
        ('DeepSeek: v3.2 + исправление', 'r3_v32_ds_fix', K31, K2.check_must2),
        ('DeepSeek: v3.2, повтор', 'r3_v32b_ds', K31, K2.check_must2),
        ('DeepSeek: v3.2 + исправление, повтор', 'r3_v32b_ds_fix', K31, K2.check_must2)]
table = []
for label, folder, K, must in RUNS:
    files = sorted(glob.glob(os.path.join(HERE, 'out', folder, '*.kub')))
    if not files:
        continue
    per = {}
    v = m = f = 0
    for p in files:
        sid = int(os.path.basename(p)[:2])
        S, e = K.compile_program(open(p).read())
        ok_v = not e
        ok_m = ok_v and not must(S, SC[sid]['must'])
        ok_f = ok_m and not staging_check(S, sid)
        v += ok_v; m += ok_m; f += ok_f
        per.setdefault(sid, []).append(ok_f)
    reps = max(len(x) for x in per.values())
    maj = sorted(s for s, x in per.items() if sum(x) >= (2 if reps >= 3 else 1))
    table.append(dict(run=label, folder=folder, n=len(files), form=v, must=m, full=f, scenes=len(maj), scene_ids=maj))
json.dump(table, open(os.path.join(HERE, 'out', 'score_all.json'), 'w'), ensure_ascii=False, indent=1)
print('| настройка | ответов | форма | набор | полностью | сцен засчитано |')
print('|---|---|---|---|---|---|')
for t in table:
    print('| %s | %d | %d | %d | %d | %d %s |' % (t['run'], t['n'], t['form'], t['must'], t['full'], t['scenes'],
                                               t['scene_ids']))
