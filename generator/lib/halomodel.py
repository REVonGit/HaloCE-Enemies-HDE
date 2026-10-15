"""Halo CE (Xbox) 'mode' + 'antr' extraction.

Model: the skeleton, shader list, regions/permutations and skinned geometry of a model tag (Xbox vertex formats:
compressed 32-byte and uncompressed 68-byte). read_animations: every animation of an animation_graph tag decoded
to per-frame per-node (translation, rotation, scale) plus root motion, uncompressed and compressed data alike.

Conventions used by everything downstream (iqm.py, jms.py, preview.py): quaternions are (x, y, z, w); Halo stores
node rotations conjugated, and hq() undoes that so returned quaternions are the usual convention; positions are
Halo world units (1 unit = 10 feet = 3.048 m); a joint's (t, q) is relative to its parent; frames[F][N] = (t, q, s)
with None where an overlay animation leaves a channel alone."""
import struct, math
import numpy as np
from tags import Tag, tag, HMap, LAYOUT

def cstr(m, addr, n=32):
    """Fixed-width (n bytes) NUL-padded string at virtual address addr, e.g. a node or region name."""
    o = m.v2o(addr)
    return m.d[o:o + n].split(b'\0')[0].decode('latin1')

# ---------------------------------------------------------------- math
def qmul(a, b):
    """Hamilton product a * b of (x, y, z, w) quaternions: the rotation b followed by a."""
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return np.array([aw*bx + ax*bw + ay*bz - az*by,
                     aw*by - ax*bz + ay*bw + az*bx,
                     aw*bz + ax*by - ay*bx + az*bw,
                     aw*bw - ax*bx - ay*by - az*bz])

def qrot(q, v):
    """The vector v (3) rotated by the unit quaternion q."""
    x, y, z, w = q
    u = np.array([x, y, z]); v = np.asarray(v, dtype=float)
    return v + 2.0 * np.cross(u, np.cross(u, v) + w * v)

def qconj(q):
    """The conjugate (inverse rotation) of a unit quaternion."""
    return np.array([-q[0], -q[1], -q[2], q[3]])

def qnorm(q):
    """q scaled to unit length; the identity for a zero quaternion."""
    q = np.asarray(q, dtype=float); n = np.linalg.norm(q)
    return q / n if n > 0 else np.array([0, 0, 0, 1.0])

# Halo stores node rotations as the inverse (conjugate) of the usual convention.
HALO_CONJ = True   # leave on: every reader (jms.py, looseantr.py) and writer assumes converted quaternions
def hq(q):
    """A rotation as Halo stores it -> the usual convention (normalised, conjugated when HALO_CONJ)."""
    q = qnorm(q)
    return qconj(q) if HALO_CONJ else q

