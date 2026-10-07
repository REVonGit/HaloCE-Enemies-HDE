"""Split the generated pack/ tree into a shared core + one pk3 source tree per faction.

  core       ZScript projectiles + replacement handler, CVARINFO, SNDINFO aliases, the HCEM sprite,
             MAPINFO event handler.  No Halo assets: safe to ship publicly.
  covenant   Grunts, Jackals, Elites, Hunters (+ Doom boss stand-ins)
  flood      infection, carrier and combat forms
  sentinels  Sentinels
  marines    Marines (Doom's marines and allied monsters become these)

Every faction pack only needs the core (and the enemy API addon); load any combination.
DoomEdNums are unchanged: each pack lists the numbers of its own classes."""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pack import PACK, TEAM

OUTDIR = os.environ.get('HCE_FACTIONS', os.path.join(os.path.dirname(PACK), 'factions'))
from build_pack import OUT
GORE = f'{OUT}/gore'                 # extract_halo_gore.py: the Covenant pack's NashGore patch
FACTION = {'COVENANT': 'covenant', 'FLOOD': 'flood', 'SENTINEL': 'sentinels', 'HUMAN': 'marines'}
TITLE = {'covenant': 'Covenant: Grunts, Jackals, Elites, Hunters', 'flood': 'Flood: infection, carrier and combat forms',
         'sentinels': 'Sentinels', 'marines': 'Marines'}
VERSION = 'version "4.15.1"\n'

def chunks(text):
    """split a generated ZScript file into (class name, parent, text) pieces (leading // comments kept)"""
    out = []
    pos = [m.start() for m in re.finditer(r'^(?://[^\n]*\n)*class ', text, re.M)]
    for i, p in enumerate(pos):
        body = text[p:pos[i + 1] if i + 1 < len(pos) else len(text)]
        m = re.search(r'^class (\w+)(?:\s*:\s*(\w+))?', body, re.M)
        out.append((m.group(1), m.group(2), body))
    return out

