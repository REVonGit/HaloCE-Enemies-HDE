"""Brute armour kit (h2_brute.zip: brute.blend + its bitmaps) -> one small IQM per armour piece, for the Halo 2
Brute ranks to mix and match.

    python3 extract_brute_kit.py      # -> out/models/BruteKit/<piece>[_<tint>].iqm, textures, BruteKit.json

The kit has two families of pieces on the Halo 2 Brute skeleton:
* "King Hit" armour - helmets (bighorn, enclosed, wing, crusader, heavy...), chest plates, shoulder pads, bracers,
  belts and leg armour in four material tiers (very common / common / uncommon / rare) plus an orange-trimmed
  chieftain set;
* Halo 3-style armour - the Minor helmet and chest, Major shoulder pad, Captain helmet, knee/shin guards and leg
  plates (one armour sheet, tinted per rank through its change-colour mask), the jump-pack and chieftain suits;
plus the Halo 2 Brute's own helmet / shoulder plates / bandolier, re-exported on the same rig.

Every piece keeps the full Brute skeleton (same 48 nodes and bind pose), so in game it is drawn as a model
attachment that rides the Brute's own animation (decoupled animations share model 0's bones). Material names are
the texture file names, so a piece needs no skin lines. Helmets also get a static, centred copy for the pop-off
debris. Pieces with no usable weights take the weights of the nearest body vertex.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, shutil, tempfile, zipfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brute_kit
from iqm import write_iqm, read_iqm
from hce_paths import OUT

SRC = os.environ.get('HCE_BRUTE_KIT', 'h2_brute.zip')       # the armour set: brute.blend + its bitmaps (zip or folder)
KH = 'bitmaps/king_hit_textures/'
H3 = 'brute_h3/bitmaps/'
# material -> (source bitmap in the kit, or 'Brute:<shader>' for the Halo 2 Brute's own maps; tinted by rank?)
MATERIALS = {
    'very common armour': (KH + 'armour_very_common_diffuse.tif', False),
    'very common armourc': (KH + 'armour_very_common_diffuse.tif', False),
    'common armour': (KH + 'armour_common_diffuse.tif', False),
    'common armour_b': (KH + 'armour_common_diffuse.tif', False),
    'uncommon armour': (KH + 'armour_uncommon_diffuse.tif', False),
    'uncommon armourc': (KH + 'armour_uncommon_diffuse.tif', False),
    'rare armour': (KH + 'armour_rare_diffuse.tif', False),
    'rare armourc': (KH + 'armour_rare_diffusec.tif', False),
    'brute_chainmail': (KH + 'brute_chain.tif', False),
    'minor_major_armor': (H3 + 'minor_major_armorwork.tif', True),
    'armor_lights%': (H3 + 'minor_major_armorwork.tif', True),
    'chieftain_armor': (H3 + 'minor_major_armorwork.tif', True),
    'jumppack_armor': (H3 + 'minor_major_armorwork.tif', True),
    'brute': ('Brute:brute', False),
    'brute_shoulder_armor': ('Brute:brute', False),
    'tartarus_shoulder_armor': ('Brute:brute', False),
}
# Halo 3 armour colours by rank (multiplied into the sheet, x1.5 like the Halo 2 change colours)
TINTS = {'minor': (0.52, 0.62, 0.86), 'major': (0.86, 0.36, 0.26), 'captain': (0.98, 0.80, 0.42),
         'chieftain': (0.80, 0.60, 0.28), 'jumper': (0.62, 0.74, 0.62)}
# blend object -> kit piece id, slot. Slots are model attachments 1..6: helmet, chest, shoulders, arms, legs, waist.
PIECES = {
    # helmets
    'helmet_small': ('h2_helmet', 'helmet'),
    'helmet_major': ('h3_helmet_minor', 'helmet'),
    'helmet_captain': ('h3_helmet_captain', 'helmet'),
    'helmet bighorn': ('kh_helmet_bighorn', 'helmet'),
    'helmet enclosed': ('kh_helmet_enclosed', 'helmet'),
    'helmet enclosed sides': ('kh_helmet_enclosed_sides', 'helmet'),
    'helmet_heavy': ('kh_helmet_heavy', 'helmet'),
    'helmet_wing': ('kh_helmet_wing', 'helmet'),
    'helmet_wing_spine': ('kh_helmet_spine', 'helmet'),
    'helmet_wing_crusader': ('kh_helmet_crusader', 'helmet'),
    'helmet_wing_crusader_chain': ('kh_helmet_crusader_chain', 'helmet'),
    'chieftain': ('kh_helmet_chieftain', 'helmet'),
    'chieftain_b': ('kh_helmet_chieftain_b', 'helmet'),
    'helmet:chieftain': ('h3_helmet_chieftain', 'helmet'),
    'helmet:jumppack': ('h3_helmet_jumper', 'helmet'),
    # chest
    'chest_light': ('h3_chest_minor', 'chest'),
    'chest_medium': ('h3_chest_major', 'chest'),
    'chest_wires': ('kh_chest_wires', 'chest'),
    'chestplace_superlight': ('kh_chest_superlight', 'chest'),
    'chestplate_light': ('kh_chest_light', 'chest'),
    'chestplate_medium': ('kh_chest_medium', 'chest'),
    'chestplate_heavy': ('kh_chest_heavy', 'chest'),
    'bandolier': ('h2_bandolier', 'chest'),
    'bandolier_large': ('kh_bandolier', 'chest'),
    'armor:chieftain': ('h3_suit_chieftain', 'chest'),
    'armor:jumppack': ('h3_suit_jumper', 'chest'),
    # shoulders
    'shoulder_plates': ('h2_shoulders', 'shoulders'),
    'shoulder_pads_small': ('h3_shoulders_minor', 'shoulders'),
    'shoulder_pad_major': ('h3_shoulder_major', 'shoulders'),
    'shoulder_pad_big': ('kh_shoulder_big', 'shoulders'),
    'shoulder_pads_parts': ('kh_shoulders_parts', 'shoulders'),
    'shoulder_pads_huge': ('h2_shoulders_huge', 'shoulders'),
    # arms
    'wrists': ('kh_wrists', 'arms'),
    'wrist_plates': ('kh_wrist_plates', 'arms'),
    'handguard': ('kh_handguard', 'arms'),
    'chieftain_handguard': ('kh_handguard_chieftain', 'arms'),
    'arm_pads_light': ('h3_arm_pads', 'arms'),
    # legs
    'kneeguards': ('h3_kneeguards', 'legs'),
    'shins': ('h3_shins', 'legs'),
    'legs_medium': ('h3_legs_medium', 'legs'),
    'legs_spikey': ('h3_legs_spiked', 'legs'),
    'legs_plates': ('h2_leg_plates', 'legs'),
    'knee_guards2': ('kh_kneeguards', 'legs'),
    'legs_heavy.002': ('kh_legs_heavy', 'legs'),
    'legs_thick': ('kh_legs_thick', 'legs'),
    'legs_chieftain': ('kh_legs_chieftain', 'legs'),
    # waist
    'belt small': ('kh_belt', 'waist'),
    'belt long': ('kh_belt_long', 'waist'),
    'groin_plates': ('kh_groin_plates', 'waist'),
}
SLOTS = ['helmet', 'chest', 'shoulders', 'arms', 'legs', 'waist']

# Rank outfits. Each slot: [(piece, weight)] with '' = nothing; tinted Halo 3 pieces take the rank's colour (or the
# tint named after '@'). 'outfits' are whole looks that replace the slot picks at the given chance.
RANKS = {
    'minor': dict(tint='minor', slots={
        'helmet': [('h2_helmet', 3), ('h3_helmet_minor', 3), ('kh_helmet_wing', 2), ('kh_helmet_enclosed', 1), ('', 1)],
        'chest': [('', 2), ('h3_chest_minor', 3), ('kh_chest_wires', 1), ('h2_bandolier', 2), ('kh_chest_superlight', 2)],
        'shoulders': [('h2_shoulders', 3), ('h3_shoulders_minor', 3), ('', 2)],
        'arms': [('', 3), ('kh_wrists', 2)],
        'legs': [('', 3), ('h3_kneeguards', 2), ('h2_leg_plates', 1)],
        'waist': [('', 3), ('kh_belt', 1)]}),
    'major': dict(tint='major', slots={
        'helmet': [('h3_helmet_minor', 3), ('kh_helmet_spine', 2), ('kh_helmet_crusader', 2), ('kh_helmet_enclosed_sides', 2), ('kh_helmet_enclosed', 1)],
        'chest': [('h3_chest_major', 3), ('kh_chest_medium', 2), ('kh_chest_light', 2), ('kh_bandolier', 2)],
        'shoulders': [('h3_shoulder_major', 3), ('kh_shoulders_parts', 2), ('h2_shoulders', 1)],
        'arms': [('kh_wrist_plates', 2), ('kh_handguard', 2), ('h3_arm_pads', 2), ('', 1)],
        'legs': [('h3_legs_medium', 2), ('h3_legs_spiked', 2), ('kh_kneeguards', 2), ('h3_shins', 2)],
        'waist': [('kh_belt', 2), ('kh_groin_plates', 1), ('', 2)]},
        outfits=[(0.2, {'helmet': 'h3_helmet_jumper@jumper', 'chest': 'h3_suit_jumper@jumper', 'shoulders': '', 'arms': '',
                        'legs': 'h3_shins@jumper', 'waist': ''})]),
    'captain': dict(tint='captain', slots={
        'helmet': [('h3_helmet_captain', 3), ('kh_helmet_bighorn', 2), ('kh_helmet_heavy', 2), ('kh_helmet_crusader_chain', 2)],
        'chest': [('kh_chest_heavy', 3), ('h3_chest_major', 2), ('kh_chest_light', 2)],
        'shoulders': [('kh_shoulder_big', 3), ('h3_shoulder_major', 2), ('h2_shoulders_huge', 1)],
        'arms': [('kh_wrist_plates', 2), ('h3_arm_pads', 2), ('kh_handguard', 1)],
        'legs': [('kh_legs_thick', 2), ('kh_legs_heavy', 2), ('h3_shins', 1), ('kh_kneeguards', 1)],
        'waist': [('kh_belt_long', 2), ('kh_groin_plates', 2)]}),
    # the Chieftain keeps Tartarus's look half the time (model 0); the rest wear one of the two kit chieftain sets
    'chieftain': dict(tint='chieftain', keep_base=0.5, slots={s: [('', 1)] for s in SLOTS},
                      outfits=[(0.5, {'helmet': 'h3_helmet_chieftain', 'chest': 'h3_suit_chieftain', 'shoulders': '', 'arms': '',
                                      'legs': '', 'waist': ''}),
                               (0.5, {'helmet': 'kh_helmet_chieftain', 'chest': 'kh_chest_heavy', 'shoulders': 'h2_shoulders_huge',
                                      'arms': 'kh_handguard_chieftain', 'legs': 'kh_legs_chieftain', 'waist': 'kh_belt_long'})]),
}


def kit_dir():
    if os.path.isdir(SRC): return SRC
    d = tempfile.mkdtemp(prefix='brutekit_')
    zipfile.ZipFile(SRC).extractall(d)
    return d


def tex_png(kd, src, od, tint=None):
    """kit bitmap -> png in od (tinted copy when tint is given); returns the file name"""
    base = os.path.splitext(os.path.basename(src))[0].replace(' ', '_').replace(':', '_')
    fn = f'kit_{base}' + (f'_{tint}' if tint else '') + '.jpg'
    dst = os.path.join(od, fn)
    if os.path.exists(dst): return fn
    if src.startswith('Brute:'):
        im = Image.open(f'{OUT}/models/Brute/Brute_{src[6:]}.png').convert('RGB')
    else:
        im = Image.open(os.path.join(kd, src)).convert('RGB')
    if tint:
        a = np.asarray(im).astype(np.float64) / 255.0
        mp = os.path.join(kd, H3 + 'minor_major_armor_cc.tif')
        mk = np.asarray(Image.open(mp).convert('RGB').resize(im.size)).astype(np.float64)[..., :1] / 255.0
        a = a * (1 - mk) + a * np.array(TINTS[tint]) * 1.5 * mk
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    im.save(dst, quality=90)
    return fn


def main():
    kd = kit_dir()
    od = f'{OUT}/models/BruteKit'
    if os.path.isdir(od): shutil.rmtree(od)
    os.makedirs(od)
    joints, bmeshes, _ = read_iqm(f'{OUT}/models/Brute/Brute.iqm')
    nodes = [j[0] for j in joints]
    K = brute_kit.Kit(os.path.join(kd, 'brute.blend'))
    body = brute_kit.fill_weights(K.piece('base', nodes), K.piece('base', nodes))
    bind = [[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]]
    # which tints each piece needs
    need = {}
    for rank, rd in RANKS.items():
        for slot, opts in rd['slots'].items():
            for p, _ in opts:
                if p: need.setdefault(p, set()).add(rd['tint'])
        for _, o in rd.get('outfits', []):
            for p in o.values():
                if p: pid, _, t = p.partition('@'); need.setdefault(pid, set()).add(t or rd['tint'])
    meta = dict(slots=SLOTS, pieces={}, ranks={})
    by_id = {pid: (obj, slot) for obj, (pid, slot) in PIECES.items()}
    for pid in sorted(need):
        obj, slot = by_id[pid]
        p = brute_kit.fill_weights(K.piece(obj, nodes), body)
        mats = sorted(set(p['tmat'].tolist()))
        tinted = any(MATERIALS.get(p['mats'][mi] if mi < len(p['mats']) else '', ('', False))[1] for mi in mats)
        tints = sorted(need[pid]) if tinted else [None]
        uv = p['uv'].copy(); uv[:, 1] = 1.0 - uv[:, 1]
        bi = p['bi'].astype(np.uint8); bw = np.round(p['bw'] * 255).astype(np.uint8)
        # rounding: make the weights sum to 255 again
        bw[:, 0] += (255 - bw.sum(1).astype(int)).astype(np.uint8)
        files = {}
        for tint in tints:
            meshes = []
            for k, mi in enumerate(mats):
                mn = p['mats'][mi] if mi < len(p['mats']) else ''
                src, can_tint = MATERIALS.get(mn, (None, False))
                if src is None: print(f'  {pid}: no texture for material {mn!r}, skipped'); continue
                fn = tex_png(kd, src, od, tint if can_tint else None)
                t = p['tris'][p['tmat'] == mi][:, [0, 2, 1]]
                used = np.unique(t)
                # corners -> shared vertices (same position, normal, uv and weights)
                key = np.concatenate([np.round(p['pos'][used] * 1e5), np.round(p['nrm'][used] * 1e3), np.round(uv[used] * 1e5),
                                      bi[used], bw[used]], axis=1)
                _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
                keep = used[first]
                remap = np.full(len(p['pos']), -1); remap[used] = inv.ravel()
                meshes.append(dict(name=f'{pid}_{k}', material=fn, pos=p['pos'][keep], nrm=p['nrm'][keep], uv=uv[keep],
                                   bidx=bi[keep], bw=bw[keep], tris=remap[t]))
            name = pid + (f'_{tint}' if tint else '')
            write_iqm(f'{od}/{name}.iqm', joints, meshes, [dict(name='bind', fps=30.0, loop=True, frames=bind)])
            files[tint or ''] = name + '.iqm'
            if slot == 'helmet':                      # pop-off debris: static, centred on the piece
                ctr = np.concatenate([m['pos'] for m in meshes]).mean(0)
                dm = [dict(m, pos=m['pos'] - ctr, bidx=np.zeros_like(m['bidx']), bw=np.tile(np.array([255, 0, 0, 0], np.uint8), (len(m['pos']), 1)))
                      for m in meshes]
                write_iqm(f'{od}/debris_{name}.iqm', [('root', -1, (0, 0, 0), (0, 0, 0, 1), (1, 1, 1))], dm,
                          [dict(name='idle', fps=30.0, loop=True, frames=[[((0, 0, 0), (0, 0, 0, 1), (1, 1, 1))]])])
        meta['pieces'][pid] = dict(slot=slot, source=obj, files=files, tris=int(len(p['tris'])))
        print(f'{pid:28s} {slot:9s} {len(p["tris"]):5d} tris  {sorted(files)}')
    for rank, rd in RANKS.items():
        def ref(p, dflt):
            if not p: return ''
            pid, _, t = p.partition('@')
            f = meta['pieces'][pid]['files']
            return f.get(t or dflt) or f.get('')
        meta['ranks'][rank] = dict(
            keep_base=rd.get('keep_base', 0.0),
            slots={s: [(ref(p, rd['tint']), w) for p, w in rd['slots'][s]] for s in SLOTS},
            outfits=[(c, {s: ref(o.get(s, ''), rd['tint']) for s in SLOTS}) for c, o in rd.get('outfits', [])])
    json.dump(meta, open(f'{od}/BruteKit.json', 'w'), indent=1)
    size = sum(os.path.getsize(os.path.join(od, f)) for f in os.listdir(od))
    print(len(meta['pieces']), 'pieces,', len([f for f in os.listdir(od) if f.endswith('.iqm')]), 'iqm,', size // 1024, 'KB')


if __name__ == '__main__':
    main()
