"""Halo 2's Honor Guard and Ranger Elites on the Halo CE Elite -> $HCE_OUT/models/EliteKit/*.iqm

    python3 extract_h2_elite_kit.py

Halo 2's Elite (01b_spacestation.map: HCE_H2_MAP, textures from HCE_H2_TEXTURES) is the same 3ds Max biped as Halo CE's
(h2_elite_anims.py), so its bodies can be carried onto the CE Elite bone by bone, as extract_h2_odst.py carries the
ODST onto the CE Marine: each vertex goes from its Halo 2 bone's bind pose to the matching CE bone's, with its weights.
The pieces are model attachments riding the CE Elite's own animation (build_pack.ELITE_KIT):

    honor_body.iqm     the whole Honor Guard (the Elite's body, head, crested 'helmet: honor', 'hg: honor' plates and
                       inset lights), its armour crimson and gold (Halo 2's colour change), cut by limb; worn in place
                       of the CE Elite's body
    ranger_body.iqm    the whole Ranger (elite_ranger's body and helmet regions: EVA suit, plates, helmet, head, gold
                       lenses and inset lights), cut by limb; worn in place of the CE Elite's body
    elite_jetpack.iqm  the Ranger's jump pack, where the Ranger's 'jetpack' marker puts it on the upper spine

Textures: Halo 2's colour maps with its bump maps' shading and its detail maps baked in (Doom lights models flat), each
with its specular mask (_spec: build_pack.kit_shine bakes the cube-map reflection under it) and, where it glows, a
brightmap (_bm).
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
from h2_elite_anims import MAP01B, CACHE01B, _qmul
from extract_h2_odst import qrot, wq, conj, ce_bone_of, height_from_normals, blur, shader_bitmaps
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
KIT = f'{OUT}/models/EliteKit'
ELITE = r'objects\characters\elite\elite'
RANGER = r'objects\characters\elite\elite_ranger\elite_ranger'
JETPACK = r'objects\characters\elite\elite_jetpack\elite_jetpack'
# piece -> (render model, kept (region, permutation)s, shaders left out)
PIECES = {
    # the whole Honor Guard: Halo 2's Elite body, head, crested honour helmet, honour plates and inset lights, worn in place
    # of the CE Elite's body (its armour in the Honor Guard's colours: PIECE_TINT)
    'honor_body': (ELITE, {('body', 'base'), ('head', 'base'), ('helmet', 'honor'), ('hg', 'honor'), ('lights', 'honor')}, ('elite_emblem',)),
    'ranger_body': (RANGER, {('helmet', 'base'), ('body', 'base')}, ()),     # the whole Ranger, worn in place of the CE body
}
SPLIT = {'honor_body', 'ranger_body'}   # pieces cut into surfaces by limb: 0 body, 1 left arm, 2 right arm, 3 head
LIMB = {f'bip01 {s} {b}': (1 if s == 'l' else 2) for s in 'lr' for b in ('clavicle', 'upperarm', 'forearm', 'hand')}
LIMB.update({b: 3 for b in ('bip01 head', 'frame mandible lower left', 'frame mandible lower right', 'frame mandible upper left',
                            'frame mandible upper right')})
# the jump pack's colour-change areas (its change_color map) take the Ranger's own blue-grey, as Halo 2 tints them
JETPACK_TINT = (0.17, 0.20, 0.26)     # dark gunmetal, as Halo 2 draws the Rangers' packs (its chrome from build_pack.kit_shine)
GLOW_GREEN = ('ranger_torso', 'torso')   # their inset-light glyphs (the green panels the lights' shader samples) glow as well
# Halo 2's colour change on a piece's armour (its _change_color / _color_change map: red the primary, green the secondary)
HONOR_PRIMARY = (0.62, 0.15, 0.07)      # the Honor Guard's crimson plates
HONOR_SECONDARY = (0.86, 0.64, 0.26)    # and gold trim
PIECE_TINT = {'honor_body': (HONOR_PRIMARY, HONOR_SECONDARY)}
LENS = 'ek_ranger_lens.png'
LENS_RGB = ((0.95, 0.72, 0.30), (0.42, 0.22, 0.06))     # the Ranger's gold lens: top and bottom of its gradient
BUMP_LIGHT = (-0.35, 0.45, 0.82)
BUMP_AMBIENT = 0.5
DETAIL_TILES = 4
DETAIL_MIX = 0.2
DIRT = 0.25
LIFT = 1.15
ILLUM_LIFT = 0.6                # the inset markings' self-illumination, baked
ILLUM_ADD = 40
EMIT_GAIN = 1.25                # a coloured light map's colours, drawn this bright where they glow
SKIP = ('bump', 'default_', 'color_', 'detail', 'illum', 'change_color', 'color_change', 'cube', 'reflection', 'multiplicative',
        'dirt', 'exhaust', 'carapace', 'glassy', 'noise')


SPEC = {}      # colour map -> its specular mask (EliteKit.json 'spec')
BRIGHT = {}    # colour map -> its brightmap (EliteKit.json 'brightmaps')


def colour_map(m, hb, bms, out, tint=None):
    """Halo 2's colour map with its bump shading, crevice grime and detail map baked in"""
    from PIL import Image
    diff = [n for n in bms if not any(x in n.split('\\')[-1] for x in SKIP)]
    src = hb.bitmap(m, diff[0]).convert('RGB')
    bump = [n for n in bms if n.split('\\')[-1].endswith('_bump') and 'active_camo' not in n]
    size = hb.bitmap(m, bump[0]).size if bump else src.size
    a = np.asarray(src.resize(size, Image.LANCZOS), float)
    H, W = a.shape[:2]
    if bump:
        n = np.asarray(hb.bitmap(m, bump[0]).convert('RGB'), float) / 127.5 - 1
        n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
        l = np.array(BUMP_LIGHT); l /= np.linalg.norm(l)
        shade = BUMP_AMBIENT + (1 - BUMP_AMBIENT) * np.clip(n @ l, 0, 1)
        a = a * shade[..., None] / (BUMP_AMBIENT + (1 - BUMP_AMBIENT) * l[2])
        ht = height_from_normals(n); cav = ht - blur(ht, 6)
        cav = np.clip(cav / max(np.percentile(np.abs(cav), 98), 1e-9), -1, 1)[..., None]
        a = a * (1 - DIRT * np.clip(-cav, 0, 1))
    det = [n for n in bms if n.split('\\')[-1].endswith('_detail') and 'default' not in n]
    if det:
        d = np.asarray(hb.bitmap(m, det[0]).convert('L').resize((max(W // DETAIL_TILES, 1), max(H // DETAIL_TILES, 1)), Image.LANCZOS), float)
        d = np.tile(d, (DETAIL_TILES + 1, DETAIL_TILES + 1))[:H, :W, None] / 255.0 * 2
        a = a * (1 + DETAIL_MIX * (d - 1))
    ill = [n for n in bms if n.split('\\')[-1].endswith('_illum')]
    if ill:                                           # the glowing parts (Doom has no glow pass here)
        ic = np.asarray(hb.bitmap(m, ill[0]).convert('RGB').resize((W, H), Image.LANCZOS), float)
        g = ic.max(axis=2, keepdims=True) / 255.0
        lit = g[..., 0] > 0.2
        sat = ((ic.max(axis=2) - ic.min(axis=2)) / np.maximum(ic.max(axis=2), 1))[lit].mean() if lit.any() else 0
        if sat > 0.3:                                 # a coloured light map (the jump pack's green and cyan): its own colours, lit
            a = a * (1 - g) + np.clip(ic * EMIT_GAIN, 0, 255) * g
        else:                                         # a grey mask (the honour armour's markings): the paint lifted, warm
            a = a * (1 + ILLUM_LIFT * g) + ILLUM_ADD * g * np.array([1.0, 0.25, 0.15])
    cc = [n for n in bms if n.split('\\')[-1].endswith(('_change_color', '_color_change'))]
    if cc and tint is not None:                       # Halo 2's colour change: the masked areas take the unit's colours
        prim, sec = (tint, None) if np.ndim(tint[0]) == 0 else tint
        k = np.asarray(hb.bitmap(m, cc[0]).convert('RGB').resize((W, H), Image.LANCZOS), float) / 255.0
        kr, kg = k[..., :1], (k[..., 1:2] if sec is not None else 0 * k[..., :1])
        lum = a.mean(axis=2, keepdims=True)
        a = a * (1 - kr - kg) + lum * np.array(prim) * 1.6 * kr + (lum * np.array(sec) * 1.6 * kg if sec is not None else 0)
    im = Image.fromarray(np.clip(a * LIFT, 0, 255).astype(np.uint8))
    if max(im.size) > 512: im.thumbnail((512, 512), Image.LANCZOS)
    im.save(f'{KIT}/{out}')
    stem = out[:-4]
    # Halo 2's specular mask (the colour map's alpha): where build_pack bakes the armour's cube-map reflection
    sp = np.asarray(hb.bitmap(m, diff[0]).convert('RGBA').split()[3].resize(im.size, Image.LANCZOS), float)
    if sp.max() > 8 and sp.min() < 250: Image.fromarray(sp.astype(np.uint8)).save(f'{KIT}/{stem}_spec.png'); SPEC[out] = f'{stem}_spec.png'
    # what glows: Halo 2's self-illumination map, and the inset lights' green glyphs where they sample this map
    glow = np.zeros(im.size[::-1])
    il = [n for n in bms if n.split('\\')[-1].endswith(('_illum', '_illumination', '_self_illum'))]
    if il: glow = np.maximum(glow, np.asarray(hb.bitmap(m, il[0]).convert('L').resize(im.size, Image.LANCZOS), float) / 255.0)
    if stem in tuple(f'ek_{g}' for g in GLOW_GREEN):
        c = np.asarray(im, float)
        glow = np.maximum(glow, np.clip((c[..., 1] - np.maximum(c[..., 0], c[..., 2]) - 40) / 60.0, 0, 1))
    if glow.max() > 0.15:
        Image.fromarray(np.clip(glow * 255 * 1.4, 0, 255).astype(np.uint8)).convert('RGB').save(f'{KIT}/{stem}_bm.png')
        BRIGHT[out] = f'{stem}_bm.png'
    print('   ', out, 'from', diff[0].split('\\')[-1], 'bump' if bump else '', 'detail' if det else '')


LENS_BULGE = 1.6       # how far the lens normals lean out from each lens's centre (a domed glass for the visor shader)


def bulge(P, N, tris):
    """a flat lens's normals leaned outward from the centre of each separate lens (its connected triangles), as if the
    glass were domed: the visor shader's cube-map reflection then sweeps across it instead of one flat colour"""
    n = len(P); parent = list(range(n))
    def f(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for t in tris:
        a, b, c = f(int(t[0])), f(int(t[1])), f(int(t[2])); parent[b] = a; parent[f(c)] = a
    roots = np.array([f(i) for i in range(n)]); out = N.copy()
    for r in set(roots.tolist()):
        k = roots == r
        if k.sum() < 3: continue
        c = P[k].mean(0); rad = max(np.linalg.norm(P[k] - c, axis=1).max(), 1e-6)
        avg = N[k].mean(0); avg /= max(np.linalg.norm(avg), 1e-6)
        d = P[k] - c; d -= (d @ avg)[:, None] * avg                       # in the lens's own plane
        v = avg + LENS_BULGE * d / rad
        out[k] = v / np.linalg.norm(v, axis=1, keepdims=True)
    return out


# inset lights drawn in a light colour of their own rather than the torso map's white glyph panels (the Honor Guard's
# amber), the whole texture glowing (its brightmap the glyphs' own light and shade)
INSET_GLOW = {'honor_body': (1.0, 0.58, 0.18)}


def inset_glow(src, rgb):
    from PIL import Image
    a = np.asarray(Image.open(f'{KIT}/{src}').convert('RGB'), float) / 255.0
    lum = a.mean(axis=2, keepdims=True)
    out = np.clip(np.array(rgb) * (0.25 + 1.2 * lum), 0, 1)
    fn = src[:-4] + '_inset.png'
    Image.fromarray((out * 255).astype(np.uint8)).save(f'{KIT}/{fn}')
    Image.fromarray((np.clip(0.35 + 0.65 * lum[..., 0], 0, 1) * 255).astype(np.uint8)).convert('RGB').save(f'{KIT}/{fn[:-4]}_bm.png')
    BRIGHT[fn] = f'{fn[:-4]}_bm.png'
    return fn


def lens_texture():
    from PIL import Image
    t, b = np.array(LENS_RGB[0]), np.array(LENS_RGB[1])
    y = np.linspace(0, 1, 64)[:, None, None]
    a = (t * (1 - y) + b * y) * 255 * np.ones((64, 64, 3))
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(f'{KIT}/{LENS}')


ANC = {}     # id(h2w) -> per Halo 2 node, the node whose bind pose its vertices are carried from (itself, or the
             # nearest ancestor the CE skeleton has: Halo 2's jaw, lip, brow, eye and finger bones go rigidly with the
             # head or hand, as they are in the bind pose, rather than being moved onto the head's own frame)


def ancestors(nodes, ce):
    out = []
    for k in range(len(nodes)):
        j = k
        while j is not None and j >= 0 and 'bip01 ' + nodes[j]['name'].replace('_', ' ') not in ce: j = nodes[j].get('parent', -1)
        out.append(j if j is not None and j >= 0 else 0)
    return out


def retarget(mm, h2w, cew, tomap, pre=None):
    """vertices from their Halo 2 bones' bind poses to the CE bones' (pre: a transform into the model's space first)"""
    pos = np.array(mm['pos'], float); nrm = np.array(mm['nrm'], float)
    if pre is not None: pos, nrm = pre(pos, nrm)
    bi, bw = np.array(mm['bi']), np.array(mm['bw'], float)
    P = np.zeros_like(pos); N = np.zeros_like(nrm); cb = np.zeros((len(pos), 4), int); cw = np.zeros((len(pos), 4))
    for v in range(len(pos)):
        acc = {}
        for k in range(bi.shape[1]):
            w = bw[v, k]
            if w <= 0: continue
            h = int(bi[v, k]); c = tomap[h]
            th, qh = h2w[ANC[id(h2w)][h]] if id(h2w) in ANC else h2w[h]; tc, qc = cew[c]
            q = _qmul(qc, conj(qh))
            P[v] += w * (tc + qrot(q, pos[v] - th)); N[v] += w * qrot(q, nrm[v])
            acc[c] = acc.get(c, 0) + w
        tot = sum(acc.values()) or 1
        P[v] /= tot; N[v] /= max(np.linalg.norm(N[v]), 1e-6)
        for k, (c, w) in enumerate(sorted(acc.items(), key=lambda x: -x[1])[:4]): cb[v, k] = c; cw[v, k] = w / tot
    w8 = np.round(cw * 255).astype(int); w8[:, 0] += 255 - w8.sum(1)
    return P, N, cb.astype(np.uint8), np.clip(w8, 0, 255).astype(np.uint8)


def main():
    from h2map import H2Map, render_model
    import extract_h2_brute as hb
    os.makedirs(KIT, exist_ok=True)
    m = H2Map(MAP01B, CACHE01B)
    J, _, _ = read_iqm(f'{OUT}/models/Elite/Elite.iqm')
    bind = [dict(name='bind', fps=30.0, loop=True, frames=[[(j[2], j[3], (1.0, 1.0, 1.0)) for j in J]])]
    ce = {j[0]: i for i, j in enumerate(J)}
    cew = wq([(j[1], j[2], j[3]) for j in J])
    meta = dict(pieces={})
    tex_done = {}
    def texture_for(R, shader, tint=None):
        if shader not in tex_done:
            fn = f'ek_{shader}.png'
            colour_map(m, hb, shader_bitmaps(m, R, shader), fn, tint)
            tex_done[shader] = fn
        return tex_done[shader]
    for pid, (tag, keep, skip) in PIECES.items():
        R = render_model(m, tag); nodes = R['nodes']
        h2w = wq([(n.get('parent', -1), n['t'], n['q']) for n in nodes])
        tomap = [ce_bone_of(n['name'], nodes, ce) for n in nodes]
        ANC[id(h2w)] = ancestors(nodes, ce)
        meshes = []
        for mm in hb.model_meshes(m, R, keep=keep):
            if mm['shader'] in skip: continue
            if 'lens' in mm['shader']:
                lens_texture(); mat = LENS
            elif 'inset_lights' in mm['shader']:          # the lights' own shader samples the body's torso map: its glyphs
                mat = texture_for(R, 'ranger_torso' if pid == 'ranger_body' else 'torso', PIECE_TINT.get(pid))
                if pid in INSET_GLOW: mat = inset_glow(mat, INSET_GLOW[pid])
            else:
                mat = texture_for(R, mm['shader'], PIECE_TINT.get(pid))
            P, N, cb, w8 = retarget(mm, h2w, cew, tomap)
            if mat == LENS: N = bulge(P, N, mm['tris'])
            tris = np.array(mm['tris'])[:, [0, 2, 1]]
            # one surface per limb (body, left arm, right arm, head), so a severed limb's pieces can go with it
            limb = np.array([LIMB.get(J[cb[t[0], 0]][0], 0) for t in tris]) if pid in SPLIT else np.zeros(len(tris), int)
            for L in range(4):
                if not (limb == L).any() and L > 0: continue
                meshes.append(dict(name=f'{mm["region"]}_{mm["shader"]}_{L}', material=mat, pos=P, nrm=N, uv=np.array(mm['uv'], float),
                                   bidx=cb, bw=w8, tris=tris[limb == L]))
            meta.setdefault('limbs', {})[pid] = [m_['name'] for m_ in meshes]
            print(f'  {pid}: {mm["region"]}:{mm["perm"]} {mm["shader"]} {len(P)} verts {len(mm["tris"])} tris')
        write_iqm(f'{KIT}/{pid}.iqm', J, meshes, bind)
        meta['pieces'][pid] = dict(file=pid + '.iqm', tris=int(sum(len(x['tris']) for x in meshes)))
    # the jump pack: a one-node model placed by the Ranger's 'jetpack' marker (upper spine), bound to the CE spine1
    R = render_model(m, RANGER); nodes = R['nodes']; names = [n['name'] for n in nodes]
    h2w = wq([(n.get('parent', -1), n['t'], n['q']) for n in nodes])
    a = m.tag('mode', RANGER)['addr']; mk = None
    for g in m.block(a + 0x58, 0xC):
        if m.sid(m.u('I', g)[0]) != 'jetpack': continue
        for k in m.block(g + 4, 0x24):
            node = m.u('4b', k)[2]; mk = (node, np.array(m.u('3f', k + 4)), np.array(m.u('4f', k + 0x10)))
    node, mt, mq = mk
    nt, nq = h2w[node]
    def place(pos, nrm):
        q = _qmul(nq, mq)
        return np.array([nt + qrot(nq, mt + qrot(mq, p)) for p in pos]), np.array([qrot(q, n) for n in nrm])
    JP = render_model(m, JETPACK)
    meshes = []
    for mm in hb.model_meshes(m, JP):
        if 'exhaust' in mm['shader']: continue
        if mm['shader'] not in tex_done:
            colour_map(m, hb, shader_bitmaps(m, JP, mm['shader']), f'ek_{mm["shader"]}.png', tint=JETPACK_TINT); tex_done[mm['shader']] = f'ek_{mm["shader"]}.png'
        mm = dict(mm, bi=np.full((len(mm['pos']), 4), node), bw=np.tile([1.0, 0, 0, 0], (len(mm['pos']), 1)))
        P, N, cb, w8 = retarget(mm, h2w, cew, [ce_bone_of(n['name'], nodes, ce) for n in nodes], pre=place)
        meshes.append(dict(name=mm['shader'], material=texture_for(JP, mm['shader']), pos=P, nrm=N, uv=np.array(mm['uv'], float),
                           bidx=cb, bw=w8, tris=np.array(mm['tris'])[:, [0, 2, 1]]))
        print(f'  elite_jetpack: {mm["shader"]} {len(P)} verts, on {names[node]} -> {J[cb[0, 0]][0]}')
    write_iqm(f'{KIT}/elite_jetpack.iqm', J, meshes, bind)
    meta['pieces']['elite_jetpack'] = dict(file='elite_jetpack.iqm', tris=int(sum(len(x['tris']) for x in meshes)))
    meta['spec'] = SPEC; meta['brightmaps'] = BRIGHT
    for f in ('ranger_helmet.iqm', 'honor_helmet.iqm', 'honor_armor.iqm'):   # the earlier pieces, before each had its body
        if os.path.exists(f'{KIT}/{f}'): os.remove(f'{KIT}/{f}')
    json.dump(meta, open(f'{KIT}/EliteKit.json', 'w'), indent=1)
    print('->', KIT, sorted(meta['pieces']))


if __name__ == '__main__':
    main()
