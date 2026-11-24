"""The DMR's model: a re-model of the pre-Xbox (E3 2000) Halo assault rifle (Raw Assets/
halo-pre-xbox-assault-rifle-re-model.zip: source/HaloAR_OG.obj, one material, UV-mapped onto Halo CE's assault rifle
texture, the MA5B's) -> out/weapons/m_dmr, in place of the Digsite E3 2000 rifle itself (its JMS, 432 vertices, and its
own texture) it was before.

    HCE_DMR_SRC=/path/to/halo-pre-xbox-assault-rifle-re-model.zip python3 dmr_e3_remodel.py   # marine_arsenal.py runs it

The OBJ is in centimetres, centred on the gun, the muzzle along +x, up +y. It is the Digsite rifle re-made, so it is
put where that one was in Halo's weapon space (+x forward, +z up, the origin on the pistol grip): OBJ_TO_WEAPON, the
similarity that lays it on the Digsite JMS (data/digsite/weapons/assault_rifle/99_e3/models/h assault rifle.JMS),
fitted once by ICP over both surfaces (scale, then a turn of under a degree; 3 mm apart on average). Its texture is
the MA5B's (out/weapons/assault_rifle/w_assault_rifle_0.png, extract_weapons.py) as it is, under the DMR's material
name (w_m_dmr_0.png), so the packs' DMR overlays keep their skins.
"""
import os, sys, pickle, zipfile, shutil
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from hce_paths import OUT

SRC = os.environ.get('HCE_DMR_SRC', os.path.join(HERE, '..', 'Raw Assets', 'halo-pre-xbox-assault-rifle-re-model.zip'))
OBJ = 'source/HaloAR_OG.obj'
WID = 'm_dmr'
MAT = 'w_m_dmr_0.png'
TEXTURE = os.path.join(OUT, 'weapons', 'assault_rifle', 'w_assault_rifle_0.png')     # the MA5B's
CREDIT = 'Halo pre-Xbox assault rifle re-model'
# OBJ (cm) -> weapon space: p' = S * R @ p + T
S = 0.004274348105890088
R = np.array([[0.99990634, 0.01367797, 0.00047115],
              [0.00044856, 0.00165455, -0.99999853],
              [-0.01367873, 0.99990508, 0.00164826]])
T = np.array([0.0671322, 0.00242342, 0.034348])


def read_obj(src):
    """the OBJ's text, from the zip or a folder"""
    if os.path.isdir(src): return open(os.path.join(src, OBJ)).read()
    return zipfile.ZipFile(src).read(OBJ).decode('latin1')


def mesh(text):
    """one mesh: a vertex per position/UV/normal corner the faces use, polygons fanned into triangles (the OBJ's
    winding is the packs' already: counter-clockwise about the normal), UVs flipped to image space (v down)"""
    v, vt, vn, faces = [], [], [], []
    for line in text.splitlines():
        a = line.split()
        if not a: continue
        if a[0] == 'v': v.append([float(x) for x in a[1:4]])
        elif a[0] == 'vt': vt.append([float(x) for x in a[1:3]])
        elif a[0] == 'vn': vn.append([float(x) for x in a[1:4]])
        elif a[0] == 'f': faces.append([tuple(int(q) - 1 for q in p.split('/')) for p in a[1:]])
    v, vt, vn = np.array(v), np.array(vt), np.array(vn)
    corners, tris = {}, []
    for f in faces:
        ids = [corners.setdefault(c, len(corners)) for c in f]
        tris += [[ids[0], ids[i], ids[i + 1]] for i in range(1, len(ids) - 1)]
    C = np.array(list(corners))
    pos = S * v[C[:, 0]] @ R.T + T
    nrm = vn[C[:, 2]] @ R.T
    # (five of its triangles have no area, their corners no normal: left out; a few more of its normals are zero-length:
    # those corners take the area-weighted normal of their triangles)
    tr = np.array(tris, int); fn = np.cross(pos[tr[:, 1]] - pos[tr[:, 0]], pos[tr[:, 2]] - pos[tr[:, 0]])
    keep = np.linalg.norm(fn, axis=1) > 1e-12; tr, fn = tr[keep], fn[keep]
    acc = np.zeros_like(pos)
    for k in range(3): np.add.at(acc, tr[:, k], fn)
    bad = np.linalg.norm(nrm, axis=1) < 1e-6; nrm[bad] = acc[bad]
    nrm[np.linalg.norm(nrm, axis=1) < 1e-12] = (0, 0, 1)             # (corners only the dropped triangles used)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    uv = np.column_stack([vt[C[:, 1], 0], 1.0 - vt[C[:, 1], 1]])
    return dict(material=MAT, pos=pos, nrm=nrm, uv=uv, tris=tr)


def build(src=SRC):
    """out/weapons/m_dmr/{m_dmr.pkl, w_m_dmr_0.png}"""
    m = mesh(read_obj(src))
    d = f'{OUT}/weapons/{WID}'; os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))              # (the Digsite rifle's files)
    shutil.copy(TEXTURE, f'{d}/{MAT}')
    pickle.dump(dict(id=WID, tag=CREDIT, meshes=[m]), open(f'{d}/{WID}.pkl', 'wb'))
    print(WID, 'tris', len(m['tris']), 'bounds', m['pos'].min(0).round(3), m['pos'].max(0).round(3), '->', d)


if __name__ == '__main__':
    build(*sys.argv[1:2])
