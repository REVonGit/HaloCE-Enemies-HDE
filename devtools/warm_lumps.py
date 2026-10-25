"""Each pack's warm-up list (refresh.sh, after repo_compose.py and move_flood_brutes.py).

    python3 warm_lumps.py <repo> hde|sa        # the repository's packs/
    python3 warm_lumps.py <folder of packs> dir  # the generator's factions/ (build.sh: the game pk3s get them too)

The core's HCE_WarmHandler (hce_warm.zsc) draws, for the first second of a level, a speck of every material shader a
pack uses, in every render style it is drawn with, so the renderer builds their pipelines before a fight needs
them, and decodes the packs' hit and death effect sounds. For each pack this writes hcewarm.<pack>:
  * one line per speck, 'HCE_WarmUp <style> <skin folder> <skin file>': the first skin of each distinct shader and
    define set in the pack's gldefs.* (material and HardwareShader blocks), in the styles STYLES gives its shader
    (normal: opaque; translucent: the derez band, the camo; add: the flares and fields); the speck is the core's
    tiny HCE_WarmUp model (split_factions.py: models/hce/warm/warm.obj) wearing the skin;
  * one line 'sound <id>' per take of the pack's hit and death effect sounds (its sndinfo.* entries whose last name
    part is in WARM_FX, a $random group's takes each): decoded inaudibly in the level's first seconds, so the first
    shield hit, shield pop or derez in a map doesn't pay for the decode.
A pack with neither gets no lump."""
import os, re, sys

repo, kind = sys.argv[1], sys.argv[2]
P = repo if kind == 'dir' else os.path.join(repo, 'packs')
# shader file (base name) -> the render styles it is drawn with
STYLES = {'hce_derez': ('normal', 'translucent'), 'hce_core': ('normal', 'translucent'), 'hce_camo': ('translucent',),
          'hce_plasma': ('add',), 'hce_plasma_h2': ('add',), 'hce_jshield': ('add',), 'hce_bubble': ('add',),
          'hce_holoflag': ('add',), 'hce_sword': ('normal',), 'hce_visor': ('normal',), 'hce_shield': ('normal',)}
# the effect sounds warmed: the last part of a sound's name (HCE/JShield/Hit, HCE/Sentinel/Chips, HCE/Derez ...);
# the voice lines are the core's HCE_WarmHandler's own business (every voice in the level, from the SNDINFO lumps)
WARM_FX = {'hit', 'deplete', 'derez', 'chips', 'beamimpact', 'h2beamimpact', 'enforcerrocketboom', 'carrierblow'}
rd = lambda p: open(p, encoding='utf-8').read()


def fx_sounds(pack):
    """the takes of the pack's WARM_FX sounds, from its sndinfo.*: a $random group's members, a plain entry itself"""
    out = []
    for f in sorted(os.listdir(pack)):
        if not f.lower().startswith('sndinfo'): continue
        for ln in rd(os.path.join(pack, f)).splitlines():
            ln = ln.strip()
            m = re.match(r'\$random\s+(HCE/\S+)\s*\{([^}]*)\}', ln)
            if m:
                if m.group(1).rsplit('/', 1)[-1].lower() in WARM_FX: out += m.group(2).split()
                continue
            m = re.match(r'(HCE/\S+)\s+"', ln)
            if m and m.group(1).rsplit('/', 1)[-1].lower() in WARM_FX: out.append(m.group(1))
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def materials(pack):
    """[(texture path, shader base name, defines text)] from the pack's gldefs.* (material and HardwareShader blocks)"""
    out = []
    for f in sorted(os.listdir(pack)):
        if not f.lower().startswith('gldefs'): continue
        for m in re.finditer(r'(?ims)^(?:material|HardwareShader)\s+texture\s+"([^"]+)"\s*\{(.*?)^\}', rd(os.path.join(pack, f))):
            tex, body = m.group(1), m.group(2)
            sh = re.search(r'(?i)shader\s+"([^"]+)"', body)
            if not sh: continue
            base = os.path.splitext(os.path.basename(sh.group(1)))[0].lower()
            defs = ' '.join(sorted(re.findall(r'(?i)define\s+("[^"]+"(?:\s*=\s*"[^"]+")?)', body)))
            out.append((tex, base, defs))
    return out


for name in sorted(os.listdir(P)):
    pack = os.path.join(P, name)
    if not os.path.isdir(pack): continue
    for f in list(os.listdir(pack)):                       # an earlier run's lumps
        if f.startswith(('hcewarm.', 'modeldef.warm_')): os.remove(os.path.join(pack, f))
    zd = os.path.join(pack, 'ZScript', 'HaloCE')
    for f in (os.listdir(zd) if os.path.isdir(zd) else []):
        if f.startswith('hce_warm_'): os.remove(os.path.join(zd, f))
    zs = os.path.join(pack, 'zscript.txt')
    if os.path.exists(zs):
        kept = [l for l in rd(zs).splitlines(True) if 'ZScript/HaloCE/hce_warm_' not in l]
        if len(kept) != len(rd(zs).splitlines(True)): open(zs, 'w').write(''.join(kept))
    mats = materials(pack)
    fx = fx_sounds(pack)
    if not mats and not fx: continue
    short = name.replace('HaloCE_', '').replace('Standalone_', '').replace('Enemies_', '').replace('_', '').lower()
    seen = set(); lines = [f'sound {x}' for x in fx]
    for tex, base, defs in mats:
        key = (base, defs)
        if key in seen: continue
        seen.add(key)
        folder, fn = os.path.split(tex)
        for style in STYLES.get(base, ('normal',)):
            lines.append(f'HCE_WarmUp {style} {folder} {fn}')
    open(os.path.join(pack, f'hcewarm.{short}'), 'w').write(
        '// warm-ups at level start (devtools/warm_lumps.py): "sound <id>", decoded inaudibly; "HCE_WarmUp <style> <skin folder> <skin file>",\n'
        '// a shader speck drawn once\n' + '\n'.join(lines) + '\n')
    print(name, ':', len(lines) - len(fx), 'specks for', len(seen), 'shader variants +', len(fx), 'sounds')
