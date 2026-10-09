"""Halo 2's rifle set held at the cheek, and the Halo 2 ODSTs' own stances ->
out/models/{Marine,MarineArmored,MarineODST}/<char>.iqm and .json

    python3 marine_h2_grips.py

* 'h2br', the battle rifle (Marine, Armored Marine, ODST): lowered in place, see below.
* 'h2ar' and 'h2shotgun' (the ODST body only, for the Halo 2 ODSTs: build_pack.ODST): Halo 2's rifle set ('h2rifle')
  re-posed for Halo CE's assault rifle and shotgun, so the Halo 2 ODSTs move, idle and fight like Halo 2's Marines
  rather than in Halo CE's rifle stance: lowered the same way, and the left hand on the rifle's handguard / the
  shotgun's pump (H2_GUNS, in Halo weapon space). Made fresh from 'h2rifle' on every run.

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
# new stance -> (left palm target in Halo weapon space, bodies): from 'h2rifle', lowered by LOWER
H2_GUNS = {'h2ar':      (np.array([0.112, 0.000, 0.010]), ('MarineODST',)),     # the assault rifle's handguard
           'h2shotgun': (np.array([0.130, 0.000, 0.012]), ('MarineODST',))}     # the shotgun's pump


def repose(anims, n, parents, R_ids, L_ids, lh_h, dz):
    """one animation's frames with the right wrist dz lower (the gun with it) and the left palm back on lh_h"""
    free = any(k in n for k in mg.FREE_LEFT)
    rh = R_ids[2]; down = np.array([0.0, 0.0, -dz]); frames = []
    for fr in anims[n]:
        local = [(tuple(a), tuple(q)) for (a, q, s) in fr]
        if dz:
            W = mg.world(parents, local)
            ht, hq = W[rh]
            mg.solve_arm(W, local, parents, R_ids, ht + down, hq)
        if not free:
            W = mg.world(parents, local)
            ht, hq = W[rh]
            lq = W[L_ids[2]][1]
            mg.solve_arm(W, local, parents, L_ids, ht + hm.qrot(hq, lh_h) - hm.qrot(lq, mg.PALM), lq)
        frames.append([(tuple(a), tuple(q), tuple(fr[i][2])) for i, (a, q) in enumerate(local)])
    return frames


def main():
    left = mg.GUNS[STANCE][0]
    for char in CHARS:
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        if not os.path.exists(pi): continue
        meta = json.load(open(pj))
        joints, meshes, anims = read_iqm(pi)
        R, t, _, _ = hand_frame(char)
        names = [j[0] for j in joints]; parents = [j[1] for j in joints]
        ix = {n: i for i, n in enumerate(names)}
        R_ids = (ix['bip01 r upperarm'], ix['bip01 r forearm'], ix['bip01 r hand'])
        L_ids = (ix['bip01 l upperarm'], ix['bip01 l forearm'], ix['bip01 l hand'])
        bt, bq = mg.world(parents, [(j[2], j[3]) for j in joints])[R_ids[2]]
        in_hand = lambda p: hm.qrot(hm.qconj(bq), R @ p + t - bt)      # weapon-space point -> right-hand space
        # the battle rifle: lowered in place, by what is still to go
        dz = LOWER - meta.get('h2br_lowered', 0.0)
        made = 0
        if abs(dz) > 1e-6:
            for n in sorted(k for k in anims if f' {STANCE} ' in f' {k} '):
                anims[n] = repose(anims, n, parents, R_ids, L_ids, in_hand(left), dz); made += 1
            meta['h2br_lowered'] = LOWER
        print(char, made, STANCE, 'animations lowered by', round(dz, 4))
        # the Halo 2 ODSTs' stances: fresh from 'h2rifle'
        for st, (palm, bodies) in H2_GUNS.items():
            for k in [k for k in anims if f' {st} ' in f' {k} ']: anims.pop(k)
            for k in [k for k in meta['anims'] if f' {st} ' in f' {k} ']: meta['anims'].pop(k)
            if char not in bodies: continue
            src = sorted(k for k in anims if ' h2rifle ' in f' {k} ')
            for n in src:
                nn = n.replace('h2rifle', st)
                anims[nn] = repose(anims, n, parents, R_ids, L_ids, in_hand(palm), LOWER)
                if n in meta['anims']: meta['anims'][nn] = dict(meta['anims'][n])
            print(char, len(src), st, 'animations')
        alist = [dict(name=k, fps=30.0, loop=True, frames=[[(tuple(a), tuple(q), tuple(s)) for a, q, s in f] for f in anims[k]])
                 for k in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(a), tuple(q), tuple(s)) for n, p, a, q, s in joints], meshes, alist)
        json.dump(meta, open(pj, 'w'), indent=1)


if __name__ == '__main__':
    main()
