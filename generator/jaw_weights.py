"""Clean hinge weights for the Marines' jaw -> out/models/{Marine,MarineArmored}/<char>.iqm

    python3 jaw_weights.py

Halo CE's Marine faces hang the lower face on 'bip01 ponytail1' (the jaw, a child of the head), but the skin weights
spill far past the mouth: the nose tip, the upper lip and even the brow ride the jaw by half or more, and the lower lip
only by a third. Halo CE barely moved the jaw, so it never showed; opened for lip-sync (build_pack.LIP_CODE) the whole
face slid and squashed. Here each face surface gets a hinge: everything from the mouth line up belongs to the head,
the lower lip and chin to the jaw, with a short ramp between. The mouth line is found on each face's own geometry: the
deepest point of the face's midline between the nose tip and the chin (the mouth's painted-in opening). Re-running
gives the same weights. Run after extract_chars.py (extract_chars.py calls it) and before anything else rewrites the IQM.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
JAW, HEAD = 'bip01 ponytail1', 'bip01 head'
RAMP = 0.006            # world units below the mouth line over which the jaw takes over (the lower lip)


def mouth_line(P):
    """z of the mouth opening on a face: the most recessed midline point between the nose tip and the chin"""
    mid = np.where((np.abs(P[:, 1]) < 0.004) & (P[:, 0] > 0.012))[0]
    if len(mid) < 4: return None
    nm = mid[(P[mid, 2] > 0.572) & (P[mid, 2] < 0.595)]       # under a hat brim or helmet rim (every face shares one skeleton)
    if not len(nm): return None
    nose = nm[np.argmax(P[nm, 0])]
    chin = P[mid, 2].min()
    band = mid[(P[mid, 2] < P[nose, 2] - 0.006) & (P[mid, 2] > P[nose, 2] - 0.022) & (P[mid, 2] > chin + 0.008)]
    if not len(band): return None
    return float(P[band[np.argmin(P[band, 0])], 2])


def fix_mesh(m, jn, hn, zm):
    B, W, P = m['bidx'].copy(), m['bw'].astype(int), m['pos']
    onjaw = (B == jn) & (W > 0)
    if not onjaw.any() or zm is None: return None
    for v in np.where(onjaw.any(1))[0]:
        z = P[v, 2]
        tot = int(W[v][(B[v] == jn) | (B[v] == hn)].sum())
        if z >= zm: t = 0.0                                          # the mouth line and up: the head's
        else: t = min(1.0, (zm - z) / RAMP)                          # lower lip, then chin: the jaw's
        if P[v, 0] < 0.012: t *= max(0.0, P[v, 0] / 0.012)          # fading out toward the ears
        wj = int(round(tot * t))
        k_j = np.where(B[v] == jn)[0][0]
        k_h = np.where(B[v] == hn)[0]
        if not len(k_h):
            free = np.where(W[v] == 0)[0]
            if not len(free): continue
            k_h = free[0]; B[v, k_h] = hn
        else: k_h = k_h[0]
        W[v, k_j] = wj; W[v, k_h] = tot - wj
    m['bw'] = W.astype(np.uint8); m['bidx'] = B
    return zm


def fix(joints, meshes, names):
    jn = [j[0] for j in joints].index(JAW); hn = [j[0] for j in joints].index(HEAD)
    done = {}
    lines = {}                  # one mouth line per face: its surfaces together (a face can be split over several)
    for nm in set(names):
        if nm.startswith('head.'):
            lines[nm] = mouth_line(np.concatenate([m['pos'] for i, m in enumerate(meshes) if i < len(names) and names[i] == nm]))
    for i, m in enumerate(meshes):
        if not (names[i] if i < len(names) else '').startswith('head.'): continue
        zm = fix_mesh(m, jn, hn, lines[names[i]])
        if zm is not None: done[names[i]] = round(zm, 3)
    return done


def main():
    import json
    from iqm import read_iqm, write_iqm
    try:
        from extract_chars import OUT
    except Exception:
        OUT = os.path.join(HERE, 'out')
    for char in ('Marine', 'MarineArmored'):
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        if not os.path.exists(pi): continue
        joints, meshes, anims = read_iqm(pi)
        meta = json.load(open(pj))
        done = fix(joints, meshes, meta.get('mesh_names') or [])
        alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
                 for n in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
        json.dump(meta, open(pj, 'w'), indent=1)
        print(char, 'jaw hinge on', len(done), 'face surfaces', sorted(set(done.values())))


if __name__ == '__main__':
    main()
