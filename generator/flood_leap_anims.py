"""Halo 2's Flood leap onto a ledge ('leap_pit') as the Flood combat forms' hoist -> out/models/<char>/<char>.iqm, .json

    HCE_H2_MAP06B=/path/to/06b_floodzone.map python3 flood_leap_anims.py [char ...]

Halo 2's Flood have no hoist or vault: they leap. Its combat forms' 'leap_pit' (06b_floodzone.map) springs up out of
a pit onto the ledge above, 1.6 world units. The climb is in the clip's root movement, not its bones, so it is baked
into the root bone here (the body visibly rises; only the rise: the leap is straight up, Halo 2 moved the unit
onto the ledge itself, and HCE_ClimbTick carries the body forward instead) and its total written as the
animation's 'move', which HaloDoom_EnemyBase.HCE_TryClimb reads like a Halo 2 hoist's. The human combat forms take the human form's clip, the
Elite forms the Elite form's (the same 3ds Max bipeds, bone for bone; CE's antenna and spike frames hold their rest
pose), under both of the Flood's stances: 'stand pistol hoist' (armed) and 'stand unarmed hoist'. Replaces this
script's animations on each run and stamps them (lib/steps.py)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import steps
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
MAP06B = os.environ.get('HCE_H2_MAP06B', '06b_floodzone.map')
CACHE06B = os.environ.get('HCE_H2_CACHE06B') or None
HUMAN = r'objects\characters\floodcombat_human\floodcombat_human'
ELITE = r'objects\characters\floodcombat_elite\floodcombat_elite'
# body -> the Halo 2 Flood whose leap it takes. To give another Flood body the leap, add it here
CHARS = {'FloodHuman': HUMAN, 'FloodArmored': HUMAN, 'FloodMarine': HUMAN, 'FloodODST': HUMAN,
         'FloodElite': ELITE}
CLIP = 'leap_pit'
NAMES = ('stand pistol hoist', 'stand unarmed hoist')     # the Flood's stances (build_pack: pistol armed, else unarmed)
_cache = {}


def leap(model, ce_joints):
    """frames of model's CLIP on ce_joints (Halo 2 rotations, CE bone offsets, the root's translation plus the clip's
    accumulated root movement) and the total movement (x forward, y left, z up, world units)"""
    from h2map import H2Map, render_model
    import h2anim
    if model not in _cache:
        m = H2Map(MAP06B, CACHE06B)
        nodes = render_model(m, model)['nodes']
        _, an = h2anim.graph(m, model)
        x = next(a for a in an if a['name'] == CLIP)
        defaults = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
        fr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], defaults)
        mv = np.asarray(mv, float).reshape(-1, 4) if len(mv) else np.zeros((len(fr), 4))
        _cache[model] = (nodes, fr, mv)
    nodes, fr, mv = _cache[model]
    h2i = {n['name']: i for i, n in enumerate(nodes)}
    src = [h2i.get(j[0].replace('bip01 ', '').replace(' ', '_')) for j in ce_joints]
    root = next(i for i, j in enumerate(ce_joints) if j[1] < 0)
    # the rise only: it is a leap straight up out of a pit (Halo 2 moved the unit onto the ledge itself), its
    # sideways drift a wobble; the AI carries the body forward onto the ledge as it climbs (HCE_ClimbTick)
    acc = np.vstack([np.zeros(3), np.cumsum(mv[:, :3], axis=0)])[:len(fr)]     # movement before each frame
    acc[:, :2] = 0
    out = []
    for f, row in enumerate(fr):
        r = []
        for j, k in enumerate(src):
            t, q = tuple(ce_joints[j][2]), tuple(ce_joints[j][3])
            if k is not None:
                q = tuple(row[k][1])
                if j == root: t = tuple(np.array(row[k][0]) + acc[f])
            r.append((t, q, (1.0, 1.0, 1.0)))
        out.append(r)
    return out, np.array([0.0, 0.0, mv[:, 2].sum()])


def add(char):
    """adds the leap under NAMES to char's IQM and json (replacing this script's earlier ones) and stamps them"""
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(MAP06B): print(char, 'skipped'); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    for k in (meta.get('steps') or {}).get('flood_leap_anims', []): anims.pop(k, None); meta['anims'].pop(k, None)
    frames, move = leap(CHARS[char], joints)
    for n in NAMES:
        anims[n] = frames
        meta['anims'][n] = dict(frames=len(frames), speed=0.0, yaw=0.0, loop=False, key=-1, next=-1, dx=[0.0, 0.0],
                                move=[round(float(v), 4) for v in move])
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    steps.stamp(meta, 'flood_leap_anims', NAMES)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, len(frames), 'frames, move', [round(float(v), 3) for v in move])


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
