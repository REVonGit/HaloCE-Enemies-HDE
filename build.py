#!/usr/bin/env python3
"""Compile the unpacked packs in packs/ into pk3s in dist/.

    python build.py                    # every pack folder -> dist/<folder>.pk3
    python build.py Covenant Digsite   # only the packs whose folder name contains one of these words
    python build.py --bundle           # also the all-in-one bundle (see BUNDLE in repo.json)
    python build.py --merged           # also every enemy pack merged into one (no API / voices)
    python build.py --all              # packs + bundle + merged

Edit the files under packs/<Pack>/ directly: each folder is exactly the root of its pk3.
Needs only Python 3 (standard library). tools/merge_hce_packs.py does the merging.
"""
import argparse, json, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS = os.path.join(HERE, 'packs')
DIST = os.path.join(HERE, 'dist')
CFG = json.load(open(os.path.join(HERE, 'repo.json')))
SKIP = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}


def zip_pack(name):
    src = os.path.join(PACKS, name)
    out = os.path.join(DIST, name + '.pk3')
    files = []
    for root, dirs, fs in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.git'))
        for f in sorted(fs):
            if f in SKIP: continue
            p = os.path.join(root, f)
            files.append((os.path.relpath(p, src).replace(os.sep, '/'), p))
    # root lumps first, then by path: stable, diff-friendly pk3s
    files.sort(key=lambda x: (x[0].count('/'), x[0].lower()))
    tmp = out + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arc, p in files:
            info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(p, 'rb') as fh:
                z.writestr(info, fh.read(), compresslevel=9)
    os.replace(tmp, out)
    print(f'  {name}.pk3  {len(files)} files  {os.path.getsize(out) / 1e6:.1f} MB')
    return out


def merged(names, output):
    sys.path.insert(0, os.path.join(HERE, 'tools'))
    from merge_hce_packs import merge
    merge([os.path.join(DIST, n + '.pk3') for n in names], os.path.join(DIST, output))


def main():
    ap = argparse.ArgumentParser(description='Compile packs/ into dist/*.pk3')
    ap.add_argument('only', nargs='*', help='build only packs whose folder name contains one of these words')
    ap.add_argument('--bundle', action='store_true', help=f'also build {CFG["bundle"]["output"]}')
    ap.add_argument('--merged', action='store_true', help=f'also build {CFG["merged"]["output"]}')
    ap.add_argument('--all', action='store_true', help='packs + bundle + merged')
    a = ap.parse_args()
    os.makedirs(DIST, exist_ok=True)
    names = sorted(d for d in os.listdir(PACKS) if os.path.isdir(os.path.join(PACKS, d)))
    if a.only:
        names = [n for n in names if any(w.lower() in n.lower() for w in a.only)]
        if not names: sys.exit('no pack folder matches ' + ' '.join(a.only))
    print(f'{CFG["title"]}: building {len(names)} pack(s) into dist/')
    for n in names: zip_pack(n)
    for key, flag in (('bundle', a.bundle or a.all), ('merged', a.merged or a.all)):
        if not flag: continue
        need = CFG[key]['packs']
        for n in need:
            if not os.path.exists(os.path.join(DIST, n + '.pk3')): zip_pack(n)
        print(f'{key}: {CFG[key]["output"]}')
        merged(need, CFG[key]['output'])
    print('load order: ' + CFG['load'])


if __name__ == '__main__':
    main()
