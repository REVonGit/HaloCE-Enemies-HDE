#!/usr/bin/env python3
"""Compile only the bundle: Core + Covenant (Digsite included) + voices (+ the enemy API in the HDE version).

    python build_bundle.py            # -> dist/HDE_CE_Covenant.pk3 (skipped if none of its packs changed)
    python build_bundle.py --force    # rebuild it even if nothing changed

The bundle is put together from the pack folders named in repo.json "bundle" (tools/make_bundle.py): the Covenant
pack and the voices are merged, the API is added whole, and Core goes in with all of its code but only the
sounds, sprites and models the bundled enemies use. Flood, Sentinels, Marines and the merged pack are skipped.
Load the result on its own (after HDE in the HDE version).

Like build.py, it first syncs the shared copies (generator sources), and it shares build.py's cache, so either
script knows what the other already built.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402  (build.py next to this file)


def main():
    ap = argparse.ArgumentParser(description='Compile only the bundle pk3 (Core + Covenant + voices [+ API])')
    ap.add_argument('--force', action='store_true', help='rebuild even if nothing changed')
    a = ap.parse_args()
    cfg = build.CFG.get('bundle')
    if not cfg: sys.exit('repo.json has no "bundle"')
    os.makedirs(build.DIST, exist_ok=True)
    cache = build.load_cache(False)
    build.sync_shared()
    print(f'{build.CFG["title"]}: dist/   ({" + ".join([cfg["core"]] + cfg.get("api", []) + cfg["merge"])})')
    build.build_bundle(cache, a.force)
    json.dump(cache, open(build.CACHE, 'w'), indent=1, sort_keys=True)
    hde = bool(cfg.get('api'))
    print(f'load: {cfg["name"]}.pk3 on its own' + (' after HaloDoom Evolved (Local_DEV)' if hde else '') +
          f'. Don\'t load it with {cfg["core"]}.pk3' + (' or the API pk3' if hde else '') + '.')


if __name__ == '__main__':
    main()
