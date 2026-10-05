"""Brute armour kit: the extra armour pieces in brute.blend (the h2_brute armour set), read without Blender.

    pieces = load(BLEND)      # {object name: dict(pos (N,3) in Halo 2 render-model units, nrm, uv, bones [(node, w)]
                              #                     -> bi/bw (N,4) indices into the Halo 2 Brute's nodes, tris (M,3),
                              #                     mat (M,) material names)}

Coordinates: the .blend is in JMS units on the Halo 2 Brute skeleton (both rigs in it are the Halo 2 biped, 48
nodes), so positions / 100 are the render model's. Vertex groups use three spellings of the same bones - Halo 2
('l_thigh'), the export prefix ('b_l_thigh') and Halo CE's ('bip01 l thigh') - all mapped onto the Halo 2 node
names; groups the Halo 2 Brute doesn't have (fingers, flaps, physics_control) fall back to their parent bone.
Object transforms, parenting and Mirror modifiers are applied; Triangulate / EdgeSplit / smoothing modifiers only
change shading, and normals are rebuilt here (split at 45 degrees).
"""
import os, sys, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blendfile as bf

BLEND = os.environ.get('HCE_BRUTE_KIT_BLEND', 'brute.blend')
FALLBACK = {'flap_front': 'pelvis', 'flap_rear': 'pelvis', 'physics_control': 'pelvis', 'l_toe': 'l_foot', 'r_toe': 'r_foot'}


def bone_name(g, nodes):
    n = g.lower().strip()
    if n.startswith('bip01 '): n = n[6:]
    if n.startswith('b_'): n = n[2:]
    n = n.replace(' ', '_')
    if n in nodes: return n
    if n in FALLBACK: return FALLBACK[n]
    for side in ('l_', 'r_'):                           # fingers -> hand
        if n.startswith(side) and any(n[2:].startswith(f) for f in ('index', 'ring', 'thumb', 'middle', 'pinky', 'finger')):
            return side + 'hand'
    return None


def flip_name(g):
    """Blender's left/right name flip for mirrored vertex groups (prefix / suffix 'l' / 'r' or the words)"""
    for a, b in (('l_', 'r_'), ('r_', 'l_'), ('L_', 'R_'), ('R_', 'L_')):
        if g.startswith(a): return b + g[2:]
    for a, b in (('_l', '_r'), ('_r', '_l'), ('.l', '.r'), ('.r', '.l'), ('.L', '.R'), ('.R', '.L')):
        if g.endswith(a): return g[:-2] + b
    for a, b in (('left', 'right'), ('right', 'left'), ('Left', 'Right'), ('Right', 'Left')):
        if a in g: return g.replace(a, b)
    return g


def euler(r, mode=1):
    """Blender euler orders 1..6 = XYZ XZY YXZ YZX ZXY ZYX (the first axis applied first)"""
    x, y, z = r
    R = {'X': np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]]),
         'Y': np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]),
         'Z': np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])}
    order = {1: 'XYZ', 2: 'XZY', 3: 'YXZ', 4: 'YZX', 5: 'ZXY', 6: 'ZYX'}.get(mode, 'XYZ')
    M = np.eye(3)
    for a in order: M = R[a] @ M
    return M


