"""The colour each Covenant material glows in -> $HCE_OUT/glow_colours.json

    python3 glow_colours.py        # after extract_chars.py (and the add-on extractors)

Halo CE's shader_model lights a texel by its multipurpose map's green channel in a colour of the shader's own, not the
texture's: 'self-illumination' color source (0x70: none, or one of the object's change colours A-D) and its animation
colour range (0x78 lower, 0x84 upper bound). build_pack.glow_maps paints that colour into the glowing texels and
brightmaps them, so the lights read as light given off rather than paint lit by a flashlight.
Our materials don't keep their shader's name, so each material is matched to its shader by its multipurpose map:
every soso shader in the Halo CE maps with a multipurpose map is decoded and compared with the material's
_multi.png (same image, same size). Materials with no match (the add-ons' own) are left out; build_pack falls back.
"""
import os, sys, json, glob
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))   # readers and writers live in lib/
try:
    from extract_chars import OUT, MAPS
except Exception:
    OUT = os.path.join(HERE, 'out'); MAPS = ['a10', 'a30', 'a50', 'b30', 'b40', 'c10', 'c20', 'c40', 'd20', 'd40']
CE_MAPS = os.environ.get('HCE_MAPS', os.path.join(HERE, 'maps'))
# the characters whose materials are matched (add a character here to give its lights their shader colour; it must
# have _multi.png maps under out/models/<Char>/ and its shaders must be in one of MAPS)
COVENANT = ('Elite', 'EliteSpecial', 'EliteRifle', 'EliteZealot', 'Grunt', 'GruntSpecOps', 'Jackal', 'JackalMajor', 'Hunter')


def main():
    """match every glowing COVENANT material to its Halo CE shader by multipurpose map and write glow_colours.json:
    material -> {shader, source (self-illumination colour source), lower, upper (its animation colour bounds)}"""
    from halomap import HMap
    from bitmaps import bitmap_image
    want = {}
    for ch in COVENANT:
        for f in sorted(glob.glob(f'{OUT}/models/{ch}/{ch}_*_multi.png')):
            g = np.asarray(Image.open(f).convert('RGBA'), np.float32)
            if g[..., 1].max() >= 0.3 * 255: want[os.path.basename(f)[:-10]] = g
    found = {}
    for mp in MAPS:
        path = f'{CE_MAPS}/{mp}.map'
        if not os.path.exists(path) or len(found) == len(want): continue
        m = HMap(path)
        for t in m.tags:
            if t['cls'] != 'soso': continue
            multi = m.u('I', t['data'] + 0xBC + 12)[0]
            if multi not in m.byid: continue
            try: im = bitmap_image(m, multi, 0)
            except Exception: continue
            if im is None: continue
            a = np.asarray(im.convert('RGBA'), np.float32)
            src = m.u('h', t['data'] + 0x70)[0]
            lo = list(m.u('3f', t['data'] + 0x78)); hi = list(m.u('3f', t['data'] + 0x84))
            for mat, g in want.items():
                if mat in found or g.shape != a.shape: continue
                if np.abs(g - a).mean() < 4.0:
                    found[mat] = dict(shader=t['name'], source=src, lower=lo, upper=hi)
                    print(f'{mat:16s} {t["name"]}: source {src} {np.round(lo, 2)} .. {np.round(hi, 2)}')
    json.dump(found, open(f'{OUT}/glow_colours.json', 'w'), indent=1)
    print(len(found), 'of', len(want), 'glowing materials matched ->', f'{OUT}/glow_colours.json')


if __name__ == '__main__':
    main()
