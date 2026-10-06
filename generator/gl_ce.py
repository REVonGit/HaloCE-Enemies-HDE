"""The Marines' grenade launcher: HaloDoom Evolved's own (GL_HDE.blend: a kitbash of Halo Reach's grenade launcher with
Halo Infinite's Bulldog receiver, grip, barrel tube and a sniper magazine, and Halo 3 shotgun stock and pump) reinterpreted
as a Halo CE gun, the same way as the Bulldog (bulldog_ce.py): every part cut to a CE polygon budget, one fresh UV
atlas, one 512x512 painted texture baked from the high-poly. The parts' own colour maps are graded into one Halo CE
palette (olive drab over gunmetal, black rubber), so the kitbash reads as one gun; the Infinite magazine, which has only
material masks, is painted from them like the Bulldog."""
import os, sys, io, subprocess
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import blend35, bulldog_ce as bc

BLEND = os.environ.get('HCE_GL_BLEND', os.path.join(HERE, 'GL_HDE.blend1'))
WID = 'm_grenade_launcher'
# object -> (role, target triangles); objects not listed (the decal plane) are left out
PARTS = {
    'olympus_combat_shotgun': ('lower', 190),           # Infinite lower receiver + pistol grip
    'olympus_combat_shotgun.002': ('upper', 210),       # Infinite upper receiver
    'olympus_combat_shotgun.003': ('tube', 110),        # Infinite barrel tube under the launcher
    'olympus_combat_shotgun.004': ('inner', 60),
    'olympus_sniper_rifle_magazine_001_s001_0': ('mag', 70),
    'default:default.005': ('stock', 120),              # Halo 3 shotgun stock
    'default:default.003': ('pump', 70),                # Halo 3 shotgun pump
    'Reach Grenade Launcher.001': ('launcher', 160),     # Reach launcher barrel
    'Reach Grenade Launcher.002': ('post', 16),
    'Reach Grenade Launcher.003': ('shroud', 190),
    'Reach Grenade Launcher.004': ('sight', 70),
}
# materials that are decals, screens, lenses or glow: not painted onto the body
SKIP = ('decal', 'ui_', 'display', 'lens', 'illum', 'slk-', 'eagle', 'sticker')
OLIVE_RAMP = ((0.10, 0.11, 0.07), (0.50, 0.52, 0.37)); METAL_RAMP = ((0.05, 0.055, 0.06), (0.42, 0.43, 0.45))
DARK_RAMP = ((0.035, 0.037, 0.04), (0.20, 0.205, 0.21))
# parts that take one finish whatever their source map's colours (the Halo 3 stock in olive drab like the Bulldog's, its pump black)
ROLE_FINISH = {'stock': 'olive', 'pump': 'dark'}

