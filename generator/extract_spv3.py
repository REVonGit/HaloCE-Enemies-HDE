"""Characters from a Halo CE PC / MCC map (e.g. SPV3's a30 with the Blind Wolf) -> IQM + skins + JSON,
reusing extract_chars.extract() with gbxmodel geometry, and the AI/stat dump for the pack generator."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import sys, json, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import halomodel as hm
import extract_chars as ec
from pcmap import PCMap, gbx_geometry
from tags import tag
from extract_ai import dump, flatten_obj, block_dump

# SPV3 maps (PC/MCC caches) and the characters taken from each
MAPS = {
    'a30': (os.environ.get('HCE_SPV3_A30', 'a30_1.map'),
            {r'characters\blind_wolf\blind_wolf': 'BlindWolf', r'characters\thorn_beast\thorn_beast': 'ThornBeast'}),
    'b30': (os.environ.get('HCE_SPV3_B30', 'b30_1.map'),
            {r'characters\engineer\engineer': 'Engineer'}),
    # the XAM Campaign Overhaul's c40 (Tropical Thunder 98): its Flood Grunt, an Unggoy combat form (claws, no gun)
    'c40': (os.environ.get('HCE_XAM_C40', 'c40_1.map'),
            {r'characters\flood grunt\flood grunt': 'FloodGrunt'}),
    # Ruby's Rebalance's c40 (mynameislol): its new Flood hosts, each with its own model, skins and damaged stumps
    'c40r': (os.environ.get('HCE_RUBY_C40', 'c40_2.map'),
             {r'characters\floodcombat_odst\floodcombat_odst': 'FloodODST',
              r'characters\floodcombat_marine\floodcombat_marine': 'FloodMarine',
              r'characters\floodcombat_human\floodcombat_human armored': 'FloodArmored',
              r'characters\floodcombat elite new\armored\floodcombat elite armored': 'FloodEliteArmored',
              r'characters\floodcombat elite new\floodcombat_elite_special\floodcombat elite commander': 'FloodEliteCommander',
              r'characters\floodcombat elite shield\floodcombat elite ultra': 'FloodEliteUltra'}),
}
# variant keys renamed (the pack's class names come from them: kept clear of the Halo CE Flood's own) and weapons re-pointed
VARIANT_KEYS = {
    r'characters\floodcombat_human\armored\floodcombat_human ': r'characters\floodcombat_human\armored\floodcombat_human armored ',
    r'characters\floodcombat_human\floodcombat_human sniper rifle': r'characters\floodcombat_human\armored\floodcombat_human armored sniper rifle',
    r'characters\floodcombat elite shield\minor\floodcombat elite minor ': r'characters\floodcombat elite shield\floodcombat elite minor ',
    r'characters\floodcombat elite shield\major\floodcombat elite major ': r'characters\floodcombat elite shield\floodcombat elite major ',
    r'characters\floodcombat elite shield\minor\floodcombat elite ': r'characters\floodcombat elite shield\floodcombat elite minor ',
    r'characters\floodcombat elite shield\major\floodcombat elite fuel rod': r'characters\floodcombat elite shield\floodcombat elite ultra fuel rod',
    r'characters\floodcombat elite shield\major\floodcombat elite ': r'characters\floodcombat elite shield\floodcombat elite major ',
    r'characters\floodcombat elite shield\floodcombat commander ': r'characters\floodcombat elite shield\floodcombat elite commander ',
}
WEAPON_REFS = {r'weapons\plasma_cannon\plasma_cannon': r'weapons\fuel rod gun\fuel rod'}   # Ruby's fuel rod

def variant_key(name):
    for a, b in VARIANT_KEYS.items():
        if name.startswith(a): return b + name[len(a):]
    return name
OUT = ec.OUT

def run(only=None):
    ai = dict(variants={}, actors={}, bipeds={}, collisions={}, weapons={})
    for key, (path, chars) in MAPS.items():
        if not os.path.exists(path): print('missing', path); continue
        sub = run_map(path, chars, only)
        for k in ai: ai[k].update(sub[k])
    json.dump(ai, open(f'{OUT}/spv3_ai.json', 'w'), indent=1, default=str)
    if not only or 'FloodSounds' in only: flood_sounds()
    return ai

def flood_sounds():
    """the Flood's voices and effects -> $HCE_OUT/sounds/Flood (+ index.json); split_factions.py ships them in the Flood pack"""
    od = f'{OUT}/sounds/Flood'
    if os.path.exists(od): shutil.rmtree(od)
    got = {}
    for pid in ('Flood', 'FloodXAM'):
        if os.path.exists(MAPS[SOUNDS[pid][0]][0]): got.update(export_sounds(pid, od, full=True))
    if got: json.dump(got, open(f'{od}/index.json', 'w'), indent=1)
    print('Flood sounds:', sum(len(v) for v in got.values()), 'files')

