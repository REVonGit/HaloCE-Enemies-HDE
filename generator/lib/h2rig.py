"""Skeleton maths shared by the Halo 2 -> Halo CE extractors (extract_h2_odst.py, extract_h2_elite_kit.py,
extract_h2_pilot.py): quaternions, bind poses, and carrying a Halo 2 mesh onto a Halo CE skeleton.

Conventions (as both games store them):
  * a quaternion is (x, y, z, w), as a numpy array or any 4-sequence
  * a skeleton is a list of joints, each with a parent index (-1 or None at the root), a translation and a rotation
    relative to its parent; Halo 2 nodes are dicts {name, parent, t, q}, IQM joints are (name, parent, t, q, ...)
  * Halo CE's joints are named 'bip01 <bone>' where Halo 2's are '<bone>' with underscores ('l_hand' -> 'bip01 l hand')

How a Halo 2 mesh is carried onto the CE skeleton (retarget): each vertex is taken out of its Halo 2 bone's bind
pose and put into the matching CE bone's bind pose, blended by its skin weights:

    P = t_ce + (q_ce * conj(q_h2)) applied to (pos - t_h2)

Halo 2 bones the CE skeleton lacks (fingers, toes, the jaw and face) are carried from their nearest ancestor that it
has (bind_ancestors), so they go rigidly with the hand, foot or head as they sit in the bind pose.
"""
import numpy as np


def qmul(a, b):
    """the rotation b, then a (Hamilton product a * b)"""
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])


def qrot(q, v):
    """the vector v rotated by the unit quaternion q"""
    x, y, z, w = q
    u = np.array([x, y, z]); return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def conj(q):
    """the inverse rotation of a unit quaternion"""
    return np.array([-q[0], -q[1], -q[2], q[3]])


def bind_world(chain):
    """bind-pose world (t, q) of each joint from [(parent, t, q)] (parents listed before their children)"""
    out = []
    for p, t, q in chain:
        t, q = np.array(t, float), np.array(q, float)
        if p is not None and p >= 0:
            pt, pq = out[p]; t = pt + qrot(pq, t); q = qmul(pq, q)
        out.append((t, q / np.linalg.norm(q)))
    return out


def h2_world(nodes):
    """bind-pose world (t, q) of each Halo 2 node"""
    return bind_world([(n.get('parent', -1), n['t'], n['q']) for n in nodes])


def ce_world(J):
    """bind-pose world (t, q) of each IQM joint"""
    return bind_world([(j[1], j[2], j[3]) for j in J])


def node_world_pos(nodes, k):
    """the bind-pose world position of one Halo 2 node (walking up its parents)"""
    t, q = np.array(nodes[k]['t'], float), np.array(nodes[k]['q'], float)
    p = nodes[k].get('parent', -1)
    while p is not None and p >= 0:
        pt, pq = np.array(nodes[p]['t'], float), np.array(nodes[p]['q'], float)
        t = pt + qrot(pq, t); q = qmul(pq, q); p = nodes[p].get('parent', -1)
    return t


def ce_head(J):
    """(index, bind-pose world position) of the CE skeleton's head joint"""
    names = [j[0] for j in J]
    k = names.index('bip01 head')
    t = np.array(J[k][2], float)
    p = J[k][1]
    while p >= 0:
        t = np.array(J[p][2], float) + qrot(np.array(J[p][3], float), t); p = J[p][1]
    return k, t


def ce_name(h2_name):
    """the CE joint name for a Halo 2 node name"""
    return 'bip01 ' + h2_name.replace('_', ' ')


def ce_bone_of(name, nodes, ce):
    """the CE joint a Halo 2 node's vertices follow: its namesake, else the nearest ancestor that has one
    (ce: CE joint name -> index)"""
    k = [n['name'] for n in nodes].index(name)
    while k is not None and k >= 0:
        cn = ce_name(nodes[k]['name'])
        if cn in ce: return ce[cn]
        k = nodes[k].get('parent', -1)
    return ce['bip01 pelvis']


def ce_bones(nodes, ce):
    """ce_bone_of for every Halo 2 node, in node order"""
    return [ce_bone_of(n['name'], nodes, ce) for n in nodes]


def bind_ancestors(nodes, ce):
    """per Halo 2 node, the node whose bind pose its vertices are carried from: itself where the CE skeleton has it,
    else its nearest ancestor that it has"""
    out = []
    for k in range(len(nodes)):
        j = k
        while j is not None and j >= 0 and ce_name(nodes[j]['name']) not in ce: j = nodes[j].get('parent', -1)
        out.append(j if j is not None and j >= 0 else 0)
    return out


def retarget(pos, nrm, bi, bw, h2w, cew, tomap, anc=None):
    """Halo 2 skinned vertices -> (positions, normals, CE bone indices (uint8, 4 a vertex), weights (uint8, sum 255))
    on the CE skeleton. pos/nrm (V, 3); bi/bw (V, k) Halo 2 node indices and weights; h2w/cew: bind_world of each
    skeleton; tomap: ce_bones; anc: bind_ancestors (None: each node from its own bind pose)"""
    pos = np.asarray(pos, float); nrm = np.asarray(nrm, float)
    bi, bw = np.asarray(bi), np.asarray(bw, float)
    P = np.zeros_like(pos); N = np.zeros_like(nrm); cb = np.zeros((len(pos), 4), int); cw = np.zeros((len(pos), 4))
    for v in range(len(pos)):
        acc = {}
        for k in range(bi.shape[1]):
            w = bw[v, k]
            if w <= 0: continue
            h = int(bi[v, k]); c = tomap[h]
            th, qh = h2w[anc[h] if anc is not None else h]; tc, qc = cew[c]
            q = qmul(qc, conj(qh))
            P[v] += w * (tc + qrot(q, pos[v] - th)); N[v] += w * qrot(q, nrm[v])
            acc[c] = acc.get(c, 0) + w
        tot = sum(acc.values()) or 1
        P[v] /= tot; N[v] /= max(np.linalg.norm(N[v]), 1e-6)
        for k, (c, w) in enumerate(sorted(acc.items(), key=lambda x: -x[1])[:4]): cb[v, k] = c; cw[v, k] = w / tot
    w8 = np.round(cw * 255).astype(int); w8[:, 0] += 255 - w8.sum(1)
    return P, N, cb.astype(np.uint8), np.clip(w8, 0, 255).astype(np.uint8)
