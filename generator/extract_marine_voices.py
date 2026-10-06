"""Marine dialogue from Halo CE and Halo 2: one voice set per Marine, for the Marines' random voices.

    python3 extract_marine_voices.py    # -> voice_extra/Marine_<Name>/<Category> N.ogg

* Halo CE: sound\\dialog\\marines\\<name>\\conditional\\combat2\\* (aussie, bisenti, fitzgerald, mendoza) and
  sound\\dialog\\sargeant\\* (Sergeant Johnson) / sound\\dialog\\sarge2\\* (the second sergeant) from the Xbox
  campaign maps (HCE_MAPS), Xbox ADPCM -> Vorbis.
* Halo 2: sound\\dialog\\combat\\marine_* and sgt_* from 01b_spacestation.map + sounds_en.dat (HCE_H2_MAP /
  HCE_H2_SOUNDS): aussie, cross, perez, timid, tough, the cautious and gruff sergeants and Johnson. (marine_sassy,
  a woman's voice, is left out: the Marine models are men.)
Halo CE's and Halo 2's Aussie and Johnson are the same men, so each pair becomes one set. The categories are
build_voices.py's (Alert, Taunt, Pain Nrml ...); a set without one borrows a related event there (FALLBACK).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import glob, hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_elite_loose import ogg_from_wav, duration

OUT = os.environ.get('HCE_VOICE_EXTRA', os.path.join(HERE, 'voice_extra'))
CE_MAPS = os.environ.get('HCE_MAPS', 'maps')
CE_ORDER = ['a10', 'a30', 'a50', 'b30', 'b40', 'c10', 'c20', 'c40', 'd20', 'd40']
H2_MAP = os.environ.get('HCE_H2_MAP', '01b_spacestation.map')   # MCC halo2\\h2_maps_win64_dx11
H2_CACHE = os.environ.get('HCE_H2_CACHE') or None
PER_SOURCE = 6                        # lines at most per category from each game

# voice set -> (Halo CE tag prefix or None, Halo 2 voice or None)
VOICES = {
    'Marine_Johnson':     ('sound\\dialog\\sargeant\\', 'sgt_johnson'),
    'Marine_Aussie':      ('sound\\dialog\\marines\\aussie\\', 'marine_aussie'),
    'Marine_Bisenti':     ('sound\\dialog\\marines\\bisenti\\', None),
    'Marine_Fitzgerald':  ('sound\\dialog\\marines\\fitzgerald\\', None),
    'Marine_Mendoza':     ('sound\\dialog\\marines\\mendoza\\', None),
    'Marine_Sarge':       ('sound\\dialog\\sarge2\\', None),
    'Marine_Cross':       (None, 'marine_cross'),
    'Marine_Perez':       (None, 'marine_perez'),
    'Marine_Timid':       (None, 'marine_timid'),
    'Marine_Tough':       (None, 'marine_tough'),
    'Marine_SgtCautious': (None, 'sgt_cautious'),
    'Marine_SgtGruff':    (None, 'sgt_gruff'),
}
# category -> (Halo CE combat2 tags <group>\<name>, Halo 2 tag leaves)
PLAN = {
    'Alert':         (['shouting\\newcombatalone', 'shouting\\oldenemysighted', 'shouting\\unexpectedenemy', 'groupcomm\\alertfriend'],
                      ['seefoe', 'seefoe_mjr', 'foundfoe', 'hrdfoe', 'morefoe', 'srprs']),
    'Taunt':         (['killingpeople\\killedenemy', 'killingpeople\\killedenemycovenant', 'killingpeople\\killedenemyfloodcombat',
                       'hurtingpeople\\damagedenemy', 'postcombatcomments\\celebration'],
                      ['tnt', 'glt', 'chr_kllfoe', 'thrtn', 'chr']),
    'Pain Nrml':     (['involuntary\\painminor'], ['pain']),
    'Pain Med':      (['beinghurt\\hurtenemy', 'beinghurt\\hurtenemyplasma', 'beinghurt\\hurtenemyneedler'], ['pain_mdm']),
    'Pain Xtr':      (['involuntary\\painmajor'], ['pain_mjr']),
    'Death':         (['involuntary\\deathquiet'], ['dth', 'dth_slnt']),
    'Death Xtr':     (['involuntary\\deathviolent', 'involuntary\\deathflying', 'involuntary\\deathfalling', 'involuntary\\deathagonizing'],
                      ['dth_mjr', 'dth_hdsht', 'dth_fall', 'dth_slw']),
    'On Fire':       (['involuntary\\screampain'], ['scrn']),
    'Grenade Thrw':  (['shouting\\grenadethrowing'], ['strk_grnd']),
    'Enemy Grenade': (['shouting\\grenadesighted', 'shouting\\grenadedangerenemy', 'shouting\\grenadedangerself'], ['warn_incmn_grnd', 'warn_incmn']),
    'Flee':          (['actions\\flee', 'groupcomm\\retreat'], ['fear_rtrt', 'newordr_retreat', 'foeordr_fallback']),
    'Panic':         ([], ['panic', 'fear']),
    'Regroup':       (['groupcomm\\groupuncover', 'groupcomm\\advance', 'groupcomm\\cover'], ['joinme', 'cvrme', 'newordr_advance', 'newordr_charge']),
    'Leader Dead':   (['friendsdying\\frienddied', 'friendsdying\\friendkilledbycovenant', 'friendsdying\\friendkilledbyenemy'], ['lmnt', 'lmnt_deadally']),
    'Berserk':       (['exclamations\\berserk', 'actions\\shootingberserk'], ['brsrk', 'charge']),
    'Melee':         ([], ['melee']),
}


def ce_lines(tmp):
    """{(voice, <group>\\<name>): [wav paths]} from the first CE map that has each tag"""
    from tags import HMap, tag
    from halosound import xbox_adpcm, to_wav
    want = {ce: v for v, (ce, _) in VOICES.items() if ce}
    tags_wanted = {s for cel, _ in PLAN.values() for s in cel}
    found = {}
    for mp in CE_ORDER:
        path = os.path.join(CE_MAPS, mp + '.map')
        if not os.path.exists(path): continue
        m = HMap(path)
        for t in m.tags:
            if t['cls'] != 'snd!': continue
            pre = next((p for p in want if t['name'].startswith(p)), None)
            if not pre: continue
            suf = '\\'.join(t['name'].split('\\')[-2:])
            key = (want[pre], suf)
            if suf not in tags_wanted or key in found: continue
            S = tag(m, t, 'sound_definition')
            ch = 2 if S['encoding'] == 1 else 1
            rate = 44100 if S['sample_rate'] == 1 else 22050
            wavs = []
            for pr in S.block('pitch_ranges', 'sound_pitch_range'):
                for pm in pr.block('permutations', 'sound_permutation'):
                    sz, fl, fo = m.u('iii', pm.addr + 64)
                    if pm['compression'] != 1 or sz <= 0: continue
                    w = os.path.join(tmp, f'ce_{len(os.listdir(tmp))}.wav')
                    to_wav(xbox_adpcm(m.d[fo:fo + sz], ch), rate, ch, w)
                    wavs.append(w)
            found[key] = wavs
    return found


def h2_lines(tmp):
    """{(voice, leaf): [ogg paths]} from Halo 2's 01b_spacestation"""
    from extract_h2_brute import tag_oggs, SOUNDS_DIR
    from h2map import H2Map
    want = {h2: v for v, (_, h2) in VOICES.items() if h2}
    leaves = {l for _, h2l in PLAN.values() for l in h2l}
    m = H2Map(H2_MAP, H2_CACHE)
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    out = {}
    for t in m.tags:
        if t['cls'] != 'snd!' or not t['name'].startswith('sound\\dialog\\combat\\'): continue
        parts = t['name'].split('\\')
        voice, leaf = parts[3], parts[-1]
        if voice not in want or leaf not in leaves: continue
        paths = []
        for i, data in enumerate(tag_oggs(m, t['name'], files) or []):
            p = os.path.join(tmp, f'h2_{voice}_{leaf}_{i}.ogg'); open(p, 'wb').write(data); paths.append(p)
        out[(want[voice], leaf)] = paths
    return out


