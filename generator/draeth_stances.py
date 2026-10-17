"""Halo 2's Elite rifle and fuel-rod stances on the Draeth -> out/models/Draeth/Draeth.iqm and .json

    python3 draeth_stances.py      # after extract_spv3.py (the Draeth); before low_ready_anims.py, reload_anims.py
                                   # and cover_anims.py, which add those stances' low ready, reloads and cover

The Draeth (the 1999 Elite, extract_spv3.py) comes with its pistol and sword stances only, so its two-handed guns
hung from one hand. It is the Elite's biped, bone for bone, so Halo 2's Elite stances go onto it as they go onto the
Halo CE Elite (h2_elite_anims.stance_anims, as extract_chars.py adds them to the Elite and the Elite Special): the
rifle stance (beam rifle, Plasma Caster) and the fuel-rod stance ('missle'), with their baked fire. Replaces this
script's animations on each run and stamps them (lib/steps.py), so build_pack.py notices a re-extraction."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import steps
from h2_elite_anims import stance_anims
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
CHARS = ('Draeth',)
STANCES = ('rifle', 'missile')                      # h2_elite_anims.STANCES keys (CE names: 'rifle', 'missle')
CE_NAME = {'rifle': 'rifle', 'missile': 'missle'}


def add(char):
    """adds the STANCES to char's IQM and json, replacing this script's earlier ones, and stamps them"""
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi): print(char, 'skipped'); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    old = set((meta.get('steps') or {}).get('draeth_stances', []))
    for k in old: anims.pop(k, None); meta['anims'].pop(k, None)
    new = []
    for st in STANCES:
        for a in stance_anims(joints, st):
            if a.name in anims: continue                  # never over the body's own animations
            anims[a.name] = [[(tuple(t), tuple(q), tuple(s)) for (t, q, s) in fr] for fr in a.frames]
            speed = float(np.hypot(a.dx[:, 0], a.dx[:, 1]).sum() / max(1, a.nframes))
            meta['anims'][a.name] = dict(frames=a.nframes, speed=speed, yaw=float(a.dx[:, 3].sum()), loop=bool(a.loop),
                                         key=-1, next=-1, dx=[float(a.dx[:, 0].sum()), float(a.dx[:, 1].sum())])
            new.append(a.name)
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    steps.stamp(meta, 'draeth_stances', new)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, len(new), 'animations:', ', '.join(sorted({n.split()[1] for n in new})))


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
