#!/usr/bin/env python3
"""Make the bundle pk3: the Covenant pack (Digsite included) and the voices, plus the enemy API and the parts of
Core they use, in one pk3. Nothing in packs/ is changed: the bundle is put together at build time.

    python tools/make_bundle.py                 # -> dist/<name>.pk3   (build_bundle.py calls this)
    python tools/make_bundle.py --dry-run       # only report which Core sounds / sprites / models are left out

repo.json:
  "bundle": {"name": "HaloCE_HDE_Bundle",
             "merge": ["HaloCE_Covenant", "HaloCE_Enemies_Voices"],
             "api":   ["HCE_EnemyAPI_LocalDEV"],
             "core":  "HaloCE_Core"}

  1. the "merge" packs are merged (same rules as merge_hce_packs.py)
  2. the "api" packs are added whole
  3. Core goes in with all of its ZScript (the replacement handler, enemy base, loot handler and projectile
     library are shared code), but of its sounds, sprites and models only what the bundled enemies reach.
What is "reached": start from every class the merged packs define plus Core's handler / API / loot code, follow
every class name mentioned in those classes (parents, Spawn / Fire calls, names in strings) through Core's
library, then keep the sounds, sprites, models and GLDEFS entries those classes name.
"""
import argparse, io, json, os, re, shutil, sys, tempfile, zipfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACKS = os.path.join(ROOT, 'packs')
sys.path.insert(0, HERE)
from merge_hce_packs import merge  # noqa: E402

ALWAYS_CORE = ('hce_handler.zsc', 'hces_api.zsc', 'hces_loot.zsc')   # code that is the root of everything
SPRITE_RE = re.compile(r'\b([A-Z0-9]{4})\b')


def read_tree(d):
    out = {}
    for root, dirs, fs in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith('.git')]
        for f in fs:
            p = os.path.join(root, f)
            out[os.path.relpath(p, d).replace(os.sep, '/')] = Path(p).read_bytes()
    return out


def zip_tree(files, path):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        for n, d in sorted(files.items()): z.writestr(n, d)


def txt(b): return b.decode('utf-8', 'replace')


def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def blocks(src, kw):
    """top-level '<kw> Name ... { body }' blocks -> [(name, start, end, header+body)]"""
    out, pat = [], re.compile(r'^(?:extend\s+)?' + kw + r'\s+(\w+)', re.M | re.I)
    for m in pat.finditer(src):
        j = src.find('{', m.end())
        if j < 0: continue
        depth, k = 0, j
        while k < len(src):
            c = src[k]
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: break
            k += 1
        out.append((m.group(1), m.start(), k + 1, src[m.start():k + 1]))
    return out


def plan(core, merged_code, extra_text):
    """-> (reached classes, needed sound names, needed sprite names, report)"""
    classes = {}                                        # core class / mixin / struct -> code
    root_code = [merged_code]
    for path, data in core.items():
        if not path.lower().endswith('.zsc'): continue
        src = strip_comments(txt(data))
        if os.path.basename(path).lower() in ALWAYS_CORE:
            root_code.append(src)
        for kw in ('class', r'mixin\s+class', 'struct'):
            for name, _, _, body in blocks(src, kw):
                classes.setdefault(name.lower(), body)
    names = set(classes)
    word = re.compile(r'\b(\w+)\b')
    reached, todo = set(), []

    def visit(code):
        for w in set(x.lower() for x in word.findall(code)):
            if w in names and w not in reached:
                reached.add(w); todo.append(w)
    for c in root_code: visit(c)
    while todo: visit(classes[todo.pop()])
    live = '\n'.join(root_code + [classes[c] for c in reached] + [extra_text])
    return reached, live


