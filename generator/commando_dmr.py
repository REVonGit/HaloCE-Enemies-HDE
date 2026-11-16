"""The Marines' Commando: Shigure's DMR-style Commando model (Raw Assets/dmr_commando.zip:
'dmr commando.blend' + PBR textures) -> out/weapons/m_commando, in place of HDE's own Commando reinterpreted as a Halo
CE gun (commando_ce.py) it was before.

    HCE_COMMANDO_DMR_SRC=/path/to/dmr_commando.zip python3 commando_dmr.py      # or the unzipped folder; marine_arsenal.py runs it

The blend (Blender 5) is a Halo weapon already: in Halo's weapon space (the muzzle along +x, up +z, its origin on the
pistol grip, where Halo's weapon frame sits and the hand closes) at the JMS scale (100 to a world unit), with Halo's
markers (the left hands, the trigger, the ejection port). The gun is the objects in its 'final' collection (FINAL;
'parts' holds their sources), on three materials:
  commando_base     the gun, its colour map with Halo CE-style shading baked in from the normal, metallic and roughness
                    maps (texture(): the same idea as ma37_shigure.py's and needle_rifle_ce.py's)
  commando_scope    the scope's lens: no colour map, an amber base colour (its metallic and roughness maps only), a flat
                    swatch (SWATCH)
  commando_display  the ammo counter: a dark blue screen with a blue glow, a flat swatch
The swatches go in texels no triangle of the gun uses, so the whole gun is one texture, w_m_commando_0.png (TEX), on
one mesh: the packs' Commando overlays keep their one surface and its skin.
"""
import os, sys, pickle, zipfile, tempfile
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from hce_paths import OUT
import brute_kit
from ma37_shigure import bake_normals

SRC = os.environ.get('HCE_COMMANDO_DMR_SRC', os.path.join(HERE, '..', 'Raw Assets', 'dmr_commando.zip'))
WID = 'm_commando'
FINAL = ('barrel.001', 'body', 'body.003', 'bolt', 'dmr', 'dmr_scope', 'dmr_scope_case', 'magazine')
TEX = 512                  # the texture (the bake at the colour map's own size, then shrunk)
SWATCH = {'commando_scope': (150, 82, 22), 'commando_display': (70, 110, 170)}     # sRGB of the materials' colours
CREDIT = 'DMR Commando by Shigure'

# shading baked into the colour map (its own PBR set is flat; Halo CE's guns carry their lighting in the texture): a key
# light from above and a little in front (no sideways part: mirrored halves share texels), ambient and a sky fill,
# bevels (where the normal map tilts) and polished metal lit, a soft sky reflection on the metal
KEY = (0.35, 0.0, 1.0)
AMBIENT, DIFFUSE, SKY = 0.50, 0.50, 0.15
REFLECT = 0.25
EDGE = 0.30


def unpack(src):
    """the blend and its textures folder (a zip is unpacked to a temp dir)"""
    if os.path.isdir(src): root = src
    else:
        root = tempfile.mkdtemp(prefix='commando_')
        zipfile.ZipFile(src).extractall(root)
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith('.blend'): return os.path.join(dp, f), os.path.join(dp, 'textures')
    raise FileNotFoundError(f'no .blend under {src}')


