"""The Flood Brute (blackandfan's Halo 2 tag pack, 'H2EK-Tags': Halo 2's cut Brute combat form) -> $HCE_OUT/models/FloodBrute

    HCE_H2_TAGPACK=/path/to/H2EK-Tags python3 extract_flood_brute.py      # after extract_h2_brute.py, extract_spv3.py

The tag pack ships its sources beside its tags (data/objects/characters/floodcombat_brute), as for the Sentinel Knight
(extract_sentinel_knight.py, whose reading this follows): the render model as a JMS (8210: 36 nodes, the Brute's body
with a Flood claw for a left arm, tendrils and Halo 2's rank armour as regions), its animations as JMA/JMM/JMO/JMR/JMT
(16395; the same nodes without their 'b_' prefix and in another order: matched by name). Textures: its own Flood
growth (floodcombat_brute.tiff); the Brute's fur, hair and armour from extract_h2_brute.py's Halo 2 Brute (the shaders
name objects\\characters\\brute\\bitmaps\\*), the fur and hair tinted per rank with the Brute's own variant change colours;
the fronds the Flood Juggernaut's (extract_spv3.py's FloodJuggernaut). The rank pieces (heads, helmets, armour, the
Captain's flag) are surfaces of their own, worn per rank (RANKS, json 'wear'). The CE guns are baked onto the right hand at its
right_hand marker (weapon origin = marker, as extract_chars.attach_weapons does). Animations: ANIM_NAMES, renamed onto
the Flood forms' 'pistol' (Halo 2's 'any') and 'unarmed' stances; the fire overlay (JMO) is baked onto the idle.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, pickle, shutil
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
from h2jms import read_jms, read_jma
from halomodel import qmul, qrot, qconj
from iqm import write_iqm
from extract_sentinel_knight import local_frames
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')

PACK = os.environ.get('HCE_H2_TAGPACK', 'H2EK-Tags')
SRC = f'{PACK}/data/objects/characters/floodcombat_brute'
DST = f'{OUT}/models/FloodBrute'
BRUTE = f'{OUT}/models/Brute'                  # extract_h2_brute.py: the Halo 2 Brute's textures and variant colours
TEX = 512
# material (the JMS's, its shader flags stripped) -> its texture: ('brute', name) the Halo 2 Brute's Brute_<name>.png,
# tinted per rank when it has a change-colour mask; ('file', path) a texture of its own
TEXTURES = {'brute': ('brute', 'brute'), 'brute_hair': ('brute', 'brute_hair'),
            'brute_shoulder_armor': ('brute', 'brute_shoulder_armor'), 'brute_honor_armor': ('brute', 'brute_honor_armor'),
            'brute_honor_inset_lights': ('brute', 'brute_honor_inset_lights'),
            'floodcombat_brute': ('file', f'{SRC}/bitmaps/floodcombat_brute.tiff'),
            'flood_fronds': ('file', f'{OUT}/models/FloodJuggernaut/FloodJuggernaut_1.png')}
# The model's regions: the body (body, torso, legs, arms: their default pieces, one surface per material) is always
# drawn; the rank pieces are worn per rank (RANKS); their 'damaged' permutation (torn pieces in the Flood human's damage
# texture) and the empty 'honor_off' placeholders are left out (32 surfaces at most)
BODY = {'body', 'torso', 'legs', 'l_arm', 'r_arm'}
SKIP_PERMS = {'damaged', 'honor_off'}
# rank -> the Halo 2 Brute variant whose fur colours it wears, and the (region, permutation) pieces it wears: the
# Minor bare-headed under the Flood, the Major and Captain in the shoulder-armour helmet (the 'major' head; the
# Captain with its flag), the Honor Guard in its ceremonial helmet and armour
RANKS = {'minor': ('minor_bth', {('head', 'default'), ('sh_armor', 'default'), ('sensors', 'default')}),
         'major': ('major_bth', {('head', 'major'), ('sh_armor', 'default'), ('sensors', 'default')}),
         'captain': ('captain_bth', {('head', 'major'), ('sh_armor', 'default'), ('sensors', 'default'), ('flag', 'captain')}),
         'honor guard': ('minor_bth', {('head', 'honor_on'), ('sh_armor', 'honor_on'), ('hg_arm', 'honor_on'), ('hg_legs', 'honor_on'),
                                       ('sensors', 'honor_on')})}
# baked on the right hand (out/weapons/<id>/<id>.pkl): Halo CE's three Flood guns and the Brutes' Spiker
GUNS = ('assault_rifle', 'shotgun', 'plasma_rifle', 'spiker')
LOOP = ('idle', 'walk_', 'move_', 'airborne')
# source animation -> the pack's name ('%N' numbers a name's variants)
ANIM_NAMES = {
    'any any idle var1.JMM': 'stand pistol idle%0', 'any any idle var2.JMM': 'stand pistol idle%1',
    'any any move_front.JMA': 'stand pistol move-front', 'any any move_back.JMA': 'stand pistol move-back',
    'any any move_left.JMA': 'stand pistol move-left', 'any any move_right.JMA': 'stand pistol move-right',
    'any any leap_start.JMA': 'stand pistol leap-start', 'any any leap_airborne.JMA': 'stand pistol leap-airborne',
    'any any leap_melee.JMR': 'stand pistol leap-melee',
    'combat any any airborne.JMA': 'stand pistol airborne', 'combat any any land_hard.JMA': 'stand pistol land-hard',
    'combat any any land_soft.JMA': 'stand pistol land-soft',
    'combat any any land_hard.JMA ': 'stand unarmed land-hard', 'combat any any land_soft.JMA ': 'stand unarmed land-soft',
    'any any leap_melee.JMR ': 'stand unarmed leap-melee',
    'combat any any airborne_dead.JMA': 'stand airborne-dead', 'combat any any landing_dead.JMA': 'stand landing-dead',
    'combat any melee var1.JMA': 'stand pistol melee%0', 'combat any melee var2.JMA': 'stand pistol melee%1',
    'combat any smash_left.JMA': 'stand pistol melee%2', 'combat any smash_right.JMA': 'stand pistol melee%3',
    'combat any melee_tackle.JMA': 'stand pistol melee%4',
    'combat any dive_front.JMA': 'stand pistol dive-front', 'combat any dive_left.JMA': 'stand pistol dive-left',
    'combat any dive_right.JMA': 'stand pistol dive-right',
    'combat any evade_left.JMA': 'stand pistol evade-left', 'combat any evade_right.JMA': 'stand pistol evade-right',
    'combat any surprise_front.JMA': 'stand pistol surprise-front',
    'combat any turn_left.JMT': 'stand pistol turn-left', 'combat any turn_right.JMT': 'stand pistol turn-right',
    'any unarmed idle var1.JMM': 'stand unarmed idle%0', 'any unarmed idle var2.JMM': 'stand unarmed idle%1',
    'any unarmed move_front.JMA': 'stand unarmed move-front', 'any unarmed move_back.JMA': 'stand unarmed move-back',
    'any unarmed move_left.JMA': 'stand unarmed move-left', 'any unarmed move_right.JMA': 'stand unarmed move-right',
    'combat unarmed melee var1.JMA': 'stand unarmed melee%0', 'combat unarmed melee var2.JMA': 'stand unarmed melee%1',
    'combat unarmed smash_left.JMA': 'stand unarmed melee%2', 'combat unarmed smash_right.JMA': 'stand unarmed melee%3',
    'combat unarmed melee_tackle.JMA': 'stand unarmed melee%4',
    'combat unarmed dive_front.JMA': 'stand unarmed dive-front', 'combat unarmed dive_left.JMA': 'stand unarmed dive-left',
    'combat unarmed evade_left var1.JMA': 'stand unarmed evade-left', 'combat unarmed evade_right var1.JMA': 'stand unarmed evade-right',
    'combat unarmed surprise_front.JMA': 'stand unarmed surprise-front',
    'combat unarmed turn_left.JMT': 'stand unarmed turn-left', 'combat unarmed turn_right.JMT': 'stand unarmed turn-right',
    'any any resurrect_front.JMA': 'stand unarmed resurrect-front',
    'combat any any h_kill front gut var1.JMA': 'h-kill front gut%0', 'combat any any h_kill front gut var2.JMA': 'h-kill front gut%1',
    'combat any any h_kill back gut.JMA': 'h-kill back gut', 'combat any any h_kill left gut.JMA': 'h-kill left gut',
    'combat any any h_kill right gut.JMA': 'h-kill right gut',
    'combat any any h_kill front head var1.JMA': 'h-kill front head%0', 'combat any any h_kill front head var2.JMA': 'h-kill front head%1',
    'combat any any s_kill front gut.JMA': 's-kill front gut', 'combat any any s_kill back gut.JMA': 's-kill back gut',
    'combat any any s_kill left gut.JMA': 's-kill left gut', 'combat any any s_kill right gut.JMA': 's-kill right gut',
    'combat any any h_ping front gut.JMA': 'h-ping front gut', 'combat any any h_ping back gut.JMA': 'h-ping back gut',
    'combat any any h_ping left gut.JMA': 'h-ping left gut', 'combat any any h_ping right gut.JMA': 'h-ping right gut',
    'combat any any h_ping front l_arm.JMA': 'h-ping front l-arm', 'combat any any h_ping front r_arm.JMA': 'h-ping front r-arm',
    'combat any h_ping front head.JMA': 'h-ping front head',
}
FIRE = ('combat any any fire_1.JMO', 'any any idle var1.JMM', 'stand pistol fire-1 baked')   # overlay, base, name


def clean(name):
    """a JMS material name without Halo 2's shader-flag characters"""
    return name.rstrip('!=%)(*#@$^').strip()


