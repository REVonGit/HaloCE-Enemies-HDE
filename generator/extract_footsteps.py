"""Halo 2's footsteps for the Halo CE bodies -> $HCE_OUT/footsteps/<set>/<surface>_<gait>_NN.ogg + index.json

    python3 extract_footsteps.py

Halo 2 (01b_spacestation.map + sounds_en.dat / sounds_neutral.dat: HCE_H2_MAP, HCE_H2_SOUNDS) has footsteps per race
and surface, a walk and a run (sound\\characters\\footsteps\\<race>\\<surface>\\walk|run), every take kept. Four sets:
the Marines', the Elites', the Grunts' (Jackals too: light, quick steps) and the Brutes' (Hunters too, pitched down).
Five surfaces the AI tells apart by the floor's texture (HaloDoom_EnemyBase.HCE_StepSurface): hard floor, metal
grating, dirt, grass, shallow water. A set without a surface's walk uses its run; the Marines have no water steps of
their own that decode from the MCC archive (and Halo CE's Marines step with the Chief's cyborg set too), so they use
the Chief's, played softer. split_factions.py ships each set in the packs whose bodies use it
(sndinfo.steps); HCE_StepTick plays one a stride.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_h2_brute import tag_oggs, SOUNDS_DIR, OUT
from h2_elite_anims import MAP01B, CACHE01B, MAP08A, CACHE08A

F = 'sound\\characters\\footsteps\\'
SETS = {
    'marine': {'hard': 'chief\\grtcement', 'metal': 'chief\\grating', 'dirt': 'chief\\dirt', 'grass': 'chief\\grass', 'water': 'chief\\water_shallow'},
    'elite':  {'hard': 'elite\\stone', 'metal': 'elite\\grating', 'dirt': 'elite\\gravel', 'grass': 'elite\\grass', 'water': 'elite\\water_shallow'},
    'grunt':  {'hard': 'grunt\\hard_surface', 'metal': 'grunt\\grating', 'dirt': 'grunt\\dirt', 'grass': 'grunt\\grass', 'water': 'grunt\\water_shallow'},
    'brute':  {'hard': 'brute\\grtcement', 'metal': 'brute\\grating', 'dirt': 'brute\\dirt', 'grass': 'brute\\grass', 'water': 'brute\\water_shallow'},
}


def main():
    from h2map import H2Map
    maps = [H2Map(MAP01B, CACHE01B), H2Map(MAP08A, CACHE08A)]           # 08a: the takes 01b can't give
    names = [{t['name'] for t in m.tags if t['cls'] == 'snd!'} for m in maps]

    def get(tn):
        for m, nm in zip(maps, names):
            if tn not in nm: continue
            try:
                o = tag_oggs(m, tn, files)
                if o: return o
            except ValueError as e:
                print('  ', tn, e)
        return None
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    od = f'{OUT}/footsteps'
    if os.path.exists(od): shutil.rmtree(od)
    idx = {}
    for st, surf in SETS.items():
        os.makedirs(f'{od}/{st}', exist_ok=True)
        for s, path in surf.items():
            for gait in ('walk', 'run'):
                oggs = get(F + path + '\\' + gait) or get(F + path + '\\run')   # no walk: the run, softer (HCE_StepTick)
                if not oggs: print('  no', path, gait); continue
                for i, data in enumerate(oggs):
                    fn = f'{st}/{s}_{gait}_{i:02d}.ogg'
                    open(f'{od}/{fn}', 'wb').write(data)
                    idx.setdefault(st, {}).setdefault(f'{s}_{gait}', []).append(fn)
        print(st, {k: len(v) for k, v in idx.get(st, {}).items()})
    json.dump(idx, open(f'{od}/index.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
