"""HDE's Bulldog (Halo Infinite's, from Bulldog_HDE.blend) reinterpreted as a Halo CE weapon: low-poly geometry
(meshoptimizer), a fresh UV atlas (xatlas), and one 512x512 CE-style painted texture baked from the high-poly's
material masks (Infinite's per-zone masks -> a Halo CE human-weapon palette, AO, edge wear and grime)."""
import os, sys, subprocess, struct, pickle, json
import numpy as np
from PIL import Image, ImageFilter
from scipy.spatial import cKDTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import blend35

BLEND = os.environ.get('HCE_BULLDOG_BLEND', os.path.join(HERE, 'Bulldog_HDE.blend'))   # HDE's Bulldog model (Halo Infinite's)
from hce_paths import OUT
WORK = os.path.join(OUT, 'bulldog_ce')
TEX = os.path.join(WORK, 'tex')
# meshtool: meshoptimizer (simplify) + xatlas (unwrap), built from their sources on first use
MESHOPT = os.environ.get('HCE_MESHOPT_SRC', os.path.join(HERE, 'third_party', 'meshoptimizer'))   # github.com/zeux/meshoptimizer
XATLAS = os.environ.get('HCE_XATLAS_SRC', os.path.join(HERE, 'third_party', 'xatlas'))           # github.com/jpcy/xatlas
TOOL = os.path.join(WORK, 'meshtool')

def ensure_tool():
    if os.path.exists(TOOL): return
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(HERE, 'lib', 'meshtool.cpp')
    cmd = ['g++', '-O2', '-std=c++17', f'-I{MESHOPT}/src', f'-I{XATLAS}/source/xatlas', '-o', TOOL, src, f'{XATLAS}/source/xatlas/xatlas.cpp'] + \
          [os.path.join(MESHOPT, 'src', f) for f in os.listdir(os.path.join(MESHOPT, 'src')) if f.endswith('.cpp')] + ['-lpthread']
    subprocess.run(cmd, check=True)

def unpack_textures(blend=None, texdir=None):
    """the .blend's packed images -> WORK/tex"""
    blend = blend or BLEND; texdir = texdir or TEX
    if os.path.isdir(texdir) and os.listdir(texdir): return
    os.makedirs(texdir, exist_ok=True)
    from blendfile import Blend
    B = Blend(blend)
    for b in B.of_type('Image'):
        nm = B.id_name(b); B.ctx = b
        pf = B.get('Image', b.off, 'packedfile')
        lst = B.get('Image', b.off, 'packedfiles')
        if not pf and lst:
            first = B.get('ListBase', lst, 'first')
            if first: pf = B.get('ImagePackedFile', B.block(first).off, 'packedfile')
        if not pf: continue
        pb = B.block(pf); sz = B.get('PackedFile', pb.off, 'size'); db = B.block(B.get('PackedFile', pb.off, 'data'))
        data = B.d[db.off:db.off + sz]
        fn = nm if nm.lower().endswith(('.png', '.jpg')) else nm + ('.jpg' if data[:2] == b'\xff\xd8' else '.png')
        open(os.path.join(texdir, fn.replace('/', '_')), 'wb').write(data)
