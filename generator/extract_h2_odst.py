"""Halo 2's ODST -> $HCE_OUT/models/MarineKit/h2_odst_body.iqm (the whole ODST) and h2_odst_helmet.iqm (its helmet)

    python3 extract_h2_odst.py

The body: the Halo 2 Marine's 'odst' body and head (armour, arms, gloves, helmet, visor), as one kit piece skinned to
the Halo CE Marine's skeleton, so it plays every Marine animation: each vertex is carried from its Halo 2 bone's bind
pose to the matching CE bone's (Halo 2's fingers, toes and face go with the hand, foot and head), with its weights.
build_pack.py hides Spiral's ODST and wears this instead for the Halo 2 ODSTs (HCE_MarineOdstHalo2*).
The helmet on its own:
Halo 2's Marine (01b_spacestation.map: HCE_H2_MAP, textures from HCE_H2_TEXTURES) has an 'odst' permutation of its head
region: the sealed ODST helmet with its visor. Halo 2's Marine is modelled in the same frame and at the same scale as
Halo CE's (their heads both sit 0.53-0.64 world units up), so the helmet is moved by the difference between the two
heads' bind positions and bound wholly to the CE Marine's head bone, like Elefant's kit pieces (extract_marine_kit.py).
Its neck collar is cut off (the bodies it goes on have their own). The visor takes the kit's visor texture, so it gets
the kit visors' cube-map reflection (build_pack.kit_visors). The piece is added to MarineKit.json (an enclosed helmet,
for the ODST variants and the Armored Marines' ODST outfit). Run after extract_marine_kit.py.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2_elite_anims import MAP01B, CACHE01B, MARINE, _qmul
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
KIT = f'{OUT}/models/MarineKit'
PID = 'h2_odst_helmet'
BODY = 'h2_odst_body'
ARMOR = 'mk_h2_odst_armor.png'               # the ODST armour's colour map, shared by the body and the helmet
VISOR = 'mk_h2_odst_visor.png'               # Halo 2's dark bluish-purple ODST visor: build_pack.kit_visors makes it from the
                                             # kit's visor texture (KIT_VISOR_TINTS 'h2odst') and gives it the cube-map shader
LIFT = 1.2                                   # brightness lift: Halo 2's specular sheen keeps the charcoal off black; Doom has none
DETAIL_TILES = 6                             # Halo 2's detail map (metal_dirty) repeats this often across the colour map
DETAIL_MIX = 0.75                            # how much of it is baked in
DIRT = 0.38                                  # grime baked into the crevices (from the bump map's height)
WEAR = 0.30                                  # worn, lighter edges on the armour plates
GRIME = 0.16                                 # broad dirty patches over everything, tinted like the CE Marines' grime
GRIME_TINT = np.array([1.0, 0.93, 0.80])     # brownish
SHEEN = 26                                   # the plates' specular sheen (Halo 2's specular mask, the alpha), baked in
BUMP_LIGHT = (-0.35, 0.45, 0.82)             # the light baked in from the bump map (tangent space), like Spiral's painted shading
BUMP_AMBIENT = 0.45                          # the baked shade: ambient + (1 - ambient) * n.l
SMOOTH = 0.3                                 # how much of the camo's fine speckle is evened out (0 = as it is)
COLLAR_Z = 0.515                            # triangles wholly below this (the neck collar) are left off


def qrot(q, v):
    x, y, z, w = q
    u = np.array([x, y, z]); return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def world(nodes, k):
    t, q = np.array(nodes[k]['t'], float), np.array(nodes[k]['q'], float)
    p = nodes[k].get('parent', -1)
    while p is not None and p >= 0:
        pt, pq = np.array(nodes[p]['t'], float), np.array(nodes[p]['q'], float)
        t = pt + qrot(pq, t); q = _qmul(pq, q); p = nodes[p].get('parent', -1)
    return t


def ce_head(J):
    names = [j[0] for j in J]
    k = names.index('bip01 head')
    t, q = np.array(J[k][2], float), np.array(J[k][3], float)
    p = J[k][1]
    while p >= 0:
        t = np.array(J[p][2], float) + qrot(np.array(J[p][3], float), t); p = J[p][1]
    return k, t


def wq(chain):
    """bind-pose world (t, q) of each joint from [(parent, t, q)]"""
    out = []
    for p, t, q in chain:
        t, q = np.array(t, float), np.array(q, float)
        if p is not None and p >= 0:
            pt, pq = out[p]; t = pt + qrot(pq, t); q = _qmul(pq, q)
        out.append((t, q / np.linalg.norm(q)))
    return out


def conj(q): return np.array([-q[0], -q[1], -q[2], q[3]])


H2_UP = {'toe': 'foot', 'index': 'hand', 'ring': 'hand', 'thumb': 'hand'}   # Halo 2 bones the CE skeleton lacks


def ce_bone_of(name, nodes, ce):
    """the CE joint a Halo 2 node's vertices follow: its namesake, else the nearest ancestor that has one"""
    k = [n['name'] for n in nodes].index(name)
    while k is not None and k >= 0:
        cn = 'bip01 ' + nodes[k]['name'].replace('_', ' ')
        if cn in ce: return ce[cn]
        k = nodes[k].get('parent', -1)
    return ce['bip01 pelvis']


