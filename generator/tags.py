"""Named-field access to Halo cache-file tags using the decomp struct layouts."""
import sys, struct, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from halomap import HMap
from clayout import Layout

LAYOUT = Layout()
FMT = {'real': 'f', 'float': 'f', 'short': 'h', 'word': 'H', 'long': 'i', 'unsigned long': 'I', 'int': 'i',
       'unsigned int': 'I', 'char': 'b', 'byte': 'B', 'unsigned short': 'H', 'boolean': 'B', 'signed char': 'b'}
VEC = {'real_point3d': '3f', 'real_vector3d': '3f', 'real_point2d': '2f', 'real_vector2d': '2f',
       'real_quaternion': '4f', 'real_euler_angles2d': '2f', 'real_rgb_color': '3f', 'real_argb_color': '4f',
       'real_bounds': '2f', 'short_bounds': '2h', 'real_rectangle3d': '6f', 'point2d': '2h'}

class Tag:
    """view of struct `st` at virtual address `addr` in map m"""
    def __init__(s, m, st, addr):
        s.m, s.st, s.addr = m, st, addr
    def _resolve(s, path):
        off = 0; cur = s.st
        parts = path.split('.')
        for i, p in enumerate(parts):
            idx = 0
            mm = re.match(r'(\w+)\[(\d+)\]', p)
            if mm: p, idx = mm.group(1), int(mm.group(2))
            L = LAYOUT.layout(cur)
            if p not in L['fields']:
                # descend into single-member wrapper structs (object/unit/biped)
                found = None
                for fn, (o, t, n) in L['fields'].items():
                    tt = re.sub(r'^(struct|union)\s+', '', t.strip())
                    if tt in LAYOUT.structs and p in LAYOUT.layout(tt)['fields']:
                        found = (fn, o, tt); break
                if not found:
                    raise KeyError(f'{cur}.{p}')
                off += found[1]; cur = found[2]
                L = LAYOUT.layout(cur)
            o, t, n = L['fields'][p]
            t = re.sub(r'^(struct|union)\s+', '', t.strip())
            sz = LAYOUT.type_info(t)[0]
            off += o + idx * sz
            cur = t
        return off, cur
    def __getitem__(s, path):
        off, t = s._resolve(path)
        a = s.addr + off
        if t in FMT: return s.m.u(FMT[t], a)[0]
        if t in VEC: return s.m.u(VEC[t], a)
        if t == 'tag_reference':
            tid = s.m.u('I', a + 12)[0]
            return s.m.byid.get(tid)
        if t == 'tag_block':
            c, p = s.m.u('II', a)
            return (c, p)
        if t == 'tag_data':
            sz, _, fo, ad = s.m.u('iiiI', a)[:4]
            return (sz, ad)
        return Tag(s.m, t, a)
    def block(s, path, st):
        c, p = s[path]
        size = LAYOUT.layout(st)['size']
        return [Tag(s.m, st, p + i * size) for i in range(c)]

def tag(m, t, st):
    return Tag(m, st, t['data'])