WID = 'm_bulldog'
M2WU = 1 / 3.048           # metres -> Halo world units
RES = 512
# part (object-name suffix) -> (role, target triangles)
PARTS = {
    'magazine_001_s0.005': ('upper', 380),     # upper receiver
    'magazine_001_s0.004': ('lower', 170),     # lower receiver + pistol grip
    'magazine_001_s0.006': ('stock', 110),
    'magazine_001_s0.003': ('fore', 170),      # fore-end tube + vertical grip
    'magazine_001_s0': ('drum', 150),          # drum magazine
    'magazine_001_s001': ('barrel', 70),
    'magazine_001_s0.007': ('scope', 70),      # rails / sight housing
    'default:default.001': ('rsight', 70),     # Halo 3 shotgun rear sight
    'OG.001': ('fsight', 30),                  # front sight
}
# Halo CE human-weapon palette: (base gunmetal, zone R, zone G, zone B, accent) per role
GUNMETAL = (0.20, 0.215, 0.23); STEEL = (0.38, 0.39, 0.40); OLIVE = (0.31, 0.33, 0.24); RUBBER = (0.085, 0.09, 0.09)
TAN = (0.45, 0.40, 0.29); ACCENT = (0.70, 0.52, 0.12)
DARK = (0.13, 0.14, 0.15)
PALETTE = {
    'upper':  (GUNMETAL, STEEL, DARK, RUBBER),
    'lower':  (DARK, GUNMETAL, RUBBER, RUBBER),
    'stock':  (OLIVE, GUNMETAL, DARK, RUBBER),
    'fore':   (OLIVE, GUNMETAL, RUBBER, RUBBER),
    'drum':   (OLIVE, GUNMETAL, (0.26, 0.28, 0.20), RUBBER),
    'barrel': (DARK, STEEL, GUNMETAL, RUBBER),
    'scope':  (DARK, STEEL, GUNMETAL, RUBBER),
}

def wbin(path, P, I):
    with open(path, 'wb') as f:
        f.write(struct.pack('<II', len(P), len(I))); f.write(np.asarray(P, '<f4').tobytes()); f.write(np.asarray(I, '<u4').tobytes())

def rbin(path, uv=False):
    d = open(path, 'rb').read(); nv, nt = struct.unpack_from('<II', d)
    o = 8; P = np.frombuffer(d, '<f4', nv * 3, o).reshape(-1, 3).astype(float); o += nv * 12
    I = np.frombuffer(d, '<u4', nt * 3, o).reshape(-1, 3).astype(int); o += nt * 12
    if not uv: return P, I
    U = np.frombuffer(d, '<f4', nv * 2, o).reshape(-1, 2).astype(float); o += nv * 8
    X = np.frombuffer(d, '<u4', nv, o).astype(int)
    return P, I, U, X

def tex(name, size=None):
    for f in os.listdir(TEX):
        if f.startswith(name): 
            im = Image.open(os.path.join(TEX, f)).convert('RGB')
            if size: im = im.resize(size, Image.BILINEAR)
            return np.asarray(im).astype(np.float32) / 255
    return None

