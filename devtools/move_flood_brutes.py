"""Move the Flood Brutes from the Covenant pack to the Flood pack in a repository's packs/ (refresh.sh, after
repo_compose.py). build_digsite makes them with the rest of the Digsite add-on, which refresh.sh merges into the
Covenant pack; they are Flood, so they ship in the Flood pack. The Flood pack loads after the Covenant pack, so their
code still finds the Digsite code it builds on (the Brute base, the Digsite handler) there.

    python3 move_flood_brutes.py <repo> hde|sa

Moves: their classes (the base, every variant, the random spawner) from ZScript/HaloCE/dig_enemies.zsc to
ZScript/HaloCE/dig_flood.zsc; their MODELDEF blocks (modeldef.dig -> modeldef.dig_flood); their GLDEFS entries (the
skins under models/hce_dig/FloodBrute: gldefs.dig -> gldefs.dig_flood); their models folder; their DoomEdNums; their
editor icons; their bestiary rows. A class is theirs if its name is in MOVE (a regex)."""
import os, re, shutil, sys

MOVE = re.compile(r'^HCE_(FloodBruteBase|FloodcombatBrute\w*|RandomFloodBrute)$')
MODELS = 'models/hce_dig/FloodBrute'

repo, kind = sys.argv[1], sys.argv[2]
P = os.path.join(repo, 'packs')
COV, FLO = ('HaloCE_Covenant', 'HaloCE_Flood') if kind == 'hde' else ('HaloCE_Standalone_Covenant', 'HaloCE_Standalone_Flood')
C, F = os.path.join(P, COV), os.path.join(P, FLO)
rd = lambda p: open(p, encoding='utf-8').read()
def wr(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w', encoding='utf-8').write(s)

zf = os.path.join(C, 'ZScript/HaloCE/dig_enemies.zsc')
if not os.path.exists(zf) or not re.search(r'(?m)^class HCE_FloodBruteBase\b', rd(zf)):
    sys.exit(0)                                     # nothing to move (no Digsite, or already moved)
# ZScript: each top-level class with the comment lines just above it; a class ends at the first '}' in column 0
lines = rd(zf).split('\n')
keep, move, i, names = [], [], 0, []
while i < len(lines):
    m = re.match(r'class (\w+)\b', lines[i])
    if not m: keep.append(lines[i]); i += 1; continue
    j = i
    while j < len(lines) and lines[j] != '}': j += 1
    block = lines[i:j + 1]
    if MOVE.match(m.group(1)):
        lead = []
        while keep and keep[-1].startswith('//'): lead.insert(0, keep.pop())
        move += lead + block + ['']; names.append(m.group(1))
    else:
        keep += block
    i = j + 1
wr(zf, '\n'.join(keep))
wr(os.path.join(F, 'ZScript/HaloCE/dig_flood.zsc'),
   '// Halo CE enemies, Flood pack: the Flood Brutes (the Digsite add-on\'s, moved here by move_flood_brutes.py).\n'
   '// They build on the Digsite code in the Covenant pack, which loads first.\n\n' + '\n'.join(move))
zs = os.path.join(F, 'zscript.txt')
if 'dig_flood.zsc' not in rd(zs): wr(zs, rd(zs).rstrip('\n') + '\n#include "ZScript/HaloCE/dig_flood.zsc"\n')
moved = set(names)
# MODELDEF
mf = os.path.join(C, 'modeldef.dig')
md = rd(mf)
blocks = re.findall(r'(?ms)^Model (\w+)\n\{.*?^\}\n', md)
spans = [(m.group(0), m.group(1)) for m in re.finditer(r'(?ms)^Model (\w+)\n\{.*?^\}\n', md)]
mine = [b for b, n in spans if n in moved or MODELS in b]
for b in mine: md = md.replace(b, '')
wr(mf, md)
wr(os.path.join(F, 'modeldef.dig_flood'), '// the Flood Brutes (move_flood_brutes.py)\n' + '\n'.join(mine))
# GLDEFS: entries for their skins
gf = os.path.join(C, 'gldefs.dig')
gl = rd(gf)
ents = [m.group(0) for m in re.finditer(r'(?ms)^(?:brightmap|material|HardwareShader) [Tt]exture "([^"]+)"\n\{.*?^\}\n', gl) if m.group(1).startswith(MODELS + '/')]
for e in ents: gl = gl.replace(e, '')
wr(gf, gl)
wr(os.path.join(F, 'gldefs.dig_flood'), '// the Flood Brutes\' skins (move_flood_brutes.py)\n' + ''.join(ents))
# their models and skins
if os.path.isdir(os.path.join(C, MODELS)):
    if os.path.isdir(os.path.join(F, MODELS)): shutil.rmtree(os.path.join(F, MODELS))
    os.makedirs(os.path.dirname(os.path.join(F, MODELS)), exist_ok=True)
    shutil.move(os.path.join(C, MODELS), os.path.join(F, MODELS))
# DoomEdNums
cm, fm = os.path.join(C, 'mapinfo.txt'), os.path.join(F, 'mapinfo.txt')
ci = rd(cm)
nums = [l for l in ci.split('\n') if re.match(r'\t\d+ = (\w+)$', l) and re.match(r'\t\d+ = (\w+)$', l).group(1) in moved]
for l in nums: ci = ci.replace(l + '\n', '')
wr(cm, ci)
fi = rd(fm)
fi = re.sub(r'(DoomEdNums\n\{\n)', lambda m: m.group(1) + ''.join(l + '\n' for l in nums), fi, count=1) if 'DoomEdNums' in fi \
    else fi + 'DoomEdNums\n{\n' + ''.join(l + '\n' for l in nums) + '}\n'
wr(fm, fi)
# editor icons only they use
movetxt, keeptxt = '\n'.join(move), '\n'.join(keep)
for spr in sorted(set(re.findall(r'//\$Sprite "(\w+)"', movetxt))):
    src = os.path.join(C, 'sprites/udb', spr + '.png')
    if os.path.exists(src):
        dst = os.path.join(F, 'sprites/udb', spr + '.png'); os.makedirs(os.path.dirname(dst), exist_ok=True)
        if f'"{spr}"' in keeptxt: shutil.copy(src, dst)
        else: shutil.move(src, dst)
# bestiary: their entries, and the lore lines only they use
bf = os.path.join(C, 'hcebest.digsite')
if os.path.exists(bf):
    rows = rd(bf).split('\n')
    ents = [r for r in rows if r.startswith('E\t') and r.split('\t')[1] in moved]
    keys = {k for r in ents for k in r.split('\t')[6].split(',')}
    other = {k for r in rows if r.startswith('E\t') and r.split('\t')[1] not in moved for k in r.split('\t')[6].split(',')}
    lore = [r for r in rows if r.startswith('L\t') and r.split('\t')[1] in keys and r.split('\t')[1] not in other]
    wr(bf, '\n'.join(r for r in rows if r not in ents and r not in lore))
    ff = os.path.join(F, 'hcebest.flood')
    wr(ff, rd(ff).rstrip('\n') + '\n' + '\n'.join(ents + lore) + '\n')
print('moved to', FLO, ':', len(names), 'classes,', len(mine), 'models,', len(ents), 'bestiary rows,', len(nums), 'DoomEdNums')