def height_from_normals(n):
    """the bump map's height field (Frankot-Chellappa: the surface whose slopes the normals give), zero mean"""
    gx = -n[..., 0] / np.maximum(n[..., 2], 0.2); gy = n[..., 1] / np.maximum(n[..., 2], 0.2)
    h, w = gx.shape
    u, v = np.meshgrid(np.fft.fftfreq(w) * 2 * np.pi, np.fft.fftfreq(h) * 2 * np.pi)
    d = u * u + v * v; d[0, 0] = 1
    z = (-1j * u * np.fft.fft2(gx) - 1j * v * np.fft.fft2(gy)) / d; z[0, 0] = 0
    return np.real(np.fft.ifft2(z))


def blur(a, r):
    from scipy import ndimage
    return ndimage.gaussian_filter(a, r / 2.0, mode='wrap')


def armor_texture(m, hb, bms):
    """the ODST armour's colour map, weathered like the Halo CE Marines' painted textures: Halo 2's bump-map shading,
    its detail map, grime in the crevices, worn plate edges, broad dirty patches and the plates' sheen, all baked in
    (Doom lights the model flat, with no bump, detail or specular pass of its own)"""
    from PIL import Image, ImageFilter
    cands = [n for n in bms if not any(x in n for x in ('bump', 'default_', 'detail', 'cube_map', 'multipurpose', 'noise', 'linear_corner'))]
    print('   armour bitmaps', bms[:6], '->', cands[:1])
    src = hb.bitmap(m, cands[0]).convert('RGBA') if cands else Image.new('RGBA', (8, 8), (70, 72, 70, 0))
    bump = [n for n in bms if 'bump' in n]
    size = hb.bitmap(m, bump[0]).size if bump else src.size
    # up to the bump map's size, so its detail survives (colour and mask apart: an RGBA resize premultiplies, blacking
    # out everything the mask leaves at 0)
    im = src.convert('RGB').resize(size, Image.LANCZOS)
    spec = np.asarray(src.split()[3].resize(size, Image.LANCZOS), float)[..., None] / 255.0   # Halo 2's specular mask: the plates
    a = np.asarray(im, float)
    soft = np.asarray(im.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.2)), float)
    a = a * (1 - SMOOTH) + soft * SMOOTH                 # the camo's fine speckle evened out
    H, W = a.shape[:2]
    if bump:
        n = np.asarray(hb.bitmap(m, bump[0]).convert('RGB'), float) / 127.5 - 1
        n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
        l = np.array(BUMP_LIGHT); l /= np.linalg.norm(l)
        lit = np.clip(n @ l, 0, 1)
        shade = BUMP_AMBIENT + (1 - BUMP_AMBIENT) * lit
        a = a * shade[..., None] / (BUMP_AMBIENT + (1 - BUMP_AMBIENT) * l[2])   # flat areas keep their colour
        # crevices and edges: the height field's departure from its own neighbourhood
        ht = height_from_normals(n)
        cav = ht - blur(ht, 6)
        cav /= max(np.percentile(np.abs(cav), 98), 1e-9)
        cav = np.clip(cav, -1, 1)[..., None]
        a = a * (1 - DIRT * np.clip(-cav, 0, 1) )        # grime settles in the seams
        a = a * (1 + WEAR * np.clip(cav, 0, 1) * spec)                          # the plates' raised edges rubbed bright
        a = a + SHEEN * spec * (lit[..., None] ** 8)                           # the plates' sheen, where the light catches
    det = [n for n in bms if 'detail' in n]
    if det:                                               # Halo 2's detail map (colour x detail x 2), tiled
        d = np.asarray(hb.bitmap(m, det[0]).convert('L').resize((W // DETAIL_TILES, H // DETAIL_TILES), Image.LANCZOS), float)
        d = np.tile(d, (DETAIL_TILES + 1, DETAIL_TILES + 1))[:H, :W, None] / 255.0 * 2
        a = a * (1 + DETAIL_MIX * (d - 1))
    rng = np.random.default_rng(7)                        # broad grime patches, the same on every build
    g = blur(rng.random((H, W)), 14); g = (g - g.min()) / max(g.max() - g.min(), 1e-9)
    g = np.clip((g - 0.45) * 2.2, 0, 1)[..., None]
    a = a * (1 - GRIME * g) * (1 - g * (1 - GRIME_TINT) * 0.6)
    a = np.clip(a * LIFT, 0, 255).astype(np.uint8)
    Image.fromarray(a).save(f'{KIT}/{ARMOR}')


def shader_bitmaps(m, R, shader):
    shs = [s for s in R['shaders'] if s and s.endswith('\\' + shader)]
    bms = []
    if shs:
        sh = m.tag('shad', shs[0])['addr']
        for pp in m.block(sh + 0x20, 0x7C)[:1]:
            for b in m.block(pp + 4, 0xC):
                t = m.u('I', b)[0]
                if t in m.byid: bms.append(m.byid[t]['name'])
    return bms


def main():
    from h2map import H2Map, render_model
    import extract_h2_brute as hb
    m = H2Map(MAP01B, CACHE01B)
    R = render_model(m, MARINE)
    nodes = R['nodes']
    J, M, A = read_iqm(f'{KIT}/helmet_closed.iqm')                 # the kit's skeleton and its bind animation
    alist = [dict(name=n, fps=30.0, loop=True, frames=fr) for n, fr in A.items()]
    ce = {j[0]: i for i, j in enumerate(J)}
    cew = wq([(j[1], j[2], j[3]) for j in J])
    h2w = wq([(n.get('parent', -1), n['t'], n['q']) for n in nodes])
    tomap = [ce_bone_of(n['name'], nodes, ce) for n in nodes]
    bone, cehead = ce_head(J)
    shift = cehead - world(nodes, [n['name'] for n in nodes].index('head'))
    print('head offset Halo 2 -> CE', shift.round(4))
    src = hb.model_meshes(m, R, keep={('body', 'odst'), ('head', 'odst')})
    armor = next(mm['shader'] for mm in src if 'visor' not in mm['shader'])
    armor_texture(m, hb, shader_bitmaps(m, R, armor))
    body, helmet = [], []
    for mm in src:
        mat = VISOR if 'visor' in mm['shader'] else ARMOR
        pos = np.array(mm['pos'], float); nrm = np.array(mm['nrm'], float); tris = np.array(mm['tris'])
        bi, bw = np.array(mm['bi']), np.array(mm['bw'], float)
        # the whole ODST: each vertex from its Halo 2 bones' bind poses to their CE bones', blended by its weights
        P = np.zeros_like(pos); N = np.zeros_like(nrm)
        cb = np.zeros_like(bi); cw = np.zeros_like(bw)
        for v in range(len(pos)):
            acc = {}
            for k in range(bi.shape[1]):
                w = bw[v, k]
                if w <= 0: continue
                h = int(bi[v, k]); c = tomap[h]
                th, qh = h2w[h]; tc, qc = cew[c]
                q = _qmul(qc, conj(qh))
                P[v] += w * (tc + qrot(q, pos[v] - th)); N[v] += w * qrot(q, nrm[v])
                acc[c] = acc.get(c, 0) + w
            tot = sum(acc.values()) or 1
            P[v] /= tot; N[v] /= max(np.linalg.norm(N[v]), 1e-6)
            top = sorted(acc.items(), key=lambda x: -x[1])[:4]
            for k, (c, w) in enumerate(top): cb[v, k] = c; cw[v, k] = w / tot
        w8 = np.round(cw * 255).astype(int); w8[:, 0] += 255 - w8.sum(1)
        body.append(dict(name=f'{mm["region"]}_{mm["shader"]}', material=mat, pos=P, nrm=N, uv=np.array(mm['uv'], float),
                         bidx=cb.astype(np.uint8), bw=np.clip(w8, 0, 255).astype(np.uint8), tris=tris[:, [0, 2, 1]]))
        print('   body', mm['region'], mm['shader'], len(pos), 'verts', len(tris), 'tris')
        if mm['region'] != 'head': continue
        # the helmet alone, rigid on the CE head bone with its neck collar cut off (the Armored Marines' ODST outfit)
        hp = pos + shift
        keep = hp[tris].max(axis=1)[:, 2] >= COLLAR_Z
        t2 = tris[keep]; used = np.unique(t2)
        remap = -np.ones(len(hp), int); remap[used] = np.arange(len(used)); n = len(used)
        helmet.append(dict(name=mm['shader'], material=mat, pos=hp[used], nrm=nrm[used], uv=np.array(mm['uv'], float)[used],
                           bidx=np.tile(np.array([bone, 0, 0, 0], np.uint8), (n, 1)),
                           bw=np.tile(np.array([255, 0, 0, 0], np.uint8), (n, 1)), tris=remap[t2][:, [0, 2, 1]]))
        print('   helmet', mm['shader'], n, 'verts', len(t2), 'tris (collar cut:', int((~keep).sum()), ')')
    write_iqm(f'{KIT}/{BODY}.iqm', J, body, alist)
    write_iqm(f'{KIT}/{PID}.iqm', J, helmet, alist)
    old = f'{KIT}/mk_{PID}.png'                                        # the helmet's own texture before the body shared it
    if os.path.exists(old): os.remove(old)
    kj = f'{KIT}/MarineKit.json'
    kit = json.load(open(kj))
    kit['pieces'][PID] = dict(slot='head', source='halo2 marine head odst', file=f'{PID}.iqm', shell=False, enclosed=True,
                              needs_helmet=False, tris=int(sum(len(x['tris']) for x in helmet)))
    kit['pieces'][BODY] = dict(slot='body', source='halo2 marine body + head odst', file=f'{BODY}.iqm', shell=False,
                               enclosed=True, needs_helmet=False, whole=True, tris=int(sum(len(x['tris']) for x in body)))
    if PID not in kit['enclosed']: kit['enclosed'].append(PID)
    for o in kit.get('outfits', {}).get('MarineArmored', []):           # the Armored Marines' ODST outfit wears the helmet too
        heads = o['slots'].get('head', [])
        if heads and not any(p == PID for p, _ in heads): heads.append([PID, 2])
    json.dump(kit, open(kj, 'w'), indent=1)
    print('->', f'{KIT}/{BODY}.iqm', f'{KIT}/{PID}.iqm')


if __name__ == '__main__':
    main()
