"""Halo CE source-asset readers: JMS (8200) models and JMA/JMM/JMT/JMO/JMR/JMZ (16390/16392) animations.

Units: JMS/JMA store 1/100 world unit; everything returned here is in world units.
Rotations: Halo stores node rotations as the conjugate of the usual convention; returned quaternions are
standard (x, y, z, w) so they match halomodel / iqm.py."""
import numpy as np
from halomodel import qmul, qrot, qconj, qnorm

U = 0.01

def _lines(path):
    return [l.strip() for l in open(path, encoding='latin1') if l.strip() != '']

def _f(s): return [float(x) for x in s.split()]

def _parents(child, sib):
    par = [-1] * len(child)
    for i in range(len(child)):
        c = child[i]
        while c >= 0:
            par[c] = i
            c = sib[c]
    return par

class JMS:
    def __init__(s, path):
        L = _lines(path); i = 0
        def nx():
            nonlocal i
            v = L[i]; i += 1; return v
        s.version = int(nx()); s.checksum = int(nx())
        n = int(nx()); s.names = []; child = []; sib = []; s.q = []; s.t = []
        for _ in range(n):
            s.names.append(nx()); child.append(int(nx())); sib.append(int(nx()))
            s.q.append(qconj(qnorm(_f(nx())))); s.t.append(np.array(_f(nx())) * U)
        s.parent = _parents(child, sib)
        nm = int(nx()); s.materials = []
        for _ in range(nm): s.materials.append((nx(), nx()))
        nk = int(nx()); s.markers = []
        for _ in range(nk):
            name = nx(); region = int(nx()); node = int(nx())
            q = qconj(qnorm(_f(nx()))); t = np.array(_f(nx())) * U; r = float(nx())
            s.markers.append(dict(name=name, region=region, node=node, q=q, t=t, radius=r))
        nr = int(nx()); s.regions = [nx() for _ in range(nr)]
        nv = int(nx())
        s.node0 = np.zeros(nv, int); s.node1 = np.zeros(nv, int); s.w1 = np.zeros(nv)
        s.pos = np.zeros((nv, 3)); s.nrm = np.zeros((nv, 3)); s.uv = np.zeros((nv, 2))
        for k in range(nv):
            s.node0[k] = int(nx()); s.pos[k] = np.array(_f(nx())) * U; s.nrm[k] = _f(nx())
            s.node1[k] = int(nx()); s.w1[k] = float(nx())
            s.uv[k] = (float(nx()), float(nx())); nx()
        nt = int(nx())
        s.tri_region = np.zeros(nt, int); s.tri_mat = np.zeros(nt, int); s.tris = np.zeros((nt, 3), int)
        for k in range(nt):
            s.tri_region[k] = int(nx()); s.tri_mat[k] = int(nx()); s.tris[k] = [int(x) for x in nx().split()]

    def world_bind(s):
        return world(s.parent, [(t, q) for t, q in zip(s.t, s.q)])

def world(parent, local):
    W = []
    for i, (t, q) in enumerate(local):
        if parent[i] < 0: W.append((np.asarray(t, float), qnorm(q)))
        else:
            pt, pq = W[parent[i]]
            W.append((pt + qrot(pq, t), qnorm(qmul(pq, q))))
    return W

class JMA:
    """frames[F][N] = (t, q, scale) in local (parent) space, standard quaternions, world units."""
    def __init__(s, path):
        L = _lines(path); i = 0
        def nx():
            nonlocal i
            v = L[i]; i += 1; return v
        s.version = int(nx()); s.nframes = int(nx()); s.fps = float(nx())
        na = int(nx())
        for _ in range(na): nx()
        n = int(nx()); s.checksum = int(nx())
        s.names = []; child = []; sib = []
        for _ in range(n):
            s.names.append(nx())
            if s.version >= 16391:
                child.append(int(nx())); sib.append(int(nx()))
        s.parent = _parents(child, sib) if child else None
        s.frames = []
        for f in range(s.nframes):
            fr = []
            for k in range(n):
                t = np.array(_f(nx())) * U; q = qconj(qnorm(_f(nx()))); sc = float(nx())
                fr.append((t, q, sc))
            s.frames.append(fr)
        ext = path.rsplit('.', 1)[-1].upper()
        s.kind = ext
