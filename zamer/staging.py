"""Проверка расстановки: не только «всё нужное есть», но и «стоит так, как в описании».

Записано 15.11.2026 до первого прогона v3, применяется одинаково к v1, v2 и v3 (к скомпилированной сцене S).
Расстояние между клетками — по Чебышёву (соседние, в том числе по диагонали, = 1).
Позиции персонажа берутся по таймлайну: старт, все клетки путей, конец.

    from staging import staging_check  ->  список невыполненных проверок (пусто = расстановка верна)
"""


def dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def heroes_of(S, look):
    return [nm for nm, h in S['heroes'].items() if h['look'] == look]


def acts_of(S, nm, kinds=None):
    return [a for a in sorted(S['acts'], key=lambda a: a['t0'])
            if a['hero'] == nm and (kinds is None or a['act'] in kinds)]


def cells_of_kind(S, kind):
    return [tuple(c) for b in S['bricks'] if b['kind'] == kind for c in b['cells']]


def path_cells(a):
    p = a.get('path') or [a.get('from'), a.get('dest')]
    p = [tuple(c) for c in p if c is not None]
    out = []
    for i in range(len(p) - 1):
        for k in range(21):
            out.append((round(p[i][0] + (p[i + 1][0] - p[i][0]) * k / 20),
                        round(p[i][1] + (p[i + 1][1] - p[i][1]) * k / 20)))
    return out or p


def start(S, nm):
    return tuple(S['heroes'][nm]['cell'])


def end(S, nm):
    return tuple(S['heroes'][nm].get('end') or S['heroes'][nm]['cell'])


def near(c, cells, k):
    return any(dist(c, x) <= k for x in cells)


def pos_at(S, nm, t):
    p = start(S, nm)
    for a in acts_of(S, nm):
        if a['t0'] <= t and a.get('dest') is not None:
            p = tuple(a['dest'])
    return p


def any_ok(S, looks, fn):
    """Есть персонаж каждого вида из looks, для которого fn(*имена) истинно."""
    import itertools
    groups = [heroes_of(S, lk) for lk in looks]
    if not all(groups):
        return False
    return any(fn(*combo) for combo in itertools.product(*groups))


def crosses(a, cells):
    return any(c in cells for c in path_cells(a))


def chk1(S):
    bars, wall = cells_of_kind(S, 'bars'), cells_of_kind(S, 'wall')
    out = []
    if not any_ok(S, ['prisoner'], lambda p: near(start(S, p), bars, 1)):
        out.append('заключённый не у решётки')
    if not any_ok(S, ['prisoner'], lambda p: any(crosses(a, wall) for a in acts_of(S, p, ('climb', 'jump')))):
        out.append('заключённый не перелезает через стену')
    if not any_ok(S, ['guard'], lambda g: any(any(near(c, bars, 2) for c in path_cells(a))
                                             for a in acts_of(S, g, ('walk', 'run', 'sneak')))):
        out.append('охранник не проходит мимо решётки')
    return out


def chk2(S):
    car = cells_of_kind(S, 'car')
    out = []
    if not any_ok(S, ['thief'], lambda t: any(any(near(c, car, 2) for c in path_cells(a))
                                             for a in acts_of(S, t, ('run',)))):
        out.append('вор не пробегает мимо машины')
    if not any_ok(S, ['cop', 'thief'], lambda c, t: acts_of(S, c, ('run',)) and
                  dist(end(S, c), end(S, t)) < dist(start(S, c), end(S, t))):
        out.append('полицейский не бежит за вором')
    return out


def chk3(S):
    tw = cells_of_kind(S, 'tower')
    out = []
    if not any_ok(S, ['kid'], lambda k: start(S, k) in tw):
        out.append('ребёнок не на вышке')
    if not any_ok(S, ['cop'], lambda c: any(tuple(a['dest']) in tw or near(tuple(a['dest']), tw, 0)
                                           for a in acts_of(S, c, ('climb', 'jump')))):
        out.append('полицейский не забирается на вышку')
    return out


