"""Loose Halo CE .bitmap tag -> PIL image (PC tags: linear, DXT / 32-bit raw little-endian pixel data)."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from loosewalk import LooseTag
from bitmaps import decode          # lib/bitmaps.py

CH = {('bitmap_group', 'sequences'): 'bitmap_group_sequence', ('bitmap_group_sequence', 'sprites'): 'bitmap_group_sprite',
      ('bitmap_group', 'bitmaps'): 'bitmap_data'}

def load(path, index=0):
    t = LooseTag(path, 'bitmap_group', CH)
    r = t.root[1]
    po, psz = r['pixel_data']
    bo, _ = r['bitmaps'][index]
    w, h = t.get('bitmap_data', bo, 'width'), t.get('bitmap_data', bo, 'height')
    fmt, fl = t.get('bitmap_data', bo, 'format'), t.get('bitmap_data', bo, 'flags')
    off = t.get('bitmap_data', bo, 'pixels_offset')
    return decode(t.d, po + off, w, h, fmt, fl & ~0x8)
