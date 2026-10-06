"""The Brutes' Plasma Caster: HaloDoom Evolved's own Plasma Caster (Plasma_Caster_HDE.blend, Halo Infinite's
covenant_grenade_launcher) reinterpreted as a Halo CE Covenant gun (hde_ce.py).

Its material in the .blend: a dark metallic base (control map: roughness, gloss, metal; alpha marks the armour
plates) and glowing lights (the colour map's alpha). Painted like Halo CE's own Covenant guns from those: the armour
plates in smooth dark vibrant purple with soft violet highlights and edges, the mechanism near-black, the lights cyan."""
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

# Halo CE's Covenant guns (plasma rifle, plasma pistol, needler): smooth deep metal with soft highlights, near-black
# mechanical parts, small glowing cyan details. The Plasma Caster is painted the same way, in a dark vibrant purple.
INDIGO_DARK, INDIGO_LIGHT = np.array([0.11, 0.02, 0.22]), np.array([0.56, 0.20, 0.86])   # dark vibrant purple
MECH_DARK, MECH_LIGHT = np.array([0.05, 0.03, 0.08]), np.array([0.25, 0.18, 0.34])
CE_GLOW = np.array([0.35, 0.95, 0.92])

def caster_paint(src):
    from scipy import ndimage
    col = src.image('covenant_grenade_launcher_default_color{pc}.png.001', alpha=True)
    ctl = src.image('covenant_grenade_launcher_default_control{pc}.png.001', alpha=True)
    nm = src.image('covenant_grenade_launcher_default_normal{pc}.png.001')
    size = ctl.shape[:2]; col = hde_ce._fit(col, size); nm = hde_ce._fit(nm[..., :3], size)
    # broad shapes only: the armour mask closed and smoothed (no speckle), the relief's large-scale bevels
    plate = ndimage.binary_closing(ndimage.binary_opening(ctl[..., 3] > 0.5, iterations=2), iterations=3)
    plate = ndimage.gaussian_filter(plate.astype(np.float32), 1.5)[..., None]
    # the armour mask is broken up across the gun's many small shells; read as CE does, the gun is one purple body
    # with only its deep mechanism darker
    plate = 0.55 + 0.45 * plate
    n = hde_ce.soften(nm * 2 - 1, 4); n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-3)
    light = np.clip(0.5 + 0.55 * (n[..., 1:2] * 0.75 - n[..., 0:1] * 0.35), 0, 1)        # soft light from above
    gloss = hde_ce.soften(ctl[..., 1:2], 6)
    t = np.clip(0.15 + 0.7 * light * (0.6 + 0.4 * gloss), 0, 1)
    armour = INDIGO_DARK + (INDIGO_LIGHT - INDIGO_DARK) * t ** 1.3
    mech = MECH_DARK + (MECH_LIGHT - MECH_DARK) * t
    out = mech * (1 - plate) + armour * plate
    rim = np.clip((1 - np.clip(n[..., 2:3], 0, 1)) * 3 - 0.4, 0, 1) * plate * 0.35      # bevels catch a lavender edge
    out = out * (1 - rim) + INDIGO_LIGHT * 1.15 * rim
    glow = np.clip(ndimage.gaussian_filter(col[..., 3], 0.8) * 2.0, 0, 1)[..., None]
    out = out * (1 - glow) + CE_GLOW * (0.75 + 0.25 * glow) * glow
    out = np.clip(out, 0, 1)
    def paint(mat, role):
        return out if mat == MAT else None                      # the ADS screen materials are left out
    return paint

def build():
    src = hde_ce.Source(BLEND, maxres=1024)
    P = src.R[PC % 104]['pos']                    # +x forward, +z up
    g = P[(P[:, 2] < -0.04) & (P[:, 0] < 0.3)]
    origin = np.array([g[:, 0].mean(), (P[:, 1].min() + P[:, 1].max()) / 2, P[:, 2].min() + 0.08])
    hde_ce.build(src, PARTS, caster_paint(src), origin, WID, 'hde:Plasma_Caster_HDE.blend (Halo CE reinterpretation)')

def overlay(char='Brute'):
    """the Plasma Caster as an overlay model on the Brute's own skeleton (its body is at UZDoom's 32-surface limit, so
    the gun is a separate model like the Marines' arsenal), placed exactly where the Brute holds its baked CE plasma
    rifle (marine_arsenal.hand_frame recovers that transform)"""
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
    if sys.argv[1:2] == ['overlay']: overlay()
    else: build()
