"""Xbox Halo bitmap -> PIL image."""
import struct, io
import numpy as np
from PIL import Image

FMT = {0: 'A8', 1: 'Y8', 2: 'AY8', 3: 'A8Y8', 6: 'R5G6B5', 8: 'A1R5G5B5', 9: 'A4R4G4B4',
       10: 'X8R8G8B8', 11: 'A8R8G8B8', 14: 'DXT1', 15: 'DXT3', 16: 'DXT5', 17: 'P8'}
BPP = {'A8': 1, 'Y8': 1, 'AY8': 1, 'A8Y8': 2, 'R5G6B5': 2, 'A1R5G5B5': 2, 'A4R4G4B4': 2,
       'X8R8G8B8': 4, 'A8R8G8B8': 4, 'P8': 1}

def _dds(w, h, fourcc, data):
    hdr = struct.pack('<4sIIIIIII44sIIII20sIIII', b'DDS ', 124, 0x1007 | 0x80000, h, w,
                      len(data), 0, 1, b'\0' * 44, 32, 4, 0, 0, b'\0' * 20, 0x1000, 0, 0, 0)
    hdr = hdr[:84] + fourcc + hdr[88:]
    return Image.open(io.BytesIO(hdr + data))

def _morton_index(w, h):
    """index array mapping linear (y,x) -> swizzled offset for Xbox (square/rect)."""
    def bits(n):
        return max(1, n).bit_length() - 1
    bw, bh = bits(w), bits(h)
    xs = np.arange(w); ys = np.arange(h)
    ox = np.zeros(w, dtype=np.int64); oy = np.zeros(h, dtype=np.int64)
    shift = 0; bx = by = 0
    while bx < bw or by < bh:
        if bx < bw:
            ox |= ((xs >> bx) & 1) << shift; shift += 1; bx += 1
        if by < bh:
            oy |= ((ys >> by) & 1) << shift; shift += 1; by += 1
    return oy[:, None] | ox[None, :]

def decode(d, off, w, h, fmt, flags):
    name = FMT.get(fmt)
    if name is None:
        return None
    if name.startswith('DXT'):
        bs = 8 if name == 'DXT1' else 16
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * bs
        img = _dds(w, h, name.encode(), bytes(d[off:off + size]))
        img.load()
        return img.convert('RGBA')
    bpp = BPP[name]
    raw = np.frombuffer(d, dtype=np.uint8, count=w * h * bpp, offset=off)
    if flags & 0x8:  # swizzled
        idx = _morton_index(w, h)
        px = raw.reshape(-1, bpp)[idx.ravel()]
    else:
        px = raw.reshape(-1, bpp)
    if bpp == 4:
        b, g, r, a = px[:, 0], px[:, 1], px[:, 2], px[:, 3]
        if name == 'X8R8G8B8': a = np.full_like(a, 255)
        rgba = np.stack([r, g, b, a], 1)
    elif bpp == 2:
        v = px[:, 0].astype(np.uint16) | (px[:, 1].astype(np.uint16) << 8)
        if name == 'R5G6B5':
            r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31
            rgba = np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31, np.full_like(r, 255)], 1)
        elif name == 'A1R5G5B5':
            a = (v >> 15) * 255; r = (v >> 10) & 31; g = (v >> 5) & 31; b = v & 31
            rgba = np.stack([r * 255 // 31, g * 255 // 31, b * 255 // 31, a], 1)
        elif name == 'A4R4G4B4':
            rgba = np.stack([((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, (v >> 12) * 17], 1)
        else:  # A8Y8
            y = px[:, 0]; a = px[:, 1]
            rgba = np.stack([y, y, y, a], 1)
    else:
        v = px[:, 0]
        if name == 'A8': rgba = np.stack([np.full_like(v, 255)] * 3 + [v], 1)
        elif name == 'P8': rgba = np.stack([v, v, v, np.full_like(v, 255)], 1)
        else: rgba = np.stack([v, v, v, np.full_like(v, 255)], 1)
    return Image.fromarray(rgba.astype(np.uint8).reshape(h, w, 4), 'RGBA')

def bitmap_image(m, tag_id, index=0):
    t = m.byid.get(tag_id)
    if not t or t['cls'] != 'bitm': return None
    c, p = m.reflexive(t['data'] + 0x60)
    if index >= c: return None
    sig, w, h, dep, typ, fmt, fl, rx, ry, mips, pad, poff, psz, tid, cb, hw, ba = \
        m.u('4s6h2h2hiiiiII', p + index * 0x30)
    if typ != 0:  # only 2D textures
        return None
    try:
        return decode(m.d, poff, w, h, fmt, fl)
    except Exception:
        return None
