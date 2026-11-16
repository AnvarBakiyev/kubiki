"""Рендер сцены «кубики» в Blender по JSON обработчика kubiki_core.py.

  blender -b --factory-startup --python render_kubiki.py -- --scene s.json --out out/clip
          [--engine eevee|cycles] [--fps 12] [--res 1920x1080] [--frames 0,30] [--samples 32]

Все детали и персонаж построены кодом (своя геометрия, без LDraw). Персонаж свой: крупная скруглённая голова,
бочонок-туловище, короткие ноги, без кистей-захватов. Камера с малой глубиной резкости и дрожанием ручной съёмки,
персонажи на 12 кадрах в секунду с микросдвигом от кадра к кадру, как при покадровой съёмке.
"""
import argparse
import json
import math
import os
import random
import sys
import time
T_START = time.time()

import bmesh
import bpy
from mathutils import Euler, Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--scene', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--engine', default='eevee')
ap.add_argument('--fps', type=int, default=12)
ap.add_argument('--res', default='1920x1080')
ap.add_argument('--frames', default='')
ap.add_argument('--samples', type=int, default=32)
ap.add_argument('--place', default='')  # street|park|market|prison: город вокруг площадки
A = ap.parse_args(argv)
OUT = os.path.abspath(A.out)
os.makedirs(OUT, exist_ok=True)
S = json.load(open(A.scene))

STUD, H, PH = 0.008, 0.0096, 0.0032
CELL = 2 * STUD
SR, SH = 0.0024, 0.0017
COL = dict(red='#b8201c', blue='#1f5fae', yellow='#f2c418', green='#2f8a3c', white='#eeeeea', black='#202022',
           gray='#8d9094', tan='#d6c08f', orange='#e5731c', brown='#6b3f22')
DIRV = dict(n=(0, 1), s=(0, -1), e=(1, 0), w=(-1, 0))
rnd = random.Random(11)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def hexrgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1]


_mats = {}


def plastic(hexc, emit=0.0, alpha=1.0):
    key = (hexc, emit, alpha)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new('p' + hexc + str(emit))
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hexrgb(hexc)
    b.inputs['Roughness'].default_value = 0.22
    b.inputs['Coat Weight'].default_value = 0.15
    if emit:
        b.inputs['Emission Color'].default_value = hexrgb(hexc)
        b.inputs['Emission Strength'].default_value = emit
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
    # отпечатки и неровность пластика: шум в шероховатости и лёгкий рельеф
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 900.0
    nz.inputs['Detail'].default_value = 3.0
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.12
    mr.inputs['To Max'].default_value = 0.38
    nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.03
    bp.inputs['Distance'].default_value = 0.0002
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    _mats[key] = m
    return m


def link(ob, parent=None):
    sc.collection.objects.link(ob)
    if parent:
        ob.parent = parent
    return ob


def box_mesh(bm, x0, y0, z0, sx, sy, sz):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co.x = x0 + (v.co.x + 0.5) * sx
        v.co.y = y0 + (v.co.y + 0.5) * sy
        v.co.z = z0 + (v.co.z + 0.5) * sz


def cyl_mesh(bm, x, y, z0, r, h, seg=16):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    for v in res['verts']:
        v.co += Vector((x, y, z0 + h / 2))


