#!/usr/bin/env python3
"""Compile the unpacked packs in packs/ into pk3s in dist/.

    python build.py                    # every pack -> dist/<folder>.pk3, plus the merged pack and the bundle
    python build.py Covenant Flood     # only the packs whose folder name contains one of these words
    python build.py --no-merged        # skip the merged pack
    python build.py --no-bundle        # skip the bundle
    python build.py --force            # rebuild even what hasn't changed
    python build_bundle.py             # only the bundle (Core + Covenant + voices [+ API])

Edit the files under packs/<Pack>/ directly: each folder is exactly the root of its pk3.

* The bundle (repo.json "bundle") is put together at build time: the Covenant pack (Digsite included), the
  voices, the enemy API and the parts of Core they use, in one pk3 (tools/make_bundle.py).
* Only what changed is rebuilt: a pk3 whose files are the same as at its last build is skipped
  (dist/.buildcache.json remembers), so a rebuild after one edit takes a second or two.
* The HDE repository's generator/ keeps the hand-written sources too (repo.json "sync"). Edit any copy:
  before building, a shared file that differs is copied from the newest copy to the others, so they never drift.
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


def write_pk3(files, out):
    """files: [(path in pk3, bytes)] -> byte-stable pk3"""
    tmp = out + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as z:
        for arc, data in files:
            info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            stored = arc.lower().endswith(STORE)
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            z.writestr(info, data, compresslevel=None if stored else 9)
    os.replace(tmp, out)
    print(f'  {os.path.basename(out)}  {len(files)} files  {os.path.getsize(out) / 1e6:.1f} MB')


def zip_pack(name, files):
    write_pk3([(arc, open(p, 'rb').read()) for arc, p in files], os.path.join(DIST, name + '.pk3'))


def build_bundle(cache, force=False, digests=None):
    """dist/<bundle>.pk3 from repo.json "bundle" (Core + Covenant + voices [+ API]); skipped if its packs are unchanged"""
    cfg = CFG.get('bundle')
    if not cfg: return
    parts = [cfg['core']] + cfg.get('api', []) + cfg['merge']
    digests = digests if digests is not None else {}
    for n in parts:
        if n not in digests: digests[n] = digest(pack_files(n))
    key = '+'.join(digests[n] for n in parts)
    out = os.path.join(DIST, cfg['name'] + '.pk3')
    if not force and cache.get('bundle') == key and os.path.exists(out):
        print(f'  {cfg["name"]}.pk3  unchanged'); return
    sys.path.insert(0, os.path.join(HERE, 'tools'))
    from make_bundle import bundle_files
    files = bundle_files(cfg, PACKS)
    write_pk3(sorted(files.items(), key=lambda x: (x[0].count('/'), x[0].lower())), out)
    cache['bundle'] = key


def load_cache(force):
    if force or not os.path.exists(CACHE): return {}
    try: return json.load(open(CACHE))
    except ValueError: return {}


def sync_shared():
    """copies that must stay identical (repo.json "sync": lists of paths from the repository root),
    e.g. the generator's hand-written sources and the packs built from them: the newest copy wins"""
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
    ap.add_argument('--no-bundle', action='store_true', help='skip the bundle')
    ap.add_argument('--merged', action='store_true', help='(kept for old scripts: the merged pack is built by default)')
    ap.add_argument('--all', action='store_true', help='(kept for old scripts: same as no options)')
    ap.add_argument('--force', action='store_true', help='rebuild everything, changed or not')
    a = ap.parse_args()
    os.makedirs(DIST, exist_ok=True)
    cache = load_cache(a.force)
    sync_shared()
    names = sorted(d for d in os.listdir(PACKS) if os.path.isdir(os.path.join(PACKS, d)))
    want = names
    if a.only:
        want = [n for n in names if any(w.lower() in n.lower() for w in a.only)]
        if not want: sys.exit('no pack folder matches ' + ' '.join(a.only))
    merged_cfg = CFG['merged']
    build_merged = not a.no_merged and not a.only
    print(f'{CFG["title"]}: dist/')
    digests = {}
    for n in names:
        if n not in want and not (build_merged and n in merged_cfg['packs']): continue
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
    if not a.no_bundle and not a.only:
        build_bundle(cache, a.force, digests)
    json.dump(cache, open(CACHE, 'w'), indent=1, sort_keys=True)
    print('load order: ' + CFG['load'])


if __name__ == '__main__':
    main()
