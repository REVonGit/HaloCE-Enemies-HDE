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
    # console command: punkassbitches -> one of every loaded enemy in a line (HCE_SpawnAllHandler)
    open(f'{core}/keyconf.txt', 'w').write('// Halo CE enemies: "punkassbitches" spawns one of every loaded enemy in a line in front of you\n'
                                          'alias punkassbitches "netevent hce_spawnall"\n')
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
                m = re.match(r'\s*(?:Model 0|SurfaceSkin 0 \d+) "(.*)"', line)
                if m: need.add(f'{path}/{m.group(1)}')
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
        open(f'{d}/mapinfo.txt', 'w').write('DoomEdNums\n{\n' + ''.join(f'\t{n} = {c}\n' for n, c in mynums) + '}\n')
        print(fac, 'classes', len(mine), 'models', len(mblocks), 'files', len(need), 'ednums', len(mynums))

if __name__ == '__main__':
    main()
