"""Halo 2 source models (JMS version 8210), as the H2EK keeps them inside its tags.

An H2EK tag that was imported from a source file (a .render_model from a JMS, a .bitmap from a TIFF) carries that
source zlib-compressed in its import info. tag_sources() pulls those out; read_jms() parses a JMS 8210 into nodes
(name, parent, bind rotation/translation, world units), materials (name, permutation, region), markers, vertices
(position, normal, up to four node weights, first UV) and triangles (material, three vertex indices).
Positions are in JMS units (1/100 world unit) scaled to world units, like jms.py does for Halo CE's."""
import zlib, struct
import numpy as np

U = 0.01   # JMS units -> world units


def tag_sources(path):
    """the zlib-compressed source files embedded in an H2EK tag file, in file order (bytes)"""
    d = open(path, 'rb').read()
    out, i = [], 0x40
    while True:
        i = d.find(b'x\xda', i)
        if i < 0: break
        o = zlib.decompressobj()
        try: t = o.decompress(d[i:])
        except zlib.error: i += 2; continue
        out.append(t)
        i = len(d) - len(o.unused_data)
    return out


def bitmap_source(path):
    """an H2EK .bitmap tag's source image (its import data: 8-bit BGRA, square) as an RGBA uint8 array"""
    t = tag_sources(path)[0]
    n = int(round((len(t) // 4) ** 0.5))
    a = np.frombuffer(t, np.uint8)[:n * n * 4].reshape(n, n, 4)
    return a[:, :, [2, 1, 0, 3]].copy()


def read_jms(text):
    """Parse a JMS 8210 (str or bytes) -> dict(version, nodes=[dict(name, parent, q (x y z w as stored), t)],
    materials=[dict(name, perm, region)], markers=[dict(name, node, q, t, radius)], pos (V,3), nrm (V,3), uv (V,2)
    first UV set, bidx (V,4) node indices, bw (V,4) weights normalised to sum 1 (the four heaviest kept),
    tri_mat (T,) material index per triangle, tris (T,3)). Positions, marker translations and radii in world units.
    Lines starting with ';' are comments; blank lines are skipped."""
    if isinstance(text, bytes): text = text.decode('latin1')
    toks = [l.strip() for l in text.replace('\r', '').split('\n') if l.strip() and not l.strip().startswith(';')]
    p = 0
    def nxt():
        """the next non-comment line of the file, advancing the cursor p"""
        nonlocal p; p += 1; return toks[p - 1]
    def fl(): return [float(x) for x in nxt().split()]
    ver = int(nxt())
    nodes = []
    for _ in range(int(nxt())):
        name = nxt(); par = int(nxt()); q = fl(); t = fl()
        nodes.append(dict(name=name, parent=par, q=q, t=[x * U for x in t]))
    mats = []
    for _ in range(int(nxt())):
        name = nxt(); desc = nxt().split()
        # '(slot) Lx permutation region'
        perm, region = (desc[2], desc[3]) if len(desc) >= 4 else ('', '')
        mats.append(dict(name=name, perm=perm, region=region))
    markers = []
    for _ in range(int(nxt())):
        name = nxt(); node = int(nxt()); q = fl(); t = fl(); r = float(nxt())
        markers.append(dict(name=name, node=node, q=q, t=[x * U for x in t], radius=r * U))
    for _ in range(int(nxt())): nxt(); nxt()                 # instance xref paths
    for _ in range(int(nxt())):                              # instance markers
        nxt(); nxt(); nxt(); fl(); fl()
    nv = int(nxt())
    P = np.zeros((nv, 3)); N = np.zeros((nv, 3)); UV = np.zeros((nv, 2))
    BI = np.zeros((nv, 4), np.int32); BW = np.zeros((nv, 4))
    for i in range(nv):
        P[i] = fl(); N[i] = fl()
        inf = []
        for _ in range(int(nxt())): inf.append((int(nxt()), float(nxt())))
        inf.sort(key=lambda x: -x[1])
        for k, (b, w) in enumerate(inf[:4]): BI[i, k] = b; BW[i, k] = w
        nt = int(nxt())
        for k in range(nt):
            uv = fl()
            if k == 0: UV[i] = uv[:2]
    s = BW.sum(1, keepdims=True); BW = BW / np.where(s > 0, s, 1)
    nt = int(nxt())
    TM = np.zeros(nt, np.int32); T = np.zeros((nt, 3), np.int32)
    for i in range(nt):
        TM[i] = int(nxt()); T[i] = [int(x) for x in nxt().split()]
    return dict(version=ver, nodes=nodes, materials=mats, markers=markers, pos=P * U, nrm=N, uv=UV, bidx=BI, bw=BW,
                tri_mat=TM, tris=T)


# Returns dict(version, fps, names, parents, t (F,N,3), q (F,N,4), s (F,N)). Header lines in order: version,
# checksum, frame count, frame rate, actor count, actor name, node count; then name/parent pairs; then per frame
# per node three lines (translation, rotation, scale).
def read_jma(text):
    """a Halo 2 animation source (JMA/JMM/JMO/JMR/JMT/JMZ, version 16395): frame rate, node names and parents, and per
    frame per node its translation (world units), rotation (x, y, z, w as stored) and scale"""
    if isinstance(text, bytes): text = text.decode('latin1')
    toks = [l.strip() for l in text.replace('\r', '').split('\n') if l.strip() and not l.strip().startswith(';')]
    ver, _chk, nf, fps, _na, _actor, nn = int(toks[0]), toks[1], int(toks[2]), int(toks[3]), toks[4], toks[5], int(toks[6])
    names, parents = [], []
    p = 7
    for _ in range(nn): names.append(toks[p]); parents.append(int(toks[p + 1])); p += 2
    T = np.zeros((nf, nn, 3)); Q = np.zeros((nf, nn, 4)); S = np.ones((nf, nn))
    for f in range(nf):
        for k in range(nn):
            T[f, k] = [float(x) for x in toks[p].split()]; Q[f, k] = [float(x) for x in toks[p + 1].split()]
            S[f, k] = float(toks[p + 2]); p += 3
    return dict(version=ver, fps=fps, names=names, parents=parents, t=T * U, q=Q, s=S)
