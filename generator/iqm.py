"""Minimal IQM v2 writer (skeletal meshes + animations)."""
import struct
import numpy as np

class IQMWriter:
    def __init__(s):
        s.text = b'\0'
        s.textidx = {'': 0}
    def T(s, t):
        if t not in s.textidx:
            s.textidx[t] = len(s.text)
            s.text += t.encode('latin1') + b'\0'
        return s.textidx[t]

def write_iqm(path, joints, meshes, anims):
    """
    joints: list of (name, parent, t(3), q(4 xyzw), s(3))
    meshes: list of dict(name, material, pos(N,3), nrm(N,3), uv(N,2), bidx(N,4) uint8, bw(N,4) uint8, tris(M,3))
    anims: list of dict(name, fps, loop(bool), frames: list[F] of list[J] of (t,q,s))
    """
    W = IQMWriter()
    for j in joints: W.T(j[0])
    for m in meshes: W.T(m['name']); W.T(m['material'])
    for a in anims: W.T(a['name'])
    # vertex data
    pos = np.concatenate([m['pos'] for m in meshes]).astype('<f4')
    nrm = np.concatenate([m['nrm'] for m in meshes]).astype('<f4')
    uv = np.concatenate([m['uv'] for m in meshes]).astype('<f4')
    bi = np.concatenate([m['bidx'] for m in meshes]).astype(np.uint8)
    bw = np.concatenate([m['bw'] for m in meshes]).astype(np.uint8)
    tris = []; mesh_recs = []; v0 = 0; t0 = 0
    for m in meshes:
        n = len(m['pos']); k = len(m['tris'])
        tris.append(m['tris'] + v0)
        mesh_recs.append((W.T(m['name']), W.T(m['material']), v0, n, t0, k))
        v0 += n; t0 += k
    tris = np.concatenate(tris).astype('<u4') if tris else np.zeros((0, 3), '<u4')
    NV = len(pos); NJ = len(joints)
    # poses / frames: 10 channels per joint
    allf = [f for a in anims for f in a['frames']]
    NF = len(allf)
    chan = np.zeros((NF, NJ, 10), dtype=np.float64)
    for fi, fr in enumerate(allf):
        for j, (t, q, sc) in enumerate(fr):
            q = np.asarray(q, float)
            chan[fi, j, 0:3] = t
            chan[fi, j, 3:7] = q
            chan[fi, j, 7:10] = (sc, sc, sc) if np.isscalar(sc) else sc
    poses = []
    mask_list = []
    for j in range(NJ):
        offs = []; scales = []; mask = 0
        for c in range(10):
            if NF:
                lo = chan[:, j, c].min(); hi = chan[:, j, c].max()
            else:
                lo = hi = 0.0
            if hi - lo > 1e-6:
                mask |= 1 << c
                offs.append(lo); scales.append((hi - lo) / 65535.0)
            else:
                offs.append(lo); scales.append(0.0)
        poses.append((joints[j][1], mask, offs, scales))
        mask_list.append(mask)
    frames = []
    for fi in range(NF):
        for j in range(NJ):
            p, mask, offs, scales = poses[j]
            for c in range(10):
                if mask >> c & 1:
                    frames.append(int(round((chan[fi, j, c] - offs[c]) / scales[c])))
    NFC = sum(bin(mk).count('1') for mk in mask_list)
    frames = np.clip(np.array(frames, dtype=np.int64), 0, 65535).astype('<u2')
    # layout
    HDR = 124
    blobs = []
    off = HDR
    def add(b):
        nonlocal off
        o = off
        pad = (-len(b)) % 4
        blobs.append(b + b'\0' * pad); off += len(b) + pad
        return o
    ofs_text = add(W.text)
    ofs_meshes = add(b''.join(struct.pack('<6I', *r) for r in mesh_recs))
    va_data = [(0, 7, 3, pos.tobytes()), (1, 7, 2, uv.tobytes()), (2, 7, 3, nrm.tobytes()),
               (4, 1, 4, bi.tobytes()), (5, 1, 4, bw.tobytes())]
    va_offsets = []
    for typ, fmt, size, data in va_data:
        va_offsets.append(add(data))
    ofs_va = add(b''.join(struct.pack('<5I', typ, 0, fmt, size, o) for (typ, fmt, size, _), o in zip(va_data, va_offsets)))
    ofs_tris = add(tris.tobytes())
    jb = b''
    for name, parent, t, q, sc in joints:
        jb += struct.pack('<Ii3f4f3f', W.T(name), parent, *t, *q, *sc)
    ofs_joints = add(jb)
    pb = b''
    for parent, mask, offs, scales in poses:
        pb += struct.pack('<iI10f10f', parent, mask, *offs, *scales)
    ofs_poses = add(pb)
    ab = b''; first = 0
    for a in anims:
        ab += struct.pack('<IIIfI', W.T(a['name']), first, len(a['frames']), float(a['fps']), 1 if a.get('loop') else 0)
        first += len(a['frames'])
    ofs_anims = add(ab)
    ofs_frames = add(frames.tobytes())
    size = off
    hdr = struct.pack('<16sII', b'INTERQUAKEMODEL\0', 2, size) + struct.pack('<25I',
        0, len(W.text), ofs_text, len(mesh_recs), ofs_meshes, len(va_data), NV, ofs_va,
        len(tris), ofs_tris, 0, NJ, ofs_joints, NJ if NF else 0, ofs_poses if NF else 0,
        len(anims), ofs_anims if anims else 0, NF, NFC if NF else 0, ofs_frames if NF else 0,
        0, 0, 0, 0, 0)
    assert len(hdr) == HDR, len(hdr)
    with open(path, 'wb') as f:
        f.write(hdr)
        for b in blobs: f.write(b)
    return size

