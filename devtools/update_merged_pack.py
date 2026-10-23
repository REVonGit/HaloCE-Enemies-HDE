#!/usr/bin/env python3
"""Update an already merged Halo CE enemy pk3 with a newer Digsite add-on (or any other pack inside it).

    python3 update_merged_pack.py                     # HaloCE_Merged.pk3 + HaloCE_Enemies_Digsite.pk3 next to this script
    python3 update_merged_pack.py HaloCE_Merged.pk3 HaloCE_Enemies_Digsite.pk3
    python3 update_merged_pack.py HaloCE_Merged.pk3 HaloCE_Enemies_Digsite.pk3 -o New_Merged.pk3

You don't need Core or Covenant again: the old Digsite content is taken out of the merged pk3 and the new one
is merged in. Without -o the merged pk3 is updated in place and the previous one is kept as <name>.bak.pk3.
Needs only Python 3 (standard library) and merge_hce_packs.py in the same folder.

What counts as the old pack's content (the merged pk3 doesn't record file owners, so it is worked out):
  * its section of zscript.txt (`// ---- from <pack>`), the ZScript files that section includes, and its
    sections of concatenated root lumps (cvarinfo.txt, CREDITS.txt ...)
  * root lumps it owns, by extension (modeldef.dig, gldefs.dig, sndinfo.dig ...)
  * asset folders it owns (models/hce_dig, sounds/hce_dig ...): folders the new pack uses that no other pack's
    definition lumps mention, so removed or renamed files don't linger
  * DoomEdNums and event handlers for classes its ZScript defined
"""
import argparse, os, re, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_hce_packs import MergeError, text, merge_mapinfo, CONCAT_EXT   # noqa: E402

DEFAULT_MERGED = 'HaloCE_Merged.pk3'
DEFAULT_NEW = 'HaloCE_Enemies_Digsite.pk3'
STANDALONE_NEW = 'HaloCE_Standalone_Digsite.pk3'
DEF_PREFIX = ('modeldef', 'gldefs', 'sndinfo', 'decorate', 'textures', 'animdefs')


def sections(src):
    """'// ---- from X' sections -> [(name or None for the head, body)]"""
    out, name, buf = [], None, []
    for line in src.split('\n'):
        m = re.match(r'// ---- from (.+?)\s*$', line)
        if m:
            out.append((name, '\n'.join(buf))); name, buf = m.group(1), []
        else:
            buf.append(line)
    out.append((name, '\n'.join(buf)))
    return out


def same_pack(a, b):
    """section owner matches the new pack: same file name, or both are the Digsite add-on (renamed copies)"""
    a, b = os.path.basename(a).lower(), os.path.basename(b).lower()
    return a == b or ('digsite' in a and 'digsite' in b)


def classes_in(zsrc):
    return set(re.findall(r'^\s*class\s+(\w+)', zsrc, re.M | re.I))


def handlers_in(zsrc):
    return set(re.findall(r'^\s*class\s+(\w+)\s*:\s*(?:Static)?EventHandler\b', zsrc, re.M | re.I))


