"""The Sentinels' own sounds from the official games -> $HCE_OUT/sounds/Sentinel/<event>_<n>.ogg + index.json

    python3 extract_sentinel_sounds.py      # Halo CE's c20 (HCE_CE_MAPS) and Halo 2's 06b_floodzone (HCE_H2_MAP06B, HCE_H2_SOUNDS)

Halo CE's Sentinel (characters\\sentinel\\sentinel and its beam, as The Library has them: the tags its biped, weapon and
effects lead to): the hover engine, the beam loop and its impact, a hit on the hull, the death. Halo 2's (Quarantine
Zone's classic sound\\characters\\sentinel set): the Enforcer's and the Constructor's engines, the Enforcer's needle cannon
and rockets, the Constructor's cutting beam, the Sentinels' melee and death. split_factions.py ships them in the
Sentinels pack (sndinfo.sentinel: HCE/Sentinel/<event>), played through HaloDoom_EnemyBase's unit sounds and fire
sounds (build_pack.SENTINEL_SOUNDS).
"""
import os, sys, json, shutil, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))
import splitfile
from extract_chars import OUT
from hce_paths import MAPS_DIR

# To add an event, add its tag here (Halo CE) or in H2 (Halo 2) and name it in build_pack.SENTINEL_SOUNDS.
CE = {  # event -> Halo CE sound tag (c20)
    'Engine': r'sound\sfx\vehicles\sent_engine',
    'BeamLoop': r'sound\sfx\vehicles\sent_laser_loop',
    'BeamImpact': r'sound\sfx\vehicles\sent_laser_impact',
    'Hit': r'sound\sfx\impulse\impacts\sentinel_impact',
    'Death': r'sound\sfx\impulse\impacts\sentinel_death',
    'Chips': r'sound\sfx\impulse\impacts\metal_chips',
}
S2 = 'sound\\characters\\sentinel\\'
H2 = {  # event -> Halo 2 sound tags (06b), played in this order or picked at random
    'EnforcerEngine': [S2 + r'sentinel_engine_enforcer\enforcer_engine\loop'],
    'ConstructorEngine': [S2 + r'sentinel_engine\sentinel_engine\loop_constructor'],
    'H2Engine': [S2 + r'sentinel_engine\sentinel_engine\loop'],
    'EnforcerNeedler': [S2 + 'needler_fire_sentinel_enforcer'],
    'EnforcerRocket': [S2 + r'sentinel_rocket_launcher\sentinel_rocket\loop'],
    'EnforcerRocketBoom': [S2 + 'enforcer_rocket_explode'],
    'GunIn': [S2 + r'sentinel_gun\sent_gun\in'], 'GunLoop': [S2 + r'sentinel_gun\sent_gun\loop'], 'GunOut': [S2 + r'sentinel_gun\sent_gun\out'],
    'H2BeamIn': [S2 + r'sent_laser_loop\sent_laser_loop\in'], 'H2BeamLoop': [S2 + r'sent_laser_loop\sent_laser_loop\loop'],
    'H2BeamOut': [S2 + r'sent_laser_loop\sent_laser_loop\out'], 'H2BeamImpact': [S2 + 'sent_laser_impact'],
    'H2Death': [S2 + 'sentinel_death_initial', S2 + 'sentinel_death'],
    'H2Melee': [S2 + 'sentinel_melee'],
}