def pc_bitmap_image(m, tag_id, index=0, _orig=ec.bitmap_image):
    """a PC map's bitmap: pixels kept in the shared bitmaps.map (flag 0x100: external; HCE_SPV3_BITMAPS, see
    gore_kit.py) read from there, the rest from the map itself"""
    t = m.byid.get(tag_id) if isinstance(m, PCMap) else None
    if t and t['cls'] == 'bitm':
        c, p = m.reflexive(t['data'] + 0x60)
        if index < c:
            _, w, h, _, typ, fmt, fl, _, _, _, _, poff, psz = m.u('4s6h2h2hiii', p + index * 0x30)[:13]
            if typ == 0 and fl & 0x100:
                from bitmaps import decode
                from gore_kit import _bitmaps_read
                try: return decode(_bitmaps_read(poff, psz), 0, w, h, fmt, fl)
                except Exception: return None
    return _orig(m, tag_id, index)
ec.bitmap_image = pc_bitmap_image


def run_map(MAP, CHARS, only=None):
    m = PCMap(MAP)
    _geo = hm.Model.geometry
    hm.Model.geometry = lambda s, gi: gbx_geometry(s.m, s.geoms[gi].addr) if isinstance(s.m, PCMap) else _geo(s, gi)
    from extract_weapons import WEAPONS
    carried = {}                                 # the guns each biped's variants in this map carry (baked into its hand)
    for t in m.find('actv'):
        v = dump(m, 'actor_variant_definition', t['data'])
        ref = (v.get('ranged_combat') or {}).get('reference') or ''
        w = WEAPONS.get(WEAPON_REFS.get(ref, ref))
        if w and os.path.exists(f'{OUT}/weapons/{w}/{w}.pkl'): carried.setdefault(v['unit_reference'], set()).add(w)
    ec.char_weapons = lambda name: sorted(carried.get(name, ()))
    try:
        for name, pid in CHARS.items():
            if only and pid not in only: continue
            meta = ec.extract(name, pid, ['spv3'], {'spv3': m})
            print(pid, 'anims', len(meta['anims']), 'joints', len(meta['joints']), 'iqm', meta['iqm_bytes'] // 1024, 'KB',
                  'h', round(meta['collision_height'], 2), 'r', round(meta['collision_radius'], 2))
    finally:
        hm.Model.geometry = _geo
    # AI data in the extract_ai.py layout
    byname = {(t['cls'], t['name']): t for t in m.tags}
    ai = dict(variants={}, actors={}, bipeds={}, collisions={}, weapons={})
    for t in m.find('actv'):
        v = dump(m, 'actor_variant_definition', t['data'])
        if not any(t['name'].startswith(c) for c in CHARS) and v['unit_reference'] not in CHARS: continue
        rc = v.get('ranged_combat') or {}
        if rc.get('reference') in WEAPON_REFS: rc['reference'] = WEAPON_REFS[rc['reference']]
        v['change_colors_list'] = block_dump(m, v.get('change_colors'), 'actor_variant_change_colors')
        ai['variants'][variant_key(t['name'])] = v
        ai['actors'][v['actor_reference']] = dump(m, 'actor_definition', byname[('actr', v['actor_reference'])]['data'])
        b = flatten_obj(dump(m, 'biped_definition', byname[('bipd', v['unit_reference'])]['data']))
        b['change_colors_list'] = []
        ai['bipeds'][v['unit_reference']] = b
        cm = b.get('collision_model')
        if cm: ai['collisions'][cm] = dump(m, 'collision_model', byname[('coll', cm)]['data'])
    return ai

