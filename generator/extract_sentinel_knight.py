"""The Sentinel Knight (blackandfan's Halo 2 tag pack, 'H2EK-Tags') -> $HCE_OUT/models/SentinelKnight

    HCE_H2_TAGPACK=/path/to/H2EK-Tags python3 extract_sentinel_knight.py

The tag pack ships its sources beside its tags (data/objects/characters/sentinel_knight): the render model as a JMS
(version 8210: 97 nodes, 15k vertices, four shaders), its animations as JMA/JMM (version 16395) and its textures as
TIFFs. Both formats hold model-space transforms with standard (x, y, z, w) quaternions; the IQM gets each node's bind
pose and every frame made local to its parent. Animations: the full-body ones (JMA/JMM: idle, walks and runs, melee,
dives, evades, flinches, deaths, taunts, berserk, the phase into and out of the ground); the JMO overlays (aim, fire)
are left out. Textures: each shader's diffuse with its change-colour map's primary channel tinted per rank (the
biped's change colours: minor, major, commander) and its self-illumination as a brightmap (_bm).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import glob, json, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
from h2jms import read_jms, read_jma
from halomodel import qmul, qrot, qconj
from iqm import write_iqm
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')

PACK = os.environ.get('HCE_H2_TAGPACK', 'H2EK-Tags')        # blackandfan's Halo 2 tag pack (its tags/ and data/ folders)
SRC = f'{PACK}/data/objects/characters/sentinel_knight'
TAGS = f'{PACK}/tags/objects/characters/sentinel_knight'
DST = f'{OUT}/models/SentinelKnight'
# shader -> (diffuse, change colour, self-illumination) under bitmaps/
SHADERS = {'Knight': ('sentinel_diffuse', 'sentinel_xf', 'sentinel_illum'),
           'SuperSentinel': ('sentinel_03_df', 'sentinel_03_xf', 'sentinel_03_illum'),
           'Monitor': ('monitor_01_df', 'monitor_01_xf', 'monitor_01_illum'),
           'Core': (None, None, None)}
TEX = 512
# the Knight's right forearm is missing from the model (no geometry from the elbow, b_r_forearm, to b_r_hand: Halo 2
# put a separate weapon object there). Its arm guns take its place: the Halo Infinite Forerunner weapons of
# promethean_ce.py, each laid along the forearm from just behind the elbow, its top facing the way the Knight looks
# when it raises the arm to aim, skinned to b_r_gun (the bone its primary_weapon marker rides). gun -> length (WU)
ARM_GUNS = {'light_rifle': 0.46, 'scattershot': 0.42, 'binary_rifle': 0.60, 'suppressor': 0.44}
LIGHT_GROW = 5                  # the guns' lights grown to this many texels across (of 512)
GUN_LOOK = 'SuperSentinel'     # the material the guns' colouring is matched to: the upper arm's, which the gun continues
ARM_BACK = 0.03                 # how far behind the elbow the gun starts (it caps the joint)
LOOP = ('idle', 'walk_', 'move_', 'airborne', 'look')
# source animation -> the pack's name (build_pack.anim_table; '%N' numbers a name's variants). The JMO overlays (aim,
# fire, soft flinches) are left out
ANIM_NAMES = {'any any idle var0.JMM': 'stand pistol idle',
              'any any move_front.JMA': 'stand pistol move-front', 'any any move_back.JMA': 'stand pistol move-back',
              'any any move_left.JMA': 'stand pistol move-left', 'any any move_right.JMA': 'stand pistol move-right',
              'any any walk_front.JMA': 'stand pistol low-move',
              'any any melee var1.JMA': 'stand pistol melee%0', 'any any melee var2.JMA': 'stand pistol melee%1',
              'any any melee var3.JMA': 'stand pistol melee%2', 'any any smash_left.JMA': 'stand pistol melee%3',
              'any any smash_right.JMA': 'stand pistol melee%4',
              'any any dive_left.JMA': 'stand pistol dive-left', 'any any dive_right.JMA': 'stand pistol dive-right',
              'any any evade_left.JMA': 'stand pistol evade-left', 'any any evade_right.JMA': 'stand pistol evade-right',
              'any any go_berserk.JMA': 'stand pistol berserk', 'any any charge_front.JMA': 'stand pistol charge-front',
              'any any taunt var1.JMM': 'stand pistol celebrate%0', 'any any taunt var2.JMM': 'stand pistol celebrate%1',
              'any any airborne.JMA': 'stand pistol airborne', 'any any land_soft.JMA': 'stand pistol land-soft',
              'any any land_hard.JMA': 'stand pistol land-hard',
              'any any leap_start.JMA': 'stand pistol leap-start', 'any any leap_airborne.JMA': 'stand pistol leap-airborne',
              'any any leap_melee.JMA': 'stand pistol leap-melee',
              'any any airborne_dead.JMA': 'stand airborne-dead', 'any any landing_dead.JMA': 'stand landing-dead',
              'h_ping front gut var1.JMA': 'h-ping front gut', 'h_ping front head var1.JMA': 'h-ping front head',
              'h_ping back gut var1.JMA': 'h-ping back gut', 'h_ping left gut var1.JMA': 'h-ping left gut',
              'h_ping right gut var1.JMA': 'h-ping right gut', 'h_ping left head var1.JMA': 'h-ping left head',
              'h_ping right head var1.JMA': 'h-ping right head',
              'h_ping front l_leg.JMA': 'h-ping front l-leg', 'h_ping front r_leg.JMA': 'h-ping front r-leg',
              # the Knight's own: sinking into the ground and rising out of it somewhere else (its phase), its rebirth
              'any any phase_into_ground.JMM': 'knight phase-out', 'any any phase_from_ground.JMM': 'knight phase-in',
              'any any resurrect_from_ground.JMM': 'knight resurrect'}
# the core (the ball at the chest, the 'Core' shader): its colour rolled per Knight from the rank's palette, cold for
# the grey Knights (minor, major), warm for the gold commanders; drawn with templates/shaders/core.fp (plasma bands,
# pulse, hot rim, a cube-map reflection) and fullbright
CORES = {'cold': {'cyan': (0.20, 0.85, 1.00), 'ice': (0.45, 0.65, 1.00), 'violet': (0.58, 0.38, 1.00), 'teal': (0.12, 0.95, 0.72)},
         'warm': {'orange': (1.00, 0.52, 0.10), 'amber': (1.00, 0.76, 0.22), 'red': (1.00, 0.26, 0.12), 'gold': (1.00, 0.88, 0.45)}}
CORE_PALETTE = {'minor': 'cold', 'major': 'cold', 'commander': 'warm'}


def local_frames(T, Q, parents):
    """model-space (F, N, 3/4) transforms -> parent-relative"""
    LT = np.zeros_like(T); LQ = np.zeros_like(Q)
    for k, p in enumerate(parents):
        if p < 0: LT[:, k] = T[:, k]; LQ[:, k] = Q[:, k]; continue
        for f in range(len(T)):
            iq = qconj(Q[f, p])
            LT[f, k] = qrot(iq, T[f, k] - T[f, p]); LQ[f, k] = qmul(iq, Q[f, k])
    n = np.linalg.norm(LQ, axis=-1, keepdims=True)
    return LT, LQ / np.where(n > 0, n, 1)


def bake(shader, rank, colour):
    """diffuse tinted by the change-colour map's primary channel -> its file name (and the brightmap beside it)"""
    df, xf, il = SHADERS[shader]
    fn = f'{shader}_{rank}.png'
    if df is None:                      # the core: one skin per colour of the rank's palette (the first is the default)
        names = list(CORES[CORE_PALETTE[rank]])
        for nm in names:
            c = np.array(CORES[CORE_PALETTE[rank]][nm])
            Image.new('RGB', (32, 32), tuple(int(v * 255) for v in c)).save(f'{DST}/core_{nm}.png')
            Image.new('L', (32, 32), 255).save(f'{DST}/core_{nm}_bm.png')
        return f'core_{names[0]}.png'
    def load(n, mode):
        f = next(iter(glob.glob(f'{SRC}/bitmaps/{n}.*')), None)
        return Image.open(f).convert(mode).resize((TEX, TEX), Image.LANCZOS) if f else None
    d = np.asarray(load(df, 'RGB')).astype(np.float64) / 255
    x = load(xf, 'RGBA')
    if x is not None:
        m = np.asarray(x).astype(np.float64)[..., :1] / 255
        d = d * (1 - m) + d * np.array(colour) * m * 1.25
    Image.fromarray((np.clip(d, 0, 1) * 255).astype(np.uint8)).save(f'{DST}/{fn}')
    i = load(il, 'L')
    if i is not None: i.save(f'{DST}/{shader}_{rank}_bm.png')
    return fn


