"""The Brutes' Plasma Caster: HaloDoom Evolved's own Plasma Caster (Plasma_Caster_HDE.blend, Halo Infinite's
covenant_grenade_launcher) reinterpreted as a Halo CE Covenant gun (hde_ce.py).

Painted after the user's concept art in flat, low-poly colours: the armour plates (the control map's alpha) a muted
dark purple, everything else dark gunmetal, a silver cone in the front pod, the lights (the colour map's alpha) cyan,
and a red Banished glyph on the housing's flanks."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import hde_ce

BLEND = os.environ.get('HCE_CASTER_BLEND', os.path.join(HERE, 'Plasma_Caster_HDE.blend'))
WID = 'plasma_caster'
PC = 'Plasma Caster:Plasma Caster.%d'
PARTS = {PC % 104: ('body', 900), PC % 601: ('rail_l', 160), PC % 611: ('rail_r', 160), PC % 591: ('drum', 80)}
PARTS.update({PC % k: ('stud', 6) for k in list(range(592, 601)) + list(range(602, 611))})
MAT = 'covenant_grenade_launcher_default.001'
FRONT, MIDDLE, RIM = np.array([0.253, 0.0, 1.0]), np.array([0.694, 0.153, 0.29]), np.array([0.204, 0.882, 1.0])
GLOW = np.array([0.137, 0.725, 0.29])

# The look (the user's concept art): a low-poly Covenant gun in flat colours. A muted dark purple housing (the armour
# plates), dark gunmetal grey for the receiver, grip, stock plate and drum, a silver cone in the front pod, two small
# cyan lights and a red Banished glyph on the housing's flank.
PURPLE = np.array([0.29, 0.24, 0.42]); GREY = np.array([0.22, 0.22, 0.24]); SILVER = np.array([0.66, 0.66, 0.70])
CYAN = np.array([0.10, 0.92, 0.96]); RED = np.array([0.62, 0.10, 0.10])
Y_MID = -0.132                                     # the gun's centre line across (y) in the .blend
GLYPH_X, GLYPH_Z = (0.31, 0.39), (0.148, 0.172)    # where the glyph sits on the housing (metres, .blend axes)

def caster_paint(src):
    from scipy import ndimage
    col = src.image('covenant_grenade_launcher_default_color{pc}.png.001', alpha=True)
    ctl = src.image('covenant_grenade_launcher_default_control{pc}.png.001', alpha=True)
    nm = src.image('covenant_grenade_launcher_default_normal{pc}.png.001')
    size = ctl.shape[:2]; col = hde_ce._fit(col, size); nm = hde_ce._fit(nm[..., :3], size)
    plate = ndimage.binary_closing(ndimage.binary_opening(ctl[..., 3] > 0.5, iterations=2), iterations=4)
    plate = ndimage.gaussian_filter(plate.astype(np.float32), 1.0)[..., None]
    n = hde_ce.soften(nm * 2 - 1, 8); n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-3)
    shade = 0.92 + 0.16 * np.clip(n[..., 1:2] * 0.7 - n[..., 0:1] * 0.3, -1, 1)          # only a hint: the flats stay flat
    out = (GREY * (1 - plate) + PURPLE * plate) * shade
    glow = np.clip(ndimage.gaussian_filter(col[..., 3], 0.6) * 2.5, 0, 1)[..., None]
    out = np.clip(out * (1 - glow) + CYAN * glow, 0, 1)
    def paint(mat, role):
        return out if mat == MAT else None                      # the ADS screen materials are left out
    return paint

def glyph():
    """the red Banished glyph: two pairs of notched triangles, as in the concept art"""
    from PIL import Image, ImageDraw
    im = Image.new('L', (120, 40), 0); d = ImageDraw.Draw(im)
    for x0 in (4, 64):
        d.polygon([(x0, 36), (x0 + 13, 4), (x0 + 26, 36)], fill=255)             # a triangle pointing up
        d.polygon([(x0 + 8, 30), (x0 + 13, 20), (x0 + 18, 30)], fill=0)          # notched
        d.polygon([(x0 + 26, 6), (x0 + 50, 6), (x0 + 38, 30)], fill=255)          # a triangle pointing down
        d.polygon([(x0 + 33, 10), (x0 + 43, 10), (x0 + 38, 19)], fill=0)
    return np.asarray(im).astype(np.float32) / 255

def caster_hook():
    G = glyph()
    def hook(role, pos, nrm, colr):
        colr = colr.copy()
        if role in ('drum', 'stud'): colr[:] = GREY; return colr
        x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
        glow = np.abs(colr - CYAN).sum(1) < 0.4
        if role in ('rail_l', 'rail_r'):                               # the front pod's outer shells: purple
            colr[~glow] = PURPLE; return colr
        # the housing over the pod and the receiver: purple, as one piece (the source's plate mask breaks it up)
        hous = (x > 0.25) & (z > 0.14) & ~glow
        colr[hous] = PURPLE
        # the front pod's silver cone: the centre of the pod, where the housing leaves bare metal
        purple = np.abs(colr - PURPLE).sum(1) < 0.25
        cone = (x > 0.62) & (z > 0.035) & (z < 0.15) & (np.abs(y - Y_MID) < 0.045) & ~purple & ~glow
        colr[cone] = SILVER * (0.85 + 0.25 * np.clip(nrm[cone, 2:3] * 0.5 + 0.5, 0, 1))
        # the glyph, on both flanks of the housing
        side = (np.abs(nrm[:, 1]) > 0.5) & (x > GLYPH_X[0]) & (x < GLYPH_X[1]) & (z > GLYPH_Z[0]) & (z < GLYPH_Z[1])
        if side.any():
            u = (x[side] - GLYPH_X[0]) / (GLYPH_X[1] - GLYPH_X[0]); v = (z[side] - GLYPH_Z[0]) / (GLYPH_Z[1] - GLYPH_Z[0])
            u = np.where(nrm[side, 1] > 0, 1 - u, u)                   # reads front-to-back on either flank
            a = G[((1 - v) * (G.shape[0] - 1)).astype(int), (u * (G.shape[1] - 1)).astype(int)][:, None]
            colr[side] = colr[side] * (1 - a) + RED * a
        return colr
    return hook

def build():
    src = hde_ce.Source(BLEND, maxres=1024)
    P = src.R[PC % 104]['pos']                    # +x forward, +z up
    g = P[(P[:, 2] < -0.04) & (P[:, 0] < 0.3)]
    origin = np.array([g[:, 0].mean(), (P[:, 1].min() + P[:, 1].max()) / 2, P[:, 2].min() + 0.08])
    hde_ce.build(src, PARTS, caster_paint(src), origin, WID, 'hde:Plasma_Caster_HDE.blend (Halo CE reinterpretation)', hook=caster_hook())

def overlay(char='Brute'):
    """the Plasma Caster as an overlay model on a character's own skeleton (the Brute's body is at UZDoom's 32-surface
    limit, so the gun is a separate model like the Marines' arsenal; the Spec Ops Elite's likewise), placed exactly
    where it holds its baked CE plasma rifle (marine_arsenal.hand_frame recovers that transform)"""
    import json, pickle, shutil
    from iqm import write_iqm
    from marine_arsenal import hand_frame, OUT
    R, t, jn, joints = hand_frame(char, 'plasma_rifle')
    d = pickle.load(open(f'{OUT}/weapons/{WID}/{WID}.pkl', 'rb'))
    od = f'{OUT}/models/{char}'; ms = []
    for k, m in enumerate(d['meshes']):
        n = len(m['pos']); bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8); bidx[:, 0] = jn; bw[:, 0] = 255
        ms.append(dict(name=f'{WID}_{k}', material=m['material'], pos=m['pos'] @ R.T + t, nrm=m['nrm'] @ R.T, uv=m['uv'],
                       bidx=bidx, bw=bw, tris=m['tris']))
        shutil.copy(f'{OUT}/weapons/{WID}/{m["material"]}', f'{od}/{m["material"]}')
    fn = f'{char}_w_{WID}.iqm'
    write_iqm(f'{od}/{fn}', joints, ms, [dict(name='bind', fps=30.0, loop=True, frames=[[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]])])
    meta = json.load(open(f'{od}/{char}.json'))
    meta.setdefault('arsenal', {})[WID] = dict(model=fn, wid=WID, materials=[m['material'] for m in d['meshes']])
    json.dump(meta, open(f'{od}/{char}.json', 'w'), indent=1)
    print(char, 'overlay', fn)

if __name__ == '__main__':
    if sys.argv[1:2] == ['overlay']:
        import os as _os
        from marine_arsenal import OUT as _OUT
        for c in sys.argv[2:] or ['Brute', 'EliteSpecial']:     # the Brute Captain's and the Spec Ops Elite's
            if _os.path.exists(f'{_OUT}/models/{c}/{c}.json'): overlay(c)
    else: build()
