"""flood_arsenal.py: every armed Flood body can carry any gun but the Forerunners' (and the sword and the hammer, which
aren't guns). Run from generator/:  python3 post/flood_arsenal.py

The Flood hold every gun the same way in Halo CE (their one-handed 'pistol' stance), so a body needs no new
animations for a new gun: only the gun in its hand. For each body in BODIES this writes
  * one overlay model per gun, <Body>_w_<gun>.iqm in packs/HaloCE_Flood/models/hce/FloodArsenal/: the gun (the
    Marine arsenal's models, marine_arsenal.py) bound to the body's gun hand on its own skeleton, placed where Halo
    places a held gun (marine_arsenal.hand_frame, from a gun the body already holds), shown as model 6
  * the guns' textures the packs don't already have, into packs/HaloCE_Flood/models/hce/weapons/
  * the body's loadouts (HCE_HasLoadouts ... HCE_LoadoutAnimTics) between the FLOOD ARSENAL markers at the end of its
    base class: the gun's firing data is the Marine body's (HCE_MarineBase's loadouts, the one body that carries all
    of them), kept once in the Covenant pack's ZScript/HaloCE/hce_flood_arsenal.zsc (HCE_FloodArsenal); the body's
    animations while it holds one are those of its armed class (ARMED); its ShowGun hides its baked guns and shows
    the overlay.
Runs again cleanly (it replaces what it wrote). The Standalone packs get it through the usual sync (bs.convert_text)."""
import os, re, sys, json, pickle, shutil
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); GEN = os.path.dirname(HERE)
sys.path.insert(0, GEN); sys.path.insert(0, os.path.join(GEN, 'lib'))
import marine_arsenal as ma
from iqm import write_iqm
from hce_paths import OUT
PACKS = os.path.join(GEN, '..', 'packs')
FLOOD, COV, MAR = (os.path.join(PACKS, p) for p in ('HaloCE_Flood', 'HaloCE_Covenant', 'HaloCE_Marines'))
ARS_DIR = 'models/hce/FloodArsenal'
OVERLAY_IDX = 6
# body -> (its base class, the zsc it is in, the armed class whose animations it uses, the gun it holds that places the hand)
BODIES = {
    'FloodHuman':        ('HCE_FloodHumanBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatHumanAssaultRifle', 'assault_rifle'),
    'FloodMarine':       ('HCE_FloodMarineBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatHumanUnarmoredAssaultRifle', 'assault_rifle'),
    'FloodArmored':      ('HCE_FloodArmoredBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatHumanArmoredAssaultRifle', 'assault_rifle'),
    'FloodODST':         ('HCE_FloodODSTBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatOdstAssaultRifle', 'assault_rifle'),
    'FloodElite':        ('HCE_FloodEliteBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatEliteAssaultRifle', 'assault_rifle'),
    'FloodEliteArmored': ('HCE_FloodEliteArmoredBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatEliteMinorPlasmaRifle', 'plasma_rifle'),
    'FloodEliteUltra':   ('HCE_FloodEliteUltraBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodcombatEliteUltraFuelRod', 'fuel_rod'),
    'FloodGrunt':        ('HCE_FloodGruntBase', f'{FLOOD}/ZScript/HaloCE/hce_flood.zsc', 'HCE_FloodGruntPlasmaPistol', 'plasma_pistol'),
    'FloodBrute':        ('HCE_FloodBruteBase', f'{COV}/ZScript/HaloCE/dig_enemies.zsc', 'HCE_FloodcombatBruteMinorAssaultRifle', 'assault_rifle'),
}
ARMED_SRC = {'HCE_FloodcombatBruteMinorAssaultRifle': f'{FLOOD}/ZScript/HaloCE/dig_flood.zsc'}
BEGIN, END = '\t// ---- FLOOD ARSENAL (generator/post/flood_arsenal.py) ----\n', '\t// ---- FLOOD ARSENAL END ----\n'


def class_block(src, cls):
    """(start, end) of class cls's body in src (end: its closing brace's index)"""
    a = src.index(f'\nclass {cls} '); i = src.index('{', a); depth = 0
    for j in range(i, len(src)):
        if src[j] == '{': depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0: return a + 1, j
    raise ValueError(cls)


def marine_loadouts():
    """HCE_MarineBase's loadouts: [(HDE gun class, ApplyLoadout body, overlay name, [(surface, skin)])]"""
    src = open(f'{MAR}/ZScript/HaloCE/hce_marines.zsc').read()
    a, b = class_block(src, 'HCE_MarineBase'); s = src[a:b]
    idx = dict((int(n), w) for w, n in re.findall(r"case '(\w+)': return (\d+);", s[s.index('override int HCE_LoadoutIndex'):]))
    out = []
    for i in sorted(idx):
        body = re.search(r'void HCE_ApplyLoadout%d\(\)\n\t\{\n\t\t\{\n(.*?)\t\t\}\n\t\}' % i, s, re.S).group(1)
        vis = re.search(r'void HCE_LoadoutVisual%d\(\)\n\t\{\n\t\t\{\n(.*?)\t\t\}\n\t\}' % i, s, re.S).group(1)
        ov = re.search(r"'Marine_w_(\w+)\.iqm'", vis).group(1)
        skins = re.findall(r"A_ChangeModel\('None', 6, \"\", 'None', (\d+), \"models/hce/weapons\", '([^']+)', CMDL_USESURFACESKIN\)", vis)
        out.append((idx[i], body, ov, [(int(k), f) for k, f in skins]))
    return out


