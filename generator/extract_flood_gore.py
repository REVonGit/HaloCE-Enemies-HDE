"""The Flood's own blood and bursts, from Halo 2 (MCC): its blood splats and the carrier's and infection form's pops.

    python3 extract_flood_gore.py      # -> packs/HaloCE_Flood/{graphics/hcegore, sprites/hcegore, decaldef.hcefloodgore}

Read from 06b_floodzone.map (Quarantine Zone; HCE_H2_MAP06B) and MCC's textures.dat (HCE_H2_TEXTURES; whole or its
numbered pieces, only textures.dat.001 is read):
* effects\\decals\\blood_splats\\bitmaps\\flood_splat (2x2 sheet: the Flood's blood_collision and medium splats) and
  flood_splat_large (the carrier's death splat): wall decals HCEGore_Flood / HCEGore_FloodBig (hce_gore.zsc picks them
  by species) and the floor splats HSFL (hits), HPFL (deaths), HKFL (skids);
* effects\\bitmaps\\solids\\impact_spray: the Flood's impact puff, HGBF (white mask, shaded with its blood colour);
* the carrier's body_destroyed effect: effects\\particle_models\\skin_burst\\skin_burst (2x2 sheet of skin chunks: HFSK),
  effects\\bitmaps\\smoke\\smoke_volumetric_dark (HFSM) and smoke_fiery_small (HFFI, added): HCE_FloodBurst
  (hce_flood_burst.zsc) throws them when a carrier or an infection form pops.
Halo draws its decals multiplied or added; extract_halo_gore.to_decal turns them into straight RGBA."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))
import os, sys, math, random
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_halo_gore import png_grab, blend_kind, to_decal, trim, DECAL_GROW
from h2map import H2Map, mcc_bitmap

MAP06B = os.environ.get('HCE_H2_MAP06B', '06b_floodzone.map')
TEXTURES = os.environ.get('HCE_H2_TEXTURES', 'textures.dat')
PACK = os.path.join(HERE, '..', 'packs', 'HaloCE_Flood')
DEC = 'effects\\decals\\blood_splats\\bitmaps\\'
QUARTERS = [(0, 0, .5, .5), (.5, 0, 1, .5), (0, .5, .5, 1), (.5, .5, 1, 1)]


def quarters(im):
    w, h = im.size
    return [im.crop((int(l * w), int(t * h), int(r * w), int(b * h))) for l, t, r, b in QUARTERS]


def mask(im):
    """a white alpha-mask sprite: alpha from the sheet's alpha, or its brightness when it carries none"""
    a = np.asarray(im.convert('RGBA')).astype(float)
    al = a[..., 3] if a[..., 3].mean() < 200 else a[..., :3].max(-1)
    out = np.dstack([np.full(al.shape, 255.), np.full(al.shape, 255.), np.full(al.shape, 255.), al])
    return Image.fromarray(out.astype(np.uint8), 'RGBA')