def ce_paint(part, role):
    """the part's Halo CE colour map, in its own UV space"""
    key = 'olympus_combat_shotgun_' + {'upper': 'receiver_upper', 'lower': 'receiver_lower', 'stock': 'stock', 'fore': 'hand_grip',
                                        'drum': 'magazine', 'barrel': 'barrel', 'scope': 'scope'}[role] + '_001_s001_'
    asg = tex(key + 'asg_control'); h, w = asg.shape[:2]; size = (w // 2, h // 2)
    asg = tex(key + 'asg_control', size); m0 = tex(key + 'mask_0', size); m1 = tex(key + 'mask_1', size); nm = tex(key + 'normal', size)
    # Infinite's zones only steer shades in CE's two-to-three-tone scheme: the part's colour, lighter steel, a darker
    # tone and black rubber; the second mask's zones nudge the shade a little
    pal = [np.array(c, np.float32) for c in PALETTE[role]]
    base = np.maximum(0, 1 - m0.sum(2, keepdims=True))
    col = base * pal[0] + m0[..., 0:1] * pal[1] + m0[..., 1:2] * pal[2] + m0[..., 2:3] * pal[3]
    col = col * (1 + 0.12 * m1[..., 0:1] - 0.10 * m1[..., 1:2] + 0.06 * m1[..., 2:3])
    ao = asg[..., 0:1]; wear = asg[..., 1:2]; grime = asg[..., 2:3]
    # normal map: bevels and panel lines -> CE-style painted edge highlights and dark seams
    n = nm * 2 - 1; tilt = 1 - np.clip(n[..., 2:3], 0, 1)
    light = np.clip(0.5 + 0.9 * (n[..., 1:2] * 0.7 - n[..., 0:1] * 0.3), 0, 1.4)       # light from the upper left
    col = col * (0.55 + 0.45 * ao) * (0.8 + 0.35 * light)
    col = col * (1 - 0.35 * np.clip(grime - 0.5, 0, 1) * 2)
    edge = np.clip(wear * 1.2 + np.clip(tilt * 3 - 0.3, 0, 1) * 0.35, 0, 1)
    col = col * (1 - edge * 0.55) + np.array(STEEL, np.float32) * 1.25 * edge * 0.55
    return np.clip(col, 0, 1)

def flat_paint(role):
    """the two sights (Halo 3 / Halo CE parts with their own maps): plain gunmetal"""
    return np.ones((8, 8, 3), np.float32) * np.array(GUNMETAL, np.float32)

def build(debug=None):
    ensure_tool(); unpack_textures()
    _, R = blend35.meshes(BLEND)
    tmpd = os.path.join(WORK, 'tmp'); os.makedirs(tmpd, exist_ok=True)
    lows = []; samples_p = []; samples_n = []; samples_c = []
    # grip origin: the pistol grip's top, centred
    lowr = next(v for k, v in R.items() if k.endswith('magazine_001_s0.004'))
    gp = lowr['pos'][(lowr['pos'][:, 2] < 0.02) & (lowr['pos'][:, 2] > -0.04)]
    origin = np.array([gp[:, 0].mean(), 0.0, 0.035])
    rng = np.random.default_rng(1)
    for name, v in R.items():
        hit = [s for s in PARTS if name.endswith(s)]
        if not hit: continue
        role, target = PARTS[max(hit, key=len)]
        P = (v['pos'] - origin) * M2WU; T = v['tris']
        # low poly
        wbin(f'{tmpd}/in.bin', P, T)
        subprocess.run([TOOL, 'simplify', f'{tmpd}/in.bin', f'{tmpd}/lo.bin', str(target), '0.05'], check=True)
        lp, lt = rbin(f'{tmpd}/lo.bin'); lows.append((role, lp, lt))
        # high-poly colour samples
        paint = ce_paint(name, role) if role in PALETTE else flat_paint(role)
        a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
        fn = np.cross(b - a, c - a); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        ns = max(60000, int(area.sum() / 1.5e-7))
        ti = rng.choice(len(T), ns, p=area / area.sum())
        r1 = np.sqrt(rng.random(ns)); r2 = rng.random(ns)
        w0, w1, w2 = 1 - r1, r1 * (1 - r2), r1 * r2
        sp = a[ti] * w0[:, None] + b[ti] * w1[:, None] + c[ti] * w2[:, None]
        U = v['uv']; uvs = U[T[ti, 0]] * w0[:, None] + U[T[ti, 1]] * w1[:, None] + U[T[ti, 2]] * w2[:, None]
        h, w = paint.shape[:2]
        x = ((uvs[:, 0] % 1) * (w - 1)).astype(int); y = ((1 - uvs[:, 1] % 1) * (h - 1)).astype(int)
        samples_p.append(sp); samples_n.append(fn[ti]); samples_c.append(paint[y, x])
        print(f'{role:7s} {len(T):6d} -> {len(lt):4d} tris, {ns} samples', flush=True)
    finish(lows, samples_p, samples_n, samples_c, WID, 'hde:Bulldog_HDE.blend (Halo CE reinterpretation)', rng)

def finish(lows, samples_p, samples_n, samples_c, wid, tag, rng):
    """low-poly parts + coloured high-poly samples -> one UV atlas, a baked CE-style texture, the weapon pkl"""
    tmpd = os.path.join(WORK, 'tmp'); os.makedirs(tmpd, exist_ok=True)
    # one mesh, one atlas
    allp = []; allt = []; base = 0
    for role, lp, lt in lows: allp.append(lp); allt.append(lt + base); base += len(lp)
    P = np.concatenate(allp); T = np.concatenate(allt)
    wbin(f'{tmpd}/all.bin', P, T)
    subprocess.run([TOOL, 'unwrap', f'{tmpd}/all.bin', f'{tmpd}/uv.bin', str(RES)], check=True)
    P, T, UV, X = rbin(f'{tmpd}/uv.bin', uv=True)
    SP = np.concatenate(samples_p); SN = np.concatenate(samples_n); SC = np.concatenate(samples_c)
    kd = cKDTree(SP)
    # bake: every atlas texel -> its point on the low-poly -> the nearest high-poly sample facing the same way
    img = np.zeros((RES, RES, 3), np.float32); filled = np.zeros((RES, RES), bool)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    for t, n in zip(T, fn):
        uv = UV[t] * RES
        x0, x1 = int(np.floor(uv[:, 0].min())), int(np.ceil(uv[:, 0].max())); y0, y1 = int(np.floor(uv[:, 1].min())), int(np.ceil(uv[:, 1].max()))
        gx, gy = np.meshgrid(np.arange(max(0, x0), min(RES, x1 + 1)) + 0.5, np.arange(max(0, y0), min(RES, y1 + 1)) + 0.5)
        if gx.size == 0: continue
        d = (uv[1, 1] - uv[2, 1]) * (uv[0, 0] - uv[2, 0]) + (uv[2, 0] - uv[1, 0]) * (uv[0, 1] - uv[2, 1])
        if abs(d) < 1e-12: continue
        l0 = ((uv[1, 1] - uv[2, 1]) * (gx - uv[2, 0]) + (uv[2, 0] - uv[1, 0]) * (gy - uv[2, 1])) / d
        l1 = ((uv[2, 1] - uv[0, 1]) * (gx - uv[2, 0]) + (uv[0, 0] - uv[2, 0]) * (gy - uv[2, 1])) / d
        l2 = 1 - l0 - l1
        m = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
        if not m.any(): continue
        pts = l0[m, None] * P[t[0]] + l1[m, None] * P[t[1]] + l2[m, None] * P[t[2]]
        dd, ii = kd.query(pts, k=24)
        face = SN[ii] @ n
        wgt = np.exp(-(dd / max(1e-5, np.median(dd[:, 0]) * 2.5 + 1e-4)) ** 2) * (face > 0.2)
        nob = wgt.sum(1) < 1e-6
        wgt[nob] = np.exp(-(dd[nob] / (dd[nob, :1] + 1e-5)) ** 2)            # nothing faces our way: just the nearest
        c = (SC[ii] * wgt[..., None]).sum(1) / wgt.sum(1, keepdims=True)
        ys = gy[m].astype(int); xs = gx[m].astype(int)
        img[ys, xs] = c; filled[ys, xs] = True
    # pad the gutters
    for _ in range(6):
        im2 = img.copy(); f2 = filled.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sh = np.roll(np.roll(img, dy, 0), dx, 1); shf = np.roll(np.roll(filled, dy, 0), dx, 1)
            take = ~f2 & shf; im2[take] = sh[take]; f2 |= take
        img, filled = im2, f2
    # Halo CE look: a touch soft, then a grainy, painted finish
    out = Image.fromarray((np.clip(img * 1.12, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.5))
    a = np.asarray(out).astype(np.float32) / 255
    grain = rng.normal(0, 0.007, (RES, RES, 1)).astype(np.float32)
    a = np.clip(a + grain, 0, 1)
    out = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.UnsharpMask(1.0, 40, 3))
    d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
    mat = f'w_{wid}_0.png'; out.save(f'{d}/{mat}')
    vn = np.zeros_like(P)
    for t, n in zip(T, fn): vn[t] += n
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    uvf = UV.copy(); uvf[:, 1] = uvf[:, 1]       # xatlas: v down, like Halo / IQM
    pickle.dump(dict(id=wid, tag=tag, meshes=[dict(material=mat, pos=P, nrm=vn, uv=uvf, tris=T)]),
                open(f'{d}/{wid}.pkl', 'wb'))
    print(wid, len(T), 'tris', P.min(0).round(3), P.max(0).round(3))


if __name__ == '__main__':
    build()