def anim_table(cls):
    """the armed class's animation table and clip lengths: (switch body of HCE_AnimName, switch body of HCE_AnimTics)"""
    path = ARMED_SRC.get(cls) or BODIES[[k for k, v in BODIES.items() if v[2] == cls][0]][1]
    src = open(path).read(); a, b = class_block(src, cls); s = src[a:b]
    names = re.search(r'override Name HCE_AnimName\(int kind\)\n\t\{\n.*?switch\(kind\)\n\t\t\{\n(.*?)\t\t\}', s, re.S).group(1)
    tics = re.search(r'override int HCE_AnimTics\(Name anim\)\n\t\{\n.*?switch\(anim\)\n\t\t\{\n(.*?)\t\t\}', s, re.S).group(1)
    return names, tics


def build_overlays(guns):
    """the overlay IQMs into the Flood pack, and the textures it lacks into its models/hce/weapons"""
    od = f'{FLOOD}/{ARS_DIR}'; os.makedirs(od, exist_ok=True)
    tex_have = set()
    for p in ('HaloCE_Covenant', 'HaloCE_Flood'):
        d = f'{PACKS}/{p}/models/hce/weapons'
        if os.path.isdir(d): tex_have |= set(os.listdir(d))
    need_tex = set(f for _, _, _, sk in guns for _, f in sk)
    for f in sorted(need_tex - tex_have):
        src = f'{MAR}/models/hce/weapons/{f}'
        if os.path.exists(src): shutil.copy(src, f'{FLOOD}/models/hce/weapons/{f}')
        else: print('  missing texture', f)
    for char, (base, zsc, armed, ref) in BODIES.items():
        R, t, jn, joints = ma.hand_frame(char, ref)
        bind = [[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]]
        for _, _, ov, _ in guns:
            wid = ma.wid_of(ov) if ov in ma.ARSENAL else ma.BASE_OVERLAYS[ov]
            d = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
            ms = []
            for k, m in enumerate(d['meshes']):
                n = len(m['pos'])
                bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8); bidx[:, 0] = jn; bw[:, 0] = 255
                pos = (m['pos'] + np.array(ma.OVERLAY_OFFSET.get(ov, (0, 0, 0)))) @ R.T + t
                ms.append(dict(name=f'{wid}_{k}', material=m['material'], pos=pos, nrm=m['nrm'] @ R.T, uv=m['uv'], bidx=bidx, bw=bw, tris=m['tris']))
            write_iqm(f'{od}/{char}_w_{ov}.iqm', joints, ms, [dict(name='bind', fps=30.0, loop=True, frames=bind)])
        print(char, len(guns), 'overlays')


def helper_zsc(guns):
    """the shared firing data and gun models (the Covenant pack: it compiles without the Flood pack)"""
    L = ["// The Flood's guns: any gun but the Forerunners' in any armed Flood body's hand (generator/post/flood_arsenal.py:",
         '// written by it, edit there). The firing data is the Marine body\'s loadouts\' (HCE_MarineBase); the gun model is',
         f'// the body\'s own overlay, {ARS_DIR}/<Body>_w_<gun>.iqm in the Flood pack, shown as model {OVERLAY_IDX}.',
         'class HCE_FloodArsenal play', '{',
         '\tstatic int Index(Name w)', '\t{', '\t\tswitch(w)', '\t\t{']
    L += [f"\t\tcase '{w}': return {i};" for i, (w, _, _, _) in enumerate(guns)]
    L += ['\t\t}', '\t\treturn -1;', '\t}',
          '\tstatic void Apply(HaloDoom_EnemyBase e, int lo)', '\t{', '\t\tswitch(lo)', '\t\t{']
    L += [f'\t\tcase {i}: Apply{i}(e); return;' for i in range(len(guns))]
    L += ['\t\t}', '\t}']
    for i, (w, body, ov, sk) in enumerate(guns):
        b = re.sub(r'(?m)^\t\t\t', '\t\t', body)
        b = re.sub(r'\b(hce_\w+|bHCE_\w+)\b(?=\s*=)', r'e.\1', b)
        L += [f'\tstatic void Apply{i}(HaloDoom_EnemyBase e)   // {w}', '\t{', b.rstrip('\n'), '\t}']
    L += [f'\t// the gun\'s model in body\'s hand (model {OVERLAY_IDX}) and its skins', '\tstatic void Visual(Actor e, String body, int lo)', '\t{', '\t\tswitch(lo)', '\t\t{']
    for i, (w, body, ov, sk) in enumerate(guns):
        L.append(f"\t\tcase {i}:")
        L.append(f"\t\t\te.A_ChangeModel('None', {OVERLAY_IDX}, \"{ARS_DIR}\", body .. \"_w_{ov}.iqm\");")
        for k, f in sk:
            L.append(f"\t\t\te.A_ChangeModel('None', {OVERLAY_IDX}, \"\", 'None', {k}, \"models/hce/weapons\", '{f}', CMDL_USESURFACESKIN);")
        L.append('\t\t\treturn;')
    L += ['\t\t}', '\t}', '}', '']
    return '\n'.join(L)


