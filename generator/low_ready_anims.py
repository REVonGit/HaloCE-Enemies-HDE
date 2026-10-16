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
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import steps
import halomodel as hm
from h2_elite_anims import MAP08A, CACHE08A, MAP01B, CACHE01B, ELITE, MARINE
from reload_anims import GRUNT, JACKAL
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')

# the body's stance -> the Halo 2 weapon class whose patrol animations it takes
# To give a new stance a low-ready set, add it to its body's table with the Halo 2 class to borrow from.
MARINE_ST = {'rifle': 'rifle', 'h2rifle': 'rifle', 'h2br': 'rifle', 'h2smg': 'rifle', 'h2bulldog': 'rifle',
             'pistol': 'pistol', 'h2pistol': 'pistol', 'h2missile': 'missile', 'missle': 'missile'}
ELITE_ST = {'pistol': 'pistol', 'rifle': 'rifle', 'missle': 'missile', 'sword': 'sword'}
GRUNT_ST = {'pistol': 'pistol', 'missle': 'missile'}
JACKAL_ST = {'pistol': 'pistol', 'rifle': 'rifle'}
BRUTE_ST = {'rifle': 'any:any', 'support': 'any:any', 'melee': 'melee'}


def brute_src():
    """the Brute's own Halo 2 model and map (imported late: extract_h2_brute reads its env at import)"""
    from extract_h2_brute import MAP, CACHE, BRUTE
    return BRUTE, MAP, CACHE


# character -> (Halo 2 model, map, cache, stance table); the Brute's source comes from brute_src()
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
    """the stance names a body has (from its 'stand / alert <stance> idle / move-front' animations)"""
    out = set()
    for k in meta['anims']:
        p = k.split()
        if len(p) >= 3 and p[0] in ('stand', 'alert') and (p[2] == 'idle' or p[2].startswith('move-front')): out.add(p[1])
    return out


def h2_patrol(model, path, cache, plan, ce_joints):
    """{pack name: (frames on the body's joints, movement (F,4))} for the body's stances"""
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
        """Halo 2 frames -> frames on the body's joints: its offsets, Halo 2 rotations, the root's translation"""
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
        """the first base (type 0) animation among the names, or None"""
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


def regrip(char, joints, new):
    """the Marines' gun stances (marine_grip.GUNS: h2smg, h2br, h2bulldog, h2plasma) take Halo 2's rifle patrol set as
    it is, with the left hand where Halo 2's battle rifle put it: re-solved onto the gun the stance carries (its palm
    target, the Bulldog's butt in the shoulder), per frame, as marine_grip.derive does for the combat set. In place"""
    import marine_grip as mg
    from marine_arsenal import hand_frame
    R, t, _, _ = hand_frame(char)
    names = [j[0] for j in joints]; parents = [j[1] for j in joints]
    ix = {n: i for i, n in enumerate(names)}
    R_ids = (ix['bip01 r upperarm'], ix['bip01 r forearm'], ix['bip01 r hand'])
    L_ids = (ix['bip01 l upperarm'], ix['bip01 l forearm'], ix['bip01 l hand'])
    rh = R_ids[2]
    bt, bq = mg.world(parents, [(j[2], j[3]) for j in joints])[rh]
    def in_hand(p): return hm.qrot(hm.qconj(bq), R @ p + t - bt)      # weapon-space point -> right-hand space
    for k, (fr, mv, h2n) in new.items():
        st = k.split()[1]
        if st not in mg.GUNS: continue
        left, butt = mg.GUNS[st]
        lh_h = in_hand(left); butt_h = in_hand(butt) if butt is not None else None
        for f in fr:
            local = [(tuple(a), tuple(q)) for (a, q, s) in f]
            W = mg.world(parents, local); ht, hq = W[rh]
            if butt_h is not None:
                ua = W[R_ids[0]][0]; chest = W[ix['bip01 spine1']][0]
                pocket = ua + (chest - ua) * 0.25
                butt_w = ht + hm.qrot(hq, butt_h)
                fwd = hm.qrot(hq, in_hand(np.array([1.0, 0, 0])) - in_hand(np.zeros(3))); fwd /= np.linalg.norm(fwd)
                delta = pocket - butt_w
                delta = fwd * np.dot(delta, fwd) + (delta - fwd * np.dot(delta, fwd)) * 0.6
                mg.solve_arm(W, local, parents, R_ids, ht + delta, hq)
                W = mg.world(parents, local); ht, hq = W[rh]
            lq = W[L_ids[2]][1]
            mg.solve_arm(W, local, parents, L_ids, ht + hm.qrot(hq, lh_h) - hm.qrot(lq, mg.PALM), lq)
            for i, (a, q) in enumerate(local): f[i] = (a, q, f[i][2])


def add(char):
    """adds low-idle / low-move for every stance the body has in its table, replacing this script's earlier ones;
    low-move keeps its root speed for stride matching"""
    model, path, cache, plan = CHARS[char]
    if char == 'Brute': model, path, cache = brute_src()
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(path): print(char, 'skipped'); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    have = stances(meta)
    plan = {st: c for st, c in plan.items() if st in have}
    new = h2_patrol(model, path, cache, plan, joints)
    if char.startswith('Marine'): regrip(char, joints, new)
    for k in [k for k in anims if k.endswith(MARK)]: anims.pop(k)
    for k in [k for k in meta['anims'] if k.endswith(MARK)]: meta['anims'].pop(k)
    if 'h2br_lowered_names' in meta: meta['h2br_lowered_names'] = [n for n in meta['h2br_lowered_names'] if n in meta['anims']]   # remade ones: marine_h2_grips.py lowers them again
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
    steps.stamp(meta, 'low_ready_anims', new)      # build_pack.py checks these are still there
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, {k: (v[2], len(v[0]), round(meta['anims'][k]['speed'], 4)) for k, v in new.items()})


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
