"""Halo 2's Elite armour on the Halo CE Elite -> $HCE_OUT/models/EliteKit/*.iqm

    python3 extract_h2_elite_kit.py

Halo 2's Elite (01b_spacestation.map: HCE_H2_MAP, textures from HCE_H2_TEXTURES) is the same 3ds Max biped as Halo CE's
(h2_elite_anims.py), so its armour can be carried onto the CE Elite bone by bone, as extract_h2_odst.py carries the
ODST onto the CE Marine: each vertex goes from its Halo 2 bone's bind pose to the matching CE bone's, with its weights.
The pieces are model attachments riding the CE Elite's own animation (build_pack.ELITE_KIT):

    honor_guard.iqm    the Honor Guard's helmet (its tall crest) and its ceremonial plates on the shoulders, arms and
                       legs (the Elite's 'helmet: honor' and 'hg: honor' permutations, with their inset lights)
    ranger_helmet.iqm  the Ranger's sealed EVA helmet and its lens (elite_ranger's 'helmet' region and lens)
    elite_jetpack.iqm  the Ranger's jump pack, where the Ranger's 'jetpack' marker puts it on the upper spine

Textures: Halo 2's colour maps with its bump maps' shading and its detail maps baked in (Doom lights models flat).
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
    'honor_helmet': (ELITE, {('helmet', 'honor'), ('head', 'base')}, ()),     # Halo 2's Elite head under it (the CE head is cut away)
    'honor_armor': (ELITE, {('hg', 'honor')}, ()),
    'ranger_helmet': (RANGER, {('helmet', 'base'), ('body', 'base')}, ('ranger_arms', 'ranger_torso', 'ranger_legs', 'inset_lights')),
}
SPLIT = {'honor_armor'}              # pieces cut into surfaces by limb: 0 body, 1 left arm, 2 right arm
LIMB = {f'bip01 {s} {b}': (1 if s == 'l' else 2) for s in 'lr' for b in ('clavicle', 'upperarm', 'forearm', 'hand')}
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
SKIP = ('bump', 'default_', 'color_', 'detail', 'illum', 'change_color', 'color_change', 'cube', 'reflection', 'multiplicative',
        'dirt', 'exhaust', 'carapace', 'glassy', 'noise')


def colour_map(m, hb, bms, out):
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
    if ill:                                           # the glowing markings (Doom has no glow pass here): lifted
        g = np.asarray(hb.bitmap(m, ill[0]).convert('L').resize((W, H), Image.LANCZOS), float)[..., None] / 255.0
        a = a * (1 + ILLUM_LIFT * g) + ILLUM_ADD * g * np.array([1.0, 0.25, 0.15])
    im = Image.fromarray(np.clip(a * LIFT, 0, 255).astype(np.uint8))
    if max(im.size) > 512: im.thumbnail((512, 512), Image.LANCZOS)
    im.save(f'{KIT}/{out}')
    print('   ', out, 'from', diff[0].split('\\')[-1], 'bump' if bump else '', 'detail' if det else '')


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
    def texture_for(R, shader):
        if shader not in tex_done:
            fn = f'ek_{shader}.png'
            colour_map(m, hb, shader_bitmaps(m, R, shader), fn)
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
            elif 'inset_lights' in mm['shader']:
                continue                                   # the lights' own shader samples the body's map: left off
            else:
                mat = texture_for(R, mm['shader'])
            P, N, cb, w8 = retarget(mm, h2w, cew, tomap)
            tris = np.array(mm['tris'])[:, [0, 2, 1]]
            # one surface per limb (body, left arm, right arm), so a severed arm's plates can go with it
            limb = np.array([LIMB.get(J[cb[t[0], 0]][0], 0) for t in tris]) if pid in SPLIT else np.zeros(len(tris), int)
            for L in range(3):
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
        mm = dict(mm, bi=np.full((len(mm['pos']), 4), node), bw=np.tile([1.0, 0, 0, 0], (len(mm['pos']), 1)))
        P, N, cb, w8 = retarget(mm, h2w, cew, [ce_bone_of(n['name'], nodes, ce) for n in nodes], pre=place)
        meshes.append(dict(name=mm['shader'], material=texture_for(JP, mm['shader']), pos=P, nrm=N, uv=np.array(mm['uv'], float),
                           bidx=cb, bw=w8, tris=np.array(mm['tris'])[:, [0, 2, 1]]))
        print(f'  elite_jetpack: {mm["shader"]} {len(P)} verts, on {names[node]} -> {J[cb[0, 0]][0]}')
    write_iqm(f'{KIT}/elite_jetpack.iqm', J, meshes, bind)
    meta['pieces']['elite_jetpack'] = dict(file='elite_jetpack.iqm', tris=int(sum(len(x['tris']) for x in meshes)))
    json.dump(meta, open(f'{KIT}/EliteKit.json', 'w'), indent=1)
    print('->', KIT, sorted(meta['pieces']))


if __name__ == '__main__':
    main()
