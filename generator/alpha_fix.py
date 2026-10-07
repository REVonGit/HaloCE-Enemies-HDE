"""Alpha-tested teeth: the Elites' teeth cut out as Halo CE draws them -> out/models/<char>/

    python3 alpha_fix.py [char ...]

Halo CE draws its 'elite teeth' shader alpha-tested and two-sided: the teeth are
cut out of a flat card by the bitmap's alpha, seen from both sides. extract_chars.py saves every skin as plain RGB, so
the cards showed as solid rectangles. Here the teeth bitmaps (read from a Halo CE map) give their alpha, made crisp
(UZDoom alpha-tests model skins), to the character's skin with the same picture, and the surfaces using that skin get
their back faces. Re-running it changes nothing more. The blood-on-the-body textures over every cut-out skin (these, and the Drone's
wings and antennae) are masked to the solid parts. Run after extract_chars.py, extract_h2.py and blood_kit.py.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
from hce_paths import MAPS_DIR as CE_MAPS     # Halo CE's maps (HCE_MAPS)
CHARS = ('Elite', 'EliteSpecial', 'EliteRifle')
CHARS = ('Elite', 'EliteSpecial', 'EliteRifle', 'EliteZealot')
TEETH = ('elite teeth',)


def teeth_bitmaps():
    from tags import HMap
    from bitmaps import bitmap_image
    from extract_chars import shader_maps
    out = []
    m = HMap(f'{CE_MAPS}/b30.map')
    for t in m.tags:
        if t['cls'] != 'soso' or not any(k in t['name'] for k in TEETH): continue
        base, _, _ = shader_maps(m, {'id': t['id']})
        im = bitmap_image(m, base) if base else None
        if im is not None: out.append((t['name'], im.convert('RGBA')))
    return out


def main(chars):
    bms = teeth_bitmaps()
    for char in chars:
        d = f'{OUT}/models/{char}'
        if not os.path.isdir(d): continue
        meta = json.load(open(f'{d}/{char}.json'))
        fixed = []
        for mat in sorted(set(meta.get('meshes', []))):
            f = f'{d}/{mat}'
            if not os.path.exists(f): continue
            rgb = np.asarray(Image.open(f).convert('RGB')).astype(int)
            for name, im in bms:
                a = np.asarray(im)
                if a.shape[:2] != rgb.shape[:2] or np.abs(a[..., :3].astype(int) - rgb).mean() > 2: continue
                out = np.dstack([rgb.astype(np.uint8), np.where(a[..., 3] >= 128, 255, 0).astype(np.uint8)])
                Image.fromarray(out, 'RGBA').save(f)
                fixed.append(mat); break
        if not fixed: print(char, 'no teeth skin'); continue
        # two-sided: the back faces of the surfaces wearing it (once)
        joints, meshes, anims = read_iqm(f'{d}/{char}.iqm')
        n = 0
        for m in meshes:
            if m['material'] not in fixed: continue
            t = m['tris']
            back = t[:, [0, 2, 1]]
            have = {tuple(sorted(x)) + (tuple(x),) for x in map(tuple, t)}
            if any(tuple(sorted(x)) + (tuple(x),) in have for x in map(tuple, back)): continue      # already two-sided
            m['tris'] = np.concatenate([t, back]); n += 1
        if n:
            alist = [dict(name=k, fps=30.0, loop=True, frames=[[(tuple(tt), tuple(q), tuple(s)) for tt, q, s in fr] for fr in anims[k]])
                     for k in sorted(anims)]
            meta['iqm_bytes'] = write_iqm(f'{d}/{char}.iqm', [(nm, p, tuple(tt), tuple(q), tuple(s)) for nm, p, tt, q, s in joints], meshes, alist)
            json.dump(meta, open(f'{d}/{char}.json', 'w'), indent=1)
        print(char, 'teeth skin', fixed, 'two-sided surfaces', n)


def mask_blood(char):
    """blood on the body (blood_kit.py) over a cut-out skin: only where the skin is solid (the Elite's teeth, the
    Drone's wings and antennae), not on the card around it"""
    d = f'{OUT}/models/{char}'
    if not os.path.isdir(d): return
    n = 0
    for f in sorted(os.listdir(d)):
        if not (f.startswith(char + '_') and f.endswith('.png')) or 'multi' in f: continue
        im = Image.open(f'{d}/{f}')
        if im.mode != 'RGBA': continue
        a = np.asarray(im)[..., 3]
        if a.min() == 255: continue
        for k in (1, 2, 3):
            bf = f'{d}/blood{k}_{f}'
            if not os.path.exists(bf): continue
            b = np.asarray(Image.open(bf).convert('RGBA')).copy()
            m = np.asarray(Image.fromarray(a).resize(b.shape[1::-1], Image.NEAREST)) >= 128
            b[..., 3] = np.where(m, b[..., 3], 0)
            Image.fromarray(b, 'RGBA').save(bf); n += 1
    if n: print(char, 'blood masked on', n, 'textures')


if __name__ == '__main__':
    main(sys.argv[1:] or CHARS)
    for c in tuple(sys.argv[1:] or CHARS) + ('Drone',): mask_blood(c)
