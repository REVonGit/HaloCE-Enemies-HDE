"""Sketchfab OBJ weapons (CC-BY) -> weapon .pkl in the same layout as extract_weapons.py:
weapon space is Halo's (+x forward, +z up, origin on the hand grip), world units."""
import os, pickle, sys
import numpy as np
from PIL import Image

SK = '/home/claude/enemy/sketchfab'
OUT = '/home/claude/enemy/out/weapons'

def load_obj(path, only=None):
    V, VT, VN = [], [], []
    faces = []          # (group, material, [(v, vt, vn)...])
    grp = mat = None
    for l in open(path, encoding='latin1'):
        if l.startswith('v '): V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith('vt '): VT.append([float(x) for x in l.split()[1:3]])
        elif l.startswith('vn '): VN.append([float(x) for x in l.split()[1:4]])
        elif l.startswith(('o ', 'g ')): grp = l[2:].strip()
        elif l.startswith('usemtl'): mat = l.split(None, 1)[1].strip()
        elif l.startswith('f '):
            if only and grp not in only: continue
            idx = []
            for tok in l.split()[1:]:
                p = (tok.split('/') + ['', ''])[:3]
                idx.append(tuple(int(x) - 1 if x else -1 for x in p))
            faces.append((grp, mat, idx))
    return np.array(V), np.array(VT) if VT else np.zeros((0, 2)), np.array(VN) if VN else np.zeros((0, 3)), faces

def to_meshes(V, VT, VN, faces, matfile, xform, wid):
    by = {}
    for grp, mat, idx in faces:
        by.setdefault(matfile[mat], []).append(idx)
    meshes = []
    for mf, polys in by.items():
        pos, nrm, uv, tris = [], [], [], []
        for idx in polys:
            base = len(pos)
            for v, t, n in idx:
                pos.append(xform(V[v])); uv.append(VT[t] if t >= 0 else (0, 0))
                nrm.append(xform(VN[n], True) if n >= 0 else (0, 0, 1))
            for k in range(1, len(idx) - 1):
                tris.append((base, base + k, base + k + 1))
        uv = np.array(uv, float); uv[:, 1] = 1.0 - uv[:, 1]
        meshes.append(dict(material=f'w_{wid}_{mf}', pos=np.array(pos), nrm=np.array(nrm), uv=uv, tris=np.array(tris)))
    return meshes

def save(wid, meshes, textures, credit):
    d = f'{OUT}/{wid}'; os.makedirs(d, exist_ok=True)
    for mf, im in textures.items():
        im.save(f'{d}/w_{wid}_{mf}')
    pickle.dump(dict(id=wid, tag=credit, meshes=meshes), open(f'{d}/{wid}.pkl', 'wb'))
    P = np.concatenate([m['pos'] for m in meshes])
    print(wid, 'tris', sum(len(m['tris']) for m in meshes), 'bounds', P.min(0).round(3), P.max(0).round(3))

def carbine():
    V, VT, VN, F = load_obj(f'{SK}/carbine/source/cov sniper.obj')
    tex = Image.open(f'{SK}/carbine/textures/wrld_plasmacannon.png').convert('RGB')
    metal = Image.open(f'{SK}/carbine/textures/fp_plasmacannon_metal.png').convert('RGB')
    # the multipurpose map isn't in the download: its faces use the colour map's UVs
    matfile = {'Material': 'body.png', 'Material.001': 'body.png', 'Material.003': 'metal.png'}
    gi = [i for i, f in enumerate(F) if f[0].startswith('grip')]
    gv = np.array([V[v] for i in gi for v, _, _ in F[i][2]])
    grip = gv.mean(0); grip[1] = gv[:, 1].max() - 0.35 * (gv[:, 1].max() - gv[:, 1].min())
    length = V[:, 2].max() - V[:, 2].min()
    s = 0.46 / length
    def xf(p, normal=False):
        p = np.asarray(p, float)
        if normal: return np.array([p[2], p[0], p[1]])
        q = (p - grip) * s
        return np.array([q[2], q[0], q[1]])
    save('plasma_carbine', to_meshes(V, VT, VN, F, matfile, xf, 'plasma_carbine'),
         {'body.png': tex, 'metal.png': metal},
         'Plasma Carbine (Halo CE cut weapon recreation), Sketchfab, CC-BY 4.0')

def beam_rifle():
    V, VT, VN, F = load_obj(f'{SK}/beam/source/untitled.obj', only={'beam_rifle'})
    used = sorted({v for f in F for v, _, _ in f[2]})
    P = V[used]
    tex = Image.open(f'{SK}/beam/textures/beam_rifle2.png').convert('RGB')
    glow = Image.new('RGB', (8, 8), (235, 120, 255))
    matfile = {'beam_rifle_gun': 'body.png', 'plasma_illum': 'glow.png'}
    lo, hi = P.min(0), P.max(0)
    ext = hi - lo
    ax = int(np.argmax(ext))
    # side profile: prongs at +x, scope ridge up (+y), thumbhole grip bar behind the core ring
    grip = np.array([-0.29, -0.03, (lo[2] + hi[2]) / 2])
    s = 0.42 / ext[0]
    def xf(p, normal=False):
        p = np.asarray(p, float)
        if normal: return np.array([p[0], -p[2], p[1]])
        q = (p - grip) * s
        return np.array([q[0], -q[2], q[1]])
    save('beam_rifle', to_meshes(V, VT, VN, F, matfile, xf, 'beam_rifle'), {'body.png': tex, 'glow.png': glow},
         'Covenant Beam Rifle (Halo 2 third-person mesh) by Bornstellar Makes Eternallasting, Sketchfab, CC-BY 4.0')

if __name__ == '__main__':
    carbine()
    beam_rifle()
