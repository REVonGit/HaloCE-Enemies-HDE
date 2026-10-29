"""The Needle Javelin's Halo CE stand-in: the needle rifle model the pack's author supplied (Raw Assets/needle_rifle.zip:
needle_rifle_rev.fbx, binary FBX from Blender, with PBR textures in texture/) -> out/weapons/needle_rifle, and the
overlay models the Elites and Jackals hold it by (HaloDoom Evolved's Halo_NeedlerJavelin, picked up or given:
build_pack.add_needle_rifle).

    HCE_NEEDLE_RIFLE_SRC=/path/to/needle_rifle.zip python3 needle_rifle_ce.py    # or the unzipped folder
    python3 needle_rifle_ce.py overlay [Char ...]      # after blood_kit.py: <Char>_w_needle_rifle.iqm (OVERLAY_CHARS)

The FBX holds the gun as six meshes (PARTS: base, top, barrel, needles, magwell, magazine), mirrors applied, read by
lib/fbx_bin.py; Y-up in centimetres, turned to the muzzle along +x, up +z and divided by SRC_UNIT (load_fbx). The gun
is scaled to LENGTH (Halo CE weapon units: between the CMT carbine's 0.41 and Halo 2's beam rifle's 0.43, the
two-handed Covenant rifles the Elites already carry) and moved so the origin is on the grip (GRIP: the bar behind the
trigger hole, where Halo's weapon frame sits and the hand closes).

Its six materials become two, as Halo CE's needler has: the body texture (TEX: a 2x2 atlas of the three PBR
materials' colour maps, each at half its size: the grey metal, the shell, the blue glass; their own UVs moved into
their cells), with Halo CE-style shading baked in from the normal, metallic and roughness maps (texture(); the same
idea as ma37_shigure.py's), and a glow texture of flat swatches for the needles, their core and the magazine's crystal
(GLOW: their materials have no image, only colours), which the pack draws fullbright (build_pack.py: brightmap).
"""
import os, sys, json, pickle, shutil, zipfile, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from hce_paths import OUT
import fbx_bin
from ma37_shigure import bake_normals, _blur

SRC = os.environ.get('HCE_NEEDLE_RIFLE_SRC', os.path.join(HERE, '..', 'Raw Assets', 'needle_rifle.zip'))
WID = 'needle_rifle'
PARTS = ('base', 'top', 'barrel', 'needles', 'magwell', 'magazine')
LENGTH = 0.42               # muzzle to stock, Halo CE world units
SRC_UNIT = 3.3             # FBX centimetres per model unit (its objects' export scale; GRIP and the bake are in these)
GRIP = (0.6, 0.0, 1.5)      # the weapon origin in model units: the middle of the grip bar
TEX = 1024                  # the body atlas; each cell CELL px, its picture inset PAD px (no bleeding between cells)
CELL, PAD = 512, 8
# PBR material -> (texture file prefix, atlas cell (column, row), the part of its UV square it uses (u0, v0, u1, v1 in
# image space, v down; None = all of it))
ATLAS = {'needle_rifle': ('needle_rifle_', (0, 0), None),
         'needle_rifle_shell': ('needle_rifle_shell_', (1, 0), None),
         'needle_rifle_blue': ('needle_rifle_blue_', (0, 1), (0.25, 0.02, 0.83, 0.85))}
# image-less materials -> their glow swatch (RGB): the user's emission colours, as Halo CE's needler glows
GLOW = {'needler luminous': (240, 60, 210), 'needler ammo crystal': (255, 40, 200), 'needler core': (255, 205, 245)}
GLOW_SWATCH = {'needler luminous': (0, 0), 'needler ammo crystal': (1, 0), 'needler core': (0, 1)}   # 8x8 cells of a 16x16
CREDIT = 'needle rifle model supplied by the pack author (REVonGit)'
# the bodies that hold it (their skeleton's gun hand, recovered from a gun baked on it: marine_arsenal.hand_frame)
OVERLAY_CHARS = {'Elite': 'plasma_rifle', 'EliteSpecial': 'plasma_rifle', 'Draeth': 'plasma_rifle',
                 'Jackal': 'plasma_pistol', 'JackalMajor': 'plasma_rifle', 'H2Jackal': 'plasma_rifle'}

