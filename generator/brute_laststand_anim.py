"""The Brute's kneeling last-stand pose -> out/models/Brute/Brute.iqm and Brute.json ('crouch rifle last-stand')

    python3 brute_laststand_anim.py        # after low_ready_anims.py; re-running replaces it

Halo 2's Brutes never crouch, so their animations have no crouch to drop into when a one-handed Brute loses its other
arm and fights a last stand (HaloDoom_EnemyBase.HCE_StartLastStand). This holds the low crouch at the end of the
Brute's forward dive ('stand rifle dive-front', the roll's recovery: down on its haunches, rifle forward) as a still
pose, the root put back over the body's origin. Its name starts with 'crouch ', so the crouched hitbox goes with it
(HCE_CrouchHitbox); the Brute's class names it as its HCE_LastStandAnim.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
NAME = 'crouch rifle last-stand'
SOURCE, FRAME = 'stand rifle dive-front', 38      # the dive's recovery crouch
LENGTH = 30                                       # frames (a still pose; any length loops the same)


def main():
    pi, pj = f'{OUT}/models/Brute/Brute.iqm', f'{OUT}/models/Brute/Brute.json'
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    pose = [list(j) for j in anims[SOURCE][FRAME]]
    idle = anims['stand rifle idle'][0]
    t = list(pose[0][0]); t[0], t[1] = idle[0][0][0], idle[0][0][1]   # the root over the origin (the dive had carried it on)
    pose[0][0] = tuple(t)
    anims[NAME] = [[tuple(j) for j in pose] for _ in range(LENGTH)]
    meta['anims'][NAME] = dict(frames=LENGTH, speed=0.0, yaw=0.0, loop=True, key=-1, next=-1, dx=[0.0, 0.0])
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(f'{NAME}: {SOURCE} frame {FRAME}, {LENGTH} frames -> {pi}')


if __name__ == '__main__':
    main()
