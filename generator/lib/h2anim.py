"""Halo 2 animation graph (jmad) decoding: codecs ported from TagTool (UncompressedStatic, 8-byte quantized
rotation, byte/word keyframe lightly quantized, and their reversed variants). Units stay in world units.

    skel, anims = graph(m, 'objects\\characters\\elite\\elite')
    frames, move = decode(a['data'], a['sizes'], a['frames'], a['nodes'], defaults)

An animation's data blob is: [static codec block][animated codec block][unknown][static flags][animated flags]
[movement data]; `sizes` from graph() gives each part's length. The codec blocks list, per node that has the
matching flag bit, that node's rotation / translation / scale keys; every other node takes its default (bind) value.
Rotations are returned as stored (x, y, z, w) and the Halo 2 extractors convert them to the Halo CE convention
themselves."""
import struct
import numpy as np

def _q(v):
    """Four int16 -> unit (x, y, z, w) quaternion (identity if zero)."""
    q = np.array(v, np.float64) / 32767.0
    n = np.linalg.norm(q); return q / n if n > 0 else np.array([0, 0, 0, 1.0])

class Codec:
    """One decoded codec block: type (byte 0), nr/nt/ns (node counts with rotation / translation / scale data), and
    per animated node its values (rot: list of quaternions, tr: list of (3) arrays, sc: list of floats) and the
    frame numbers they sit on (rk, tk, sk). Values and keys line up index for index."""
    def __init__(s, data, pos, frames):
        """data: the animation blob; pos: offset of the codec block; frames: frame count."""
        s.d = data; s.p0 = pos; s.F = frames
        s.type, s.nr, s.nt, s.ns = data[pos], data[pos + 1], data[pos + 2], data[pos + 3]
        s.rot = []; s.tr = []; s.sc = []; s.rk = []; s.tk = []; s.sk = []

def read_codec(d, pos, F):
    """Parse the codec block at pos. Type 1 (UncompressedStatic) holds one value per node (keys left empty, every
    frame uses it); type 3 (uncompressed animated) holds F values per node, laid out node-major; types 4-7 are
    keyframed: a run of key frame numbers per node (bytes for 4/6, words for 5/7, read until the numbers stop
    increasing or exceed F) at pos + 48 + 4 * (nr + nt + ns), then the values at the three offsets stored at pos + 32.
    Types 6/7 store the lists reversed, so they are flipped back. Other types raise ValueError."""
    c = Codec(d, pos, F); t = c.type
    if t in (1, 3):
        toff, soff, rbs, tbs, sbs = struct.unpack_from('<5I', d, pos + 12)
        p = pos + 32
        n = 1 if t == 1 else F
        for i in range(c.nr):
            c.rot.append([_q(struct.unpack_from('<4h', d, p + 8 * (i * n + k))) for k in range(n)])
        p = pos + 32 + c.nr * n * 8 if t == 1 else pos + 32 + rbs * c.nr
        for i in range(c.nt):
            c.tr.append([np.array(struct.unpack_from('<3f', d, p + 12 * (i * n + k))) for k in range(n)])
        p2 = p + c.nt * n * 12 if t == 1 else p + tbs * c.nt
        for i in range(c.ns):
            c.sc.append([struct.unpack_from('<f', d, p2 + 4 * (i * n + k))[0] for k in range(n)])
        if t == 3:
            c.rk = [list(range(F))] * c.nr; c.tk = [list(range(F))] * c.nt; c.sk = [list(range(F))] * c.ns
        return c
    if t in (4, 5, 6, 7):
        ks = 1 if t in (4, 6) else 2
        roff, toff, soff = struct.unpack_from('<3I', d, pos + 32)
        p = pos + 48 + 4 * (c.nr + c.nt + c.ns)
        def keys():
            """read one node's keyframe index list (uint8 or uint16 per ks) from p, stopping when the indices stop
            rising or pass F; advances p"""
            nonlocal p
            out = []
            while True:
                v = d[p] if ks == 1 else struct.unpack_from('<H', d, p)[0]
                if out and not (out[-1] <= v and F >= v): break
                out.append(v); p += ks
            return out
        c.rk = [keys() for _ in range(c.nr)]; c.tk = [keys() for _ in range(c.nt)]; c.sk = [keys() for _ in range(c.ns)]
        p = pos + roff
        for k in c.rk:
            c.rot.append([_q(struct.unpack_from('<4h', d, p + 8 * j)) for j in range(len(k))]); p += 8 * len(k)
        p = pos + toff
        for k in c.tk:
            c.tr.append([np.array(struct.unpack_from('<3f', d, p + 12 * j)) for j in range(len(k))]); p += 12 * len(k)
        p = pos + soff
        for k in c.sk:
            c.sc.append([struct.unpack_from('<f', d, p + 4 * j)[0] for j in range(len(k))]); p += 4 * len(k)
        if t in (6, 7):
            for a in ('rk', 'tk', 'sk', 'rot', 'tr', 'sc'): getattr(c, a).reverse()
        return c
    raise ValueError('codec %d' % t)

def slerp(a, b, t):
    """Spherical interpolation between unit quaternions a and b at t in 0..1, taking the short way round."""
    d = float(np.dot(a, b))
    if d < 0: b = -b; d = -d
    if d > 0.9995: r = a + (b - a) * t; return r / np.linalg.norm(r)
    th = np.arccos(d); return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)

