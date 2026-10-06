"""The Halo CE Jackal's armoured helmet, for the Halo 2 Jackal.

    helmet(maps_dir) -> dict(pos, nrm (N,3) in the CE head bone's frame, uv (N,2), tris (M,3), base (PIL), multi (PIL or None),
                             head (N2,3) the CE bare head's vertices in the same frame, for fitting)

Halo CE's Jackal model has two head permutations, base00 and armored_head; the armoured one is the same head with a
helmet over it. The helmet is what armored_head has and base00 doesn't: vertices more than a hair away from any
bare-head vertex, and the triangles made of them.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

JACKAL = r'characters\jackal\jackal'


def _qmat(q):
    w, x, y, z = q[3], q[0], q[1], q[2]
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def helmet(maps_dir):
    from tags import HMap, tag
    from bitmaps import bitmap_image
    import halomodel as hm
    from extract_chars import shader_maps
    for mp in ('a30', 'a10', 'b30', 'c10'):
        p = os.path.join(maps_dir, mp + '.map')
        if not os.path.exists(p): continue
        m = HMap(p)
        bt = [t for t in m.find('bipd') if t['name'] == JACKAL]
        if bt: break
    else:
        raise FileNotFoundError('no Halo CE map with the Jackal')
    B = tag(m, bt[0], 'biped_definition')
    model = hm.Model(m, B['model'])
    reg = next(r for r in model.regions if r['name'] == 'head')
    def geo(name):
        perm = next(p for p in reg['perms'] if p['name'] == name)
        best = None
        for gi in sorted(set(perm['geoms'])):
            g = model.geometry(gi)
            nt = sum(len(x['tris']) for x in g)
            if best is None or nt > best[0]: best = (nt, g)
        return best[1]
    bare = geo('base00'); armd = geo('armored_head')
    bare_pos = np.concatenate([x['pos'] for x in bare])
    from scipy.spatial import cKDTree
    tree = cKDTree(bare_pos)
    head_shader = next(x['shader'] for x in armd if 'jackal head' in model.shaders[x['shader']]['name'])
    part = next(x for x in armd if x['shader'] == head_shader)
    d, _ = tree.query(part['pos'])
    new = d > 0.002
    tris = part['tris'][new[part['tris']].sum(1) >= 2]
    used = np.unique(tris); remap = np.full(len(part['pos']), -1); remap[used] = np.arange(len(used))
    sh = model.shaders[head_shader]
    base, multi, (us, vs) = shader_maps(m, sh)
    bms = model.base_map_scale
    uv = part['uv'][used] * np.array([bms[0] * us, bms[1] * vs])
    W = model.world_bind()
    hi = next(i for i, n in enumerate(model.nodes) if n['name'] == 'bip01 head')
    t, q = W[hi]; R = _qmat(q)
    to_local = lambda P: (P - t) @ R            # world -> head frame
    return dict(pos=to_local(part['pos'][used]), nrm=part['nrm'][used] @ R, uv=uv, tris=remap[tris][:, [0, 2, 1]],
                base=bitmap_image(m, base) if base else None, multi=bitmap_image(m, multi) if multi else None,
                head=to_local(bare_pos))


def fit(src, dst):
    """rotation (one of the 24 axis-aligned ones), uniform scale and offset taking point cloud src onto dst,
    by the best chamfer distance after matching centroids and spreads"""
    import itertools
    from scipy.spatial import cKDTree
    cs, cd = src.mean(0), dst.mean(0)
    ss = np.sqrt(((src - cs) ** 2).sum(1).mean()); sd = np.sqrt(((dst - cd) ** 2).sum(1).mean())
    s = sd / ss
    tree = cKDTree(dst)
    best = None
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            R = np.zeros((3, 3))
            for i in range(3): R[perm[i], i] = sg[i]
            if np.linalg.det(R) < 0: continue
            p = (src - cs) @ R.T * s + cd
            e = tree.query(p)[0].mean() + cKDTree(p).query(dst)[0].mean()
            if best is None or e < best[0]: best = (e, R)
    return best[1], s, cs, cd, best[0]
