"""a minimal binary FBX (7.x) reader: the node tree, and the meshes in it (generator/needle_rifle_ce.py)"""
import struct, zlib
import numpy as np

class Node:
    __slots__ = ('name', 'props', 'kids')
    def __init__(s, name, props, kids): s.name, s.props, s.kids = name, props, kids
    def find(s, name): return next((k for k in s.kids if k.name == name), None)
    def all(s, name): return [k for k in s.kids if k.name == name]
    def __repr__(s): return f'<{s.name} {s.props[:3]} {len(s.kids)} kids>'

_ARR = {'f': ('<f4', 4), 'd': ('<f8', 8), 'l': ('<i8', 8), 'i': ('<i4', 4), 'b': ('<u1', 1)}

def _prop(b, o):
    t = chr(b[o]); o += 1
    if t == 'Y': return struct.unpack_from('<h', b, o)[0], o + 2
    if t == 'C': return bool(b[o]), o + 1
    if t == 'I': return struct.unpack_from('<i', b, o)[0], o + 4
    if t == 'F': return struct.unpack_from('<f', b, o)[0], o + 4
    if t == 'D': return struct.unpack_from('<d', b, o)[0], o + 8
    if t == 'L': return struct.unpack_from('<q', b, o)[0], o + 8
    if t in 'SR':
        n = struct.unpack_from('<I', b, o)[0]; o += 4; v = bytes(b[o:o + n])
        return (v.decode('utf8', 'replace') if t == 'S' else v), o + n
    if t in _ARR:
        n, enc, cl = struct.unpack_from('<III', b, o); o += 12
        raw = bytes(b[o:o + cl]); o += cl
        if enc == 1: raw = zlib.decompress(raw)
        return np.frombuffer(raw, _ARR[t][0], n), o
    raise ValueError(f'fbx property type {t!r}')

def load(path):
    b = open(path, 'rb').read()
    assert b[:20] == b'Kaydara FBX Binary  ', 'not a binary FBX'
    ver = struct.unpack_from('<I', b, 23)[0]; big = ver >= 7500
    def node(o):
        if big: end, np_, _ = struct.unpack_from('<QQQ', b, o); o += 24
        else: end, np_, _ = struct.unpack_from('<III', b, o); o += 12
        nl = b[o]; o += 1
        if end == 0: return None, o + nl
        name = b[o:o + nl].decode(); o += nl
        props = []
        for _ in range(np_): v, o = _prop(b, o); props.append(v)
        kids = []
        while o < end:
            k, o = node(o)
            if k is None: break
            kids.append(k)
        return Node(name, props, kids), end
    o = 27; top = []
    while o < len(b) - 13:
        k, o2 = node(o)
        if k is None: break
        top.append(k); o = o2
    return Node('', [], top)

def _p70(n):
    d = {}
    p = n.find('Properties70')
    for k in (p.kids if p else []): d[k.props[0]] = k.props[4:]
    return d

def _euler(r):
    """FBX default rotation order XYZ (applied X then Y then Z), degrees -> matrix"""
    x, y, z = np.radians(r)
    Rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    Rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx

def _local(props):
    M = np.eye(4)
    t = props.get('Lcl Translation', (0, 0, 0)); r = props.get('Lcl Rotation', (0, 0, 0)); s = props.get('Lcl Scaling', (1, 1, 1))
    pre = props.get('PreRotation', (0, 0, 0))
    M[:3, :3] = _euler(pre) @ _euler(r) @ np.diag(s); M[:3, 3] = t
    return M

def _layer(g, name, key, idxkey, ncorner, pvi, nverts):
    """a LayerElement as per-corner values"""
    le = g.find(name)
    if le is None: return None
    vals = le.find(key).props[0]
    mode = le.find('MappingInformationType').props[0]; ref = le.find('ReferenceInformationType').props[0]
    if ref.startswith('IndexToDirect') and le.find(idxkey) is not None: idx = le.find(idxkey).props[0]
    else: idx = None
    return vals, mode, idx

