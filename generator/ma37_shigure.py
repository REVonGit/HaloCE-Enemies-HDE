"""Shigure's MA37 (Raw Assets/ma37.zip: 'ma37 rev.blend' + its PBR textures) -> out/weapons/m_ma37: the Marines' and
Brutes' MA37, in place of the Digsite E3 2000 rifle repainted in Reach's colours it was before.

    HCE_MA37_SRC=/path/to/ma37.zip python3 ma37_shigure.py      # or the unzipped folder; marine_arsenal.py runs it

The blend (Blender 5.0) holds the gun as eight objects on one material (body, bolt, cowling, cylinders, display,
display_mount, gas, magazine), the muzzle along +x, up +z, four of them half models with a Mirror modifier
(lib/brute_kit.Kit.piece applies it). They are scaled so the gun is as long as Halo CE's assault rifle (LENGTH) and
moved so the origin is on the pistol grip (GRIP, in the blend's units: the grip is the lowest part of the body, in
front of the magazine: the MA5 line is a bullpup), which is where Halo's weapon frame sits and the hand closes.
One texture: the base colour with Halo CE-style shading baked in from the PBR maps and the emission (the ammo
counter) on top, at TEX_SIZE (texture()).
"""
import os, sys, io, pickle, zipfile, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from hce_paths import OUT
import brute_kit

SRC = os.environ.get('HCE_MA37_SRC', os.path.join(HERE, '..', 'Raw Assets', 'ma37.zip'))
WID = 'm_ma37'
LENGTH = 0.289              # Halo CE assault rifle, muzzle to stock, in world units (out/weapons/assault_rifle)
GRIP = (-1.5, 0.0, 0.6)     # the weapon origin in the blend's units: the middle of the pistol grip
TEX_SIZE = 512
CREDIT = 'MA37 by Shigure'


def unpack(src):
    """the blend and its textures folder (a zip is unpacked to a temp dir)"""
    if os.path.isdir(src): root = src
    else:
        root = tempfile.mkdtemp(prefix='ma37_')
        zipfile.ZipFile(src).extractall(root)
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith('.blend'): return os.path.join(dp, f), os.path.join(dp, 'textures')
    raise FileNotFoundError(f'no .blend under {src}')


# The PBR set's base colour is a flat mid grey (its detail lives in the normal, height, metal and roughness maps, which
# the engine doesn't use), so it looked flat beside Halo CE's MA5B, whose texture is near black with its lighting
# painted in: lighter on top, darker underneath, bright edges. texture() bakes the same into the colour:
#   light      the gun's own lighting, baked texel by texel: each triangle is drawn into the texture (its UVs) with its
#              normals, the normal map's detail added in each triangle's tangent frame, and lit by a key light from
#              above and a little in front (KEY: no sideways part, so the mirrored halves, which share texels, light
#              the same) over an ambient (AMBIENT) and a sky-over-ground fill (SKY); metal also takes a soft reflection
#              of a bright sky (REFLECT)
#   tone       the base colour darkened into the MA5B's range: metal (the metallic map) by DARK_METAL, the polymer
#              furniture by DARK_POLY, keeping its own variation (tint, wear marks)
#   cavity     grooves and recesses (the height map below its own blur) darkened, to CAVITY
#   bevels     edges (where the normal map tilts) and polished metal (low roughness) lit, by EDGE: worn steel
#   grime      a faint low-frequency mottle
#   emission   the ammo counter and the green light on top, untouched
KEY = (0.35, 0.0, 1.0)     # gun space: +x the muzzle, +z up
AMBIENT, DIFFUSE, SKY = 0.30, 0.75, 0.25
REFLECT = 0.35
DARK_METAL = 0.47          # the base colour's lightness is multiplied by these
DARK_POLY = 0.60
CAVITY = 0.50              # how dark a deep groove gets (1: not at all)
EDGE = 0.45                # how bright a full bevel or a polished edge gets (added, before the clamp)
GRIME = 0.10


def _blur(a, r):
    """gaussian blur of a 2-D float array (scipy)"""
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(a.astype(np.float32), r, mode='nearest')


def bake_normals(pos, nrm, uv, tris, nmap, size):
    """each texel's gun-space normal, with the normal map's detail: (size, size, 3), and a (size, size) mask of the
    texels some triangle covers. Each triangle is drawn into the texture by its UVs (v down, wrapped into 0..1 by its
    own corner), its vertex normals interpolated and bent by the normal map in its tangent frame (OpenGL: green up)"""
    N = np.zeros((size, size, 3), np.float32); M = np.zeros((size, size), bool)
    for t in tris:
        P, Nv, U = pos[t], nrm[t], uv[t].copy()
        U -= np.floor(U.min(0))
        px = U * size
        # tangent frame from the UV derivatives
        e1, e2 = P[1] - P[0], P[2] - P[0]
        d1, d2 = U[1] - U[0], U[2] - U[0]
        det = d1[0] * d2[1] - d2[0] * d1[1]
        if abs(det) < 1e-12: continue
        T = (e1 * d2[1] - e2 * d1[1]) / det
        Bt = (e2 * d1[0] - e1 * d2[0]) / det
        x0, y0 = np.floor(px.min(0)).astype(int); x1, y1 = np.ceil(px.max(0)).astype(int)
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a, b, c = px
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9: continue
        w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any(): continue
        ix = (xs[inside].astype(int)) % size; iy = (ys[inside].astype(int)) % size
        n = w0[inside, None] * Nv[0] + w1[inside, None] * Nv[1] + w2[inside, None] * Nv[2]
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        tm = nmap[iy, ix] * 2 - 1
        tt = T - n * (n @ T)[:, None]; tt /= np.maximum(np.linalg.norm(tt, axis=1, keepdims=True), 1e-6)
        bb = np.cross(n, tt) * np.sign(np.dot(np.cross(T, Bt), n.mean(0)) or 1.0)
        # (v runs down the texture, so the map's green, up in the image, is -v: along -B)
        dn = tt * tm[:, 0:1] - bb * tm[:, 1:2] + n * tm[:, 2:3]
        dn /= np.maximum(np.linalg.norm(dn, axis=1, keepdims=True), 1e-6)
        N[iy, ix] = dn; M[iy, ix] = True
    return N, M


