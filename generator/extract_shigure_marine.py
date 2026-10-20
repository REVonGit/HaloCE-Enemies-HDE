"""Shigure's Marine rifleman (Sabopool's Halo CE Overhaul 2.0) -> $HCE_OUT/models/MarineKit/shigure_body.iqm

    HCE_SABO_C40=/path/to/c40.map HCE_SABO_BITMAPS=/path/to/bitmaps.map python3 extract_shigure_marine.py
                                       # after extract_spv3.py MarineShigure and extract_marine_kit.py

The body is Shigure's 'classic' Marine (the 'Gunther' rifleman) as Sabopool's Halo CE Overhaul 2.0 (Steam Workshop
3735328357) carries it in its c40 (extract_spv3.py reads it into out/models/MarineShigure). Its skeleton is the Halo CE
Marine's 20 bones, so it becomes one Marine kit piece on the CE Marine's skeleton, as Mercury Rising's medic does
(extract_mr_marines.py): build_pack.py hides the Marine and wears the piece (HCE_MarineRifleman<Gun>), so it plays every
Marine animation and carries every gun.
Two changes to his look:
* his armour's green (painted into the textures) is turned to the brown of Sabopool's armoured Marine (marine_c_new):
  that Marine armour's median hue, saturation and brightness (BROWN), the green pixels' own shading kept (their
  saturation and brightness scaled by the brown's over the green's medians). Only the armour textures change (more
  than GREEN_SHARE of their pixels green): the face, balaclava and glasses keep theirs.
* his hands, which borrow scraps of the armour texture, wear the mod's ODST's black knit gloves instead: the triangles
  carried by the hand bones go on a surface of their own, box-mapped (by their faces' facing) onto a seamless tile cut
  from the ODST's arm bitmap (GLOVE_BITMAP, GLOVE_CROP: the back of the glove, mirrored into a 2 x 2 tile).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))
import os, sys, json
import numpy as np
from PIL import Image, ImageOps
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2rig import ce_world, retarget
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
KIT = f'{OUT}/models/MarineKit'
SRC = 'MarineShigure'                  # extract_spv3.py's pack id for the rifleman
PIECE = 'shigure_body'
BROWN = (0.0625, 0.263, 0.259)         # hue, saturation, value of Sabopool's armoured Marine's brown (its armour's median)
GREEN = (0.14, 0.45, 0.10)             # a green pixel: hue between the first two, saturation over the third
GREEN_SHARE = 0.4                      # a texture is armour when more than this share of its pixels is green
GLOVE_BITMAP = r'characters\marine_odst\bitmaps\h1_odst_arms'
GLOVE_CROP = (25, 295, 105, 345)       # the back of the glove in that 256 x 512 bitmap
GLOVE_TILE = 0.03                      # world units one tile of the glove covers


def brown(a):
    """an RGB image (0..1) with its green turned brown (BROWN), or None when it is not an armour texture"""
    h = rgb_to_hsv(a)
    g = (h[..., 0] > GREEN[0]) & (h[..., 0] < GREEN[1]) & (h[..., 1] > GREEN[2])
    if g.mean() <= GREEN_SHARE: return None
    gs, gv = np.median(h[..., 1][g]), np.median(h[..., 2][g])
    w = np.clip((h[..., 1] - GREEN[2]) / 0.08, 0, 1) * g          # soft at the edge of the green
    o = h.copy()
    o[..., 0] = np.where(g, BROWN[0], h[..., 0])
    o[..., 1] = h[..., 1] * (1 - w) + np.clip(h[..., 1] * BROWN[1] / gs, 0, 1) * w
    o[..., 2] = h[..., 2] * (1 - w) + np.clip(h[..., 2] * BROWN[2] / gv, 0, 1) * w
    return hsv_to_rgb(o)


def glove_tile():
    """the ODST's glove fabric as a seamless tile, read from the mod's map (HCE_SABO_C40 / HCE_SABO_BITMAPS)"""
    import gore_kit
    import extract_spv3 as sp
    gore_kit.SPV3_BITMAPS = sp.MAP_BITMAPS['sabo']
    m = sp.PCMap(sp.MAPS['sabo'][0])
    t = next(t for t in m.find('bitm') if t['name'] == GLOVE_BITMAP)
    g = sp.pc_bitmap_image(m, t['id']).convert('RGB').crop(GLOVE_CROP)
    tile = Image.new('RGB', (g.width * 2, g.height * 2))
    tile.paste(g, (0, 0)); tile.paste(ImageOps.mirror(g), (g.width, 0))
    tile.paste(ImageOps.flip(g), (0, g.height)); tile.paste(ImageOps.flip(ImageOps.mirror(g)), (g.width, g.height))
    return tile.resize((128, 128), Image.LANCZOS)


def texture(mat):
    """the rifleman's texture mat (brown where it was green) as mk_shigure_<k>.png in the kit"""
    out = f'mk_{PIECE}_{mat[len(SRC) + 1:]}'
    a = np.asarray(Image.open(f'{OUT}/models/{SRC}/{mat}').convert('RGB'), np.float64) / 255.0
    b = brown(a)
    Image.fromarray((np.clip(a if b is None else b, 0, 1) * 255).round().astype(np.uint8)).save(f'{KIT}/{out}')
    return out


