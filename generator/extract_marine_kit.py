"""Elefant's Marine kit (marine.blend + elefant.zip) -> one small IQM per accessory, for the Marines to mix and match.

    python3 extract_marine_kit.py      # -> out/models/MarineKit/<piece>.iqm, textures, MarineKit.json
    python3 extract_marine_kit.py odst_helmet_filters ...     # only those pieces, into the kit already extracted

Elefant rebuilt Halo CE's Marine in Blender and gave it a wardrobe: helmets and headgear, headsets, HUD eyepieces,
goggles and glasses, masks, pouches, packs, radios, sleeping bags, shoulder pads and gloves, all rigged to the Halo CE
Marine skeleton. The .blend links its textures rather than packing them: the pieces on Halo CE's own texture sheets
(Elefant's "woodland" camo sheets share CE's layouts) take Halo CE's bitmaps, read from the CE maps; the rest take the
bitmaps in elefant.zip (Elefant's 'innie' set), and the balaclavas and glasses the head add-ons sheet. Pieces whose textures aren't in either (Elefant's new faces, the
'head add ons' sheet) and the Insurrectionist, ODST, stealth and damaged sets are left out.

Every piece keeps the full Marine skeleton, so in game it is a model attachment riding the Marine's own animation, as
the Brutes' armour kit does (build_pack.marine_kit_code). Slots (model attachments): 1 headgear (a whole head, or a
helmet shell worn in place of Halo CE's helmet), 2 face and head add-ons, 3 chest, 4 back, 5 shoulders, 8 gloves (replace the
arms), 9 leg armour, 10 gauntlets, 11 waist. ODST pieces come as a whole outfit (OUTFITS) on some Armored Marines, some of the closed ODST helmets with the blend's
orphaned pair of gas-mask filters on the chin; the
launcher tube and the fuel tanks go with the rocket launcher and the flamethrower (WEAPON_BACKS). Faces in the kit get the same clean jaw hinge as the base faces (jaw_weights.py).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, shutil, zipfile, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import elefant_kit as ek, brute_kit, jaw_weights
from iqm import write_iqm, read_iqm

from hce_paths import OUT
BLEND = ek.BLEND
ZIP = os.environ.get('HCE_MARINE_KIT_ZIP', os.path.join(HERE, 'extra', 'elefant.zip'))
ADDONS = os.environ.get('HCE_MARINE_KIT_ADDONS', os.path.join(HERE, 'extra', 'head_add_ons.tif'))   # Elefant's head add-ons sheet
from hce_paths import MAPS_DIR as CE_MAPS     # Halo CE's maps (HCE_MAPS)
INNIE = 'elefant/characters/innie/bitmaps/'
# the .blend's image -> Halo CE bitmap (map, tag) or the zip's file
CE = {
    'woodland_marine_body.tif': ('a50', r'characters\marine\bitmaps\marine_body'),
    'woodland_marine_hats.tif': ('a10', r'characters\marine\bitmaps\marine_hats'),
    'woodland_marine_helmet.tif': ('a30', r'characters\marine_armored\bitmaps\marine_helmet'),
    'marine_helmet.tif.001': ('a30', r'characters\marine_armored\bitmaps\marine_helmet'),
    'woodland_marine_arms.tif': ('a30', r'characters\marine_armored\bitmaps\marine_arms'),
    'woodland_marine_legs.tif': ('a30', r'characters\marine_armored\bitmaps\marine_legs'),
    'woodland_marine_torso.tif': ('a30', r'characters\marine_armored\bitmaps\marine_torso'),
    'marine_torso.tif': ('a30', r'characters\marine_armored\bitmaps\marine_torso'),
    'marine_helmet_hud.tif': ('a30', r'characters\marine_armored\bitmaps\marine_helmet_hud'),
    'pilot_body.tif': ('a30', r'characters\pilot\bitmaps\pilot_body'),
    'healthpack.tga': ('a30', r'powerups\healthpack\bitmaps\healthpack'),
    'frag grenade.tga': ('a30', r'weapons\frag grenade\bitmaps\frag grenade'),
    'frag grenade decal.tga': ('a30', r'weapons\frag grenade\bitmaps\frag grenade decal'),
    'sr ammo.tga': ('a30', r'powerups\sniper rifle ammo\bitmaps\sr ammo'),
    'rocket launcher black.tiff': ('b30', r'weapons\rocket launcher\bitmaps\rocket launcher'),
    'flamethrower ammo.tga': ('c20', r'powerups\flamethrower ammo\bitmaps\flamethrower ammo'),
    'face_charles.tif': ('a10', r'characters\marine\bitmaps\face_charles'),
    'face_marcus.tif': ('a10', r'characters\marine\bitmaps\face_marcus'),
    'face_matt.tif': ('a10', r'characters\marine\bitmaps\face_matt'),
    'face_rob.tif': ('a10', r'characters\marine\bitmaps\face_rob'),
    'face_shiek.tif': ('a10', r'characters\marine\bitmaps\face_shiek'),
    'face_chris.tif': ('a10', r'characters\marine\bitmaps\face_chris'),
    'face_fred.tif': ('a50', r'characters\marine\bitmaps\face_fred'),
    'face_paul.tif': ('a50', r'characters\marine\bitmaps\face_paul'),
}
# materials whose node tree names no image: what they stand for
FALLBACK = {'innie_cigar': 'innie_cigar.tif', 'visor': 'innie_visor_diff.tif', 'marine_hats': 'woodland_marine_hats.tif',
            'marine_helmet': 'woodland_marine_helmet.tif', 'marine_torso': 'marine_torso.tif', 'marine_body': 'woodland_marine_body.tif',
            'frag light': 'frag grenade.tga', 'h1_odst_visor': 'innie_visor_diff.tif'}
FACES = ('face_', 'eyes_')
# blend object -> (piece id, slot). Slots: head (replaces the head), face, chest, back, shoulders, arms (replaces arms)
PIECES = {
    # headgear: helmet shells worn over an Armored Marine's own face in place of Halo CE's helmet, and whole heads
    # (Elefant's helmets on Halo CE's Fred and Marcus faces; the closed and enclosed helmets)
    'helm_tilted': ('helmet_tilted', 'head'), 'helm': ('helmet_strapped', 'head'),
    'head:fred_helmet': ('helmet_fred', 'head'), 'head:marcus_helmet': ('helmet_marcus', 'head'),
    'helm_closed': ('helmet_closed', 'head'), 'helm_enclosed': ('helmet_enclosed', 'head'),
    'helm_hellbringer': ('helmet_hellbringer', 'head'),
    # whole heads with a balaclava or a cap (the head add-ons sheet)
    'face_charles_bala': ('charles_balaclava', 'head'), 'face_paul_cap': ('paul_cap', 'head'),
    'head:marcus_belaclava': ('helmet_marcus_balaclava', 'head'), 'head:matt_balaclava': ('helmet_matt_balaclava', 'head'),
    'head:shiek_helmet_bala': ('helmet_shiek_balaclava', 'head'),
    # ODST: helmets (the shock-trooper shell over the Marine's own face), headset, vest, leg armour, pads, gauntlets, cape
    'helm_odst': ('odst_helmet', 'head'), 'helm_odst_shock': ('odst_helmet_shock', 'head'), 'helm_odst_shock.003': ('odst_helmet_open', 'head'),
    # the closed ODST helmets with the blend's orphaned pair of gas-mask filters (addon_gasmask.001) on the chin
    ('helm_odst', 'addon_gasmask.001'): ('odst_helmet_filters', 'head'),
    ('helm_odst_shock', 'addon_gasmask.001'): ('odst_helmet_shock_filters', 'head'),
    'addons_head_set_odst': ('odst_headset', 'face'), 'addons_head_set_odst_b': ('odst_headset_b', 'face'),
    'torso_odst': ('odst_vest', 'chest'), 'legs_odst': ('odst_legs', 'legs'), 'pads_odst': ('odst_pads', 'shoulders'),
    'pads_odst_heavy': ('odst_pads_heavy', 'shoulders'), 'arms_gauntlet_odst': ('odst_gauntlets', 'wrists'),
    'odst_cape': ('odst_cape', 'waist'),
    # the flamethrower Marines' fuel tanks (always theirs: build_pack.marine_kit_code)
    'chest_flamer': ('flamer_tank', 'back'),
    # face / head add-ons
    'addons_head_set_mic': ('headset_mic', 'face'), 'addons_head_set_mic_b': ('headset_mic_b', 'face'), 'mic': ('headset_boom', 'face'),
    'addons_eye_piece': ('hud_eyepiece', 'face'), 'addons_eye_piece_tilted': ('hud_eyepiece_tilted', 'face'),
    'addon_goggles': ('goggles', 'face'), 'addon_pilot goggles': ('pilot_goggles', 'face'), 'addon_sniper goggles': ('sniper_goggles', 'face'),
    'addon_glasses': ('glasses', 'face'), 'addon_cigar': ('cigar', 'face'), 'addon_gasmask': ('gas_mask', 'face'),
    'addon_balaclava': ('face_wrap', 'face'),
    'helm_jawstrap': ('helmet_strap_goggles', 'face'),       # goggles on the band and a chin strap, over Halo CE's helmet
    # chest
    'pouches': ('pouches', 'chest'), 'pouches_a': ('pouches_a', 'chest'), 'pouches_c': ('pouches_grenades', 'chest'),
    'pouches_d': ('pouches_grenades_b', 'chest'), 'pouches_e': ('pouches_grenades_c', 'chest'), 'pouch': ('pouch', 'chest'),
    'chest_pad': ('chest_rig', 'chest'), 'first aid': ('first_aid', 'chest'), 'nades_a': ('grenade_belt', 'chest'), 'addon_scarf': ('scarf', 'chest'),
    # back
    'radiopack': ('radio_pack', 'back'), 'backpack': ('backpack', 'back'), 'sleeping bag': ('bedroll', 'back'),
    'sleeping bag.001': ('bedroll_b', 'back'), 'sr_pack': ('ammo_pack', 'back'), 'tube': ('launcher_tube', 'back'),
    # shoulders
    'pads_small': ('pads_small', 'shoulders'), 'pads_medium': ('pads_medium', 'shoulders'), 'pads_long': ('pads_long', 'shoulders'),
    # arms (replace the Marine's arms)
    'arms:sleeves_gloves': ('arms_gloves', 'arms'), 'arms:sleeves_gauntlets': ('arms_gauntlets', 'arms'),
    'arms:sleeves_guantlets_gloves': ('arms_gauntlets_gloves', 'arms'),
}
SLOTS = {'head': 1, 'face': 2, 'chest': 3, 'back': 4, 'shoulders': 5, 'arms': 8, 'legs': 9, 'wrists': 10, 'waist': 11}
ENCLOSED = {'helmet_closed', 'helmet_enclosed', 'odst_helmet', 'odst_helmet_shock', 'odst_helmet_filters', 'odst_helmet_shock_filters'}                  # no face showing: no face add-ons over them
SHELLS = {'helmet_tilted', 'helmet_strapped', 'helmet_hellbringer', 'odst_helmet_open'}  # worn over the Marine's own (helmeted) face: hide only CE's helmet
NEEDS_HELMET = {'helmet_strap_goggles'}                       # only over Halo CE's own helmet
# a weapon's own back piece, always (and only) on the Marines carrying it
WEAPON_BACKS = {'Halo_RocketLauncher': 'launcher_tube', 'Halo_Flamethrower': 'flamer_tank'}
# whole outfits: (chance, {slot: [(piece, weight)], '' = nothing}); rolled before the slots
OUTFITS = {
    'MarineArmored': [(0.15, dict(head=[('odst_helmet', 3), ('odst_helmet_shock', 2), ('odst_helmet_open', 2), ('odst_helmet_filters', 1), ('odst_helmet_shock_filters', 1)], chest=[('odst_vest', 1)],
                                  legs=[('odst_legs', 1)], shoulders=[('odst_pads', 2), ('odst_pads_heavy', 1)],
                                  wrists=[('odst_gauntlets', 1)], waist=[('odst_cape', 1), ('', 1)], face=[('odst_headset', 1), ('odst_headset_b', 1), ('', 2)]))],
}
# per body: chance a slot is filled, and the weighted picks
POOLS = {
    'Marine': dict(
        face=(0.35, [('headset_mic', 2), ('headset_mic_b', 2), ('headset_boom', 2), ('goggles', 2), ('pilot_goggles', 1), ('sniper_goggles', 1),
                     ('glasses', 2), ('cigar', 1), ('gas_mask', 1), ('face_wrap', 2)]),
        chest=(0.45, [('pouches', 3), ('pouches_a', 3), ('pouches_grenades', 2), ('pouches_grenades_b', 2), ('pouches_grenades_c', 2),
                      ('pouch', 2), ('chest_rig', 2), ('first_aid', 2), ('grenade_belt', 2), ('scarf', 1)]),
        head=(0.12, [('charles_balaclava', 1), ('paul_cap', 1)]),
        back=(0.4, [('radio_pack', 2), ('backpack', 3), ('bedroll', 3), ('bedroll_b', 3), ('ammo_pack', 2)]),
        shoulders=(0.25, [('pads_small', 3), ('pads_medium', 2), ('pads_long', 1)]),
        arms=(0.2, [('arms_gloves', 3), ('arms_gauntlets', 1), ('arms_gauntlets_gloves', 2)])),
    'MarineArmored': dict(
        head=(0.35, [('helmet_tilted', 2), ('helmet_strapped', 3), ('helmet_fred', 3), ('helmet_marcus', 3),
                     ('helmet_closed', 1), ('helmet_enclosed', 1), ('helmet_hellbringer', 1), ('helmet_marcus_balaclava', 2),
                     ('helmet_matt_balaclava', 2), ('helmet_shiek_balaclava', 2)]),
        face=(0.4, [('headset_mic', 3), ('headset_mic_b', 3), ('headset_boom', 2), ('hud_eyepiece', 3), ('hud_eyepiece_tilted', 2),
                     ('helmet_strap_goggles', 3),
                     ('goggles', 1), ('sniper_goggles', 1), ('glasses', 1), ('gas_mask', 1)]),
        chest=(0.45, [('pouches', 3), ('pouches_a', 3), ('pouches_grenades', 2), ('pouches_grenades_b', 2), ('pouches_grenades_c', 2),
                      ('chest_rig', 1), ('first_aid', 2), ('grenade_belt', 2)]),
        back=(0.4, [('radio_pack', 3), ('backpack', 3), ('bedroll', 2), ('bedroll_b', 2), ('ammo_pack', 2)]),
        shoulders=(0.2, [('pads_small', 2), ('pads_medium', 2), ('pads_long', 2), ('odst_pads', 1)])),
}


def material_images(B):
    """material name -> its image's name (first Image node of its node tree)"""
    out = {}
    for m in B.of_type('Material'):
        B.ctx = m
        nt = B.block(B.get('Material', m.off, 'nodetree'))
        ims = []
        if nt:
            B.ctx = nt
            for n in B.listbase(B.get('bNodeTree', nt.off, 'nodes'), 'bNode'):
                idb = B.block(B.get('bNode', n.off, 'id'))
                if idb and B.stype(idb) == 'Image': ims.append(B.id_name(idb))
        out[B.id_name(m)] = ims[0] if ims else None
    return out