def main():
    m = H2Map(MAP06B)
    get = lambda n: mcc_bitmap(m, n, TEXTURES).convert('RGBA')
    gdir = os.path.join(PACK, 'graphics', 'hcegore'); sdir = os.path.join(PACK, 'sprites', 'hcegore')
    os.makedirs(gdir, exist_ok=True); os.makedirs(sdir, exist_ok=True)
    # the splats: decals and floor sprites
    small = [trim(to_decal(q, blend_kind(q))) for q in quarters(get(DEC + 'flood_splat'))]
    small = [s for s in small if s]
    big = get(DEC + 'flood_splat_large'); big = trim(to_decal(big, blend_kind(big)))
    dd = ['// the Flood\'s blood: Halo 2\'s flood_splat and flood_splat_large (extract_flood_gore.py)', '']
    names = []
    for i, s in enumerate(small + [big]):
        nm = f'h2_flood_splat_{i}' if i < len(small) else 'h2_flood_splat_large'
        s.save(os.path.join(gdir, nm + '.png')); names.append(nm)
        sc = (1.1 if i < len(small) else 1.6) * DECAL_GROW / 2
        dd += [f'Decal HCEG_{nm}', '{', f'\tPic "graphics/hcegore/{nm}.png"', '\tTranslucent 0.95', f'\tX-Scale {sc:.2f}',
               f'\tY-Scale {sc:.2f}', '\tRandomFlipX', '\tRandomFlipY', '\tAnimator HCEGoreFade', '}', '']
    dd += ['DecalGroup HCEGore_Flood', '{'] + [f'\tHCEG_{n} 1' for n in names[:-1]] + ['}', '']
    dd += ['DecalGroup HCEGore_FloodBig', '{'] + [f'\tHCEG_{n} 1' for n in names] + [f'\tHCEG_{names[-1]} 2', '}', '']
    open(os.path.join(PACK, 'decaldef.hcefloodgore'), 'w').write('\n'.join(dd) + '\n')
    for spr, ims in (('HSFL', small), ('HPFL', small + [big, big]), ('HKFL', small)):
        for n, s in enumerate(ims):
            png_grab(os.path.join(sdir, f'{spr}{chr(65 + n)}0.png'), s, s.width // 2, s.height // 2)
    # the impact puff: the spray, turned four ways
    spray = trim(mask(get('effects\\bitmaps\\solids\\impact_spray')))
    for n in range(4):
        r = spray.rotate(90 * n, expand=True)
        png_grab(os.path.join(sdir, f'HGBF{chr(65 + n)}0.png'), r, r.width // 2, r.height // 2)
    # the burst: skin chunks (coloured, own alpha), dark smoke (mask), fiery smoke (added: brightness kept as colour)
    for n, q in enumerate(quarters(get('effects\\particle_models\\skin_burst\\skin_burst'))):
        q = trim(q)
        if q: png_grab(os.path.join(sdir, f'HFSK{chr(65 + n)}0.png'), q, q.width // 2, q.height // 2)
    sm = mask(get('effects\\bitmaps\\smoke\\smoke_volumetric_dark'))
    sm = Image.merge('RGBA', (Image.new('L', sm.size, 40), Image.new('L', sm.size, 36), Image.new('L', sm.size, 26), sm.split()[3]))   # (its own dark colour: drawn plain translucent, soft-edged)
    for n in range(2):
        r = sm.rotate(180 * n)
        png_grab(os.path.join(sdir, f'HFSM{chr(65 + n)}0.png'), r, r.width // 2, r.height // 2)
    # the same smoke in the Flood's pale yellow-green: the gas a carrier bursts into (HFGS)
    gs = Image.merge('RGBA', (Image.new('L', sm.size, 196), Image.new('L', sm.size, 204), Image.new('L', sm.size, 118), sm.split()[3]))
    for n in range(2):
        r = gs.rotate(180 * n)
        png_grab(os.path.join(sdir, f'HFGS{chr(65 + n)}0.png'), r, r.width // 2, r.height // 2)
    # the fireball's flash (HFFL, drawn here): a soft bright ball with a lumpy edge, under the fiery smoke
    rnd = random.Random(3); n = 96; cc = (n - 1) / 2
    lob = [(rnd.uniform(0, 6.283), rnd.uniform(0.75, 1.0)) for _ in range(9)]
    fl = Image.new('RGB', (n, n)); fp = fl.load()
    for y in range(n):
        for x in range(n):
            dx, dy = (x - cc) / cc, (y - cc) / cc; r = math.hypot(dx, dy); th = math.atan2(dy, dx)
            edge = 0.62 + 0.12 * sum(math.cos(3 * (th - a)) * w for a, w in lob) / 9
            v = min(1, max(0, 1 - r / max(edge, 0.3)) ** 1.4 + math.exp(-(r / 0.22) ** 2) * 0.6)
            fp[x, y] = (int(255 * v),) * 3
    png_grab(os.path.join(sdir, 'HFFLA0.png'), fl, n // 2, n // 2)
    fi = get('effects\\bitmaps\\smoke\\smoke_fiery_small'); fi.putalpha(255)
    png_grab(os.path.join(sdir, 'HFFIA0.png'), fi.convert('RGB'), fi.width // 2, fi.height // 2)
    print('flood gore:', len(small), 'splats + large; puff, skin chunks, smoke and fire sprites')


if __name__ == '__main__':
    main()