def gloves(mm, joints):
    """mm's triangles carried by the hand bones split off: (mm without them, the glove surface)"""
    hb = [i for i, j in enumerate(joints) if 'hand' in j[0]]
    bi = np.asarray(mm['bidx'], int); bw = np.asarray(mm['bw'], float) / 255.0
    w = sum(np.isin(bi[:, k], hb) * bw[:, k] for k in range(4))
    T = np.asarray(mm['tris']); hand = w[T].max(1) > 0.5
    if not hand.any(): return mm, None
    P = np.asarray(mm['pos'], float); ht = T[hand]; idx = ht.reshape(-1)
    fn = np.cross(P[ht[:, 1]] - P[ht[:, 0]], P[ht[:, 2]] - P[ht[:, 0]])
    ax = np.abs(fn).argmax(1).repeat(3)
    uv = np.zeros((len(idx), 2))
    for a in range(3):                     # box mapping: each face onto the plane it faces most
        s = ax == a
        uv[s] = P[idx][s][:, [k for k in range(3) if k != a]] / GLOVE_TILE
    glove = dict(name='gloves', material=f'mk_{PIECE}_gloves.png', pos=P[idx], nrm=np.asarray(mm['nrm'], float)[idx], uv=uv,
                 bidx=np.asarray(mm['bidx'])[idx], bw=np.asarray(mm['bw'])[idx], tris=np.arange(len(idx)).reshape(-1, 3))
    return dict(mm, tris=T[~hand]), glove


def main():
    """the rifleman retargeted onto the kit's skeleton, browned and gloved, written as MarineKit/shigure_body.iqm with
    its textures, and added to MarineKit.json as a whole body"""
    MJ, _, MA = read_iqm(f'{KIT}/helmet_closed.iqm')          # the kit's skeleton (the CE Marine's) and its bind animation
    alist = [dict(name=n, fps=30.0, loop=True, frames=fr) for n, fr in MA.items()]
    mw = ce_world(MJ)
    names = [j[0] for j in MJ]
    J, M, _ = read_iqm(f'{OUT}/models/{SRC}/{SRC}.iqm')
    sw = ce_world(J)
    tomap = [names.index(j[0]) for j in J]
    out = []
    for mm in M:
        if mm['name'].startswith('weapon_'): continue          # (no gun on the body: the arsenal carries them)
        bi = np.asarray(mm['bidx'], int); bw = np.asarray(mm['bw'], float) / 255.0
        P, N, cb, w8 = retarget(mm['pos'], mm['nrm'], bi, bw, sw, mw, tomap)
        body, glove = gloves(dict(mm, pos=P, nrm=N, bidx=cb, bw=w8), MJ)
        out.append(dict(name=mm['name'], material=texture(mm['material']), pos=body['pos'], nrm=body['nrm'],
                        uv=np.asarray(mm['uv'], float), bidx=body['bidx'], bw=body['bw'], tris=np.asarray(body['tris'])))
        if glove is not None:
            glove_tile().save(f'{KIT}/{glove["material"]}')
            out.append(glove)
        print(f'   {mm["name"]}: {len(P)} verts, {len(body["tris"])} tris' + (f', {len(glove["tris"])} gloved' if glove else ''))
    write_iqm(f'{KIT}/{PIECE}.iqm', MJ, out, alist)
    kj = f'{KIT}/MarineKit.json'
    kit = json.load(open(kj))
    kit['pieces'][PIECE] = dict(slot='body', source=f'sabopool {SRC}', file=f'{PIECE}.iqm', shell=False, enclosed=True,
                                needs_helmet=False, whole=True, tris=int(sum(len(x['tris']) for x in out)))
    json.dump(kit, open(kj, 'w'), indent=1)
    print('->', f'{KIT}/{PIECE}.iqm')


if __name__ == '__main__':
    main()