def body_block(char, base, armed):
    names, tics = anim_table(armed)
    return (BEGIN +
        f'\t// any gun but the Forerunners\' (HCE_FloodArsenal): held as its armed forms hold theirs ({armed}\'s animations)\n'
        '\toverride bool HCE_HasLoadouts() { return true; }\n'
        '\toverride int HCE_LoadoutIndex(Name w) { return HCE_FloodArsenal.Index(w); }\n'
        '\toverride void HCE_ApplyLoadout(int lo) { HCE_FloodArsenal.Apply(self, lo); }\n'
        f'\toverride void HCE_LoadoutVisual(int lo) {{ HCE_FloodBakedGuns(false); HCE_FloodArsenal.Visual(self, "{char}", lo); }}\n'
        '\toverride Name HCE_LoadoutAnim(int lo, int kind)\n\t{\n\t\tswitch(kind)\n\t\t{\n' + names + '\t\t}\n\t\treturn \'None\';\n\t}\n'
        '\toverride int HCE_LoadoutAnimTics(Name anim)\n\t{\n\t\tswitch(anim)\n\t\t{\n' + tics + '\t\t}\n\t\treturn 0;\n\t}\n'
        + END)


def patch_body(path, char, base, armed):
    src = open(path).read()
    a, b = class_block(src, base); s = src[a:b]
    if BEGIN in s: s = s[:s.index(BEGIN)] + s[s.index(END) + len(END):]
    # its ShowGun: the baked guns through HCE_FloodBakedGuns, and with a loadout the overlay instead of them
    m = re.search(r'\toverride void HCE_ShowGun\(bool show\)\n\t\{\n\t\tsuper\.HCE_ShowGun\(show\);\n\t\tstatic const int W\[\] = \{([^}]*)\};\n'
                  r'\t\tfor\(int i = 0; i < W\.Size\(\); i\+\+\)\n\t\t\{\n\t\t\tif\(show\) HCE_ShowSurface\(W\[i\]\);\n\t\t\telse HCE_HideSurface\(W\[i\]\);[^\n]*\n\t\t\}\n\t\}\n', s)
    if m:
        s = s[:m.start()] + ('\toverride void HCE_ShowGun(bool show)\n\t{\n\t\tsuper.HCE_ShowGun(show);\n'
            '\t\tHCE_FloodBakedGuns(show && !hce_hasLoadout);\n'
            f"\t\tif(show && hce_hasLoadout) HCE_LoadoutVisual(hce_loadout);\n"
            f"\t\telse A_ChangeModel('None', {OVERLAY_IDX}, \"\", 'None', 0, \"\", 'None', CMDL_HIDEMODEL);\n\t}}\n"
            '\t// its baked guns (the guns it never held stay undrawn)\n'
            '\tvoid HCE_FloodBakedGuns(bool show)\n\t{\n'
            f'\t\tstatic const int W[] = {{{m.group(1)}}};\n'
            '\t\tfor(int i = 0; i < W.Size(); i++)\n\t\t{\n\t\t\tif(show) HCE_ShowSurface(W[i]);\n\t\t\telse HCE_HideSurface(W[i]);\n\t\t}\n\t}\n') + s[m.end():]
    elif 'void HCE_FloodBakedGuns' not in s:
        raise ValueError(f'{base}: no ShowGun to rework')
    s = s.rstrip('\n\t') + '\n' + body_block(char, base, armed)
    open(path, 'w').write(src[:a] + s + src[b:])


if __name__ == '__main__':
    guns = marine_loadouts()
    print(len(guns), 'guns:', ' '.join(w for w, *_ in guns))
    build_overlays(guns)
    open(f'{COV}/ZScript/HaloCE/hce_flood_arsenal.zsc', 'w').write(helper_zsc(guns))
    zt = f'{COV}/zscript.txt'; z = open(zt).read()
    if 'hce_flood_arsenal.zsc' not in z: open(zt, 'w').write(z.rstrip('\n') + '\n#include "ZScript/HaloCE/hce_flood_arsenal.zsc"\n')
    for char, (base, path, armed, ref) in BODIES.items():
        patch_body(path, char, base, armed)
        print('loadouts:', base)
