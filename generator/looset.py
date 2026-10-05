"""Read loose (source) Halo CE tag files with the same decomp layouts used for cache maps.

Tag files are big-endian: 64-byte header, then the main struct, then each field's child data in field
order (tag reference paths, data blobs, block elements).  Only the main struct is mapped here; tag
reference names are recovered by walking the trailing strings in order.  Blocks are left unresolved
(count only), which is enough for the actor/variant/biped/collision stats the pack uses."""
import struct, re
from tags import LAYOUT, FMT, VEC

GROUPS = {'actv': 'actor_variant_definition', 'actr': 'actor_definition', 'bipd': 'biped_definition',
          'coll': 'collision_model', 'weap': 'weapon_definition'}

class LooseMap:
    def __init__(s):
        s.d = b''; s.tags = []; s.byid = {}
    def u(s, fmt, a):
        return struct.unpack_from('>' + fmt, s.d, a)
    def find(s, cls): return [t for t in s.tags if t['cls'] == cls]

    def _tagrefs(s, st, base, out):
        L = LAYOUT.layout(st)
        for fn, (o, t, n) in sorted(L['fields'].items(), key=lambda x: x[1][0]):
            t = re.sub(r'^(struct|union)\s+', '', t.strip())
            if t == 'tag_reference':
                out.append(base + o)
            elif t in LAYOUT.structs and t not in ('tag_block', 'tag_data') and n == 1:
                s._tagrefs(t, base + o, out)

    def load(s, path, name):
        raw = open(path, 'rb').read()
        grp = raw[0x24:0x28].decode('latin1')
        st = GROUPS[grp]
        base = len(s.d) + 0x100
        s.d += b'\0' * (base - len(s.d)) + raw
        d = bytearray(s.d)
        size = LAYOUT.layout(st)['size']
        refs = []
        s._tagrefs(st, base + 64, refs)
        cur = base + 64 + size
        for a in refs:
            cls = d[a:a + 4].decode('latin1', 'replace')
            ln = struct.unpack_from('>i', d, a + 8)[0]
            tid = 0xFFFFFFFF
            if 0 < ln < 256:
                # next NUL-terminated printable string of exactly this length
                m = re.compile(rb'[\x20-\x7e]{%d}\x00' % ln).search(bytes(d), cur)
                if m:
                    nm = m.group(0)[:-1].decode('latin1')
                    cur = m.end()
                    tid = 0x10000 + len(s.byid)
                    s.byid[tid] = dict(cls=cls, id=tid, name=nm, data=None)
            struct.pack_into('>I', d, a + 12, tid)
        s.d = bytes(d)
        t = dict(cls=grp, id=0x80000 + len(s.tags), name=name, data=base + 64)
        s.tags.append(t)
        return t
