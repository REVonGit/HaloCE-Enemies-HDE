#!/usr/bin/env python3
"""Merge Halo CE enemy pk3s (core, faction packs, Digsite/SPV3 add-on) into one pk3.

    python3 merge_hce_packs.py                       # merges Core + Covenant + Digsite found next to this script
                                                     # (or the HaloCE_Standalone_* set if that's what is there)
    python3 merge_hce_packs.py -o Mine.pk3 HaloCE_Core.pk3 HaloCE_Covenant.pk3 HaloCE_Enemies_Digsite.pk3

Needs only Python 3 (standard library). Load the result exactly where the separate packs went:
    HDE (Local_DEV) -> HCE_EnemyAPI_LocalDEV.pk3 -> <merged pk3> -> HaloCE_Enemies_Voices.pk3 (optional)
    standalone packs: <merged pk3> -> HaloCE_Enemies_Voices.pk3 (optional), with any other mods

How files are combined:
  * zscript.txt     one root lump: the highest `version`, then every pack's #includes in load order
  * mapinfo.txt     one DoomEdNums block (a number used twice for different classes is an error),
                    one GameInfo with every pack's AddEventHandlers in load order, other blocks kept as-is
  * cvarinfo, CREDITS and other root text lumps of the same name: concatenated, one section per pack
  * a #include already made by an earlier pack is dropped (a bundle carries Core's code; Core may be merged too)
  * a root lump in two packs where one holds every line of the other (Core's sndinfo vs a bundle's trimmed
    copy): the fuller one is kept
  * everything else (models, sounds, ZScript sources, modeldef.*/gldefs.*/sndinfo.*): copied; a path present
    in two packs must be byte-identical, otherwise the merge stops and names the file
Packs are ordered core first (the one carrying hce_handler.zsc), then the rest in the order given.
"""
import argparse, os, re, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUTS = ['HaloCE_Core.pk3', 'HaloCE_Covenant.pk3', 'HaloCE_Enemies_Digsite.pk3']
STANDALONE_INPUTS = ['HaloCE_Standalone_Core.pk3', 'HaloCE_Standalone_Covenant.pk3', 'HaloCE_Standalone_Digsite.pk3']
SPECIAL = {'zscript.txt', 'mapinfo.txt'}
CONCAT_EXT = ('.txt', '.lmp', '')
STORE = ('.ogg', '.png', '.jpg', '.jpeg', '.flac', '.mp3')        # root lumps of these kinds that collide get concatenated


class MergeError(Exception):
    pass


def text(data):
    return data.decode('utf-8', 'replace').replace('\r\n', '\n')


def top_blocks(src):
    """mapinfo text -> [(header, body)] for each top-level `Header { ... }` block (comments kept in bodies)"""
    out, i, n = [], 0, len(src)
    while i < n:
        j = src.find('{', i)
        if j < 0: break
        header = src[i:j].strip()
        header = '\n'.join(l for l in header.split('\n') if not l.strip().startswith('//')).strip()
        depth, k = 0, j
        while k < n:
            if src[k] == '{': depth += 1
            elif src[k] == '}':
                depth -= 1
                if depth == 0: break
            k += 1
        out.append((header, src[j + 1:k]))
        i = k + 1
    return out


def merge_zscript(parts):
    versions, body, seen = [], [], set()
    for name, src in parts:
        m = re.search(r'^\s*version\s+"([\d.]+)"', src, re.M)
        if m: versions.append(tuple(int(x) for x in m.group(1).split('.')))
        rest = re.sub(r'^\s*version\s+"[\d.]+"\s*\n', '', src, count=1, flags=re.M).strip('\n')
        keep = []                              # a file #included by an earlier pack (Core inside a bundle) only once
        for line in rest.split('\n'):
            m = re.match(r'\s*#include\s+"([^"]+)"', line)
            if m:
                if m.group(1).lower() in seen: continue
                seen.add(m.group(1).lower())
            keep.append(line)
        rest = '\n'.join(keep)
        body.append(f'// ---- from {name}\n{rest}\n')
    head = f'version "{".".join(map(str, max(versions)))}"\n\n' if versions else ''
    return head + '// Merged by merge_hce_packs.py\n\n' + '\n'.join(body)


def merge_mapinfo(parts):
    ednums, handlers, other = {}, [], []
    for name, src in parts:
        for header, body in top_blocks(src):
            key = header.lower()
            if key == 'doomednums':
                for num, cls in re.findall(r'^\s*(\d+)\s*=\s*(\w+)', body, re.M):
                    num = int(num)
                    if num in ednums and ednums[num][0].lower() != cls.lower():
                        raise MergeError(f'DoomEdNum {num} is {ednums[num][0]} in {ednums[num][1]} '
                                         f'but {cls} in {name}')
                    ednums.setdefault(num, (cls, name))
            elif key == 'gameinfo':
                for line in body.split('\n'):
                    m = re.match(r'\s*AddEventHandlers\s*=\s*(.*)', line, re.I)
                    if m:
                        for h in re.findall(r'"([^"]+)"', m.group(1)):
                            if h not in handlers: handlers.append(h)
                    elif line.strip() and not line.strip().startswith('//'):
                        other.append((name, 'GameInfo', line.strip()))
            else:
                other.append((name, header, body))
    out = ['// Merged by merge_hce_packs.py']
    if ednums:
        out.append('DoomEdNums\n{\n' + ''.join(f'\t{n} = {c}\n' for n, (c, _) in sorted(ednums.items())) + '}')
    gi = [l for (_, h, l) in other if h == 'GameInfo']
    if handlers or gi:
        lines = ([f'\tAddEventHandlers = {", ".join(chr(34) + h + chr(34) for h in handlers)}'] if handlers else []) + \
                [f'\t{l}' for l in gi]
        out.append('GameInfo\n{\n' + '\n'.join(lines) + '\n}')
    for name, header, body in other:
        if header == 'GameInfo': continue
        out.append(f'// from {name}\n{header}\n{{{body}}}')
    return '\n\n'.join(out) + '\n', len(ednums), handlers