# creature sounds that live in the map itself (ogg permutations, stored inline)
SOUNDS = {'ThornBeast': ('a30', [r'sound\sfx\impulse\thornbeast']),
          'Engineer': ('b30', [r'sound\dialog\engineer\conditional', r'sound\sfx\impulse\impacts\engineer explosion']),
          # the Flood's voices and effects (Ruby's Rebalance's c40: Halo CE's flood set and Ruby's 'flood_new' one), for the
          # Flood pack (build_pack.flood_sounds)
          'Flood': ('c40r', [r'sound\dialog\flood', r'sound\dialog\flood_new', r'sound\sfx\impulse\flood\infection',
                             r'sound\sfx\impulse\flood\carrier', r'sound\sfx\impulse\impacts\flood_limbs',
                             r'sound\sfx\impulse\animations\flood_combat_human', r'sound\sfx\impulse\animations\flood_combat_elite']),
          # the XAM Campaign Overhaul's own Flood sounds (its c40): the human and Elite forms' idle growls, the Flood Grunt's attack
          'FloodXAM': ('c40', [r'sound\sfx2\characters\flood', r'sound\sfx2\impacts\flood flesh impact'])}

def export_sounds(pid, out_dir, full=False):
    """every snd! under SOUNDS[pid] -> out_dir/<tag>_<n>.ogg; returns {tag basename: [files]} (full: keyed by the tag's
    folder and name, 'flood_new_pain', for sets whose tag names repeat across folders)"""
    import subprocess, tempfile
    from halosound import xbox_adpcm, to_wav
    key, prefixes = SOUNDS[pid]
    m = PCMap(MAPS[key][0])
    os.makedirs(out_dir, exist_ok=True)
    res = {}
    tmp = tempfile.mkdtemp()
    for t in m.tags:
        if t['cls'] != 'snd!' or not any(t['name'] == p or t['name'].startswith(p + '\\') for p in prefixes): continue
        S = tag(m, t, 'sound_definition')
        base = '_'.join(t['name'].split('\\')[-2:]) if full else t['name'].split('\\')[-1]
        for pr in S.block('pitch_ranges', 'sound_pitch_range'):
            for k, pm in enumerate(pr.block('permutations', 'sound_permutation')):
                sz, fl, fo = m.u('iii', pm.addr + 64)
                data = m.d[fo:fo + sz]
                fn = f'{base.replace(" ", "_")}_{k}.ogg'
                ch = 2 if S['encoding'] == 1 else 1
                rate = 44100 if S['sample_rate'] == 1 else 22050
                if pm['compression'] == 3 and data[:4] == b'OggS':
                    open(f'{out_dir}/{fn}', 'wb').write(data)
                elif pm['compression'] in (0, 1):      # 16-bit PCM (little-endian in PC caches) / Xbox ADPCM
                    import numpy as np
                    a = np.frombuffer(data[:len(data) // 2 * 2], '<i2').reshape(-1, ch) if pm['compression'] == 0 else xbox_adpcm(data, ch)
                    wav = f'{tmp}/{fn[:-4]}.wav'
                    to_wav(a, rate, ch, wav)
                    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '3', f'{out_dir}/{fn}'], check=True)
                else:
                    continue
                # a permutation kept in SPV3's shared sounds.map (not the level map) reads as garbage here: dropped
                ok = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                     f'{out_dir}/{fn}'], capture_output=True, text=True)
                if ok.returncode or not ok.stdout.strip() or ok.stderr.strip():
                    os.remove(f'{out_dir}/{fn}'); continue
                res.setdefault(base, []).append(fn)
    return res

if __name__ == '__main__':
    ai = run(sys.argv[1:])
    for k, v in ai['variants'].items():
        print(k, v['unit'], v['ranged_combat']['reference'], v['ranged_combat']['melee_range'])
