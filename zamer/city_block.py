# Вставляется в render_kubiki.py (exec) вместо белого задника, когда задано место: --place street|park|market|prison.
# Город собран из тех же кубиков: плиты-кварталы 20x20 шипов вокруг площадки действия, дома с окнами,
# машины, фонари, деревья, прилавки, стена тюрьмы. Для одного места город всегда одинаковый (своё зерно).
# Перед камерой (сторона -y, откуда обычно снимают общий план) дома стоят дальше, чтобы не загораживать.

TILE = 20 * STUD
crng = random.Random({'street': 3, 'park': 5, 'market': 7, 'prison': 9}.get(A.place, 1))
PAL = ['#c94a3a', '#e3c26b', '#5b7fb5', '#e6e2d8', '#8a9a7a', '#b07040', '#d98a4a', '#9aa3ad', '#6f8fa8', '#d6b4a0']


def boxes_obj(name, boxes, color, studs=(), bevel=0.0004, emit=0.0):
    """Много коробок и шипов одним мешем через from_pydata: bmesh-операция на каждую коробку шла минутами."""
    V, F = [], []
    for (x0, y0, z0, sx, sy, sz) in boxes:
        b = len(V)
        V += [(x0, y0, z0), (x0 + sx, y0, z0), (x0 + sx, y0 + sy, z0), (x0, y0 + sy, z0),
              (x0, y0, z0 + sz), (x0 + sx, y0, z0 + sz), (x0 + sx, y0 + sy, z0 + sz), (x0, y0 + sy, z0 + sz)]
        F += [(b, b + 3, b + 2, b + 1), (b + 4, b + 5, b + 6, b + 7), (b, b + 1, b + 5, b + 4),
              (b + 1, b + 2, b + 6, b + 5), (b + 2, b + 3, b + 7, b + 6), (b + 3, b, b + 4, b + 7)]
    ring = [(math.cos(2 * math.pi * k / 8) * SR, math.sin(2 * math.pi * k / 8) * SR) for k in range(8)]
    for (x, y, z) in studs:
        b = len(V)
        V += [(x + cx, y + cy, z) for cx, cy in ring] + [(x + cx, y + cy, z + SH) for cx, cy in ring]
        F += [(b + k, b + (k + 1) % 8, b + 8 + (k + 1) % 8, b + 8 + k) for k in range(8)]
        F.append(tuple(b + 8 + k for k in range(8)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(V, [], F)
    me.update()
    ob = link(bpy.data.objects.new(name, me))
    if bevel:
        mod = ob.modifiers.new('bv', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = 'ANGLE'
    ob.data.materials.append(plastic(COL.get(color, color), emit=emit))
    return ob


def studs_on(x0, y0, nx, ny, z):
    return [(x0 + (i + 0.5) * STUD, y0 + (j + 0.5) * STUD, z) for i in range(nx) for j in range(ny)]


def tile_type(i, j):
    r = max(abs(i), abs(j))
    p = A.place
    if p == 'street':
        if j == 0 or i == 3:
            return 'road'
        return 'walk'
    if p == 'park':
        if r <= 2:
            return 'path' if (j == 0 and abs(i) >= 1) else 'grass'
        return 'road' if (j == -3 or abs(i) == 3) and r == 3 else 'walk'
    if p == 'market':
        if r <= 1:
            return 'plaza'
        return 'road' if (j == -3 or i == 3) else 'walk'
    if p == 'prison':
        if r <= 2:
            return 'concrete'
        return 'road' if (j == -4 or i == 4) else 'walk'
    return 'walk'


GROUND = dict(road='#55585e', walk='#b8bcc2', grass='#4c9a3f', path='#d6c08f', plaza='#d9c9a3', concrete='#9a9da2')
RB, RF = dict(street=(2, 3), park=(3, 4), market=(2, 3), prison=(4, 4)).get(A.place, (3, 4))

# земля: плиты по типам, шипы только рядом с площадкой (дальше их съедает глубина резкости)
gb, gs = {}, {}
for i in range(-5, 6):
    for j in range(-5, 6):
        if i == 0 and j == 0:
            continue
        t = tile_type(i, j)
        x0, y0 = (i - 0.5) * TILE, (j - 0.5) * TILE
        gb.setdefault(t, []).append((x0, y0, -PH, TILE, TILE, PH))
        if t != 'road' and max(abs(i), abs(j)) <= 2:
            gs.setdefault(t, []).append((x0, y0))
for t, bx in gb.items():
    boxes_obj('city_g_' + t, bx, GROUND[t], bevel=0.0002)
# шипы на плитах рядом с площадкой: один меш 20x20 на тип, плиты ссылаются на него (строить каждый шип заново — минуты)
for t, corners in gs.items():
    tmpl = boxes_obj('city_gs_' + t + '_0', [], GROUND[t], studs_on(0, 0, 20, 20, 0.0), bevel=0)
    tmpl.location = (corners[0][0], corners[0][1], 0)
    for k, (x0, y0) in enumerate(corners[1:]):
        ob = link(bpy.data.objects.new('city_gs_%s_%d' % (t, k + 1), tmpl.data))
        ob.location = (x0, y0, 0)
# под городом — земля до горизонта
boxes_obj('city_far', [(-6.0, -6.0, -PH - 0.002, 12.0, 12.0, 0.001)], '#8e9296', bevel=0)

# разметка дорог
marks = []
for i in range(-5, 6):
    for j in range(-5, 6):
        if tile_type(i, j) != 'road' or (i == 0 and j == 0):
            continue
        x0, y0 = (i - 0.5) * TILE, (j - 0.5) * TILE
        horiz = tile_type(i - 1, j) == 'road' or tile_type(i + 1, j) == 'road'
        for k in range(3):
            if horiz:
                marks.append((x0 + 0.01 + k * 0.053, y0 + TILE / 2 - 0.0015, 0, 0.03, 0.003, 0.0004))
            else:
                marks.append((x0 + TILE / 2 - 0.0015, y0 + 0.01 + k * 0.053, 0, 0.003, 0.03, 0.0004))
if marks:
    boxes_obj('city_marks', marks, '#f2f2ee', bevel=0)

# ---------- дома ----------
glass, frames, doors, awn = [], [], [], {}


def building(x0, y0, w, d, floors, color, shop=False, face='s', barred=False):
    hh = floors * 3 * H
    body = [(x0, y0, 0, w * STUD, d * STUD, hh)]
    roof = [(x0 - 0.001, y0 - 0.001, hh, w * STUD + 0.002, d * STUD + 0.002, PH)]
    near = math.hypot(x0 + w * STUD / 2, y0 + d * STUD / 2) < 0.5
    boxes_obj('city_b%d' % len(doors), body, color, bevel=0.0006)
    boxes_obj('city_r%d' % len(doors), roof, '#6b6e73', bevel=0.0003)
    out = 0.0006
    for f in range(floors):
        z = f * 3 * H + 0.9 * H
        if f == 0 and shop:
            continue
        for side in ('s', 'n', 'e', 'w'):
            n = w if side in ('s', 'n') else d
            for k in range(1, n - 1, 3):
                if side == 's':
                    g = (x0 + k * STUD, y0 - out, z, 2 * STUD, out, 1.5 * H)
                elif side == 'n':
                    g = (x0 + k * STUD, y0 + d * STUD, z, 2 * STUD, out, 1.5 * H)
                elif side == 'w':
                    g = (x0 - out, y0 + k * STUD, z, out, 2 * STUD, 1.5 * H)
                else:
                    g = (x0 + w * STUD, y0 + k * STUD, z, out, 2 * STUD, 1.5 * H)
                glass.append(g)
                # подоконник
                sx, sy, sz = g[0] - (0.0006 if side in 's n' else 0), g[1] - (0.0006 if side in 'e w' else 0), z - 0.0012
                frames.append((sx, sy, sz, g[3] + (0.0012 if side in 's n' else out), g[4] + (0.0012 if side in 'e w' else out), 0.0012))
                if barred:
                    for b in range(3):
                        if side in ('s', 'n'):
                            frames.append((g[0] + (b + 0.5) * 2 * STUD / 3, g[1] - 0.0004, z, 0.0008, 0.0012, 1.5 * H))
    # дверь и витрина на стороне к площадке
    cx, cy = x0 + w * STUD / 2, y0 + d * STUD / 2
    if face == 's':
        dx, dy, sx_, sy_ = cx - STUD, y0 - out, 2 * STUD, out
    elif face == 'n':
        dx, dy, sx_, sy_ = cx - STUD, y0 + d * STUD, 2 * STUD, out
    elif face == 'w':
        dx, dy, sx_, sy_ = x0 - out, cy - STUD, out, 2 * STUD
    else:
        dx, dy, sx_, sy_ = x0 + w * STUD, cy - STUD, out, 2 * STUD
    doors.append((dx, dy, 0, sx_, sy_, 2.6 * H))
    if shop:
        col = crng.choice(['#c0392b', '#2e86c1', '#27ae60', '#f1c40f'])
        if face in ('s', 'n'):
            sgn = -1 if face == 's' else 1
            base_y = y0 if face == 's' else y0 + d * STUD
            glass.append((x0 + 2 * STUD, base_y + (sgn * out if sgn > 0 else -out), 0.5 * H,
                          (w - 4) * STUD, out, 1.8 * H))
            for k in range(w):
                awn.setdefault(col if k % 2 == 0 else '#f4f4f0', []).append(
                    (x0 + k * STUD, base_y + (0 if sgn > 0 else -0.009), 2.5 * H, STUD, 0.009, 0.0016))
        else:
            sgn = -1 if face == 'w' else 1
            base_x = x0 if face == 'w' else x0 + w * STUD
            glass.append((base_x + (out if sgn > 0 else -out), y0 + 2 * STUD, 0.5 * H, out, (d - 4) * STUD, 1.8 * H))
            for k in range(d):
                awn.setdefault(col if k % 2 == 0 else '#f4f4f0', []).append(
                    (base_x + (0 if sgn > 0 else -0.009), y0 + k * STUD, 2.5 * H, 0.009, STUD, 0.0016))


def face_to_center(i, j):
    if abs(j) >= abs(i):
        return 's' if j > 0 else 'n'
    return 'w' if i > 0 else 'e'


for i in range(-5, 6):
    for j in range(-5, 6):
        r = max(abs(i), abs(j))
        if tile_type(i, j) != 'walk' or r < RB or (j <= 0 and r < RF):
            continue
        if A.place == 'street' and abs(j) == 1:
            continue  # тротуар вдоль улицы
        x0, y0 = (i - 0.5) * TILE + 1.5 * STUD, (j - 0.5) * TILE + 1.5 * STUD
        if crng.random() < 0.5:
            fl = crng.randint(3, 6) + (r - 2)
            building(x0, y0, 17, 17, fl, crng.choice(PAL), shop=(r <= 3), face=face_to_center(i, j))
        else:
            fl1, fl2 = crng.randint(3, 7) + (r - 2), crng.randint(2, 6) + (r - 2)
            building(x0, y0, 8, 17, fl1, crng.choice(PAL), shop=(r <= 3), face=face_to_center(i, j))
            building(x0 + 9 * STUD, y0, 8, 17, fl2, crng.choice(PAL), shop=(r <= 3), face=face_to_center(i, j))

# ---------- место ----------
props = {}


def lamp_at(x, y):
    props.setdefault('#202022', []).extend([(x - 0.0015, y - 0.0015, 0, 0.003, 0.003, 7 * H),
                                            (x - STUD, y - 0.0015, 7 * H, 1.2 * STUD, 0.003, 0.002)])
    props.setdefault('lampglass', []).append((x - STUD - 0.002, y - 0.002, 7 * H - 0.003, 0.004, 0.004, 0.003))


def car_at(x, y, along_x, col):
    lx, ly = (4 * STUD, 2 * STUD) if along_x else (2 * STUD, 4 * STUD)
    x0, y0 = x - lx / 2, y - ly / 2
    props.setdefault(col, []).append((x0, y0, 0.006, lx, ly, H))
    if along_x:
        props.setdefault(col, []).append((x0 + 0.8 * STUD, y0, 0.006 + H, 2 * STUD, ly, H))
        props.setdefault('carglass', []).append((x0 + 2.8 * STUD, y0 + 0.0005, 0.006 + H, 0.0008, ly - 0.001, 0.8 * H))
        wheels = [(x0 + 0.8 * STUD, y0 - 0.0006), (x0 + 3.2 * STUD, y0 - 0.0006),
                  (x0 + 0.8 * STUD, y0 + ly - 0.0024), (x0 + 3.2 * STUD, y0 + ly - 0.0024)]
        for wx, wy in wheels:
            props.setdefault('#202022', []).append((wx - 0.005, wy, 0.0005, 0.01, 0.003, 0.01))
    else:
        props.setdefault(col, []).append((x0, y0 + 0.8 * STUD, 0.006 + H, lx, 2 * STUD, H))
        props.setdefault('carglass', []).append((x0 + 0.0005, y0 + 2.8 * STUD, 0.006 + H, lx - 0.001, 0.0008, 0.8 * H))
        wheels = [(x0 - 0.0006, y0 + 0.8 * STUD), (x0 - 0.0006, y0 + 3.2 * STUD),
                  (x0 + lx - 0.0024, y0 + 0.8 * STUD), (x0 + lx - 0.0024, y0 + 3.2 * STUD)]
        for wx, wy in wheels:
            props.setdefault('#202022', []).append((wx, wy - 0.005, 0.0005, 0.003, 0.01, 0.01))


def tree_at(x, y, k):
    props.setdefault('#6b3f22', []).append((x - 0.0035, y - 0.0035, 0, 0.007, 0.007, 5 * H))
    c = crng.choice(['#2f8a3c', '#3c9a46', '#27753a', '#4aa64e'])
    props.setdefault(c, []).extend([(x - 2 * STUD, y - 2 * STUD, 5 * H, 4 * STUD, 4 * STUD, H),
                                    (x - STUD, y - STUD, 6 * H, 2 * STUD, 2 * STUD, 2 * H)])


def crate_at(x, y, n=1):
    for z in range(n):
        props.setdefault('#8a5a2b', []).append((x - STUD, y - STUD, z * 2 * H, 2 * STUD, 2 * STUD, 2 * H - 0.0004))


def free_of_camera(x, y, rmin=0.2):
    """Не ставить высокие вещи в коридор общего плана (сторона -y) и вплотную к площадке."""
    r = math.hypot(x, y)
    ang = math.degrees(math.atan2(x, -y))  # 0 = прямо на -y
    return r > rmin and not (abs(ang) < 55 and r < 0.42)


if A.place == 'street':
    for x in (-0.72, -0.48, -0.24, 0.24, 0.72):
        for y in (0.125, -0.125):
            if free_of_camera(x, y, 0.15):
                lamp_at(x, y)
    for x, y, col in ((-0.3, 0.055, '#c0392b'), (-0.62, -0.055, '#2e86c1'), (0.62, 0.055, '#f1c40f'),
                      (0.85, -0.055, '#ecf0f1'), (-0.85, 0.055, '#27ae60')):
        car_at(x, y, True, col)
    for y in (-0.42, 0.42, 0.7):
        car_at(0.48 + (0.03 if y > 0 else -0.03), y, False, crng.choice(['#c0392b', '#2e86c1', '#ecf0f1', '#202022']))
    for k in range(6):  # зебра
        props.setdefault('#f2f2ee', []).append((0.42 + k * 0.022, 0.09, 0, 0.012, 0.05, 0.0005))
elif A.place == 'park':
    k = 0
    while k < 22:
        x, y = crng.uniform(-0.37, 0.37), crng.uniform(-0.37, 0.37)
        if free_of_camera(x, y, 0.15) and abs(y) > 0.06:
            tree_at(x, y, k)
            k += 1
    for x in (-0.4, -0.2, 0.2, 0.4):
        lamp_at(x, 0.075)
        props.setdefault('#7a4a26', []).append((x + 0.02, 0.1, 0.01, 0.04, 0.012, 0.004))  # скамейка
        props.setdefault('#202022', []).extend([(x + 0.022, 0.102, 0, 0.003, 0.008, 0.01), (x + 0.055, 0.102, 0, 0.003, 0.008, 0.01)])
    for k in range(-23, 24):  # низкая ограда парка
        for (x, y) in ((k * 0.0165, 0.39), (0.39, k * 0.0165), (-0.39, k * 0.0165)):
            props.setdefault('#eeeeea', []).append((x - 0.0015, y - 0.0015, 0, 0.003, 0.003, 1.5 * H))
elif A.place == 'market':
    k = 0
    for ang in range(0, 360, 30):
        x, y = 0.205 * math.sin(math.radians(ang)), 0.205 * math.cos(math.radians(ang))
        if not free_of_camera(x, y, 0.19):
            continue
        col = ['#c0392b', '#2e86c1', '#27ae60', '#f39c12'][k % 4]
        k += 1
        for px, py in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            props.setdefault('#6b3f22', []).append((x + px * 2 * STUD - 0.0012, y + py * 1.5 * STUD - 0.0012, 0, 0.0024, 0.0024, 4.5 * H))
        props.setdefault('#d6c08f', []).append((x - 2 * STUD, y - 1.5 * STUD, 0, 4 * STUD, 3 * STUD, 1.6 * H))
        for s_ in range(5):
            props.setdefault(col if s_ % 2 == 0 else '#f4f4f0', []).append(
                (x - 2.4 * STUD + s_ * 0.96 * STUD, y - 2 * STUD, 4.5 * H, 0.96 * STUD, 4 * STUD, 0.002))
        props.setdefault(crng.choice(['#e74c3c', '#f1c40f', '#27ae60', '#e67e22']), []).append(
            (x - 1.6 * STUD, y - STUD, 1.6 * H, 3.2 * STUD, 2 * STUD, 0.4 * H))  # товар на прилавке
    for k in range(14):
        x, y = crng.uniform(-0.23, 0.23), crng.uniform(-0.23, 0.23)
        if free_of_camera(x, y, 0.14) and max(abs(x), abs(y)) > 0.11:
            crate_at(x, y, crng.randint(1, 3))
    for x in (-0.36, 0.36):
        lamp_at(x, 0.15)
elif A.place == 'prison':
    WH = 12 * H
    walls = [(-0.34, 0.30, 0.68, STUD, WH), (-0.34, -0.42, 0.68, STUD, WH)]
    sides = [(-0.34, -0.42, STUD, 0.72 + STUD, WH), (0.34 - STUD, -0.42, STUD, 0.72 + STUD, WH)]
    props.setdefault('#9a9da2', []).extend([(x, y, 0, sx, sy, h) for x, y, sx, sy, h in walls + sides])
    props.setdefault('#7d8086', []).extend([(x - 0.001, y - 0.001, h, sx + 0.002, sy + 0.002, PH)
                                            for x, y, sx, sy, h in walls + sides])
    for cx, cy in ((-0.34, 0.30), (0.34, 0.30), (-0.34, -0.42), (0.34, -0.42)):
        props.setdefault('#7d8086', []).extend([(cx - 2 * STUD, cy - 2 * STUD, 0, 4 * STUD, 4 * STUD, 16 * H)])
        props.setdefault('#5a5d63', []).append((cx - 2.5 * STUD, cy - 2.5 * STUD, 16 * H, 5 * STUD, 5 * STUD, 3 * H))
        props.setdefault('carglass', []).append((cx - 2.6 * STUD, cy - 2.6 * STUD, 16.8 * H, 5.2 * STUD, 5.2 * STUD, 1.4 * H))
        props.setdefault('#202022', []).append((cx - 2.8 * STUD, cy - 2.8 * STUD, 19 * H, 5.6 * STUD, 5.6 * STUD, PH))
    building(-0.26, 0.34, 64, 14, 4, '#a4a7ab', face='s', barred=True)
    for x in (-0.25, 0.25):
        lamp_at(x, 0.24)

GLASS = '#36506e'
if glass:
    boxes_obj('city_glass', glass, GLASS, bevel=0)
if frames:
    boxes_obj('city_frames', frames, '#eeeeea' if A.place != 'prison' else '#202022', bevel=0)
if doors:
    boxes_obj('city_doors', doors, '#5b3a22', bevel=0.0003)
for c, bx in awn.items():
    boxes_obj('city_awn' + c, bx, c, bevel=0.0002)
for c, bx in props.items():
    if c == 'lampglass':
        boxes_obj('city_lampglass', bx, '#ffe9a8', bevel=0, emit=4.0)
    elif c == 'carglass':
        boxes_obj('city_carglass', bx, '#9fc6e0', bevel=0)
    else:
        boxes_obj('city_p' + c, bx, c, bevel=0.0003)

# небо и солнце
w_ = bpy.data.worlds.new('sky')
sc.world = w_
w_.use_nodes = True
w_.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.68, 0.86, 1)
w_.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.55
sun = bpy.data.lights.new('sun', 'SUN')
sun.energy = 2.2
sun.angle = math.radians(6)
sun.color = (1.0, 0.96, 0.9)
so = link(bpy.data.objects.new('sun', sun))
so.rotation_euler = (math.radians(50), 0, math.radians(-35))