def superset(a, b):
    """two versions of a root text lump: the one that holds every line of the other, or None"""
    la = {l.strip() for l in text(a).split('\n') if l.strip() and not l.strip().startswith('//')}
    lb = {l.strip() for l in text(b).split('\n') if l.strip() and not l.strip().startswith('//')}
    if la <= lb: return b
    if lb <= la: return a
    return None


def pack_kind(z):
    """'standalone' (HCES_EnemyBase, no HDE needed), 'hde' (needs HDE + HCE_EnemyAPI) or None (voices etc.)"""
    for n in z.namelist():
        if not n.lower().endswith('.zsc'): continue
        t = z.read(n).decode('utf-8', 'replace')
        if 'HCES_EnemyBase' in t or n.lower().endswith('hces_lib.zsc'): return 'standalone'
        if 'HaloDoom_EnemyBase' in t: return 'hde'
    return None


def merge(inputs, output, quiet=False):
    zips = []
    for p in inputs:
        if not os.path.isfile(p): raise MergeError(f'not found: {p}')
        zips.append((os.path.basename(p), zipfile.ZipFile(p)))
    kinds = {n: pack_kind(z) for n, z in zips}
    if 'standalone' in kinds.values() and 'hde' in kinds.values():
        raise MergeError('standalone and HDE packs can\'t be merged together (they define the same enemies): '
                         'standalone ' + ', '.join(n for n, k in kinds.items() if k == 'standalone') +
                         '; HDE ' + ', '.join(n for n, k in kinds.items() if k == 'hde'))
    # core first, the rest in the order given
    zips.sort(key=lambda nz: 0 if any(n.lower().endswith('hce_handler.zsc') for n in nz[1].namelist()) else 1)
    files, sources, special = {}, {}, {k: [] for k in SPECIAL}
    concat = {}
    for name, z in zips:
        for info in z.infolist():
            if info.is_dir(): continue
            path = info.filename
            low = path.lower()
            data = z.read(info)
            if low in SPECIAL:
                special[low].append((name, text(data))); continue
            if path in files:
                if files[path] == data: continue
                if '/' not in path and low not in SPECIAL:
                    sup = superset(files[path], data)    # Core's file vs a bundle's copy of it (all of it or a part)
                    if sup is not None:
                        files[path] = sup; continue
                root = '/' not in path and os.path.splitext(low)[1] in CONCAT_EXT
                if root:
                    concat.setdefault(path, [(sources[path], files[path])]).append((name, data)); continue
                raise MergeError(f'{path} differs between {sources[path]} and {name}')
            files[path], sources[path] = data, name
    for path, chunks in concat.items():        # cvarinfo.txt, CREDITS.txt ...
        files[path] = '\n'.join(f'// ---- from {n}\n{text(d).strip()}\n' for n, d in chunks).encode()
    if special['zscript.txt']: files['zscript.txt'] = merge_zscript(special['zscript.txt']).encode()
    nums, handlers = 0, []
    if special['mapinfo.txt']:
        mi, nums, handlers = merge_mapinfo(special['mapinfo.txt'])
        files['mapinfo.txt'] = mi.encode()
    tmp = output + '.tmp'
    with zipfile.ZipFile(tmp, 'w') as out:
        for path in sorted(files, key=lambda p: (p.count('/'), p.lower())):
            info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))   # byte-stable output
            info.external_attr = 0o644 << 16
            stored = path.lower().endswith(STORE)                          # sounds/images are compressed already
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            out.writestr(info, files[path], compresslevel=None if stored else 9)
    os.replace(tmp, output)
    if quiet: return
    print(f'merged {", ".join(n for n, _ in zips)}')
    print(f'  -> {output}: {len(files)} files, {nums} DoomEdNums, handlers {", ".join(handlers) or "none"}, '
          f'{os.path.getsize(output) / 1e6:.1f} MB')


def main():
    ap = argparse.ArgumentParser(description='Merge Halo CE enemy pk3s into one.')
    ap.add_argument('inputs', nargs='*', help='pk3s to merge (default: Core, Covenant and Digsite next to this script)')
    ap.add_argument('-o', '--output', default=None, help='output pk3 (default: HaloCE_Merged.pk3 next to the first input)')
    a = ap.parse_args()
    inputs = a.inputs or [os.path.join(HERE, f) for f in DEFAULT_INPUTS]
    if not a.inputs and not all(os.path.isfile(p) for p in inputs):
        sa = [os.path.join(HERE, f) for f in STANDALONE_INPUTS]      # the standalone set, if that's what's here
        if all(os.path.isfile(p) for p in sa): inputs = sa
    output = a.output or os.path.join(os.path.dirname(os.path.abspath(inputs[0])), 'HaloCE_Merged.pk3')
    if os.path.abspath(output) in map(os.path.abspath, inputs): sys.exit('output would overwrite an input')
    try:
        merge(inputs, output)
    except (MergeError, zipfile.BadZipFile) as e:
        sys.exit(f'merge failed: {e}')


if __name__ == '__main__':
    main()
