"""Halo CE + Halo 2 blood for the NashGore patch (Covenant pack): the games' own blood decals and impact bursts.

    python3 extract_halo_gore.py      # -> out/gore/{graphics/hcegore/*.png, sprites/hcegore/*.png, decaldef.hcegore}

* Halo CE (Xbox maps, HCE_MAPS): effects\\decals\\blood splats\\bitmaps\\* - the Elite, Grunt, Hunter (+ glow),
  Engineer and generic splats and the Elite / Grunt smears - cut out of their sprite sheets by the bitmap's own
  sequence rectangles; effects\\particles\\solid\\bitmaps\\blood generic burst / blood burst for impact puffs.
* Halo 2 (08b_deltacontrol.map + MCC textures.dat): effects\\decals\\blood_splats\\bitmaps\\* - Elite, Grunt, Brute,
  Hunter, Drone ("bugger") and generic splats, the drippy combat splat - 2x2 sheets; blood_generic_burst and
  blood_trails for impact puffs and spray streaks.
Halo draws its decals multiplied (white background) or added (black background); both become plain coloured RGBA
here (alpha from how much the decal changes the wall), so they look the same on a mid-grey wall. Puffs become white
alpha masks, shaded with the victim's blood colour at run time.
DECALDEF: one decal per cut-out, grouped per species (HCEGore_<Species>, HCEGore_<Species>Big for deaths).
"""
import os as _os, sys as _sys
import os, sys, struct, zlib, json
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hce_paths import OUT, MAPS_DIR as CE_MAPS
from extract_h2_brute import MAP as MAP08B, CACHE as CACHE08B
TEXTURES = os.environ.get('HCE_H2_TEXTURES', 'textures.dat')
CE_DEC = 'effects\\decals\\blood splats\\bitmaps\\'
CE_PART = 'effects\\particles\\solid\\bitmaps\\'
H2_DEC = 'effects\\decals\\blood_splats\\bitmaps\\'

# species -> [(game, bitmap, decal scale)]; 'Big' groups (deaths) add the smears and the large splats
SPLATS = {
    'Elite':    [('ce', CE_DEC + 'blood splat elite', 0.8), ('h2', H2_DEC + 'blood_splat_elite', 0.8)],
    'Grunt':    [('ce', CE_DEC + 'blood splat grunt', 0.7), ('h2', H2_DEC + 'blood_splat_grunt', 0.7)],
    'Hunter':   [('ce', CE_DEC + 'blood splat hunter', 0.9), ('ce', CE_DEC + 'blood splat hunter glow', 0.9),
                 ('h2', H2_DEC + 'blood_splat_hunter', 0.9), ('h2', H2_DEC + 'blood_splat_hunter2', 0.9)],
    'Brute':    [('h2', H2_DEC + 'blood_splat_brute', 0.9)],
    'Drone':    [('h2', H2_DEC + 'blood_splat_bugger', 0.6), ('h2', H2_DEC + 'blood_splat_bugger2', 0.6)],
    'Engineer': [('ce', CE_DEC + 'blood splat engineer', 0.7)],
    'Beast':    [('ce', CE_DEC + 'blood splat', 0.9), ('h2', H2_DEC + 'blood_splat', 0.9)],
    'Flood':    [('h2', H2_DEC + 'flood_splat', 0.8)],
    'Human':    [('ce', CE_DEC + 'blood splat', 0.8), ('h2', H2_DEC + 'blood_splat', 0.8)],
}
BIG = {
    'Elite':  [('ce', CE_DEC + 'blood smear elite lg', 0.7), ('ce', CE_DEC + 'blood smear elite med', 0.7)],
    'Grunt':  [('ce', CE_DEC + 'blood smear grunt lg', 0.6), ('ce', CE_DEC + 'blood smear grunt med', 0.6)],
    'Beast':  [('h2', 'scenarios\\decorators\\combat\\bitmaps\\bloodsplat_drippy', 0.6)],
    'Flood':  [('h2', H2_DEC + 'flood_splat_large', 0.7)],
    'Human':  [('h2', 'scenarios\\decorators\\combat\\bitmaps\\bloodsplat_drippy', 0.6)],
}
PUFFS = [('ce', CE_PART + 'blood generic burst'), ('h2', 'effects\\bitmaps\\solids\\blood_generic_burst')]
STREAKS = [('h2', 'effects\\bitmaps\\solids\\blood_trails')]


