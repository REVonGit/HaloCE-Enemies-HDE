#!/usr/bin/env python3
"""Merge the Covenant essentials into one pk3, for the HDE version and/or the standalone version.

    python3 merge_core_covenant.py               # both versions, whichever packs are next to this script
    python3 merge_core_covenant.py --hde         # HDE version only
    python3 merge_core_covenant.py --standalone  # standalone version only

  HDE version         HCE_EnemyAPI_LocalDEV.pk3 + HaloCE_Core.pk3 + HaloCE_Covenant.pk3 + HaloCE_Enemies_Voices.pk3
                      -> HaloCE_Covenant_Merged.pk3            load it right after HDE (Local_DEV), nothing else needed
  standalone version  HaloCE_Standalone_Core.pk3 (the API is built in) + HaloCE_Standalone_Covenant.pk3
                      + HaloCE_Enemies_Voices.pk3
                      -> HaloCE_Standalone_Covenant_Merged.pk3 load it on its own, with any other mods

The voice pack is optional: without it the merge still runs, just silent enemies. The API pk3 only replaces HDE's
own ZScript/BaseAI/enemies_base.zsc, so inside the merged pk3 it still overrides HDE's copy as long as the merged
pk3 loads after HDE. Needs Python 3 and merge_hce_packs.py in the same folder.
"""
import argparse, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from merge_hce_packs import merge, pack_kind, MergeError
except ImportError:
    sys.exit('merge_hce_packs.py was not found next to this script; keep the merge scripts in one folder.')

VOICES = 'HaloCE_Enemies_Voices.pk3'
SETS = {
    'hde': dict(title='HDE', required=['HCE_EnemyAPI_LocalDEV.pk3', 'HaloCE_Core.pk3', 'HaloCE_Covenant.pk3'],
                output='HaloCE_Covenant_Merged.pk3',
                load='HDE (Local_DEV) -> {out}   (the API is inside it: don\'t load HCE_EnemyAPI_LocalDEV.pk3 or the voice pack separately)'),
    'standalone': dict(title='standalone', required=['HaloCE_Standalone_Core.pk3', 'HaloCE_Standalone_Covenant.pk3'],
                       output='HaloCE_Standalone_Covenant_Merged.pk3',
                       load='{out} on its own, with any other mods   (don\'t load the voice pack separately)'),
}


def build(key, base):
    cfg = SETS[key]
    paths = [os.path.join(base, f) for f in cfg['required']]
    missing = [os.path.basename(p) for p in paths if not os.path.isfile(p)]
    if missing:
        return None, f'{cfg["title"]} version skipped: missing {", ".join(missing)}'
    v = os.path.join(base, VOICES)
    note = ''
    if os.path.isfile(v): paths.append(v)
    else: note = f' ({VOICES} not found: merged without voices)'
    for p in paths:
        k = pack_kind(zipfile.ZipFile(p))
        if k is not None and k != key:
            return None, f'{cfg["title"]} version skipped: {os.path.basename(p)} is not a {cfg["title"]} pack'
    out = os.path.join(base, cfg['output'])
    print(f'== {cfg["title"]} version: {", ".join(os.path.basename(p) for p in paths)}{note}')
    merge(paths, out)
    load = cfg['load'].format(out=cfg['output'])
    if not os.path.isfile(v): load = load.replace(' or the voice pack', '').replace('   (don\'t load the voice pack separately)', '')
    print('   load order: ' + load)
    return out, None


def main():
    ap = argparse.ArgumentParser(description='Merge Core + Covenant (+ API) + voices for the HDE and/or standalone version.')
    ap.add_argument('--hde', action='store_true', help='HDE version only')
    ap.add_argument('--standalone', action='store_true', help='standalone version only')
    ap.add_argument('--dir', default=HERE, help='folder holding the pk3s (default: this script\'s folder)')
    a = ap.parse_args()
    keys = [k for k, on in (('hde', a.hde), ('standalone', a.standalone)) if on] or ['hde', 'standalone']
    made, notes = [], []
    for k in keys:
        try:
            out, why = build(k, os.path.abspath(a.dir))
        except (MergeError, zipfile.BadZipFile) as e:
            out, why = None, f'{SETS[k]["title"]} version failed: {e}'
        if out: made.append(out)
        if why: notes.append(why)
    for n in notes: print(n)
    if not made: sys.exit('nothing merged. Put the packs listed above next to this script and run again.')


if __name__ == '__main__':
    main()
