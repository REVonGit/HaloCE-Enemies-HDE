"""Gun-specific Marine stances built from Halo 2's Marine rifle set ('h2rifle', h2_elite_anims.py) by inverse
kinematics, so the hands hold the gun the Marine actually carries:

* 'h2smg'     the SMG: the left hand on the SMG's vertical fore-grip (Halo 2's own left_hand marker on the SMG)
* 'h2br'      the battle rifle: the left hand where Halo 2's battle rifle puts it (its left_hand marker)
* 'h2bulldog' the Bulldog: the gun slid along its own axis until the stock's butt plate sits in the right shoulder
              pocket, the right hand carried with it to the pistol grip, and the left hand on the vertical fore-grip

Per frame: forward kinematics on the CE skeleton, the gun placed in the right hand exactly as the pack attaches it
(the hand marker), then a two-bone IK (upper arm, forearm) for each arm that has a new target, keeping the arm's own
bend plane (the elbow stays on the side the animation put it); the hand keeps the world rotation the animation gave
it. Animations where the left hand lets go of the gun (grenade throw, signals, celebrating, warning) only get the
right-arm / stock correction."""
import numpy as np
import halomodel as hm

PALM = np.array([0.028, 0.0, 0.0])       # hand bone origin (the wrist) -> the middle of the palm, in hand space (WU)
# gun -> (left hand palm target, butt plate centre or None), in Halo weapon space (WU)
GUNS = {
    'h2smg':     (np.array([0.063, 0.003, 0.009]), None),
    'h2br':      (np.array([0.105, 0.002, 0.019]), None),
    'h2bulldog': (np.array([0.162, 0.000, -0.012]), np.array([-0.106, 0.0, 0.029])),
}
FREE_LEFT = ('throw-grenade', 'signal-attack', 'celebrate', 'warn')

def world(parents, frame):
    W = []
    for i, (t, q) in enumerate(frame):
        q = hm.qnorm(np.asarray(q, float)); t = np.asarray(t, float)
        if parents[i] < 0: W.append((t, q))
        else:
            pt, pq = W[parents[i]]
            W.append((pt + hm.qrot(pq, t), hm.qnorm(hm.qmul(pq, q))))
    return W

def rot_between(a, b):
    a = a / max(np.linalg.norm(a), 1e-12); b = b / max(np.linalg.norm(b), 1e-12)
    c = np.cross(a, b); d = float(np.dot(a, b))
    if d < -0.999999:
        ax = np.cross(a, [1, 0, 0]);
        if np.linalg.norm(ax) < 1e-6: ax = np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax); return np.array([*ax, 0.0])
    q = np.array([*c, 1 + d]); return q / np.linalg.norm(q)

def two_bone(S, E, Wr, T):
    """shoulder, elbow, wrist, target -> new elbow and wrist (keeps the bend plane and the bone lengths)"""
    a = np.linalg.norm(E - S); b = np.linalg.norm(Wr - E)
    d = T - S; dl = np.linalg.norm(d)
    dl = np.clip(dl, abs(a - b) + 1e-5, a + b - 1e-5)
    dn = (T - S) / max(np.linalg.norm(T - S), 1e-12)
    pole = E - S; pole = pole - dn * np.dot(pole, dn)
    if np.linalg.norm(pole) < 1e-8: pole = np.cross(dn, [0, 0, 1])
    pole /= np.linalg.norm(pole)
    x = (a * a - b * b + dl * dl) / (2 * dl); h = np.sqrt(max(a * a - x * x, 0))
    E2 = S + dn * x + pole * h
    return E2, S + dn * dl

