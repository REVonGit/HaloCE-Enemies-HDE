"""The Marines' plasma-rifle stance ('h2plasma', marine_grip.GUNS) added to Marines already extracted ->
out/models/{Marine,MarineArmored}/<char>.iqm and .json

    python3 marine_plasma_grip.py

Halo 2's Marine rifle set ('h2rifle'), the plasma rifle in the right hand where the pack attaches it, and the left hand
moved by two-bone IK to the bottom of the gun, under its lower prong (marine_grip.py does the same for the SMG, battle
rifle and Bulldog at extraction; extract_chars.py makes this stance too on a full re-extraction). Re-running replaces
only these."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
import halomodel as hm
import marine_grip as mg
from marine_arsenal import hand_frame
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
STANCE = 'h2plasma'


def main():
    left = mg.GUNS[STANCE][0]
    for char in ('Marine', 'MarineArmored'):
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        if not os.path.exists(pi): continue
        joints, meshes, anims = read_iqm(pi)
        meta = json.load(open(pj))
        for k in [k for k in anims if f' {STANCE} ' in f' {k} ']: anims.pop(k)
        for k in [k for k in meta['anims'] if f' {STANCE} ' in f' {k} ']: meta['anims'].pop(k)
        R, t, _, _ = hand_frame(char)
        names = [j[0] for j in joints]; parents = [j[1] for j in joints]
        ix = {n: i for i, n in enumerate(names)}
        L_ids = (ix['bip01 l upperarm'], ix['bip01 l forearm'], ix['bip01 l hand'])
        rh = ix['bip01 r hand']
        bt, bq = mg.world(parents, [(j[2], j[3]) for j in joints])[rh]
        lh_h = hm.qrot(hm.qconj(bq), R @ left + t - bt)           # the palm target, in right-hand space
        made = 0
        for n in sorted(k for k in anims if ' h2rifle ' in f' {k} '):
            free = any(k in n for k in mg.FREE_LEFT)
            frames = []
            for fr in anims[n]:
                local = [(tuple(a), tuple(q)) for (a, q, s) in fr]
                if not free:
                    W = mg.world(parents, local)
                    ht, hq = W[rh]
                    lq = W[L_ids[2]][1]
                    mg.solve_arm(W, local, parents, L_ids, ht + hm.qrot(hq, lh_h) - hm.qrot(lq, mg.PALM), lq)
                frames.append([(tuple(a), tuple(q), tuple(fr[i][2])) for i, (a, q) in enumerate(local)])
            nn = n.replace('h2rifle', STANCE)
            anims[nn] = frames
            if n in meta['anims']: meta['anims'][nn] = dict(meta['anims'][n])
            made += 1
        alist = [dict(name=k, fps=30.0, loop=True, frames=[[(tuple(a), tuple(q), tuple(s)) for a, q, s in f] for f in anims[k]])
                 for k in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(a), tuple(q), tuple(s)) for n, p, a, q, s in joints], meshes, alist)
        json.dump(meta, open(pj, 'w'), indent=1)
        print(char, made, STANCE, 'animations')


if __name__ == '__main__':
    main()
