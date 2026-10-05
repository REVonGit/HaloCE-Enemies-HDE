"""Characters from a Halo CE PC / MCC map (e.g. SPV3's a30 with the Blind Wolf) -> IQM + skins + JSON,
reusing extract_chars.extract() with gbxmodel geometry, and the AI/stat dump for the pack generator."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import sys, json, os
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
}
OUT = ec.OUT

def run(only=None):
    ai = dict(variants={}, actors={}, bipeds={}, collisions={}, weapons={})
    for key, (path, chars) in MAPS.items():
        if not os.path.exists(path): print('missing', path); continue
        sub = run_map(path, chars, only)
        for k in ai: ai[k].update(sub[k])
    json.dump(ai, open(f'{OUT}/spv3_ai.json', 'w'), indent=1, default=str)
    return ai

def run_map(MAP, CHARS, only=None):
    m = PCMap(MAP)
    _geo = hm.Model.geometry
    hm.Model.geometry = lambda s, gi: gbx_geometry(s.m, s.geoms[gi].addr) if isinstance(s.m, PCMap) else _geo(s, gi)
    ec.char_weapons = lambda name: []
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
        if not any(t['name'].startswith(c) for c in CHARS): continue
        v = dump(m, 'actor_variant_definition', t['data'])
        v['change_colors_list'] = block_dump(m, v.get('change_colors'), 'actor_variant_change_colors')
        ai['variants'][t['name']] = v
        ai['actors'][v['actor_reference']] = dump(m, 'actor_definition', byname[('actr', v['actor_reference'])]['data'])
        b = flatten_obj(dump(m, 'biped_definition', byname[('bipd', v['unit_reference'])]['data']))
        b['change_colors_list'] = []
        ai['bipeds'][v['unit_reference']] = b
        cm = b.get('collision_model')
        if cm: ai['collisions'][cm] = dump(m, 'collision_model', byname[('coll', cm)]['data'])
    return ai

# creature sounds that live in the map itself (ogg permutations, stored inline)
SOUNDS = {'ThornBeast': ('a30', [r'sound\sfx\impulse\thornbeast']),
          'Engineer': ('b30', [r'sound\dialog\engineer\conditional', r'sound\sfx\impulse\impacts\engineer explosion'])}

def export_sounds(pid, out_dir):
    """every snd! under SOUNDS[pid] -> out_dir/<tag>_<n>.ogg; returns {tag basename: [files]}"""
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
        base = t['name'].split('\\')[-1]
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
                res.setdefault(base, []).append(fn)
    return res

if __name__ == '__main__':
    ai = run(sys.argv[1:])
    for k, v in ai['variants'].items():
        print(k, v['unit'], v['ranged_combat']['reference'], v['ranged_combat']['melee_range'])