def png_grab(path, im, ox, oy):
    """save a PNG with a grAb chunk (Doom sprite offsets)"""
    im.save(path)
    d = open(path, 'rb').read()
    body = b'grAb' + struct.pack('>ii', ox, oy)
    chunk = struct.pack('>I', 8) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)
    i = d.index(b'IDAT') - 4
    open(path, 'wb').write(d[:i] + chunk + d[i:])


def ce_sheet(name):
    from tags import HMap
    from bitmaps import bitmap_image
    for mp in ('a10', 'a50', 'b30', 'c10'):
        p = os.path.join(CE_MAPS, mp + '.map')
        if not os.path.exists(p): continue
        m = HMap(p)
        t = next((t for t in m.tags if t['cls'] == 'bitm' and t['name'] == name), None)
        if not t: continue
        im = bitmap_image(m, t['id'], 0).convert('RGBA')
        sc, sp = m.reflexive(t['data'] + 0x54)
        rects = []
        for i in range(sc):
            n, spp = m.reflexive(sp + i * 64 + 52)
            for k in range(n):
                _, l, r, tp, b, _, _ = m.u('h2x4x4f2f', spp + k * 32)
                rects.append((l, tp, r, b))
        return im, rects
    raise FileNotFoundError(name)


_h2 = None
def h2_sheet(name):
    global _h2
    from h2map import H2Map, mcc_bitmap
    if _h2 is None: _h2 = H2Map(MAP08B, CACHE08B)
    im = mcc_bitmap(_h2, name, TEXTURES).convert('RGBA')
    w, h = im.size
    if 'drippy' in name or name.endswith('flood_splat_large'): return im, [(0, 0, 1, 1)]
    if 'generic_burst' in name or 'trails' in name: return im, None          # loose shapes: connected parts
    return im, [(0, 0, .5, .5), (.5, 0, 1, .5), (0, .5, .5, 1), (.5, .5, 1, 1)]


def blend_kind(im):
    a = np.asarray(im).astype(float)
    if a[..., 3].mean() < 128: return 'alpha'          # a real coverage alpha (the drippy splat); others carry masks
    edge = np.concatenate([a[0, :, :3], a[-1, :, :3], a[:, 0, :3], a[:, -1, :3]])
    return 'mul' if edge.mean() > 128 else 'add'


def to_decal(im, kind):
    """Halo decal (multiplied on white / added on black / plain alpha) -> straight RGBA"""
    a = np.asarray(im).astype(float) / 255.0
    rgb = a[..., :3]
    if kind == 'mul':
        al = 1.0 - rgb.min(-1)
        col = 1.0 - (1.0 - rgb) / np.maximum(al[..., None], 1e-3)       # over white this gives the original back
        col = np.clip(col * 0.85, 0, 1)                                  # a touch darker: walls aren't white
    elif kind == 'add':
        al = rgb.max(-1)
        col = rgb / np.maximum(al[..., None], 1e-3)
    else:
        al = a[..., 3]; col = rgb
    al = np.clip(al * 1.15, 0, 1)
    return Image.fromarray((np.dstack([col, al]) * 255).astype(np.uint8), 'RGBA')


def crops(im, rects):
    w, h = im.size
    if rects is None:                                 # connected shapes in the alpha (or brightness)
        from scipy import ndimage
        a = np.asarray(im).astype(float)
        mask = (a[..., 3] if a[..., 3].mean() < 200 else a[..., :3].max(-1)) > 40
        lab, n = ndimage.label(ndimage.binary_dilation(mask, iterations=3))
        out = []
        for sl in ndimage.find_objects(lab):
            if (sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start) < 60: continue
            out.append(im.crop((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)))
        return out
    return [im.crop((int(l * w), int(t * h), int(r * w), int(b * h))) for l, t, r, b in rects]


