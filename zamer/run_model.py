"""Прогон Qwen 3.5 9B (Ollama) по сценам: программа на языке «кубики», проверка обработчиком и must.

    python3 run_model.py noise          # сцена 1 три раза (шум повтора)
    python3 run_model.py main           # сцены 1..10 по разу
Пишет out/<режим>/<сцена>_<повтор>.kub, out/<режим>/results.json.
"""
import json
import os
import sys
import time
import urllib.request

import kubiki_core as K
import kubiki_core2 as K2

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = 'qwen3.5:9b'
V = os.environ.get('KUBIKI_V', '1')
SPEC = open(os.path.join(HERE, 'LANGUAGE-kubiki.md' if V == '1' else 'LANGUAGE-kubiki-v2.md')).read()
SCENES = json.load(open(os.path.join(HERE, 'scenes.json')))['scenes']


def ask(text):
    prompt = (SPEC + chr(10) + 'ЗАДАЧА. Напиши программу на этом языке для сцены ниже. Выведи только строки программы, '
              'без пояснений и без разметки.' + chr(10) + chr(10) + 'СЦЕНА: ' + text)
    body = dict(model=MODEL, messages=[dict(role='user', content=prompt)], stream=False, think=False,
                options=dict(num_ctx=4096))
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=1500))
    return r['message']['content'], time.time() - t, r.get('prompt_eval_count'), r.get('eval_count')


def run(mode):
    jobs = [(1, i) for i in (1, 2, 3)] if mode == 'noise' else [(s['id'], 1) for s in SCENES]
    out = os.path.join(HERE, 'out', mode if V == '1' else 'v2_' + mode)
    os.makedirs(out, exist_ok=True)
    res = []
    for sid, rep in jobs:
        sc = SCENES[sid - 1]
        txt, sec, pin, pout = ask(sc['text'])
        open(os.path.join(out, '%02d_%d.kub' % (sid, rep)), 'w').write(txt)
        if V == '1':
            S, errs = K.compile_program(txt)
            miss = K.check_must(S, sc['must'])
        else:
            S, errs = K2.compile_program(txt)
            miss = K2.check_must2(S, sc['must'])
        ok = not errs and not miss
        res.append(dict(scene=sid, rep=rep, ok=ok, errors=errs, missing=miss, fixes=S.get('fixes', []), sec=round(sec, 1),
                        prompt_tokens=pin, out_tokens=pout))
        print('сцена %d повтор %d: %s  ошибок %d, не хватает %s  (%.0f с)' % (
            sid, rep, 'ОСМЫСЛЕННЫЙ' if ok else 'нет', len(errs), miss, sec), flush=True)
        for e in errs[:4]:
            print('   ', e, flush=True)
    json.dump(dict(model=MODEL, lang=V, mode=mode, results=res, ok=sum(r['ok'] for r in res), n=len(res)),
              open(os.path.join(out, 'results.json'), 'w'), ensure_ascii=False, indent=1)
    print('итог %s: %d из %d' % (mode, sum(r['ok'] for r in res), len(res)))


if __name__ == '__main__':
    run(sys.argv[1])
