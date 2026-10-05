#!/usr/bin/env python3
"""Compile the unpacked packs in packs/ into pk3s in dist/.

    python build.py                    # every pack -> dist/<folder>.pk3, plus the merged pack
    python build.py Bundle Flood       # only the packs whose folder name contains one of these words
    python build.py --no-merged        # skip the merged pack
    python build.py --force            # rebuild even what hasn't changed

Edit the files under packs/<Pack>/ directly: each folder is exactly the root of its pk3.

* Only what changed is rebuilt: a pack whose files are the same as at its last build is skipped
  (dist/.buildcache.json remembers), so a rebuild after one edit takes a second or two.
* The bundle carries its own copy of Core's code (and, in the HDE version, the enemy API), and the HDE
  repository's generator/ keeps the hand-written sources too (repo.json "sync"). Edit any copy: before
  building, a shared file that differs is copied from the newest copy to the others, so they never drift.
* Sounds and images (already compressed) are stored as they are; text and models are deflated.
* The pk3s are byte-stable: the same files always give the same pk3.
Needs only Python 3 (standard library). tools/merge_hce_packs.py does the merging.
"""
import argparse, hashlib, json, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS = os.path.join(HERE, 'packs')
DIST = os.path.join(HERE, 'dist')
CACHE = os.path.join(DIST, '.buildcache.json')
CFG = json.load(open(os.path.join(HERE, 'repo.json')))
SKIP = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '.loudened.json'}
STORE = ('.ogg', '.png', '.jpg', '.jpeg', '.flac', '.mp3')       # already compressed: stored, not deflated


def pack_files(name):
    src = os.path.join(PACKS, name)
    files = []
    for root, dirs, fs in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.git'))
        for f in sorted(fs):
            if f in SKIP or f.endswith('.tmp'): continue
            p = os.path.join(root, f)
            files.append((os.path.relpath(p, src).replace(os.sep, '/'), p))
    files.sort(key=lambda x: (x[0].count('/'), x[0].lower()))   # root lumps first, then by path
    return files


def digest(files):
    h = hashlib.sha1()
    for arc, p in files:
        h.update(arc.encode() + b'\0')
        with open(p, 'rb') as fh: h.update(hashlib.sha1(fh.read()).digest())
    return h.hexdigest()


def zip_pack(name, files):
    out = os.path.join(DIST, name + '.pk3')
    tmp = out + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as z:
        for arc, p in files:
            info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            stored = arc.lower().endswith(STORE)
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            with open(p, 'rb') as fh:
                z.writestr(info, fh.read(), compresslevel=None if stored else 9)
    os.replace(tmp, out)
    print(f'  {name}.pk3  {len(files)} files  {os.path.getsize(out) / 1e6:.1f} MB')


def sync_shared():
    """Core's (and the API's) files that the bundle also carries: newer copy wins, both ways"""
    bf = CFG.get('bundle_folder')
    if not bf: return
    bundle = os.path.join(PACKS, bf['name'])
    if not os.path.isdir(bundle): return
    for other in [bf['core']] + bf.get('api', []):
        od = os.path.join(PACKS, other)
        if not os.path.isdir(od): continue
        for arc, p in pack_files(other):
            if '/' not in arc: continue                # root lumps (cvarinfo, sndinfo ...) are merged/trimmed copies
            q = os.path.join(bundle, *arc.split('/'))
            if not os.path.isfile(q): continue
            a, b = open(p, 'rb').read(), open(q, 'rb').read()
            if a == b: continue
            src, dst = (p, q) if os.path.getmtime(p) >= os.path.getmtime(q) else (q, p)
            shutil.copy2(src, dst)
            print(f'  synced {arc}: {os.path.relpath(src, PACKS)} -> {os.path.relpath(dst, PACKS)}')
    # other copies that must stay identical (repo.json "sync": lists of paths from the repository root),
    # e.g. the generator's hand-written sources and the packs built from them
    for group in CFG.get('sync', []):
        paths = [os.path.join(HERE, *g.split('/')) for g in group if os.path.isfile(os.path.join(HERE, *g.split('/')))]
        if len(paths) < 2: continue
        newest = max(paths, key=os.path.getmtime)
        data = open(newest, 'rb').read()
        for q in paths:
            if q != newest and open(q, 'rb').read() != data:
                shutil.copy2(newest, q)
                print(f'  synced {os.path.relpath(newest, HERE)} -> {os.path.relpath(q, HERE)}')


def main():
    ap = argparse.ArgumentParser(description='Compile packs/ into dist/*.pk3 (only what changed)')
    ap.add_argument('only', nargs='*', help='build only packs whose folder name contains one of these words')
    ap.add_argument('--no-merged', action='store_true', help=f'skip {CFG["merged"]["output"]}')
    ap.add_argument('--merged', action='store_true', help='(kept for old scripts: the merged pack is built by default)')
    ap.add_argument('--all', action='store_true', help='(kept for old scripts: same as no options)')
    ap.add_argument('--force', action='store_true', help='rebuild everything, changed or not')
    a = ap.parse_args()
    os.makedirs(DIST, exist_ok=True)
    cache = {}
    if not a.force and os.path.exists(CACHE):
        try: cache = json.load(open(CACHE))
        except ValueError: cache = {}
    sync_shared()
    names = sorted(d for d in os.listdir(PACKS) if os.path.isdir(os.path.join(PACKS, d)))
    want = names
    if a.only:
        want = [n for n in names if any(w.lower() in n.lower() for w in a.only)]
        if not want: sys.exit('no pack folder matches ' + ' '.join(a.only))
    merged_cfg = CFG['merged']
    build_merged = not a.no_merged and not a.only
    need = set(want) | (set(merged_cfg['packs']) if build_merged else set())
    print(f'{CFG["title"]}: dist/')
    digests = {}
    for n in names:
        if n not in need: continue
        files = pack_files(n)
        d = digests[n] = digest(files)
        out = os.path.join(DIST, n + '.pk3')
        if cache.get(n) == d and os.path.exists(out):
            if n in want: print(f'  {n}.pk3  unchanged')
            continue
        zip_pack(n, files)
        cache[n] = d
    if build_merged:
        key = '+'.join(digests[n] for n in merged_cfg['packs'])
        out = os.path.join(DIST, merged_cfg['output'])
        if cache.get('merged') == key and os.path.exists(out):
            print(f'  {merged_cfg["output"]}  unchanged')
        else:
            sys.path.insert(0, os.path.join(HERE, 'tools'))
            from merge_hce_packs import merge
            merge([os.path.join(DIST, n + '.pk3') for n in merged_cfg['packs']], out)
            cache['merged'] = key
    json.dump(cache, open(CACHE, 'w'), indent=1, sort_keys=True)
    print('load order: ' + CFG['load'])


if __name__ == '__main__':
    main()
