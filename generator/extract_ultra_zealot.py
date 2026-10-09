"""The Ultra Zealot: Shigure's Zealot Elite (elite.blend from Ultra_Zealot.zip) on the Halo CE Elite -> out/models/EliteZealot/

    python3 extract_ultra_zealot.py

elite.blend is the Halo CE Elite rebuilt with Zealot armour by Shigure: a crested Zealot helmet and ornament, the
Zealot torso and Reach-style arm plates over the Elite Special's undersuit and legs, and a diamond energy shield on
the left forearm. Every piece is rigged to the Halo CE Elite's skeleton ('bip01 ...' groups; the shield has none and
rides the left forearm), so it goes on the Elite's own skeleton and animations, and stands like any sword Elite. Its
guard, taken up when it takes cover from fire, and its sword actions are SPV3's shield Elite's (a30_1.map, 'elite
shield new': the Elite Vanguard animations by Masterz1337 and Ruby of Blue; the shield arm held out in front). The
Halo CE energy sword is kept from the Elite (its weapon surfaces). Textures are Halo CE's own (read from b30.map by shader
name: base map, multipurpose map), so build_pack.py paints the armour like any Elite rank; the inset lights are
turned Reach blue, and the shield keeps the Jackal shield's noise for build_pack.bake_shield (a blue energy field,
animated and drawn bright like the Jackals').
Run after extract_chars.py; then gore_kit.py, blood_kit.py and alpha_fix.py take EliteZealot like the other Elites.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, shutil
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import brute_kit as bk
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')

BLEND = os.environ.get('HCE_ULTRA_ZEALOT', os.path.join(HERE, 'extra', 'rev elite', 'elite.blend'))   # from Ultra_Zealot.zip
from hce_paths import MAPS_DIR as CE_MAPS     # Halo CE's maps (HCE_MAPS)
CHAR = 'EliteZealot'
PIECES = ('base_torso', 'zealot_torso', 'basic_special', 'shoulder_general', 'zealot_arms_reach', 'special_legs',
          'zealot', 'zealot_ornament', 'shield.001')
# blend material -> Halo CE shader
SHADERS = {'elite arms': r'characters\elite\shaders\elite arms', 'elite head': r'characters\elite\shaders\elite head',
           'elite heada': r'characters\elite\shaders\elite heada', 'elite legs': r'characters\elite\shaders\elite legs',
           'elite teeth': r'characters\elite\shaders\elite teeth', 'elite torso': r'characters\elite\shaders\elite torso',
           'elite inset lights': r'characters\elite\shaders\elite inset lights',
           'elite special body': r'characters\elite\elite_special\shaders\elite special body',
           'elite special inset lights': r'characters\elite\elite_special\shaders\elite special inset lights',
           'jackal shield': r'characters\jackal\shaders\jackal shield'}
SPV3_A30 = os.environ.get('HCE_SPV3_A30', 'a30_1.map')
SHIELD_BIPED = r'characters\elite\elite shield\elite shielded'
# SPV3's shield Elite (a30: 'elite shield new', on the Halo CE Elite's skeleton), its shield arm held out in front: the
# Zealot's guard, taken up when it takes cover from fire ('guard sword ...', the API's GUARD kinds); otherwise it
# stands and moves like every sword Elite. pack name <- SPV3 name (its 'new' stance set, and its own sword actions)
SHIELD_ANIMS = {'guard sword idle': 'new stand idle',
                'guard sword move-front': 'new stand move front', 'guard sword move-back': 'new stand move back',
                'guard sword move-left': 'new stand move left', 'guard sword move-right': 'new stand move right',
                'crouch guard sword idle': 'new crouch idle', 'crouch guard sword move-front': 'new crouch move front'}
LIGHTS = ('elite inset lights', 'elite special inset lights')
SHIELD = 'jackal shield'
REACH_BLUE = np.array([0.30, 0.66, 1.00], np.float32)


def ce_textures():
    """material -> (base RGBA image, multipurpose RGBA image or None)"""
    from tags import HMap
    from bitmaps import bitmap_image
    from extract_chars import shader_maps
    m = HMap(f'{CE_MAPS}/b30.map')
    by = {t['name']: t for t in m.tags if t['cls'] in ('soso', 'sotr')}
    out = {}
    for mat, sh in SHADERS.items():
        t = by.get(sh)
        if not t: print('no shader', sh); continue
        base, multi, _ = shader_maps(m, {'id': t['id']})
        im = bitmap_image(m, base) if base else None
        mu = bitmap_image(m, multi) if multi else None
        out[mat] = (im.convert('RGBA') if im is not None else None, mu.convert('RGBA') if mu is not None else None)
    return out


def lights(im):
    """inset lights in Reach's blue: the light's brightness kept, its hue turned"""
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
    v = a.max(2, keepdims=True)
    o = np.clip(REACH_BLUE * v * 1.25 + np.clip(v - 0.75, 0, 1) * 0.9, 0, 1)
    return Image.fromarray((o * 255).astype(np.uint8))


def shield_anims():
    """SPV3's shield Elite (a30) -> (anims, anim meta) under the pack's sword-stance names, or None"""
    if not os.path.exists(SPV3_A30): print('no', SPV3_A30, ': the Zealot keeps the Elite sword animations, no guard'); return None
    import tempfile
    import halomodel as hm
    import extract_chars as ec
    from pcmap import PCMap, gbx_geometry
    m = PCMap(SPV3_A30)
    tmp = tempfile.mkdtemp(); os.makedirs(f'{tmp}/models')
    old = ec.OUT, ec.char_weapons, hm.Model.geometry
    _geo = hm.Model.geometry
    ec.OUT = tmp; ec.char_weapons = lambda name: []
    hm.Model.geometry = lambda s_, gi: gbx_geometry(s_.m, s_.geoms[gi].addr) if isinstance(s_.m, PCMap) else _geo(s_, gi)
    try:
        ec.extract(SHIELD_BIPED, 'ShieldElite', ['spv3'], {'spv3': m})
    finally:
        ec.OUT, ec.char_weapons, hm.Model.geometry = old
    _, _, an = read_iqm(f'{tmp}/models/ShieldElite/ShieldElite.iqm')
    meta = json.load(open(f'{tmp}/models/ShieldElite/ShieldElite.json'))['anims']
    shutil.rmtree(tmp)
    names = dict(SHIELD_ANIMS)
    for k in an:                                       # its own sword actions (melee, dives, evades, ...)
        if k.startswith(('stand sword ', 'crouch sword ')): names[k] = k
    return {k: an[v] for k, v in names.items() if v in an}, {k: meta[v] for k, v in names.items() if v in an}


def build():
    d = f'{OUT}/models/{CHAR}'
    os.makedirs(d, exist_ok=True)
    src = f'{OUT}/models/Elite'
    # the skeleton and every animation the Elite has now (low-ready and the rest added after gore_kit.py); its surfaces
    # (the energy sword) from the pristine copy
    joints, _, anims = read_iqm(f'{src}/Elite.iqm')
    anim_meta = json.load(open(f'{src}/Elite.json'))['anims']
    pristine = f'{src}/Elite_nogore' if os.path.exists(f'{src}/Elite_nogore.iqm') else f'{src}/Elite'
    _, emeshes, _ = read_iqm(pristine + '.iqm')
    emeta = json.load(open(pristine + '.json'))
    emeta['anims'] = anim_meta
    sa = shield_anims()
    if sa:
        for k, fr in sa[0].items():
            anims[k] = fr; emeta['anims'][k] = dict(sa[1][k], loop=emeta['anims'].get(k, sa[1][k]).get('loop', sa[1][k]['loop']))
        print('shield Elite guard and sword actions:', len(sa[0]), 'animations')
    nodes = [j[0][6:].replace(' ', '_') if j[0].startswith('bip01 ') else j[0].replace(' ', '_') for j in joints]
    lfore = nodes.index('l_forearm')
    kit = bk.Kit(BLEND)
    tex = ce_textures()
    mats = []                                   # material order -> EliteZealot_<k>
    meshes = []
    for name in PIECES:
        p = kit.piece(name, nodes)
        bi, bw = p['bi'].copy(), p['bw'].copy()
        none = bw.sum(1) == 0
        bi[none] = 0; bw[none] = 0; bi[none, 0] = lfore; bw[none, 0] = 1.0          # the shield: on the left forearm
        for k, mn in enumerate(p['mats']):
            sel = p['tmat'] == k
            if not sel.any() or mn not in tex: continue
            if mn not in mats: mats.append(mn)
            used = np.unique(p['tris'][sel]); rm = -np.ones(len(p['pos']), int); rm[used] = np.arange(len(used))
            w8 = np.round(bw[used] * 255).astype(int)
            w8[:, 0] += 255 - w8.sum(1)
            meshes.append(dict(name=f'{name}_{k}', material=f'{CHAR}_{mats.index(mn)}.png', pos=p['pos'][used],
                               nrm=p['nrm'][used], uv=np.stack([p['uv'][used, 0], 1 - p['uv'][used, 1]], 1),
                               bidx=bi[used].astype(np.uint8), bw=np.clip(w8, 0, 255).astype(np.uint8), tris=rm[p['tris'][sel]]))
    # one surface per material (UZDoom draws at most 32 per model): the pieces' surfaces of a material merged
    merged = []
    for k, mn in enumerate(mats):
        grp = [m for m in meshes if m['material'] == f'{CHAR}_{k}.png']
        base = 0; P, N, U, BI, BW, T = [], [], [], [], [], []
        for m in grp:
            P.append(m['pos']); N.append(m['nrm']); U.append(m['uv']); BI.append(m['bidx']); BW.append(m['bw']); T.append(m['tris'] + base)
            base += len(m['pos'])
        merged.append(dict(name=mn.replace(' ', '_'), material=f'{CHAR}_{k}.png', pos=np.concatenate(P), nrm=np.concatenate(N),
                           uv=np.concatenate(U), bidx=np.concatenate(BI), bw=np.concatenate(BW), tris=np.concatenate(T)))
    # the Elite's energy sword
    mw = emeta.get('mesh_weapon') or []
    weapons = [(m, mw[i]) for i, m in enumerate(emeshes) if i < len(mw) and mw[i] == 'energy_sword']
    for m, _ in weapons:
        shutil.copy(f'{src}/{m["material"]}', f'{d}/{m["material"]}')
    allm = merged + [m for m, _ in weapons]
    # textures
    has_multi = []
    for k, mn in enumerate(mats):
        im, mu = tex[mn]
        fn = f'{d}/{CHAR}_{k}.png'
        if mn in LIGHTS: lights(im).save(fn)
        elif mn == SHIELD: im.convert('RGB').save(fn)              # build_pack.bake_shield makes it the energy field
        elif mn == 'elite teeth': im.save(fn)                    # alpha_fix.py cuts it out
        else:
            im.convert('RGB').save(fn)
            if mu is not None:
                mu.resize(im.size).save(f'{d}/{CHAR}_{k}_multi.png'); has_multi.append(k)
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta = {k: v for k, v in emeta.items() if k not in ('gore', 'blood', 'mesh_names')}
    meta.update(id=CHAR, tag='shigure:elite.blend (Ultra Zealot)', materials=[f'{CHAR}_{k}' for k in range(len(mats))],
                meshes=[m['material'] for m in allm], mesh_weapon=[None] * len(merged) + [w for _, w in weapons],
                has_multi=has_multi, zealot_materials=mats,
                glow=[f'{CHAR}_{mats.index(m)}' for m in mats if m in LIGHTS], shield=f'{CHAR}_{mats.index(SHIELD)}')
    meta['iqm_bytes'] = write_iqm(f'{d}/{CHAR}.iqm', [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], allm, alist)
    json.dump(meta, open(f'{d}/{CHAR}.json', 'w'), indent=1)
    for f in ('iqm', 'json'):                                   # gore_kit.py starts from the pristine copy
        for old in (f'{d}/{CHAR}_nogore.{f}',):
            if os.path.exists(old): os.remove(old)
    print(CHAR, len(allm), 'surfaces', {m['name']: len(m['tris']) for m in allm})


if __name__ == '__main__':
    build()
