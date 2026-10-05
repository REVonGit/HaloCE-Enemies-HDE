"""Halo BSP render mesh -> chunked OBJ models with baked lightmap brightness."""
import struct, os, math
import numpy as np
from collections import defaultdict
from halomap import tagrefs
from bitmaps import bitmap_image

LIGHT_BINS = [88, 128, 168, 208, 248]

def shader_basemap(m, shader_id):
    t = m.byid.get(shader_id)
    if not t: return None, False
    cls = t['cls']
    if cls == 'senv':
        flags = m.u('H', t['data'] + 0x28)[0]
        ref = m.u('I', t['data'] + 0x88 + 12)[0]
        alpha_test = bool(flags & 1)
        if ref in m.byid: return ref, alpha_test
    refs = tagrefs(m, t['data'], 0x300)
    if refs: return refs[0][1], cls in ('schi', 'scex', 'sgla')
    # chicago shaders keep maps in a block: follow reflexives one level
    for k in range(0x28, 0x200, 4):
        c, p = m.u('II', t['data'] + k)
        if 0 < c < 16 and 0x80000000 <= p < 0x84000000:
            try:
                r = tagrefs(m, p, min(c * 0x80, 0x400))
            except Exception:
                continue
            if r: return r[0][1], True
    return None, False

class LightmapSampler:
    def __init__(s, m, bsp):
        s.imgs = {}
        s.m = m
        s.tag = bsp.u('I', bsp.root + 12)[0]
    def get(s, idx):
        if idx < 0: return None
        if idx not in s.imgs:
            im = bitmap_image(s.m, s.tag, idx)
            s.imgs[idx] = np.asarray(im.convert('RGB'), dtype=np.float32) / 255.0 if im else None
        return s.imgs[idx]
    def sample(s, idx, uvs):
        a = s.get(idx)
        if a is None: return None
        h, w, _ = a.shape
        out = []
        for u, v in uvs:
            x = min(w - 1, max(0, int(u * w))); y = min(h - 1, max(0, int(v * h)))
            out.append(a[y, x])
        return np.mean(out, axis=0)

def render_triangles(m, b):
    """yield dict(shader, pos[3], uv[3], light) per triangle (halo units)."""
    sc, sp = b.blk(b.root + 0xF8)
    surf_raw = b.m.d[b.o(sp):b.o(sp) + sc * 6]
    surfaces = np.frombuffer(surf_raw, dtype='<u2').reshape(-1, 3)
    lc, lp = b.blk(b.root + 0x104)
    lms = LightmapSampler(m, b)
    tris = []
    for li in range(lc):
        la = lp + li * 32
        bidx = b.u('h', la)[0]
        mc, mp = b.blk(la + 0x14)
        for mi in range(mc):
            a = mp + mi * 0x100
            shader = b.u('I', a + 0xC)[0]
            first, count = b.u('ii', a + 0x14)
            nv = b.u('i', a + 0xB4)[0]
            vaddr = b.u('I', a + 0xF8)[0]
            if nv <= 0 or count <= 0: continue
            o = b.o(vaddr)
            vr = np.frombuffer(b.m.d, dtype=np.uint8, count=nv * 32, offset=o).reshape(nv, 32)
            pos = vr[:, 0:12].copy().view('<f4').reshape(nv, 3)
            uv = vr[:, 24:32].copy().view('<f4').reshape(nv, 2)
            lm = np.frombuffer(b.m.d, dtype=np.uint8, count=nv * 8, offset=o + nv * 32).reshape(nv, 8)
            luv = lm[:, 4:8].copy().view('<i2').reshape(nv, 2).astype(np.float32) / 32767.0
            idx = surfaces[first:first + count].astype(np.int64)
            if idx.size == 0 or idx.max() >= nv: continue
            img = lms.get(bidx)
            if img is not None:
                h, w, _ = img.shape
                lx = np.clip((luv[:, 0] * w).astype(int), 0, w - 1)
                ly = np.clip((luv[:, 1] * h).astype(int), 0, h - 1)
                cu = luv[idx].mean(axis=1)
                cx_ = np.clip((cu[:, 0] * w).astype(int), 0, w - 1)
                cy_ = np.clip((cu[:, 1] * h).astype(int), 0, h - 1)
                tl = 0.6 * img[cy_, cx_].mean(axis=1) + 0.4 * img[ly, lx].mean(axis=1)[idx].mean(axis=1)
            else:
                tl = np.full(len(idx), 0.6, dtype=np.float32)
            tris.append((shader, pos[idx], uv[idx], tl))
    return tris

