"""Halo 2's Brute Shot stance on the Brute -> out/models/Brute/Brute.iqm and .json

    python3 brute_stance.py

Halo 2's Brutes carry the Brute Shot in their 'support' stance (08b_deltacontrol.map, combat:support:*): the heavy
launcher held low across the body in both hands, the left on its grip (combat:support:bs:grip, laid over every
frame as extract_h2_brute.py lays the hammer grip). The pack's Brutes use it for the human guns they pick up --
the heavy ones, held the way a Brute holds its own launcher. The Brute's skeleton is Halo 2's own, so the animations
go on as they are. Names follow the generator ('stand support idle', 'stand support melee', ...); the firing overlay
(combat:support:bs:fire_1) is baked onto the idle. Run after extract_h2_brute.py and the gore / blood / overlay steps.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from extract_h2_brute import MAP, CACHE, BRUTE, OUT
from h2_elite_anims import _qmul

PLAN = {'idle': 'idle', 'move_front': 'move-front', 'move_back': 'move-back', 'move_left': 'move-left', 'move_right': 'move-right',
        'turn_left': 'turn-left', 'turn_right': 'turn-right', 'dive_front': 'dive-front', 'dive_left': 'dive-left',
        'dive_right': 'dive-right', 'evade_left': 'evade-left', 'evade_right': 'evade-right',
        'throw_grenade:var1': 'throw-grenade', 'cheer': 'celebrate', 'taunt': 'warn', 'airborne': 'airborne',
        'land_soft': 'land-soft', 'land_hard': 'land-hard', 'bs:melee:var1': 'melee'}


def main():
    sys.path.insert(0, '/home/claude/spv3')
    from h2map import H2Map
    import h2anim
    pi, pj = f'{OUT}/models/Brute/Brute.iqm', f'{OUT}/models/Brute/Brute.json'
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    m = H2Map(MAP, CACHE)
    _, an = h2anim.graph(m, BRUTE)
    byname = {x['name']: x for x in an}
    NJ = len(joints)
    defaults = [(np.array(j[2]), np.array(j[3])) for j in joints]
    nanq = [(np.full(3, np.nan), np.full(4, np.nan))] * NJ
    g = byname['combat:support:bs:grip']
    gfr, _ = h2anim.decode(g['data'], g['sizes'], g['frames'], g['nodes'], nanq)
    grip = {j: gfr[0][j] for j in range(NJ) if not np.isnan(np.array(gfr[0][j][1], float)).any()}
    def gripped(fr):
        return [[(row[j][0], tuple(grip[j][1]), row[j][2]) if j in grip else row[j] for j in range(NJ)] for row in fr]
    for k in [k for k in anims if k.startswith('stand support ')]: anims.pop(k)
    for k in [k for k in meta['anims'] if k.startswith('stand support ')]: meta['anims'].pop(k)
    new = {}
    for src, dst in PLAN.items():
        x = byname.get('combat:support:' + src)
        if not x: print('  no', src); continue
        fr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], defaults)
        new[f'stand support {dst}'] = (gripped(fr), np.asarray(mv, float).reshape(-1, 4))
    # the firing overlay on the idle
    o = byname['combat:support:bs:fire_1']
    ofr, _ = h2anim.decode(o['data'], o['sizes'], o['frames'], o['nodes'], [(np.zeros(3), np.array([0, 0, 0, 1.0]))] * NJ)
    b0 = new['stand support idle'][0][0]
    fire = []
    for f in ofr:
        row = []
        for k in range(NJ):
            bt, bq, bs = b0[k]; ot, oq, _ = f[k]
            q = _qmul(np.array(bq), np.array(oq)); q /= np.linalg.norm(q)
            row.append((tuple(np.array(bt) + np.array(ot)), tuple(q), bs))
        fire.append(row)
    new['stand support fire-1 baked'] = (fire, np.zeros((len(fire), 4)))
    for k, (fr, mv) in new.items():
        anims[k] = fr
        meta['anims'][k] = dict(frames=len(fr), speed=float(np.hypot(mv[:, 0], mv[:, 1]).sum() / max(1, len(fr))),
                                yaw=float(np.degrees(mv[:, 3].sum())), loop=True, key=-1, next=-1, dx=[float(mv[:, 0].sum()), float(mv[:, 1].sum())])
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), (s if isinstance(s, tuple) else (s, s, s)) if not hasattr(s, '__len__') or len(s) != 3 else tuple(s)) for t, q, s in f] for f in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    json.dump(meta, open(pj, 'w'), indent=1)
    print('Brute', sorted(new))


if __name__ == '__main__':
    main()
