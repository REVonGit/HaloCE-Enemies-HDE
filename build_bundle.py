#!/usr/bin/env python3
"""Compile only the Covenant bundle: Core, Covenant, Digsite, voices and the enemy API, nothing else.

    python build_bundle.py            # -> dist/<bundle>.pk3 (skipped if nothing in it changed)
    python build_bundle.py --force    # rebuild it even if nothing changed

The bundle folder (repo.json "bundle_folder") already holds exactly those five parts: the Covenant enemies,
the Digsite add-on, the voices, the enemy API and the Core code they use. So this builds that one pk3 and
skips Flood, Sentinels, Marines and the merged pack. Load the result on its own (after HDE in the HDE version).

Like build.py, it first syncs the shared copies (Core / API / generator sources), and it shares build.py's
cache, so either script knows what the other already built.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402  (build.py next to this file)


def main():
    ap = argparse.ArgumentParser(description='Compile only the bundle pk3 (Core + Covenant + Digsite + voices + API)')
    ap.add_argument('--force', action='store_true', help='rebuild even if nothing changed')
    a = ap.parse_args()
    bf = build.CFG.get('bundle_folder')
    if not bf or not os.path.isdir(os.path.join(build.PACKS, bf['name'])):
        sys.exit('no bundle folder in packs/ (repo.json "bundle_folder")')
    name = bf['name']
    os.makedirs(build.DIST, exist_ok=True)
    cache = {}
    if os.path.exists(build.CACHE):
        try: cache = json.load(open(build.CACHE))
        except ValueError: cache = {}
    build.sync_shared()
    files = build.pack_files(name)
    d = build.digest(files)
    out = os.path.join(build.DIST, name + '.pk3')
    print(f'{build.CFG["title"]}: dist/')
    if not a.force and cache.get(name) == d and os.path.exists(out):
        print(f'  {name}.pk3  unchanged')
    else:
        build.zip_pack(name, files)
        cache[name] = d
        json.dump(cache, open(build.CACHE, 'w'), indent=1, sort_keys=True)
    print(f'load: {name}.pk3 on its own' + (' after HaloDoom Evolved (Local_DEV)' if bf.get('api') else '') +
          '. Don\'t load it with the separate Core' + (' or API' if bf.get('api') else '') + ' pk3.')


if __name__ == '__main__':
    main()