# ---------------------------------------------------------------- model
class Model:
    """A model ('mode') tag: nodes (list of dict(name, parent, t, q) in parent-relative bind pose), shaders (list
    of shader tag dicts or None), base_map_scale, geoms (model_geometry Tags) and regions (list of dict(name,
    perms=[dict(name, geoms=[geometry index per LOD, super high .. super low])]))."""
    def __init__(s, m, mode_tag):
        """m: HMap; mode_tag: a 'mode' entry from m.tags."""
        s.m = m
        M = tag(m, mode_tag, 'model')
        s.tag = M
        s.nodes = []
        for n in M.block('nodes', 'model_node'):
            s.nodes.append(dict(name=cstr(m, n.addr), parent=n['parent_node_index'],
                                t=np.array(n['default_translation']), q=hq(n['default_rotation'])))
        s.shaders = [sh['shader'] for sh in M.block('shaders', 'model_shader_reference')]
        s.base_map_scale = M['base_map_scale']
        s.geoms = M.block('geometries', 'model_geometry')
        s.regions = []
        for r in M.block('regions', 'model_region'):
            perms = []
            for p in r.block('permutations', 'model_region_permutation'):
                perms.append(dict(name=cstr(m, p.addr), geoms=[p['geometry_indices[%d]' % i] for i in range(5)]))
            s.regions.append(dict(name=cstr(m, r.addr), perms=perms))

    def world_bind(s):
        """Bind pose in model space: list of (t, q) per node, parents composed in (nodes are stored parents-first)."""
        W = []
        for i, n in enumerate(s.nodes):
            if n['parent'] < 0:
                W.append((n['t'].copy(), n['q'].copy()))
            else:
                pt, pq = W[n['parent']]
                W.append((pt + qrot(pq, n['t']), qnorm(qmul(pq, n['q']))))
        return W

    # Vertex buffer type 5 (compressed, 32 bytes): pos 3f; normal packed 11/11/10-bit signed in a u32; binormal and
    # tangent u32 (skipped); uv 2 x i16 (-32767..32767 -> 0..1); node0, node1 as bytes (index * 3); weight0 as a
    # byte (weight1 = 1 - weight0). Type 4 (uncompressed, 68 bytes) is the gbxmodel layout: see pcmap.gbx_geometry.
    # Triangle buffer type 1 is a strip (count + 2 u16s, degenerates dropped, winding alternates); otherwise a list.
    # Node indices are model node indices; weights sum to 1 (one-bone vertices have w = (1, 0)).
    def geometry(s, gi):
        """list of parts: dict(shader, pos(N,3), nrm, uv(N,2), nodes(N,2), w(N,2), tris(M,3))"""
        m = s.m
        out = []
        for p in s.geoms[gi].block('parts', 'model_geometry_part'):
            tb_type, _, tb_count, tb_addr, tb_hw = m.u('hhiII', p.addr + 0x44)
            vb_type, _, vb_count, vb_off, vb_addr, vb_hw = m.u('hhiiII', p.addr + 0x54)
            data = m.u('3I', vb_hw)[1] + vb_off
            if vb_type == 5:
                raw = np.frombuffer(m.d, dtype=np.uint8, count=vb_count * 32, offset=m.v2o(data)).reshape(-1, 32)
                pos = raw[:, 0:12].copy().view('<f4').reshape(-1, 3)
                pk = raw[:, 12:16].copy().view('<u4').ravel()
                nx = ((pk & 0x7ff).astype(np.int32) ^ 0x400) - 0x400
                ny = (((pk >> 11) & 0x7ff).astype(np.int32) ^ 0x400) - 0x400
                nz = (((pk >> 22) & 0x3ff).astype(np.int32) ^ 0x200) - 0x200
                nrm = np.stack([nx / 1023.0, ny / 1023.0, nz / 511.0], 1)
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
                tc = raw[:, 24:28].copy().view('<i2').reshape(-1, 2).astype(np.float64)
                uv = (tc * 2.0 + 1.0) / 65535.0
                nd = raw[:, 28:30].astype(np.int32) // 3
                w0 = raw[:, 30].astype(np.float64) / 255.0
                w = np.stack([w0, 1.0 - w0], 1)
            elif vb_type == 4:
                raw = np.frombuffer(m.d, dtype=np.uint8, count=vb_count * 68, offset=m.v2o(data)).reshape(-1, 68)
                f = raw.copy().view('<f4')
                pos = f[:, 0:3]; nrm = f[:, 3:6]; uv = f[:, 12:14].astype(np.float64)
                nd = raw[:, 56:60].copy().view('<i2').reshape(-1, 2).astype(np.int32)
                w = f[:, 15:17].astype(np.float64)
            else:
                raise ValueError('vertex type %d' % vb_type)
            if tb_type == 1:
                idx = np.frombuffer(m.d, dtype='<u2', count=tb_count + 2, offset=m.v2o(tb_addr))
                tris = []
                for k in range(len(idx) - 2):
                    a, b, c = int(idx[k]), int(idx[k + 1]), int(idx[k + 2])
                    if a == b or b == c or a == c: continue
                    tris.append((a, b, c) if k % 2 == 0 else (b, a, c))
                tris = np.array(tris, dtype=np.int32).reshape(-1, 3)
            else:
                idx = np.frombuffer(m.d, dtype='<u2', count=tb_count * 3, offset=m.v2o(tb_addr))
                tris = idx.reshape(-1, 3).astype(np.int32)
            out.append(dict(shader=p['shader_index'], pos=pos.astype(np.float64), nrm=nrm, uv=uv,
                            nodes=nd, w=w, tris=tris))
        return out

# ---------------------------------------------------------------- animation
COMP_HDR = '11i'   # compressed animation header: 11 int32 offsets (see read_compressed); not used directly

