"""Halo 4's Promethean derez embers -> h4_derez/ (tracked: the core pack's graphics/HCEDZ*.png)

    HCE_H4_MAP=ff151_mezzanine.map H4_MAPS_DIR=<folder with Halo 4's shared.map> python3 extract_h4_derez.py

A Knight's derez (objects\\characters\\storm_knight\\fx\\derez\\derez.mdsv) throws its embers from the cheap particle
emitter ...\\derez\\parts\\derez.cpem: four particle types of fx\\cheap_particles\\global.cptl, all additive, tinted
orange-red, each a slice of the runtime texture array fx\\cheap_particles\\global_render_texture (64x64 A8R8G8B8, 31
slices, each slice with its full mip chain down to 1x1: 21844 bytes; its pixels live in shared.map):
    knight_derez_square        weight 0.35  slice 29  size 0.007-0.013 wu  rises (gravity -0.5)
    knight_derez_sm            weight 0.25  slice 28  size 0.01-0.03       falls (0.4)
    derez_digital_ash          weight 0.20  slice 29  size 0.01-0.02       falls (0.4)
    derez_digital_ash_curved   weight 0.20  slice 30  size 0.012-0.027     falls (0.25)
Slice 28 is forerunner_tech_ash, 29 forerunner_tech_ash_chunky, 30 forerunner_tech_ash_curved. Each is written grey
(its luminance, brightened to full white: Halo 4 lights them in HDR) with its alpha, so a particle's colour tints it:
HCEDZ28.png, HCEDZ29.png, HCEDZ30.png.
HaloDoom_EnemyBase.HCE_DerezTick throws them (the derez of every body, in the killing shot's colour).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))
import os
import numpy as np
from PIL import Image
from h4map import H4Map, Resources, bitmap_info

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'h4_derez')
SLICES = (28, 29, 30)
SLICE_BYTES = 64 * 64 * 4 + 32 * 32 * 4 + 16 * 16 * 4 + 8 * 8 * 4 + 4 * 4 * 4 + 2 * 2 * 4 + 4   # 21844: down to 1x1


def main():
    m = H4Map(); r = Resources(m)
    ti = next(t['index'] for t in m.tags if t['group'] == 'bitm' and t['name'] == 'fx\\cheap_particles\\global_render_texture')
    bi = bitmap_info(m, ti); im = bi['images'][0]
    assert (im['w'], im['h'], im['fmt'], im['depth']) == (64, 64, 11, 31), im
    e = r.entry(bi['res'][0]); p, sec, _ = r.segment(e['seg'])
    d = np.frombuffer((sec or b'') + (p or b''), np.uint8)
    os.makedirs(OUT, exist_ok=True)
    for k in SLICES:
        a = d[k * SLICE_BYTES:k * SLICE_BYTES + 64 * 64 * 4].reshape(64, 64, 4)[..., [2, 1, 0, 3]].astype(np.float32)
        # Halo 4 lights them at 140-180x (HDR, bloomed): here full white at the sprite's brightest, a touch of gamma
        lum = a[..., :3].max(2)
        lum = 255.0 * np.clip(lum / max(1.0, np.percentile(lum[a[..., 3] > 8], 98)), 0, 1) ** 0.7
        out = np.stack([lum, lum, lum, a[..., 3]], 2)
        Image.fromarray(out.astype(np.uint8), 'RGBA').save(f'{OUT}/HCEDZ{k}.png')
    print('->', OUT, sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main()
