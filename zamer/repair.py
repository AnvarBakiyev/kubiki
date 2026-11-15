"""Один круг исправления: ответ, не прошедший сборщик, возвращается модели вместе с ошибками сборщика.

    python3 repair.py r3_v31 [plan]   первая попытка берётся из out/<папка>, исправления пишутся в out/<папка>_fix
Ответы, прошедшие с первой попытки, не трогаются. Зачёт тот же: форма + must + расстановка.
"""
import json
import os
import sys

import kubiki_core31 as K31
import kubiki_core2 as K2
from run3 import chat, SCENES, SPEC31, SPEC32, NL, TASK
from staging import staging_check

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, 'out', sys.argv[1])
out = src + '_fix'
os.makedirs(out, exist_ok=True)
res = []
for sc in SCENES:
    for rep in (1, 2, 3):
        txt = open(os.path.join(src, '%02d_%d.kub' % (sc['id'], rep))).read()
        S, errs = K31.compile_program(txt)
        tries = 1
        if errs:
            prompt = ((SPEC32 if 'v32' in sys.argv[1] else SPEC31) + NL + TASK + NL + NL + 'СЦЕНА: ' + sc['text'] + NL + NL + 'ТВОЯ ПРОГРАММА:' + NL + txt +
                      NL + NL + 'СБОРЩИК НЕ ПРИНЯЛ СТРОКИ:' + NL + NL.join(errs) + NL + NL +
                      'Исправь эти строки словами из языка и выведи программу целиком, только строки программы.')
            txt, _ = chat(prompt)
            tries = 2
            S, errs = K31.compile_program(txt)
        open(os.path.join(out, '%02d_%d.kub' % (sc['id'], rep)), 'w').write(txt)
        miss = K2.check_must2(S, sc['must']) if not errs else ['(ошибки)']
        stg = staging_check(S, sc['id']) if not errs else ['(ошибки)']
        r = dict(scene=sc['id'], rep=rep, tries=tries, valid=not errs, must_ok=not errs and not miss,
                 full_ok=not errs and not miss and not stg, errors=errs, missing=miss, staging=stg)
        res.append(r)
        print('fix сцена %d/%d попыток %d: %s %s %s' % (sc['id'], rep, tries, 'ФОРМА' if r['valid'] else 'ошибки',
              'НАБОР' if r['must_ok'] else '-', 'РАССТАНОВКА' if r['full_ok'] else ''), flush=True)
summ = dict(valid=sum(r['valid'] for r in res), must=sum(r['must_ok'] for r in res),
            full=sum(r['full_ok'] for r in res), n=len(res), calls_extra=sum(r['tries'] - 1 for r in res),
            scenes_full_any=sorted(set(r['scene'] for r in res if r['full_ok'])),
            scenes_full_majority=sorted(s['id'] for s in SCENES
                                        if sum(r['full_ok'] for r in res if r['scene'] == s['id']) >= 2))
json.dump(dict(model=__import__('run3').MODEL_NAME, cfg=sys.argv[1] + '_fix', summary=summ, results=res), open(os.path.join(out, 'results.json'), 'w'),
          ensure_ascii=False, indent=1)
print('fix', json.dumps(summ, ensure_ascii=False))
