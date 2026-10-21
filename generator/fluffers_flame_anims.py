"""The Fluffers' Marine flamethrower animations -> the Marines' flamethrower ('support') stance

    python3 fluffers_flame_anims.py        # after cyborg_flame_anims.py

The Fluffers made a full heavy-weapon stance for the Halo CE Marine biped (marine_flamethrower_mk13.model_animations,
HCE_FLUFFERS_FLAME: the loose tag; 'zstand flame ...' and 'zcrouch flame ...'): idle, moves, turns, melee and grenade
throw, standing and crouched, made on the Marine's own skeleton (the same 20 'bip01' bones), so they play as they
are. The firing pose is the idle leaned into the shot (level_fire). The left hand is moved onto Halo CE's gun's top handle (left_grip). They replace the cyborg's support set from cyborg_flame_anims.py where they have an action; what they lack (the
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


# The left hand's grip. The Fluffers made their stance for their own flamethrower; on Halo CE's (marine_arsenal's
# overlay, carried in the right hand) their left hand sits some 5 cm down the gun, inside its body. Halo's own stance
# for this gun, the cyborg's (cyborg_flame_anims.py: its support idle, retargeted onto the Marine), has the left hand on
# the top handle. left_grip moves the left hand there in every Fluffers animation where it holds the gun: per frame,
# the hand's place and turn relative to the gun hand shifted by the idle's difference from the cyborg's (so the
# motion is kept), reached with a two-bone IK of the left arm (the elbow kept on its side). Where the left hand leaves
# the gun (the grenade throw) the shift fades out: in full within GRIP_HOLD of the idle's grip, none past GRIP_FREE.
GRIP_HOLD, GRIP_FREE = 0.03, 0.10
_GRIP = {}


def _cyborg_grip(joints):
    """(left wrist place, left hand turn) relative to the gun hand in the cyborg's support idle, on this skeleton;
    None without the cyborg's map"""
    key = tuple(j[0] for j in joints)
    if key in _GRIP: return _GRIP[key]
    import preview as pv
    import cyborg_flame_anims as cf
    if not os.path.exists(cf.MAP): print('  no', cf.MAP, ': the left hand kept where the Fluffers put it'); _GRIP[key] = None; return None
    nodes, crest, an = cf.cyborg_anims()
    fr = cf.retarget(joints, nodes, crest, [an['stand support idle'].frames[0]])[0]
    _GRIP[key] = _rel(joints, [(x[0], x[1]) for x in fr])
    return _GRIP[key]


def _rel(joints, loc):
    """(left wrist place, left hand rotation matrix) in the right hand's frame for local pose loc"""
    import preview as pv
    names = [j[0] for j in joints]; par = [j[1] for j in joints]
    rh, lh = names.index('bip01 r hand'), names.index('bip01 l hand')
    W = pv.world(par, loc)
    Rr = pv.qmat(W[rh][1])
    return Rr.T @ (np.asarray(W[lh][0], float) - W[rh][0]), Rr.T @ pv.qmat(W[lh][1])


def _mat_q(M):
    """rotation matrix -> (x, y, z, w) quaternion"""
    from scipy.spatial.transform import Rotation
    return Rotation.from_matrix(M).as_quat()


def left_grip(joints, frames, idle_loc):
    """frames (rows of (t, q, s) per joint) with the left hand on the flamethrower's top handle (see left_grip's note)"""
    import preview as pv
    from halomodel import qmul, qconj, qnorm
    cy = _cyborg_grip(joints)
    if cy is None: return frames
    names = [j[0] for j in joints]; par = [j[1] for j in joints]
    ua, fa, lh, rh = (names.index(n) for n in ('bip01 l upperarm', 'bip01 l forearm', 'bip01 l hand', 'bip01 r hand'))
    ip, iR = _rel(joints, idle_loc)
    dp, dR = cy[0] - ip, iR.T @ cy[1]                    # the idle's grip -> Halo's
    out = []
    for f in frames:
        loc = [(np.asarray(t, float), np.asarray(q, float)) for t, q, _ in f]
        W = pv.world(par, loc)
        Rr = pv.qmat(W[rh][1])
        p, Rl = _rel(joints, loc)
        w = float(np.clip((GRIP_FREE - np.linalg.norm(p - ip)) / (GRIP_FREE - GRIP_HOLD), 0, 1))   # still on the gun?
        if w <= 0: out.append(f); continue
        T = W[rh][0] + Rr @ (p + dp * w)                 # where the wrist goes (world)
        S, E, H = (np.asarray(W[k][0], float) for k in (ua, fa, lh))
        a, b = np.linalg.norm(E - S), np.linalg.norm(H - E)
        d = T - S; L = min(np.linalg.norm(d), a + b - 1e-4); u = d / np.linalg.norm(d)
        pole = (E - S) - np.dot(E - S, u) * u
        pole = pole / (np.linalg.norm(pole) or 1)
        x = (a * a - b * b + L * L) / (2 * L)
        E2 = S + u * x + pole * np.sqrt(max(a * a - x * x, 0))
        def turn(q_world, v0, v1):
            """q_world turned by the shortest rotation taking direction v0 to v1"""
            v0 = v0 / np.linalg.norm(v0); v1 = v1 / np.linalg.norm(v1)
            c = np.cross(v0, v1); w = 1 + np.dot(v0, v1)
            r = qnorm(np.array([c[0], c[1], c[2], w])) if w > 1e-6 else np.array([0, 0, 1.0, 0])
            return qnorm(qmul(r, q_world))
        qu = turn(W[ua][1], E - S, E2 - S)
        T2 = S + u * L                                   # (the reachable wrist)
        qf0 = qnorm(qmul(qu, qmul(qconj(W[ua][1]), W[fa][1])))       # the forearm carried with the upper arm
        Hc = E2 + pv.qmat(qf0) @ pv.qmat(W[fa][1]).T @ (H - E)
        qf = turn(qf0, Hc - E2, T2 - E2)
        from scipy.spatial.transform import Rotation
        qh = _mat_q(Rr @ Rl @ Rotation.from_matrix(dR).__pow__(w).as_matrix())   # the hand turned onto the handle
        loc[ua] = (loc[ua][0], qnorm(qmul(qconj(W[par[ua]][1]), qu)))
        loc[fa] = (loc[fa][0], qnorm(qmul(qconj(qu), qf)))
        loc[lh] = (loc[lh][0], qnorm(qmul(qconj(qf), qh)))
        out.append([(tuple(loc[k][0]), tuple(loc[k][1]), tuple(f[k][2])) for k in range(len(f))])
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
        # the Fluffers' idle on this body (its left hand's grip is what left_grip corrects)
        idle_loc = [(np.asarray(made['stand support idle'][0][0][k][0], float), np.asarray(made['stand support idle'][0][0][k][1], float))
                    if k is not None and j != jn else (np.asarray(joints[j][2], float), np.asarray(joints[j][3], float))
                    for j, k in enumerate(src)]
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
            fr = left_grip(joints, fr, idle_loc)
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