def meshes(root):
    """each Model with a mesh: dict(name, pos, nrm, uv (per corner, v up), tris (corner indices), tmat, mats), in world space"""
    objs = root.find('Objects'); conns = root.find('Connections')
    by = {o.props[0]: o for o in objs.kids}
    parent, children = {}, {}
    for c in conns.kids:
        if c.props[0] == 'OO': parent.setdefault(c.props[1], []).append(c.props[2]); children.setdefault(c.props[2], []).append(c.props[1])
    def world(mid):
        M = _local(_p70(by[mid]))
        for p in parent.get(mid, []):
            if p in by and by[p].name == 'Model': return world(p) @ M
        return M
    out = []
    for o in objs.kids:
        if o.name != 'Model': continue
        kids = [by[k] for k in children.get(o.props[0], []) if k in by]
        geo = next((k for k in kids if k.name == 'Geometry'), None)
        if geo is None: continue
        mats = [k.props[1].split('\x00')[0] for k in kids if k.name == 'Material']
        V = geo.find('Vertices').props[0].reshape(-1, 3).astype(np.float64)
        pvi = geo.find('PolygonVertexIndex').props[0].astype(np.int64)
        cv = np.where(pvi < 0, ~pvi, pvi); ends = np.nonzero(pvi < 0)[0]
        starts = np.concatenate([[0], ends[:-1] + 1])
        nc = len(pvi); poly_of = np.repeat(np.arange(len(ends)), ends - starts + 1)
        def per_corner(name, key, idxkey, dim):
            L = _layer(geo, name, key, idxkey, nc, pvi, len(V))
            if L is None: return None
            vals, mode, idx = L; vals = vals.reshape(-1, dim).astype(np.float64)
            if mode == 'ByPolygonVertex': i = np.arange(nc)
            elif mode in ('ByVertice', 'ByVertex'): i = cv
            elif mode == 'ByPolygon': i = poly_of
            else: i = np.zeros(nc, int)
            if idx is not None: i = idx[i]
            return vals[i]
        N = per_corner('LayerElementNormal', 'Normals', 'NormalsIndex', 3)
        U = per_corner('LayerElementUV', 'UV', 'UVIndex', 2)
        le = geo.find('LayerElementMaterial')
        if le is not None:
            m = le.find('Materials').props[0].astype(int)
            pm = m if le.find('MappingInformationType').props[0] == 'ByPolygon' else np.zeros(len(ends), int) + m[0]
        else: pm = np.zeros(len(ends), int)
        tris, tmat = [], []
        for f, (a, b) in enumerate(zip(starts, ends)):
            for k in range(a + 1, b): tris.append((a, k, k + 1)); tmat.append(int(pm[f]))
        M = world(o.props[0])
        pos = V[cv] @ M[:3, :3].T + M[:3, 3]
        if N is None: N = np.zeros_like(pos); N[:, 2] = 1
        Ni = np.linalg.inv(M[:3, :3]).T; nrm = N @ Ni.T; nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        if np.linalg.det(M[:3, :3]) < 0: tris = [(a, c, b) for a, b, c in tris]
        out.append(dict(name=o.props[1].split('\x00')[0], pos=pos, nrm=nrm, uv=U if U is not None else np.zeros((nc, 2)),
                        tris=np.array(tris, int).reshape(-1, 3), tmat=np.array(tmat, int), mats=mats))
    return out

def axes(root):
    """GlobalSettings (UpAxis, UpAxisSign, FrontAxis, FrontAxisSign, CoordAxis, CoordAxisSign, UnitScaleFactor)"""
    g = _p70(root.find('GlobalSettings'))
    return {k: g[k][0] for k in ('UpAxis', 'UpAxisSign', 'FrontAxis', 'FrontAxisSign', 'CoordAxis', 'CoordAxisSign', 'UnitScaleFactor') if k in g}