def main():
    tmp = tempfile.mkdtemp()
    ce_dir = os.path.join(tmp, 'ce'); os.makedirs(ce_dir)
    ce = ce_lines(ce_dir)
    h2 = h2_lines(tmp)
    report = {}
    for voice in VOICES:
        od = os.path.join(OUT, voice)
        os.makedirs(od, exist_ok=True)
        for f in glob.glob(os.path.join(od, '*.ogg')): os.remove(f)
        counts = {}
        for cat, (ce_tags, h2_leaves) in PLAN.items():
            n = 0; seen = set()
            took = 0
            for suf in ce_tags:
                for w in ce.get((voice, suf), []):
                    if took >= PER_SOURCE: break
                    key = hashlib.sha1(open(w, 'rb').read()).hexdigest()
                    if key in seen: continue
                    seen.add(key); n += 1; took += 1
                    ogg_from_wav(w, os.path.join(od, f'{cat} {n}.ogg'))
            took = 0
            for leaf in h2_leaves:
                for p in h2.get((voice, leaf), []):
                    if took >= PER_SOURCE: break
                    if duration(p) < 0.15: continue
                    n += 1; took += 1
                    ogg_from_wav(p, os.path.join(od, f'{cat} {n}.ogg'))
            if n: counts[cat] = n
        report[voice] = counts
        print(f'{voice:20s}', sum(counts.values()), 'lines', counts)
    json.dump(report, open(os.path.join(OUT, 'marine_voices.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
