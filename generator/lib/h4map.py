"""Minimal Halo 4 MCC cache reader (v13, the Update 7 build of Apr 1 2023; layouts from Assembly's Formats/Halo4MCC):
the tag index and names, tag blocks and references, string ids, bitmap tags (bitmap_info) and their pixel data through
the resource gestalt (Resources: pages are raw deflate; a page in an external cache (shared.map, campaign.map) is read
from $H4_MAPS_DIR, whole or as numbered pieces: splitfile). Used by extract_h4_derez.py."""
import os, sys, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import splitfile

MAP = os.environ.get('HCE_H4_MAP', '/mnt/user-data/uploads/Halo The Master Chief Collection/Split/ff151_mezzanine.map')
EXPAND = 0x4FFF0000


def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def i32(b, o): return struct.unpack_from('<i', b, o)[0]
def u64(b, o): return struct.unpack_from('<Q', b, o)[0]
def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def i16(b, o): return struct.unpack_from('<h', b, o)[0]


class H4Map:
    def __init__(s, path=MAP):
        s.f = splitfile.open(path)
        h = s.h = s.read(0, 0x1E000)
        s.masks = [u32(h, 0x4C4 + 4 * i) for i in range(4)]
        s.sections = [(u32(h, 0x4D4 + 8 * i), u32(h, 0x4D8 + 8 * i)) for i in range(4)]
        s.vbase = u64(h, 0x2D8)
        s.index_addr = u64(h, 0x2E0)
        s.meta_off = (s.sections[2][0] + s.masks[2]) & 0xffffffff
        s.meta_size = u32(h, 0x14)
        s.meta = s.read(s.meta_off, s.meta_size)
        dbg = s.masks[0]
        # tag names
        n, off, size, idx = (i32(h, 0x20), u32(h, 0x24), u32(h, 0x28), u32(h, 0x2C))
        data = s.read((off + dbg) & 0xffffffff, size); ind = s.read((idx + dbg) & 0xffffffff, 4 * n)
        s.names = []
        for i in range(n):
            o = i32(ind, 4 * i)
            s.names.append(data[o:data.index(b'\0', o)].decode('latin1') if o >= 0 else None)
        # string ids
        n, off, size, idx = (i32(h, 0x30), u32(h, 0x34), u32(h, 0x38), u32(h, 0x3C))
        data = s.read((off + dbg) & 0xffffffff, size); ind = s.read((idx + dbg) & 0xffffffff, 4 * n)
        s.strings = []
        for i in range(n):
            o = i32(ind, 4 * i)
            s.strings.append(data[o:data.index(b'\0', o)].decode('latin1') if o >= 0 else None)
        s.ns_count = i32(h, 0x40); s.ns_off = u32(h, 0x44)
        s.namespaces = list(struct.unpack('<%di' % s.ns_count, s.read((s.ns_off + dbg) & 0xffffffff, 4 * s.ns_count))) if s.ns_count else []
        # index header
        ih = s.at(s.index_addr, 0x4C)
        ngroups, gaddr, ntags, taddr = i32(ih, 0), u64(ih, 8), i32(ih, 0x10), u64(ih, 0x18)
        nglob, glob = i32(ih, 0x20), u64(ih, 0x28)
        g = s.at(gaddr, 0x10 * ngroups)
        s.groups = []
        for i in range(ngroups):
            s.groups.append(g[16 * i:16 * i + 4][::-1].decode('latin1'))
        t = s.at(taddr, 8 * ntags)
        s.tags = []
        for i in range(ntags):
            gi, salt, addr = i16(t, 8 * i), u16(t, 8 * i + 2), u32(t, 8 * i + 4)
            s.tags.append(dict(index=i, group=s.groups[gi] if gi >= 0 else None, salt=salt, addr=addr,
                               name=s.names[i] if i < len(s.names) else None))
        gl = s.at(glob, 8 * nglob)
        s.globals = {gl[8 * i:8 * i + 4][::-1].decode('latin1'): u32(gl, 8 * i + 4) & 0xffff for i in range(nglob)}

    def read(s, off, n):
        s.f.seek(off); return s.f.read(n)

    def expand(s, p): return (p << 2) + EXPAND if p else 0

    def at(s, vaddr, n):
        o = vaddr - s.vbase
        return s.meta[o:o + n]

    def ptr(s, p, n):
        """bytes at a 32-bit compressed meta pointer"""
        return s.at(s.expand(p), n)

    def tagdata(s, t, n):
        if isinstance(t, int): t = s.tags[t & 0xffff]
        return s.ptr(t['addr'], n)

    def block(s, b, o, esize):
        """(count, list of element bytes) of a tag block at b[o]"""
        n, p = i32(b, o), u32(b, o + 4)
        if n <= 0 or not p: return []
        d = s.ptr(p, n * esize)
        return [d[i * esize:(i + 1) * esize] for i in range(n)]

    def sid(s, v):
        """resolve a string id: Assembly's H4 layout is index 17 bits / namespace 8 bits / length 7 (H4MCC uses
        the namespace table: overall index = sum(namespace sizes before ns) + local index, with ns 0 offset)"""
        if v == 0: return ''
        idx = v & 0x1FFFF; ns = (v >> 17) & 0xFF
        if s.namespaces:
            # Blamite: namespace 0 strings come after all others? compute like StringIDNamespaceResolver
            if ns == 0 and idx >= s.namespaces[0] if s.namespaces else False:
                base = sum(s.namespaces[1:])
                return s._sget(idx - s.namespaces[0] + base) if False else s._sget(idx + sum(s.namespaces[1:]) - s.namespaces[0] + s.namespaces[0])
            base = sum(s.namespaces[:ns])
            return s._sget(base + idx)
        return s._sget(idx)

    def _sget(s, i):
        return s.strings[i] if 0 <= i < len(s.strings) else '<sid %x>' % i

    def ref(s, b, o):
        """tag reference at b[o]: (group, tag index or None)"""
        g = b[o:o + 4][::-1].decode('latin1', 'replace'); d = u32(b, o + 0xC)
        return (g, None if d == 0xFFFFFFFF else d & 0xffff)

    def tname(s, i):
        t = s.tags[i]; return '%s.%s' % (t['name'], t['group'])


