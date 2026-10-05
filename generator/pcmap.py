"""Halo CE PC / MCC cache file (.map, uncompressed, tag index base 0x50000000) with the HMap interface
used by tags.py / halomodel.py, plus gbxmodel geometry (vertices and strips live in the model-data area)."""
import struct
import numpy as np

class PCMap:
    BASE = 0x50000000
    def __init__(s, path):
        s.d = d = open(path, 'rb').read()
        s.off, _ = struct.unpack_from('<II', d, 0x10)
        s.name = d[0x20:0x40].split(b'\0')[0].decode()
        ptr, s.scen_id, _, s.count, _, s.model_off, _, s.index_rel, s.model_size = struct.unpack_from('<9I', d, s.off)
        s.tags = []; s.byid = {}
        p = s.v2o(ptr)
        for i in range(s.count):
            q = p + i * 32
            cls = d[q:q + 4][::-1].decode('latin1')
            tid, nptr, dptr, ext = struct.unpack_from('<IIII', d, q + 12)
            t = dict(cls=cls, id=tid, name=s.cstr(nptr), data=dptr, ext=ext)
            s.tags.append(t); s.byid[tid] = t
    def v2o(s, a): return a - s.BASE + s.off
    def cstr(s, a):
        o = s.v2o(a); return s.d[o:s.d.index(b'\0', o)].decode('latin1')
    def u(s, fmt, a): return struct.unpack_from('<' + fmt, s.d, s.v2o(a))
    def reflexive(s, a): return struct.unpack_from('<III', s.d, s.v2o(a))[:2]
    def find(s, cls): return [t for t in s.tags if t['cls'] == cls]

PART = 132   # gbxmodel part in PC caches (decomp part + local-node table)

def gbx_geometry(m, geom_addr):
    """parts of one gbxmodel geometry: dict(shader, pos, nrm, uv, nodes, w, tris)"""
    cnt, ptr = m.u('II', geom_addr + 36)
    out = []
    for i in range(cnt):
        p = ptr + i * PART
        shader = m.u('h', p + 4)[0]
        icount, ioff, ioff2 = m.u('iII', p + 0x48)
        vcount = m.u('i', p + 0x58)[0]
        voff = m.u('I', p + 0x64)[0]
        lnc = m.d[m.v2o(p + 0x6B)]
        local = list(m.d[m.v2o(p + 0x6C):m.v2o(p + 0x6C) + 22])
        raw = np.frombuffer(m.d, np.uint8, vcount * 68, m.model_off + voff).reshape(-1, 68)
        f = raw.copy().view('<f4')
        pos = f[:, 0:3].astype(np.float64); nrm = f[:, 3:6]; uv = f[:, 12:14].astype(np.float64)
        nd = raw[:, 56:60].copy().view('<i2').reshape(-1, 2).astype(np.int32)
        w = f[:, 15:17].astype(np.float64)
        if lnc:   # local node indices -> model nodes
            nd = np.where(nd >= 0, np.array(local + [0] * 32)[np.clip(nd, 0, 53)], nd)
        idx = np.frombuffer(m.d, '<u2', icount + 2, m.model_off + m.index_rel + ioff)
        tris = []
        for k in range(len(idx) - 2):
            a, b, c = int(idx[k]), int(idx[k + 1]), int(idx[k + 2])
            if a == b or b == c or a == c or max(a, b, c) >= vcount: continue
            tris.append((a, b, c) if k % 2 == 0 else (b, a, c))
        out.append(dict(shader=shader, pos=pos, nrm=nrm, uv=uv, nodes=nd, w=w,
                        tris=np.array(tris, np.int32).reshape(-1, 3)))
    return out
