"""Adopt the post-extraction steps already on the bodies as step stamps (lib/steps.py) -> out/models/<Char>/<Char>.json

    python3 stamp_steps.py [char ...]

For a model made before the stamps existed: records, for each step that covers the body (the steps' CHARS tables),
the animations of that step's kind that the body already has, as if the step had just run. A body with none of a
step's animations gets no stamp, so build_pack.py's check then asks for the step. Re-running a step writes its own
stamp; this only fills in the past."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import steps, low_ready_anims, reload_anims, cover_anims, marine_h2_grips
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
# step -> (bodies, does this animation name belong to the step on that body)
STEPS = {
    'low_ready_anims': (low_ready_anims.CHARS, lambda c, n: n.endswith(low_ready_anims.MARK)),
    'reload_anims': (reload_anims.CHARS, lambda c, n: n.startswith('stand ') and any(m in n for m in reload_anims.MARK)),
    'cover_anims': (cover_anims.CHARS, lambda c, n: n.startswith('stand ') and any(m in n for m in cover_anims.MARK)),
    'marine_h2_grips': (marine_h2_grips.CHARS, lambda c, n: f' {marine_h2_grips.STANCE} ' in f' {n} '
                        or any(f' {st} ' in f' {n} ' for st, (_, bodies) in marine_h2_grips.H2_GUNS.items() if c in bodies)),
}


def main(chars):
    for c in chars or sorted({c for bodies, _ in STEPS.values() for c in bodies}):
        pj = f'{OUT}/models/{c}/{c}.json'
        if not os.path.exists(pj): continue
        meta = json.load(open(pj)); done = []
        for step, (bodies, owns) in STEPS.items():
            if c not in bodies or step in (meta.get('steps') or {}): continue
            names = [n for n in meta['anims'] if owns(c, n)]
            if names: steps.stamp(meta, step, names); done.append(f'{step} ({len(names)})')
        if done:
            json.dump(meta, open(pj, 'w'), indent=1)
            print(c, 'stamped:', ', '.join(done))


if __name__ == '__main__':
    main(sys.argv[1:])