def sample(keys, vals, f, interp):
    """Value at frame f of a keyed channel: keys (sorted frame numbers), vals (one per key), interp(a, b, t) between
    the two keys around f; clamped to the first / last key outside the range."""
    if len(keys) == 1 or f <= keys[0]: return vals[0]
    if f >= keys[-1]: return vals[-1]
    j = int(np.searchsorted(keys, f, side='right'))
    k0, k1 = keys[j - 1], keys[j]
    if k0 == f: return vals[j - 1]
    return interp(vals[j - 1], vals[j], (f - k0) / (k1 - k0))

def bits(d, off, size, n):
    """A node-flags block (size bytes at off: three equal bit sets, rotation / translation / scale, each a run of
    u32 words) -> [[bool] * n] * 3, or None when the block is empty."""
    if not size: return None
    L = size // 3 // 4
    out = []
    for c in range(3):
        words = struct.unpack_from('<%dI' % L, d, off + c * L * 4)
        out.append([bool(words[i // 32] >> (i % 32) & 1) for i in range(n)])
    return out

# sizes = (static flags size, animated flags size, movement data size, pill offset size, static codec size,
# unknown size, animated codec size) as the jmad animation struct stores them (graph()). Per node and channel, a
# static flag bit means "one value for the whole animation", an animated flag bit means "keyed", neither means the
# default. Movement data is F rows of 2 (dx dy), 3 (dx dy dyaw) or 4 (dx dy dz dyaw) floats. Scale is returned as a
# 3-tuple so the frames drop straight into write_iqm.
def decode(data, sizes, F, N, defaults):
    """-> frames[F][N] of (t, q xyzw, s), movement (F,4) dx dy dz dyaw.  defaults: [(t, q)] per node"""
    sflag, aflag, move, pill, ssize, usize, csize = sizes
    st = read_codec(data, 0, F) if ssize else None
    an = read_codec(data, ssize, F)
    flag_off = ssize + csize + usize
    sb = bits(data, flag_off, sflag, N); ab = bits(data, flag_off + sflag, aflag, N)
    lerp = lambda a, b, t: a + (b - a) * t
    out = [[None] * N for _ in range(F)]
    comps = []
    for ci, (sv, av, ak, interp) in enumerate(((st.rot if st else [], an.rot, an.rk, slerp), (st.tr if st else [], an.tr, an.tk, lerp),
                                                 (st.sc if st else [], an.sc, an.sk, lerp))):
        res = [[None] * N for _ in range(F)]
        si = ai = 0
        for n in range(N):
            if sb and sb[ci][n]:
                v = sv[si][0]; si += 1
                for f in range(F): res[f][n] = v
            elif ab and ab[ci][n]:
                for f in range(F): res[f][n] = sample(ak[ai], av[ai], f, interp)
                ai += 1
            else:
                dv = defaults[n][1] if ci == 0 else (defaults[n][0] if ci == 1 else 1.0)
                for f in range(F): res[f][n] = dv
        comps.append(res)
    mv = np.zeros((F, 4))
    mo = flag_off + sflag + aflag
    if move:
        per = move // max(1, F) // 4
        for f in range(F):
            v = struct.unpack_from('<%df' % per, data, mo + f * per * 4)
            if per == 2: mv[f, :2] = v
            elif per == 3: mv[f, 0], mv[f, 1], mv[f, 3] = v
            elif per == 4: mv[f, 0], mv[f, 1], mv[f, 2], mv[f, 3] = v
    frames = [[(tuple(comps[1][f][n]), tuple(comps[0][f][n]), (comps[2][f][n],) * 3) for n in range(N)] for f in range(F)]
    return frames, mv

# Returns (skeleton node names in graph order, animations). Animation entries are 0x60 bytes at jmad + 0x2C: name
# sid +0, type +0x10 (0 base, 1 overlay, 2 replacement), frame info type +0x11, blend screen +0x12, node count +0x13,
# frame count +0x14, loop frame +0x20, data (size, pointer) +0x28, sizes +0x30 (see decode). Node names are at +0xC
# (0x20 bytes each). The frames themselves are not decoded here: call decode() on data / sizes.
def graph(m, name):
    """animations of a jmad tag: list of dict(name, type, frame_info, nodes, frames, loop, data, sizes)"""
    a = m.tag('jmad', name)['addr']
    skel = [m.sid(m.u('I', n)[0]) for n in m.block(a + 0xC, 0x20)]
    anims = []
    for e in m.block(a + 0x2C, 0x60):
        nm = m.sid(m.u('I', e)[0])
        typ, fit, bsi, nc = m.b[m.o(e + 0x10)], m.b[m.o(e + 0x11)], m.b[m.o(e + 0x12)], m.b[m.o(e + 0x13)]
        fc = m.u('h', e + 0x14)[0]; loop = m.u('h', e + 0x20)[0]
        dsz, dptr = m.u('II', e + 0x28)
        sizes = struct.unpack_from('<BBhhhii', m.b, m.o(e + 0x30))
        data = m.b[m.o(dptr):m.o(dptr) + dsz]
        anims.append(dict(name=nm, type=typ, frame_info=fit, nodes=nc, frames=fc, loop=loop, data=data, sizes=sizes))
    return skel, anims
