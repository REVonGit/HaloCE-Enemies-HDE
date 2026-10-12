"""The XAM Campaign Overhaul's Flood skins on the Halo CE Flood combat forms.

    HCE_XAM_C40=/path/to/c40_1.map HCE_SPV3_BITMAPS=/path/to/bitmaps.map python3 xam_flood.py

Run after extract_chars.py and before gore_kit.py. The XAM Campaign Overhaul (Tropical Thunder 98; SPV3's c40_1.map)
keeps Halo CE's Flood combat form meshes and UV layouts but repaints them: the human form in a raw, reddish
flesh ('characters\\zombie human' bitmaps), the Elite form in purple, each with its damaged (torn-stump) texture to
match. The pixels live in SPV3's shared bitmaps.map (pieces .015 and .016 of the split copy); the level map only
holds their headers. They replace the extracted Halo CE images of the base and damaged materials (<Char>_0 and
<Char>_1), at TEX pixels. Without the map or bitmaps.map the Halo CE skins stay.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys
from PIL import Image
from extract_chars import OUT

XAM_C40 = os.environ.get('HCE_XAM_C40', 'c40_1.map')   # SPV3's c40_1.map (the XAM Campaign Overhaul's c40)
TEX = 1024
# material -> XAM bitmap (the shaders XAM's c40 floodcombat models use)
SKINS = {
    'FloodHuman_0': r'characters\zombie human\bitmaps\floodhuman',
    'FloodHuman_1': r'characters\zombie human\bitmaps\floodhuman_damaged',
    'FloodElite_0': r'characters\floodcombat elite\bitmaps\floodcombat elite',
    'FloodElite_1': r'characters\floodcombat elite\bitmaps\floodcombat elite_damaged',
}


def xam_image(m, name):
    """an XAM bitmap's pixels (from bitmaps.map), or None"""
    from bitmaps import decode
    from gore_kit import _bitmaps_read
    t = next((t for t in m.tags if t['cls'] == 'bitm' and t['name'] == name), None)
    if t is None: return None
    c, p = m.reflexive(t['data'] + 0x60)
    _, w, h, _, _, fmt, fl, _, _, _, _, poff, psz = m.u('4s6h2h2hiii', p)[:13]
    try: return decode(_bitmaps_read(poff, psz), 0, w, h, fmt, fl)
    except (OSError, EOFError): return None


def main():
    if not os.path.exists(XAM_C40): print('xam_flood: no', XAM_C40, '(Halo CE skins kept)'); return
    from pcmap import PCMap
    m = PCMap(XAM_C40)
    for mat, bmp in SKINS.items():
        char = mat.rsplit('_', 1)[0]
        dst = f'{OUT}/models/{char}/{mat}.png'
        if not os.path.exists(dst): print('xam_flood: no', dst); continue
        im = xam_image(m, bmp)
        if im is None: print('xam_flood:', bmp, 'not in bitmaps.map (Halo CE skin kept)'); continue
        im.convert('RGB').resize((TEX, TEX), Image.LANCZOS).save(dst)
        print(f'{mat}: XAM {bmp.split(chr(92))[-1]} ({im.size[0]} px) -> {TEX} px')


if __name__ == '__main__':
    main()
