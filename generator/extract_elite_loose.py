"""The Elite_Loose dialogue set, rebuilt from Halo CE's Elite dialogue plus Halo 2's elite_loose lines played
backwards. CE's Elites speak recorded English run in reverse, so reversed Halo 2 lines sit with them as the
same alien tongue.

    python3 extract_elite_loose.py      # -> voice_extra/Elite_Loose/<Category> N.ogg  (+ REPLACE marker)

* Halo CE: sound\\dialog\\elite\\* from the Xbox campaign maps (HCE_MAPS, the first map that has the tag), kept
  as they are (Xbox ADPCM -> Vorbis).
* Halo 2: sound\\dialog\\combat\\elite_loose\\* from 08a_deltacliffs.map + sounds_en.dat (HCE_H2_MAP08 /
  HCE_H2_SOUNDS), reversed with a short fade at the (new) end so it doesn't stop on a click.
The REPLACE marker tells build_voices.py to use these lines instead of the main source's Elite_Loose set.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import glob, hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.environ.get('HCE_VOICE_EXTRA', os.path.join(HERE, 'voice_extra'))
CE_MAPS = os.environ.get('HCE_MAPS', 'maps')
CE_ORDER = ['a10', 'a30', 'a50', 'b30', 'b40', 'c10', 'c20', 'c40', 'd20', 'd40']
CE_PREFIX = 'sound\\dialog\\elite\\'
H2_PREFIX = 'sound\\dialog\\combat\\elite_loose\\'

# pack category (build_voices.CAT key) -> CE tags (all their lines), [(Halo 2 tag, how many lines)]
PLAN = {
    'Alert':         (['groupcomm\\sightednewenemy', 'groupcomm\\oldenemysighted', 'groupcomm\\sightedenemyrecentcombat'],
                      [('seefoe', 3), ('seefoe_srprs', 2), ('foundfoe', 2)]),
    'Taunt':         (['actions\\taunt', 'hurtingpeople\\damagedenemy'],
                      [('tnt', 3), ('tnt_hum', 2), ('thrtn', 3), ('thrtn_hum', 2)]),
    'Kill Player':   (['killingpeople\\killedenemyplayer', 'killingpeople\\killedenemyplayercm'],
                      [('glt', 3), ('glt_hum', 2), ('chr_kllfoe', 2)]),
    'Berserk':       (['exclamations\\berserk'], [('brsrk', 4), ('charge', 2)]),
    'Melee':         (['exclamations\\meleeattack'], [('melee', 4)]),
    'Grenade Thrw':  (['shouting\\grenadethrowing'], [('strk_grnd', 4)]),
    'Enemy Grenade': (['shouting\\grenadesighted', 'shouting\\grenadedangerenemy'], [('warn_incmn_grnd', 3), ('warn_incmn', 2)]),
    'Regroup':       (['groupcomm\\groupuncover', 'groupcomm\\newenemynearre'], [('joinme', 3), ('cvrme', 2)]),
    'Leader Dead':   (['friendsdying\\frienddied', 'friendsdying\\friendkilledbyenemyplayer'], [('lmnt_deadally', 3)]),
    'Death':         (['involuntary\\deathquiet', 'involuntary\\deathinstant'], [('dth', 4), ('dth_slnt', 2)]),
    'Death Xtr':     (['involuntary\\deathviolent', 'involuntary\\deathflying', 'involuntary\\deathfalling'], [('dth_mjr', 3), ('dth_hdsht', 2)]),
    'Pain Nrml':     (['involuntary\\painminor'], [('pain', 4)]),
    'Pain Med':      (['beinghurt\\hurtenemy', 'beinghurt\\hurtenemymelee'], [('pain_mdm', 4)]),
    'Pain Xtr':      (['involuntary\\painmajor'], [('pain_mjr', 3)]),
    'On Fire':       (['involuntary\\screampain'], [('whn_hrtbrn', 3)]),
    'Stuck':         ([], [('whn', 3), ('whn_hrtblt', 2)]),
    'Panic':         ([], [('panic', 3)]),
    'Flee':          ([], [('newordr_retreat', 3), ('foeordr_fallback', 2)]),
    'Man Down':      (['friendsdying\\frienddied', 'friendsdying\\friendkilledbyenemy'], [('lmnt_deadally', 3), ('lmnt', 2)]),
    'Heard Gunfire': (['groupcomm\\searchquery'], [('hrdfoe', 3), ('srchstart', 2)]),
    # combat callouts (HCE_Say: Cover, SearchStart ...)
    'Cover': ([], [('cvrme', 3), ('cvrme_re', 2)]),
    'Uncovered': ([], [('hlpme_uncovered', 3)]),
    'Search Start': ([], [('srchstart', 3), ('srchpresrch', 2)]),
    'Search Clear': ([], [('srch_allclr', 3), ('prst_allclr', 2)]),
    'Search Fail': ([], [('prstfail', 3), ('prstfail_agg', 1), ('prstfail_tim', 1)]),
    'Keep Watch': ([], [('keepwatch', 3)]),
    'Found Foe': ([], [('foundfoe_srch', 3), ('foundfoe', 2)]),
    'Join Me': ([], [('joinme', 3), ('joinme_emrg', 2)]),
    'Charge': ([], [('newordr_charge', 3), ('charge', 2)]),
    'Investigate': ([], [('cvrme_invsgt', 3)]),
    'Behind': ([], [('seefoe_srprs', 3), ('seefoe_too', 2)]),
    'Sniper': ([], [('warn_wpn_snpr', 3)]),
    'Sword': ([], [('warn_wpn_swrd', 3)]),
    'Up There': ([], [('seefoe_upthere', 3)]),
    'Down There': ([], [('seefoe_downthere', 3)]),
    'Fall Back': ([], [('newordr_fallback', 3), ('newordr_retreat', 2)]),
    'Advance': ([], [('newordr_advance', 3), ('newordr_moveon', 2)]),
}


def ogg_from_wav(wav, out, extra_af=None):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', wav]
    if extra_af: cmd += ['-af', extra_af]
    subprocess.run(cmd + ['-c:a', 'libvorbis', '-q:a', '5', out], check=True)


def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True).stdout.strip()
    return float(r or 0)


def ce_lines(tmp):
    """{CE tag suffix: [wav paths]} from the first CE map that has each tag"""
    from tags import HMap, tag
    from halosound import xbox_adpcm, to_wav
    want = {s for ce, _ in PLAN.values() for s in ce}
    found = {}
    for mp in CE_ORDER:
        path = os.path.join(CE_MAPS, mp + '.map')
        if not os.path.exists(path) or len(found) == len(want): continue
        m = HMap(path)
        for t in m.tags:
            if t['cls'] != 'snd!' or not t['name'].startswith(CE_PREFIX): continue
            suf = '\\'.join(t['name'].split('\\')[-2:])                        # <group>\<name>
            if suf not in want or suf in found: continue
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
            found[suf] = wavs
    return found


def h2_lines(tmp):
    """{Halo 2 tag leaf: [ogg paths]}"""
    from extract_h2_brute import tag_oggs, SOUNDS_DIR, MAP08A, CACHE08A
    from h2map import H2Map
    want = {leaf for _, h2 in PLAN.values() for leaf, _ in h2}
    m = H2Map(MAP08A, CACHE08A)
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    out = {}
    for t in m.tags:
        if t['cls'] != 'snd!' or not t['name'].startswith(H2_PREFIX): continue
        leaf = t['name'].split('\\')[-1]
        if leaf not in want: continue
        paths = []
        for i, data in enumerate(tag_oggs(m, t['name'], files) or []):
            p = os.path.join(tmp, f'h2_{leaf}_{i}.ogg'); open(p, 'wb').write(data); paths.append(p)
        out[leaf] = paths
    return out


def main():
    od = os.path.join(OUT, 'Elite_Loose')
    os.makedirs(od, exist_ok=True)
    for f in glob.glob(os.path.join(od, '*.ogg')): os.remove(f)
    tmp = tempfile.mkdtemp()
    ce_dir = os.path.join(tmp, 'ce'); os.makedirs(ce_dir)
    ce = ce_lines(ce_dir)
    h2 = h2_lines(tmp)
    used_h2, report = set(), {}
    for cat, (ce_tags, h2_picks) in PLAN.items():
        n = 0; rep = []; seen = set()
        for suf in ce_tags:
            took = 0
            for w in ce.get(suf, []):
                key = hashlib.sha1(open(w, 'rb').read()).hexdigest()
                if key in seen: continue          # CE's tags share recordings (its pain / death screams): once per event
                seen.add(key); n += 1; took += 1
                ogg_from_wav(w, os.path.join(od, f'{cat} {n}.ogg'))
            rep.append(f'CE {suf.split(chr(92))[-1]}:{took}')
        for leaf, want in h2_picks:
            took = 0
            for p in h2.get(leaf, []):
                if took >= want: break
                if p in used_h2: continue
                d = duration(p)
                if d < 0.15: continue
                used_h2.add(p); n += 1; took += 1
                fade = min(0.06, d * 0.2)
                ogg_from_wav(p, os.path.join(od, f'{cat} {n}.ogg'), f'areverse,afade=t=out:st={d - fade:.3f}:d={fade:.3f}')
            rep.append(f'H2 {leaf} reversed:{took}')
        report[cat] = rep
    open(os.path.join(od, 'REPLACE'), 'w').write('build_voices.py: use these lines instead of the main source set\n')
    json.dump(report, open(os.path.join(od, 'sources.json'), 'w'), indent=1)
    for cat, rep in report.items(): print(f'{cat:14s}', ', '.join(rep))
    print(len(glob.glob(os.path.join(od, '*.ogg'))), 'lines')


if __name__ == '__main__':
    main()