# shading baked into the colour maps (their own PBR set is flat; Halo CE's guns carry their lighting in the texture):
# a key light from above and a little in front (no sideways part: the mirrored halves share texels), ambient and a sky
# fill, bevels (where the normal map tilts) and polished metal lit, a soft sky reflection on the metal
KEY = (0.35, 0.0, 1.0)
AMBIENT, DIFFUSE, SKY = 0.55, 0.45, 0.15
REFLECT = 0.25
EDGE = 0.30


def unpack(src):
    """the FBX and its texture folder (a zip is unpacked to a temp dir)"""
    if os.path.isdir(src): root = src
    else:
        root = tempfile.mkdtemp(prefix='needle_rifle_')
        zipfile.ZipFile(src).extractall(root)
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith('.fbx'):
                td = os.path.join(dp, 'texture')
                return os.path.join(dp, f), td if os.path.isdir(td) else os.path.join(dp, 'textures')
    raise FileNotFoundError(f'no .fbx under {src}')


def load_fbx(fbx):
    """the PARTS as meshes in the gun's frame (muzzle +x, up +z, in SRC_UNIT units): the FBX is Y-up in centimetres
    (Blender's export: x stays, its y is our up, its z our -y)"""
    by = {m['name']: m for m in fbx_bin.meshes(fbx_bin.load(fbx))}
    missing = [n for n in PARTS if n not in by]
    if missing: raise SystemExit(f'{fbx}: no mesh {missing} (has {sorted(by)})')
    C = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)      # FBX (x, y, z) -> (x, -z, y)
    parts = []
    for n in PARTS:
        m = dict(by[n]); m['pos'] = m['pos'] @ C.T / SRC_UNIT; m['nrm'] = m['nrm'] @ C.T
        parts.append(m)
    return parts


def cell_map(mat):
    """(scale, offset) taking a material's image-space UV (v down) to the atlas's: uv * scale + offset"""
    _, (cx, cy), crop = ATLAS[mat]
    u0, v0, u1, v1 = crop or (0, 0, 1, 1)
    k = (CELL - 2 * PAD) / max(u1 - u0, v1 - v0) / TEX
    off = np.array([(cx * CELL + PAD) / TEX - u0 * k, (cy * CELL + PAD) / TEX - v0 * k])
    return k, off


def bake_cell(texdir, mat, pos, nrm, uv, tris):
    """one material's colour map with the shading baked in (see above), at its source size"""
    pre = ATLAS[mat][0]
    def load(n, mode='RGB'):
        """one of the material's PBR maps as floats 0..1"""
        return np.asarray(Image.open(f'{texdir}/{pre}{n}.png').convert(mode), np.float32) / 255
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
    out = base * light[..., None] + (EDGE * edge + refl)[..., None] * np.clip(base * 0.6 + 0.25, 0, 1)
    return np.clip(out, 0, 1)


