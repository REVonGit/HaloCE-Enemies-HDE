"""The Fluffers' Marine flamethrower animations -> the Marines' flamethrower ('support') stance

    python3 fluffers_flame_anims.py        # after cyborg_flame_anims.py

The Fluffers made a full heavy-weapon stance for the Halo CE Marine biped (marine_flamethrower_mk13.model_animations,
HCE_FLUFFERS_FLAME: the loose tag; 'zstand flame ...' and 'zcrouch flame ...'): idle, moves, turns, melee and grenade
throw, standing and crouched, made on the Marine's own skeleton (the same 20 'bip01' bones), so they play as they
are. The firing pose is the idle leaned into the shot (level_fire). They replace the cyborg's support set from cyborg_flame_anims.py where they have an action; what they lack (the
airborne and landing animations, the flinch, the reload) stays the cyborg's. The jaw stays shut (extract_chars.py).
Credit: the Fluffers (animations), Spiral (help).
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
from looseantr import Antr
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
SRC = os.environ.get('HCE_FLUFFERS_FLAME', 'marine_flamethrower_mk13.model_animations')
# Fluffers' name -> pack name (build_pack.anim_table's support stance)
NAMES = {
    'zstand flame idle': 'stand support idle', 'zstand flame move-front': 'stand support move-front',
    'zstand flame move-back': 'stand support move-back', 'zstand flame move-left': 'stand support move-left',
    'zstand flame move-right': 'stand support move-right', 'zstand flame turn-left': 'stand support turn-left',
    'zstand flame turn-right': 'stand support turn-right', 'zstand flame melee': 'stand support melee',
    'zstand flame throw-grenade': 'stand support throw-grenade',
    'zcrouch flame idle': 'crouch support idle', 'zcrouch flame move-front': 'crouch support move-front',
    'zcrouch flame move-back': 'crouch support move-back', 'zcrouch flame move-left': 'crouch support move-left',
    'zcrouch flame move-right': 'crouch support move-right', 'zcrouch flame turn-left': 'crouch support turn-left',
    'zcrouch flame turn-right': 'crouch support turn-right',
}
CHARS = ('Marine', 'MarineArmored')


def level_fire(nodes, frame):
    """the firing pose: the idle carries the flamethrower raised some 25 degrees (port arms); firing, the Marine leans
    into it, the upper body pitched down at the lower spine until the nozzle points level, the head kept level"""
    import marine_arsenal as ma
    from halomodel import qmul, qconj, qnorm
    import preview as pv
    import pickle
    R, t, jn, joints = ma.hand_frame('Marine')
    names = [j[0] for j in joints]
    par = [j[1] for j in joints]
    order = [nodes.index(n) for n in names]                 # the tag's node order -> the model's
    wid = ma.wid_of('flamethrower')
    d = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
    P = np.concatenate([m['pos'] for m in d['meshes']]); c = P.mean(0)
    ax = np.linalg.svd(P - c)[2][0]
    if np.dot(P[np.argmax((P - c) @ ax)], ax) < -np.dot(P[np.argmin((P - c) @ ax)], ax): ax = -ax      # toward the nozzle
    Wb = pv.world(par, [(j[2], j[3]) for j in joints]); Rb = pv.qmat(Wb[jn][1])
    loc = [(np.array(frame[k][0], float), np.array(frame[k][1], float)) for k in order]
    sp, nk = names.index('bip01 spine1'), names.index('bip01 neck')
    def pitch(l):
        """the flamethrower's nozzle axis pitch (radians, up positive) in world space for the local pose l"""
        W = pv.world(par, l); v = pv.qmat(W[jn][1]) @ Rb.T @ R @ ax
        return np.arctan2(v[2], np.hypot(v[0], v[1]))
    for _ in range(4):
        a = pitch(loc)
        W = pv.world(par, loc)
        rot = np.array([0, np.sin(a / 2), 0, np.cos(a / 2)])     # about the lateral axis: nose down by a
        new_sp = qnorm(qmul(rot, W[sp][1]))
        loc[sp] = (loc[sp][0], qnorm(qmul(qconj(W[par[sp]][1]), new_sp)))
        loc[nk] = (loc[nk][0], qnorm(qmul(qconj(new_sp), W[nk][1])))            # the head where it was
    out = list(frame)
    for j, k in enumerate(order): out[k] = (loc[j][0], loc[j][1], frame[k][2])
    print(f'  firing pose: the nozzle {np.degrees(pitch(loc)):+.1f} degrees')
    return out


def main():
    """decodes the NAMES animations from the loose tag, makes the firing pose, and writes them onto each Marine body
    by bone name (the jaw at rest), over whatever cyborg_flame_anims.py left under the same names"""
    A = Antr(SRC)
    nodes = A.nodes()
    made = {}
    for a in A.animations():
        pn = NAMES.get(a['name'])
        if not pn or a['type'] != 0: continue
        made[pn] = A.decode(a, len(nodes))
    idle = made['stand support idle'][0][0]
    fire = level_fire(nodes, idle)
    made['stand support fire-1 baked'] = ([fire] * 6, np.zeros((6, 4)))
    for char in CHARS:
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        if not os.path.exists(pi): continue
        joints, meshes, anims = read_iqm(pi)
        meta = json.load(open(pj))
        names = [j[0] for j in joints]
        assert all(n in names for n in nodes), (char, 'skeleton differs')
        src = [nodes.index(n) if n in nodes else None for n in names]
        jn = names.index('bip01 ponytail1') if 'bip01 ponytail1' in names else -1
        for pn, (frames, dx) in made.items():
            fr = []
            for f in frames:
                row = []
                for j, k in enumerate(src):
                    t, q = tuple(joints[j][2]), tuple(joints[j][3])
                    if k is not None and j != jn:
                        t, q = tuple(f[k][0]), tuple(f[k][1])
                    row.append((t, q, (1.0, 1.0, 1.0)))
                fr.append(row)
            anims[pn] = fr
            speed = float(np.hypot(dx[:, 0], dx[:, 1]).sum() / max(1, len(fr)))
            meta['anims'][pn] = dict(frames=len(fr), speed=speed, yaw=float(dx[:, 3].sum()), loop=True, key=-1, next=-1,
                                     dx=[float(dx[:, 0].sum()), float(dx[:, 1].sum())])
        alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in f] for f in anims[n]])
                 for n in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
        json.dump(meta, open(pj, 'w'), indent=1)
        print(char, sorted(made))


if __name__ == '__main__':
    main()
