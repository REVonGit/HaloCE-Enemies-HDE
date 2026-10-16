"""Step stamps: a record in a model's JSON of what each post-extraction step added, so build_pack.py can tell when a
body was re-extracted and a step not re-run.

A model's JSON (out/models/<Char>/<Char>.json) is written fresh by its extractor (extract_chars.py, extract_odst.py,
extract_h2_jackal.py ...); the steps that add to the body afterwards (low_ready_anims.py, reload_anims.py,
cover_anims.py, marine_h2_grips.py) each stamp the names they added:

    meta['steps'][<step>] = [animation names]

A re-extraction drops the stamps (fresh JSON) or leaves stamped names with no animation behind them (an extractor that
keeps the JSON but rewrites the animations); either way check() reports it, and build_pack stops with the script to
re-run instead of building a body that falls back to the wrong stance (the Halo 2 ODSTs held their guns like pistols
for three days this way).
"""


def stamp(meta, step, names):
    """record in meta that step added the animations names"""
    meta.setdefault('steps', {})[step] = sorted(set(names))


def check(meta, char, required):
    """problems with char's stamps: required = {step: script to run}; returns ['<what>: run <script>', ...]"""
    out = []
    anims = meta.get('anims') or {}
    steps = meta.get('steps') or {}
    for step, script in required.items():
        if step not in steps:
            out.append(f"{char}: no record of {step} (the body was re-extracted since?): run {script}")
            continue
        lost = [n for n in steps[step] if n not in anims]
        if lost:
            out.append(f"{char}: {len(lost)} of {step}'s animations are gone (e.g. {lost[0]!r}; the body was re-extracted since?): run {script}")
    return out
