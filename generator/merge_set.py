"""Shared runner for merge_hde_packs.py and merge_standalone_packs.py (one pack set each)."""
import argparse, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from merge_hce_packs import merge, pack_kind, MergeError
except ImportError:
    sys.exit('merge_hce_packs.py was not found next to this script; keep the merge scripts in one folder.')

VOICES = 'HaloCE_Enemies_Voices.pk3'


def run(cfg):
    ap = argparse.ArgumentParser(description=f'Merge the {cfg["title"]} Halo CE enemy packs into one pk3.')
    ap.add_argument('inputs', nargs='*', help=f'pk3s to merge (default: every {cfg["title"]} pack next to this script)')
    ap.add_argument('-o', '--output', default=None, help=f'output pk3 (default: {cfg["output"]} next to the inputs)')
    ap.add_argument('--voices', action='store_true', help=f'also fold {VOICES} into the merged pack')
    a = ap.parse_args()

    if a.inputs:
        inputs = [os.path.abspath(p) for p in a.inputs]
        base = os.path.dirname(inputs[0])
    else:
        base = HERE
        core = os.path.join(base, cfg['core'])
        if not os.path.isfile(core):
            sys.exit(f'{cfg["core"]} was not found next to this script. It is required: put it here and run again.')
        inputs = [core] + [os.path.join(base, f) for f in cfg['optional'] if os.path.isfile(os.path.join(base, f))]
    if a.voices:
        v = os.path.join(base, VOICES)
        if not os.path.isfile(v): sys.exit(f'--voices: {VOICES} was not found next to the packs.')
        if v not in inputs: inputs.append(v)
    output = os.path.abspath(a.output or os.path.join(base, cfg['output']))
    if output in inputs: sys.exit('the output would overwrite one of the packs being merged')

    # every pack must belong to this set (the voice pack belongs to both)
    wrong = []
    for p in inputs:
        if not os.path.isfile(p): sys.exit(f'not found: {p}')
        try:
            k = pack_kind(zipfile.ZipFile(p))
        except zipfile.BadZipFile:
            sys.exit(f'not a pk3/zip: {p}')
        if k is not None and k != cfg['kind']: wrong.append(os.path.basename(p))
    if wrong:
        other = 'merge_standalone_packs.py' if cfg['kind'] == 'hde' else 'merge_hde_packs.py'
        sys.exit(f'not {cfg["title"]} packs: {", ".join(wrong)}. Use {other} for those.')

    print(f'{cfg["title"]} packs: {", ".join(os.path.basename(p) for p in inputs)}')
    try:
        merge(inputs, output)
    except (MergeError, zipfile.BadZipFile) as e:
        sys.exit(f'merge failed: {e}')
    load = cfg['load'].format(out=os.path.basename(output))
    if a.voices: load = load.replace(f' -> {VOICES} (optional)', '') + f'   ({VOICES} is inside it: don\'t load it separately)'
    print('load order: ' + load)