_blend = None; _imgs = {}
def image(name):
    global _blend
    if name in _imgs: return _imgs[name]
    from blendfile import Blend
    B = _blend
    for b in B.of_type('Image'):
        if B.id_name(b) != name: continue
        B.ctx = b
        pf = B.get('Image', b.off, 'packedfile'); lst = B.get('Image', b.off, 'packedfiles')
        if not pf and lst:
            first = B.get('ListBase', lst, 'first')
            if first: pf = B.get('ImagePackedFile', B.block(first).off, 'packedfile')
        if not pf: break
        pb = B.block(pf); sz = B.get('PackedFile', pb.off, 'size'); db = B.block(B.get('PackedFile', pb.off, 'data'))
        im = Image.open(io.BytesIO(B.d[db.off:db.off + sz])).convert('RGB')
        if max(im.size) > 1024: im = im.resize((im.size[0] // 2, im.size[1] // 2), Image.BILINEAR)
        _imgs[name] = np.asarray(im).astype(np.float32) / 255
        return _imgs[name]
    _imgs[name] = None
    return None

def grade(col, nm=None, ao=None, finish=None):
    """a modern colour map -> Halo CE: gradient-mapped onto olive drab (anything coloured: paint, polymer) or gunmetal
    (greys), detail kept from its luminance; AO and the normal map's bevels painted in as shading and edge wear"""
    L = col @ np.array([0.3, 0.59, 0.11], np.float32)
    mx, mn = col.max(2), col.min(2); sat = (mx - mn) / np.maximum(mx, 1e-3)
    lo, hi = np.percentile(L, 2), np.percentile(L, 98)
    t = np.clip((L - lo) / max(hi - lo, 1e-3), 0, 1)[..., None]
    paint = np.clip((sat - 0.12) / 0.15, 0, 1)[..., None]
    def ramp(r): return np.array(r[0], np.float32) * (1 - t) + np.array(r[1], np.float32) * t
    out = ramp(METAL_RAMP) * (1 - paint) + ramp(OLIVE_RAMP) * paint
    if finish == 'olive': out = ramp(OLIVE_RAMP)
    elif finish == 'dark': out = ramp(DARK_RAMP)
    if ao is not None: out = out * (0.5 + 0.5 * ao[..., :1])
    if nm is not None and nm.shape[:2] == col.shape[:2]:
        n = nm * 2 - 1; tilt = 1 - np.clip(n[..., 2:3], 0, 1)
        light = np.clip(0.5 + 0.9 * (-n[..., 1:2] * 0.7 - n[..., 0:1] * 0.3), 0, 1.4)    # DirectX normal maps: green down
        out = out * (0.8 + 0.35 * light)
        edge = np.clip(tilt * 3 - 0.3, 0, 1) * 0.35
        out = out * (1 - edge) + np.array(bc.STEEL, np.float32) * 1.25 * edge
    return np.clip(out, 0, 1)

def material_paint(mat, info, role):
    if any(k in mat.lower() for k in SKIP) or mat == 'Material': return None
    imgs = info.get('all', [])
    pick = lambda *keys: next((i for i in imgs if all(k in i for k in keys)), None)
    if pick('mask_0'):                                      # Infinite material masks only (the sniper magazine)
        asg, m0, m1, nm = (image(pick(k)) for k in ('asg_control', 'mask_0', 'mask_1', 'normal'))
        size = asg.shape[:2]
        rs = lambda a: a if a.shape[:2] == size else np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize(size[::-1])).astype(np.float32) / 255
        m0, m1, nm = rs(m0), rs(m1), rs(nm)
        pal = [np.array(c, np.float32) for c in (bc.OLIVE, bc.GUNMETAL, bc.DARK, bc.RUBBER)]
        base = np.maximum(0, 1 - m0.sum(2, keepdims=True))
        col = base * pal[0] + m0[..., 0:1] * pal[1] + m0[..., 1:2] * pal[2] + m0[..., 2:3] * pal[3]
        col = col * (0.55 + 0.45 * asg[..., 0:1]) * (1 - 0.3 * np.clip(asg[..., 2:3] - 0.5, 0, 1) * 2)
        edge = np.clip(asg[..., 1:2] * 1.2, 0, 1) * 0.5
        return np.clip(col * (1 - edge) + np.array(bc.STEEL, np.float32) * 1.25 * edge, 0, 1)
    col = image(pick('Base_Color')) if pick('Base_Color') else None
    if col is None: col = image(pick('default_color')) if pick('default_color') else None
    if col is None: col = image(pick('rubber.png')) if 'rubber' in mat else None
    if col is None: col = image(pick('shotgun_diffuse')) if pick('shotgun_diffuse') else None
    if col is None: return None
    aon = pick('Mixed_AO'); nmn = pick('Normal_DirectX')
    ao = image(aon) if aon else None; nm = image(nmn) if nmn else None
    if ao is not None and ao.shape[:2] != col.shape[:2]: ao = None
    out = grade(col, nm, ao, ROLE_FINISH.get(role, 'dark' if 'rubber' in mat else None))
    return out

def build():
    global _blend
    bc.ensure_tool()
    _blend, R = blend35.meshes(BLEND)
    mats = blend35.base_images(_blend)
    rng = np.random.default_rng(2)
    # Halo weapon space: the gun points along +y in the file
    def to_halo(P): return np.stack([P[:, 1], -P[:, 0], P[:, 2]], 1)
    lowr = to_halo(R['olympus_combat_shotgun']['pos'])
    z0, z1 = lowr[:, 2].min(), lowr[:, 2].max()
    grip = lowr[(lowr[:, 2] < z0 + 0.35 * (z1 - z0)) & (lowr[:, 2] > z0 + 0.1 * (z1 - z0))]
    origin = np.array([grip[:, 0].mean(), lowr[:, 1].mean(), z0 + 0.45 * (z1 - z0)])
    tmpd = os.path.join(bc.WORK, 'gl_tmp'); os.makedirs(tmpd, exist_ok=True)
    lows = []; SPs = []; SNs = []; SCs = []
    for name, (role, target) in PARTS.items():
        v = R.get(name)
        if v is None: print('missing', name); continue
        P = (to_halo(v['pos']) - origin) * bc.M2WU; T = v['tris']; tm = v['tmat']
        paints = {k: material_paint(m, mats.get(m, {}), role) for k, m in enumerate(v['mats'])}
        keep = np.array([paints.get(int(m)) is not None for m in tm])
        if not keep.any(): print('nothing painted on', name); continue
        T = T[keep]; tm = tm[keep]
        bc.wbin(f'{tmpd}/in.bin', P, T)
        subprocess.run([bc.TOOL, 'simplify', f'{tmpd}/in.bin', f'{tmpd}/lo.bin', str(target), '0.05'], check=True)
        lp, lt = bc.rbin(f'{tmpd}/lo.bin'); lows.append((role, lp, lt))
        a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
        fn = np.cross(b - a, c - a); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        ns = max(60000, int(area.sum() / 1.5e-7))
        ti = rng.choice(len(T), ns, p=area / area.sum())
        r1 = np.sqrt(rng.random(ns)); r2 = rng.random(ns); w0, w1, w2 = 1 - r1, r1 * (1 - r2), r1 * r2
        sp = a[ti] * w0[:, None] + b[ti] * w1[:, None] + c[ti] * w2[:, None]
        U = v['uv']; uvs = U[T[ti, 0]] * w0[:, None] + U[T[ti, 1]] * w1[:, None] + U[T[ti, 2]] * w2[:, None]
        sc = np.zeros((ns, 3), np.float32)
        for k, pt in paints.items():
            if pt is None: continue
            sel = tm[ti] == k
            if not sel.any(): continue
            h, w = pt.shape[:2]
            x = ((uvs[sel, 0] % 1) * (w - 1)).astype(int); y = ((1 - uvs[sel, 1] % 1) * (h - 1)).astype(int)
            sc[sel] = pt[y, x]
        SPs.append(sp); SNs.append(fn[ti]); SCs.append(sc)
        print(f'{role:9s} {len(v["tris"]):6d} -> {len(lt):4d} tris, {ns} samples', flush=True)
    bc.finish(lows, SPs, SNs, SCs, WID, 'hde:GL_HDE.blend1 (Halo CE reinterpretation)', rng)

if __name__ == '__main__':
    build()