def q6(words):
    """Unpack a 6-byte (three u16) compressed rotation into a (x, y, z, w) array in -1..1: 12 bits per component,
    sign-extended, in Halo's bit arrangement."""
    w0, w1, w2 = words
    def s16(v): v &= 0xffff; return v - 0x10000 if v & 0x8000 else v
    i = s16((w0 >> 12) | (w0 & 0xFFF0))
    j = s16(((w1 >> 4) & 0x0FF0) | (w0 & 0x000F) | (w0 << 12))
    k = s16(((((w2 >> 4) & 0x0F00) | (w1 & 0x00F0)) >> 4) | (w1 << 8))
    w = s16(((w2 >> 8) & 0x000F) | (w2 << 4))
    return np.array([i, j, k, w], dtype=float) / 32767.0

class Animation:
    """Plain holder filled by read_animations: name, type (0 base, 1 overlay, 2 replacement), nframes, flags, loop
    (loop frame index), key (key frame index), next (next animation index), fi_type (frame info type: 0 none,
    1 dx dy, 2 dx dy dyaw, 3 dx dy dz dyaw), frames[F][N] = (t, q, s) and dx (F, 4) = per-frame root motion."""
    pass

# Animations whose node count differs from node_count (e.g. the graph's weapon animations) and ones whose data
# fails to decode are skipped, so the returned list can be shorter than the tag's block. Rotations come out in the
# usual convention (hq). Overlay frames keep None for channels the animation doesn't touch (see bake_overlay).
def read_animations(m, antr_tag, node_count):
    """returns list of Animation(name, type, frames[F][N] = (t, q, s), dx[F] root motion)"""
    G = tag(m, antr_tag, 'animation_graph')
    res = []
    for a in G.block('animations', 'animation'):
        A = Animation()
        A.name = cstr(m, a.addr)
        A.type = a['type']
        A.nframes = a['frame_count']
        A.flags = a['flags']
        A.loop = a['private_loop_frame_index']
        A.key = a['private_key_frame_index']
        A.next = a['next_animation_index']
        A.fi_type = a['frame_info_type']
        if a['node_count'] != node_count or A.nframes <= 0:
            continue
        overlay = A.type != 0
        tflags = a['nodes_with_translation_flags[0]'] | (a['nodes_with_translation_flags[1]'] << 32)
        rflags = a['nodes_with_rotation_flags[0]'] | (a['nodes_with_rotation_flags[1]'] << 32)
        sflags = a['nodes_with_scale_flags[0]'] | (a['nodes_with_scale_flags[1]'] << 32)
        dsz, dad = a['default_data']
        datsz, datad = a['data']
        fsize = a['frame_size']
        cdo = a['compressed_data_offset']
        compressed = (A.flags & 1) and cdo == 0
        frames = []
        try:
            if not compressed:
                for f in range(A.nframes):
                    po = m.v2o(datad) + f * fsize
                    do = m.v2o(dad) if dsz else None
                    cur = []
                    for n in range(node_count):
                        q = t = sc = None
                        if rflags >> n & 1:
                            q = np.array(struct.unpack_from('<4h', m.d, po), float) / 32767.0; po += 8
                        elif not overlay:
                            q = np.array(struct.unpack_from('<4h', m.d, do), float) / 32767.0; do += 8
                        if tflags >> n & 1:
                            t = np.array(struct.unpack_from('<3f', m.d, po)); po += 12
                        elif not overlay:
                            t = np.array(struct.unpack_from('<3f', m.d, do)); do += 12
                        if sflags >> n & 1:
                            sc = struct.unpack_from('<f', m.d, po)[0]; po += 4
                        elif not overlay:
                            sc = struct.unpack_from('<f', m.d, do)[0]; do += 4
                        cur.append((t, hq(q) if q is not None else None, sc))
                    frames.append(cur)
            else:
                frames = read_compressed(m, datad + cdo, A.nframes, node_count, rflags, tflags, sflags)
                if overlay:
                    frames = [[(fr[n][0] if tflags >> n & 1 else None, fr[n][1] if rflags >> n & 1 else None, None)
                               for n in range(node_count)] for fr in frames]
        except Exception as e:
            continue
        A.frames = frames
        # root motion
        A.dx = np.zeros((A.nframes, 4))
        fisz, fiad = a['frame_info']
        if fisz and A.fi_type:
            per = {1: 8, 2: 12, 3: 16}[A.fi_type]
            for f in range(min(A.nframes, fisz // per)):
                vals = struct.unpack_from('<%df' % (per // 4), m.d, m.v2o(fiad) + f * per)
                if A.fi_type == 1: A.dx[f] = (vals[0], vals[1], 0, 0)
                elif A.fi_type == 2: A.dx[f] = (vals[0], vals[1], 0, vals[2])
                else: A.dx[f] = (vals[0], vals[1], vals[2], vals[3])
        res.append(A)
    return res

def read_compressed(m, addr, F, N, rflags, tflags, sflags):
    """Decode Halo's compressed keyframe animation data at virtual address addr for F frames of N nodes.
    Layout (offsets relative to addr): an 11-int header (rotation key-index table, rotation defaults, rotation keys,
    translation header, translation key-index table, translation defaults, translation keys, scale header, scale
    key-index table, scale defaults, scale keys), then at 0x2C one u32 per animated-rotation node (first key
    index << 12 | key count); the translation header holds the same per animated-translation node. Rotations are
    6-byte q6 values, translations 3 floats, keys are u16 frame numbers. Each node's channel is linearly interpolated
    between its keys (its default value before the first key, held after the last). Scale is not decoded (always
    1.0). Returns frames[F][N] = (t, q in the usual convention, 1.0), with the per-node default where a flag bit is
    clear."""
    o = m.v2o(addr)
    hdr = struct.unpack_from('<11i', m.d, o)
    (r_idx, r_def, r_key, t_hdr, t_idx, t_def, t_key, s_hdr, s_idx, s_def, s_key) = hdr
    def u16(off): return struct.unpack_from('<H', m.d, o + off)[0]
    def rot_at(off): return q6(struct.unpack_from('<3H', m.d, o + off))
    def interp(keys_frames, getter, deflt, f):
        """the value at frame f: linear between the keys at keys_frames (getter(i) gives key i's value), from deflt
        before the first key, held after the last; deflt when there are no keys"""
        if not keys_frames: return deflt
        if f < keys_frames[0]:
            a0, f0, a1, f1 = deflt, 0, getter(0), keys_frames[0]
        elif f >= keys_frames[-1]:
            return getter(len(keys_frames) - 1)
        else:
            k = max(i for i in range(len(keys_frames)) if keys_frames[i] <= f)
            a0, f0, a1, f1 = getter(k), keys_frames[k], getter(k + 1), keys_frames[k + 1]
        t = (f - f0) / max(1, (f1 - f0))
        return a0 * (1 - t) + a1 * t
    frames = [[None] * N for _ in range(F)]
    ri = ti = si = 0
    for n in range(N):
        dq = qnorm(rot_at(r_def + n * 6))
        if rflags >> n & 1:
            h = struct.unpack_from('<I', m.d, o + 0x2C + ri * 4)[0]; ri += 1
            first, cnt = h >> 12, h & 0xfff
            kf = [u16(r_idx + (first + i) * 2) for i in range(cnt)]
            getr = lambda i, first=first: qnorm(rot_at(r_key + (first + i) * 6))
        else:
            kf, getr = [], None
        dt = np.array(struct.unpack_from('<3f', m.d, o + t_def + n * 12))
        if tflags >> n & 1:
            h = struct.unpack_from('<I', m.d, o + t_hdr + ti * 4)[0]; ti += 1
            first, cnt = h >> 12, h & 0xfff
            tkf = [u16(t_idx + (first + i) * 2) for i in range(cnt)]
            gett = lambda i, first=first: np.array(struct.unpack_from('<3f', m.d, o + t_key + (first + i) * 12))
        else:
            tkf, gett = [], None
        for f in range(F):
            q = interp(kf, getr, dq, f) if kf else dq
            t = interp(tkf, gett, dt, f) if tkf else dt
            frames[f][n] = (t, hq(qnorm(q)), 1.0)
    return frames


# base_frame: one frame [N] of (t, q, s) (usually the bind pose or an idle frame); overlay_frames: an overlay
# animation's frames[F][N] with None for untouched channels. Returns full frames[F][N] ready for write_iqm.
def bake_overlay(base_frame, overlay_frames):
    """Halo overlay: rotation = overlay*base (halo conv) -> base*overlay in ours; translation added."""
    out = []
    for ov in overlay_frames:
        fr = []
        for (bt, bq, bs), (ot, oq, osc) in zip(base_frame, ov):
            t = bt + ot if ot is not None else bt
            q = qnorm(qmul(bq, oq)) if oq is not None else bq
            sc = osc if osc is not None else bs
            fr.append((t, q, sc))
        out.append(fr)
    return out