def texture(texdir, pos, nrm, uv, tris):
    """the gun's one texture: the base colour with Halo CE-style lighting and shading baked in (see above), plus the
    emission"""
    S = TEX_SIZE * 2
    def load(n, mode='RGB'):
        return np.asarray(Image.open(f'{texdir}/ma37_body_{n}.png').convert(mode).resize((S, S), Image.LANCZOS), np.float32) / 255
    base, emis = load('BaseColor'), load('Emission')
    nmap, height = load('Normal'), load('Displacement', 'L')
    metal, rough = load('Metallic', 'L'), load('Roughness', 'L')
    # light: the gun's own, baked
    N, covered = bake_normals(np.asarray(pos, float), np.asarray(nrm, float), np.asarray(uv, float), np.asarray(tris, int), nmap, S)
    key = np.array(KEY, np.float32); key /= np.linalg.norm(key)
    diff = np.clip(N @ key, 0, 1)
    sky = 0.5 + 0.5 * N[..., 2]
    light = AMBIENT + DIFFUSE * diff + SKY * sky
    light = np.where(covered, light, AMBIENT + DIFFUSE * 0.6 + SKY * 0.5)
    refl = REFLECT * metal * np.clip(N[..., 2] * 0.5 + 0.5, 0, 1) ** 3 * np.clip((0.8 - rough) / 0.6, 0, 1) * covered
    # tone: darker overall, metal darker than the polymer
    tone = base * (DARK_POLY + (DARK_METAL - DARK_POLY) * metal)[..., None]
    # cavity: the height map's recesses against their surroundings
    cav = np.clip((_blur(height, 6) - height) / 0.08, 0, 1)
    shade = 1 - (1 - CAVITY) * cav
    # bevels: the normal map's tilt (its xy away from flat), and polished metal (low roughness)
    nx, ny = nmap[..., 0] * 2 - 1, nmap[..., 1] * 2 - 1
    tilt = np.clip((np.sqrt(nx * nx + ny * ny) - 0.12) / 0.35, 0, 1)
    polish = metal * np.clip((0.55 - rough) / 0.35, 0, 1)
    edge = np.clip(tilt * 0.8 + polish * 0.35, 0, 1) * np.clip(light / (AMBIENT + DIFFUSE + SKY), 0.3, 1)
    # grime: low-frequency mottle
    rng = np.random.default_rng(37)
    g = _blur(rng.random(height.shape).astype(np.float32), 18)
    g = (g - g.mean()) / max(g.std(), 1e-6)
    steel = np.array([0.30, 0.31, 0.33], np.float32)
    out = tone * (light * shade * (1 + GRIME * g))[..., None] + (EDGE * edge + refl)[..., None] * steel
    out = out + emis * 1.5
    im = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    return im.resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)


def build(src=SRC):
    """out/weapons/m_ma37/{m_ma37.pkl, w_m_ma37_body.png}"""
    blend, texdir = unpack(src)
    K = brute_kit.Kit(blend)
    B = K.B
    pieces = [K.piece(nm, []) for nm, o in K.objects.items() if B.get('Object', o.off, 'type') == 1]
    P = np.concatenate([p['pos'] for p in pieces]) * 100            # piece() divides by 100 (Halo 2 render units)
    s = LENGTH / (P[:, 0].max() - P[:, 0].min())
    g = np.array(GRIP)
    pos, nrm, uv, tris = [], [], [], []
    for p in pieces:
        base = len(pos)
        pp = (p['pos'] * 100 - g) * s
        pos.extend(pp); nrm.extend(p['nrm']); uv.extend(np.column_stack([p['uv'][:, 0], 1.0 - p['uv'][:, 1]]))
        tris.extend(p['tris'] + base)
    d = f'{OUT}/weapons/{WID}'; os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))              # (the Digsite rifle's files)
    mat = f'w_{WID}_body.png'
    texture(texdir, pos, nrm, uv, tris).save(f'{d}/{mat}')
    meshes = [dict(material=mat, pos=np.array(pos, float), nrm=np.array(nrm, float), uv=np.array(uv, float), tris=np.array(tris, int))]
    pickle.dump(dict(id=WID, tag=CREDIT, meshes=meshes), open(f'{d}/{WID}.pkl', 'wb'))
    Q = meshes[0]['pos']
    print(WID, 'tris', len(tris), 'bounds', Q.min(0).round(3), Q.max(0).round(3), '->', d)


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else SRC)