def trim(im):
    bb = im.split()[3].point(lambda v: 255 if v > 8 else 0).getbbox()
    return im.crop(bb) if bb else None


def main():
    od = f'{OUT}/gore'
    gdir = f'{od}/graphics/hcegore'; sdir = f'{od}/sprites/hcegore'
    for d in (gdir, sdir): os.makedirs(d, exist_ok=True)
    for d in (gdir, sdir):
        for f in os.listdir(d): os.remove(os.path.join(d, f))
    dec = ['// Halo CE and Halo 2 blood decals (extract_halo_gore.py), used by the NashGore patch (hce_gore.zsc)',
           'Fader HCEGoreFade\n{\n\tDecayStart 60.0\n\tDecayTime 20.0\n}\n']
    groups = {}; made = {}
    def add_group(gname, src):
        names = []
        for game, bm, scale in src:
            if bm in made: names += made[bm]; continue
            made[bm] = []
            im, rects = (ce_sheet if game == 'ce' else h2_sheet)(bm)
            for k, c in enumerate(crops(im, rects)):
                c = trim(to_decal(c, blend_kind(c)))          # per cut-out: some sheets mix backgrounds
                if c is None or c.size[0] < 8: continue
                stem = f'{game}_{bm.split(chr(92))[-1].replace(" ", "_")}_{k}'
                c.save(f'{gdir}/{stem}.png')
                dn = f'HCEG_{stem}'
                glow = 'glow' in bm
                dec.append(f'Decal {dn}\n{{\n\tPic "graphics/hcegore/{stem}.png"\n'
                           + ('\tAdd 0.8\n\tFullbright\n' if glow else '\tTranslucent 0.95\n')
                           + f'\tX-Scale {scale:.2f}\n\tY-Scale {scale:.2f}\n\tRandomFlipX\n\tRandomFlipY\n\tAnimator HCEGoreFade\n}}\n')
                names.append(dn); made[bm].append(dn)
        groups[gname] = names
    for sp, src in SPLATS.items(): add_group(f'HCEGore_{sp}', src)
    for sp, src in BIG.items(): add_group(f'HCEGore_{sp}Big', src + SPLATS[sp])
    for sp in SPLATS:
        if f'HCEGore_{sp}Big' not in groups: groups[f'HCEGore_{sp}Big'] = groups[f'HCEGore_{sp}']
    for g, names in groups.items():
        dec.append(f'DecalGroup {g}\n{{\n' + ''.join(f'\t{n} 1\n' for n in names) + '}\n')
    open(f'{od}/decaldef.hcegore', 'w').write('\n'.join(dec))
    # impact puffs (HGBP) and spray streaks (HGBS): white alpha masks, frames A..
    def sprites(spr, src):
        n = 0
        for game, bm in src:
            im, rects = (ce_sheet if game == 'ce' else h2_sheet)(bm)
            if game == 'ce' and 'generic burst' in bm: rects = rects
            kind = blend_kind(im)
            for c in crops(im, rects):
                a = np.asarray(c).astype(float)
                al = a[..., 3] if kind == 'alpha' or a[..., 3].mean() < 200 else a[..., :3].max(-1)
                m = Image.fromarray(np.dstack([np.full(al.shape, 255.0)] * 3 + [al]).astype(np.uint8), 'RGBA')
                m = trim(m)
                if m is None or n >= 26: continue
                w, h = m.size
                png_grab(f'{sdir}/{spr}{chr(65 + n)}0.png', m, w // 2, h // 2)
                n += 1
        return n
    npuff = sprites('HGBP', PUFFS)
    nstreak = sprites('HGBS', STREAKS)
    json.dump(dict(groups={g: len(v) for g, v in groups.items()}, puffs=npuff, streaks=nstreak), open(f'{od}/gore.json', 'w'), indent=1)
    print({g: len(v) for g, v in groups.items()}, 'puffs', npuff, 'streaks', nstreak)


if __name__ == '__main__':
    main()
