"""Hidden model surfaces cost nothing: drop the MODELDEF lines that hide a surface behind the transparent skin.

A model surface whose MODELDEF line is 'SurfaceSkin m s "hce_hidden.png"' is still drawn every frame (UZDoom's
IQMModel::RenderFrame sends it to the GPU with the see-through texture: its triangles, its bones, a draw call). With no
SurfaceSkin line at all the engine falls back to the IQM's own material for that mesh, and when that name is no file
in the model's folder (LoadSkin finds nothing), it skips the mesh entirely. Every body carries every gun its kind can
hold, the spare armour variants and the gore pieces, so most of each model is such hidden surfaces.

prune(pack) rewrites each modeldef.* in the pack folder without those lines, keeping a line when the mesh's material
would resolve (it would then be drawn, textured) or when the block gives that model a whole-model Skin (which the
engine draws in place of the surface skins). The visible result is the same: a surface the ZScript shows at run time
(A_ChangeModel ... CMDL_USESURFACESKIN) is drawn with the skin it sets; one it hides again with hce_hidden.png is drawn
see-through as before; setting 'None' falls back to the MODELDEF line, now absent: skipped, as hidden as it was."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HIDDEN = 'hce_hidden.png'
_mats = {}


def materials(path):
    """IQM file -> [mesh material] (cached)"""
    if path not in _mats:
        from iqm import read_iqm
        try:
            _mats[path] = [m['material'] for m in read_iqm(path)[1]]
        except Exception:
            _mats[path] = None
    return _mats[path]


def _exists(pack, rel):
    """rel (a path in the pack, any case) is a file"""
    d = pack
    for part in rel.replace('\\', '/').split('/'):
        if not os.path.isdir(d): return False
        low = {n.lower(): n for n in os.listdir(d)}
        if part.lower() not in low: return False
        d = os.path.join(d, low[part.lower()])
    return os.path.isfile(d)


def prune_block(pack, b):
    """one MODELDEF block -> (its text without the droppable hidden-surface lines, {model index: surfaces the engine
    skips: no SurfaceSkin line left and a material that is no file}, {model index: its folder})"""
    lines = b.split('\n')
    path, model_file, skinned = '', {}, set()
    for line in lines:
        m = re.match(r'\s*Path\s+"([^"]*)"', line)
        if m: path = m.group(1); continue
        m = re.match(r'\s*Model\s+(\d+)\s+"([^"]*)"', line)
        if m: model_file[int(m.group(1))] = (path, m.group(2)); continue
        m = re.match(r'\s*Skin\s+(\d+)\s+"([^"]*)"', line)
        if m and m.group(2): skinned.add(int(m.group(1)))

    def mats_of(mi):
        mp, mf = model_file[mi]
        return materials(os.path.join(pack, mp, mf)) if mf.lower().endswith('.iqm') else None

    keep, lined = [], {}
    for line in lines:
        m = re.match(r'\s*SurfaceSkin\s+(\d+)\s+(\d+)\s+"([^"]*)"', line)
        if m and int(m.group(1)) in model_file:
            mi, si = int(m.group(1)), int(m.group(2))
            if os.path.basename(m.group(3)).lower() == HIDDEN and mi not in skinned:
                mats = mats_of(mi)
                if mats is not None and (si >= len(mats) or not _exists(pack, f'{model_file[mi][0]}/{mats[si]}')):
                    continue
            lined.setdefault(mi, set()).add(si)
        keep.append(line)
    skipped = {}
    for mi, (mp, mf) in model_file.items():
        if mi in skinned: continue
        mats = mats_of(mi)
        if mats is None: continue
        skipped[mi] = {si for si, mt in enumerate(mats) if si not in lined.get(mi, set()) and not _exists(pack, f'{mp}/{mt}')}
    return '\n'.join(keep), skipped, {mi: mp for mi, (mp, _) in model_file.items()}


def prune_text(pack, txt):
    """one modeldef's text -> (pruned text, lines dropped)"""
    out = [prune_block(pack, b)[0] for b in re.split(r'(?m)^(?=Model\s+\w+\s*$)', txt)]
    new = ''.join(out)
    return new, txt.count('\n') - new.count('\n')


