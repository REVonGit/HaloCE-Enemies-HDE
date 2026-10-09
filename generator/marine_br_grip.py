"""The battle-rifle stance ('h2br') held lower: the gun at the cheek, not level with the top of the helmet ->
out/models/{Marine,MarineArmored,MarineODST}/<char>.iqm and .json

    python3 marine_br_grip.py

Halo 2's rifle set on the CE skeleton raises the right hand to about head height, and the battle rifle rides on that
hand, so it sat level with the top of the helmet. In every 'h2br' animation the right wrist goes down by LOWER world
units (two-bone IK, the hand keeping its rotation), so the gun drops with it, and the left hand follows it back onto
the battle rifle's fore-end (marine_grip.GUNS['h2br']) unless that animation lets go of the gun. The amount already
applied is kept in the json ('h2br_lowered'), so re-running only makes up the difference. Run after the Marine steps
(extract_chars.py ... cover_anims.py) and extract_odst.py; a re-extraction starts again from Halo 2's height."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import halomodel as hm
import marine_grip as mg
from marine_arsenal import hand_frame
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
STANCE = 'h2br'
LOWER = 0.04                     # world units (a Marine stands about 0.7)
CHARS = ('Marine', 'MarineArmored', 'MarineODST')


def main():
    left = mg.GUNS[STANCE][0]
    for char in CHARS:
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        if not os.path.exists(pi): continue
        meta = json.load(open(pj))
        dz = LOWER - meta.get('h2br_lowered', 0.0)
        if abs(dz) < 1e-6: print(char, 'already at', LOWER); continue
        joints, meshes, anims = read_iqm(pi)
        R, t, _, _ = hand_frame(char)
        names = [j[0] for j in joints]; parents = [j[1] for j in joints]
        ix = {n: i for i, n in enumerate(names)}
        R_ids = (ix['bip01 r upperarm'], ix['bip01 r forearm'], ix['bip01 r hand'])
        L_ids = (ix['bip01 l upperarm'], ix['bip01 l forearm'], ix['bip01 l hand'])
        rh = R_ids[2]
        bt, bq = mg.world(parents, [(j[2], j[3]) for j in joints])[rh]
        lh_h = hm.qrot(hm.qconj(bq), R @ left + t - bt)           # the left palm's target, in right-hand space
        down = np.array([0.0, 0.0, -dz])
        made = 0
        for n in sorted(k for k in anims if f' {STANCE} ' in f' {k} '):
            free = any(k in n for k in mg.FREE_LEFT)
            frames = []
            for fr in anims[n]:
                local = [(tuple(a), tuple(q)) for (a, q, s) in fr]
                W = mg.world(parents, local)
                ht, hq = W[rh]
                mg.solve_arm(W, local, parents, R_ids, ht + down, hq)
                if not free:
                    W = mg.world(parents, local)
                    ht, hq = W[rh]
                    lq = W[L_ids[2]][1]
                    mg.solve_arm(W, local, parents, L_ids, ht + hm.qrot(hq, lh_h) - hm.qrot(lq, mg.PALM), lq)
                frames.append([(tuple(a), tuple(q), tuple(fr[i][2])) for i, (a, q) in enumerate(local)])
            anims[n] = frames
            made += 1
        alist = [dict(name=k, fps=30.0, loop=True, frames=[[(tuple(a), tuple(q), tuple(s)) for a, q, s in f] for f in anims[k]])
                 for k in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(a), tuple(q), tuple(s)) for n, p, a, q, s in joints], meshes, alist)
        meta['h2br_lowered'] = LOWER
        json.dump(meta, open(pj, 'w'), indent=1)
        print(char, made, STANCE, 'animations lowered by', round(dz, 4))


if __name__ == '__main__':
    main()
