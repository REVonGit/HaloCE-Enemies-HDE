#!/usr/bin/env python3
"""Bundle the Halo CE enemies into a single pk3: Core + Covenant + Digsite + enemy API + voices.

    python3 merge_bundle.py hde           # -> HaloCE_HDE_Bundle.pk3
    python3 merge_bundle.py standalone    # -> HaloCE_Standalone_Bundle.pk3
    python3 merge_bundle.py hde -o Mine.pk3

  hde         HaloCE_Core + HaloCE_Covenant + HaloCE_Enemies_Digsite + HCE_EnemyAPI_LocalDEV + HaloCE_Enemies_Voices
              Load:  HDE (Local_DEV) -> HaloCE_HDE_Bundle.pk3
              (the API's ZScript/BaseAI/enemies_base.zsc still overrides HDE's file of the same path, so the
              bundle must load after HDE, and nothing else is needed)
  standalone  HaloCE_Standalone_Core + _Covenant + _Digsite + HaloCE_Enemies_Voices
              (the standalone core already carries the enemy API)
              Load:  HaloCE_Standalone_Bundle.pk3 on its own, with any other mods

All the packs are looked for next to this script. Needs Python 3 and merge_hce_packs.py in the same folder.
"""
import argparse, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from merge_hce_packs import merge, pack_kind, MergeError
except ImportError:
    sys.exit('merge_hce_packs.py was not found next to this script; keep them in one folder.')

BUNDLES = {
    'hde': dict(
        packs=['HaloCE_Core.pk3', 'HaloCE_Covenant.pk3', 'HaloCE_Enemies_Digsite.pk3', 'HCE_EnemyAPI_LocalDEV.pk3',
               'HaloCE_Enemies_Voices.pk3'],
        output='HaloCE_HDE_Bundle.pk3',
        load='HDE (Local_DEV) -> {out}   (no separate API, core, faction or voice pk3s)'),
    'standalone': dict(
        packs=['HaloCE_Standalone_Core.pk3', 'HaloCE_Standalone_Covenant.pk3', 'HaloCE_Standalone_Digsite.pk3',
               'HaloCE_Enemies_Voices.pk3'],
        output='HaloCE_Standalone_Bundle.pk3',
        load='{out} on its own, with any other mods (no HDE needed)'),
}


def main():
    ap = argparse.ArgumentParser(description='Bundle Core, Covenant, Digsite, the enemy API and voices into one pk3.')
    ap.add_argument('version', choices=sorted(BUNDLES), help='hde (needs HaloDoom Evolved) or standalone')
    ap.add_argument('-o', '--output', default=None, help='output pk3 (default: HaloCE_<Version>_Bundle.pk3 here)')
    a = ap.parse_args()
    b = BUNDLES[a.version]
    inputs = [os.path.join(HERE, f) for f in b['packs']]
    missing = [f for f, p in zip(b['packs'], inputs) if not os.path.isfile(p)]
    if missing:
        sys.exit('missing next to this script: ' + ', '.join(missing) + '\nAll of these are needed: ' + ', '.join(b['packs']))
    if a.version == 'standalone':
        print('(the standalone core already contains the enemy API; HCE_EnemyAPI_LocalDEV.pk3 is HDE-only)')
    wrong = []
    for p in inputs:
        try:
            k = pack_kind(zipfile.ZipFile(p))
        except zipfile.BadZipFile:
            sys.exit(f'not a pk3/zip: {p}')
        if k is not None and k != a.version: wrong.append(os.path.basename(p))
    if wrong:
        sys.exit(f'not {a.version} packs: {", ".join(wrong)}')
    output = os.path.abspath(a.output or os.path.join(HERE, b['output']))
    if output in map(os.path.abspath, inputs): sys.exit('the output would overwrite one of the packs')
    try:
        merge(inputs, output)
    except (MergeError, zipfile.BadZipFile) as e:
        sys.exit(f'merge failed: {e}')
    print('load order: ' + b['load'].format(out=os.path.basename(output)))


if __name__ == '__main__':
    main()