def texture(mat, rank):
    """the rank's texture for a material -> its file name in DST (baked once)"""
    kind, src = TEXTURES[mat]
    var = RANKS[rank][0]
    tinted = kind == 'brute' and os.path.exists(f'{BRUTE}/Brute_{src}_mask.png')
    fn = f'FloodBrute_{mat}_{rank.replace(" ", "_")}.png' if tinted else f'FloodBrute_{mat}.png'
    if os.path.exists(f'{DST}/{fn}'): return fn
    path = f'{BRUTE}/Brute_{src}.png' if kind == 'brute' else src
    # the tag pack's own textures carry Halo 2's specular mask in their alpha: dropped. The fronds (the Juggernaut's,
    # black behind the strands) get their cut-out from their brightness
    im = Image.open(path); has_a = 'A' in im.mode and kind == 'brute'
    a = np.asarray(im.convert('RGBA')).astype(np.float64) / 255.0
    if mat == 'flood_fronds':
        a[..., 3] = np.clip((a[..., :3].max(-1) - 0.12) * 6.0, 0, 1); has_a = True
    if tinted:       # the Brute's fur / hair change colours (build_digsite.brute_skin's formula)
        cols = json.load(open(f'{BRUTE}/Brute.json'))['change_colors']
        cols = cols.get(var) or cols['minor_bth']
        mk = np.asarray(Image.open(f'{BRUTE}/Brute_{src}_mask.png').convert('RGB').resize(im.size)).astype(np.float64) / 255.0
        rgb = a[..., :3]
        for ch, col in ((0, cols[0]), (1, cols[1])):
            if col is None: continue
            m_ = mk[..., ch:ch + 1] if src == 'brute_hair' else mk[..., :1] if ch == 0 else None
            if m_ is None: continue
            rgb = rgb * (1 - m_) + rgb * np.array(col) * 1.5 * m_
        a[..., :3] = rgb
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), 'RGBA')
    if max(out.size) > TEX: out = out.resize((min(TEX, out.size[0]), min(TEX, out.size[1])), Image.LANCZOS)
    (out if has_a else out.convert('RGB')).save(f'{DST}/{fn}')
    return fn


