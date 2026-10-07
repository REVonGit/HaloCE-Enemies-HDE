"""Halo 2's low-ready stances and walks on the bodies -> out/models/<char>/<char>.iqm and .json

    python3 low_ready_anims.py [char ...]

Halo 2's AI has a 'patrol' mode for when it isn't fighting: the weapon held low, a relaxed idle and an unhurried walk
(patrol:<weapon class>:idle and :walk_front / :move_front). Halo CE has none, so its bodies stood and moved at combat
ready all the time. These are added to each body in a stance it has, under the generator's names

    stand <stance> low-idle    the low-ready idle
    stand <stance> low-move    the walk, with its root motion (speed) for stride matching

and the pack plays them out of combat (HaloDoom_EnemyBase.HCE_Play: idle and walking, no target, 10 s after the last
fight). Halo CE bodies take Halo 2's Marine (01b_spacestation.map) or Elite / Grunt / Jackal (08a_deltacliffs.map)
animations bone for bone, as reload_anims.py does; the Brute takes its own (08b_deltacontrol.map). Run after
reload_anims.py (and brute_stance.py); re-running replaces only these.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2_elite_anims import MAP08A, CACHE08A, MAP01B, CACHE01B, ELITE, MARINE
from reload_anims import GRUNT, JACKAL
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')

# the body's stance -> the Halo 2 weapon class whose patrol animations it takes
MARINE_ST = {'rifle': 'rifle', 'h2rifle': 'rifle', 'h2br': 'rifle', 'h2smg': 'rifle', 'h2bulldog': 'rifle',
             'pistol': 'pistol', 'h2pistol': 'pistol', 'h2missile': 'missile', 'missle': 'missile'}
ELITE_ST = {'pistol': 'pistol', 'rifle': 'rifle', 'missle': 'missile', 'sword': 'sword'}
GRUNT_ST = {'pistol': 'pistol', 'missle': 'missile'}
JACKAL_ST = {'pistol': 'pistol', 'rifle': 'rifle'}
BRUTE_ST = {'rifle': 'any:any', 'support': 'any:any', 'melee': 'melee'}


def brute_src():
    from extract_h2_brute import MAP, CACHE, BRUTE
    return BRUTE, MAP, CACHE


CHARS = {
    'Marine': (MARINE, MAP01B, CACHE01B, MARINE_ST), 'MarineArmored': (MARINE, MAP01B, CACHE01B, MARINE_ST),
    'Elite': (ELITE, MAP08A, CACHE08A, ELITE_ST), 'EliteSpecial': (ELITE, MAP08A, CACHE08A, ELITE_ST),
    'EliteRifle': (ELITE, MAP08A, CACHE08A, ELITE_ST),
    'Grunt': (GRUNT, MAP08A, CACHE08A, GRUNT_ST), 'GruntSpecOps': (GRUNT, MAP08A, CACHE08A, GRUNT_ST),
    'Jackal': (JACKAL, MAP08A, CACHE08A, JACKAL_ST), 'JackalMajor': (JACKAL, MAP08A, CACHE08A, JACKAL_ST),
    'H2Jackal': (JACKAL, MAP08A, CACHE08A, JACKAL_ST),
    'Brute': (None, None, None, BRUTE_ST),
}
MARK = (' low-idle', ' low-move')


def stances(meta):
    out = set()
    for k in meta['anims']:
        p = k.split()
        if len(p) >= 3 and p[0] in ('stand', 'alert') and (p[2] == 'idle' or p[2].startswith('move-front')): out.add(p[1])
    return out


def h2_patrol(model, path, cache, plan, ce_joints):
    """{pack name: (frames on the body's joints, movement (F,4))} for the body's stances"""
    sys.path.insert(0, '/home/claude/spv3')
    from h2map import H2Map, render_model
    import h2anim
    m = H2Map(path, cache)
    nodes = render_model(m, model)['nodes']
    h2i = {n['name']: i for i, n in enumerate(nodes)}
    _, an = h2anim.graph(m, model)
    byname = {x['name']: x for x in an}
    bind = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
    src = [h2i.get(j[0].replace('bip01 ', '').replace(' ', '_')) for j in ce_joints]

    def to_body(fr):
        out = []
        for row in fr:
            r = []
            for j, k in enumerate(src):
                t, q = tuple(ce_joints[j][2]), tuple(ce_joints[j][3])
                if k is not None:
                    q = tuple(row[k][1])
                    if ce_joints[j][1] < 0: t = tuple(row[k][0])          # the root moves as Halo 2 moves it
                r.append((t, q, (1.0, 1.0, 1.0)))
            out.append(r)
        return out

    def first(names):
        return next((byname[n] for n in names if n in byname and byname[n]['type'] == 0), None)

    res = {}
    for st, cls in plan.items():
        for kind, names in (('low-idle', [f'patrol:{cls}:idle', f'patrol:{cls}:idle:var0', f'patrol:{cls}:idle:var1']),
                            ('low-move', [f'patrol:{cls}:walk_front', f'patrol:{cls}:move_front', f'patrol:{cls}:move_front:var0'])):
            x = first(names)
            if not x: continue
            fr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], bind)
            res[f'stand {st} {kind}'] = (to_body(fr), np.asarray(mv, float).reshape(-1, 4), x['name'])
    return res


def add(char):
    model, path, cache, plan = CHARS[char]
    if char == 'Brute': model, path, cache = brute_src()
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(path): print(char, 'skipped'); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    have = stances(meta)
    plan = {st: c for st, c in plan.items() if st in have}
    new = h2_patrol(model, path, cache, plan, joints)
    for k in [k for k in anims if k.endswith(MARK)]: anims.pop(k)
    for k in [k for k in meta['anims'] if k.endswith(MARK)]: meta['anims'].pop(k)
    jn = [j[0] for j in joints].index('bip01 ponytail1') if char.startswith('Marine') else -1
    for k, (fr, mv, h2n) in new.items():
        if jn >= 0:                              # the Marine's jaw stays shut (extract_chars.py)
            for f in fr: f[jn] = (tuple(joints[jn][2]), tuple(joints[jn][3]), tuple(joints[jn][4]))
        anims[k] = fr
        speed = float(np.hypot(mv[:, 0], mv[:, 1]).sum() / max(1, len(fr)))
        meta['anims'][k] = dict(frames=len(fr), speed=speed if k.endswith('low-move') else 0.0, yaw=0.0, loop=True,
                                key=-1, next=-1, dx=[float(mv[:, 0].sum()), float(mv[:, 1].sum())])
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, {k: (v[2], len(v[0]), round(meta['anims'][k]['speed'], 4)) for k, v in new.items()})


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
