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
    od = os.path.join(OUT, 'Grunt_Crazy')
    os.makedirs(od, exist_ok=True)
    for f in glob.glob(os.path.join(od, '*.ogg')): os.remove(f)
    full = {t['name'].split('\\')[-1]: t['name'] for t in m.tags if t['cls'] == 'snd!' and t['name'].startswith(PREFIX)}
    tmp = os.path.join(od, '.probe.ogg')
    report = {}
    for cat, picks in PLAN.items():
        n = 0
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
    json.dump(report, open(os.path.join(od, 'sources.json'), 'w'), indent=1)
    for cat, v in report.items(): print(f'{cat:14s}', ', '.join(v))


if __name__ == '__main__':
    main()