def main():
    """the model's surfaces (one per region, permutation and material), the guns on the right hand, the animations,
    then FloodBrute.iqm and FloodBrute.json (extract_chars.py's layout plus wear, rank_variant and gun_surface)"""
    os.makedirs(DST, exist_ok=True)
    for f in os.listdir(DST):
        if f.startswith('FloodBrute_') and f.endswith('.png'): os.remove(f'{DST}/{f}')
    j = read_jms(open(f'{SRC}/render/floodcombat_brutenewmixed.JMS', 'rb').read())
    nodes = j['nodes']; parents = [n['parent'] for n in nodes]
    WT = np.array([n['t'] for n in nodes])[None]; WQ = np.array([n['q'] for n in nodes])[None]
    BT, BQ = local_frames(WT, WQ, parents)
    joints = [(n['name'], n['parent'], BT[0, k], BQ[0, k], (1.0, 1.0, 1.0)) for k, n in enumerate(nodes)]
    w8 = np.round(j['bw'] * 255).astype(int); w8[:, 0] += 255 - w8.sum(1)
    groups = {}
    for k, m in enumerate(j['materials']):
        region, perm = m['region'], m['perm']
        if perm in SKIP_PERMS: continue
        if region in BODY: region = 'body'
        groups.setdefault((region, perm, clean(m['name'])), []).append(k)
    meshes, names = [], []
    for (region, perm, mat), ks in sorted(groups.items()):
        if mat not in TEXTURES: print('  no texture for', mat); continue
        sel = np.isin(j['tri_mat'], ks)
        if not sel.any(): continue
        T = j['tris'][sel]; vs = np.unique(T); inv = np.full(len(j['pos']), -1); inv[vs] = np.arange(len(vs))
        for r in RANKS: texture(mat, r)
        meshes.append(dict(name=f'{region}.{perm}.{mat}', material=texture(mat, 'minor'),
                           pos=j['pos'][vs], nrm=j['nrm'][vs], uv=j['uv'][vs] * [1, -1] + [0, 1],
                           bidx=j['bidx'][vs].astype(np.uint8), bw=np.clip(w8[vs], 0, 255).astype(np.uint8),
                           tris=inv[T][:, [0, 2, 1]]))
        names.append(meshes[-1]['name'])
    # the guns, rigid on the right hand at its marker
    mk = next(m for m in j['markers'] if m['name'] == 'right_hand')
    node, mt, mq = mk['node'], np.array(mk['t']), np.array(mk['q'])
    wt, wq = WT[0, node], WQ[0, node]
    tq = qmul(wq, mq)
    mesh_weapon = [None] * len(meshes)
    for wid in GUNS:
        pk = f'{OUT}/weapons/{wid}/{wid}.pkl'
        if not os.path.exists(pk): print('  no', pk); continue
        wd = pickle.load(open(pk, 'rb'))
        merged = {}                                  # one surface per texture (UZDoom draws 32 at most)
        for wm in wd['meshes']:
            m0 = merged.get(wm['material'])
            if m0 is None: merged[wm['material']] = dict(wm); continue
            n0 = len(m0['pos'])
            m0.update(pos=np.concatenate([m0['pos'], wm['pos']]), nrm=np.concatenate([m0['nrm'], wm['nrm']]),
                      uv=np.concatenate([m0['uv'], wm['uv']]), tris=np.concatenate([m0['tris'], np.asarray(wm['tris']) + n0]))
        for k, wm in enumerate(merged.values()):
            pos = np.array([wt + qrot(wq, mt + qrot(mq, v)) for v in wm['pos']])
            nrm = np.array([qrot(tq, n) for n in wm['nrm']])
            n = len(pos); bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8); bidx[:, 0] = node; bw[:, 0] = 255
            shutil.copy(f'{OUT}/weapons/{wid}/{wm["material"]}', f'{DST}/{wm["material"]}')
            meshes.append(dict(name=f'weapon_{wid}_{k}', material=wm['material'], pos=pos, nrm=nrm, uv=wm['uv'],
                               bidx=bidx, bw=bw, tris=wm['tris']))
            mesh_weapon.append(wid); names.append(f'weapon_{wid}_{k}')
    assert len(meshes) <= 32, f'{len(meshes)} surfaces > 32'
    # animations: by node name onto the JMS's order, the root's travel moved into the json
    jn = [n['name'] for n in nodes]
    strip = lambda s: s[2:] if s.startswith('b_') else s

    def load(fn):
        a = read_jma(open(f'{SRC}/animations/{fn}', 'rb').read())
        nm = [strip(x) for x in a['names']]           # most drop the prefix, resurrect_front keeps it
        order = [nm.index(strip(n)) for n in jn]
        T = a['t'][:, order].copy(); Q = a['q'][:, order].copy()
        return a, T, Q

    anims, info = [], {}

    def add(dst, T, Q, fps, loop):
        root = T[:, 0, :2].copy()
        T = T.copy(); T[:, :, :2] -= root[:, None, :]
        LT, LQ = local_frames(T, Q, parents)
        frames = [[(LT[f, k], LQ[f, k], (1.0, 1.0, 1.0)) for k in range(len(nodes))] for f in range(len(LT))]
        step = np.diff(root, axis=0)
        info[dst] = dict(frames=len(frames), speed=float(np.hypot(step[:, 0], step[:, 1]).sum() / max(1, len(frames))), yaw=0.0,
                         loop=int(loop), key=-1, next=-1, dx=[float(root[-1, 0] - root[0, 0]), float(root[-1, 1] - root[0, 1])])
        anims.append(dict(name=dst, fps=float(fps), loop=loop, frames=frames))

    for src_name, dst in ANIM_NAMES.items():
        src_name = src_name.strip()            # (a trailing space: a second name for the same file)
        if not os.path.exists(f'{SRC}/animations/{src_name}'): print('  no', src_name); continue
        a, T, Q = load(src_name)
        add(dst, T, Q, a['fps'], any(x in src_name for x in LOOP))
    # the fire overlay baked onto the idle's first frame: its change from its own first frame, in parent space
    ov, oT, oQ = load(FIRE[0]); base, bT, bQ = load(FIRE[1])
    oLT, oLQ = local_frames(oT, oQ, parents); bLT, bLQ = local_frames(bT[:1], bQ[:1], parents)
    T2 = np.zeros_like(oLT); Q2 = np.zeros_like(oLQ)
    for f in range(len(oLT)):
        for k in range(len(nodes)):
            T2[f, k] = bLT[0, k] + (oLT[f, k] - oLT[0, k])
            Q2[f, k] = qmul(bLQ[0, k], qmul(qconj(oLQ[0, k]), oLQ[f, k]))
    frames = [[(T2[f, k], Q2[f, k] / np.linalg.norm(Q2[f, k]), (1.0, 1.0, 1.0)) for k in range(len(nodes))] for f in range(len(T2))]
    info[FIRE[2]] = dict(frames=len(frames), speed=0.0, yaw=0.0, loop=0, key=-1, next=-1, dx=[0.0, 0.0])
    anims.append(dict(name=FIRE[2], fps=float(ov['fps']), loop=False, frames=frames))
    write_iqm(f'{DST}/FloodBrute.iqm', joints, meshes, anims)
    allp = j['pos']
    meta = dict(id='FloodBrute', tag=r'objects\characters\floodcombat_brute\floodcombat_brute', maps=['H2EK-Tags'],
                joints=jn, bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info,
                materials=[m_['material'][:-4] for m_ in meshes], meshes=[m_['material'] for m_ in meshes],
                mesh_names=names, mesh_weapon=mesh_weapon, has_multi={m_['material'][:-4]: False for m_ in meshes},
                collision_height=0.95, collision_radius=0.32,
                markers={m_['name']: [dict(node=m_['node'], t=list(m_['t']), q=list(m_['q']))] for m_ in j['markers']},
                wear={r: sorted(list(p) for p in w) for r, (_, w) in RANKS.items()},
                rank_variant={r: v for r, (v, _) in RANKS.items()})
    json.dump(meta, open(f'{DST}/FloodBrute.json', 'w'), indent=1)
    print(f'-> {DST}: {len(nodes)} nodes, {len(j["tris"])} tris, {len(meshes)} surfaces, {len(anims)} animations')


if __name__ == '__main__':
    main()