def sndinfo_needed(sources, live):
    """sndinfo texts -> (needed logical names, needed lump files) by following $random / $alias from what code names"""
    defs, groups, lines = {}, {}, []
    for text in sources:
        for line in text.splitlines():
            s = line.strip()
            m = re.match(r'(\$random|\$alias)\s+(\S+)\s*(.*)', s, re.I)
            if m:
                refs = re.findall(r'[\w/.\-]+', m.group(3).strip('{} '))
                groups.setdefault(m.group(2).lower(), []).extend(r.lower() for r in refs)
                continue
            m = re.match(r'([^\s$/][^\s]*)\s+"([^"]+)"', s)
            if m: defs[m.group(1).lower()] = m.group(2)
    strings = set(x.lower() for x in re.findall(r'"([^"\n]*)"', live))
    strings |= set(x.lower() for x in re.findall(r"'([^'\n]*)'", live))
    want, todo = set(), [s for s in strings if s in defs or s in groups]
    while todo:
        n = todo.pop()
        if n in want: continue
        want.add(n)
        todo.extend(groups.get(n, []))
    return want, {defs[n].lower() for n in want if n in defs}


def prune_sndinfo(text, want):
    out = []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r'\$(random|alias|volume|limit|attenuation|pitchshift|rolloff)\s+(\S+)', s, re.I)
        if m:
            if m.group(2).lower() in want: out.append(line)
            continue
        m = re.match(r'([^\s$/][^\s]*)\s+"([^"]+)"', s)
        if m:
            if m.group(1).lower() in want: out.append(line)
            continue
        out.append(line)                                 # comments, blank lines
    return '\n'.join(out).rstrip() + '\n'


def prune_blocks(text, kw, keep):
    """drop top-level '<kw> Class {...}' blocks whose class isn't kept; -> (text, dropped names)"""
    dropped, pieces, last = [], [], 0
    for name, a, b, _ in blocks(text, kw):
        if name.lower() in keep: continue
        pieces.append(text[last:a]); last = b; dropped.append(name)
    pieces.append(text[last:])
    return re.sub(r'\n{3,}', '\n\n', ''.join(pieces)).strip() + '\n', dropped


