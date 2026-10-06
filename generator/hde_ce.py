"""HaloDoom Evolved's own weapon models (.blend files of Halo Infinite / Reach / MCC rips) reinterpreted as Halo CE
guns: each part cut to a CE polygon budget, one fresh UV atlas, one painted 512x512 texture baked from the
high-poly (bulldog_ce.finish). Shared by the Commando, the Hydra and the Plasma Caster (and usable for any other).

Colour comes from the source's own shading so a gun keeps its colour scheme: Halo Infinite materials (the
"Halo Infinite Shader" node group: ASG control map, two zone masks, per-zone top/mid/bottom colours) are evaluated
here, and plain colour maps (Substance exports) are used as they are. Then the CE treatment: AO and the normal map's
bevels painted in as shading and edge wear, colours pulled a little towards CE's flatter, warmer palette."""
import os, sys, io, subprocess
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import blend35, bulldog_ce as bc

def srgb(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)

class Source:
    """one .blend: meshes, packed images, Infinite-shader inputs per material"""
    def __init__(s, path, maxres=1024):
        s.B, s.R = blend35.meshes(path)
        s.mats = blend35.base_images(s.B)
        s.inf = infinite_inputs(s.B)
        s.maxres = maxres; s._imgs = {}
    def image(s, name, alpha=False):
        key = (name, alpha)
        if key in s._imgs: return s._imgs[key]
        B = s.B; res = None
        for b in B.of_type('Image'):
            if B.id_name(b) != name: continue
            B.ctx = b
            pf = B.get('Image', b.off, 'packedfile'); lst = B.get('Image', b.off, 'packedfiles')
            if not pf and lst:
                first = B.get('ListBase', lst, 'first')
                if first: pf = B.get('ImagePackedFile', B.block(first).off, 'packedfile')
            if not pf: break
            pb = B.block(pf); sz = B.get('PackedFile', pb.off, 'size'); db = B.block(B.get('PackedFile', pb.off, 'data'))
            im = Image.open(io.BytesIO(B.d[db.off:db.off + sz])).convert('RGBA' if alpha else 'RGB')
            while max(im.size) > s.maxres: im = im.resize((im.size[0] // 2, im.size[1] // 2), Image.BILINEAR)
            res = np.asarray(im).astype(np.float32) / 255
            break
        s._imgs[key] = res
        return res

def infinite_inputs(B):
    """material -> {'inputs': socket name -> default value, 'links': socket name -> image name} for the Halo Infinite
    shader group in its node tree"""
    def sockval(sk):
        dv = B.get('bNodeSocket', sk.off, 'default_value'); db = B.block(dv) if dv else None
        if not db: return None
        for st in ('bNodeSocketValueRGBA', 'bNodeSocketValueFloat'):
            try: return B.get(st, db.off, 'value')
            except Exception: pass
    out = {}
    for m in B.of_type('Material'):
        name = B.id_name(m); B.ctx = m
        nt = B.block(B.get('Material', m.off, 'nodetree'))
        if not nt: continue
        nodes = {}; socks = {}
        for nd in B.listbase(B.get('bNodeTree', nt.off, 'nodes'), 'bNode'):
            idp = B.get('bNode', nd.off, 'id'); sub = B.block(idp) if idp else None
            nodes[nd.old] = (B.get('bNode', nd.off, 'idname'), B.id_name(sub) if sub else '')
            for sk in B.listbase(B.get('bNode', nd.off, 'inputs'), 'bNodeSocket'):
                socks[sk.old] = (nd.old, B.get('bNodeSocket', sk.off, 'name'), sockval(sk))
        grp = [k for k, (i, n) in nodes.items() if 'Infinite Shader' in n]
        if not grp: continue
        g = grp[0]; res = {'inputs': {}, 'links': {}}
        for so, (nd, n, v) in socks.items():
            if nd == g and v is not None: res['inputs'][n] = v
        links = [(B.get('bNodeLink', lk.off, 'fromnode'), B.get('bNodeLink', lk.off, 'tonode'), B.get('bNodeLink', lk.off, 'tosock'))
                 for lk in B.listbase(B.get('bNodeTree', nt.off, 'links'), 'bNodeLink')]
        def src(node, d=0):
            if d > 6 or node not in nodes: return None
            if nodes[node][0] == 'ShaderNodeTexImage': return nodes[node][1]
            for f, t, ts in links:
                if t == node:
                    r = src(f, d + 1)
                    if r: return r
        for f, t, ts in links:
            if t == g:
                tb = B.block(ts)
                if not tb: continue
                sock = B.get('bNodeSocket', tb.off, 'name')
                if nodes.get(f, ('',))[0] == 'ShaderNodeGroup' and sock.endswith('Gradient Out'):
                    # a zone's material swatch: its tiling gradient mask (bot -> mid -> top) lives in that group
                    res['links'][sock] = ('group', nodes[f][1])
                    continue
                r = src(f)
                if r: res['links'][sock] = r
        out[name] = res
    # material swatch group -> its gradient mask image
    out['__groups__'] = {}
    for ng in B.of_type('bNodeTree'):
        B.ctx = ng
        for nd in B.listbase(B.get('bNodeTree', ng.off, 'nodes'), 'bNode'):
            idp = B.get('bNode', nd.off, 'id')
            if idp and 'TexImage' in B.get('bNode', nd.off, 'idname'):
                ib = B.block(idp); nm = B.id_name(ib) if ib else ''
                if 'gradientmask' in nm: out['__groups__'][B.id_name(ng)] = nm
    return out

def fv(x):
    """a float socket's value (bNodeSocketValueFloat reads as subtype, value, min, max)"""
    return x[1] if isinstance(x, (list, tuple)) else x

def soften(a, k):
    """low-pass: down by k, back up (bilinear)"""
    h, w = a.shape[:2]; c = a.shape[2]
    im = [Image.fromarray(a[..., i].astype(np.float32), 'F') for i in range(c)]
    im = [x.resize((max(1, w // k), max(1, h // k)), Image.BOX).resize((w, h), Image.BILINEAR) for x in im]
    return np.stack([np.asarray(x) for x in im], -1)

def _fit(a, size):
    if a is None: return None
    if a.shape[:2] == size: return a
    return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize(size[::-1], Image.BILINEAR)).astype(np.float32) / 255

def infinite_paint(src, mat):
    """evaluate the Infinite shader's colour for one material (sRGB float image), or None"""
    d = src.inf.get(mat)
    if not d or not isinstance(d, dict) or 'ASG' not in d.get('links', {}): return None
    I, L = d['inputs'], d['links']
    asg = src.image(L['ASG']); size = asg.shape[:2]
    m0 = _fit(src.image(L['Mask_0']), size) if 'Mask_0' in L else np.zeros_like(asg)
    m1 = _fit(src.image(L['Mask_1']), size) if 'Mask_1' in L else np.zeros_like(asg)
    def col(z, part):
        for k in (f'Zone {z} {part}Color', f'Zone {z} {part}'):
            if k in I: return np.array(I[k][:3], np.float32)
        return None
    def on(z):
        t = I.get(f'Zone {z} Toggle'); return z == 1 or t is None or fv(t) > 0.5
    g = asg[..., 2:3]
    w = [None, None] + [m0[..., k:k + 1] for k in range(3)] + [m1[..., k:k + 1] for k in range(3)]
    zones = [z for z in range(2, 8) if on(z) and col(z, 'Top') is not None]
    total = sum(w[z] for z in zones) if zones else np.zeros_like(g)
    w[1] = np.clip(1 - total, 0, 1)
    out = np.zeros_like(asg)
    for z in [1] + zones:
        top, mid, bot = col(z, 'Top'), col(z, 'Mid'), col(z, 'Bot')
        if top is None: continue
        mid = top if mid is None else mid; bot = mid if bot is None else bot
        # the zone's tone: Infinite picks bot / mid / top by the zone material's tiling gradient mask; CE paints
        # flat, so the mask's average picks one colour (a little of the control map's gradient channel for variation)
        gl = L.get(f'Zone {z} Gradient Out'); gv = 0.5
        if isinstance(gl, tuple) and gl[1] in src.inf['__groups__']:
            gm = src.image(src.inf['__groups__'][gl[1]]); gv = float(gm[..., 0].mean()) if gm is not None else 0.5
        gg = np.clip(gv + (g - g.mean()) * 0.25, 0, 1)
        c = np.where(gg < 0.5, bot + (mid - bot) * (gg * 2), mid + (top - mid) * (gg * 2 - 1))
        sc = col(z, 'Scratch'); sa = I.get(f'Zone {z} Scratch Amount'); sa = fv(sa) if sa is not None else 0.5
        if sc is not None:
            s = np.clip(asg[..., 1:2] * sa, 0, 1); c = c * (1 - s) + sc * s
        out += c * w[z]
    # Infinite's gradient and scratch masks are fine, high-contrast grain meant to be read at 4K: CE paints broad
    # tones, so the colour is low-passed, then the AO and the normal map's shading go back on at full resolution
    out = soften(out, 8)
    out = srgb(out * (0.35 + 0.65 * soften(asg[..., 0:1], 2)))
    nm = _fit(src.image(L['Normal']), size) if 'Normal' in L else None
    return ce_shade(out, nm)

def ce_shade(col, nm=None, ao=None):
    """CE treatment: soft painted lighting from the normal map, bevel highlights, AO"""
    out = col
    if ao is not None: out = out * (0.5 + 0.5 * _fit(ao, col.shape[:2])[..., :1])
    if nm is not None:
        nm = _fit(nm, col.shape[:2]); n = nm * 2 - 1; tilt = 1 - np.clip(n[..., 2:3], 0, 1)
        light = np.clip(0.5 + 0.9 * (n[..., 1:2] * 0.7 - n[..., 0:1] * 0.3), 0, 1.4)
        out = out * (0.82 + 0.3 * light)
        edge = np.clip(tilt * 3 - 0.3, 0, 1) * 0.3
        out = out * (1 - edge) + np.clip(out * 1.8 + 0.08, 0, 1) * edge
    return np.clip(out, 0, 1)

def build(src, parts, paint, origin, wid, tag, to_halo=lambda P: P, seed=3, hook=None):
    """parts: object name -> (role, target tris); paint(mat, role) -> sRGB image or None (None: faces left out);
    origin: point in Halo axes (metres) that becomes the gun's origin (mid grip); hook(role, pos, nrm, col) -> col
    repaints the colour samples by where they sit (pos in Halo axes, metres, before the origin shift)"""
    bc.ensure_tool()
    rng = np.random.default_rng(seed)
    tmpd = os.path.join(bc.WORK, f'{wid}_tmp'); os.makedirs(tmpd, exist_ok=True)
    lows = []; SPs = []; SNs = []; SCs = []; decals = []
    for name, (role, target) in parts.items():
        v = src.R.get(name)
        if v is None: print('missing', name); continue
        P = (to_halo(v['pos']) - origin) * bc.M2WU; T = v['tris']; tm = v['tmat']
        paints = {k: paint(m, role) for k, m in enumerate(v['mats'])}
        dec = np.array([paints.get(int(m)) is not None and paints[int(m)].shape[2] == 4 for m in tm])
        if dec.any(): decals.append(_decal_samples(P[...], T[dec], tm[dec], v['uv'], paints, rng))
        keep = np.array([paints.get(int(m)) is not None for m in tm]) & ~dec
        if not keep.any(): print('decals only' if dec.any() else 'nothing painted on', name); continue
        T = T[keep]; tm = tm[keep]
        bc.wbin(f'{tmpd}/in.bin', P, T)
        subprocess.run([bc.TOOL, 'simplify', f'{tmpd}/in.bin', f'{tmpd}/lo.bin', str(target), '0.05'], check=True)
        lp, lt = bc.rbin(f'{tmpd}/lo.bin'); lows.append((role, lp, lt))
        a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
        fn = np.cross(b - a, c - a); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        ns = max(60000, int(area.sum() / 6e-8))
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
            sc[sel] = pt[y, x, :3]
        if hook is not None: sc = hook(role, sp / bc.M2WU + origin, fn[ti], sc)
        SPs.append(sp); SNs.append(fn[ti]); SCs.append(sc)
        print(f'{role:9s} {len(v["tris"]):6d} -> {len(lt):4d} tris, {ns} samples', flush=True)
    if decals:                                          # decal sheets: paint them onto the surface samples beneath
        from scipy.spatial import cKDTree
        DP = np.concatenate([d[0] for d in decals]); DC = np.concatenate([d[1] for d in decals]); DA = np.concatenate([d[2] for d in decals])
        kd = cKDTree(DP); r = 0.006 * bc.M2WU
        for i, (sp, sc) in enumerate(zip(SPs, SCs)):
            dd, ii = kd.query(sp, k=4, distance_upper_bound=r)
            ok = np.isfinite(dd)
            if not ok.any(): continue
            ii = np.where(ok, ii, 0); w = ok * DA[ii]
            a = np.clip(w.max(1), 0, 1)[:, None]
            c = (DC[ii] * w[..., None]).sum(1) / np.maximum(w.sum(1), 1e-6)[:, None]
            SCs[i] = sc * (1 - a) + c * a
        print('decals', len(DP), 'samples')
    bc.finish(lows, SPs, SNs, SCs, wid, tag, rng)

def _decal_samples(P, T, tm, U, paints, rng, ns=30000):
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    ti = rng.choice(len(T), ns, p=area / area.sum())
    r1 = np.sqrt(rng.random(ns)); r2 = rng.random(ns); w0, w1, w2 = 1 - r1, r1 * (1 - r2), r1 * r2
    sp = a[ti] * w0[:, None] + b[ti] * w1[:, None] + c[ti] * w2[:, None]
    uvs = U[T[ti, 0]] * w0[:, None] + U[T[ti, 1]] * w1[:, None] + U[T[ti, 2]] * w2[:, None]
    col = np.zeros((ns, 4), np.float32)
    for k, pt in paints.items():
        if pt is None or pt.shape[2] != 4: continue
        sel = tm[ti] == k
        h, w = pt.shape[:2]
        x = (np.clip(uvs[sel, 0], 0, 1) * (w - 1)).astype(int); y = ((1 - np.clip(uvs[sel, 1], 0, 1)) * (h - 1)).astype(int)
        col[sel] = pt[y, x]
    keep = col[:, 3] > 0.05
    return sp[keep], col[keep, :3], col[keep, 3]

def default_paint(src, skip=()):
    """paint(mat, role): the Infinite shader where there is one, else the material's colour map (with its AO /
    normal maps when it has them); materials matching `skip` are left out"""
    def paint(mat, role):
        if mat == 'Material' or any(k in mat.lower() for k in skip): return None
        p = infinite_paint(src, mat)
        if p is not None: return p
        info = src.mats.get(mat, {}); imgs = info.get('all', [])
        cn = info.get('color') or next((i for i in imgs if 'base_color' in i.lower() or 'diff' in i.lower() or 'color' in i.lower()), None) \
            or (imgs[0] if len(imgs) == 1 else None)
        if not cn: return None
        if 'decal' in mat.lower():                       # decal: RGBA, composited onto the surface under it
            return src.image(cn, alpha=True)
        col = src.image(cn)
        if col is None: return None
        aon = next((i for i in imgs if 'ao' in i.lower().split('_')[-1] or 'mixed_ao' in i.lower()), None)
        nmn = info.get('normal') or next((i for i in imgs if 'normal' in i.lower()), None)
        return ce_shade(col, src.image(nmn) if nmn else None, src.image(aon) if aon else None)
    return paint