def brick_obj(name, w, d, layers, color, at, studs=True, parent=None, bevel=0.00035, plate=False):
    """Кубик w x d шипов, высота layers кирпичей (или пластина). at — левый нижний угол в метрах."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    hh = PH if plate else H * layers
    g = 0.0001
    box_mesh(bm, g, g, 0, w * STUD - 2 * g, d * STUD - 2 * g, hh)
    if studs:
        for i in range(w):
            for j in range(d):
                cyl_mesh(bm, (i + 0.5) * STUD, (j + 0.5) * STUD, hh, SR, SH)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me), parent)
    ob.location = at
    mod = ob.modifiers.new('bv', 'BEVEL')
    mod.width = bevel
    mod.segments = 2
    mod.limit_method = 'ANGLE'
    ob.data.materials.append(plastic(COL.get(color, color)))
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def round_obj(name, r, layers, color, at, parent=None, stud=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    cyl_mesh(bm, 0, 0, 0, r, H * layers, 24)
    if stud:
        cyl_mesh(bm, 0, 0, H * layers, SR, SH)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me), parent)
    ob.location = at
    ob.data.materials.append(plastic(COL.get(color, color)))
    return ob


def cell_xy(c):
    return ((c[0] - 4.5) * CELL, (c[1] - 4.5) * CELL)


def cell_corner(c):
    return ((c[0] - 5) * CELL, (c[1] - 5) * CELL)


# ---------------- плита и детали ----------------
brick_obj('plate', 20, 20, 1, S['plate'], (-10 * STUD, -10 * STUD, -PH), plate=True)
HEIGHT = {}  # высота детали на клетке (для прыжков и стояния наверху)
STAND = {}


def build_brick(b, idx):
    k, col, cells, d = b['kind'], b['color'], [tuple(c) for c in b['cells']], b['dir']
    x0 = min(cell_corner(c)[0] for c in cells)
    y0 = min(cell_corner(c)[1] for c in cells)
    along_x = d in ('e', 'w')
    n = len(cells)
    L = n * 2  # шипов вдоль
    nm = '%s%d' % (k, idx)
    if k == 'block':
        brick_obj(nm, 2, 2, 1, col, (x0, y0, 0)); h = H
    elif k == 'crate':
        for z in range(2):
            brick_obj(nm + str(z), 2, 2, 1, col, (x0, y0, z * H), studs=(z == 1))
        h = 2 * H
        STAND[cells[0]] = h + SH
    elif k == 'wall':
        layers = 5
        for z in range(layers):
            off = (z % 2)
            pos = -off
            while pos < L:
                a, bb = max(pos, 0), min(pos + 2, L)
                if along_x:
                    brick_obj('%s_%d_%d' % (nm, z, a), bb - a, 1, 1, col,
                              (x0 + a * STUD, y0 + 0.5 * STUD, z * H), studs=True)
                else:
                    brick_obj('%s_%d_%d' % (nm, z, a), 1, bb - a, 1, col,
                              (x0 + 0.5 * STUD, y0 + a * STUD, z * H), studs=True)
                pos += 2
        h = layers * H
    elif k == 'bars':
        hb = 5
        if along_x:
            brick_obj(nm + 'b', L, 1, 1, col, (x0, y0 + 0.5 * STUD, 0), plate=True, studs=False)
            brick_obj(nm + 't', L, 1, 1, col, (x0, y0 + 0.5 * STUD, hb * H), plate=True)
            for i in range(L + 1):
                round_obj(nm + 'r%d' % i, 0.0009, hb, 'black', (x0 + i * STUD, y0 + STUD, PH), stud=False)
        else:
            brick_obj(nm + 'b', 1, L, 1, col, (x0 + 0.5 * STUD, y0, 0), plate=True, studs=False)
            brick_obj(nm + 't', 1, L, 1, col, (x0 + 0.5 * STUD, y0, hb * H), plate=True)
            for i in range(L + 1):
                round_obj(nm + 'r%d' % i, 0.0009, hb, 'black', (x0 + STUD, y0 + i * STUD, PH), stud=False)
        h = hb * H + PH
    elif k == 'door':
        brick_obj(nm, 2 if along_x else 1, 1 if along_x else 2, 5, col,
                  (x0 + (0 if along_x else 0.5 * STUD), y0 + (0.5 * STUD if along_x else 0), 0))
        kn = round_obj(nm + 'k', 0.0012, 0.3, 'yellow', (0, 0, 0), stud=False)
        kn.rotation_euler = (math.pi / 2, 0, 0) if along_x else (0, math.pi / 2, 0)
        kn.location = (x0 + (1.6 * STUD if along_x else 0.5 * STUD - 0.0003),
                       y0 + (0.5 * STUD - 0.0003 if along_x else 1.6 * STUD), 2.4 * H)
        h = 5 * H
    elif k == 'tree':
        cx, cy = cell_xy(cells[0])
        # крона начинается выше макушки (голова в шапке до ~0,047 м), иначе сосед по клетке прячет в ней лицо
        round_obj(nm + 'trunk', STUD * 0.45, 5, 'brown', (cx, cy, 0), stud=False)
        brick_obj(nm + 'c1', 4, 4, 1, col, (cx - 2 * STUD, cy - 2 * STUD, 5 * H), studs=False)
        brick_obj(nm + 'c2', 2, 2, 2, col, (cx - STUD, cy - STUD, 6 * H))
        h = 8 * H
    elif k == 'lamp':
        cx, cy = cell_xy(cells[0])
        round_obj(nm + 'post', STUD * 0.4, 6, 'black', (cx, cy, 0), stud=False)
        brick_obj(nm + 'top', 2, 2, 1, 'black', (cx - STUD, cy - STUD, 6 * H), plate=True)
        round_obj(nm + 'glass', STUD * 0.7, 0.8, '#ffe9a8', (cx, cy, 6 * H - 0.8 * H), stud=False).data.materials[0] = \
            plastic('#ffe9a8', emit=8.0)
        L_ = bpy.data.lights.new(nm + 'L', 'POINT')
        L_.energy = 0.6
        L_.color = (1.0, 0.85, 0.6)
        L_.shadow_soft_size = 0.004
        lo = link(bpy.data.objects.new(nm + 'L', L_))
        lo.location = (cx, cy, 5.5 * H)
        h = 6 * H
    elif k == 'tower':
        for (ix, iy) in ((0, 0), (1, 0), (0, 1), (1, 1)):
            for z in range(6):
                brick_obj('%sleg%d%d%d' % (nm, ix, iy, z), 1, 1, 1, 'gray' if z % 2 else col,
                          (x0 + ix * STUD, y0 + iy * STUD, z * H), studs=False)
        # площадка шире ног: наверху помещаются двое
        brick_obj(nm + 'top', 4, 4, 1, col, (x0 - STUD, y0 - STUD, 6 * H), plate=True)
        h = 6 * H + PH
        STAND[cells[0]] = h + SH
    elif k == 'car':
        lx, ly = (L, 2) if along_x else (2, L)
        brick_obj(nm + 'ch', lx, ly, 1, 'black', (x0, y0, 0.6 * H), plate=True, studs=False)
        brick_obj(nm + 'b1', lx, ly, 1, col, (x0, y0, 0.6 * H + PH), studs=False)
        if along_x:
            brick_obj(nm + 'cab', 2, 2, 1, col, (x0 + STUD, y0, 0.6 * H + PH + H))
            brick_obj(nm + 'gl', 1, 2, 1, '#9fc6e0', (x0 + 3 * STUD, y0, 0.6 * H + PH + H), studs=False)
            wpos = [(x0 + 0.8 * STUD, y0 - 0.0005), (x0 + 3.2 * STUD, y0 - 0.0005),
                    (x0 + 0.8 * STUD, y0 + 2 * STUD + 0.0005), (x0 + 3.2 * STUD, y0 + 2 * STUD + 0.0005)]
            wrot = (math.pi / 2, 0, 0)
        else:
            brick_obj(nm + 'cab', 2, 2, 1, col, (x0, y0 + STUD, 0.6 * H + PH + H))
            brick_obj(nm + 'gl', 2, 1, 1, '#9fc6e0', (x0, y0 + 3 * STUD, 0.6 * H + PH + H), studs=False)
            wpos = [(x0 - 0.0005, y0 + 0.8 * STUD), (x0 - 0.0005, y0 + 3.2 * STUD),
                    (x0 + 2 * STUD + 0.0005, y0 + 0.8 * STUD), (x0 + 2 * STUD + 0.0005, y0 + 3.2 * STUD)]
            wrot = (0, math.pi / 2, 0)
        for i, (wx, wy) in enumerate(wpos):
            w_ = round_obj(nm + 'w%d' % i, 0.0055, 0.4, 'black', (0, 0, 0), stud=False)
            w_.rotation_euler = wrot
            w_.location = (wx, wy, 0.0055)
        h = 0.6 * H + PH + 2 * H
    else:
        h = H
    for c in cells:
        HEIGHT[c] = h


for i, b in enumerate(S['bricks']):
    build_brick(b, i)

# фон: светлый изогнутый задник и стол
bd = bpy.data.meshes.new('backdrop')
bm = bmesh.new()
box_mesh(bm, -1.0, -1.0, -PH - 0.01, 2.0, 2.0, 0.01)
box_mesh(bm, -1.0, 0.45, -PH, 2.0, 0.01, 1.0)
bm.to_mesh(bd)
bm.free()
bo = link(bpy.data.objects.new('backdrop', bd)) if not A.place else bpy.data.objects.new('backdrop', bd)
mb = bpy.data.materials.new('bd')
mb.use_nodes = True
mb.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = hexrgb('#c9cdd3')
mb.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
bo.data.materials.append(mb)
if A.place:
    bo.location.z = -10.0

# ---------------- лица ----------------
FACE_DIR = os.path.join(OUT, '_faces')
os.makedirs(FACE_DIR, exist_ok=True)


def face_png(mood):
    """Лицо рисуется в PNG без сторонних библиотек: пиксели считаются в Python."""
    W = 128
    px = [0.0] * (W * W * 4)

    def dot(cx, cy, rx, ry):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if 0 <= x < W and 0 <= y < W and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                    i = (y * W + x) * 4
                    px[i:i + 4] = [0.05, 0.04, 0.04, 1.0]

    def line(x0, y0, x1, y1, th):
        n = 60
        for k in range(n + 1):
            t = k / n
            dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, th, th)

    def arc(cx, cy, r, a0, a1, th, sy=1.0):
        n = 50
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            dot(cx + r * math.cos(a), cy + r * sy * math.sin(a), th, th)

    ey = 72  # глаза (y вверх)
    big = mood in ('scared', 'surprised')
    for ex in (42, 86):
        dot(ex, ey, 7 if big else 6, 9 if big else 8)
        if not big:
            pass
    # брови
    br = dict(calm=(0, 0), happy=(3, 3), angry=(-9, 9), scared=(8, -6), surprised=(8, 8), sly=(-6, 2))[mood]
    line(32, ey + 15 - br[1] * 0, 52, ey + 15 + br[0] * 0.6, 2.4) if mood != 'angry' else line(32, ey + 20, 52, ey + 12, 2.6)
    line(76, ey + 15 + br[0] * 0.6, 96, ey + 15 - br[1] * 0, 2.4) if mood != 'angry' else line(76, ey + 12, 96, ey + 20, 2.6)
    if mood in ('scared', 'surprised'):
        line(32, ey + 18, 52, ey + 22, 2.4); line(76, ey + 22, 96, ey + 18, 2.4)
    # рот
    my = 38
    if mood == 'happy':
        arc(64, my + 10, 20, math.pi * 1.15, math.pi * 1.85, 2.8)
    elif mood == 'angry':
        arc(64, my - 6, 16, math.pi * 0.2, math.pi * 0.8, 2.6)
    elif mood == 'scared':
        arc(64, my, 9, 0, 2 * math.pi, 2.4, sy=0.6)
    elif mood == 'surprised':
        dot(64, my, 8, 10)
    elif mood == 'sly':
        line(50, my - 2, 80, my + 6, 2.4); arc(80, my + 10, 5, math.pi * 1.3, math.pi * 1.9, 2.2)
    else:
        line(52, my, 76, my, 2.4)
    img = bpy.data.images.new('face_' + mood, W, W, alpha=True)
    img.pixels = px
    p = os.path.join(FACE_DIR, mood + '.png')
    img.filepath_raw = p
    img.file_format = 'PNG'
    img.save()
    return img


FACE_IMG = {m: face_png(m) for m in ('calm', 'happy', 'angry', 'scared', 'surprised', 'sly')}
FACE_MAT = {}
for m, img in FACE_IMG.items():
    mt = bpy.data.materials.new('face_' + m)
    mt.use_nodes = True
    nt = mt.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    b.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
    b.inputs['Roughness'].default_value = 0.3
    nt.links.new(tx.outputs['Alpha'], b.inputs['Alpha'])
    mt.blend_method = 'HASHED' if hasattr(mt, 'blend_method') else None
    FACE_MAT[m] = mt

# ---------------- персонажи ----------------
SKIN = '#e9c49d'
LOOK = dict(prisoner=('orange', 'orange', None), guard=('#3d4249', 'black', 'black'),
            thief=('black', 'gray', 'black'), cop=('blue', '#16305a', 'blue'),
            kid=('yellow', 'red', None), citizen=('green', 'tan', None))
# причёски: цвет и форма (короткая, с чёлкой, длинные)
HAIR = dict(prisoner=('#3a2a1f', 'crop'), kid=('#9a5a24', 'fringe'), citizen=('#6b3a1f', 'long'))


def rounded_box(name, sx, sy, sz, r, color, parent, loc):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    box_mesh(bm, -sx / 2, -sy / 2, 0, sx, sy, sz)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me), parent)
    ob.location = loc
    mo = ob.modifiers.new('bv', 'BEVEL')
    mo.width = r
    mo.segments = 4
    ob.data.materials.append(plastic(COL.get(color, color)))
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def empty(name, parent=None, loc=(0, 0, 0)):
    e = link(bpy.data.objects.new(name, None), parent)
    e.location = loc
    return e


RIG = {}
for nm, h in S['heroes'].items():
    body, legs, hat = LOOK[h['look']]
    s = 0.82 if h['look'] == 'kid' else 1.0
    root = empty(nm)
    root.scale = (s, s, s)
    hips = empty(nm + '_hips', root, (0, 0, 0.012))
    lg = {}
    for side, x in (('L', -0.0042), ('R', 0.0042)):
        pv = empty(nm + '_leg' + side, hips, (x, 0, 0))
        rounded_box(nm + '_legm' + side, 0.0074, 0.0085, 0.012, 0.0018, legs, pv, (0, 0, -0.012))
        lg[side] = pv
    torso = rounded_box(nm + '_torso', 0.0175, 0.0105, 0.0135, 0.003, body, hips, (0, 0, 0))
    if h['look'] == 'prisoner':
        for z in (0.004, 0.0085):
            rounded_box(nm + '_str%.4f' % z, 0.0178, 0.0108, 0.0015, 0.0004, 'black', hips, (0, 0, z))
    if h['look'] == 'cop':
        rounded_box(nm + '_badge', 0.003, 0.001, 0.003, 0.0004, 'yellow', hips, (-0.004, 0.0053, 0.008))
    ar = {}
    for side, x in (('L', -0.0105), ('R', 0.0105)):
        pv = empty(nm + '_arm' + side, hips, (x, 0, 0.0115))
        rounded_box(nm + '_armm' + side, 0.0048, 0.0055, 0.0115, 0.0018, body, pv, (0, 0, -0.0115))
        rounded_box(nm + '_hand' + side, 0.0048, 0.0052, 0.0032, 0.0016, SKIN, pv, (0, 0, -0.0142))
        ar[side] = pv
    neck = empty(nm + '_neck', hips, (0, 0, 0.0135))
    head = rounded_box(nm + '_head', 0.0175, 0.0155, 0.0155, 0.0045, SKIN, neck, (0, 0, 0.0008))
    hair_col, style = HAIR.get(h['look'], (None, None))
    if not hat and hair_col:
        if h['look'] == 'citizen' and nm[-1].isdigit():
            hair_col, style = ('#2a2a2a', 'crop') if int(nm[-1]) % 2 == 0 else ('#c99a4b', 'fringe')
        rounded_box(nm + '_hairT', 0.0187, 0.0167, 0.0044, 0.0018, hair_col, neck, (0, -0.0001, 0.0133))
        rounded_box(nm + '_hairB', 0.0187, 0.0042, 0.0195 if style == 'long' else 0.0085, 0.0015, hair_col, neck,
                    (0, -0.0066, -0.0018 if style == 'long' else 0.009))
        if style == 'fringe':
            rounded_box(nm + '_hairF', 0.0187, 0.0032, 0.0034, 0.0012, hair_col, neck, (0, 0.0068, 0.0126))
        if style == 'long':
            for sx in (-0.0089, 0.0089):
                rounded_box(nm + '_hairS%d' % (sx > 0), 0.0034, 0.0125, 0.0175, 0.0012, hair_col, neck, (sx, -0.0012, -0.0005))
    elif hat:
        # из-под шапки видны виски
        for sx in (-0.0086, 0.0086):
            rounded_box(nm + '_hairS%d' % (sx > 0), 0.0024, 0.0110, 0.0060, 0.0009, '#2a2a2a', neck, (sx, -0.0018, 0.0100))
    if hat:
        rounded_box(nm + '_hat', 0.0185, 0.0165, 0.0045, 0.0015, hat, neck, (0, 0, 0.0155))
        if h['look'] == 'cop':
            rounded_box(nm + '_brim', 0.0185, 0.007, 0.0012, 0.0005, hat, neck, (0, 0.009, 0.0155))
    faces = {}
    for m in FACE_MAT:
        me = bpy.data.meshes.new(nm + '_f' + m)
        bm = bmesh.new()
        r = bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.0068)
        bm.to_mesh(me)
        bm.free()
        me.uv_layers.new()
        for poly in me.polygons:
            for li in poly.loop_indices:
                v = me.vertices[me.loops[li].vertex_index].co
                me.uv_layers[0].data[li].uv = (v.x / 0.0136 * 0.7 + 0.5, v.y / 0.0136 * 0.7 + 0.5)
        fo = link(bpy.data.objects.new(nm + '_f' + m, me), neck)
        fo.rotation_euler = (math.pi / 2, 0, 0)
        fo.location = (0, 0.0078 + 0.00012, 0.0083)
        fo.data.materials.append(FACE_MAT[m])
        faces[m] = fo
    RIG[nm] = dict(root=root, hips=hips, leg=lg, arm=ar, neck=neck, face=faces, look=h['look'], s=s)


# ---------------- время: состояние персонажа ----------------
def yaw_of(d):
    return math.atan2(-d[0], d[1])


def ground(c):
    return STAND.get(tuple(c), SH * 0.6)


def path_top(a, b):
    top = 0.0
    for i in range(41):
        x = a[0] + (b[0] - a[0]) * i / 40
        y = a[1] + (b[1] - a[1]) * i / 40
        top = max(top, HEIGHT.get((int(round(x)), int(round(y))), 0.0))
    return top


ACTS = {}
for a in S['acts']:
    ACTS.setdefault(a['hero'], []).append(a)
for v in ACTS.values():
    v.sort(key=lambda a: a['t0'])


def hero_state(nm, t):
    """Положение по программе, а затем расталкивание: двое не проходят друг сквозь друга.
    Каждый отходит от соседа на половину нехватки до 1,25 клетки; если стоят в одной точке — по оси x
    (порядок по имени), иначе вдоль линии между ними. Работает на ходу, а не только когда стоят."""
    st = _hero_state(nm, t)
    MIN = 1.25 * CELL
    raw = {o: _hero_state(o, t) for o in S['heroes']}
    names = sorted(raw)
    px, py = st['xy']
    for _ in range(1):
        for o in names:
            if o == nm or abs(raw[o]['z'] - st['z']) > 0.03:
                continue
            ox, oy = raw[o]['xy']
            vx, vy = px - ox, py - oy
            d = math.hypot(vx, vy)
            if d >= MIN:
                continue
            if d < 1e-5:
                vx, vy, d = (1.0 if names.index(nm) > names.index(o) else -1.0), 0.0, 1.0
                push = MIN / 2
            else:
                push = (MIN - d) / 2
            px, py = px + vx / d * push, py + vy / d * push
    st['xy'] = (px, py)
    return st


def _hero_state(nm, t):
    h = S['heroes'][nm]
    pos = tuple(h['cell'])
    yaw = yaw_of(DIRV[h['dir']])
    st = dict(z=ground(pos), act='stand', u=0.0, tl=t, fallen=False)
    xy = cell_xy(pos)
    for a in ACTS.get(nm, []):
        if t < a['t0']:
            break
        fr, de = tuple(a['from']), (tuple(a['dest']) if a['dest'] else None)
        u = min(1.0, (t - a['t0']) / (a['t1'] - a['t0']))
        st = dict(act=a['act'], u=u, tl=t - a['t0'], fallen=False, dur=a['t1'] - a['t0'])
        if de:
            p0, p1 = cell_xy(fr), cell_xy(de)
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            if abs(dx) + abs(dy) > 1e-9:
                yaw = math.atan2(-dx, dy)
            ue = u if a['act'] in ('run', 'walk', 'sneak') else (0.5 - 0.5 * math.cos(math.pi * u))
            xy = (p0[0] + dx * ue, p0[1] + dy * ue)
            pts = [cell_xy(c) for c in a.get('path') or []]
            if len(pts) > 2 and a['act'] in ('run', 'walk', 'sneak'):
                seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
                want = sum(seg) * ue
                for i, sl in enumerate(seg):
                    if want <= sl or i == len(seg) - 1:
                        k = min(1.0, want / sl) if sl else 1.0
                        q0, q1 = pts[i], pts[i + 1]
                        xy = (q0[0] + (q1[0] - q0[0]) * k, q0[1] + (q1[1] - q0[1]) * k)
                        yaw = math.atan2(-(q1[0] - q0[0]), q1[1] - q0[1])
                        break
                    want -= sl
            z0, z1 = ground(fr), ground(de)
            z = z0 + (z1 - z0) * ue
            if a['act'] in ('climb', 'jump'):
                top = path_top(fr, de)
                lift = max(0.0, top + 0.006 - max(z0, z1)) + 0.008
                z += lift * math.sin(math.pi * u)
            st['z'] = z
            pos = de if u >= 1 else pos
        else:
            xy = cell_xy(fr)
            st['z'] = ground(fr)
            if a['act'] == 'fall':
                st['fallen'] = True
        if u >= 1:
            st['act'] = 'stand' if a['act'] != 'fall' else 'lying'
    st['xy'] = xy
    st['yaw'] = yaw
    return st


def mood_at(nm, t):
    m = 'calm'
    for f in sorted(S['faces'], key=lambda f: f['t']):
        if f['hero'] == nm and f['t'] <= t + 1e-6:
            m = f['face']
    return m


def pose(nm, t, jit):
    R = RIG[nm]
    st = hero_state(nm, t)
    root = R['root']
    x, y = st['xy']
    root.location = (x + jit.gauss(0, 0.00012), y + jit.gauss(0, 0.00012), st['z'])
    root.rotation_euler = (0, 0, st['yaw'] + jit.gauss(0, 0.012))
    a, tl = st['act'], st['tl']
    sw = arm = lean = crouch = 0.0
    armL = armR = None
    if a in ('walk', 'run', 'sneak'):
        amp, f = dict(walk=(0.45, 2.0), run=(0.8, 3.2), sneak=(0.3, 1.4))[a]
        sw = amp * math.sin(2 * math.pi * f * tl)
        lean = dict(walk=0.05, run=0.22, sneak=0.15)[a]
        crouch = 0.25 if a == 'sneak' else 0.0
    elif a in ('climb', 'jump'):
        sw = 0.5 * math.sin(math.pi * st['u'])
        armL = armR = -2.4 * math.sin(math.pi * st['u'])
    elif a == 'wave':
        armR = -2.6 + 0.35 * math.sin(2 * math.pi * 3 * tl)
    elif a == 'hide':
        crouch = 0.45
        armL = armR = -2.7
    elif a == 'push':
        armL = armR = -1.5
        lean = 0.3
    fallen = a in ('fall', 'lying')
    fall_ang = (min(1.0, st['u'] / 0.4) if a == 'fall' else 1.0) * 1.45 if fallen else 0.0
    R['hips'].location = (0, 0, 0.012 * (1 - crouch * 0.5) if not fallen else 0.004 * fall_ang + 0.012 * (1 - fall_ang / 1.45))
    R['hips'].rotation_euler = (-(lean + fall_ang), 0, 0)
    R['leg']['L'].rotation_euler = (sw + (crouch * -1.0), 0, 0)
    R['leg']['R'].rotation_euler = (-sw + (crouch * -1.0), 0, 0)
    R['arm']['L'].rotation_euler = (armL if armL is not None else -sw * 0.9, 0, 0)
    R['arm']['R'].rotation_euler = (armR if armR is not None else sw * 0.9, 0, 0)
    R['neck'].rotation_euler = (0, 0, jit.gauss(0, 0.02))
    m = mood_at(nm, t)
    for k, fo in R['face'].items():
        fo.hide_render = (k != m)
        fo.hide_viewport = (k != m)
    return st


# ---------------- эффекты ----------------
DUST = []
for i, f in enumerate(S['fx']):
    if f['fx'] in ('dust', 'crash'):
        grp = []
        for j in range(14 if f['fx'] == 'dust' else 22):
            me = bpy.data.meshes.new('d%d_%d' % (i, j))
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            bm.to_mesh(me)
            bm.free()
            o = link(bpy.data.objects.new('d%d_%d' % (i, j), me))
            o.data.materials.append(plastic('#b9ad9c', alpha=0.5))
            grp.append((o, rnd.uniform(0, 2 * math.pi), rnd.uniform(0.4, 1.0), rnd.uniform(0.002, 0.0045)))
        DUST.append((f, grp))
FLASH = []
for i, f in enumerate(S['fx']):
    if f['fx'] in ('flash', 'alarm', 'crash'):
        L_ = bpy.data.lights.new('fx%d' % i, 'POINT')
        L_.color = (1, 0.1, 0.05) if f['fx'] == 'alarm' else (1, 1, 0.95)
        L_.shadow_soft_size = 0.01
        lo = link(bpy.data.objects.new('fx%d' % i, L_))
        FLASH.append((f, L_, lo))


def target_xyz(tgt, t, head=True):
    if isinstance(tgt, str):
        st = hero_state(tgt, t)
        return Vector((st['xy'][0], st['xy'][1], st['z'] + (0.03 if head else 0.015) * RIG[tgt]['s']))
    x, y = cell_xy(tgt)
    return Vector((x, y, 0.012))


def fx_update(t):
    for f, grp in DUST:
        u = (t - f['t']) / 0.8
        p = target_xyz(f['target'], f['t'], head=False)
        for o, ang, sp, r in grp:
            if 0 <= u <= 1:
                o.hide_render = False
                rr = 0.004 + 0.018 * u * sp
                o.location = (p.x + rr * math.cos(ang), p.y + rr * math.sin(ang), 0.002 + 0.008 * u * sp)
                o.scale = (r * (0.6 + u),) * 3
            else:
                o.hide_render = True
    for f, L_, lo in FLASH:
        p = target_xyz(f['target'], t)
        lo.location = (p.x, p.y - 0.01, p.z + 0.03)
        dt = t - f['t']
        if f['fx'] == 'alarm':
            L_.energy = (3.0 if (dt >= 0 and int(dt * 6) % 2 == 0) else 0.0)
        else:
            L_.energy = 6.0 * math.exp(-dt * 8) if dt >= 0 else 0.0


# ---------------- свет и камера ----------------
def area(name, loc, power, size, color, target=(0, 0, 0.01)):
    L_ = bpy.data.lights.new(name, 'AREA')
    L_.energy = power
    L_.size = size
    L_.color = color
    o = link(bpy.data.objects.new(name, L_))
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


area('key', (-0.25, -0.3, 0.35), 7, 0.25, (1.0, 0.93, 0.84))
area('fill', (0.35, -0.2, 0.15), 2, 0.3, (0.85, 0.9, 1.0))
area('rim', (0.1, 0.4, 0.3), 4, 0.2, (1.0, 0.95, 0.9))
w = bpy.data.worlds.new('w')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.52, 0.56, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.12

camd = bpy.data.cameras.new('cam')
cam = link(bpy.data.objects.new('cam', camd))
sc.camera = cam
camd.dof.use_dof = True
camd.clip_start = 0.001
camd.clip_end = 5.0
camd.sensor_width = 23.5
# в городе общий план ниже и дальше: видно улицу и дома, а не одну плиту сверху
SHOT = dict(wide=(0.42, 0.30, 30, 11.0) if A.place else (0.30, 0.55, 30, 11.0), medium=(0.17, 0.30, 45, 11.0 if A.place else 8.0), close=(0.13, 0.12, 55, 9.0 if A.place else 8.0),
            low=(0.12, 0.02, 30, 8.0), top=(0.24, 1.15, 35, 11.0), follow=(0.16, 0.25, 45, 8.0))
CAMS = sorted(S['cams'], key=lambda c: c['t'])


CROWN = [cell_xy(_c) for _b in S['bricks'] if _b['kind'] == 'tree' for _c in _b['cells']]


def blocked(p, q, t=0.0, skip=None):
    """Луч камера -> цель упирается в деталь, крону дерева или другого персонажа."""
    others = []
    for nm in RIG:
        if nm != skip:
            st = hero_state(nm, t)
            others.append((st['xy'], st['z'], 0.045 * RIG[nm]['s']))
    for i in range(1, 60):
        v = p + (q - p) * (i / 60)
        if (q - v).length < 0.012:
            break
        c = (int(math.floor(v.x / CELL + 5)), int(math.floor(v.y / CELL + 5)))
        if c in HEIGHT and v.z < HEIGHT[c] and c not in STAND:
            return True
        if 5 * H < v.z < 8.3 * H and any(abs(v.x - tx) < 2 * STUD and abs(v.y - ty) < 2 * STUD for tx, ty in CROWN):
            return True
        for (hx, hy), hz, hh in others:
            if abs(v.x - hx) < 0.6 * CELL and abs(v.y - hy) < 0.6 * CELL and hz < v.z < hz + hh:
                return True
    return False


_CUT = {}
_JIT0 = random.Random(0)


def _mine(ob, nm):
    n = ob.original.name if hasattr(ob, 'original') else ob.name
    return n == nm or n.startswith(nm + '_')


def _see_through(ob):
    import re
    n = ob.original.name if hasattr(ob, 'original') else ob.name
    return bool(re.match(r'^(bars\d+r\d+|d\d+_\d+)$', n)) or n.startswith('fx')


_STATIC = []


def _hero_of(name):
    for h in RIG:
        if name == h or name.startswith(h + '_'):
            return h
    return None


def _bvh_of(obs):
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for ob in obs:
        mw = ob.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in ob.data.vertices]
        polys += [[base + i for i in pl.vertices] for pl in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys) if polys else None


_TREES = {}


def _trees_at(t):
    """Деревья поиска для героев в момент t: поза зависит только от времени, строим один раз на момент."""
    if t not in _TREES:
        for o in RIG:
            pose(o, t, _JIT0)
        bpy.context.view_layer.update()
        trees = {}
        for ob in sc.objects:
            h = _hero_of(ob.name)
            if h and ob.type == 'MESH' and not ob.hide_viewport:
                trees.setdefault(h, []).append(ob)
        _TREES[t] = {h: _bvh_of(v) for h, v in trees.items()}
    return _TREES[t]


def head_visible(p, nm, t):
    """Луч от камеры до головы героя: первым попадается сам герой (сквозь прутья решётки видно).
    Своё дерево поиска (BVH): неподвижное строится один раз, герои — на каждую пробу. scene.ray_cast
    на городе перестраивал всё на каждый луч и шёл минутами."""
    if not _STATIC:
        bpy.context.view_layer.update()
        stat = [ob for ob in sc.objects if ob.type == 'MESH' and not _hero_of(ob.name) and not _see_through(ob)
                and not ob.name.startswith(('city_g_', 'city_far', 'city_marks', 'plate', 'backdrop'))]
        _STATIC.append(_bvh_of(stat))
    trees = _trees_at(t)
    st = hero_state(nm, t)
    s_ = RIG[nm]['s']
    # лицо должно смотреть в сторону камеры, иначе снимаем затылок
    fx_, fy_ = -math.sin(st['yaw']), math.cos(st['yaw'])
    cx_, cy_ = p.x - st['xy'][0], p.y - st['xy'][1]
    # лицо нарисовано только спереди: в профиль (90°) его не видно, нужен поворот к камере не больше ~70°
    if (fx_ * cx_ + fy_ * cy_) / (math.hypot(cx_, cy_) or 1) < 0.35 and st['act'] not in ('fall', 'lying'):
        return False
    ok = 0
    for dz in (0.034, 0.028):
        q = Vector((st['xy'][0], st['xy'][1], st['z'] + dz * s_))
        d, far = (q - p).normalized(), (q - p).length
        own = trees[nm].ray_cast(p, d, far + 0.02)[3] if trees.get(nm) else None
        lim = own if own is not None else far
        hit = False
        for tr in [_STATIC[0]] + [tr for h, tr in trees.items() if h != nm]:
            if tr is None:
                continue
            dist = tr.ray_cast(p, d, lim)[3]
            if dist is not None and dist < lim - 1e-5:
                hit = True
                break
        ok += not hit
    return ok == 2


def on_cell(c, t):
    """Цель-клетка, на которой стоит герой (наверху вышки): камера смотрит на него, а не в основание детали."""
    for nm in RIG:
        st = hero_state(nm, t)
        if math.dist(st['xy'], cell_xy(c)) < 0.6 * CELL:
            return nm
    return None


def _near_heroes(xy, t0, t1, r):
    """Герои, которые в начале или в конце плана стоят ближе r к точке xy."""
    out = []
    for h in sorted(RIG):
        for tp in (t0, t1):
            hx, hy = hero_state(h, tp)['xy']
            if math.hypot(hx - xy[0], hy - xy[1]) < r:
                out.append(h)
                break
    return out


def cam_update(t, jit):
    c = dict([c for c in CAMS if c['t'] <= t + 1e-6][-1])
    key = [i for i, x in enumerate(CAMS) if x['t'] <= t + 1e-6][-1]
    nxt = [x['t'] for x in CAMS if x['t'] > c['t']]
    t_end = min(nxt) if nxt else S['len']
    if not isinstance(c['target'], str):
        hn = on_cell(c['target'], c['t'])
        hn = hn or on_cell(c['target'], t_end - 0.05)
        if hn and c['shot'] != 'wide':
            c['target'] = hn
    dist, elev, lens, fst = SHOT[c['shot']]
    near_shot = c['shot'] in ('close', 'medium', 'low', 'follow')
    # группа: план на деталь, а рядом герои — снимаем героев (середину группы), а не деталь;
    # план на героя, а рядом другие — их лица тоже должны быть видны
    grp, main = [], None
    if near_shot and not isinstance(c['target'], str):
        grp = _near_heroes(cell_xy(c['target']), c['t'], t_end - 0.05, 4 * CELL)
    elif near_shot:
        main = c['target']
        st0 = hero_state(main, c['t'])['xy']
        grp = [main] + [h for h in _near_heroes(st0, c['t'], t_end - 0.05, 3 * CELL) if h != main]
        if len(grp) == 1:
            grp, main = [], None

    def aim(tp):
        if grp:
            vs = [target_xyz(h, tp) for h in grp]
            return sum(vs, Vector((0, 0, 0))) / len(vs)
        return target_xyz(c['target'], tp)

    tgt_now = aim(t)
    base = tgt_now if (grp or isinstance(c['target'], str)) else target_xyz(c['target'], c['t'])
    if c['shot'] == 'wide':
        base = Vector((base.x * 0.4, base.y * 0.4, 0.01))
        tgt_now = base
    front = math.radians(-18)
    if isinstance(c['target'], str) and near_shot and not grp:
        yw = hero_state(c['target'], c['t'])['yaw']
        front = math.atan2(-math.sin(yw), -math.cos(yw))  # направление «лицом к камере»
    if len(grp) >= 2:
        # двое и больше: смотреть поперёк линии между ними, тогда оба в профиль или вполоборота,
        # а не один из них затылком к камере
        tm = (c['t'] + t_end) / 2
        ax, ay = hero_state(grp[0], tm)['xy']
        bx, by = hero_state(grp[1], tm)['xy']
        nx, ny = -(by - ay), (bx - ax)
        if ny > 0:
            nx, ny = -nx, -ny  # камера с ближней к зрителю стороны
        if abs(nx) + abs(ny) > 1e-6:
            front = math.atan2(nx, -ny)
    if key not in _CUT:
        t_cut = time.time()
        # место камеры выбирается один раз на склейку: смотрим начало, середину и конец плана
        probes = [c['t'], (c['t'] + t_end) / 2, max(c['t'], t_end - 0.05)]
        skip = c['target'] if isinstance(c['target'], str) else None
        lows = (0.006, 0.02, 0.04, 0.06)
        face = (isinstance(c['target'], str) and near_shot) or bool(grp)
        # группа шире кадра: отойти, чтобы поместились все
        scale = 1.0
        if grp:
            span = max([0.0] + [(target_xyz(a, tp) - target_xyz(b, tp)).length
                                for tp in probes for a in grp for b in grp])
            scale = max(1.0, (span + 3 * CELL) / (dist * 36.0 / lens))  # ширина кадра ~ расстояние * 36 / фокусное
        fronts = (0, 20, -20, 45, -45, 70, -70)
        order = [(dd, li, dm) for dm in (1.0, 1.4, 1.9) for li in (0, 1) for dd in fronts] + \
                [(dd, 2, dm) for dm in (1.0, 1.4, 1.9) for dd in fronts]
        if grp:
            order += [(dd, li, dm) for dm in (1.0, 1.4) for li in (0, 1) for dd in (180, 160, -160)]
        if face and not grp:
            # сзади лица не видно, но если спереди закрыто всё, лучше отойти сбоку, чем снимать сверху
            order += [(dd, li, dm) for dm in (1.0, 1.4) for li in (0, 1) for dd in (100, -100)]
        if not face:
            order = [(dd, li, 1.0) for dd in (0, 20, -20, 45, -45) for li in range(4)] + \
                    [(dd, li, 1.0) for li in range(4) for dd in (75, -75, 110, -110, 150, -150, 180)]
        full = len(probes) * ((len(grp) + (1 if main else 0)) if grp else 1)
        best, best_n = None, -1
        for dd, li, dm in order:
            n_ok = 0
            for tp in probes:
                bp = aim(tp) if (grp or isinstance(c['target'], str)) else base
                if c['shot'] == 'wide':
                    bp = base
                el = elev + (0.0, 0.3, 0.6, 0.95)[li]
                az = front + math.radians(dd)
                cand = bp + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist * dm * scale
                if c['shot'] == 'low':
                    cand.z = lows[li] if dm == 1.0 else lows[li] + 0.5 * (bp.z - lows[li]) * (dm - 1)
                if c['shot'] in ('wide', 'top'):
                    n_ok += 1
                elif grp:
                    for h in grp:
                        # лицо главного героя весит вдвое
                        n_ok += head_visible(cand, h, tp) * (2 if h == main else 1)
                elif isinstance(c['target'], str):
                    n_ok += head_visible(cand, c['target'], tp)
                else:
                    n_ok += not blocked(cand, bp, tp, skip)
            if n_ok > best_n:
                best, best_n = (dd, li, dm * scale), n_ok
            if n_ok >= full:
                break
        _CUT[key] = best
        print('KUBIKI cam cut %d %s%s -> (%d, %d, %.2f) (%d/%d) %.1fs' % (
            key, c['target'], (' group ' + ','.join(grp)) if grp else '', best[0], best[1], best[2],
            best_n, full, time.time() - t_cut), flush=True)
        for o in RIG:
            pose(o, t, jit)
    dd, li, dm = _CUT[key]
    el = elev + (0.0, 0.3, 0.6, 0.95)[li]
    az = front + math.radians(dd)
    pos = base + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist * dm
    if c['shot'] == 'low':
        lw = (0.006, 0.02, 0.04, 0.06)[li]
        pos.z = lw if dm == 1.0 else lw + 0.5 * (base.z - lw) * (dm - 1)
    k = 0.0009 if c['shake'] else 0.00012
    pos += Vector((jit.gauss(0, k), jit.gauss(0, k), jit.gauss(0, k)))
    cam.location = pos
    d = tgt_now - pos
    e = d.to_track_quat('-Z', 'Y').to_euler()
    rk = 0.012 if c['shake'] else 0.0015
    cam.rotation_euler = (e.x + jit.gauss(0, rk), e.y + jit.gauss(0, rk * 0.5), e.z + jit.gauss(0, rk))
    camd.lens = lens
    camd.dof.aperture_fstop = fst if not grp else max(fst, 16.0)
    camd.dof.focus_distance = d.length - (0.008 if (grp or isinstance(c['target'], str)) else 0.0)


if A.place:
    exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'city_block.py')).read())

# ---------------- движок ----------------
rx, ry = [int(v) for v in A.res.split('x')]
sc.render.resolution_x, sc.render.resolution_y = rx, ry
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'AgX'
try:
    sc.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass
if A.engine == 'cycles':
    sc.render.engine = 'CYCLES'
    pr = bpy.context.preferences.addons['cycles'].preferences
    pr.compute_device_type = 'METAL'
    pr.get_devices()
    for d in pr.devices:
        d.use = True
    sc.cycles.device = 'GPU'
    sc.cycles.samples = A.samples
    sc.cycles.use_denoising = True
    sc.cycles.use_adaptive_sampling = True
else:
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
    ee = sc.eevee
    ee.taa_render_samples = A.samples
    if hasattr(ee, 'use_raytracing'):
        ee.use_raytracing = True
    if hasattr(ee, 'use_shadows'):
        ee.use_shadows = True
    for mt in FACE_MAT.values():
        if hasattr(mt, 'surface_render_method'):
            mt.surface_render_method = 'DITHERED'

print('KUBIKI setup %.1fs' % (time.time() - T_START), flush=True)
L = S['len']
nfr = int(round(L * A.fps))
frames = [int(v) for v in A.frames.split(',')] if A.frames else list(range(nfr))
times = []
for fi in frames:
    t = fi / A.fps
    jit = random.Random(1000 + fi)
    for nm in RIG:
        pose(nm, t, jit)
    fx_update(t)
    cam_update(t, jit)
    sc.render.filepath = os.path.join(OUT, 'f%04d.png' % fi)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    times.append(round(time.time() - t0, 2))
    print('KUBIKI frame %d %.2fs' % (fi, times[-1]), flush=True)
json.dump(dict(engine=A.engine, res=A.res, samples=A.samples, fps=A.fps, frames=frames, sec=times,
               devices=[d.name for d in bpy.context.preferences.addons['cycles'].preferences.devices if d.use]
               if A.engine == 'cycles' else None),
          open(os.path.join(OUT, 'timings_%s.json' % A.engine), 'w'), indent=1)
