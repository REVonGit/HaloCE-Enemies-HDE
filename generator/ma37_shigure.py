"""Shigure's MA37 (Raw Assets/ma37.zip: 'ma37 rev.blend' + its PBR textures) -> out/weapons/m_ma37: the Marines' and
Brutes' MA37, in place of the Digsite E3 2000 rifle repainted in Reach's colours it was before.

    HCE_MA37_SRC=/path/to/ma37.zip python3 ma37_shigure.py      # or the unzipped folder; marine_arsenal.py runs it

The blend (Blender 5.0) holds the gun as eight objects on one material (body, bolt, cowling, cylinders, display,
display_mount, gas, magazine), the muzzle along +x, up +z, four of them half models with a Mirror modifier
(lib/brute_kit.Kit.piece applies it). They are scaled so the gun is as long as Halo CE's assault rifle (LENGTH) and
moved so the origin is on the pistol grip (GRIP, in the blend's units: the grip is the lowest part of the body, in
front of the magazine: the MA5 line is a bullpup), which is where Halo's weapon frame sits and the hand closes.
One texture: the base colour with the emission (the ammo counter's digits) added, at TEX_SIZE.
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


def texture(texdir):
    """the base colour with the emission added, resized"""
    base = np.asarray(Image.open(f'{texdir}/ma37_body_BaseColor.png').convert('RGB'), np.float32)
    emis = np.asarray(Image.open(f'{texdir}/ma37_body_Emission.png').convert('RGB'), np.float32)
    return Image.fromarray(np.clip(base + emis * 1.5, 0, 255).astype(np.uint8)).resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)


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
    texture(texdir).save(f'{d}/{mat}')
    meshes = [dict(material=mat, pos=np.array(pos, float), nrm=np.array(nrm, float), uv=np.array(uv, float), tris=np.array(tris, int))]
    pickle.dump(dict(id=WID, tag=CREDIT, meshes=meshes), open(f'{d}/{WID}.pkl', 'wb'))
    Q = meshes[0]['pos']
    print(WID, 'tris', len(tris), 'bounds', Q.min(0).round(3), Q.max(0).round(3), '->', d)


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else SRC)