def gun_skin(src, rank, colour):
    """a Forerunner arm gun's baked texture in the Knight's own colouring, as its upper arm (GUN_LOOK, the
    'SuperSentinel' shader) wears it: the gun's brightness remapped onto the rank's texture of that material (quantile by quantile over the
    unlit texels, so the same darks, mids and highlights), coloured with that texture's average tint (the rank's
    change colour mixed in as on the body); the gun's lights keep the blend's emission colours (blue, violet,
    green), kept in its brightmap -> the file name"""
    base = os.path.basename(src)[:-4]; fn = f'{base}_{rank}.png'
    g = np.asarray(Image.open(src).convert('RGB')).astype(np.float64) / 255
    bmf = src[:-4] + '_bm.png'
    bm = np.asarray(Image.open(bmf).convert('L')).astype(np.float64)[..., None] / 255 if os.path.exists(bmf) else np.zeros(g.shape[:2] + (1,))
    k = np.asarray(Image.open(f'{DST}/{GUN_LOOK}_{rank}.png').convert('RGB')).astype(np.float64) / 255
    kb = np.asarray(Image.open(f'{DST}/{GUN_LOOK}_{rank}_bm.png').convert('L').resize(k.shape[1::-1])).astype(np.float64) / 255
    kl = k.mean(2)[kb < 0.2]; tint = k[kb < 0.2].mean(0); tint = tint / tint.mean()
    L = g.mean(2); unlit = bm[..., 0] < 0.2
    qs = np.linspace(0, 100, 101)
    Lm = np.interp(L, np.percentile(L[unlit], qs), np.percentile(kl, qs))
    out = Lm[..., None] * tint
    # the lights keep the blend's own glow colours, at full brightness and grown a texel or two (in Blender the bloom
    # of their huge emission strength makes them read; a flat texture needs the size instead)
    from scipy import ndimage
    gb = ndimage.maximum_filter(bm[..., 0], size=LIGHT_GROW)[..., None]
    w = (bm[..., 0] > 0.3)
    hue = g * 0; 
    if w.any():
        idx = ndimage.distance_transform_edt(~w, return_distances=False, return_indices=True)
        hue = g[idx[0], idx[1]]                         # each grown texel takes the colour of its nearest light
    hue = hue / np.maximum(hue.max(2, keepdims=True), 1e-3)
    out = out * (1 - gb) + hue * gb
    bm = gb
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(f'{DST}/{fn}')
    Image.fromarray((bm[..., 0] * 255).astype(np.uint8)).save(f'{DST}/{fn[:-4]}_bm.png')
    return fn


