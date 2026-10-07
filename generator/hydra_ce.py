"""The Marines' Hydra: HaloDoom Evolved's own Hydra (Hydra_HDE.blend, Halo Infinite's MLRS-1) as a Halo CE gun.

The model keeps the .blend's own UV layout and texture: each part is cut to a CE polygon budget with its UVs kept
(meshtool simplifyuv), and the blend's material (mlrs_default: Base Color x Mixed AO) is baked into one map and
downscaled to Halo CE's 512x512. The UNSC caution and stripe decals ride on top as their own alpha-tested surfaces."""
import os, sys, pickle, subprocess
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hde_ce, bulldog_ce as bc

BLEND = os.environ.get('HCE_HYDRA_BLEND', os.path.join(HERE, 'Hydra_HDE.blend'))
WID = 'm_hydra'
RES = 512
PARTS = {'Hydra': ('body', 1100),                 # receiver, stock, grip, tube housing
         'Hydra.003': ('tubes', 320),             # the six-tube missile pod
         'Hydra.001': ('cover', 110),             # pod cover
         'Hydra.002': ('trigger', 16)}
MAT = 'mlrs_default'
DECALS = (('Hydra', 'unsc_decals_Caution'), ('unsc_decals_Stripes.001', None))


def baked(src):
    """the blend's material as the gun wears it: Base Color x Mixed AO, at CE resolution"""
    col = src.image('mlrs_default_Base_Color.jpg'); ao = src.image('mlrs_default_Mixed_AO.jpg')
    img = col * (0.35 + 0.65 * ao[..., :1])
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.resize((RES, RES), Image.LANCZOS)).astype(np.float32) / 255


def decal_meshes(src, origin):
    """the caution and stripe decals as their own alpha-tested surfaces (the gun's map is shared by its mirrored
    halves, so painting them in would print them twice, one reversed), lifted a hair off the gun, two-sided"""
    out = []
    for obj, mat in DECALS:
        v = src.R.get(obj)
        if v is None: continue
        for k, mn in enumerate(v['mats']):
            if 'decal' not in mn or (mat and mn != mat): continue
            sel = v['tmat'] == k
            cn = src.mats.get(mn, {}).get('color')
            if not sel.any() or not cn: continue
            used = np.unique(v['tris'][sel]); rm = -np.ones(len(v['pos']), int); rm[used] = np.arange(len(used))
            P = (v['pos'][used] - origin) * bc.M2WU; T = rm[v['tris'][sel]]; U = v['uv'][used]
            fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]); vn = np.zeros_like(P)
            for j in range(3): np.add.at(vn, T[:, j], fn)
            vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
            im = src.image(cn, alpha=True)
            name = f'w_{WID}_{len(out) + 1}.png'
            rgba = (np.clip(im, 0, 1) * 255).astype(np.uint8); rgba[..., 3] = np.where(rgba[..., 3] > 110, 255, 0)
            pic = Image.fromarray(rgba, 'RGBA')
            if max(pic.size) > 256: pic = pic.resize((256, 256 * pic.size[1] // pic.size[0]), Image.NEAREST)
            out.append((dict(material=name, pos=P + vn * 0.0008, nrm=vn, uv=np.stack([U[:, 0], 1 - U[:, 1]], 1),
                             tris=np.concatenate([T, T[:, [0, 2, 1]]])), pic))
    return out


def build():
    bc.ensure_tool()
    src = hde_ce.Source(BLEND, maxres=4096)
    P0 = src.R['Hydra']['pos']                    # +x forward, +z up
    g = P0[(P0[:, 2] < -0.04) & (P0[:, 0] > -0.08) & (P0[:, 0] < 0.04)]
    origin = np.array([g[:, 0].mean(), (P0[:, 1].min() + P0[:, 1].max()) / 2, P0[:, 2].min() + 0.075])
    tmpd = os.path.join(bc.WORK, f'{WID}_tmp'); os.makedirs(tmpd, exist_ok=True)
    Ps, Ts, Us = [], [], []; base = 0
    for name, (role, target) in PARTS.items():
        v = src.R[name]
        keep = np.array([v['mats'][int(m)] == MAT for m in v['tmat']])
        T = v['tris'][keep]
        P = (v['pos'] - origin) * bc.M2WU
        bc.wbin(f'{tmpd}/in.bin', P, T)
        with open(f'{tmpd}/in.bin', 'ab') as f: f.write(np.asarray(v['uv'], '<f4').tobytes())
        subprocess.run([bc.TOOL, 'simplifyuv', f'{tmpd}/in.bin', f'{tmpd}/lo.bin', str(target), '0.02'], check=True)
        lp, lt, lu, _ = bc.rbin(f'{tmpd}/lo.bin', uv=True)
        print(f'{role:8s} {len(v["tris"]):6d} -> {len(lt):4d} tris')
        Ps.append(lp); Ts.append(lt + base); Us.append(lu); base += len(lp)
    P, T, U = np.concatenate(Ps), np.concatenate(Ts), np.concatenate(Us)
    UV = np.stack([U[:, 0], 1 - U[:, 1]], 1)     # Blender's v up -> v down, like Halo / IQM
    img = baked(src)
    d = f'{bc.OUT}/weapons/{WID}'; os.makedirs(d, exist_ok=True)
    mat = f'w_{WID}_0.png'
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(f'{d}/{mat}')
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    vn = np.zeros_like(P)
    for k in range(3): np.add.at(vn, T[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    meshes = [dict(material=mat, pos=P, nrm=vn, uv=UV, tris=T)]
    for m, pic in decal_meshes(src, origin):
        pic.save(f'{d}/{m["material"]}'); meshes.append(m)
    pickle.dump(dict(id=WID, tag='hde:Hydra_HDE.blend (its own UVs and texture, at Halo CE resolution)', meshes=meshes),
                open(f'{d}/{WID}.pkl', 'wb'))
    print(WID, len(T), 'tris', P.min(0).round(3), P.max(0).round(3))


if __name__ == '__main__':
    build()