def quat_mat(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0; w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class Kit:
    def __init__(s, path=BLEND):
        s.B = B = bf.Blend(path)
        s.objects = {B.id_name(o): o for o in B.of_type('Object')}

    def world(s, o):
        B = s.B; B.ctx = o
        M = np.eye(4)
        rm = B.get('Object', o.off, 'rotmode')
        if rm == 0: R = quat_mat(B.get('Object', o.off, 'quat'))
        elif rm == -1:
            ax = np.array(B.get('Object', o.off, 'rotAxis')); an = B.get('Object', o.off, 'rotAngle')
            R = quat_mat((math.cos(an / 2), *(ax / max(np.linalg.norm(ax), 1e-12) * math.sin(an / 2))))
        else: R = euler(B.get('Object', o.off, 'rot'), rm)
        M[:3, :3] = R * np.array(B.get('Object', o.off, 'size'))
        M[:3, 3] = B.get('Object', o.off, 'loc')
        par = B.block(B.get('Object', o.off, 'parent'))
        if par:
            pi = np.array(B.get('Object', o.off, 'parentinv')).reshape(4, 4).T
            M = s.world(par) @ pi @ M
        return M

    def attrs(s, me):
        B = s.B; out = {}
        a = B.get('Mesh', me.off, 'attribute_storage')
        blk = B.block(B.get('AttributeStorage', a, 'dna_attributes')); n = B.get('AttributeStorage', a, 'dna_attributes_num')
        sz = B.fields('Attribute')['__size__']
        for k in range(n):
            p = blk.off + k * sz
            nb = B.block(B.get('Attribute', p, 'name'))
            name = B.d[nb.off:nb.off + nb.size].split(b'\0')[0].decode('latin1')
            dt = B.get('Attribute', p, 'data_type'); dom = B.get('Attribute', p, 'domain')
            arr = B.block(B.get('Attribute', p, 'data'))
            if not arr or B.get('Attribute', p, 'storage_type') != 0: continue
            data = B.get('AttributeArray', arr.off, 'data'); size = B.get('AttributeArray', arr.off, 'size')
            spec = {7: ('<f4', 3), 6: ('<f4', 2), 3: ('<i4', 1), 4: ('<i4', 2), 2: ('<i2', 2), 0: ('u1', 1), 1: ('<f4', 1)}.get(dt)
            if not spec: continue
            a_ = B.array(data, spec[0])
            if a_ is None: continue
            a_ = a_[:size * spec[1]]
            out[name] = (a_.reshape(size, spec[1]) if spec[1] > 1 else a_, dom)
        return out

    def piece(s, name, nodes):
        """one object -> mesh in Halo 2 render-model space, bones as indices into nodes (list of names)"""
        B = s.B; o = s.objects[name]
        me = B.block(B.get('Object', o.off, 'data'))
        B.ctx = me
        nv = B.get('Mesh', me.off, 'totvert'); nf = B.get('Mesh', me.off, 'totpoly')
        A = s.attrs(me)
        pos = A['position'][0].astype(np.float64)
        cv = A['.corner_vert'][0]
        off = B.array(B.get('Mesh', me.off, 'poly_offset_indices'), '<i4')[:nf + 1]
        mi = A['material_index'][0] if 'material_index' in A else np.zeros(nf, int)
        uvn = [k for k, (v, d) in A.items() if d == 3 and v.ndim == 2 and v.shape[1] == 2 and v.dtype == np.float32 and not k.startswith('.')]
        uv = A[uvn[0]][0] if uvn else np.zeros((len(cv), 2), np.float32)
        mats = B.array(B.get('Mesh', me.off, 'mat'), '<u8')
        mnames = [B.id_name(B.block(int(p))) if p and B.block(int(p)) else '' for p in (mats if mats is not None else [])][:B.get('Mesh', me.off, 'totcol')]
        groups = [B.get('bDeformGroup', g.off, 'name') for g in B.listbase(B.get('Mesh', me.off, 'vertex_group_names'), 'bDeformGroup')]
        # deform weights
        W = [[] for _ in range(nv)]
        lp = B.get('CustomData', B.get('Mesh', me.off, 'vdata'), 'layers'); lb = B.block(lp)
        if lb:
            lsz = B.fields('CustomDataLayer')['__size__']
            for k in range(B.get('CustomData', B.get('Mesh', me.off, 'vdata'), 'totlayer')):
                if B.get('CustomDataLayer', lb.off + k * lsz, 'type') != 2: continue
                db = B.block(B.get('CustomDataLayer', lb.off + k * lsz, 'data'))
                dsz = B.fields('MDeformVert')['__size__']
                for v in range(nv):
                    p = db.off + v * dsz
                    dwb = B.block(B.get('MDeformVert', p, 'dw')); tw = B.get('MDeformVert', p, 'totweight')
                    if not dwb: continue
                    for t in range(tw):
                        q = dwb.off + t * 8
                        g, w = B.get('MDeformWeight', q, 'def_nr'), B.get('MDeformWeight', q, 'weight')
                        if g < len(groups) and w > 0: W[v].append((groups[g], w))
        # polygons -> triangles over corners
        tris, tmat = [], []
        for f in range(nf):
            a, b = off[f], off[f + 1]
            for k in range(a + 1, b - 1): tris.append((a, k, k + 1)); tmat.append(int(mi[f]) if f < len(mi) else 0)
        tris = np.array(tris, int).reshape(-1, 3); tmat = np.array(tmat, int)
        cpos = pos[cv]; cuv = uv.astype(np.float64); cw = [W[v] for v in cv]
        # mirror modifiers (object space, before the world transform)
        B.ctx = o
        for md in B.listbase(B.get('Object', o.off, 'modifiers'), 'ModifierData'):
            if B.get('ModifierData', md.off, 'type') != 5: continue
            flag = B.get('MirrorModifierData', md.off, 'flag')
            if B.get('MirrorModifierData', md.off, 'mirror_ob'): print('  mirror object ignored on', name)
            for ax in range(3):
                if not flag & (1 << (3 + ax)): continue
                n0 = len(cpos)
                mp = cpos.copy(); mp[:, ax] *= -1
                mw = [[(flip_name(g), w) for g, w in ws] for ws in cw] if flag & (1 << 2) else cw
                cpos = np.concatenate([cpos, mp]); cuv = np.concatenate([cuv, cuv]); cw = cw + mw
                tris = np.concatenate([tris, tris[:, ::-1] + n0]); tmat = np.concatenate([tmat, tmat])
        M = s.world(o)
        cpos = cpos @ M[:3, :3].T + M[:3, 3]
        if np.linalg.det(M[:3, :3]) < 0: tris = tris[:, ::-1]
        cpos /= 100.0
        # bones
        ni = {n: i for i, n in enumerate(nodes)}
        bi = np.zeros((len(cpos), 4), int); bw = np.zeros((len(cpos), 4))
        miss = set()
        for v, ws in enumerate(cw):
            acc = {}
            for g, w in ws:
                bn = bone_name(g, ni)
                if bn is None: miss.add(g); continue
                acc[ni[bn]] = acc.get(ni[bn], 0) + w
            if not acc: acc = {ni['head']: 1.0} if False else {}
            it = sorted(acc.items(), key=lambda x: -x[1])[:4]
            tot = sum(w for _, w in it)
            for k, (b_, w) in enumerate(it): bi[v, k] = b_; bw[v, k] = w / tot
        # left/right sanity: a vertex well off to one side bound to the other side's limb bones takes its mirror
        # bone (the kit's bracers are both weighted to the left forearm)
        for v in range(len(cpos)):
            y = cpos[v, 1]
            if abs(y) < 0.05: continue
            for k_ in range(4):
                if bw[v, k_] <= 0: continue
                nm = nodes[bi[v, k_]]
                want, other = ('l_', 'r_') if y > 0 else ('r_', 'l_')
                if nm.startswith(other) and want + nm[2:] in ni: bi[v, k_] = ni[want + nm[2:]]
        unweighted = int((bw.sum(1) == 0).sum())
        # normals: face normals averaged over corners sharing a position within 45 degrees
        fn = np.cross(cpos[tris[:, 1]] - cpos[tris[:, 0]], cpos[tris[:, 2]] - cpos[tris[:, 0]])
        fl = np.linalg.norm(fn, axis=1, keepdims=True); fn = fn / np.maximum(fl, 1e-12)
        key = np.round(cpos * 1e4).astype(np.int64)
        groups_ = {}
        for t in range(len(tris)):
            for c in tris[t]: groups_.setdefault(tuple(key[c]), []).append((c, t))
        nrm = np.zeros_like(cpos)
        cos45 = math.cos(math.radians(45))
        for lst in groups_.values():
            for c, t in lst:
                acc = np.zeros(3)
                for c2, t2 in lst:
                    if fn[t] @ fn[t2] >= cos45: acc += fn[t2] * fl[t2, 0]
                nrm[c] = acc / max(np.linalg.norm(acc), 1e-12)
        return dict(name=name, pos=cpos, nrm=nrm, uv=cuv, bi=bi, bw=bw, tris=tris, tmat=tmat, mats=mnames,
                    missing=sorted(miss), unweighted=unweighted)


def fill_weights(p, src):
    """vertices with no usable weights take the weights of the nearest vertex of src (the body)"""
    miss = p['bw'].sum(1) == 0
    if not miss.any(): return p
    from scipy.spatial import cKDTree
    _, nn = cKDTree(src['pos']).query(p['pos'][miss])
    p['bi'][miss] = src['bi'][nn]; p['bw'][miss] = src['bw'][nn]
    p['unweighted'] = 0
    return p