def body_texture(texdir, parts):
    """the 2x2 atlas: each ATLAS material's baked colour map shrunk into its cell (edges padded outwards)"""
    atlas = np.zeros((TEX, TEX, 3), np.float32)
    for mat, (_, (cx, cy), crop) in ATLAS.items():
        P, Nn, U, T = [], [], [], []
        for p in parts:
            sel = [i for i, m in enumerate(p['tmat']) if p['mats'][m] == mat]
            if not sel: continue
            t = p['tris'][sel]; b = sum(len(x) for x in P)
            P.append(p['pos']); Nn.append(p['nrm']); U.append(p['uvimg']); T.append(t + b)
        img = bake_cell(texdir, mat, np.concatenate(P), np.concatenate(Nn), np.concatenate(U), np.concatenate(T))
        S = img.shape[0]
        u0, v0, u1, v1 = crop or (0, 0, 1, 1)
        x0, y0 = int(u0 * S), int(v0 * S); w = int(max(u1 - u0, v1 - v0) * S)
        sub = img[y0:y0 + w, x0:x0 + w]
        sub = np.pad(sub, ((0, w - sub.shape[0]), (0, w - sub.shape[1]), (0, 0)), mode='edge')
        n = CELL - 2 * PAD
        small = np.asarray(Image.fromarray((sub * 255).astype(np.uint8)).resize((n, n), Image.LANCZOS), np.float32) / 255
        atlas[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = np.pad(small, ((PAD, PAD), (PAD, PAD), (0, 0)), mode='edge')
    # the free cell: the grey metal's mean, so nothing samples black
    atlas[CELL:, CELL:] = atlas[:CELL, :CELL].reshape(-1, 3).mean(0)
    return Image.fromarray((atlas * 255).astype(np.uint8))


def glow_texture():
    """16x16: one 8x8 swatch per GLOW material"""
    g = np.zeros((16, 16, 3), np.uint8); g[:] = GLOW['needler luminous']
    for m, (cx, cy) in GLOW_SWATCH.items(): g[cy * 8:(cy + 1) * 8, cx * 8:(cx + 1) * 8] = GLOW[m]
    return Image.fromarray(g)


def build(src=SRC):
    """out/weapons/needle_rifle/{needle_rifle.pkl, w_needle_rifle_body.png, w_needle_rifle_glow.png}"""
    fbx, texdir = unpack(src)
    parts = load_fbx(fbx)
    P = np.concatenate([p['pos'] for p in parts])
    s = LENGTH / np.ptp(P[:, 0])
    g = np.array(GRIP)
    for p in parts:
        p['uvimg'] = np.column_stack([p['uv'][:, 0], 1.0 - p['uv'][:, 1]])
    d = f'{OUT}/weapons/{WID}'; os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    body, glow = f'w_{WID}_body.png', f'w_{WID}_glow.png'
    body_texture(texdir, parts).save(f'{d}/{body}')
    glow_texture().save(f'{d}/{glow}')
    out = {body: dict(pos=[], nrm=[], uv=[], tris=[]), glow: dict(pos=[], nrm=[], uv=[], tris=[])}
    for p in parts:
        for ti, t in enumerate(p['tris']):
            mat = p['mats'][p['tmat'][ti]]
            if mat in ATLAS:
                k, off = cell_map(mat); dst = out[body]; uv = p['uvimg'][t] * k + off
            elif mat in GLOW:
                cx, cy = GLOW_SWATCH[mat]; dst = out[glow]; uv = np.tile([(cx * 8 + 4) / 16, (cy * 8 + 4) / 16], (3, 1))
            else: raise SystemExit(f'{p["name"]}: material {mat!r} is neither in ATLAS nor in GLOW')
            b = len(dst['pos'])
            dst['pos'].extend((p['pos'][t] - g) * s); dst['nrm'].extend(p['nrm'][t]); dst['uv'].extend(uv); dst['tris'].append([b, b + 1, b + 2])
    meshes = [dict(material=m, pos=np.array(v['pos'], float), nrm=np.array(v['nrm'], float), uv=np.array(v['uv'], float),
                   tris=np.array(v['tris'], int)) for m, v in out.items()]
    pickle.dump(dict(id=WID, tag=CREDIT, meshes=meshes), open(f'{d}/{WID}.pkl', 'wb'))
    Q = np.concatenate([m['pos'] for m in meshes])
    print(WID, 'tris', sum(len(m['tris']) for m in meshes), 'bounds', Q.min(0).round(3), Q.max(0).round(3), '->', d)


def overlay(char, ref):
    """the needle rifle as an overlay model on a character's own skeleton, in its gun hand exactly where it holds its
    baked gun 'ref' (marine_arsenal.hand_frame), listed in the body's json 'arsenal' as plasma_caster_ce.overlay does"""
    from iqm import write_iqm
    from marine_arsenal import hand_frame
    R, t, jn, joints = hand_frame(char, ref)
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
        for c in sys.argv[2:] or list(OVERLAY_CHARS):
            if os.path.exists(f'{OUT}/models/{c}/{c}.json'): overlay(c, OVERLAY_CHARS[c])
    else: build(sys.argv[1] if len(sys.argv) > 1 else SRC)
