"""Halo 2 MCC cache reader (version 13, chunk-compressed): decompress, tag index, names, blocks, raw."""
import struct, zlib, os, json
import numpy as np

class H2Map:
    def __init__(s, path, cache=None):
        d = open(path, 'rb').read()
        s.hdr = d[:0x380]
        cache = cache or path + '.dec'
        if os.path.exists(cache) and os.path.getsize(cache) == struct.unpack_from('<I', s.hdr, 8)[0] - 0x380:
            s.b = open(cache, 'rb').read()
        else:
            cnt = struct.unpack_from('<I', s.hdr, 0x314)[0]
            tab_off = struct.unpack_from('<I', s.hdr, 0x310)[0]
            out = []
            for i in range(cnt):
                sz, off = struct.unpack_from('<iI', d, tab_off + i * 8)
                out.append(d[off + 2:off + 2 - sz] if sz < 0 else zlib.decompressobj(-15).decompress(d[off + 2:off + sz]))
            s.b = b''.join(out)
            try: open(cache, 'wb').write(s.b)
            except OSError: pass
        s.H = struct.unpack_from('<I', s.hdr, 0x10)[0] - 0x380          # tag index header == tag address base
        _, _, tptr, s.scen, s.glob, _, tcount = struct.unpack_from('<7I', s.b, s.H)
        names_off = struct.unpack_from('<I', s.hdr, 0x24)[0] - 0x380
        p = names_off; s.tags = []; s.byid = {}; s.by = {}
        for i in range(tcount):
            c, tid, a, sz = struct.unpack_from('<4sIII', s.b, s.H + tptr + i * 16)
            e = s.b.index(b'\0', p); n = s.b[p:e].decode('latin1'); p = e + 1
            t = dict(cls=c[::-1].decode('latin1'), id=tid, addr=a, size=sz, name=n)
            s.tags.append(t); s.byid[tid] = t; s.by[(t['cls'], n)] = t
        # string ids
        sc = struct.unpack_from('<I', s.hdr, 0x30)[0]
        so = struct.unpack_from('<I', s.hdr, 0x34)[0] - 0x380
        si = struct.unpack_from('<I', s.hdr, 0x3C)[0] - 0x380
        s.sid_off = [struct.unpack_from('<i', s.b, si + 4 * i)[0] for i in range(sc)]
        s.sid_data = so
    def o(s, addr): return s.H + addr
    def u(s, fmt, addr): return struct.unpack_from('<' + fmt, s.b, s.H + addr)
    def block(s, addr, size):
        c, p = s.u('II', addr)
        return [p + i * size for i in range(c)]
    def sid(s, v):
        i = v & 0xFFFFFF
        if v == 0 or i >= len(s.sid_off): return ''
        o = s.sid_data + s.sid_off[i]
        return s.b[o:s.b.index(b'\0', o)].decode('latin1')
    def raw(s, ptr, size):
        loc = ptr >> 30
        if loc: raise ValueError('raw data lives in a shared map (location %d)' % loc)
        o = (ptr & 0x3FFFFFFF) - 0x380
        return s.b[o:o + size]
    def tag(s, cls, name): return s.by[(cls, name)]

def sound_perms(m, name):
    """[(perm name, codec, channels, rate, bytes)] for a snd! tag, via the ugh! gestalt"""
    t = m.tag('snd!', name); a = t['addr']
    flags, cls_, rate, enc, codec, pb, pri = struct.unpack_from('<hBBBBhh', m.b, m.o(a))
    prc = m.b[m.o(a) + 10]
    g = [t for t in m.tags if t['cls'] == 'ugh!'][0]['addr']
    names = m.block(g + 16, 4); prs = m.block(g + 32, 12); perms = m.block(g + 40, 16); chunks = m.block(g + 64, 12)
    out = []
    for r in prs[pri:pri + prc] if pri >= 0 else []:
        nidx, _, _, _, first, cnt = m.u('6h', r)
        for i in range(cnt):
            p = perms[first + i]
            pn, _, _, _, _, ssz, bi, bc = struct.unpack_from('<hhBBhihh', m.b, m.o(p))
            data = b''
            for c in chunks[bi:bi + bc]:
                ptr, sz = m.u('II', c); data += m.raw(ptr, sz & 0xFFFFFF)
            out.append((m.sid(m.u('I', names[pn])[0]), codec, enc, {0: 22050, 1: 44100, 2: 32000}.get(rate, 22050), data))
    return out