def texture(texdir, pos, nrm, uv, tris):
    """the commando_base colour map with the shading baked in (see above), at its own size, 0..1"""
    def load(n, mode='RGB'):
        return np.asarray(Image.open(f'{texdir}/commando_base_{n}.png').convert(mode), np.float32) / 255
    base, nmap = load('BaseColor'), load('Normal')
    metal, rough = load('Metallic', 'L'), load('Roughness', 'L')
    S = base.shape[0]
    N, covered = bake_normals(np.asarray(pos, float), np.asarray(nrm, float), np.asarray(uv, float), np.asarray(tris, int), nmap, S)
    key = np.array(KEY, np.float32); key /= np.linalg.norm(key)
    light = AMBIENT + DIFFUSE * np.clip(N @ key, 0, 1) + SKY * (N[..., 2] * 0.5 + 0.5)
    light = np.where(covered, light, AMBIENT + DIFFUSE * 0.6 + SKY * 0.5)
    refl = REFLECT * metal * np.clip(N[..., 2] * 0.5 + 0.5, 0, 1) ** 3 * np.clip((0.8 - rough) / 0.6, 0, 1) * covered
    nx, ny = nmap[..., 0] * 2 - 1, nmap[..., 1] * 2 - 1
    tilt = np.clip((np.sqrt(nx * nx + ny * ny) - 0.12) / 0.35, 0, 1)
    polish = metal * np.clip((0.55 - rough) / 0.35, 0, 1)
    edge = np.clip(tilt * 0.8 + polish * 0.35, 0, 1) * np.clip(light / (AMBIENT + DIFFUSE + SKY), 0.3, 1)
    return np.clip(base * light[..., None] + (EDGE * edge + refl)[..., None] * np.clip(base * 0.6 + 0.25, 0, 1), 0, 1)


def free_spots(uv, tris, n, size=TEX, cell=8):
    """n cell x cell squares of the texture (pixel corners) no triangle covers, with a margin (uv wrapped into 0..1)"""
    m = Image.new('L', (size, size), 0); d = ImageDraw.Draw(m)
    for t in tris:
        U = uv[t].copy(); U -= np.floor(U.min(0))
        for ox in (0, -1):
            for oy in (0, -1):
                d.polygon([((u + ox) * size, (v + oy) * size) for u, v in U], fill=255)
    used = np.asarray(m) > 0
    out = []
    for y in range(4, size - cell - 4, cell):
        for x in range(4, size - cell - 4, cell):
            if not used[y - 4:y + cell + 4, x - 4:x + cell + 4].any():
                out.append((x, y))
                used[y - 4:y + cell + 4, x - 4:x + cell + 4] = True
                if len(out) == n: return out
    raise ValueError('no free texels for the swatches')


def build(src=SRC):
    """out/weapons/m_commando/{m_commando.pkl, w_m_commando_0.png}"""
    blend, texdir = unpack(src)
    K = brute_kit.Kit(blend)
    pos, nrm, uv, tris, mat = [], [], [], [], []
    for nm in FINAL:
        p = K.piece(nm, [])
        b = len(pos)
        pos.extend(p['pos']); nrm.extend(p['nrm'])               # (piece() divides by 100: the JMS scale to world units)
        uv.extend(np.column_stack([p['uv'][:, 0], 1.0 - p['uv'][:, 1]]))      # image space, v down
        tris.extend(p['tris'] + b); mat.extend(p['mats'][m] for m in p['tmat'])
    pos, nrm, uv, tris = np.array(pos, float), np.array(nrm, float), np.array(uv, float), np.array(tris, int)
    mat = np.array(mat)
    gun = mat == 'commando_base'
    img = texture(texdir, pos, nrm, uv, tris[gun])
    im = Image.fromarray((img * 255).astype(np.uint8)).resize((TEX, TEX), Image.LANCZOS)
    # the swatches: each flat material's corners moved onto its square's middle
    uv = uv.copy()
    for (x, y), (name, rgb) in zip(free_spots(uv, tris[gun], len(SWATCH)), SWATCH.items()):
        im.paste(rgb, (x, y, x + 8, y + 8))
        sel = np.unique(tris[mat == name])
        if not len(sel): continue
        # (each triangle's corners are its own here, piece() unshared: one uv for all of them)
        uv[sel] = ((x + 4) / TEX, (y + 4) / TEX)
    d = f'{OUT}/weapons/{WID}'; os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))              # (the old Commando's files)
    m0 = f'w_{WID}_0.png'
    im.save(f'{d}/{m0}')
    meshes = [dict(material=m0, pos=pos, nrm=nrm, uv=uv, tris=tris)]
    pickle.dump(dict(id=WID, tag=CREDIT, meshes=meshes), open(f'{d}/{WID}.pkl', 'wb'))
    print(WID, 'tris', len(tris), 'bounds', pos.min(0).round(3), pos.max(0).round(3), '->', d)


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else SRC)