def chk4(S):
    door = cells_of_kind(S, 'door')
    out = []
    if not any_ok(S, ['guard'], lambda g: near(start(S, g), door, 1)):
        out.append('охранник не у двери')
    if not any_ok(S, ['prisoner', 'guard'], lambda p, g: any(
            min(dist(c, start(S, g)) for c in path_cells(a)) <= 1 and dist(tuple(a['dest']), start(S, g)) >= 1
            and dist(tuple(a['from']), tuple(a['dest'])) >= 2 for a in acts_of(S, p, ('sneak',)))):
        out.append('заключённый не крадётся мимо охранника')
    return out


def chk5(S):
    cr = cells_of_kind(S, 'crate')
    out = []
    if not any_ok(S, ['thief'], lambda t: any(near(pos_at(S, t, a['t0']), cr, 1) for a in acts_of(S, t, ('fall',)))):
        out.append('вор падает не у ящика')
    if not any_ok(S, ['cop', 'thief'], lambda c, t: dist(end(S, c), end(S, t)) <= 2):
        out.append('полицейский не подбегает к вору')
    return out


def chk6(S):
    door = cells_of_kind(S, 'door')
    out = []
    if not any_ok(S, ['prisoner'], lambda p: near(start(S, p), door, 1) and acts_of(S, p, ('run',))
                  and not near(end(S, p), door, 2)):
        out.append('заключённый не выбегает из двери')
    return out


def chk7(S):
    tr = cells_of_kind(S, 'tree')
    out = []
    if not any_ok(S, ['thief'], lambda t: any(near(pos_at(S, t, a['t0']), tr, 1) for a in acts_of(S, t, ('hide',)))):
        out.append('вор прячется не у дерева')
    if not any_ok(S, ['cop', 'thief'], lambda c, t: any(
            min(dist(x, end(S, t)) for x in path_cells(a)) <= 2 for a in acts_of(S, c, ('walk',)))):
        out.append('полицейский не проходит мимо вора')
    return out


def chk8(S):
    wall = cells_of_kind(S, 'wall')
    out = []
    if not any_ok(S, ['cop'], lambda c: any(crosses(a, wall) for a in acts_of(S, c, ('climb', 'jump')))):
        out.append('полицейский не перепрыгивает стену')
    if not any_ok(S, ['cop', 'kid'], lambda c, k: dist(end(S, c), end(S, k)) <= 1):
        out.append('полицейский не оказывается рядом с ребёнком')
    return out


def chk9(S):
    lamp = cells_of_kind(S, 'lamp')
    out = []
    if not any_ok(S, ['prisoner'], lambda p: near(start(S, p), lamp, 1)):
        out.append('заключённый не у фонаря')
    gs = [g for g in heroes_of(S, 'guard') if acts_of(S, g, ('run',))]
    pr = heroes_of(S, 'prisoner')
    good = [g for g in gs if pr and any(dist(end(S, g), end(S, p)) <= 2 for p in pr)]
    if len(good) < 2:
        out.append('два охранника не прибегают к заключённому')
    elif not any(dist(start(S, a), start(S, b)) >= 3 for a in good for b in good if a != b):
        out.append('охранники бегут не с разных сторон')
    return out


def chk10(S):
    car = cells_of_kind(S, 'car')
    out = []
    if not any_ok(S, ['cop', 'thief'], lambda c, t: acts_of(S, c, ('run',)) and dist(end(S, c), end(S, t)) <= 1
                  and near(end(S, t), car, 2)):
        out.append('полицейский не догоняет вора у машины')
    if not any_ok(S, ['citizen', 'thief'], lambda z, t: dist(end(S, z), end(S, t)) <= 4):
        out.append('прохожие не рядом')
    return out


CHECKS = {1: chk1, 2: chk2, 3: chk3, 4: chk4, 5: chk5, 6: chk6, 7: chk7, 8: chk8, 9: chk9, 10: chk10}


def staging_check(S, scene_id):
    try:
        return CHECKS[scene_id](S)
    except Exception as e:  # сломанная сцена не проходит
        return ['проверка упала: %r' % e]