def strip_to_tris(idx):
    t = []
    for k in range(len(idx) - 2):
        a, b, c = int(idx[k]), int(idx[k + 1]), int(idx[k + 2])
        if a == b or b == c or a == c: continue
        t.append((a, b, c) if k % 2 == 0 else (b, a, c))
    return np.array(t, np.int32).reshape(-1, 3)

def render_model(m, name):
    """nodes, sections (decoded), shaders, regions of an H2 mode tag"""
    a = m.tag('mode', name)['addr']
    nodes = []
    for n in m.block(a + 0x48, 0x60):
        nodes.append(dict(name=m.sid(m.u('I', n)[0]), parent=m.u('h', n + 4)[0],
                          t=list(m.u('3f', n + 0xC)), q=list(m.u('4f', n + 0x18))))
    shaders = []
    for s in m.block(a + 0x60, 0x20):
        cls, tid = m.u('4sI', s + 8)
        shaders.append(m.byid[tid]['name'] if tid in m.byid else None)
    regions = []
    for r in m.block(a + 0x1C, 0x10):
        perms = [dict(name=m.sid(m.u('I', p)[0]), lods=list(m.u('6h', p + 4))) for p in m.block(r + 8, 0x10)]
        regions.append(dict(name=m.sid(m.u('I', r)[0]), perms=perms))
    sections = []
    for s in m.block(a + 0x24, 0x5C):
        cls = m.u('h', s)[0]; vc, tc = m.u('HH', s + 4); npv = m.b[m.o(s + 0x14)]
        ptr, dsize, hsize, rsize = m.u('IIII', s + 0x38)
        res = [m.u('hhhhII', r) for r in m.block(s + 0x48, 0x10)]
        raw = m.raw(ptr, dsize)
        base = dsize - rsize - 4
        info_idx = struct.unpack_from('<H', raw, 40)[0]
        R = lambda t0, t1=None: next((r for r in res if r[2] == t0 and (t1 is None or r[3] == t1)), None)
        sub = res[0]
        parts = []
        for k in range(sub[4] // 72):
            q = base + sub[5] + k * 72
            parts.append(dict(shader=struct.unpack_from('<h', raw, q + 4)[0], start=struct.unpack_from('<H', raw, q + 6)[0],
                              count=struct.unpack_from('<H', raw, q + 8)[0]))
        ir = R(32); idx = np.frombuffer(raw, '<u2', info_idx, base + ir[5])
        vr = R(56, 0); vsz = vr[4] // vc
        V = np.frombuffer(raw, np.uint8, vc * vsz, base + vr[5]).reshape(vc, vsz)
        pos = V[:, :12].copy().view('<f4').reshape(-1, 3).astype(np.float64)
        ur = R(56, 1); uv = np.frombuffer(raw, '<f4', vc * 2, base + ur[5]).reshape(-1, 2).astype(np.float64)
        nr = R(56, 2); nrm = np.frombuffer(raw, '<f4', vc * 9, base + nr[5]).reshape(-1, 9)[:, :3].astype(np.float64)
        nmr = R(104); nmap = list(raw[base + nmr[5]: base + nmr[5] + nmr[4]]) if nmr else []
        if cls == 3 or (cls == 2 and vsz >= 20):
            bi = V[:, 12:16].astype(np.int32); bw = V[:, 16:20].astype(np.float64) / 255.0
        elif vsz >= 13:
            bi = np.zeros((vc, 4), np.int32); bi[:, 0] = V[:, 12]; bw = np.zeros((vc, 4)); bw[:, 0] = 1
        else:
            bi = np.zeros((vc, 4), np.int32); bw = np.zeros((vc, 4)); bw[:, 0] = 1
        if nmap:
            nm = np.array(nmap + [0] * 256)
            bi = nm[np.clip(bi, 0, 255)]
        tris_all = []
        for p in parts:
            seg = idx[p['start']:p['start'] + p['count']]
            tl = strip_to_tris(seg) if len(idx) != tc * 3 else seg.reshape(-1, 3).astype(np.int32)
            tris_all.append((p['shader'], tl))
        cb = m.block(s + 0x1C, 0x38) or m.block(a + 0x14, 0x38)
        if cb:
            bx = m.u('14f', cb[0])
            lo = np.array([bx[0], bx[2], bx[4]]); hi = np.array([bx[1], bx[3], bx[5]])
            pos = lo + (pos + 1) * 0.5 * (hi - lo)
            ulo = np.array([bx[6], bx[8]]); uhi = np.array([bx[7], bx[9]])
            uv = ulo + (uv + 1) * 0.5 * (uhi - ulo)
        sections.append(dict(cls=cls, vc=vc, tc=tc, npv=npv, vsz=vsz, pos=pos, uv=uv, nrm=nrm, bi=bi, bw=bw,
                             parts=tris_all, nmap=nmap))
    return dict(nodes=nodes, shaders=shaders, regions=regions, sections=sections)

def sound_chunks(m, name):
    """[(perm name, codec(rate, enc, comp), [(bank, file offset, size, pcm bytes)])] for a snd! tag (MCC gestalt)"""
    g = [t for t in m.tags if t['cls'] == 'ugh!'][0]['addr']
    codecs = m.block(g, 3); names = m.block(g + 0x18, 4); prs = m.block(g + 0x28, 12)
    perms = m.block(g + 0x30, 16); banks = [m.block(c, 16) for c in m.block(g + 0x60, 8)]
    a = m.tag('snd!', name)['addr']
    ci = m.b[m.o(a) + 3]; pri = m.u('h', a + 8)[0]; prc = m.b[m.o(a) + 10]
    codec = tuple(m.b[m.o(codecs[ci]) + k] for k in range(3)) if 0 <= ci < len(codecs) else None
    out = []
    for r in (prs[pri:pri + prc] if pri >= 0 else []):
        first, cnt = m.u('hh', r + 8)
        for i in range(cnt):
            p = perms[first + i]
            pn = m.u('h', p)[0]
            locs = []
            for bi, l in enumerate(m.block(p + 8, 8)):
                ss, fc, cc = m.u('Ihh', l)
                if cc <= 0: continue
                locs.append((bi, [m.u('ihhii', banks[bi][k]) for k in range(fc, fc + cc)], ss))
            out.append((m.sid(m.u('I', names[pn])[0]), codec, locs))
    return out

def mcc_bitmap(m, name, texfile, index=0):
    """MCC Halo 2 bitmap -> PIL RGBA (top mip). Pixels live in textures.dat: int count, int[count] block sizes, then
    zlib blocks (negative size = stored)."""
    import zlib, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from bitmaps import decode
    e = m.block(m.tag('bitm', name)['addr'] + 0x44, 0xA8)[index]
    w, h = m.u('hh', e + 4); fmt = m.u('h', e + 0xC)[0]; off = m.u('I', e + 0x38)[0]
    with open(texfile, 'rb') as f:
        f.seek(off); cnt = struct.unpack('<i', f.read(4))[0]
        segs = struct.unpack('<%di' % cnt, f.read(4 * cnt)); out = b''
        for sz in segs:
            blk = f.read(abs(sz))
            out += blk if sz < 0 else zlib.decompressobj().decompress(blk)
    return decode(out, 0, w, h, fmt, 0)
