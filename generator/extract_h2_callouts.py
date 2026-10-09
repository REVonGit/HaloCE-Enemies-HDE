"""'Man down' and 'heard gunfire' lines for the voice sets that have no builder of their own: the Jackal and the
Dogmatic Elite.

    python3 extract_h2_callouts.py      # -> voice_extra/<Voice>/{Man Down,Heard Gunfire} N.ogg

* Halo 2: sound\\dialog\\combat\\<voice>\\* in 08a_deltacliffs.map (+ sounds_en.dat): lmnt_deadally / lmnt (a
  comrade killed), hrdfoe / srchstart (an enemy heard, a search begun).
* Halo CE: the Jackal's own search_query (combat2\\groupcomm) from the Xbox campaign maps.
build_voices.py merges these with the main source's set of the same name (no REPLACE marker). Re-running replaces
only these two categories. (Marines: extract_marine_voices.py; Elite_Loose: extract_elite_loose.py; Grunt_Crazy:
extract_h2_grunt.py; Brutes: build_digsite.BRUTE_EVENTS.)"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import glob, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.environ.get('HCE_VOICE_EXTRA', os.path.join(HERE, 'voice_extra'))
CE_MAPS = os.environ.get('HCE_MAPS', 'maps')
CE_ORDER = ['a10', 'a30', 'a50', 'b30', 'b40', 'c10', 'c20', 'c40', 'd20', 'd40']
# voice set -> (Halo 2 voice, Halo CE tag prefix or None, {category: ([(H2 leaf, n)], [(CE <group>\<name>, n)])})
SETS = {
    'Jackal': ('jackal', 'sound\\dialog\\jackal\\combat2\\', {
        'Heard Gunfire': ([('hrdfoe', 4)], [('groupcomm\\search_query', 3)]),
    }),
    'Elite_Dogmatic': ('elite_dogmatic', None, {
        'Man Down':      ([('lmnt_deadally', 4), ('lmnt', 2)], []),
        'Heard Gunfire': ([('hrdfoe', 4), ('srchstart', 2)], []),
    }),
}


def main():
    from extract_h2_brute import tag_oggs, SOUNDS_DIR, MAP08A, CACHE08A
    from extract_elite_loose import ogg_from_wav, duration
    from h2map import H2Map
    from tags import HMap, tag
    from halosound import xbox_adpcm, to_wav
    m = H2Map(MAP08A, CACHE08A)
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    full = {}                                    # (voice, leaf) -> tag name (the voices file their lines in subfolders)
    for t in m.tags:
        if t['cls'] == 'snd!' and t['name'].startswith('sound\\dialog\\combat\\'):
            full.setdefault((t['name'].split('\\')[3], t['name'].split('\\')[-1]), t['name'])
    ce_want = {(pre, leaf) for _, pre, cats in SETS.values() if pre for _, ce in cats.values() for leaf, _ in ce}
    tmp = tempfile.mkdtemp()
    ce = {}
    for mp in CE_ORDER:
        path = os.path.join(CE_MAPS, mp + '.map')
        if not os.path.exists(path) or len(ce) == len(ce_want): continue
        cm = HMap(path)
        for pre, leaf in ce_want:
            if (pre, leaf) in ce: continue
            t = next((t for t in cm.tags if t['cls'] == 'snd!' and t['name'] == pre + leaf), None)
            if not t: continue
            S = tag(cm, t, 'sound_definition')
            ch = 2 if S['encoding'] == 1 else 1
            rate = 44100 if S['sample_rate'] == 1 else 22050
            wavs = []
            for pr in S.block('pitch_ranges', 'sound_pitch_range'):
                for pm in pr.block('permutations', 'sound_permutation'):
                    sz, fl, fo = cm.u('iii', pm.addr + 64)
                    if pm['compression'] != 1 or sz <= 0: continue
                    w = os.path.join(tmp, f'ce_{len(os.listdir(tmp))}.wav')
                    to_wav(xbox_adpcm(cm.d[fo:fo + sz], ch), rate, ch, w)
                    wavs.append(w)
            ce[(pre, leaf)] = wavs
    for voice, (h2v, pre, cats) in SETS.items():
        od = os.path.join(OUT, voice); os.makedirs(od, exist_ok=True)
        for cat, (h2, cel) in cats.items():
            for f in glob.glob(os.path.join(od, f'{cat} *.ogg')): os.remove(f)
            n = 0; rep = []
            for leaf, want in h2:
                name = full.get((h2v, leaf))
                took = 0
                for data in (tag_oggs(m, name, files) or []) if name else []:
                    if took >= want: break
                    p = os.path.join(tmp, 'probe.ogg'); open(p, 'wb').write(data)
                    if duration(p) < 0.15: continue
                    n += 1; took += 1
                    ogg_from_wav(p, os.path.join(od, f'{cat} {n}.ogg'))
                rep.append(f'{leaf}:{took}')
            for leaf, want in cel:
                took = 0
                for w in ce.get((pre, leaf), [])[:want]:
                    n += 1; took += 1
                    ogg_from_wav(w, os.path.join(od, f'{cat} {n}.ogg'))
                rep.append(f'ce {leaf}:{took}')
            print(f'{voice:16s} {cat:14s}', ', '.join(rep))


if __name__ == '__main__':
    main()
