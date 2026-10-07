"""Extra Crazy Grunt dialogue from Halo 2 (MCC), to fill the events the Grunt_Crazy set is short on next to
Grunt_Whiley / Grunt_Whimpy: kamikaze, kill player, taunt, leader dead, regroup, death, hard death, alert,
grenade throw, enemy grenade, stuck, heavy pain and on fire.

    python3 extract_h2_grunt.py        # -> voice_extra/Grunt_Crazy/<Category> N.ogg

Source: sound\\dialog\\combat\\grunt_crazy\\* in 08a_deltacliffs.map (+ sounds_en.dat), the same voice as the
existing Crazy lines. Lines the existing set already has (matched by waveform envelope against
HCE_VOICE_SRC/Grunt_Crazy) are skipped. build_voices.py reads voice_extra/ after the main source, with the same
"<Category> N.ogg" naming.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import glob, json, os, subprocess, sys
import glob, json, os, re, shutil, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_h2_brute import tag_oggs, SOUNDS_DIR, MAP08A, CACHE08A
from h2map import H2Map

OUT = os.environ.get('HCE_VOICE_EXTRA', os.path.join(HERE, 'voice_extra'))
SRC = os.environ.get('HCE_VOICE_SRC', 'HaloDoomEnemies/Sounds')
PREFIX = 'sound\\dialog\\combat\\grunt_crazy\\'

# pack category (build_voices.CAT key) -> [(Halo 2 tag leaf, how many lines)]
PLAN = {
    'Kamikaze':      [('thrtn', 5), ('thrtn_hum', 2)],                          # threats while charging in
    'Kill Player':   [('glt', 3), ('glt_hum', 1), ('glt_mjrfoe_chief', 2)],     # gloats
    'Taunt':         [('tnt', 4), ('tnt_mjrfoe_chief', 2)],
    'Leader Dead':   [('fear_rtrt_ldrdead', 5), ('fear', 3)],
    'Regroup':       [('joinme', 2), ('joinme_emrg', 2), ('newordr_fallback', 2)],
    'Death':         [('dth', 4)],
    'Death Xtr':     [('dth_mjr', 4), ('dth_fall', 2), ('dth_hdsht', 2)],                         # blasts, throws (DeathHard)
    'Alert':         [('seefoe', 2)],
    'Grenade Thrw':  [('strk_grnd', 3)],
    'Enemy Grenade': [('warn_incmn_grnd', 1)],
    'Stuck':         [('panic', 2)],
    'Pain Xtr':      [('pain_mjr', 1), ('dth_slw', 1)],
    'On Fire':       [('dth_slw', 1)],                                          # drawn-out agonised screams
}
# the grenade death screams (the same voice actor in both games, though Halo CE doesn't label its Grunt voices): the
# kamikaze run and a stuck grenade. Halo 2: grunt_crazy's panic screams; Halo CE: combat2 grenade_danger_self
CE_PLAN = {'Kamikaze': [('shouting\\grenade_danger_self', 5)], 'Stuck': [('shouting\\grenade_danger_self', 5)]}
CE_PREFIX = 'sound\\dialog\\grunt\\conditional\\combat2\\'
from hce_paths import MAPS_DIR as CE_MAPS     # Halo CE's maps (HCE_MAPS)


def ce_grunt_lines(tmp):
    """{combat2 <group>\\<name>: [wav paths]} from the first Halo CE map with each tag"""
    from tags import HMap, tag
    from halosound import xbox_adpcm, to_wav
    wanted = {leaf for v in CE_PLAN.values() for leaf, _ in v}
    out = {}
    for mp in ('a10', 'a30', 'a50', 'b30', 'b40', 'c10', 'c20', 'c40', 'd20', 'd40'):
        path = os.path.join(CE_MAPS, mp + '.map')
        if not os.path.exists(path): continue
        m = HMap(path)
        for t in m.tags:
            if t['cls'] != 'snd!' or not t['name'].startswith(CE_PREFIX): continue
            leaf = t['name'][len(CE_PREFIX):]
            if leaf not in wanted or leaf in out: continue
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
            out[leaf] = wavs
        if len(out) == len(wanted): break
    return out


def envelope(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '8000', '-f', 's16le', '-'],
                         capture_output=True).stdout
    a = np.frombuffer(raw, '<i2').astype(float)
    n = len(a) // 80
    return np.log(np.sqrt((a[:n * 80].reshape(n, 80) ** 2).mean(1) + 1))


def same_line(a, b):
    """best normalised correlation of the shorter envelope slid along the longer one"""
    if len(a) > len(b): a, b = b, a
    if len(a) < 8 or len(b) > len(a) * 1.4 + 10: return 0.0
    a = (a - a.mean()) / (a.std() + 1e-9)
    best = 0.0
    for lag in range(len(b) - len(a) + 1):
        s = b[lag:lag + len(a)]
        best = max(best, float((a * (s - s.mean()) / (s.std() + 1e-9)).mean()))
    return best


def main():
    m = H2Map(MAP08A, CACHE08A)
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    have = [envelope(p) for p in sorted(glob.glob(os.path.join(SRC, 'Grunt_Crazy', '*.ogg')))]
    base_have = list(have)
    od = os.path.join(OUT, 'Grunt_Crazy')
    os.makedirs(od, exist_ok=True)
    for f in glob.glob(os.path.join(od, '*.ogg')): os.remove(f)
    full = {t['name'].split('\\')[-1]: t['name'] for t in m.tags if t['cls'] == 'snd!' and t['name'].startswith(PREFIX)}
    tmp = os.path.join(od, '.probe.ogg')
    report = {}
    for cat, picks in list(PLAN.items()) + list(H2_EXTRA.items()):
        n = len(glob.glob(os.path.join(od, f'{cat} *.ogg')))
        for leaf, want in picks:
            oggs = tag_oggs(m, full[leaf], files) or [] if leaf in full else []
            took = 0
            for data in oggs:
                if took >= want: break
                open(tmp, 'wb').write(data)
                e = envelope(tmp)
                if any(same_line(e, h) > 0.93 for h in have): continue        # already in the set
                n += 1; took += 1
                os.replace(tmp, os.path.join(od, f'{cat} {n}.ogg'))
                have.append(e)                                                   # and no repeats among the extras
            report.setdefault(cat, []).append(f'{leaf}:{took}')
    if os.path.exists(tmp): os.remove(tmp)
    # Halo CE's grenade screams: each line once, under every category that wants it (the voice set's own files)
    import tempfile
    from extract_elite_loose import ogg_from_wav
    counts = {}
    for f in glob.glob(os.path.join(od, '*.ogg')):
        c = re.sub(r'\s*\d+$', '', os.path.basename(f)[:-4]); counts[c] = counts.get(c, 0) + 1
    with tempfile.TemporaryDirectory() as td:
        ce = ce_grunt_lines(td)
        for cat, picks in CE_PLAN.items():
            for leaf, want in picks:
                took = 0
                for w in ce.get(leaf, [])[:want]:
                    probe = os.path.join(td, 'probe.ogg'); ogg_from_wav(w, probe)
                    e = envelope(probe)
                    if any(same_line(e, h) > 0.93 for h in have[:len(base_have)]): continue   # in the main set already
                    counts[cat] = counts.get(cat, 0) + 1; took += 1
                    shutil.copy(probe, os.path.join(od, f'{cat} {counts[cat]}.ogg'))
                report.setdefault(cat, []).append(f'ce:{leaf}:{took}')
    json.dump(report, open(os.path.join(od, 'sources.json'), 'w'), indent=1)
    for cat, v in report.items(): print(f'{cat:14s}', ', '.join(v))


if __name__ == '__main__':
    main()
