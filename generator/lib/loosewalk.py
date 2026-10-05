"""Generic sequential walker for loose (source) Halo CE tag files.

Tag files are big-endian: a 64-byte header, the root struct, then each struct's child data in field order
(block elements, then each element's own children; tag_data blobs; tag reference paths)."""
import struct, re
from tags import LAYOUT

PSEUDO = {'model_triangle': 6}     # element types the decomp headers don't spell out as structs

def fields(st):
    if st in PSEUDO: return PSEUDO[st], []
    L = LAYOUT.layout(st)
    out = []
    for fn, (o, t, n) in sorted(L['fields'].items(), key=lambda x: x[1][0]):
        out.append((fn, o, re.sub(r'^(struct|union)\s+', '', t.strip()), n))
    return L['size'], out

class LooseTag:
    def __init__(s, path, root, child):
        s.d = open(path, 'rb').read()
        s.group = s.d[0x24:0x28].decode('latin1')
        s.child = child
        size, _ = fields(root)
        s.cur = 64 + size
        s.root = (64, s.walk(root, 64))
        s.complete = s.cur == len(s.d)

    def u(s, f, o): return struct.unpack_from('>' + f, s.d, o)

    def walk(s, st, off):
        res = {}
        _, fl = fields(st)
        for fn, o, t, n in fl:
            if t == 'tag_reference':
                ln, = s.u('i', off + o + 8)
                if ln > 0:
                    res[fn] = s.d[s.cur:s.cur + ln].decode('latin1'); s.cur += ln + 1
            elif t == 'tag_data':
                sz, = s.u('i', off + o)
                res[fn] = (s.cur, sz); s.cur += sz
            elif t == 'tag_block':
                cnt, = s.u('i', off + o)
                if cnt <= 0: res[fn] = []; continue
                if cnt > 100000 or s.cur + cnt > len(s.d): raise ValueError(f'bad count {st}.{fn} {cnt}')
                et = s.child.get((st, fn))
                if et is None: raise ValueError(f'unknown block element {st}.{fn} ({cnt}) at {s.cur}')
                esz, _ = fields(et)
                base = s.cur; s.cur += cnt * esz
                if et in PSEUDO or not any(t2 in ('tag_block', 'tag_data', 'tag_reference') for _, _, t2, _ in fields(et)[1]):
                    res[fn] = [(base + i * esz, {}) for i in range(cnt)]
                else:
                    res[fn] = [(base + i * esz, s.walk(et, base + i * esz)) for i in range(cnt)]
            elif t in LAYOUT.structs and t not in ('tag_block', 'tag_data', 'tag_reference') and n == 1:
                sub = s.walk(t, off + o)
                if sub: res[fn] = sub
        return res

    def get(s, st, off, name):
        """scalar/vector field by name from the decomp layout"""
        L = LAYOUT.layout(st)['fields']
        o, t, n = L[name]
        t = re.sub(r'^(struct|union)\s+', '', t.strip())
        fmt = {'real': 'f', 'float': 'f', 'short': 'h', 'word': 'H', 'long': 'i', 'unsigned long': 'I', 'word_flags': 'H', 'unsigned short': 'H', 'unsigned long': 'I', 'unsigned int': 'I', 'int': 'i',
               'long_flags': 'I', 'short_enum': 'h', 'real_point3d': '3f', 'real_vector3d': '3f', 'real_quaternion': '4f',
               'real_point2d': '2f', 'char': 'b', 'byte': 'B', 'byte_flags': 'B'}.get(t)
        if fmt is None: raise KeyError(f'{st}.{name}: {t}')
        if n > 1 and len(fmt) == 1: fmt = f'{n}{fmt}'
        v = s.u(fmt, off + o)
        return v if len(v) > 1 else v[0]

    def cstr(s, off, n=32):
        return s.d[off:off + n].split(b'\0')[0].decode('latin1')
