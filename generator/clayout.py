"""Minimal i386 C struct layout calculator for the Halo decomp headers."""
import re, os, glob

from hce_paths import HALO_SRC as SRC

PRIM = {  # name: (size, align)
    'char': (1, 1), 'byte': (1, 1), 'boolean': (1, 1), 'byte_flags': (1, 1), 'signed char': (1, 1),
    'unsigned char': (1, 1), 'short': (2, 2), 'word': (2, 2), 'unsigned short': (2, 2), 'word_flags': (2, 2),
    'short_enum': (2, 2), 'long': (4, 4), 'int': (4, 4), 'unsigned int': (4, 4), 'unsigned long': (4, 4),
    'dword': (4, 4), 'long_flags': (4, 4), 'real': (4, 4), 'float': (4, 4), 'long_enum': (4, 4),
    'real_fraction': (4, 4), 'angle': (4, 4), 'tag': (4, 4), 'datum_index': (4, 4), 'string_id': (4, 4),
    'real_point3d': (12, 4), 'real_vector3d': (12, 4), 'real_point2d': (8, 4), 'real_vector2d': (8, 4),
    'real_quaternion': (16, 4), 'real_euler_angles2d': (8, 4), 'real_euler_angles3d': (12, 4),
    'real_rgb_color': (12, 4), 'real_argb_color': (16, 4), 'real_plane3d': (16, 4), 'real_plane2d': (12, 4),
    'real_rectangle2d': (16, 4), 'real_rectangle3d': (24, 4), 'real_bounds': (8, 4), 'short_bounds': (4, 2),
    'angle_bounds': (8, 4), 'real_fraction_bounds': (8, 4), 'point2d': (4, 2), 'rectangle2d': (8, 2),
    'rgb_color': (4, 4), 'argb_color': (4, 4), 'real_matrix4x3': (52, 4), 'real_matrix3x3': (36, 4),
    'byte_rectangle3d': (6, 1), 'real_orientation': (32, 4), 'real_hsv_color': (12, 4), 'real_ahsv_color': (16, 4),
}

class Layout:
    def __init__(s):
        s.structs = {}
        files = glob.glob(SRC + '/**/*.h', recursive=True) + glob.glob(SRC + '/**/*.c', recursive=True)
        for f in files:
            try:
                txt = open(f, errors='ignore').read()
            except Exception:
                continue
            txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
            txt = re.sub(r'//[^\n]*', '', txt)
            for m in re.finditer(r'(?:typedef\s+)?(struct|union)\s+(\w+)\s*\{(.*?)\}\s*(\w*)\s*;', txt, re.S):
                kind, name, body, alias = m.groups()
                if '{' in body:  # nested definitions: skip (rare)
                    continue
                s.structs.setdefault(name, (kind, body))
                if alias and alias != name:
                    s.structs.setdefault(alias, (kind, body))
        s.cache = {}
        s.consts = {}
        for f in files:
            txt = open(f, errors='ignore').read()
            for m in re.finditer(r'\b([A-Z][A-Z0-9_]+)\s*=\s*([0-9]+)\s*,', txt):
                s.consts.setdefault(m.group(1), int(m.group(2)))
            for m in re.finditer(r'#define\s+([A-Z][A-Z0-9_]+)\s+\(?([0-9]+)\)?\s*$', txt, re.M):
                s.consts.setdefault(m.group(1), int(m.group(2)))
            for em in re.finditer(r'\benum\s*\w*\s*\{(.*?)\}', re.sub(r'/\*.*?\*/|//[^\n]*', '', txt, flags=re.S), re.S):
                val = -1
                for item in em.group(1).split(','):
                    item = item.strip()
                    if not item: continue
                    mm = re.match(r'(\w+)\s*(?:=\s*(.+))?$', item, re.S)
                    if not mm: break
                    if mm.group(2) is not None:
                        try: val = int(eval(mm.group(2).strip(), {}, {}))
                        except Exception:
                            try: val = s.eval_dim(mm.group(2))
                            except Exception: break
                    else:
                        val += 1
                    s.consts.setdefault(mm.group(1), val)

    def eval_dim(s, e):
        e = e.strip()
        for k in sorted(s.consts, key=len, reverse=True):
            if k in e:
                e = re.sub(r'\b' + k + r'\b', str(s.consts[k]), e)
        return int(eval(e))

    def type_info(s, t):
        t = t.strip()
        t = re.sub(r'\bconst\b', '', t).strip()
        if t.endswith('*'):
            return 4, 4
        t = re.sub(r'^(struct|union)\s+', '', t)
        if t in ('tag_block',):
            return 12, 4
        if t in ('tag_reference',):
            return 16, 4
        if t in ('tag_data',):
            return 20, 4
        if t in PRIM:
            return PRIM[t]
        if t in s.structs:
            L = s.layout(t)
            return L['size'], L['align']
        raise KeyError('unknown type ' + t)

    def layout(s, name):
        if name in s.cache:
            return s.cache[name]
        kind, body = s.structs[name]
        off = 0; align = 1; fields = {}; size = 0
        for decl in body.split(';'):
            decl = ' '.join(decl.split())
            if not decl:
                continue
            m = re.match(r'(.*?)(\*?)\s*(\w+)\s*((?:\[[^\]]+\])*)$', decl)
            if not m:
                raise ValueError('cannot parse ' + decl)
            t, ptr, fname, dims = m.groups()
            if ':' in decl:
                raise ValueError('bitfield ' + decl)
            t = (t + ptr).strip()
            sz, al = s.type_info(t)
            n = 1
            for d in re.findall(r'\[([^\]]+)\]', dims):
                n *= s.eval_dim(d)
            if kind == 'struct':
                off = (off + al - 1) // al * al
                fields[fname] = (off, t, n)
                off += sz * n
            else:
                fields[fname] = (0, t, n)
                size = max(size, sz * n)
            align = max(align, al)
        if kind == 'struct':
            size = (off + align - 1) // align * align
        else:
            size = (size + align - 1) // align * align
        L = dict(size=size, align=align, fields=fields)
        s.cache[name] = L
        return L

    def offset(s, name, path):
        """path like 'ranged_combat.maximum_firing_range'"""
        off = 0; cur = name
        for part in path.split('.'):
            L = s.layout(cur)
            o, t, n = L['fields'][part]
            off += o
            cur = re.sub(r'^(struct|union)\s+', '', t.strip())
        return off

if __name__ == '__main__':
    L = Layout()
    for st in ['actor_definition', 'actor_variant_definition', 'animation', 'model_geometry_part']:
        try:
            print(st, hex(L.layout(st)['size']))
        except Exception as e:
            print(st, 'ERR', e)