def main():
    from extract_h2_drone_ranks import change_colours
    os.makedirs(DST, exist_ok=True)
    j = read_jms(open(f'{SRC}/render/sentinel_knight.JMS', 'rb').read())
    nodes = j['nodes']; parents = [n['parent'] for n in nodes]
    WT = np.array([n['t'] for n in nodes])[None]; WQ = np.array([n['q'] for n in nodes])[None]
    BT, BQ = local_frames(WT, WQ, parents)
    joints = [(n['name'], n['parent'], BT[0, k], BQ[0, k], (1.0, 1.0, 1.0)) for k, n in enumerate(nodes)]
    cols = change_colours(open(f'{TAGS}/sentinel_knight.biped', 'rb').read())
    ranks = {r: [round(float(v), 3) for v in (np.array(lo) + np.array(hi)) / 2] for r, (lo, hi) in cols.items()}
    # one surface per shader (the JMS's materials repeat them, one per piece)
    w8 = np.round(j['bw'] * 255).astype(int); w8[:, 0] += 255 - w8.sum(1)
    meshes, mats = [], []
    for sh in SHADERS:
        sel = np.isin(j['tri_mat'], [k for k, m in enumerate(j['materials']) if m['name'] == sh])
        if not sel.any(): continue
        T = j['tris'][sel]; vs = np.unique(T); inv = np.full(len(j['pos']), -1); inv[vs] = np.arange(len(vs))
        meshes.append(dict(name=sh, material=bake(sh, 'minor', ranks['minor']), pos=j['pos'][vs], nrm=j['nrm'][vs],
                           uv=j['uv'][vs] * [1, -1] + [0, 1], bidx=j['bidx'][vs].astype(np.uint8),
                           bw=np.clip(w8[vs], 0, 255).astype(np.uint8), tris=inv[T][:, [0, 2, 1]]))
        mats.append(sh)
        for r in ranks:
            if r != 'minor': bake(sh, r, ranks[r])
    # the arm guns, one surface each (a Knight shows one, build_pack hides the others)
    import pickle
    idx = {n['name']: k for k, n in enumerate(nodes)}
    # the gun's frame: along the forearm (b_r_gun's +y, the way the Knight's bones point), its top up when the arm is
    # raised to aim (the idle holds the forearm level, pointing ahead: the bone axis that is up there is the gun's up)
    gn = nodes[idx['b_r_gun']]; gq = np.array(gn['q']); t = np.array(gn['t'])
    idle = read_jma(open(f'{SRC}/animations/any any idle var0.JMM', 'rb').read())
    lup = qrot(qconj(idle['q'][0, idx['b_r_gun']]), np.array([0, 0, 1.0])); lup[1] = 0; lup /= np.linalg.norm(lup)
    X = qrot(gq, np.array([0, 1.0, 0])); Z = qrot(gq, lup); Y = np.cross(Z, X)
    R = np.stack([X, Y, Z], 1)                               # gun axes (x forward, y left, z up) -> model space
    elbow = R.T @ (np.array(nodes[idx['b_r_forearm']]['t']) - t)
    zc = 0.0
    gb = idx['b_r_gun']
    guns = []
    for gun, length in ARM_GUNS.items():
        pk = f'{OUT}/weapons/sk_{gun}/sk_{gun}.pkl'
        if not os.path.exists(pk): print('  no', pk, '(run promethean_ce.py)'); continue
        g = pickle.load(open(pk, 'rb')); gm = g['meshes'][0]
        sc = length / max(gm['pos'][:, 0].max(), 1e-6)
        P = t + (gm['pos'] * sc + [elbow[0] - ARM_BACK, 0, zc]) @ R.T
        N = gm['nrm'] @ R.T
        n = len(P); bi = np.zeros((n, 4), np.uint8); bi[:, 0] = gb; bw = np.zeros((n, 4), np.uint8); bw[:, 0] = 255
        import shutil
        for f in (gm['material'], gm['material'][:-4] + '_bm.png'):       # the baked texture and its lights' brightmap
            if os.path.exists(os.path.join(os.path.dirname(pk), f)): shutil.copy(os.path.join(os.path.dirname(pk), f), f'{DST}/{f}')
        mat = None
        for r in ranks: f = gun_skin(f'{DST}/{gm["material"]}', r, ranks[r]); mat = mat or f
        meshes.append(dict(name=f'gun_{gun}', material=mat, pos=P, nrm=N, uv=gm['uv'], bidx=bi, bw=bw,
                           tris=np.asarray(gm['tris'])))
        guns.append(gun)
    # animations: renamed onto the pack's names (build_pack.anim_table: the 'pistol' stance, one arm gun), their
    # movement taken off the root (b_pedestal carries it, x/y in model space) into the json's per-animation speed and dx
    anims, info = [], {}
    names = [n['name'] for n in nodes]
    for src_name, dst in ANIM_NAMES.items():
        f = f'{SRC}/animations/{src_name}'
        if not os.path.exists(f): print('  no', src_name); continue
        a = read_jma(open(f, 'rb').read())
        if a['names'] != names: print('  skip', src_name, '(other skeleton)'); continue
        T = a['t'].copy(); root = T[:, 0, :2].copy()
        T[:, :, :2] -= root[:, None, :]                             # the pose about a fixed root
        LT, LQ = local_frames(T, a['q'], a['parents'])
        frames = [[(LT[fr, k], LQ[fr, k], (1.0, 1.0, 1.0)) for k in range(len(nodes))] for fr in range(len(LT))]
        step = np.diff(root, axis=0)
        loop = any(x in src_name for x in LOOP)
        info[dst] = dict(frames=len(frames), speed=float(np.hypot(step[:, 0], step[:, 1]).sum() / max(1, len(frames))), yaw=0.0,
                         loop=int(loop), key=-1, next=-1, dx=[float(root[-1, 0] - root[0, 0]), float(root[-1, 1] - root[0, 1])])
        anims.append(dict(name=dst, fps=float(a['fps']), loop=loop, frames=frames))
    write_iqm(f'{DST}/SentinelKnight.iqm', joints, meshes, anims)
    allp = j['pos']
    meta = dict(id='SentinelKnight', tag=r'objects\characters\sentinel_knight\sentinel_knight', maps=['H2EK-Tags'],
                joints=names, bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info,
                materials=[m_['material'][:-4] for m_ in meshes], meshes=[m_['material'] for m_ in meshes],
                mesh_names=[m_['name'] for m_ in meshes], mesh_weapon=[None] * len(meshes),
                has_multi={m_['material'][:-4]: False for m_ in meshes},
                collision_height=0.95, collision_radius=0.32,
                markers={m_['name'].replace('_', ' '): [dict(node=m_['node'], t=list(m_['t']), q=list(m_['q']))] for m_ in j['markers']},
                guns=guns, gun_surface={g: len(SHADERS) - (0 if 'Core' in mats else 1) + i for i, g in enumerate(guns)},
                shader_surface={sh: i for i, sh in enumerate(mats)},
                cores={k: list(v) for k, v in CORES.items()}, core_palette=CORE_PALETTE, ranks=ranks)
    json.dump(meta, open(f'{DST}/SentinelKnight.json', 'w'), indent=1)
    print(f'-> {DST}: {len(nodes)} nodes, {len(j["tris"])} tris, {len(anims)} animations, ranks {list(ranks)}')


if __name__ == '__main__':
    main()