def bundle_files(cfg, packs_dir=PACKS, log=print):
    """{path in pk3: bytes} of the bundle described by cfg (repo.json "bundle")"""
    for p in cfg['merge'] + cfg.get('api', []) + [cfg['core']]:
        if not os.path.isdir(os.path.join(packs_dir, p)): sys.exit(f'packs/{p} is missing')
    core = read_tree(os.path.join(packs_dir, cfg['core']))
    with tempfile.TemporaryDirectory() as tmp:
        ins = []
        for p in cfg['merge']:
            zp = os.path.join(tmp, p + '.pk3'); zip_tree(read_tree(os.path.join(packs_dir, p)), zp); ins.append(zp)
        merged_pk3 = os.path.join(tmp, 'merged.pk3')
        merge(ins, merged_pk3, quiet=True)
        with zipfile.ZipFile(merged_pk3) as mz:              # closed before the temp folder goes (Windows)
            merged = {i.filename: mz.read(i) for i in mz.infolist() if not i.is_dir()}
    api = {}
    for p in cfg.get('api', []): api.update(read_tree(os.path.join(packs_dir, p)))

    merged_code = '\n'.join(strip_comments(txt(d)) for n, d in {**merged, **api}.items() if n.lower().endswith('.zsc'))
    # text in the merged packs that can name core sounds / classes (sndinfo aliases, gldefs, modeldef, mapinfo)
    extra = '\n'.join(txt(d) for n, d in merged.items() if '/' not in n and not n.lower().endswith('.zsc'))
    reached, live = plan(core, merged_code, extra)

    # sounds
    snd_files = [n for n in core if n.lower().startswith('sndinfo')]
    want_snd, want_lumps = sndinfo_needed([txt(core[n]) for n in snd_files] +
                                          [txt(d) for n, d in merged.items() if n.lower().startswith('sndinfo')], live)
    # model / gldefs objects for classes that are reached (or defined by the merged packs)
    merged_classes = {n.lower() for n in re.findall(r'^\s*class\s+(\w+)', merged_code, re.M | re.I)}
    keep_cls = reached | merged_classes
    new_core, dropped = {}, {'sounds': [], 'sprites': [], 'models': [], 'modeldef': [], 'gldefs': [], 'sndinfo': 0}
    for n, d in core.items():
        low = n.lower()
        if low.startswith('modeldef'):
            t, gone = prune_blocks(txt(d), 'model', keep_cls); dropped['modeldef'] += gone; new_core[n] = t.encode()
        elif low.startswith('gldefs') and 'lights' not in low:
            t, gone = prune_blocks(txt(d), 'object', keep_cls); dropped['gldefs'] += gone; new_core[n] = t.encode()
        elif low.startswith('sndinfo'):
            t = prune_sndinfo(txt(d), want_snd)
            dropped['sndinfo'] += txt(d).count('\n') - t.count('\n'); new_core[n] = t.encode()
        else:
            new_core[n] = d
    # sprites and models named by what is left
    keep_text = live + '\n'.join(txt(new_core[n]) for n in new_core if '/' not in n)
    sprite_names = set(SPRITE_RE.findall(keep_text))
    model_refs = set(x.lower() for x in re.findall(r'"([^"]+\.(?:md3|iqm|md2|obj|png|tga|jpg|dmx))"', keep_text, re.I))
    for n in list(new_core):
        low = n.lower()
        if low.startswith('sounds/') and low not in want_lumps:
            dropped['sounds'].append(n); del new_core[n]
        elif low.startswith('sprites/') and os.path.basename(n)[:4].upper() not in sprite_names:
            dropped['sprites'].append(n); del new_core[n]
        elif low.startswith('models/') and os.path.basename(low) not in model_refs:
            dropped['models'].append(n); del new_core[n]
    for n in [n for n in new_core if n.lower().startswith('sndinfo') or n.lower().startswith('modeldef')
              or n.lower().startswith('gldefs')]:
        body = re.sub(r'//[^\n]*', '', txt(new_core[n])).strip()
        if not body: del new_core[n]

    if log:
        log(f'  Core classes the bundle reaches: {len(reached)}; left out of Core: ' +
            ', '.join(f'{len(dropped[k])} {k}' for k in ('sounds', 'sprites', 'models')) +
            f', {len(dropped["modeldef"])} modeldef / {len(dropped["gldefs"])} gldefs entries, {dropped["sndinfo"]} sndinfo lines')

    # merge Core + API + merged packs exactly like merge_hce_packs (Core first, so its handler & includes lead)
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for name, files in (('core', new_core), ('api', api), ('merged', merged)):
            if not files: continue
            zp = os.path.join(tmp, f'{name}.pk3'); zip_tree(files, zp); parts.append(zp)
        final = os.path.join(tmp, 'bundle.pk3')
        merge(parts, final, quiet=True)
        with zipfile.ZipFile(final) as z:                   # closed before the temp folder goes (Windows)
            for info in z.infolist():
                if info.is_dir(): continue
                data = z.read(info)
                if info.filename == 'zscript.txt':     # one header (repo.json "header") over the #includes, in load order
                    src = data.decode()
                    ver = re.search(r'^version\s+"[\d.]+"', src, re.M)
                    head = cfg.get('header') or [f'// {cfg["name"]}: ' + ' + '.join(cfg['merge'] + cfg.get('api', [])) + ' + Core code']
                    data = ((ver.group(0) + '\n\n' if ver else '') + '\n'.join(head) + '\n\n' +
                            '\n'.join(re.findall(r'^#include.*$', src, re.M)) + '\n').encode()
                out[info.filename] = data
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dry-run', action='store_true', help='only report what is left out of Core')
    a = ap.parse_args()
    cfg = json.loads(Path(os.path.join(ROOT, 'repo.json')).read_text(encoding='utf-8'))['bundle']
    files = bundle_files(cfg)
    if a.dry_run: return
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    out = os.path.join(ROOT, 'dist', cfg['name'] + '.pk3')
    zip_tree(files, out)
    print(f'  {cfg["name"]}.pk3  {len(files)} files  {os.path.getsize(out) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
