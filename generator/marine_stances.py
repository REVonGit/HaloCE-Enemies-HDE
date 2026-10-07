"""Halo 2's Marine launcher stance on both Marine bodies -> out/models/{Marine,MarineArmored}/<char>.iqm and .json

    python3 marine_stances.py

'h2missile' (h2_elite_anims.H2MISSILE: the rocket launcher on the shoulder, from 01b_spacestation.map), moved onto
the Halo CE Marine skeleton the way the other Halo 2 stances are; its melee and reload are Halo 2 replacement
animations, laid over the stance idle (reload_anims.h2_anims). The rocket launcher, Hydra and fuel rod Marines use
it. Run after extract_chars.py and the gore / blood / arsenal steps; re-running replaces only these animations.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2_elite_anims import stance_anims, MARINE, MAP01B, CACHE01B
from reload_anims import h2_anims, OUT

EXTRA = {'stand h2missile melee': ('combat:missile:melee', 'combat:missile:idle'),
         'stand h2missile reload-1': ('combat:missile:reload_1', 'combat:missile:idle')}


def main():
    for char in ('Marine', 'MarineArmored'):
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        joints, meshes, anims = read_iqm(pi)
        meta = json.load(open(pj))
        for k in [k for k in anims if ' h2missile ' in k]: anims.pop(k)
        for k in [k for k in meta['anims'] if ' h2missile ' in k]: meta['anims'].pop(k)
        new = {a.name: (a.frames, a.dx) for a in stance_anims(joints, 'h2missile')}
        for k, fr in h2_anims(MARINE, MAP01B, CACHE01B, EXTRA, joints).items(): new[k] = (fr, np.zeros((len(fr), 4)))
        jn = [j[0] for j in joints].index('bip01 ponytail1')
        for k, (fr, dx) in new.items():
            fr = [list(f) for f in fr]
            for f in fr: f[jn] = (tuple(joints[jn][2]), tuple(joints[jn][3]), tuple(joints[jn][4]))     # jaw shut
            anims[k] = fr
            dx = np.asarray(dx, float).reshape(-1, 4) if len(dx) else np.zeros((len(fr), 4))
            meta['anims'][k] = dict(frames=len(fr), speed=float(np.hypot(dx[:, 0], dx[:, 1]).sum() / max(1, len(fr))),
                                    yaw=float(dx[:, 3].sum()), loop=True, key=-1, next=-1, dx=[float(dx[:, 0].sum()), float(dx[:, 1].sum())])
        alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in f] for f in anims[n]])
                 for n in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
        json.dump(meta, open(pj, 'w'), indent=1)
        print(char, sorted(new))


if __name__ == '__main__':
    main()
