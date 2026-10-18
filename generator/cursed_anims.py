"""Cursed Halo's leaping spin attack on the Hunter -> out/models/Hunter/Hunter.iqm, .json

    HCE_CURSED_A50=/path/to/cursed_halo/maps/a50.map python3 cursed_anims.py

Cursed Halo Again (MCC Steam Workshop 2962107814) gives the Hunter, on Halo CE's own Hunter graph and biped, two
animations Halo CE's lacks: 'stand unarmed leap-start' (a crouch and spring, 9 frames) and 'stand unarmed
melee-airborne' (a full-body spin through the air into its target, 47 frames). This takes those two (ANIMS) from the
mod's a50 into the Hunter's IQM and json; build_pack.py gives a Hunter whose body has them a leap (HCE_Leaps: the
spring, then the spin, hitting what it lands on). Bones by name. Run after be_anims.py (Hunter); replaces this
script's animations on each run and stamps them (lib/steps.py)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import steps
from be_anims import graph
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
CURSED_A50 = os.environ.get('HCE_CURSED_A50', 'a50.map')
GRAPH = r'characters\hunter\hunter'
CHARS = ('Hunter',)
ANIMS = ('stand unarmed leap-start', 'stand unarmed melee-airborne')
STEP = 'cursed_anims'


def add(char):
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(CURSED_A50): print(char, 'skipped'); return
    from pcmap import PCMap
    B, nodes = graph(PCMap(CURSED_A50), GRAPH)
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    for k in (meta.get('steps') or {}).get(STEP, []): anims.pop(k, None); meta['anims'].pop(k, None)
    jn = [j[0] for j in joints]
    src = [nodes.index(n) if n in nodes else None for n in jn]
    new = []
    for n in ANIMS:
        a = B.get(n)
        if a is None: print(char, 'no', n, 'in', GRAPH); continue
        frames = []
        for fr in a.frames:
            r = []
            for j, k in enumerate(src):
                t, q, s = fr[k] if k is not None else (None, None, None)
                r.append((tuple(joints[j][2]) if t is None else tuple(t), tuple(joints[j][3]) if q is None else tuple(q),
                          (1.0, 1.0, 1.0) if s is None else ((s, s, s) if np.isscalar(s) else tuple(s))))
            frames.append(r)
        anims[n] = frames
        meta['anims'][n] = dict(frames=a.nframes, speed=float(np.hypot(a.dx[:, 0], a.dx[:, 1]).sum() / max(1, a.nframes)),
                                yaw=float(a.dx[:, 3].sum()), loop=a.loop, key=a.key, next=-1,
                                dx=[float(a.dx[:, 0].sum()), float(a.dx[:, 1].sum())])
        new.append(n)
    alist = [dict(name=k, fps=30.0, loop=True, frames=anims[k]) for k in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    steps.stamp(meta, STEP, new)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, ', '.join(new))


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