class Textures:
    def __init__(s, od):
        s.od = od; s.done = {}; s.maps = {}
        s.zip = zipfile.ZipFile(ZIP) if os.path.exists(ZIP) else None

    def get(s, img):
        """image name -> png file name in od, or None when it isn't available"""
        if img in s.done: return s.done[img]
        im = None
        if img in CE:
            from halomap import HMap
            from bitmaps import bitmap_image
            mp, tg = CE[img]
            m = s.maps.setdefault(mp, HMap(f'{CE_MAPS}/{mp}.map'))
            t = [x for x in m.tags if x['name'] == tg and x['cls'] == 'bitm']
            im = bitmap_image(m, t[0]['id']) if t else None
        elif img == 'head add ons.tif' and os.path.exists(ADDONS):
            im = Image.open(ADDONS); im.load()
        elif s.zip and INNIE + img in s.zip.namelist():
            import io
            im = Image.open(io.BytesIO(s.zip.read(INNIE + img))); im.load()
        if im is None: s.done[img] = None; return None
        im = im.convert('RGBA' if im.mode in ('RGBA', 'LA') else 'RGB')
        if max(im.size) > 512: im.thumbnail((512, 512), Image.LANCZOS)
        fn = 'mk_' + os.path.splitext(img.replace('.001', ''))[0].replace(' ', '_').replace('.', '_') + '.png'
        im.save(os.path.join(s.od, fn))
        s.done[img] = fn
        return fn