def solve_arm(W, local, parents, ids, target_wrist, hand_rot):
    """re-aim upper arm and forearm so the wrist reaches target_wrist; the hand gets world rotation hand_rot"""
    ua, fa, ha = ids
    S, E, Wr = W[ua][0], W[fa][0], W[ha][0]
    E2, W2 = two_bone(S, E, Wr, target_wrist)
    # upper arm
    r1 = rot_between(E - S, E2 - S)
    ua_q = hm.qnorm(hm.qmul(r1, W[ua][1]))
    # forearm: its world rotation follows the upper arm, then turns onto the new wrist
    fa_q0 = hm.qnorm(hm.qmul(r1, W[fa][1]))
    Wr_after = E2 + hm.qrot(r1, Wr - E)
    r2 = rot_between(Wr_after - E2, W2 - E2)
    fa_q = hm.qnorm(hm.qmul(r2, fa_q0))
    # back to local rotations
    pq = W[parents[ua]][1]
    local[ua] = (local[ua][0], tuple(hm.qnorm(hm.qmul(hm.qconj(pq), ua_q))))
    local[fa] = (local[fa][0], tuple(hm.qnorm(hm.qmul(hm.qconj(ua_q), fa_q))))
    local[ha] = (local[ha][0], tuple(hm.qnorm(hm.qmul(hm.qconj(fa_q), hand_rot))))

def derive(anims, joints, weapon_to_bind, Anim):
    """anims: {name: Anim} with the 'h2rifle' set; weapon_to_bind(p) -> bind-pose world point of weapon-space p.
    Returns new Anim objects for every stance in GUNS."""
    names = [j[0] for j in joints]; parents = [j[1] for j in joints]
    ix = {n: i for i, n in enumerate(names)}
    R_ids = (ix['bip01 r upperarm'], ix['bip01 r forearm'], ix['bip01 r hand'])
    L_ids = (ix['bip01 l upperarm'], ix['bip01 l forearm'], ix['bip01 l hand'])
    rh = R_ids[2]
    bind = world(parents, [(j[2], j[3]) for j in joints])
    bt, bq = bind[rh]
    def in_hand(p):                       # weapon-space point -> right-hand space
        return hm.qrot(hm.qconj(bq), weapon_to_bind(p) - bt)
    out = []
    src = {n: a for n, a in anims.items() if ' h2rifle ' in f' {n} '}
    for stance, (left, butt) in GUNS.items():
        lh_h = in_hand(left); butt_h = in_hand(butt) if butt is not None else None
        for n, a in src.items():
            free = any(k in n for k in FREE_LEFT)
            frames = []
            for fr in a.frames:
                local = [(tuple(t), tuple(q)) for (t, q, s) in fr]
                W = world(parents, local)
                ht, hq = W[rh]
                if butt_h is not None:
                    # slide the gun (with the right hand) along its own axis until the butt is in the shoulder pocket
                    ua = W[R_ids[0]][0]; chest = W[ix['bip01 spine1']][0]
                    pocket = ua + (chest - ua) * 0.25
                    butt_w = ht + hm.qrot(hq, butt_h)
                    fwd = hm.qrot(hq, in_hand(np.array([1.0, 0, 0])) - in_hand(np.zeros(3)))
                    fwd /= np.linalg.norm(fwd)
                    delta = pocket - butt_w
                    delta = fwd * np.dot(delta, fwd) + (delta - fwd * np.dot(delta, fwd)) * 0.6   # mostly along the gun
                    solve_arm(W, local, parents, R_ids, ht + delta, hq)
                    W = world(parents, local); ht, hq = W[rh]
                if not free:
                    target_palm = ht + hm.qrot(hq, lh_h)
                    lq = W[L_ids[2]][1]
                    solve_arm(W, local, parents, L_ids, target_palm - hm.qrot(lq, PALM), lq)
                frames.append([(t, q, (1.0, 1.0, 1.0)) for (t, q) in local])
            b = Anim(n.replace('h2rifle', stance), frames, np.zeros((0, 4)), a.loop)
            b.dx = a.dx.copy(); b.nframes = len(frames)
            for k in ('key', 'next', 'type'): setattr(b, k, getattr(a, k, -1))
            out.append(b)
    return out
