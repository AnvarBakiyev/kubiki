"""Прогон трёх настроек по 3 повтора на каждую из десяти сцен, Qwen 3.5 9B (Ollama).

    python3 run3.py v2        язык v2, одна подсказка (база с шумом)
    python3 run3.py v3        язык v3 (отношения), одна подсказка
    python3 run3.py v31 | v31plan   язык v3.1 (по видам, без клеток)
    python3 run3.py v3plan    язык v3, сначала модель раскладывает сцену на события, потом пишет программу

Для каждого ответа: ошибки обработчика, недостающие must, проверка расстановки (staging.py).
Пишет out/r3_<настройка>/<сцена>_<повтор>.kub (+ .plan.txt), results.json.
"""
import json
import os
import sys

import kubiki_core2 as K2
import kubiki_core3 as K3
import kubiki_core31 as K31
import run_model as R
from staging import staging_check

HERE = os.path.dirname(os.path.abspath(__file__))
SCENES = json.load(open(os.path.join(HERE, 'scenes.json')))['scenes']
SPEC2 = open(os.path.join(HERE, 'LANGUAGE-kubiki-v2.md')).read()
SPEC3 = open(os.path.join(HERE, 'LANGUAGE-kubiki-v3.md')).read()
SPEC31 = open(os.path.join(HERE, 'LANGUAGE-kubiki-v31.md')).read()
SPEC32 = open(os.path.join(HERE, 'LANGUAGE-kubiki-v32.md')).read()
NL = chr(10)
TASK = 'ЗАДАЧА. Напиши программу на этом языке для сцены ниже. Выведи только строки программы, без пояснений и без разметки.'
PLAN = ('Разложи сцену ниже на события по порядку времени. Сначала строки «деталь: ...» — какие детали нужны. '
        'Потом строки «в начале: <кто> <где стоит относительно чего>». Потом строки «событие: <кто> <что делает> '
        '<относительно чего или кого> <с какой по какую секунду>». Отдельным событием каждое действие, каждое '
        'выражение лица и каждая смена камеры из описания. Ничего не пропускай и не добавляй. Только список.')


BACKEND = os.environ.get('KUBIKI_BACKEND', 'ollama')  # ollama | api (любой OpenAI-совместимый сервер)
if BACKEND == 'azure':
    BACKEND = 'api'  # старое имя, так шёл замер: DeepSeek-V4-Flash на Azure AI Foundry
API_URL = os.environ.get('KUBIKI_API_URL', '')  # например https://<ресурс>.services.ai.azure.com/openai/v1/chat/completions
AZ_MODEL = os.environ.get('KUBIKI_API_MODEL', os.environ.get('KUBIKI_AZ_MODEL', 'DeepSeek-V4-Flash'))
KEY_FILE = os.path.expanduser(os.environ.get('KUBIKI_API_KEY_FILE', '~/.config/kubiki/api.key'))
MODEL_NAME = AZ_MODEL if BACKEND == 'api' else R.MODEL
TAG = '' if BACKEND == 'ollama' else '_ds'


def chat(prompt):
    import json as J
    import time
    import urllib.error
    import urllib.request
    t = time.time()
    if BACKEND == 'api':
        if not API_URL:
            raise SystemExit('KUBIKI_API_URL не задан: адрес chat/completions вашего сервера')
        key = os.environ.get('KUBIKI_API_KEY') or open(KEY_FILE).readline().strip()
        body = dict(model=AZ_MODEL, messages=[dict(role='user', content=prompt)], stream=False, max_tokens=1500)
        head = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key, 'api-key': key}
        for attempt in range(6):
            try:
                req = urllib.request.Request(API_URL, data=J.dumps(body).encode(), headers=head)
                r = J.load(urllib.request.urlopen(req, timeout=600))
                return r['choices'][0]['message'].get('content') or '', time.time() - t
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 5:  # лимит 125 тыс. токенов в минуту
                    time.sleep(60); continue
                raise
    body = dict(model=R.MODEL, messages=[dict(role='user', content=prompt)], stream=False, think=False,
                options=dict(num_ctx=4096))
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=J.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    r = J.load(urllib.request.urlopen(req, timeout=1500))
    return r['message']['content'], time.time() - t


def run(cfg, reps=3):
    out = os.path.join(HERE, 'out', 'r3_' + cfg + TAG)
    os.makedirs(out, exist_ok=True)
    K = K2 if cfg == 'v2' else (K31 if cfg.startswith('v31') or cfg.startswith('v32') else K3)
    spec = SPEC2 if cfg == 'v2' else (SPEC32 if cfg.startswith('v32') else (SPEC31 if cfg.startswith('v31') else SPEC3))
    res = []
    for sc in SCENES:
        for rep in range(1, reps + 1):
            plan = ''
            if cfg.endswith('plan'):
                plan, _ = chat(PLAN + NL + NL + 'СЦЕНА: ' + sc['text'])
                open(os.path.join(out, '%02d_%d.plan.txt' % (sc['id'], rep)), 'w').write(plan)
                prompt = (spec + NL + TASK + ' Каждое событие из плана должно стать строкой программы.' + NL + NL +
                          'СЦЕНА: ' + sc['text'] + NL + NL + 'ПЛАН СОБЫТИЙ:' + NL + plan)
            else:
                prompt = spec + NL + TASK + NL + NL + 'СЦЕНА: ' + sc['text']
            txt, sec = chat(prompt)
            open(os.path.join(out, '%02d_%d.kub' % (sc['id'], rep)), 'w').write(txt)
            S, errs = K.compile_program(txt)
            miss = K2.check_must2(S, sc['must']) if not errs else ['(ошибки)']
            stg = staging_check(S, sc['id']) if not errs else ['(ошибки)']
            r = dict(scene=sc['id'], rep=rep, valid=not errs, must_ok=not errs and not miss,
                     full_ok=not errs and not miss and not stg, errors=errs, missing=miss, staging=stg,
                     fixes=len(S.get('fixes', [])), sec=round(sec, 1))
            res.append(r)
            print('%s сцена %d/%d: %s %s %s' % (cfg, sc['id'], rep, 'ФОРМА' if r['valid'] else 'ошибки',
                  'НАБОР' if r['must_ok'] else '-', 'РАССТАНОВКА' if r['full_ok'] else ''), flush=True)
    summ = dict(valid=sum(r['valid'] for r in res), must=sum(r['must_ok'] for r in res),
                full=sum(r['full_ok'] for r in res), n=len(res),
                scenes_full_any=sorted(set(r['scene'] for r in res if r['full_ok'])),
                scenes_full_majority=sorted(s['id'] for s in SCENES
                                            if sum(r['full_ok'] for r in res if r['scene'] == s['id']) >= 2))
    json.dump(dict(model=MODEL_NAME, cfg=cfg, summary=summ, results=res), open(os.path.join(out, 'results.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(cfg, json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    run(sys.argv[1])