def bitmap_info(m, ti):
    d = m.tagdata(ti, 0xCC)
    out = dict(seqs=[], images=[], res=[], ilv=[])
    for e in m.block(d, 0x70, 0x40):
        name = e[:0x20].split(b'\0')[0].decode('latin1')
        sprites = [(i16(sp, 0),) + struct.unpack_from('<4f2f', sp, 8) for sp in m.block(e, 0x34, 0x20)]
        out['seqs'].append(dict(name=name, first=i16(e, 0x20), count=i16(e, 0x22), sprites=sprites))
    for e in m.block(d, 0x7C, 0x30):
        out['images'].append(dict(w=u16(e, 0), h=u16(e, 2), depth=e[4], fflags=e[5], type=e[6], fmt=u16(e, 8),
                                  flags=u16(e, 0xA), mips=e[0x10], ig=struct.unpack_from('b', e, 0x12)[0],
                                  im=struct.unpack_from('b', e, 0x13)[0], off=i32(e, 0x14), cnt=i32(e, 0x18), raw=e))
    out['res'] = [u32(e, 0) for e in m.block(d, 0xA8, 8)]
    out['stitch'] = [u32(e, 0) for e in m.block(d, 0xB4, 8)]
    out['ilv'] = [u32(e, 0) for e in m.block(d, 0xC0, 8)]
    return out