def merged_piece(K, objs, nodes):
    """one piece from several blend objects (a helmet and the filters on it): their meshes and materials together"""
    ps = [K.piece(o, nodes) for o in objs]
    mats = []; tm = []; tris = []; base = 0
    for p in ps:
        ix = []
        for mn in p['mats']:
            if mn not in mats: mats.append(mn)
            ix.append(mats.index(mn))
        tm.append(np.array(ix)[p['tmat']]); tris.append(p['tris'] + base); base += len(p['pos'])
    out = {k: np.concatenate([p[k] for p in ps]) for k in ('pos', 'nrm', 'uv', 'bi', 'bw')}
    out.update(tris=np.concatenate(tris), tmat=np.concatenate(tm), mats=mats)
    return out


def main(only=None):
    """only: piece ids to (re)build into the existing kit, keeping the rest"""
    od = f'{OUT}/models/MarineKit'
    if not only:
        if os.path.isdir(od): shutil.rmtree(od)
        os.makedirs(od)
    joints, bmeshes, _ = read_iqm(f'{OUT}/models/Marine/Marine.iqm')
    nodes = ek.marine_nodes(joints)
    K = ek.Kit(BLEND)
    mimg = material_images(K.B)
    tex = Textures(od)
    body = dict(pos=np.concatenate([m['pos'] for m in bmeshes]), bi=np.concatenate([m['bidx'] for m in bmeshes]).astype(int),
                bw=np.concatenate([m['bw'] for m in bmeshes]).astype(float) / 255.0)
    bind = [[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]]
    meta = dict(slots=SLOTS, pieces={}, pools={}, enclosed=sorted(ENCLOSED))
    if only:
        meta['pieces'] = json.load(open(f'{od}/MarineKit.json'))['pieces']
        for pid in only: meta['pieces'].pop(pid, None)
    for obj, (pid, slot) in PIECES.items():
        if only and pid not in only: continue
        p = brute_kit.fill_weights(merged_piece(K, obj, nodes) if isinstance(obj, tuple) else K.piece(obj, nodes), body)
        uv = p['uv'].copy(); uv[:, 1] = 1.0 - uv[:, 1]
        bi = p['bi'].astype(np.uint8); bw = np.round(p['bw'] * 255).astype(np.uint8)
        bw[:, 0] += (255 - bw.sum(1).astype(int)).astype(np.uint8)
        meshes, names, skipped = [], [], []
        for mi in sorted(set(p['tmat'].tolist())):
            mn = p['mats'][mi] if mi < len(p['mats']) else ''
            img = mimg.get(mn) or FALLBACK.get(mn)
            fn = tex.get(img) if img else None
            if not fn: skipped.append(mn); continue
            t = p['tris'][p['tmat'] == mi][:, [0, 2, 1]]
            used = np.unique(t)
            key = np.concatenate([np.round(p['pos'][used] * 1e5), np.round(p['nrm'][used] * 1e3), np.round(uv[used] * 1e5), bi[used], bw[used]], axis=1)
            _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
            keep = used[first]
            remap = np.full(len(p['pos']), -1); remap[used] = inv.ravel()
            meshes.append(dict(name=f'{pid}_{len(meshes)}', material=fn, pos=p['pos'][keep], nrm=p['nrm'][keep], uv=uv[keep],
                               bidx=bi[keep].copy(), bw=bw[keep].copy(), tris=remap[t]))
            names.append('head.kit' if mn.startswith(FACES) else '')
        if not meshes: print(f'  {pid}: nothing left, skipped'); continue
        if 'head.kit' in names: jaw_weights.fix(joints, meshes, names)       # a clean jaw hinge, as the base faces
        write_iqm(f'{od}/{pid}.iqm', joints, meshes, [dict(name='bind', fps=30.0, loop=True, frames=bind)])
        meta['pieces'][pid] = dict(slot=slot, source='+'.join(obj) if isinstance(obj, tuple) else obj, file=pid + '.iqm', shell=pid in SHELLS, enclosed=pid in ENCLOSED, needs_helmet=pid in NEEDS_HELMET, tris=int(sum(len(m['tris']) for m in meshes)))
        print(f'{pid:24s} {slot:9s} {meta["pieces"][pid]["tris"]:5d} tris' + (f'  (no texture, left out: {skipped})' if skipped else ''))
    for body_, pools in POOLS.items():
        meta['pools'][body_] = {s: dict(chance=c, picks=[(p, w) for p, w in picks if p in meta['pieces']]) for s, (c, picks) in pools.items()}
    meta['outfits'] = {b: [dict(chance=c, slots={s: [(p, w) for p, w in picks if not p or p in meta['pieces']] for s, picks in o.items()})
                           for c, o in outs] for b, outs in OUTFITS.items()}
    meta['weapon_backs'] = {w: p for w, p in WEAPON_BACKS.items() if p in meta['pieces']}
    json.dump(meta, open(f'{od}/MarineKit.json', 'w'), indent=1)
    size = sum(os.path.getsize(os.path.join(od, f)) for f in os.listdir(od))
    print(len(meta['pieces']), 'pieces,', size // 1024, 'KB')


if __name__ == '__main__':
    # python3 extract_marine_kit.py [piece ...]: only those pieces, added to the kit already extracted
    main(sys.argv[1:] or None)