# the run-time hide of a body surface, as the generator and templates write it (model 0, the see-through skin):
# routed through the class's HCE_HideSurface, which knows the surfaces its MODELDEF leaves undrawn; and the run-time
# show back to the MODELDEF's skin ('None'): routed through HCE_ShowSurface, which gives the dressed surfaces theirs
HIDE_CALL = re.compile(r"(?<![\w.])A_ChangeModel\('None', 0, \"\", 'None', ([^,()]+), \"[^\"]*\", 'hce_hidden\.png', CMDL_USESURFACESKIN\)")
SHOW_CALL = re.compile(r"(?<![\w.])A_ChangeModel\('None', 0, \"\", 'None', ([^,()]+), \"[^\"]*\", 'None', CMDL_USESURFACESKIN\)")
ENEMY_ROOTS = ('HaloDoom_EnemyBase', 'HCES_EnemyBase')
# the dressing: functions that hide body surfaces as an enemy spawns (Grunt backs, the Marine kit, the Brute kit, a
# Halo 2 body over the CE one, the Flood's damaged parts until a limb comes off), and the gun's (hidden when it dies
# or throws it away: so a corpse's gun is skipped, not drawn see-through for as long as the corpse lies there)
SHIELD_SURFACE_DEFAULT = 5          # the API's HCE_ShieldSurface() (the CE Jackal's)
DRESS_FUNCS = r'PostBeginPlay|HCE_DressMarine|HCE_DressArmour|HCE_ShowGun|HCE_HideWeaponSurfaces'


def _classes(text):
    """[(class name, its text)] of the top-level classes in ZScript text"""
    parts = re.split(r'(?m)^(?=(?:mixin\s+|extend\s+)?class\s+\w+|struct\s|enum\s)', text)
    return parts, [(m.group(1) if m else None) for m in (re.match(r'class\s+(\w+)', p) for p in parts)]


def _dressed(text):
    """surfaces a class's spawn dressing may hide: every number in its dressing functions' int arrays and literal hides"""
    out = set()
    for fm in re.finditer(r'(?m)^\t(?:override\s+)?void\s+(?:' + DRESS_FUNCS + r')\s*\([^)]*\)\s*\n\t\{(.*?)\n\t\}', text, re.S):
        body = fm.group(1)
        if 'HCE_HideSurface' not in body and 'hce_hidden' not in body: continue
        for arr in re.findall(r'static\s+const\s+int\s+\w+\s*\[\s*\]\s*=\s*\{([^}]*)\}', body):
            out |= {int(x) for x in re.findall(r'\d+', arr)}
        out |= {int(x) for x in re.findall(r'HCE_HideSurface\((\d+)\)', body)}
        out |= {int(x) for x in re.findall(r"A_ChangeModel\('None', 0, \"\", 'None', (\d+), \"[^\"]*\", 'hce_hidden\.png'", body)}
    # a Jackal's energy shield: hidden by its shield actor while it's down (hce_core.zsc, through HCE_HideSurface)
    if re.search(r'\+\s*HaloDoom_EnemyBase\.HCE_FrontShield|\+\s*HCES_EnemyBase\.HCE_FrontShield', text, re.I):
        sh = re.findall(r'override\s+int\s+HCE_ShieldSurface\(\)\s*\{\s*return\s+(\d+)', text)
        out |= {int(x) for x in sh} if sh else {SHIELD_SURFACE_DEFAULT}
    return out


