"""Blood on the body: a blood-splatter overlay for every enemy that bleeds, worn more heavily as it is shot.

    python3 blood_kit.py [Char ...]     # out/models/<Char>/ -> <Char>_blood1..3.iqm + blood<k>_<material>.png

Run after gore_kit.py (it uses the final surface list). For each character:

* overlay models <Char>_blood1.iqm .. _blood3.iqm: the body's own surfaces (same skeleton and weights, so it moves
  with the body as a model attachment), pushed a hair out along the normals so it sits on the skin; guns, gore
  stumps and the shield are left empty. Model k's materials are the stage-k blood textures.
* blood textures blood<k>_<material>.png, one per body material and stage: transparent, with splats of the race's
  blood where shots landed. The hits are placed on the body in 3D (random points on its surface, weighted by area)
  and painted into texture space through a per-texel map of the model's surface (its triangles rasterised over
  their UVs), so a splat crosses texture seams and covers neighbouring parts the way a real spray would: a ragged
  wet blot with a darker core and lighter edges, and drips running down from it. Stage 1 has 5 hits, stage 2
  adds 7, stage 3 adds 10 more.
* json 'blood': the overlay models and textures. build_pack.py attaches them at run time (HCE_BloodStage: model
  attachment 7, swapped for the next stage as the enemy takes more damage once its shields are down).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, zlib
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from hce_paths import OUT
STAGE_HITS = (5, 7, 10)              # new hits per stage
PUSH = 0.004                          # world units the overlay sits out from the skin
TEX = 256                             # blood texture size
NO_BLOOD = {'Sentinel'}


def blood_colour(char):
    import build_pack as bp
    c = bp.BLOOD.get(char)
    return None if not c else np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0


def surface_map(meshes, mat, size):
    """per texel of material 'mat': model-space position and normal (posed bind), and coverage"""
    from preview import skin
    W = H = size
    P = np.zeros((H, W, 3), np.float32); N = np.zeros((H, W, 3), np.float32); hit = np.zeros((H, W), bool)
    for m in meshes:
        if m['material'] != mat or not len(m['tris']): continue
        uv = m['uv'] % 1.0 * np.array([W - 1, H - 1])
        for t in m['tris']:
            p = uv[t]
            x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
            if x1 - x0 > W * 0.6 or y1 - y0 > H * 0.6: continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            v0, v1 = p[1] - p[0], p[2] - p[0]
            den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-9: continue
            dx, dy = xs - p[0][0], ys - p[0][1]
            b1 = (dx * v1[1] - v1[0] * dy) / den; b2 = (v0[0] * dy - dx * v0[1]) / den; b0 = 1 - b1 - b2
            ins = (b0 >= -0.03) & (b1 >= -0.03) & (b2 >= -0.03)
            xi, yi = xs[ins] % W, ys[ins] % H
            bw = np.stack([b0[ins], b1[ins], b2[ins]], 1)
            P[yi, xi] = bw @ m['pos'][t]; N[yi, xi] = bw @ m['nrm'][t]; hit[yi, xi] = True
    return P, N, hit


def noise3(p, seed, scale):
    """cheap smooth 3D value noise at points p (N,3)"""
    rng = np.random.default_rng(seed)
    g = rng.random((17, 17, 17))
    q = (p / scale) % 16
    i = np.floor(q).astype(int); f = q - i; f = f * f * (3 - 2 * f)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * g[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out


def process(char):
    od = f'{OUT}/models/{char}'
    jp = f'{od}/{char}.json'
    if not os.path.exists(jp): print(char, 'missing'); return
    col = blood_colour(char)
    if col is None or char in NO_BLOOD: print(char, 'no blood'); return
    meta = json.load(open(jp))
    joints, meshes, _ = read_iqm(f'{od}/{char}.iqm')
    mw = list(meta.get('mesh_weapon') or []) + [None] * len(meshes)
    stubs = {d['stub'] for d in meta.get('gore', {}).get('limbs', {}).values()}
    names = meta.get('mesh_names') or [m['name'] for m in meshes]
    def body(si, m):
        mat = m['material'].lower()
        return not (mw[si] or si in stubs or 'shield' in mat or 'shield' in names[si] or mat.startswith('w_') or 'gore' in mat) and len(m['tris'])
    body_ix = [si for si, m in enumerate(meshes) if body(si, m)]
    # hits on the body surface, area-weighted, same for every stage (cumulative)
    rng = np.random.default_rng(zlib.crc32(char.encode()))
    tri_p, tri_a = [], []
    for si in body_ix:
        m = meshes[si]; v = m['pos'][m['tris']]
        a = np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1) * 0.5
        tri_p.append(v); tri_a.append(a)
    tri_p = np.concatenate(tri_p); tri_a = np.concatenate(tri_a)
    allp = tri_p.reshape(-1, 3)
    height = allp[:, 2].max() - allp[:, 2].min()
    nh = sum(STAGE_HITS)
    pick = rng.choice(len(tri_a), nh, p=tri_a / tri_a.sum())
    r1, r2 = rng.random(nh), rng.random(nh)
    s1 = np.sqrt(r1)
    centres = (tri_p[pick, 0] * (1 - s1)[:, None] + tri_p[pick, 1] * (s1 * (1 - r2))[:, None] + tri_p[pick, 2] * (s1 * r2)[:, None])
    radii = height * rng.uniform(0.04, 0.085, nh)
    drips = rng.integers(1, 5, nh)
    mats = sorted({meshes[si]['material'] for si in body_ix})
    stage_end = np.cumsum(STAGE_HITS)
    tex_files = {}
    for mat in mats:
        P, N, hit = surface_map(meshes, mat, TEX)
        if not hit.any(): continue
        flat = P[hit]
        # blot field: nearest-ish of the hits, roughened by noise
        rough = noise3(flat, 3, height * 0.02) * 0.55 + noise3(flat, 5, height * 0.006) * 0.3
        shade = noise3(flat, 9, height * 0.01)
        for k in range(3):
            field = np.zeros(len(flat))
            for h in range(stage_end[k]):
                c, r = centres[h], radii[h]
                d = np.linalg.norm(flat - c, axis=1) / r
                field = np.maximum(field, 1.25 - d)
                # drips: thin runs straight down from the blot
                for j in range(drips[h]):
                    off = (rng_d := np.random.default_rng(h * 7 + j)).uniform(-0.6, 0.6, 2) * r
                    ln = r * rng_d.uniform(1.5, 3.5)
                    w = r * rng_d.uniform(0.12, 0.22)
                    dxy = np.linalg.norm(flat[:, :2] - (c[:2] + off), axis=1)
                    below = (c[2] - flat[:, 2])
                    run = (below > 0) & (below < ln)
                    taper = 1 - np.clip(below / ln, 0, 1) * 0.6
                    field = np.maximum(field, np.where(run, 1.2 - dxy / (w * taper), 0))
            v = field + (rough - 0.45)
            a = v > 0.55
            core = np.clip((v - 0.55) / 0.5, 0, 1)
            rgb = col[None] * (0.8 + 0.55 * shade[:, None]) * (1 - 0.35 * core[:, None]) + (shade[:, None] > 0.85) * 0.18
            img = np.zeros((TEX, TEX, 4), np.uint8)
            px = np.zeros((len(flat), 4))
            px[:, :3] = np.clip(rgb, 0, 1) * 255; px[:, 3] = a * 255
            img[hit] = px.astype(np.uint8)
            fn = f'blood{k + 1}_{os.path.splitext(mat)[0]}.png'
            Image.fromarray(img, 'RGBA').save(f'{od}/{fn}')
            tex_files.setdefault(k, {})[mat] = fn
    # overlay models: body surfaces pushed out along the normals; everything else empty
    models = []
    for k in range(3):
        gm = []
        for si, m in enumerate(meshes):
            if si in body_ix and m['material'] in tex_files.get(k, {}):
                gm.append(dict(m, name=names[si], material=tex_files[k][m['material']], pos=m['pos'] + m['nrm'] * PUSH))
            else:
                gm.append(dict(name=names[si], material='hce_noblood.png', pos=np.zeros((0, 3)), nrm=np.zeros((0, 3)), uv=np.zeros((0, 2)),
                               bidx=np.zeros((0, 4), np.uint8), bw=np.zeros((0, 4), np.uint8), tris=np.zeros((0, 3), int)))
        # an attachment takes its bones from the body (model 0): one bind frame is all it needs
        bind = [[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]]
        fn = f'{char}_blood{k + 1}.iqm'
        write_iqm(f'{od}/{fn}', joints, gm, [dict(name='bind', fps=30.0, loop=True, frames=bind)])
        models.append(fn)
    meta['blood'] = dict(models=models, textures=sorted({f for d in tex_files.values() for f in d.values()}),
                         surfaces=[si for si in body_ix])
    json.dump(meta, open(jp, 'w'), indent=1)
    print(f'{char:14s} blood: {len(body_ix)} surfaces, {len(mats)} materials, {len(meta["blood"]["textures"])} textures')


if __name__ == '__main__':
    chars = sys.argv[1:] or sorted(d for d in os.listdir(f'{OUT}/models') if os.path.exists(f'{OUT}/models/{d}/{d}.json') and os.path.exists(f'{OUT}/models/{d}/{d}.iqm'))
    for c in chars: process(c)
