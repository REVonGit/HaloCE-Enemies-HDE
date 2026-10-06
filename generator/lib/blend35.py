"""Blender 3.x mesh reader (MVert/MPoly/MLoop/MLoopUV) on top of enemy/blendfile.py"""
import sys, numpy as np
from blendfile import Blend

def layer(B, me, cd, typ, nth=0):
    base = B.get('Mesh', me.off, cd)
    n = B.get('CustomData', base, 'totlayer'); lb = B.block(B.get('CustomData', base, 'layers'))
    lsz = B.fields('CustomDataLayer')['__size__']; k2 = 0
    for k in range(n):
        p = lb.off + k * lsz
        if B.get('CustomDataLayer', p, 'type') == typ:
            if k2 == nth: return B.block(B.get('CustomDataLayer', p, 'data')), B.get('CustomDataLayer', p, 'name')
            k2 += 1
    return None, None

def struct_array(B, blk, sname, n, fields):
    f = B.fields(sname); sz = f['__size__']
    raw = np.frombuffer(B.d, np.uint8, n * sz, blk.off).reshape(n, sz)
    out = {}
    for name, dt, cnt in fields:
        off = f[name][0]
        out[name] = raw[:, off:off + np.dtype(dt).itemsize * cnt].copy().view(dt).reshape(n, cnt) if cnt > 1 else raw[:, off:off + np.dtype(dt).itemsize].copy().view(dt).ravel()
    return out

def meshes(path):
    B = Blend(path)
    res = {}
    for o in B.of_type('Object'):
        if B.get('Object', o.off, 'type') != 1: continue
        me = B.block(B.get('Object', o.off, 'data')); B.ctx = me
        nv, nf, nl = (B.get('Mesh', me.off, k) for k in ('totvert', 'totpoly', 'totloop'))
        vb, _ = layer(B, me, 'vdata', 0); pb, _ = layer(B, me, 'pdata', 25); lb, _ = layer(B, me, 'ldata', 26); ub, uvname = layer(B, me, 'ldata', 16)
        V = struct_array(B, vb, 'MVert', nv, [('co', '<f4', 3)])['co'].astype(float)
        P = struct_array(B, pb, 'MPoly', nf, [('loopstart', '<i4', 1), ('totloop', '<i4', 1), ('mat_nr', '<i2', 1)])
        L = struct_array(B, lb, 'MLoop', nl, [('v', '<u4', 1)])['v']
        UV = struct_array(B, ub, 'MLoopUV', nl, [('uv', '<f4', 2)])['uv'].astype(float) if ub else np.zeros((nl, 2))
        mats = B.array(B.get('Mesh', me.off, 'mat'), '<u8')
        mnames = [B.id_name(B.block(int(p))) if p and B.block(int(p)) else '' for p in (mats if mats is not None else [])][:B.get('Mesh', me.off, 'totcol')]
        tris = []; tm = []
        for s, c, m in zip(P['loopstart'], P['totloop'], P['mat_nr']):
            for k in range(1, c - 1): tris.append((s, s + k, s + k + 1)); tm.append(m)
        M = np.array(B.get('Object', o.off, 'obmat')).reshape(4, 4).T
        hide = B.get('Object', o.off, 'visibility_flag') if 'visibility_flag' in B.fields('Object') else 0
        pos = V[L] @ M[:3, :3].T + M[:3, 3]
        res[B.id_name(o)] = dict(pos=pos, uv=UV, tris=np.array(tris, int).reshape(-1, 3), tmat=np.array(tm, int), mats=mnames, hide=hide, uvname=uvname)
    return B, res