def light_level(l):
    ll = 72 + 260 * float(l)
    best = min(LIGHT_BINS, key=lambda q: abs(q - ll))
    return best

def export_chunks(tris, xf, outdir, prefix, texname, chunk=768, zband=512, anchor=None):
    """Group triangles by (cell x, cell y, z band, light bin) -> OBJ files.
    texname(shader_id) -> pk3 texture path or None. Returns list of chunk dicts."""
    groups = defaultdict(lambda: defaultdict(list))
    for shader, P, UV, TL in tris:
        tex = texname(shader)
        if tex is None: continue
        D = np.empty_like(P, dtype=np.float64)
        D[..., 0] = (P[..., 0] - xf.ox) * xf.S
        D[..., 1] = (P[..., 1] - xf.oy) * xf.S
        D[..., 2] = (P[..., 2] - xf.oz) * xf.S
        cen = D.mean(axis=1)
        cx = np.floor(cen[:, 0] / chunk).astype(int)
        cy = np.floor(cen[:, 1] / chunk).astype(int)
        cz = np.floor(cen[:, 2] / zband).astype(int)
        lb = np.array([light_level(l) for l in TL])
        for i in range(len(D)):
            groups[(cx[i], cy[i], cz[i], lb[i])][tex].append((D[i], UV[i]))
    os.makedirs(outdir, exist_ok=True)
    chunks = []
    for k, (key, mats) in enumerate(sorted(groups.items())):
        cx, cy, cz, ll = key
        allp = np.concatenate([np.array([t[0] for t in lst]).reshape(-1, 3) for lst in mats.values()])
        ax = (cx + 0.5) * chunk; ay = (cy + 0.5) * chunk; az = float(np.floor(allp[:, 2].min()))
        if anchor is not None:
            # the actor must stand inside a real sector of the area it draws, or
            # UZDoom skips it when that map section is out of view
            cen = allp.reshape(-1, 3, 3).mean(axis=1)
            order = np.argsort(np.hypot(cen[:, 0] - ax, cen[:, 1] - ay))
            for q in order[:: max(1, len(order) // 40)][:40]:
                if anchor(cen[q, 0], cen[q, 1]):
                    ax, ay = float(round(cen[q, 0], 1)), float(round(cen[q, 1], 1)); break
        lines = ['# Halo CE BSP chunk']
        vi = 1
        for tex, lst in mats.items():
            lines.append(f'usemtl {tex}')
            for p3, uv3 in lst:
                for (x, y, z), (u, v) in zip(p3, uv3):
                    lines.append(f'v {x-ax:.2f} {z-az:.2f} {-(y-ay):.2f}')
                    lines.append(f'vt {u:.4f} {1-v:.4f}')
                lines.append(f'f {vi}/{vi} {vi+2}/{vi+2} {vi+1}/{vi+1}')
                vi += 3
        fn = f'{prefix}_{k:04d}.obj'
        open(os.path.join(outdir, fn), 'w').write('\n'.join(lines) + '\n')
        r = float(np.max(np.hypot(allp[:, 0] - ax, allp[:, 1] - ay)))
        chunks.append(dict(file=fn, x=ax, y=ay, z=az, light=int(ll), radius=r, tris=vi // 3))
    return chunks
