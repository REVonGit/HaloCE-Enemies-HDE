"""The Sentinel Knights' arm guns: the Halo Infinite Forerunner weapons of HDE_promethian_weapons.blend (the Knight
arm versions of the Light Rifle, Scattershot, Binary Rifle and Suppressor) reinterpreted as Halo CE models (hde_ce.py:
cut to a polygon budget, one atlas, one baked 512 texture each) -> $HCE_OUT/weapons/sk_<gun>/sk_<gun>.pkl.

    HCE_PROMETHEAN_BLEND=/path/to/HDE_promethian_weapons.blend python3 promethean_ce.py

The four guns sit in the .blend one above the other, each pointing +x. Each pkl's origin is the gun's back end on its
centre line (where it meets the elbow); extract_sentinel_knight.py mounts them as the Knight's right forearm."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import hde_ce

BLEND = os.environ.get('HCE_PROMETHEAN_BLEND', 'HDE_promethian_weapons.blend')
# gun -> object names (the Knight versions: 'knight:' the Light Rifle, 'knight_arm:' the Scattershot and the Binary
# Rifle, 'Sup'/'sup' the Suppressor; the 'default:' objects are the hand-held guns, and the lvl_1 scope copies are left out)
SKIP = ('knight:default.003', 'knight:default.004')


def groups(R):
    g = {'light_rifle': [], 'scattershot': [], 'binary_rifle': [], 'suppressor': []}
    for n, v in R.items():
        if n in SKIP or n.startswith('default:'): continue
        if n.startswith('knight:'): g['light_rifle'].append(n)
        elif n.lower().startswith('sup'): g['suppressor'].append(n)
        elif n.startswith('knight_arm:'):
            g['binary_rifle' if 'binary_rifle_default' in v['mats'] else 'scattershot'].append(n)
    return g


# The .blend's own materials, baked: every one is the same Principled setup (Halo 5's colour / control / normal maps):
#   base colour = colour map (sRGB) x control green (raised to 1.95 where a Gamma node sits on it) x a grey constant
#   metallic = control blue, roughness = 1 - control red, normal = the normal map (green flipped)
#   emission = colour map x its alpha (the lights' mask) x the material's emission colour, at a strength that saturates it
# material -> (grey constant, control gamma, emission colour); the energy bars are emission only
BLEND_MATS = {'light_rifle_default_body': (0.467, 1.95, (0.0, 0.12, 1.0)),
              'Material.001': (0.467, 1.95, (0.0, 0.12, 1.0)),            # the Halo 5 group over the same maps
              'light_rifle_default_scope': (0.6, 1.0, (0.0, 0.12, 1.0)),
              'light_rifle_lvl_1_000_scope': (0.671, 1.95, (0.0, 0.12, 1.0)),
              'binary_rifle_default': (0.522, 1.0, (0.0, 1.0, 0.296)),
              'scattershot_default': (0.537, 1.0, (0.47, 0.414, 1.0)),
              'suppressor_default': (0.733, 1.0, (0.0, 0.292, 1.0))}
EMISSION_ONLY = {'storm_spread_gun_energy_bar_default': (0.281, 0.0, 0.947)}
GLOW_SAT = 0.35            # the baked texture's brightmap: texels at least this saturated (the lights; the metal is grey)


def lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def blend_paint(src):
    """paint(mat, role): each material's node tree evaluated into one sRGB colour image, as a base-colour + emission
    bake would give it, with the CE treatment on top (the normal map's bevels as painted shading; metal a little
    brighter on its upturned faces, its sheen under the room's light)"""
    cache = {}
    def paint(mat, role):
        if mat in cache: return cache[mat]
        if mat in EMISSION_ONLY:
            c = np.array(EMISSION_ONLY[mat]); c = c / c.max()
            cache[mat] = np.tile(srgb(c * 0.9 + 0.1), (8, 8, 1)).astype(np.float32); return cache[mat]
        k, gamma, tint = BLEND_MATS.get(mat, (0.5, 1.0, (1.0, 1.0, 1.0)))
        imgs = src.mats.get(mat, {}).get('all', [])
        if mat == 'Material.001': imgs = ['light_rifle_default_color{pc}.png', 'light_rifle_default_control{pc}.png', 'light_rifle_default_normal{pc}.png']
        pick = lambda key: next((i for i in imgs if f'_{key}' in i), None)
        col = src.image(pick('color'), alpha=True)
        ctl = src.image(pick('control'), alpha=True) if pick('control') else None
        nm = src.image(pick('normal')) if pick('normal') else None
        size = col.shape[:2]
        ctl = hde_ce._fit(ctl, size) if ctl is not None else np.ones(size + (4,), np.float32)
        g = ctl[..., 1:2] ** gamma
        base = lin(col[..., :3]) * g * k                       # linear base colour, as Blender shades it
        metal = ctl[..., 2:3]; rough = 1 - ctl[..., 0:1]
        # a bake under soft, even light: diffuse for the dielectric parts, the base colour as the reflectance of the
        # metal, which polished (low roughness) catches more of the light around it
        out = base * (1 - metal) + base * metal * (0.85 + 0.6 * (1 - rough))
        out = hde_ce.ce_shade(srgb(out).astype(np.float32), hde_ce._fit(nm, size) if nm is not None else None)
        e = col[..., :3] * col[..., 3:4]                        # the lights
        lit = np.clip(e.max(2, keepdims=True) * 3, 0, 1)
        t = np.array(tint, np.float32); glow = srgb(np.clip(t / t.max() * 0.85 + e * 0.35, 0, 1))
        out = out * (1 - lit) + glow * lit
        cache[mat] = np.clip(out, 0, 1).astype(np.float32)
        return cache[mat]
    return paint


def brightmap(wid):
    """the baked texture's lights (its saturated texels) as a brightmap beside it"""
    from PIL import Image
    d = f'{hde_ce.bc.OUT}/weapons/{wid}'; f = f'{d}/w_{wid}_0.png'
    a = np.asarray(Image.open(f).convert('RGB')).astype(np.float32) / 255
    mx, mn = a.max(2), a.min(2); sat = (mx - mn) / np.maximum(mx, 1e-3)
    bm = np.clip((sat - GLOW_SAT) / 0.25, 0, 1) * np.clip(mx * 1.5, 0, 1)
    Image.fromarray((bm * 255).astype(np.uint8)).save(f'{d}/w_{wid}_0_bm.png')


def build():
    src = hde_ce.Source(BLEND)
    paint = blend_paint(src)
    for gun, names in groups(src.R).items():
        P = np.concatenate([src.R[n]['pos'] for n in names])
        origin = np.array([P[:, 0].min(), (P[:, 1].min() + P[:, 1].max()) / 2, (P[:, 2].min() + P[:, 2].max()) / 2])
        total = sum(len(src.R[n]['tris']) for n in names)
        parts = {n: (f'{gun}_{k}', max(24, int(len(src.R[n]['tris']) * 1800 / total))) for k, n in enumerate(names)}
        hde_ce.build(src, parts, paint, origin, f'sk_{gun}', f'hde:HDE_promethian_weapons.blend {gun} (Knight arm)')
        brightmap(f'sk_{gun}')


if __name__ == '__main__':
    build()