def update(merged_path, new_path, out_path):
    mz, nz = zipfile.ZipFile(merged_path), zipfile.ZipFile(new_path)
    new_name = os.path.basename(new_path)
    files = {i.filename: mz.read(i) for i in mz.infolist() if not i.is_dir()}
    new = {i.filename: nz.read(i) for i in nz.infolist() if not i.is_dir()}
    if 'zscript.txt' not in files or 'Merged by merge_hce_packs.py' not in text(files['zscript.txt']):
        raise MergeError(f'{os.path.basename(merged_path)} was not made by merge_hce_packs.py')

    # ---- zscript.txt: drop the old pack's section, remember what it included
    secs = sections(text(files['zscript.txt']))
    old = [(n, b) for n, b in secs if n and same_pack(n, new_name)]
    if not old:
        raise MergeError(f'no section from {new_name} (or another Digsite pack) in the merged zscript.txt; '
                         'use merge_hce_packs.py to add a pack that was never merged in')
    old_inc = {p for _, b in old for p in re.findall(r'#include\s+"([^"]+)"', b)}
    old_zs = '\n'.join(text(files[p]) for p in old_inc if p in files)
    old_classes, old_handlers = classes_in(old_zs), handlers_in(old_zs)
    removed = set(p for p in old_inc if p in files)

    # ---- root lumps the old pack owned (by the new pack's lump extensions, e.g. .dig)
    new_root = [p for p in new if '/' not in p]
    exts = {os.path.splitext(p)[1].lower() for p in new_root
            if p.lower().split('.')[0] in DEF_PREFIX and os.path.splitext(p)[1].lower() not in ('', '.txt', '.lmp')}
    for p in files:
        if '/' not in p and os.path.splitext(p)[1].lower() in exts: removed.add(p)

    # ---- asset folders the old pack owned: used by the new pack, mentioned by no other pack's definitions
    others = '\n'.join(text(d) for p, d in files.items() if '/' not in p and p not in removed
                       and p.lower().split('.')[0] in DEF_PREFIX).lower()
    owned = set()
    for p in new:
        parts = p.split('/')
        if len(parts) >= 3 and parts[0].lower() in ('models', 'sounds', 'sprites', 'textures', 'graphics', 'music'):
            d = '/'.join(parts[:2])
            if d.lower() + '/' not in others: owned.add(d.lower())
    for p in files:
        if '/' in p and '/'.join(p.split('/')[:2]).lower() in owned: removed.add(p)

    # ---- concatenated root text lumps: replace the old pack's section
    concat = {}
    for p in list(files):
        if '/' in p or p in ('zscript.txt', 'mapinfo.txt') or p in removed: continue
        if os.path.splitext(p.lower())[1] not in CONCAT_EXT: continue
        secs_p = sections(text(files[p]))
        if len(secs_p) > 1:
            kept = [(n, b) for n, b in secs_p[1:] if not same_pack(n, new_name)]
            if len(kept) < len(secs_p) - 1: concat[p] = kept
        elif p in new:
            removed.add(p)                          # single-owner lump that the new pack ships again

    # ---- mapinfo: drop the old classes' DoomEdNums and handlers, then merge the new pack's in
    mi_old = text(files.get('mapinfo.txt', b''))
    mi_old = re.sub(r'^\s*\d+\s*=\s*(\w+)\s*$', lambda m: '' if m.group(1) in old_classes else m.group(0), mi_old, flags=re.M)
    def drop_handlers(m):
        hs = [h for h in re.findall(r'"([^"]+)"', m.group(1)) if h not in old_handlers]
        return ('\tAddEventHandlers = ' + ', '.join(f'"{h}"' for h in hs)) if hs else ''
    mi_old = re.sub(r'^\s*AddEventHandlers\s*=\s*(.*)$', drop_handlers, mi_old, flags=re.M | re.I)
    mi_old = re.sub(r'// from ' + re.escape(new_name) + r'\n[^{]*\{[^}]*\}', '', mi_old)
    parts = [(os.path.basename(merged_path), mi_old)]
    if 'mapinfo.txt' in new: parts.append((new_name, text(new['mapinfo.txt'])))
    mapinfo, nums, handlers = merge_mapinfo(parts)

    # ---- assemble
    out = {p: d for p, d in files.items() if p not in removed}
    for p, d in new.items():
        if p in ('zscript.txt', 'mapinfo.txt'): continue
        if '/' not in p and p in concat:
            out[p] = '\n'.join(f'// ---- from {n}\n{b.strip()}\n' for n, b in concat[p] + [(new_name, text(d))]).encode()
            continue
        if p in out and out[p] != d:
            raise MergeError(f'{p} differs between the merged pack and {new_name} and is not the add-on\'s own file')
        out[p] = d
    for p, kept in concat.items():
        if p not in new: out[p] = '\n'.join(f'// ---- from {n}\n{b.strip()}\n' for n, b in kept).encode()
    head = secs[0][1].rstrip('\n')
    nz_src = re.sub(r'^\s*version\s+"[\d.]+"\s*\n', '', text(new.get('zscript.txt', b'')), count=1, flags=re.M).strip('\n')
    body = [f'// ---- from {n}\n{b.strip(chr(10))}\n' for n, b in secs[1:] if not same_pack(n, new_name)]
    body.append(f'// ---- from {new_name}\n{nz_src}\n')
    vm = re.search(r'^\s*version\s+"([\d.]+)"', text(new.get('zscript.txt', b'')), re.M)
    if vm:
        hv = re.search(r'^\s*version\s+"([\d.]+)"', head, re.M)
        if hv and tuple(map(int, vm.group(1).split('.'))) > tuple(map(int, hv.group(1).split('.'))):
            head = head.replace(hv.group(0), f'version "{vm.group(1)}"')
    out['zscript.txt'] = (head + '\n\n' + '\n'.join(body)).encode()
    out['mapinfo.txt'] = mapinfo.encode()

    tmp = out_path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(out, key=lambda p: (p.count('/'), p.lower())):
            z.writestr(p, out[p])
    mz.close(); nz.close()
    if os.path.abspath(out_path) == os.path.abspath(merged_path):
        bak = os.path.splitext(merged_path)[0] + '.bak.pk3'
        shutil.copy2(merged_path, bak)
        print(f'previous merged pack kept as {os.path.basename(bak)}')
    os.replace(tmp, out_path)
    gone = sorted(p for p in removed if p not in new)
    print(f'replaced {old[0][0]} with {new_name}: {len(removed)} old files out, {len(new)} new files in'
          + (f' ({len(gone)} no longer shipped)' if gone else ''))
    print(f'  -> {out_path}: {len(out)} files, {nums} DoomEdNums, handlers {", ".join(handlers) or "none"}, '
          f'{os.path.getsize(out_path) / 1e6:.1f} MB')


def main():
    ap = argparse.ArgumentParser(description='Swap a newer Digsite add-on (or other pack) into a merged Halo CE enemy pk3.')
    ap.add_argument('merged', nargs='?', default=os.path.join(HERE, DEFAULT_MERGED), help='merged pk3 (default HaloCE_Merged.pk3)')
    ap.add_argument('new', nargs='?', default=os.path.join(HERE, DEFAULT_NEW), help='new pack (default HaloCE_Enemies_Digsite.pk3)')
    ap.add_argument('-o', '--output', default=None, help='write here instead of updating the merged pk3 in place')
    a = ap.parse_args()
    if a.new == os.path.join(HERE, DEFAULT_NEW) and not os.path.isfile(a.new) and os.path.isfile(os.path.join(HERE, STANDALONE_NEW)):
        a.new = os.path.join(HERE, STANDALONE_NEW)          # standalone set
    for p in (a.merged, a.new):
        if not os.path.isfile(p): sys.exit(f'not found: {p}')
    try:
        update(a.merged, a.new, a.output or a.merged)
    except (MergeError, zipfile.BadZipFile) as e:
        sys.exit(f'update failed: {e}')


if __name__ == '__main__':
    main()