def apply(pack, md_text, zs_text, other_zs=''):
    """the whole pass for a pack being built: (pruned MODELDEF text, ZScript with each enemy class's overrides).
    Each enemy class with a MODELDEF block:
      - the surfaces its spawn dressing may hide leave its MODELDEF; HCE_DressSurfaces gives them their skins as it
        spawns (BeginPlay), so the dressing's hides set them back to undrawn
      - HCE_HideSurface: those and the surfaces its MODELDEF leaves out -> 'None' (skipped); the rest see-through
      - HCE_ShowSurface: the dressed surfaces their skins; the rest back to the MODELDEF ('None')
    and its own body hides / shows are routed through them. other_zs: the rest of the ZScript the classes derive from
    (the main pack's, the API's), to tell which classes are enemies and what their parents dress"""
    parent = {a.lower(): b.lower() for a, b in re.findall(r'(?m)^\s*class\s+(\w+)\s*:\s*(\w+)', zs_text + '\n' + other_zs)}
    dress = {}
    for text in (other_zs, zs_text):
        ps, ns = _classes(text)
        for p, n in zip(ps, ns):
            if n: dress[n.lower()] = dress.get(n.lower(), set()) | _dressed(p)

    def chain(c):
        seen = []
        while c and c not in seen: seen.append(c); c = parent.get(c)
        return seen

    def enemy(c): return any(x in (r.lower() for r in ENEMY_ROOTS) for x in chain(c))

    def dress_of(c): return set().union(*(dress.get(x, set()) for x in chain(c)))

    out, info = [], {}
    dropped = 0
    for b in re.split(r'(?m)^(?=Model\s+\w+\s*$)', md_text):
        m = re.match(r'Model\s+(\w+)', b)
        table = {}
        if m and enemy(m.group(1).lower()):
            want = dress_of(m.group(1).lower())
            if want:
                keep, path = [], ''
                for line in b.split('\n'):
                    pm = re.match(r'\s*Path\s+"([^"]*)"', line)
                    if pm: path = pm.group(1)
                    sm = re.match(r'\s*SurfaceSkin\s+0\s+(\d+)\s+"([^"]*)"', line)
                    if sm and int(sm.group(1)) in want and os.path.basename(sm.group(2)).lower() != HIDDEN:
                        table[int(sm.group(1))] = (path, sm.group(2)); continue
                    keep.append(line)
                b = '\n'.join(keep)
        nb, skipped, dirs = prune_block(pack, b)
        dropped += b.count('\n') - nb.count('\n')
        out.append(nb)
        if m:
            info[m.group(1).lower()] = (sorted(skipped.get(0, ())), table, dirs.get(0) or 'models/hce/x')

    parts, names = _classes(zs_text)
    n_cls = n_hide = n_show = n_dress = 0
    for i, (part, n) in enumerate(zip(parts, names)):
        if not n or not enemy(n.lower()): continue
        part, k = HIDE_CALL.subn(r'HCE_HideSurface(\1)', part); n_hide += k
        part, k = SHOW_CALL.subn(r'HCE_ShowSurface(\1)', part); n_show += k
        if n.lower() in info:
            sk, table, mdir_path = info[n.lower()]
            wdir = os.path.dirname(mdir_path) + '/weapons'
            undrawn = sorted(set(sk) | set(table))
            arr = (f'\t\tstatic const int K[] = {{ {", ".join(map(str, undrawn))} }};\n'
                   '\t\tfor(int i = 0; i < K.Size(); i++) if(K[i] == s) { A_ChangeModel(\'None\', 0, "", \'None\', s, "", \'None\', CMDL_USESURFACESKIN); return; }\n'
                   if undrawn else '')
            body = ('\t// lib/modeldef_prune.py: the surfaces this class\'s MODELDEF leaves undrawn are hidden by setting them back\n'
                    '\t// to it (the engine skips them); the ones its spawn dressing may hide get their skins here as it spawns\n'
                    '\toverride void HCE_HideSurface(int s)\n\t{\n' + arr +
                    f'\t\tA_ChangeModel(\'None\', 0, "", \'None\', s, "{wdir}", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n\t}}\n')
            if table:
                cases = ''.join(f'\t\tcase {s}: A_ChangeModel(\'None\', 0, "", \'None\', {s}, "{p}", \'{f}\', CMDL_USESURFACESKIN); return;\n'
                                for s, (p, f) in sorted(table.items()))
                body += ('\toverride void HCE_ShowSurface(int s)\n\t{\n\t\tswitch(s)\n\t\t{\n' + cases + '\t\t}\n'
                         '\t\tA_ChangeModel(\'None\', 0, "", \'None\', s, "", \'None\', CMDL_USESURFACESKIN);\n\t}\n'
                         '\toverride void HCE_DressSurfaces()\n\t{\n'
                         + ''.join(f'\t\tA_ChangeModel(\'None\', 0, "", \'None\', {s}, "{p}", \'{f}\', CMDL_USESURFACESKIN);\n'
                                   for s, (p, f) in sorted(table.items())) + '\t}\n')
                n_dress += 1
            part = part.replace('{', '{\n' + body, 1)
            n_cls += 1
        parts[i] = part
    print(f'modeldef_prune: {dropped} surfaces left out of the MODELDEFs, {n_cls} classes told which ({n_dress} dressed at '
          f'spawn), {n_hide} run-time hides and {n_show} shows routed')
    return ''.join(out), ''.join(parts)


def prune(pack):
    """every modeldef.* in the pack folder (the lines only: for blocks written after apply()); returns the number dropped"""
    n = 0
    for f in sorted(os.listdir(pack)):
        if not f.lower().startswith('modeldef'): continue
        p = os.path.join(pack, f)
        txt, d = prune_text(pack, open(p).read())
        if d: open(p, 'w').write(txt)
        n += d
    print(f'modeldef_prune: {n} more hidden surfaces left undrawn in {pack}')
    return n


def unresolve_material(iqm_path, material):
    """make the IQM's meshes using 'material' fall back to nothing (skipped, as prune wants) when no MODELDEF line
    skins them: the name in the IQM's text block becomes one of the same length that is no file ('.png' -> '.pnx').
    For the gore stumps, whose texture sits in the model's folder but which the ZScript always skins by name when it
    shows them. Returns whether the name was found."""
    import struct
    data = bytearray(open(iqm_path, 'rb').read())
    num_text, ofs_text = struct.unpack_from('<II', data, 16 + 3 * 4)
    old = material.encode()
    new = (material[:-1] + ('x' if material[-1] != 'x' else 'y')).encode()
    text = bytes(data[ofs_text:ofs_text + num_text])
    hit, i = False, 0
    while True:
        i = text.find(old + b'\0', i)
        if i < 0: break
        if i == 0 or text[i - 1] == 0:
            data[ofs_text + i:ofs_text + i + len(old)] = new; hit = True
        i += len(old)
    if hit: open(iqm_path, 'wb').write(bytes(data))
    return hit


if __name__ == '__main__':
    for a in sys.argv[1:]: prune(a)