def ce_sounds(od, idx):
    """Halo CE's (CE table, from c20.map): every Xbox ADPCM permutation -> od/<event>_<n>.ogg, appended to idx[event]"""
    from tags import HMap, tag
    from halosound import xbox_adpcm, to_wav
    m = HMap(os.path.join(MAPS_DIR, 'c20.map'))
    by = {t['name']: t for t in m.tags if t['cls'] == 'snd!'}
    tmp = tempfile.mkdtemp()
    for ev, name in CE.items():
        t = by.get(name)
        if not t: print('  no', name); continue
        S = tag(m, t, 'sound_definition')
        ch = 2 if S['encoding'] == 1 else 1
        rate = 44100 if S['sample_rate'] == 1 else 22050
        n = 0
        for pr in S.block('pitch_ranges', 'sound_pitch_range'):
            for pm in pr.block('permutations', 'sound_permutation'):
                sz, fl, fo = m.u('iii', pm.addr + 64)
                if pm['compression'] != 1 or sz <= 0: continue
                w = f'{tmp}/{ev}_{n}.wav'
                to_wav(xbox_adpcm(m.d[fo:fo + sz], ch), rate, ch, w)
                fn = f'{ev}_{n}.ogg'
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', w, '-ac', '1', '-c:a', 'libvorbis', '-q:a', '5', f'{od}/{fn}'], check=True)
                idx.setdefault(ev, []).append(fn); n += 1
    shutil.rmtree(tmp, ignore_errors=True)


def h2_sounds(od, idx):
    """Halo 2's: Opus (most) or Xbox ADPCM (the loops: extract_h2_jetpack_sound.py has the chunk layout)

    Every permutation of every tag of an H2 event, from 06b_floodzone.map and MCC's sounds_en / sounds_neutral.dat,
    -> od/<event>_<n>.ogg (mono Vorbis), appended to idx[event]."""
    import h2opus
    from extract_h2_brute import SOUNDS_DIR
    from h2map import H2Map, sound_chunks
    from halosound import xbox_adpcm, to_wav
    m = H2Map(os.environ.get('HCE_H2_MAP06B', '06b_floodzone.map'), os.environ.get('HCE_H2_CACHE06B') or None)
    files = {k: splitfile.open(os.path.join(SOUNDS_DIR, fn)) for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if splitfile.exists(os.path.join(SOUNDS_DIR, fn))}
    tmp = tempfile.mkdtemp()
    for ev, names in H2.items():
        n = 0
        for name in names:
            for pn, (rate, enc, comp), locs in sound_chunks(m, name):
                ch = [l for l in locs if l[0] == 0][0][1]
                f = files['neutral' if any(fl & 0x2000 for _, _, fl, _, _ in ch) else 'en']
                nch = 2 if enc == 1 else 1
                if comp == 1:                 # Xbox ADPCM: a chunk past 64 KiB keeps its size's high bits in the flags
                    data = b''
                    for o, cs, fl, us, ri in ch: f.seek(o); data += f.read((cs & 0xFFFF) | ((fl & 0xFF) << 16))
                    src = f'{tmp}/{ev}_{n}.wav'
                    to_wav(xbox_adpcm(data, nch), {0: 22050, 1: 44100, 2: 32000}.get(rate, 22050), nch, src)
                else:
                    pk = []
                    for o, cs, fl, us, ri in ch: f.seek(o); pk += h2opus.packets(f.read(cs & 0xFFFF), strict=True)
                    src = f'{tmp}/{ev}_{n}.ogg'; open(src, 'wb').write(h2opus.to_ogg(pk, channels=nch))
                fn = f'{ev}_{n}.ogg'          # -> Vorbis, mono (GZDoom plays Vorbis everywhere)
                r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-ac', '1', '-c:a', 'libvorbis', '-q:a', '5', f'{od}/{fn}'])
                if r.returncode == 0: idx.setdefault(ev, []).append(fn); n += 1
                else: print('  undecodable', name, 'codec', comp)
        if not n: print('  no', ev)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    """out/sounds/Sentinel/ rebuilt from both games, with index.json {event: [files]}"""
    od = f'{OUT}/sounds/Sentinel'
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    idx = {}
    ce_sounds(od, idx)
    h2_sounds(od, idx)
    json.dump(idx, open(f'{od}/index.json', 'w'), indent=1)
    for ev, fs in sorted(idx.items()): print(f'  {ev}: {len(fs)}')


if __name__ == '__main__':
    main()
