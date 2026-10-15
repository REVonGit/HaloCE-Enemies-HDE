"""Named-field access to Halo cache-file tags using the decomp struct layouts.

    T = tag(m, m.find('bipd')[0], 'biped_definition')
    T['unit.object.bounding_radius']            # scalar by struct field name, wrapper structs may be skipped
    T['nodes_with_translation_flags[1]']        # array element
    for n in T.block('nodes', 'model_node'): ...  # tag_block elements as Tags

Struct names and field names are the ones in the Halo CE decomp headers (hce_paths.HALO_SRC), parsed by clayout.py.
Works on any map object with u()/byid (halomap.HMap, pcmap.PCMap, looset.LooseMap)."""
import sys, struct, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from halomap import HMap
from clayout import Layout

LAYOUT = Layout()   # one parse of the decomp headers, shared by every module that imports tags
# decomp scalar type name -> struct format char; a field of a type missing here comes back as a nested Tag.
# To read a new scalar type, add it here (and its size/alignment to clayout.PRIM if it isn't there).
FMT = {'real': 'f', 'float': 'f', 'short': 'h', 'word': 'H', 'long': 'i', 'unsigned long': 'I', 'int': 'i',
       'unsigned int': 'I', 'char': 'b', 'byte': 'B', 'unsigned short': 'H', 'boolean': 'B', 'signed char': 'b'}
# decomp vector type name -> struct format (returned as a tuple)
VEC = {'real_point3d': '3f', 'real_vector3d': '3f', 'real_point2d': '2f', 'real_vector2d': '2f',
       'real_quaternion': '4f', 'real_euler_angles2d': '2f', 'real_rgb_color': '3f', 'real_argb_color': '4f',
       'real_bounds': '2f', 'short_bounds': '2h', 'real_rectangle3d': '6f', 'point2d': '2h'}

class Tag:
    """view of struct `st` at virtual address `addr` in map m"""
    def __init__(s, m, st, addr):
        """m: map object; st: decomp struct name; addr: virtual address of the struct."""
        s.m, s.st, s.addr = m, st, addr
    def _resolve(s, path):
        """Dotted field path -> (byte offset from s.addr, decomp type name of the final field). A path part that is
        not a direct field is looked for one level down in the struct's single-member wrapper fields, so
        'bounding_radius' works on a biped_definition without spelling out unit.object."""
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
        """Read a field by dotted path. Scalars (FMT) come back as numbers, vectors (VEC) as tuples, a tag_reference
        as the referenced tag dict (or None), a tag_block as (count, element address), a tag_data as (size, address),
        anything else as a nested Tag."""
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
        """The elements of the tag_block at path as Tags of struct st (the element struct must be named; the
        headers don't record it)."""
        c, p = s[path]
        size = LAYOUT.layout(st)['size']
        return [Tag(s.m, st, p + i * size) for i in range(c)]

def tag(m, t, st):
    """Tag view of a tag-index entry t (dict from m.tags / m.byid) as decomp struct st."""
    return Tag(m, st, t['data'])