def main():
    if os.path.exists(OUTDIR): shutil.rmtree(OUTDIR)
    zs = open(f'{PACK}/ZScript/HaloCE/hce_enemies.zsc').read()
    parts = chunks(zs)
    char_of = {}
    for cls, parent, _ in parts:                     # base classes first, then variants / aliases / spawners
        m = re.fullmatch(r'HCE_(\w+)Base', cls)
        if m: char_of[cls] = m.group(1)
    for _ in range(3):
        for cls, parent, _ in parts:
            if cls in char_of: continue
            if parent in char_of: char_of[cls] = char_of[parent]
            m = re.fullmatch(r'HCE_Random(\w+)', cls)
            if m and m.group(1) in TEAM: char_of[cls] = m.group(1)
            m = re.fullmatch(r'HCE_(\w+)ShieldShell', cls)
            if m and m.group(1) in TEAM: char_of[cls] = m.group(1)
            m = re.fullmatch(r'(HCE_\w+)Blade', cls)              # a cloaked sword Elite's blade copy: its Elite's pack
            if m and m.group(1) in char_of: char_of[cls] = char_of[m.group(1)]
    fac_of = {c: FACTION[TEAM[ch]] for c, ch in char_of.items()}
    missing = [c for c, _, _ in parts if c not in fac_of]
    assert not missing, missing
    facs = sorted(set(fac_of.values()))
    # ---------------- core
    core = f'{OUTDIR}/core'
    os.makedirs(f'{core}/ZScript/HaloCE')
    for f in ('hce_projectiles.zsc', 'hce_explosives.zsc', 'hce_core.zsc', 'hce_handler.zsc'):
        shutil.copy(f'{PACK}/ZScript/HaloCE/{f}', f'{core}/ZScript/HaloCE/{f}')
    for f in ('cvarinfo.txt', 'sndinfo.hce'):
        shutil.copy(f'{PACK}/{f}', f'{core}/{f}')
    shutil.copytree(f'{PACK}/sprites', f'{core}/sprites')
    open(f'{core}/zscript.txt', 'w').write(VERSION + '\n// Halo CE enemies, core: shared projectiles and the Doom-monster replacement handler.\n'
        '// Needs HaloDoom_EnemyBase from HCE_EnemyAPI_LocalDEV.pk3 (loaded before this file); add any faction packs after it.\n'
        '#include "ZScript/HaloCE/hce_explosives.zsc"\n#include "ZScript/HaloCE/hce_core.zsc"\n#include "ZScript/HaloCE/hce_projectiles.zsc"\n#include "ZScript/HaloCE/hce_handler.zsc"\n')
    open(f'{core}/mapinfo.txt', 'w').write('GameInfo\n{\n\tAddEventHandlers = "HCE_ReplaceHandler", "HCE_MissileTracker", "HCE_SpawnAllHandler"\n}\n')
    # enemy laser tracers (HCE_EnemyLaser, in the API): HaloDoom Evolved's own beam model and texture
    open(f'{core}/modeldef.hce_lasers', 'w').write('// enemy laser tracers: HaloDoom Evolved\'s laser beam model (Models/Lasers, in HDE)\n'
        'Model HCE_EnemyLaser\n{\n\tModel 0 "Models/Lasers/beam_simple.md3"\n\tSkin 0 "Models/Lasers/BEAM_detailed.png"\n'
        '\tUSEACTORPITCH\n\tFrameIndex HCEM A 0 0\n}\n')
    # Options > Halo CE Gore: blood on the body (hce_bodyblood, blood_kit.py's overlays), off by default
    open(f'{core}/menudef.hce', 'w').write(
        'AddOptionMenu "OptionsMenu"\n{\n\tSubmenu "Halo CE Gore", "HCE_GoreOptions"\n}\n\n'
        'OptionMenu "HCE_GoreOptions"\n{\n\tTitle "Halo CE Gore"\n'
        '\tOption "Blood on bodies", "hce_bodyblood", "OnOff"\n'
        '\tStaticText ""\n'
        '\tStaticText "Enemies get bloodier as they are hurt.", 1\n}\n')
    # console command: punkassbitches -> one of every loaded enemy in a line (HCE_SpawnAllHandler)
    open(f'{core}/keyconf.txt', 'w').write('// Halo CE enemies: "punkassbitches" spawns one of every loaded enemy in a line in front of you,\n'
                                          '// "leatherneck" one of every loaded Marine\n'
                                          'alias punkassbitches "netevent hce_spawnall"\nalias leatherneck "netevent hce_spawnmarines"\n'
                                          '\n// squad orders to the Marines following you (Options > Customize Controls > Halo CE Squad)\n'
                                          'alias hce_follow "netevent hce_squad 0"\nalias hce_hold "netevent hce_squad 1"\nalias hce_regroup "netevent hce_squad 2"\n'
                                          'addkeysection "Halo CE Squad" hce_squad\n'
                                          'addmenukey "Squad: follow me" hce_follow\naddmenukey "Squad: hold here" hce_hold\naddmenukey "Squad: regroup on me" hce_regroup\n')
    # ---------------- factions
    md = open(f'{PACK}/modeldef.hce').read()
    blocks = {re.match(r'Model (\w+)', b).group(1): b for b in re.findall(r'Model \w+\n\{.*?\n\}\n', md, re.S)}
    ed = re.findall(r'^\t(\d+) = (\w+)$', open(f'{PACK}/mapinfo.txt').read(), re.M)
    gl = open(f'{PACK}/gldefs.hce').read()
    bms = re.findall(r'brightmap texture "([^"]+)"\n\{\n\tmap "[^"]+"\n\}', gl)
    camo = re.findall(r'HardwareShader Texture "([^"]+)"', gl)
    for fac in facs:
        d = f'{OUTDIR}/{fac}'
        os.makedirs(f'{d}/ZScript/HaloCE')
        mine = [(c, p, t) for c, p, t in parts if fac_of[c] == fac]
        open(f'{d}/ZScript/HaloCE/hce_{fac}.zsc', 'w').write('\n'.join(t.rstrip('\n') + '\n' for _, _, t in mine))
        open(f'{d}/zscript.txt', 'w').write(VERSION + f'\n// Halo CE enemies, {TITLE[fac]}.\n'
            '// Load after HaloCE_Core.pk3 (and HCE_EnemyAPI_LocalDEV.pk3 before both).\n'
            f'#include "ZScript/HaloCE/hce_{fac}.zsc"\n')
        mblocks = [blocks[c] for c, _, _ in mine if c in blocks]
        open(f'{d}/modeldef.hce_{fac}', 'w').write('\n'.join(mblocks))
        # files the models reference
        need = set()
        for b in mblocks:
            path = None
            for line in b.split('\n'):
                m = re.match(r'\s*Path "(.*)"', line)
                if m: path = m.group(1); continue
                m = re.match(r'\s*(?:Model \d+|SurfaceSkin \d+ \d+) "(.*)"', line)      # model 6: Marine arsenal guns
                if m: need.add(f'{path}/{m.group(1)}')
        # dismemberment (gore_kit.py) and blood on the body (blood_kit.py): gib pieces, stump texture, blood overlays
        for f in list(need):
            if not f.endswith('.iqm'): continue
            dn, stem = os.path.dirname(f), os.path.basename(f)[:-4]
            for g in sorted(os.listdir(f'{PACK}/{dn}')):
                if g.startswith(f'{stem}_gib_') or g == f'gore_{stem}.png' or g.startswith(f'{stem}_blood') \
                        or g.startswith('blood') and g.endswith('.png') or g == 'hce_noblood.png': need.add(f'{dn}/{g}')
        # models and skins the class code swaps in at run time (A_ChangeModel: the sticky detonator's fired gun...)
        ztxt = '\n'.join(t for _, _, t in mine)
        for dn, fn in re.findall(r'A_ChangeModel\([^;]*?"(models/[^"]+)", \'([^\']+\.(?:iqm|png))\'', ztxt):
            if os.path.exists(f'{PACK}/{dn}/{fn}'): need.add(f'{dn}/{fn}')
        # the transparent skin ZScript swaps in at run time (A_ChangeModel: Marine cosmetics, gore, blood overlays)
        for b in mblocks:
            for pth in set(re.findall(r'Path "(models/[^/"]+)/', b)):
                if os.path.exists(f'{PACK}/{pth}/weapons/hce_hidden.png'): need.add(f'{pth}/weapons/hce_hidden.png')
        for f in sorted(need):
            os.makedirs(os.path.dirname(f'{d}/{f}'), exist_ok=True)
            shutil.copy(f'{PACK}/{f}', f'{d}/{f}')
        mybms = [t for t in bms if t in need]
        mycamo = [t for t in camo if t in need]
        if mybms or mycamo:
            out = [f'// Halo CE enemies, {fac}: glowing surfaces' + (', active camo shimmer' if mycamo else '')]
            if mybms:
                shutil.copy(f'{PACK}/models/hce/brightmap_full.png', f'{d}/models/hce/brightmap_full.png')
                out += [f'brightmap texture "{t}"\n{{\n\tmap "models/hce/brightmap_full.png"\n}}' for t in mybms]
            if mycamo:
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_camo.fp', f'{d}/shaders/hce_camo.fp')
                out += [f'HardwareShader Texture "{t}"\n{{\n\tShader "shaders/hce_camo.fp"\n\tSpeed 1.0\n}}' for t in mycamo]
            open(f'{d}/gldefs.hce_{fac}', 'w').write('\n'.join(out) + '\n')
        mynums = [(n, c) for n, c in ed if fac_of.get(c) == fac]
        mi = 'DoomEdNums\n{\n' + ''.join(f'\t{n} = {c}\n' for n, c in mynums) + '}\n'
        if fac == 'covenant' and os.path.exists(f'{GORE}/decaldef.hcegore'):
            # NashGore patch: Halo CE / Halo 2 blood decals and bursts (extract_halo_gore.py, hce_gore.zsc)
            shutil.copy(f'{PACK}/ZScript/HaloCE/hce_gore.zsc', f'{d}/ZScript/HaloCE/hce_gore.zsc')
            with open(f'{d}/zscript.txt', 'a') as zf: zf.write('#include "ZScript/HaloCE/hce_gore.zsc"\n')
            shutil.copy(f'{GORE}/decaldef.hcegore', f'{d}/decaldef.hcegore')
            for sub in ('graphics/hcegore', 'sprites/hcegore'): shutil.copytree(f'{GORE}/{sub}', f'{d}/{sub}')
            open(f'{d}/cvarinfo.txt', 'w').write('server bool hce_halogore = true;        // with NashGore loaded: Halo CE / Halo 2 blood decals and bursts on Covenant enemies\n')
            mi = 'GameInfo\n{\n\tAddEventHandlers = "HCE_HaloGoreHandler"\n}\n\n' + mi
        open(f'{d}/mapinfo.txt', 'w').write(mi)
        print(fac, 'classes', len(mine), 'models', len(mblocks), 'files', len(need), 'ednums', len(mynums))

if __name__ == '__main__':
    main()
