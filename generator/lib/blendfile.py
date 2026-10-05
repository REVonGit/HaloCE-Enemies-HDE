"""Minimal .blend reader (SDNA-driven), enough to pull meshes, vertex groups, materials and objects out of a
Blender 4.x / 5.x file without Blender. Supports the old 12-byte header (BLENDER-v / _v) and the 5.0 'BLENDER17-01'
header with 32-byte block headers.
"""
import struct, zlib
import numpy as np


class Block:
    __slots__ = ('code', 'sdna', 'old', 'size', 'count', 'off', 'owner')
    def __init__(s, code, sdna, old, size, count, off):
        s.code, s.sdna, s.old, s.size, s.count, s.off = code, sdna, old, size, count, off


class Blend:
    def __init__(s, path):
        d = open(path, 'rb').read()
        if d[:2] == b'\x1f\x8b': d = zlib.decompress(d, 16 + 15)
        if d[:4] == b'\x28\xb5\x2f\xfd':
            import zstandard; d = zstandard.ZstdDecompressor().decompressobj().decompress(d)
        s.d = d
        if d[7:9] == b'17':                      # BLENDER17-01v0500
            s.ptr = 8; s.le = True; pos = 17; s.large = True
        else:
            s.ptr = 8 if d[7:8] == b'-' else 4; s.le = d[8:9] == b'v'; pos = 12; s.large = False
        s.e = '<' if s.le else '>'
        s.blocks = []; s.by_old = {}; s.ctx = None; owner = -1
        while pos < len(d):
            if s.large:
                code, sdna, old, size, count = struct.unpack_from(s.e + '4siQqq', d, pos); hl = 32
            else:
                code, size, old, sdna, count = struct.unpack_from(s.e + '4siQii', d, pos); hl = 24
            b = Block(code.rstrip(b'\0').decode('latin1'), sdna, old, size, count, pos + hl)
            pos += hl + size
            if b.code == 'ENDB': break
            if b.code != 'DATA': owner = len(s.blocks)
            b.owner = owner
            s.blocks.append(b)
            if b.code == 'DNA1': s._dna(b)
            s.by_old.setdefault(old, []).append(b)
        s.struct_by_name = {s.types[t]: i for i, (t, _) in enumerate(s.structs)}

    def _dna(s, b):
        d = s.d; p = b.off + 4
        def align(p): return b.off + ((p - b.off + 3) & ~3)
        assert d[p:p + 4] == b'NAME'; p += 4; n = struct.unpack_from(s.e + 'i', d, p)[0]; p += 4
        names = []
        for _ in range(n):
            q = d.index(b'\0', p); names.append(d[p:q].decode('latin1')); p = q + 1
        p = align(p); assert d[p:p + 4] == b'TYPE'; p += 4; n = struct.unpack_from(s.e + 'i', d, p)[0]; p += 4
        types = []
        for _ in range(n):
            q = d.index(b'\0', p); types.append(d[p:q].decode('latin1')); p = q + 1
        p = align(p); assert d[p:p + 4] == b'TLEN'; p += 4
        tlen = list(struct.unpack_from(s.e + f'{n}h', d, p)); p = align(p + 2 * n)
        assert d[p:p + 4] == b'STRC'; p += 4; n = struct.unpack_from(s.e + 'i', d, p)[0]; p += 4
        structs = []
        for _ in range(n):
            t, nf = struct.unpack_from(s.e + 'hh', d, p); p += 4
            f = []
            for _ in range(nf):
                ft, fn = struct.unpack_from(s.e + 'hh', d, p); p += 4; f.append((ft, fn))
            structs.append((t, f))
        s.names, s.types, s.tlen, s.structs = names, types, tlen, structs
        # tlen may be clipped for big structs (> 32767): recompute from fields
        s.layout = {}

    def _field_size(s, ft, fname):
        if fname.startswith('*') or fname.startswith('(*'): base = s.ptr
        else: base = s.tlen[ft] if s.tlen[ft] >= 0 else s.tlen[ft] + 65536
        n = 1
        for part in fname.split('[')[1:]: n *= int(part.split(']')[0])
        return base * n

    def fields(s, sname):
        """{field name (no * / []): (offset, type name, raw name, size)}"""
        if sname in s.layout: return s.layout[sname]
        t, f = s.structs[s.struct_by_name[sname]]
        out = {}; off = 0
        for ft, fn in f:
            raw = s.names[fn]; sz = s._field_size(ft, raw)
            key = raw.replace('*', '').replace('(', '').replace(')', '').split('[')[0]
            out[key] = (off, s.types[ft], raw, sz); off += sz
        out['__size__'] = off
        s.layout[sname] = out
        return out

    def get(s, sname, base, field):
        off, tn, raw, sz = s.fields(sname)[field]
        p = base + off
        if raw.startswith('*') or raw.startswith('(*'): return struct.unpack_from(s.e + 'Q', s.d, p)[0]
        fmt = {'char': 'b', 'uchar': 'B', 'short': 'h', 'ushort': 'H', 'int': 'i', 'uint': 'I', 'float': 'f', 'double': 'd',
               'int64_t': 'q', 'uint64_t': 'Q', 'int8_t': 'b', 'uint8_t': 'B', 'int16_t': 'h', 'uint16_t': 'H',
               'int32_t': 'i', 'uint32_t': 'I'}.get(tn)
        if '[' in raw:
            if tn == 'char': return s.d[p:p + sz].split(b'\0')[0].decode('latin1')
            if fmt: return struct.unpack_from(s.e + f'{sz // struct.calcsize(fmt)}{fmt}', s.d, p)
            return p
        if fmt: return struct.unpack_from(s.e + fmt, s.d, p)[0]
        return p                                   # embedded struct: its address

    def block(s, ptr, ctx=None):
        """the block a stored pointer points to; Blender 4.2+ keeps pointer ids unique only within one ID's data,
        so ambiguous ones resolve to the block owned by the same ID as ctx (default s.ctx)"""
        c = s.by_old.get(ptr)
        if not c: return None
        if len(c) == 1: return c[0]
        ctx = ctx or s.ctx
        if ctx is not None:
            for b in c:
                if b.owner == ctx.owner: return b
        return c[0]
    def stype(s, b): return s.types[s.structs[b.sdna][0]]
    def of_type(s, sname): return [b for b in s.blocks if b.size and s.stype(b) == sname]
    def id_name(s, b): return s.get('ID', b.off, 'name')[2:]

    def listbase(s, base, sname):
        first = s.get('ListBase', base, 'first'); out = []
        while first:
            b = s.block(first)
            if not b: break
            out.append(b); first = s.get(sname, b.off, 'next')
        return out

    def array(s, ptr, dtype, shape=None, ctx=None):
        b = s.block(ptr, ctx)
        if not b: return None
        a = np.frombuffer(s.d, dtype=dtype, count=b.size // np.dtype(dtype).itemsize, offset=b.off)
        return a.reshape(shape) if shape else a