class Resources:
    def __init__(s, m):
        s.m = m
        z = m.tagdata(m.globals['zone'], 0x230)
        p = m.tagdata(m.globals['play'], 0x40)
        s.zone = z
        s.ext = [e[:0x100].split(b'\0')[0].decode('latin1') for e in m.block(p, 0xC, 0x108)]
        s.pages = []
        for e in m.block(p, 0x18, 0x58):
            s.pages.append(dict(salt=u16(e, 0), flags=e[2], codec=struct.unpack_from('b', e, 3)[0],
                                shared=i16(e, 4), off=i32(e, 8), csize=i32(e, 0xC), usize=i32(e, 0x10)))
        s.sizes = []
        for e in m.block(p, 0x24, 0x10):
            s.sizes.append(dict(total=i32(e, 0), parts=[(i32(q, 0), i32(q, 4)) for q in m.block(e, 4, 8)]))
        s.segs = []
        for e in m.block(p, 0x30, 0x18):
            s.segs.append(struct.unpack('<3i6h', e))
        s.res = m.block(z, 0x58, 0x44)
        s.info_size = i32(z, 0x154); s.info_addr = u32(z, 0x160)
        s.raw_off = (m.sections[1][0] + m.masks[1]) & 0xffffffff
        s._cache = {}

    def entry(s, datum):
        e = s.res[datum & 0xffff]
        return dict(group=e[:4][::-1].decode('latin1'), owner=u32(e, 0xC) & 0xffff, salt=u16(e, 0x10),
                    type=struct.unpack_from('b', e, 0x12)[0], flags=e[0x13], info_size=i32(e, 0x14),
                    bits=u16(e, 0x18), seg=i16(e, 0x1A), base_def=u32(e, 0x1C),
                    fixups=[(i32(q, 0), u32(q, 4)) for q in s.m.block(e, 0x20, 8)],
                    deffix=[(i32(q, 0), i32(q, 4)) for q in s.m.block(e, 0x2C, 8)],
                    info_offs=[i32(q, 0) for q in s.m.block(e, 0x38, 4)], raw=e)

    def page_data(s, pi):
        if pi in s._cache: return s._cache[pi]
        pg = s.pages[pi]
        if pg['shared'] != -1:
            f, roff = s._external(pg['shared'])
            if f is None:
                raise RuntimeError('page %d lives in external cache %r (raw-table offset %#x, %d bytes deflated)' %
                                   (pi, s.ext[pg['shared']], pg['off'], pg['csize']))
            f.seek(roff + pg['off']); raw = f.read(pg['csize'])
        else:
            raw = s.m.read(s.raw_off + pg['off'], pg['csize'])
        if pg['codec'] == -1:
            d = raw[:pg['usize']]
        else:
            d = zlib.decompress(raw, -15)
        s._cache[pi] = d
        return d

    def _external(s, k):
        """(file, resource-section file offset) of external cache k, looked for in $H4_MAPS_DIR (whole or split)"""
        import os
        if not hasattr(s, '_ext'): s._ext = {}
        if k not in s._ext:
            path = os.path.join(os.environ.get('H4_MAPS_DIR', os.path.dirname(MAP)), s.ext[k].split('\\')[-1])
            if os.path.exists(path): f = open(path, 'rb')
            elif splitfile.exists(path): f = splitfile.open(path)
            else: s._ext[k] = (None, 0); return s._ext[k]
            f.seek(0); h = f.read(0x600)
            s._ext[k] = (f, (u32(h, 0x4D4 + 8) + u32(h, 0x4C4 + 4)) & 0xffffffff)
        return s._ext[k]

    def segment(s, si):
        """(primary bytes or None, secondary bytes or None, (primary size entry, secondary size entry))"""
        if si < 0: return None, None, (-1, -1)
        po, so, to, pp, sp, tp, ps, ss, ts = s.segs[si]
        out = []
        for off, pg, sz in ((po, pp, ps), (so, sp, ss)):
            if pg == -1: out.append(None); continue
            d = s.page_data(pg)
            n = s.sizes[sz]['total'] if sz != -1 else len(d) - off
            out.append(d[off:off + n])
        return out[0], out[1], (ps, ss)
