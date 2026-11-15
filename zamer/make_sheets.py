"""Контактные листы для проверки на глаз: по каждой сцене первый ответ, прошедший форму (лучше всего полный),
три кадра (20 %, 55 %, 90 % длины), Eevee 640x360. Склейка 3x10 в один jpg.

    python3 make_sheets.py r3_v3plan  ->  out/r3_v3plan/sheet.jpg, out/r3_v3plan/sheet_pick.json
"""
import json
import os
import subprocess
import sys

import kubiki_core2 as K2
import kubiki_core3 as K3

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
cfg = sys.argv[1]
d = os.path.join(HERE, 'out', cfg)
res = json.load(open(os.path.join(d, 'results.json')))['results']
import kubiki_core31 as K31
K = K2 if cfg.endswith('v2') else (K31 if ('v31' in cfg or 'v32' in cfg) else K3)
tmp = os.path.join(os.path.expanduser(os.environ.get('KUBIKI_FRAMES', '~/kubiki-frames')), 'sheets', cfg)
os.makedirs(tmp, exist_ok=True)
pick, rows = {}, []
for sid in range(1, 11):
    rs = [r for r in res if r['scene'] == sid]
    best = next((r for r in rs if r['full_ok']), None) or next((r for r in rs if r['must_ok']), None) or \
        next((r for r in rs if r['valid']), None)
    if best is None:
        rows.append(None); continue
    S, e = K.compile_program(open(os.path.join(d, '%02d_%d.kub' % (sid, best['rep']))).read())
    sj = os.path.join(tmp, 's%02d.json' % sid)
    json.dump(S, open(sj, 'w'), default=list)
    fps = 12
    n = int(S['len'] * fps)
    fr = [int(n * 0.2), int(n * 0.55), min(n - 1, int(n * 0.9))]
    od = os.path.join(tmp, 's%02d' % sid)
    subprocess.run([BL, '-b', '--factory-startup', '--python', os.path.join(HERE, 'render_kubiki.py'), '--',
                    '--scene', sj, '--out', od, '--res', '640x360', '--samples', '16',
                    '--frames', ','.join(map(str, fr))], capture_output=True)
    rows.append([os.path.join(od, 'f%04d.png' % f) for f in fr])
    pick[sid] = dict(rep=best['rep'], full_ok=best['full_ok'], must_ok=best['must_ok'], staging=best['staging'])
    print(sid, pick[sid], flush=True)
# склейка: строка на сцену
inputs, filt = [], []
k = 0
for i, row in enumerate(rows):
    for p in (row or []):
        inputs += ['-i', p]
    if row:
        filt.append(''.join('[%d]' % (k + j) for j in range(3)) + 'hstack=3,drawtext=text=%d:x=10:y=10:fontsize=40:'
                    'fontcolor=red[r%d]' % (i + 1, i))
        k += 3
names = ''.join('[r%d]' % i for i, row in enumerate(rows) if row)
cnt = sum(1 for row in rows if row)
filt.append('%svstack=%d,scale=1440:-1' % (names, cnt) if cnt > 1 else names + 'scale=1440:-1')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + inputs +
               ['-filter_complex', ';'.join(filt), '-q:v', '4', os.path.join(d, 'sheet.jpg')], check=True)
json.dump(pick, open(os.path.join(d, 'sheet_pick.json'), 'w'), ensure_ascii=False, indent=1)
print('лист', os.path.join(d, 'sheet.jpg'))
