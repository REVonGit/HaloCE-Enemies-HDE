"""Fold a repository's pack folders into the shipped layout: Core and the enemy API go into the Covenant pack, and the
dialogue is split between the Covenant (every enemy voice) and the Marines (their voices).

    python3 repo_compose.py <repo> hde|sa

Reads packs/<Core>, [packs/HCE_EnemyAPI_LocalDEV], packs/<Covenant>, packs/HaloCE_Enemies_Voices, packs/<Marines>
(as refresh.sh unpacked them) and rewrites packs/<Covenant> and packs/<Marines>, removing the folded-in folders."""
import os, re, sys, shutil, zipfile, tempfile, io

repo, kind = sys.argv[1], sys.argv[2]
P = os.path.join(repo, 'packs')
sys.path.insert(0, os.path.join(repo, 'tools'))
from merge_hce_packs import merge
if kind == 'hde':
    CORE, API, COV, MAR, OTHERS = 'HaloCE_Core', 'HCE_EnemyAPI_LocalDEV', 'HaloCE_Covenant', 'HaloCE_Marines', ['HaloCE_Flood', 'HaloCE_Sentinels']
else:
    CORE, API, COV, MAR, OTHERS = 'HaloCE_Standalone_Core', None, 'HaloCE_Standalone_Covenant', 'HaloCE_Standalone_Marines', ['HaloCE_Standalone_Flood', 'HaloCE_Standalone_Sentinels']
VOI = 'HaloCE_Enemies_Voices'

def tree(d):
    out = {}
    for root, dirs, fs in os.walk(d):
        for f in fs:
            p = os.path.join(root, f); out[os.path.relpath(p, d).replace(os.sep, '/')] = open(p, 'rb').read()
    return out

def zipit(files, path):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, d in sorted(files.items()): z.writestr(n, d)

def unzip(path, d):
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(d)
    with zipfile.ZipFile(path) as z: z.extractall(d)

if not os.path.isdir(os.path.join(P, CORE)):
    sys.exit(f'{CORE} already folded in')
tmp = tempfile.mkdtemp()
# the dialogue: Marine voices to the Marines, everything else to the Covenant
voi = tree(os.path.join(P, VOI))
snd = voi.pop('sndinfo.voices').decode('utf-8')
sec = re.split(r'(?m)^(?=// ---- )', snd)
head, parts = sec[0], sec[1:]
mar_snd = [s for s in parts if s.startswith('// ---- Marine')]
cov_snd = [s for s in parts if not s.startswith('// ---- Marine')]
is_mar = lambda n: n.startswith('sounds/hce_voice/marine_')
cov_voi = {n: d for n, d in voi.items() if not is_mar(n)}; cov_voi['sndinfo.voices'] = (head + ''.join(cov_snd)).encode()
mar_voi = {n: d for n, d in voi.items() if is_mar(n)}
mar_voi['sndinfo.marine_voices'] = ('// Halo CE and Halo 2 Marine dialogue (extract_marine_voices.py).\n'
                                   '// Logical names HCE/<Voice>/<Event> are played by HaloDoom_EnemyBase.HCE_Say().\n\n' + ''.join(mar_snd)).encode()
# Covenant = Core + API + Covenant + the enemy dialogue
order = [CORE] + ([API] if API else []) + [COV]
zips = []
for n in order:
    z = os.path.join(tmp, n + '.pk3'); zipit(tree(os.path.join(P, n)), z); zips.append(z)
z = os.path.join(tmp, 'voices.pk3'); zipit(cov_voi, z); zips.append(z)
merge(zips, os.path.join(tmp, 'cov.pk3'), quiet=True)
unzip(os.path.join(tmp, 'cov.pk3'), os.path.join(P, COV))
# the Covenant pack's own header
zf = os.path.join(P, COV, 'zscript.txt'); z = open(zf).read()
ver = re.match(r'(version "[\d.]+"\n)', z).group(1); incs = re.findall(r'#include "[^"]+"', z)
head = ('// Halo CE enemies, Covenant pack: the Core code (shared projectiles, the Doom-monster replacement handler,'
        + (' the enemy API in ZScript/BaseAI/enemies_base.zsc,' if API else ' the enemy API and projectile library,')
        + '\n// console commands), the Covenant (Grunts, Jackals, Elites, Hunters, and the Digsite add-on: Drinol + Cyberdemon boss,\n'
        '// Slug Men, carbine / pulse-carbine Elites, Blind Wolf, Thorn Beast, Engineer, Drones, Brutes) and their dialogue.\n'
        + ('// Load after HaloDoom Evolved (Local_DEV); the Flood, Sentinels and Marines packs go after it.\n' if API else
           '// Needs no other pk3; the Flood, Sentinels and Marines packs go after it.\n'))
open(zf, 'w').write(ver + '\n' + head + '\n' + '\n'.join(incs) + '\n')
# Marines get their voices
for n, d in mar_voi.items():
    q = os.path.join(P, MAR, n); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(d)
# the other packs now load after the Covenant (which carries Core)
for n in [MAR] + OTHERS:
    zf = os.path.join(P, n, 'zscript.txt')
    s = open(zf).read()
    s = re.sub(r'// Load after HaloCE(_Standalone)?_Core\.pk3[^\n]*', '// Load after ' + COV + '.pk3 (it carries Core' + (' and the enemy API' if API else '') + ').', s)
    open(zf, 'w').write(s)
for n in [CORE, VOI] + ([API] if API else []): shutil.rmtree(os.path.join(P, n))
shutil.rmtree(tmp)
print('folded', ', '.join([CORE] + ([API] if API else []) + [VOI]), '->', COV, '+', MAR, '| marine voice files', len(mar_voi) - 1, '| covenant voice files', len(cov_voi) - 1)
