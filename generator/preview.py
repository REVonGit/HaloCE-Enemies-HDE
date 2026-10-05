"""Tiny software renderer for checking skinned poses: painter's algorithm, per-triangle texture sample."""
import numpy as np
from PIL import Image, ImageDraw
from halomodel import qmul, qrot, qconj, qnorm

def world(parent, local):
    W = []
    for i, (t, q) in enumerate(local):
        if parent[i] < 0: W.append((np.asarray(t, float), qnorm(q)))
        else:
            pt, pq = W[parent[i]]
            W.append((pt + qrot(pq, t), qnorm(qmul(pq, q))))
    return W

def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def skin(joints, meshes, pose):
    """joints: (name,parent,t,q,s) bind locals; pose: list of (t,q) locals or None for bind"""
    parent = [j[1] for j in joints]
    B = world(parent, [(j[2], j[3]) for j in joints])
    P = world(parent, pose) if pose is not None else B
    mats = []
    for (bt, bq), (pt, pq) in zip(B, P):
        R = qmat(pq) @ qmat(bq).T
        mats.append((R, pt - R @ bt))
    out = []
    for m in meshes:
        pos = np.zeros_like(m['pos'], dtype=float)
        for k in range(4):
            w = m['bw'][:, k].astype(float) / 255.0
            if not w.any(): continue
            idx = m['bidx'][:, k]
            for j in np.unique(idx[w > 0]):
                sel = (idx == j) & (w > 0)
                R, T = mats[j]
                pos[sel] += w[sel, None] * (m['pos'][sel] @ R.T + T)
        out.append(pos)
    return out

def render(joints, meshes, pose, tex, path=None, size=512, yaw=200, pitch=10, extra=None, img=None, rect=None):
    """tex: material -> PIL image.  extra: list of (pos(N,3), tris, color) drawn too."""
    posed = skin(joints, meshes, pose)
    items = []
    a = np.radians(yaw); p = np.radians(pitch)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    V = Rx @ Rz
    allp = np.concatenate(posed + ([e[0] for e in extra] if extra else []))
    cam = allp @ V.T
    lo, hi = cam.min(0), cam.max(0)
    span = max(hi[0] - lo[0], hi[2] - lo[2]) * 1.1
    ctr = (lo + hi) / 2
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    def add(pos, tris, colfn):
        c = pos @ V.T
        for t in tris:
            a_, b_, c_ = c[t[0]], c[t[1]], c[t[2]]
            n = np.cross(pos[t[1]] - pos[t[0]], pos[t[2]] - pos[t[0]])
            nn = np.linalg.norm(n)
            if nn == 0: continue
            sh = 0.35 + 0.65 * abs(np.dot(n / nn, light))
            items.append(((a_[1] + b_[1] + c_[1]) / 3, [a_, b_, c_], colfn(t), sh))
    for m, pos in zip(meshes, posed):
        im = tex.get(m['material'])
        arr = np.asarray(im.convert('RGB')) if im is not None else None
        def colfn(t, m=m, arr=arr):
            if arr is None: return (180, 180, 180)
            uv = m['uv'][t].mean(0)
            x = int((uv[0] % 1) * (arr.shape[1] - 1)); y = int((uv[1] % 1) * (arr.shape[0] - 1))
            return tuple(int(v) for v in arr[y, x])
        add(pos, m['tris'], colfn)
    for pos, tris, col in (extra or []):
        add(pos, tris, lambda t, col=col: col)
    items.sort(key=lambda x: -x[0])
    if img is None:
        img = Image.new('RGB', (size, size), (40, 44, 52)); rect = (0, 0, size, size)
    dr = ImageDraw.Draw(img)
    x0, y0, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
    for _, tri, col, sh in items:
        pts = [(x0 + w / 2 + (v[0] - ctr[0]) / span * w, y0 + h / 2 - (v[2] - ctr[2]) / span * h) for v in tri]
        dr.polygon(pts, fill=tuple(int(min(255, c * sh)) for c in col))
    if path: img.save(path)
    return img
