"""SOI7's Hunter animations from Halo: Brutality Evolved on the Hunter -> out/models/Hunter/Hunter.iqm, .json

    HCE_BE_A50=/path/to/brutality_evolved/maps/a50.map python3 hunter_be_anims.py

Halo: Brutality Evolved (RoxanneGoat; MCC Steam Workshop 3014096841) gives the Hunter SOI7's animation graph
('old_lords\\characters\\hunter\\hunter') on Halo CE's own Hunter biped, bone for bone. Next to Halo CE's it adds a
standing idle, a berserk roar and four melee swings (in place of Halo CE's one), and redoes the crouched idle,
crouched walk (four ways) and turns; its aim, look, fire and flinch overlays are Halo CE's. This takes those
(ANIMS) from the mod's a50 into the Hunter's IQM and json, replacing Halo CE's crouched set and dropping its single
'stand unarmed melee' (build_pack.anim_table then picks the four swings as the melee variants, the berserk and the
standing idle). Run after extract_chars.py (Hunter); replaces this script's animations on each run and stamps them
(lib/steps.py)."""
import os, sys, json, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import halomodel as hm
import steps
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
BE_A50 = os.environ.get('HCE_BE_A50', 'a50.map')
GRAPH = r'old_lords\characters\hunter\hunter'
CHAR = 'Hunter'
CHARS = (CHAR,)
# the mod's animations taken (its overlays match Halo CE's and are left as they are)
ANIMS = re.compile(r'^(stand unarmed (idle|berserk|melee%\d)|crouch unarmed (idle|move-\w+|turn-\w+))$')
DROP = ('stand unarmed melee',)          # Halo CE's single swing, which the mod's four replace


def main():
    pi, pj = f'{OUT}/models/{CHAR}/{CHAR}.iqm', f'{OUT}/models/{CHAR}/{CHAR}.json'
    if not os.path.exists(pi) or not os.path.exists(BE_A50): print(CHAR, 'skipped (no model or', BE_A50, ')'); return
    from pcmap import PCMap
    m = PCMap(BE_A50)
    t = next(t for t in m.tags if t['cls'] == 'antr' and t['name'] == GRAPH)
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    for k in (meta.get('steps') or {}).get('hunter_be_anims', []): anims.pop(k, None); meta['anims'].pop(k, None)
    got = [a for a in hm.read_animations(m, t, len(joints)) if a.type == 0 and ANIMS.match(a.name)]
    if not got: print(CHAR, 'no animations found in', GRAPH); return
    for k in DROP: anims.pop(k, None); meta['anims'].pop(k, None)
    for a in got:
        anims[a.name] = [[(tuple(tt), tuple(q), (s, s, s) if np.isscalar(s) else tuple(s)) for (tt, q, s) in fr] for fr in a.frames]
        meta['anims'][a.name] = dict(frames=a.nframes, speed=float(np.hypot(a.dx[:, 0], a.dx[:, 1]).sum() / max(1, a.nframes)),
                                     yaw=float(a.dx[:, 3].sum()), loop=a.loop, key=a.key, next=-1,
                                     dx=[float(a.dx[:, 0].sum()), float(a.dx[:, 1].sum())])
    alist = [dict(name=n, fps=30.0, loop=True, frames=anims[n]) for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(tt), tuple(q), tuple(s)) for n, p, tt, q, s in joints], meshes, alist)
    steps.stamp(meta, 'hunter_be_anims', [a.name for a in got])
    json.dump(meta, open(pj, 'w'), indent=1)
    print(CHAR, len(got), 'animations:', ', '.join(sorted(a.name for a in got)))


if __name__ == '__main__':
    main()