def read_iqm(path):
    """inverse of write_iqm (for previews/tests): returns joints, meshes, anims (frames[F][J] = (t, q, s))"""
    d = open(path, 'rb').read()
    h = struct.unpack_from('<25I', d, 24)
    (flags, ntext, otext, nmesh, omesh, nva, nv, ova, ntri, otri, oadj, nj, oj, npose, opose,
     nanim, oanim, nf, nfc, of, ob, nc, oc, ne, oe) = h
    def s(o): return d[otext + o:d.index(b'\0', otext + o)].decode('latin1')
    va = {}
    for i in range(nva):
        typ, fl, fmt, size, o = struct.unpack_from('<5I', d, ova + i * 20)
        dt = {7: '<f4', 1: 'u1'}[fmt]
        va[typ] = np.frombuffer(d, dt, nv * size, o).reshape(nv, size)
    tris = np.frombuffer(d, '<u4', ntri * 3, otri).reshape(-1, 3)
    joints = []
    for i in range(nj):
        r = struct.unpack_from('<Ii3f4f3f', d, oj + i * 48)
        joints.append((s(r[0]), r[1], r[2:5], r[5:9], r[9:12]))
    meshes = []
    for i in range(nmesh):
        n, mat, v0, vn, t0, tn = struct.unpack_from('<6I', d, omesh + i * 24)
        meshes.append(dict(name=s(n), material=s(mat), pos=va[0][v0:v0 + vn].astype(float), uv=va[1][v0:v0 + vn].astype(float),
                           nrm=va[2][v0:v0 + vn].astype(float), bidx=va[4][v0:v0 + vn], bw=va[5][v0:v0 + vn],
                           tris=tris[t0:t0 + tn].astype(int) - v0))
    poses = [struct.unpack_from('<iI10f10f', d, opose + i * 88) for i in range(npose)]
    fr = np.frombuffer(d, '<u2', nf * nfc, of) if nf else np.zeros(0)
    allf = []; k = 0
    for f in range(nf):
        cur = []
        for p in poses:
            mask = p[1]; ch = []
            for c in range(10):
                v = p[2 + c]
                if mask >> c & 1: v += fr[k] * p[12 + c]; k += 1
                ch.append(v)
            cur.append((np.array(ch[0:3]), np.array(ch[3:7]), np.array(ch[7:10])))
        allf.append(cur)
    anims = {}
    for i in range(nanim):
        n, first, num, fps, fl = struct.unpack_from('<IIIfI', d, oanim + i * 20)
        anims[s(n)] = allf[first:first + num]
    return joints, meshes, anims
