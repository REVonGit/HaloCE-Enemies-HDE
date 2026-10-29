"""Halo 2's Jackal rifle stance on the Halo CE Jackals -> out/models/<char>/<char>.iqm and .json

    python3 jackal_rifle_anims.py [char ...]    # after extract_chars.py (the Jackals); before low_ready_anims.py,
                                                # reload_anims.py and cover_anims.py, which add the stance's low ready,
                                                # reloads and cover

Halo CE's Jackal has a 'stand rifle' set (idle, moves, turns) that is its pistol pose again: the gun arm hangs at the
side, so a two-handed gun (the Needle Javelin: build_pack.add_needle_rifle) pointed at the floor. Halo 2's Jackal
(08a_deltacliffs.map) is the same biped, gun in the left hand as on CE's (bones by name, 'bip01 l hand' = 'l_hand'),
and carries its beam rifle in a two-handed rifle stance: that set goes onto the CE Jackals in place of CE's
(h2_elite_anims.stance_anims, as draeth_stances.py does for the Draeth), with the sniper's shot baked over its idle
as the stance's fire. Replaces this script's animations on each run and stamps them (lib/steps.py)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import steps
import h2_elite_anims as H
from reload_anims import JACKAL
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
CHARS = ('Jackal', 'JackalMajor')

# Halo 2 name -> CE-style name (as extract_h2_jackal.anim_plan names the Halo 2 Jackal's own)
RIFLE = {'combat:rifle:idle': 'stand rifle idle', 'combat:rifle:warn': 'stand rifle warn',
         'combat:rifle:airborne': 'stand rifle airborne', 'combat:rifle:land_soft': 'stand rifle land-soft',
         'combat:rifle:land_hard': 'stand rifle land-hard', 'combat:rifle:surprise_front:var0': 'stand rifle surprise-front',
         'combat:rifle:surprise_back': 'stand rifle surprise-back', 'combat:rifle:signal_attack': 'stand rifle signal-attack',
         'combat:rifle:celebrate': 'stand rifle celebrate',
         'crouch:rifle:idle': 'crouch rifle idle', 'crouch:rifle:move_front': 'crouch rifle move-front'}
for d in ('front', 'back', 'left', 'right'): RIFLE[f'combat:rifle:move_{d}'] = f'stand rifle move-{d}'
for d in ('left', 'right'): RIFLE[f'combat:rifle:turn_{d}'] = f'stand rifle turn-{d}'; RIFLE[f'combat:rifle:evade_{d}'] = f'stand rifle evade-{d}'
for d in ('front', 'left', 'right'): RIFLE[f'combat:rifle:dive_{d}'] = f'stand rifle dive-{d}'
FIRE = ('crouch:rifle:csr:fire_1:var0', 'combat:rifle:idle', 'stand rifle fire-1 csr baked')
H.STANCES['jackal_rifle'] = (RIFLE, FIRE)
H.STANCE_SOURCE['jackal_rifle'] = (JACKAL, H.MAP08A, H.CACHE08A)


def add(char):
    """the Halo 2 rifle stance onto char, over CE's own 'stand rifle' set and this script's earlier ones; stamped"""
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi): print(char, 'skipped'); return
    made = H.stance_anims(read_iqm(pi)[0], 'jackal_rifle')
    if not made: print(char, 'skipped: no', H.MAP08A); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    new = []
    for a in made:
        anims[a.name] = [[(tuple(t), tuple(q), tuple(s)) for (t, q, s) in fr] for fr in a.frames]
        speed = float(np.hypot(a.dx[:, 0], a.dx[:, 1]).sum() / max(1, a.nframes))
        meta['anims'][a.name] = dict(frames=a.nframes, speed=speed, yaw=float(a.dx[:, 3].sum()), loop=bool(a.loop),
                                     key=-1, next=-1, dx=[float(a.dx[:, 0].sum()), float(a.dx[:, 1].sum())])
        new.append(a.name)
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    steps.stamp(meta, 'jackal_rifle_anims', new)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, len(new), 'animations:', ', '.join(sorted(new)))


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
