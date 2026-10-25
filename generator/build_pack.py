"""Generate the Halo CE enemy pack: ZScript classes, MODELDEF, skins, projectiles.

Run: python3 build_pack.py (from generator/, after the extractors, gore_kit.py and blood_kit.py have filled out/).
Reads (OUT = $HCE_OUT, default out/): ai_data.json (extract_ai.py: bipeds, actors, variants, weapons, collisions),
models/<Char>/<Char>.iqm + .json + textures (extract_chars.py and the other extractors), weapons/, cubemaps/,
spv3_ai.json / galap_ai.json (the SPV3, Mercury Rising and Galap units), udb_icons/, glow_colours.json; variants.py
(the colour and shine tables), templates/ (ZScript and GLSL copied in), assets/elite_skins/, pack/bestiary_lore.txt
and ednum_pins.json (the DoomEdNums already shipped).
Writes (PACK = $HCE_PACK, default pack/): ZScript/HaloCE/hce_enemies.zsc (a base class per character and a class per
variant), ZScript/HaloCE/hce_projectiles.zsc, modeldef.hce, gldefs.hce (brightmaps and the shield / sword / camo /
visor shaders), shaders/, models/hce/<Char>/ (the IQM, baked skins, gibs, blood overlays), models/hce/weapons/,
mapinfo.txt (DoomEdNums), bestiary.txt, sprites/udb/ and out/pack_index.json. split_factions.py then cuts the pack into
the faction packs.

Order of events: AI is loaded at import, then patched in place from top to bottom. The add_* functions and the
module-level blocks (swap_jackal_ranks, add_grunt_ranks, the Sentinel Knights, Halo 2's Sentinels, Galap's, the Marine
arsenal, pilots, ODSTs, Mercury Rising ...) add or re-stat variants in AI['variants'] (a variant with '_late' gets its
DoomEdNum after everything released before it; '_ov' holds its per-variant overrides, see CHAR_OVERRIDES). The weapon
tables (WEAPONS, PATTERNS, FIRE_SOUNDS, DROP_WEAPON ...) are extended the same way. build() then runs: per character,
copies the model and writes its abstract base class (gore, blood, guns, Marine cosmetics); per variant, picks the
stance and animation table, turns Halo's combat numbers into the HCE_* Default properties, bakes the skins, writes
the class and its MODELDEF; then the projectile classes, the random spawners, the Doom boss stand-ins, GLDEFS, the
DoomEdNum list (pinned by ednum_pins.json), the UDB icons and the bestiary lump.

Where to start for the common edits: a stat (health, shield, speed, melee) -> CHAR_OVERRIDES (per character) or
the add_* function that makes the variant (per variant); a weapon's feel -> PATTERNS, FIRE_SOUNDS, WEAPONS and
MARINE_ARSENAL; a new enemy -> an add_* function copying an existing variant (and CHAR_OF_UNIT / TEAM if it is a new
body), plus a lore entry in pack/bestiary_lore.txt; the colours and shine -> variants.py; which Doom monsters the
enemies replace (the replacement mix) -> pack/ZScript/HaloCE/hce_handler.zsc, not this file; the AI itself -> the
hand-written ZScript in pack/ZScript/HaloCE/ (enemies_base.zsc and friends).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, re, math, shutil, glob, zipfile, sys
import json, os, re, math, shutil, glob, zipfile, sys, copy
import numpy as np
from variants import *            # the variants' colours, ranks and looks: the tables a modder tunes (variants.py)
from templates import template   # templates/: the ZScript and GLSL written into the pack as-is
from PIL import Image
from texmath import raster_normals, sample_cube, bake_reflection   # texture maths shared with the extractors
import modeldef_prune                 # hidden model surfaces left undrawn (lib/modeldef_prune.py)

from hce_paths import OUT, PACK
S = 80.0                     # map units per Halo world unit
TICK = 30.0 / 35.0           # Halo ticks per Doom tic
DEG = 180.0 / math.pi

AI = json.load(open(f'{OUT}/ai_data.json'))

def swap_jackal_ranks(variants):
    """The plasma-rifle Jackal is the Ultra and the needler Jackal the Major (extract_ai.synthesize built them the
    other way round). Each keeps its weapon, its shield colour and its DoomEdNum (30248 plasma rifle, 30279 needler);
    the rank's name and stats move: Ultra 100 body / 350 shield, Major 75 / 250."""
    J = 'characters\\jackal\\'
    pr, nd = variants.pop(J + 'jackal major plasma rifle', None), variants.pop(J + 'jackal ultra needler', None)
    if not (pr and nd): return
    for v, rank, body, shield, late in ((pr, 'ultra', 100.0, 350.0, False), (nd, 'major', 75.0, 250.0, True)):
        v['unit']['maximum_body_vitality'] = body
        v['unit']['maximum_shield_vitality'] = shield
        v['_rank'] = rank
        v.pop('_late', None)
        if late: v['_late'] = True
    variants[J + 'jackal ultra plasma rifle'] = pr
    variants[J + 'jackal major needler'] = nd

swap_jackal_ranks(AI['variants'])

# Fuel-rod Elite (new): an Elite Major carrying the Spec Ops Grunts' fuel rod gun, in Halo 2's fuel-rod stance
# (h2_elite_anims.py puts it on the CE skeleton). Its firing data is the fuel-rod Grunt's.
def add_fuel_rod_elite(variants):
    """Fuel-rod Elite (new): a deep copy of the Elite Major plasma rifle variant with the Spec Ops fuel-rod Grunt's
    ranged_combat block, marked '_late' so it spawns in later encounters. To change its gun or ranges, edit fr here"""
    E = 'characters\\elite\\elite major\\elite major '
    base, fr = variants.get(E + 'plasma rifle'), variants.get('characters\\grunt\\grunt specops fuel rod')
    if not (base and fr) or (E + 'fuel rod') in variants: return
    import copy
    v = copy.deepcopy(base)
    v['ranged_combat'] = copy.deepcopy(fr['ranged_combat'])
    v['_late'] = True
    variants[E + 'fuel rod'] = v

add_fuel_rod_elite(AI['variants'])

# GRUNT_RANKS: variants.py
def add_grunt_ranks(variants):
    """Ultra Grunts (new) with the needler and the plasma pistol: the Major's variant, a third tougher, in
    GRUNT_RANKS['ultra']'s colour; and the Heavy Grunt: the Spec Ops fuel-rod Grunt in GRUNT_RANKS['heavy']'s colour.
    To change their toughness, edit the 1.33 here; their colours, GRUNT_RANKS in variants.py"""
    import copy
    G = 'characters\\grunt\\grunt '
    def colour(v, lo_hi):
        """set the variant's first change colour to the (lower, upper) RGB range lo_hi"""
        cl = copy.deepcopy(v.get('change_colors_list') or [])
        lo, hi = lo_hi
        if cl: cl[0].update(color_lower_bound=list(lo), color_upper_bound=list(hi))
        else: cl = [dict(color_lower_bound=list(lo), color_upper_bound=list(hi))]
        v['change_colors_list'] = cl
    for w in ('needler', 'plasma pistol'):
        base = variants.get(G + 'major ' + w)
        if not base or (G + 'ultra ' + w) in variants: continue
        v = copy.deepcopy(base)
        v['unit']['maximum_body_vitality'] = round(base['unit']['maximum_body_vitality'] * 1.33)
        colour(v, GRUNT_RANKS['ultra'])
        v['_rank'] = 'ultra'; v['_late'] = True
        variants[G + 'ultra ' + w] = v
    # the Ultra with the fuel rod (Halo 2 / 3): the Spec Ops fuel-rod Grunt (its body carries the gun) in the Ultras'
    # white, as tough as the other Ultras
    base, ult = variants.get(G + 'specops fuel rod'), variants.get(G + 'ultra needler')
    if base and ult and (G + 'ultra fuel rod') not in variants:
        v = copy.deepcopy(base)
        v['unit']['maximum_body_vitality'] = ult['unit']['maximum_body_vitality']
        colour(v, GRUNT_RANKS['ultra'])
        v['_rank'] = 'ultra'; v['_late'] = True
        variants[G + 'ultra fuel rod'] = v
    base = variants.get(G + 'specops fuel rod')
    if base and (G + 'heavy fuel rod') not in variants:
        v = copy.deepcopy(base)
        colour(v, GRUNT_RANKS['heavy'])
        v['_rank'] = 'heavy'; v['_late'] = True
        variants[G + 'heavy fuel rod'] = v

add_grunt_ranks(AI['variants'])

# GRUNT_SHIELDS: variants.py. The Ultras and the Spec Ops Grunts carry an energy shield (with the shield flare on
# their own bodies); the Heavies, made from the Spec Ops, don't
def add_grunt_shields(variants):
    """give every Grunt variant whose rank (its '_rank', else the second word of its name) is in GRUNT_SHIELDS that
    much shield vitality. To change which ranks have shields or how much, edit GRUNT_SHIELDS in variants.py"""
    for vn, v in variants.items():
        if not vn.startswith('characters\\grunt\\grunt '): continue
        rank = v.get('_rank') or vn.split('\\')[-1].split(' ')[1]
        if rank in GRUNT_SHIELDS: v['unit'] = dict(v['unit'], maximum_shield_vitality=GRUNT_SHIELDS[rank])

add_grunt_shields(AI['variants'])

# HEAVY_GREEN: variants.py
def add_elite_heavy(variants):
    """Heavy Elites (new): the Major's fuel rod, plasma rifle and needler variants on the 'elite heavy' unit, 125 body
    / 200 shield, painted HEAVY_GREEN (variants.py; elite_skin turns the blue Minor skin green for them)"""
    import copy
    E = 'characters\\elite\\elite major\\elite major '
    H = 'characters\\elite\\elite heavy\\elite heavy '
    for w in ('fuel rod', 'plasma rifle', 'needler'):
        base = variants.get(E + w)
        if not base or (H + w) in variants: continue
        v = copy.deepcopy(base)
        v['unit']['maximum_body_vitality'] = 125.0
        v['unit']['maximum_shield_vitality'] = 200.0
        cl = copy.deepcopy(v.get('change_colors_list') or [{}])
        cl[0].update(color_lower_bound=list(HEAVY_GREEN), color_upper_bound=list(HEAVY_GREEN))
        v['change_colors_list'] = cl
        v['_rank'] = 'heavy'; v['_late'] = True
        variants[H + w] = v

add_elite_heavy(AI['variants'])

# ULTRA_WHITE: variants.py
def add_elite_ultra(variants):
    """Ultra Elites (new, Halo 2's white rank on the Halo CE Elite): the Major's plasma rifle, needler and fuel rod
    variants, 125 body / 250 shield (above the Heavy, below the Commander's sword), a quarter tighter aim, painted
    ULTRA_WHITE (variants.py; elite_skin whitens the blue Minor skin's plates for them, the silver shine)"""
    import copy
    E = 'characters\\elite\\elite major\\elite major '
    U = 'characters\\elite\\elite ultra\\elite ultra '
    for w in ('plasma rifle', 'needler', 'fuel rod'):
        base = variants.get(E + w)
        if not base or (U + w) in variants: continue
        v = copy.deepcopy(base)
        v['unit']['maximum_body_vitality'] = 125.0
        v['unit']['maximum_shield_vitality'] = 250.0
        v['ranged_combat']['projectile_error_angle'] = base['ranged_combat']['projectile_error_angle'] * 0.75
        cl = copy.deepcopy(v.get('change_colors_list') or [{}])
        cl[0].update(color_lower_bound=list(ULTRA_WHITE), color_upper_bound=list(ULTRA_WHITE))
        v['change_colors_list'] = cl
        v['_rank'] = 'ultra'; v['_late'] = True
        variants[U + w] = v

add_elite_ultra(AI['variants'])

def add_jackal_loadouts(variants):
    """the Halo CE Jackals' other loadouts (new): the Major with the plasma pistol (Halo CE's own 'jackal major plasma
    pistol', which extract_ai.synthesize re-armed) and the Minor with the needler; each keeps its rank's stats and
    shield, and takes the other's ranged_combat block"""
    import copy
    J = 'characters\\jackal\\jackal '
    mpp, mnd = variants.get(J + 'minor plasma pistol'), variants.get(J + 'major needler')
    if not (mpp and mnd): return
    for name, rank_v, gun_v, rank in (('major plasma pistol', mnd, mpp, 'major'), ('minor needler', mpp, mnd, 'minor')):
        if (J + name) in variants: continue
        v = copy.deepcopy(rank_v)
        v['ranged_combat'] = copy.deepcopy(gun_v['ranged_combat'])
        v['_rank'] = rank; v['_late'] = True
        variants[J + name] = v

add_jackal_loadouts(AI['variants'])

# Halo 2's Honor Guard and Ranger Elites (new), in Halo 2's armour worn over the Halo CE Elite (extract_h2_elite_kit.py:
# the pieces carried bone by bone onto the CE skeleton, attached as models 1-3 riding its animation; ELITE_KIT_CODE).
# The Honor Guard: the High Council's guard, the Commander's stats (Halo 2's elite_honor_guard char is a Major
# underneath, but they guard the Prophets), the tall-crested ceremonial helmet and plates, a crimson harness; the plasma
# rifle and the energy sword (the plasma carbine: build_digsite.py). The Ranger: Halo 2's EVA Elite, a Minor's stats
# (its char's 30 body / 70 shield), the sealed helmet with its gold lens and the jump pack it hops about the fight on
# (HCE_Jetpack, enemies_base.zsc HCE_TryJet), a pale steel harness; the plasma rifle and the needler.
ELITE_KIT = f'{OUT}/models/EliteKit'
# HONOR_RED: variants.py
# RANGER_STEEL: variants.py
# ELITE_H2_ARMOUR: variants.py

SKIN_PAIRS = []      # (source texture, baked skin): skin_check.py's deep-fried check after each build

def elite_kit_code(pieces, mdir='hce', whole=False):
    """attach Halo 2's pieces (models 1..) to a CE Elite. Pieces cut by limb (extract_h2_elite_kit.SPLIT: surfaces named
    _1 left arm, _2 right arm, _3 head) lose that limb's surfaces when it is severed; a helmet piece that isn't cut
    (the Honor Guard's, models 1) goes whole with the head. whole: a whole body (the Ranger's) worn in place of the CE
    Elite's, whose body surfaces are hidden on the model and its blood overlay ({HCE_BODY_SURFS}: filled in per model
    by build_pack when the class is written)"""
    kj = f'{ELITE_KIT}/EliteKit.json'
    limbs = json.load(open(kj)).get('limbs', {}) if os.path.exists(kj) else {}
    hid = f'"models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN'
    att = ''.join(f'\t\tA_ChangeModel(\'None\', {k + 1}, "models/{mdir}/EliteKit", "{p}.iqm", {k + 1}, "", \'None\');\n' for k, p in enumerate(pieces))
    kmeta = json.load(open(kj)) if os.path.exists(kj) else {}
    stumps = kmeta.get('stumps', {})
    # the Halo 2 bodies' own stumps (extract_h2_elite_kit.add_stumps): hidden until their limb comes off
    att += ''.join(f"\t\tA_ChangeModel('None', {k + 1}, \"\", 'None', {i}, {hid});\n"
                   for k, p in enumerate(pieces) for i in stumps.get(p, {}).values())
    sev = []
    for L, lc in ((1, 'HCE_LIMB_LARM'), (2, 'HCE_LIMB_RARM'), (3, 'HCE_LIMB_HEAD')):
        lines = []
        for k, p in enumerate(pieces):
            names = limbs.get(p, [])
            split = any(n[-2:] in ('_1', '_2', '_3') for n in names)
            if split: si = [i for i, n in enumerate(names) if n.endswith(f'_{L}')]
            else: si = list(range(len(names))) if (L == 3 and k == 0 and not whole) else []
            lines += [f"\t\t\tA_ChangeModel('None', {k + 1}, \"\", 'None', {i}, {hid});\n" for i in si]
            st = stumps.get(p, {}).get(str(L))
            if st is not None:                  # its own stump shows; the CE Elite's, inside it, stays hidden
                lines.append(f"\t\t\tA_ChangeModel('None', {k + 1}, \"\", 'None', {st}, \"models/{mdir}/EliteKit\", '{kmeta.get('stump_tex', {}).get(p, {}).get(str(L)) or kmeta.get('gore_tex', 'gore_Elite.png')}', CMDL_USESURFACESKIN);\n")
                if whole:
                    lines.append(f"\t\t\tA_ChangeModel('None', 0, \"\", 'None', {{HCE_STUB_{L}}}, {hid});\n")
        if lines: sev.append(f'\t\tif(limb == {lc})\n\t\t{{\n' + ''.join(lines) + '\t\t}\n')
    body = ''
    if whole:
        hide = f"\t\tfor(int i = 0; i < BS.Size(); i++) A_ChangeModel('None', {{idx}}, \"\", 'None', BS[i], {hid});\n"
        body = ('\t\tstatic const int BS[] = { {HCE_BODY_SURFS} };\n' + hide.replace('{idx}', '0'))
        att = body + att
    fire = json.load(open(kj)).get('jet_fire') if os.path.exists(kj) else None
    if 'elite_jetpack' in pieces and fire:
        # the pack's nozzles (its jet_fire markers, in the CE Elite's bind space) for HCE_JetExhaust, at this model's
        # scale ({HCE_MODEL_SCALE}: filled in per model, as the body surfaces are; MODELDEF's height is 1.2 times it)
        (x, y, z), (dx, dy, dz) = fire[0]['pos'], fire[0]['dir']
        att += (f'\t\thce_jetNozzle = ({x}, {abs(y)}, {z * 1.2}) * {{HCE_MODEL_SCALE}};\n'
                f'\t\thce_jetDir = ({dx}, {abs(dy)}, {dz});\n')
    out = ('\t// Halo 2 over the CE Elite (extract_h2_elite_kit.py): ' + ', '.join(pieces) + ('; the CE body hidden under it' if whole else '') + '\n'
           '\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n' + att
           + '\t\tHCE_ResumeAnim();        // A_ChangeModel resets the animation the spawn started (idle, sleeping)\n\t}\n'
           '\toverride void HCE_OnSever(int limb, bool gunArm)\n\t{\n\t\tsuper.HCE_OnSever(limb, gunArm);\n' + ''.join(sev) + '\t}\n')
    gibs = (json.load(open(kj)).get('gibs', {}) if os.path.exists(kj) else {}).get(pieces[0], {})
    if whole and gibs:                    # its severed head and arms are its own pieces, not the CE Elite's
        cases = ''.join(f'\t\tcase {lc}: path = "models/{mdir}/EliteKit"; model = \'{g["file"]}\'; stub = {g["stub"]}; tex = \'{g["tex"]}\'; break;\n'
                        for limb, lc in (('head', 'HCE_LIMB_HEAD'), ('larm', 'HCE_LIMB_LARM'), ('rarm', 'HCE_LIMB_RARM'))
                        for g in [gibs.get(limb)] if g)
        out += ('\toverride void HCE_GibOverride(int limb, out String path, out Name model, out int stub, out Name tex)\n\t{\n'
                '\t\tswitch(limb)\n\t\t{\n' + cases + '\t\t}\n\t}\n')
    if whole:                             # its shield flare in the shape of the Halo 2 body (h2_shell_code)
        out += f"\toverride Name HCE_ShellClass() {{ return 'HCE_{{HCE_CHAR}}{''.join(w.capitalize() for w in pieces[0].split('_'))}ShieldShell'; }}\n"
    if whole:
        out += ('\toverride void HCE_BloodHideClass()\n\t{\n\t\tsuper.HCE_BloodHideClass();\n\t\tstatic const int BS[] = { {HCE_BODY_SURFS} };\n'
                + hide.replace('{idx}', '{HCE_BLOOD_IDX}') + '\t}\n')
    return out

# KIT_SHINE: variants.py

def kit_shine(d):
    """bake KIT_SHINE's reflection into the pack's copies of the Elite kit's colour maps (d: its EliteKit folder)"""
    from iqm import read_iqm
    meta = json.load(open(f'{ELITE_KIT}/EliteKit.json'))
    specs = meta.get('spec', {})
    meshes = []
    for f in sorted(os.listdir(d)):
        if f.endswith('.iqm'): meshes += read_iqm(f'{d}/{f}')[1]
    for tex, (k, cube) in KIT_SHINE.items():
        if tex not in specs or not os.path.exists(f'{d}/{tex}'): continue
        faces = cube_faces('elite', cube)
        if faces is None: continue
        im = Image.open(f'{ELITE_KIT}/{tex}').convert('RGB')
        rgb = np.asarray(im).astype(np.float32) / 255.0
        spec = np.asarray(Image.open(f'{ELITE_KIT}/{specs[tex]}').convert('L').resize(im.size)).astype(np.float32) / 255.0
        n = raster_normals(meshes, tex, im.size).copy()
        Image.fromarray((bake_reflection(rgb, n, spec, faces, k) * 255).astype(np.uint8)).save(f'{d}/{tex}')
        SKIN_PAIRS.append((f'{ELITE_KIT}/{tex}', f'{d}/{tex}'))

def h2_shell_code(char, pieces, meta, pack, mdir, scs, shells):
    """the energy-shield flare for a Halo 2 body worn over a CE Elite: the CE model with every surface hidden (it carries
    the animation), the Halo 2 pieces over it as attachments, every surface of them the glowing shield texture. The
    flare actor plays the Elite's animations (HCE_ApplyAnim), so the pieces move with it. Returns (ZScript, MODELDEF)"""
    from iqm import read_iqm
    name = f"HCE_{char}{''.join(w.capitalize() for w in pieces[0].split('_'))}ShieldShell"
    if name in shells: return [], []
    shells.add(name)
    kit = f'{pack}/models/{mdir}/EliteKit'
    bake_shell(SHELL_TINT[char], f'{kit}/ek_shieldshell.png')
    lines = [f'\tPath "models/{mdir}/{char}"', f'\tModel 0 "{char}.iqm"', f'\tPath "models/{mdir}/weapons"']
    lines += [f'\tSurfaceSkin 0 {i} "hce_hidden.png"' for i in range(len(meta.get('mesh_names') or meta['meshes']))]
    lines += [f'\tPath "models/{mdir}/EliteKit"']
    frames = ['\tFrameIndex HCEM A 0 0']
    for k, p in enumerate(pieces):
        n = len(read_iqm(f'{kit}/{p}.iqm')[1])
        lines += [f'\tModel {k + 1} "{p}.iqm"'] + [f'\tSurfaceSkin {k + 1} {i} "ek_shieldshell.png"' for i in range(n)]
        frames.append(f'\tFrameIndex HCEM A {k + 1} 0')
    zs = [f'// energy-shield flare for the {pieces[0]} Elites: the Halo 2 body\'s shape\nclass {name} : HCE_ShieldShell {{}}\n']
    md = [f'Model {name}\n{{\n' + '\n'.join(lines) + f'\n\tScale {scs:.1f} {scs:.1f} {scs * 1.2:.1f}\n\tUseActorPitch\n\tBaseFrame\n'
          + '\n'.join(frames) + '\n}\n']
    return zs, md

def add_elite_h2_armour(variants):
    """The Honor Guard and Ranger Elites from ELITE_H2_ARMOUR (variants.py: rank -> ({gun: the CE variant it copies},
    armour colour, Halo 2 pieces, extra flags)): each a copy of its source variant wearing the Halo 2 body
    (elite_kit_code) in place of the CE Elite's. Skipped when extract_h2_elite_kit.py hasn't run"""
    import copy
    if not os.path.exists(f'{ELITE_KIT}/EliteKit.json'): return
    for rank, (srcs, rgb, pieces, extra) in ELITE_H2_ARMOUR.items():
        for gun, src in srcs.items():
            vn = f'characters\\elite\\elite {rank}\\elite {rank} {gun}'
            if src not in variants or vn in variants: continue
            v = copy.deepcopy(variants[src])
            cl = copy.deepcopy(v.get('change_colors_list') or [{}])
            cl[0].update(color_lower_bound=list(rgb), color_upper_bound=list(rgb))
            v['change_colors_list'] = cl
            v['_late'] = True
            # Halo 2's whole Honor Guard or Ranger, worn in place of the CE Elite's body
            v['_ov'] = dict(v.get('_ov') or {}, code=elite_kit_code(pieces, whole=True), add_flags=list(extra), h2_pieces=list(pieces))
            variants[vn] = v

add_elite_h2_armour(AI['variants'])

# Beam-rifle Spec Ops Elite (new): the Spec Ops plasma-rifle Elite's stats with Halo 2's beam rifle, in Halo 2's own
# Elite rifle stance (h2_elite_anims.py), fighting from further back
def add_beam_rifle_specops(variants):
    """Beam-rifle Spec Ops Elite (new): the Spec Ops plasma-rifle variant re-armed with H2BEAM_REF and pushed to
    sniper ranges (6-22 wu combat, 45 wu max), '_late'. To change its engagement distance, edit the ranges here"""
    E = 'characters\\elite\\elite specops\\elite specops '
    base = variants.get(E + 'plasma rifle')
    if not base or (E + 'beam rifle') in variants: return
    import copy
    v = copy.deepcopy(base)
    v['ranged_combat']['reference'] = H2BEAM_REF
    v['ranged_combat'].update(combat_range_lower_bound=6.0, combat_range_upper_bound=22.0, maximum_firing_range=45.0)
    v['_late'] = True
    variants[E + 'beam rifle'] = v

H2BEAM_REF = r'h2\weapons\beam rifle'
add_beam_rifle_specops(AI['variants'])

# Plasma-Caster Spec Ops Elite (new): the Spec Ops plasma-rifle Elite with HDE's Plasma Caster (plasma_caster_ce.py: a
# Halo CE-style model, attached as an overlay model on the Elite's own skeleton), in the Elite rifle stance; it lobs
# Plasma Caster shots (charged: the three-shot cluster) from mid range
CASTER_REF = r'hde\plasma caster'
def add_caster_specops(variants):
    """Plasma-Caster Spec Ops Elite (new): the Spec Ops plasma-rifle variant re-armed with CASTER_REF at mid range
    (4-14 wu, 20 wu max), '_late', with the plasma_caster overlay model in the rifle stance ('_ov').
    To change its ranges, edit the update() here"""
    E = 'characters\\elite\\elite specops\\elite specops '
    base = variants.get(E + 'plasma rifle')
    if not base or (E + 'plasma caster') in variants: return
    import copy
    v = copy.deepcopy(base)
    v['ranged_combat']['reference'] = CASTER_REF
    v['ranged_combat'].update(combat_range_lower_bound=4.0, combat_range_upper_bound=14.0, maximum_firing_range=20.0)
    v['_late'] = True
    v['_ov'] = dict(overlay='plasma_caster', stance='rifle')
    variants[E + 'plasma caster'] = v

add_caster_specops(AI['variants'])

# The Ultra Jackal is the Digsite add-on's now, on the Halo 2 Jackal (build_digsite.py takes its variant from MOVED;
# same class name, same DoomEdNum 30248)
MOVED = {k: AI['variants'].pop(k) for k in [r'characters\jackal\jackal ultra plasma rifle'] if k in AI['variants']}

# The gold Elite (Commander) wears the regular Elite body: its colour mask leaves the hands their own dark colour,
# where the Elite Special's covers the gauntlets too. Its stats, weapons and DoomEdNums stay its own.
for _vn, _v in AI['variants'].items():
    if 'elite commander' in _vn and _v['unit_reference'] == r'characters\elite\elite special':
        _v['unit_reference'] = r'characters\elite\elite'

# DoomEdNums already released never change (maps place them): ednum_pins.json holds every shipped class's number.
# A class that is still there keeps its pinned number even if its position in the list moved; new classes take the
# lowest numbers no pinned class uses, from where the generated list would have put them.
PINS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ednum_pins.json')

def pin_ednums(ednums):
    """[(DoomEdNum, class)] as the build numbered them -> the same list with every class in ednum_pins.json on its
    shipped number and the rest moved off any number a pin holds, sorted by number. To pin a new release's numbers,
    add its classes to ednum_pins.json. A class taken out of the pack keeps its entry, renamed '<class> (retired)',
    so its number stays reserved: deleting the entry freed the number and the next unpinned classes slid onto it"""
    pins = json.load(open(PINS_PATH)) if os.path.exists(PINS_PATH) else {}
    used = set(pins.values())
    out = []
    for n, cls in ednums:
        if cls in pins: out.append((pins[cls], cls)); continue
        while n in used: n += 1
        used.add(n); out.append((n, cls))
    return sorted(out)
# Halo CE unit (biped tag path, as ai_data.json keys it) -> the pack's character name: the folder under out/models
# and models/hce, the HCE_<Char>Base class, and the key of every per-character table below (TEAM, VOICES, BLOOD,
# CHAR_OVERRIDES, HEAD_CLEAR ...). A new body needs an entry here and in TEAM; the optional units (SPV3, Knights,
# Sentinels, Galap, Mercury Rising) are added further down when their extracted models exist
CHAR_OF_UNIT = {
    r'characters\grunt\grunt': 'Grunt', r'characters\grunt\grunt specops': 'GruntSpecOps',
    r'characters\jackal\jackal': 'Jackal', r'characters\jackal\jackal major': 'JackalMajor',
    r'characters\elite\elite': 'Elite', r'characters\elite\elite special': 'EliteSpecial',
    r'characters\hunter\hunter': 'Hunter', r'characters\flood_infection\flood_infection': 'FloodInfection',
    r'characters\floodcarrier\floodcarrier': 'FloodCarrier', r'characters\floodcombat elite\floodcombat elite': 'FloodElite',
    r'characters\floodcombat_human\floodcombat_human': 'FloodHuman', r'characters\sentinel\sentinel': 'Sentinel',
    r'characters\marine\marine': 'Marine', r'characters\marine_armored\marine_armored': 'MarineArmored',
    r'characters\marine_odst\odst': 'MarineODST',
}
# character -> its side: COVENANT, FLOOD, SENTINEL or HUMAN (the Species and HCE_Team of its classes, who it fights and
# won't harm; HUMAN is +FRIENDLY; the UDB category and the faction pack it ships in, UDB_CATEGORY / split_factions.py)
TEAM = {'Grunt': 'COVENANT', 'GruntSpecOps': 'COVENANT', 'Jackal': 'COVENANT', 'JackalMajor': 'COVENANT',
        'Elite': 'COVENANT', 'EliteSpecial': 'COVENANT', 'Hunter': 'COVENANT', 'FloodInfection': 'FLOOD',
        'FloodCarrier': 'FLOOD', 'FloodElite': 'FLOOD', 'FloodHuman': 'FLOOD', 'Sentinel': 'SENTINEL',
        'Marine': 'HUMAN', 'MarineArmored': 'HUMAN', 'MarineODST': 'HUMAN'}

# Flood forms from SPV3 maps (extract_spv3.py -> spv3_ai.json), in the Flood pack with the Halo CE Flood: the XAM Campaign
# Overhaul's Flood Grunt (Tropical Thunder 98) and Ruby's Rebalance's Flood hosts (mynameislol), from their c40 maps
SPV3_FLOOD = {r'characters\flood grunt\flood grunt': 'FloodGrunt',
              # Sabopool's Halo CE Overhaul 2.0's armed Flood Grunts (its c40): the plasma pistol and the needler, in the
              # same body (theirs: every Flood Grunt wears it)
              r'characters\floodcombat_grunt\floodcombat grunt': 'FloodGrunt',
              r'characters\floodcombat_odst\floodcombat_odst': 'FloodODST',
              r'characters\floodcombat_marine\floodcombat_marine': 'FloodMarine',
              r'characters\floodcombat_human\floodcombat_human armored': 'FloodArmored',
              r'characters\floodcombat elite new\armored\floodcombat elite armored': 'FloodEliteArmored',
              r'characters\floodcombat elite new\floodcombat_elite_special\floodcombat elite commander': 'FloodEliteCommander',
              r'characters\floodcombat elite shield\floodcombat elite ultra': 'FloodEliteUltra',
              # SOI's Singleplayer Adventure V3's Flood Juggernaut (its c20: Halo 2's Juggernaut)
              r'soi\characters\flood_juggernaut\juggernaut': 'FloodJuggernaut'}
# their DoomEdNums, in this order after everything released before them (the Flood Grunt keeps the number it shipped with)
SPV3_FLOOD_ORDER = (
    ['HCE_FloodGrunt', 'HCE_RandomFloodGrunt',
     'HCE_FloodcombatOdstAssaultRifle', 'HCE_FloodcombatOdstShotgun', 'HCE_FloodcombatOdstSniperRifle', 'HCE_RandomFloodODST',
     'HCE_FloodcombatHumanUnarmoredAssaultRifle', 'HCE_FloodcombatHumanUnarmoredPistol', 'HCE_FloodcombatHumanUnarmoredUnarmed', 'HCE_RandomFloodMarine',
     'HCE_FloodcombatHumanArmoredAssaultRifle', 'HCE_FloodcombatHumanArmoredPistol', 'HCE_FloodcombatHumanArmoredShotgun',
     'HCE_FloodcombatHumanArmoredRocketLauncher', 'HCE_FloodcombatHumanArmoredSniperRifle', 'HCE_FloodcombatHumanArmoredUnarmed', 'HCE_RandomFloodArmored']
    + [f'HCE_FloodcombatElite{r}{w}' for r in ('Minor', 'Major') for w in ('Needler', 'PlasmaPistol', 'PlasmaRifle', 'Unarmed')]
    + ['HCE_RandomFloodEliteArmored', 'HCE_FloodcombatEliteCommanderEnergySword', 'HCE_FloodcombatEliteUltraFuelRod',
       'HCE_RandomFloodEliteCommander', 'HCE_RandomFloodEliteUltra', 'HCE_FloodJuggernaut', 'HCE_RandomFloodJuggernaut',
       'HCE_FloodGruntPlasmaPistol', 'HCE_FloodGruntNeedler'])
# the armed Flood Grunts fight as the combat forms do (their own actor's kind: Flood), not as the XAM one bursting like a carrier
FLOOD_GRUNT_ARMED = dict(stance='pistol', flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Leaps', 'HCE_Resurrects'])
_sp = f'{OUT}/spv3_ai.json'
if os.path.exists(_sp):
    _S3 = json.load(open(_sp))
    for _u, _c in SPV3_FLOOD.items():
        if _u not in _S3['bipeds'] or not os.path.exists(f'{OUT}/models/{_c}/{_c}.json'): continue
        CHAR_OF_UNIT[_u] = _c; TEAM[_c] = 'FLOOD'
        AI['bipeds'][_u] = _S3['bipeds'][_u]
        for _k, _v in _S3['variants'].items():
            if _v['unit_reference'] != _u: continue
            _v['_late'] = True
            if _u == r'characters\floodcombat_grunt\floodcombat grunt': _v['_ov'] = dict(FLOOD_GRUNT_ARMED)
            AI['variants'][_k] = _v
            AI['actors'][_v['actor_reference']] = _S3['actors'][_v['actor_reference']]
        _cm = _S3['bipeds'][_u].get('collision_model')
        if _cm and _cm in _S3['collisions']: AI['collisions'][_cm] = _S3['collisions'][_cm]

# Sentinel Knights (extract_sentinel_knight.py: blackandfan's Halo 2 tag pack, with the Halo Infinite Forerunner arm guns of
# promethean_ce.py as their right forearms): in the Sentinels pack. Three ranks from the tag pack's character tags (normal
# body / shield vitality) and the biped's change colours (grey minors and majors, gold commanders), each with every gun.
# Their combat data starts from the CE Elite Major's (re-statted here), the pistol stance (one arm gun)
KNIGHT = r'objects\characters\sentinel_knight\sentinel_knight'
KNIGHT_JSON = f'{OUT}/models/SentinelKnight/SentinelKnight.json'
KNIGHT_RANKS = {'minor': dict(body=200, shield=50), 'major': dict(body=300, shield=100), 'commander': dict(body=400, shield=150)}
# gun -> (weapon tag path, combat range min, max (WU), the gun's surface name)
KNIGHT_GUNS = {'light rifle': (r'weapons\light rifle\light rifle', 3.0, 22.0, 'light_rifle'),
               'scattershot': (r'weapons\scattershot\scattershot', 1.0, 6.0, 'scattershot'),
               'binary rifle': (r'weapons\binary rifle\binary rifle', 8.0, 40.0, 'binary_rifle'),
               'suppressor': (r'weapons\suppressor\suppressor', 2.0, 14.0, 'suppressor')}
# their DoomEdNum order (one class per rank and gun, then the random spawner): appended to MAIN's late_order, never re-sorted
KNIGHT_ORDER = [f'HCE_SentinelKnight{r.capitalize()}{"".join(w.capitalize() for w in g.split())}' for r in KNIGHT_RANKS for g in KNIGHT_GUNS] \
    + ['HCE_RandomSentinelKnight']
if os.path.exists(KNIGHT_JSON):
    _base = AI['variants'][r'characters\elite\elite major\elite major plasma rifle']
    CHAR_OF_UNIT[KNIGHT] = 'SentinelKnight'; TEAM['SentinelKnight'] = 'SENTINEL'
    AI['actors'][KNIGHT] = copy.deepcopy(AI['actors'][_base['actor_reference']])
    _kb = copy.deepcopy(AI['bipeds'][_base['unit_reference']])
    _kb.update(collision_height_standing=0.95, collision_radius=0.32); _kb['change_colors_list'] = []
    AI['bipeds'][KNIGHT] = _kb
    for _r, _rd in KNIGHT_RANKS.items():
        for _g, (_ref, _lo, _hi, _surf) in KNIGHT_GUNS.items():
            _v = copy.deepcopy(_base)
            _v['unit_reference'] = KNIGHT; _v['actor_reference'] = KNIGHT
            _v['unit'] = dict(_v['unit'], maximum_body_vitality=float(_rd['body']), maximum_shield_vitality=float(_rd['shield']))
            _v['ranged_combat']['reference'] = _ref
            _v['ranged_combat'].update(combat_range_lower_bound=_lo, combat_range_upper_bound=_hi, maximum_firing_range=max(_hi * 1.6, 12.0))
            _v['items']['grenades_lower_bound'] = 0; _v['items']['grenades_upper_bound'] = 0
            _v['grenade_combat']['throw_grenade_chance'] = 0.0
            _v['change_colors'] = None; _v['change_colors_list'] = []
            _v['_rank'] = _r; _v['_late'] = True; _v['_knight_gun'] = _surf
            _v['_ov'] = dict(pellets=6) if _g == 'scattershot' else {}
            if _r == 'commander': _v['_ov']['code'] = '\toverride int HCE_KnightPalette() { return 1; }    // warm core colours\n'
            AI['variants'][f'{KNIGHT} {_r} {_g}'] = _v

# Halo 2's Sentinels (extract_h2_sentinels.py, 06b_floodzone): the Aggressor's model stands in for the Halo CE Sentinel's
# (same classes, numbers and stats; the rank colours Halo 2's biped gives: minor steel blue, captain gold; the shielded
# ranks wear its shield bubble while their shield holds), plus the Eliminator (Halo 2's shielded Aggressor with the
# heavier beam: 120 body, 60 shield, the CE Sentinels' two-to-one scale of Halo 2's 60 / 30) and the Enforcer (600 body,
# Halo 2's normal vitality; two energy shields across its front, the needler's hard-light bolts, rocket salvoes, the
# grapple at close range; scaled to 0.6 to fit Doom's corridors)
SENTINEL_JSON = f'{OUT}/models/Sentinel/Sentinel.json'
H2_SENTINEL = os.path.exists(SENTINEL_JSON) and json.load(open(SENTINEL_JSON)).get('source') == 'h2'
# Halo CE Sentinel variant -> its rank key (the skin's change colour, h2sentinel_skin; the bubble's SHIELD_TINT)
SENTINEL_RANKS = {r'characters\sentinel\sentinel': 'sentinel_minor', r'characters\sentinel\sentinel major': 'sentinel_captain',
                  r'characters\sentinel\sentinel_defensive': 'sentinel_minor', r'characters\sentinel\sentinel_shielded': 'sentinel_minor',
                  r'characters\sentinel\sentinel_shielded major': 'sentinel_captain'}
ENFORCER = r'objects\characters\sentinel_enforcer\sentinel_enforcer'
ENFORCER_JSON = f'{OUT}/models/SentinelEnforcer/SentinelEnforcer.json'
SENTINEL_ORDER = ['HCE_SentinelEliminator', 'HCE_SentinelEnforcer', 'HCE_SentinelConstructor']   # their DoomEdNum order (late_order)
NO_RANDOM = {'SentinelEnforcer', 'SentinelConstructor'}     # one class each: no random spawner
# classes kept out of their character's random spawner (still placeable): the double barrel is Fire Team Raven's and
# Sergeant Stacker's gun, so the regular Marines don't spawn with it
RANDOM_EXCLUDE = {'HCE_MarineDoubleBarrel', 'HCE_MarineArmoredDoubleBarrel'}
CONSTRUCTOR = r'objects\characters\sentinel_constructor\sentinel_constructor'
CONSTRUCTOR_JSON = f'{OUT}/models/SentinelConstructor/SentinelConstructor.json'
SENTINEL_BUBBLE = "\toverride bool HCE_HasBubble() { return true; }    // Halo 2's shield bubble\n"
if H2_SENTINEL:
    for _k, _r in SENTINEL_RANKS.items():
        if _k in AI['variants']: AI['variants'][_k]['_rank'] = _r
    for _k in (r'characters\sentinel\sentinel_shielded', r'characters\sentinel\sentinel_shielded major'):
        if _k in AI['variants']: AI['variants'][_k]['_ov'] = dict(AI['variants'][_k].get('_ov') or {}, code=SENTINEL_BUBBLE)
    _v = copy.deepcopy(AI['variants'][r'characters\sentinel\sentinel_shielded major'])
    _v['unit'] = dict(_v['unit'], maximum_body_vitality=120.0, maximum_shield_vitality=60.0)
    _v['ranged_combat']['weapon_damage_modifier'] = 1.75
    _v['_rank'] = 'sentinel_captain'; _v['_late'] = True; _v['_ov'] = dict(code=SENTINEL_BUBBLE)
    AI['variants'][r'characters\sentinel\sentinel eliminator'] = _v
if os.path.exists(ENFORCER_JSON):
    _base = AI['variants'][r'characters\sentinel\sentinel']
    CHAR_OF_UNIT[ENFORCER] = 'SentinelEnforcer'; TEAM['SentinelEnforcer'] = 'SENTINEL'
    AI['actors'][ENFORCER] = copy.deepcopy(AI['actors'][_base['actor_reference']])
    _eb = copy.deepcopy(AI['bipeds'][_base['unit_reference']]); _eb['change_colors_list'] = []
    AI['bipeds'][ENFORCER] = _eb
    _v = copy.deepcopy(_base)
    _v['unit_reference'] = ENFORCER; _v['actor_reference'] = ENFORCER
    _v['unit'] = dict(_v['unit'], maximum_body_vitality=600.0, maximum_shield_vitality=0.0)
    _v['ranged_combat']['reference'] = r'weapons\enforcer needler\enforcer needler'
    _v['ranged_combat'].update(combat_range_lower_bound=4.0, combat_range_upper_bound=20.0, maximum_firing_range=32.0)
    _v['change_colors'] = None; _v['change_colors_list'] = []
    _v['items']['grenades_lower_bound'] = 0; _v['items']['grenades_upper_bound'] = 0
    _v['grenade_combat']['throw_grenade_chance'] = 0.0
    _v['_rank'] = 'enforcer'; _v['_late'] = True
    AI['variants'][r'objects\characters\sentinel_enforcer\sentinel enforcer'] = _v      # -> HCE_SentinelEnforcer
# the Constructor: Halo 2's little builder drone in the Lost Souls' place (30 body, no shield, no gun: it darts and welds)
if os.path.exists(CONSTRUCTOR_JSON):
    _base = AI['variants'][r'characters\sentinel\sentinel']
    CHAR_OF_UNIT[CONSTRUCTOR] = 'SentinelConstructor'; TEAM['SentinelConstructor'] = 'SENTINEL'
    AI['actors'][CONSTRUCTOR] = copy.deepcopy(AI['actors'][_base['actor_reference']])
    _cb = copy.deepcopy(AI['bipeds'][_base['unit_reference']]); _cb['change_colors_list'] = []
    AI['bipeds'][CONSTRUCTOR] = _cb
    _v = copy.deepcopy(_base)
    _v['unit_reference'] = CONSTRUCTOR; _v['actor_reference'] = CONSTRUCTOR
    _v['unit'] = dict(_v['unit'], maximum_body_vitality=30.0, maximum_shield_vitality=0.0)
    _v['ranged_combat']['reference'] = None
    _v['change_colors'] = None; _v['change_colors_list'] = []
    _v['items']['grenades_lower_bound'] = 0; _v['items']['grenades_upper_bound'] = 0
    _v['grenade_combat']['throw_grenade_chance'] = 0.0
    _v['_rank'] = 'constructor'; _v['_late'] = True
    AI['variants'][r'objects\characters\sentinel_constructor\sentinel constructor'] = _v   # -> HCE_SentinelConstructor

# Galap's Sentinels (extract_galap_sentinels.py -> galap_ai.json): custom Halo CE Sentinels, each its own body, with
# the stats of Galap's actor variants. Their guns: Galap's Sentinel needler is the Enforcer's hard-light needles, the
# blue beam and the Beam Gunner's the Sentinel beam, the Lancer's incinerator a flamethrower. The shielded ones wear
# the hard-light shield lattice while it holds (sentinel_h2.zs); the ally variants fight on the player's side.
GALAP_AI = f'{OUT}/galap_ai.json'
# Galap's weapon tag (its leaf name) -> the weapon ref the pack fires it as (WEAPONS / the Sentinel beam)
GALAP_WEAPONS = {'sentinel_needler': r'weapons\enforcer needler\enforcer needler', 'sentinel_beam_blue': r'characters\sentinel\sentinel',
                 'sentinel_beam_gunner': r'characters\sentinel\sentinel', 'sentinel': r'characters\sentinel\sentinel',
                 'sentinel_incinerator': r'weapons\flamethrower\flamethrower'}
# Galap's variant -> the pack's name (cname: HCE_<words>)
GALAP_NAMES = {'sentinel_soldier': 'sentinel soldier', 'sentinel_soldier_ally': 'sentinel soldier ally',
               'sentinel_dragoon': 'sentinel dragoon', 'sentinel_dragoon_ally': 'sentinel dragoon ally',
               'sentinel_gold': 'sentinel gold', 'sentinel_gold_major': 'sentinel gold major',
               'sentinel_gold_shielded': 'sentinel gold shielded', 'sentinel_gold_shielded major': 'sentinel gold shielded major',
               'sentinel_onyx': 'sentinel onyx', 'sentinel_warden': 'sentinel warden', 'sentinel_protector': 'sentinel protector',
               'sentinel_lancer': 'sentinel lancer', 'sentinel_interceptor': 'sentinel interceptor', 'sentinelmarauder': 'sentinel marauder',
               'sentinel_crawler': 'sentinel crawler'}
# Galap's beam gunners are not enemies of their own: CE gives a body one weapon, so he seats invisible gunner bipeds on a
# Sentinel's markers to give it more (the bipeds' 'gunseat' seats, from the biped tags). Here the host fires them itself
# (HCE_GunnerSeat): host variant -> (its markers, the gunner's actor variant, whose burst and damage the beam takes)
GALAP_GUNNERS = {'sentinel soldier': (('beam gun a', 'beam gun b'), 'sentinel_beam_gunner'),
                 'sentinel soldier ally': (('beam gun a', 'beam gun b'), 'sentinel_beam_gunner_ally'),
                 'sentinel dragoon': (('beam gun',), 'sentinel_beam_gunner_heavy'),
                 'sentinel dragoon ally': (('beam gun',), 'sentinel_beam_gunner_ally_heavy')}
GALAP_ORDER = ['HCE_' + ''.join(w.capitalize() for w in n.split()) for n in GALAP_NAMES.values()]   # DoomEdNum order (late_order)
GALAP_CHARS = set()     # the Galap characters whose models exist (filled below; SENTINEL_LIKE, skins, overrides)
if os.path.exists(GALAP_AI):
    _G = json.load(open(GALAP_AI))
    _base = AI['variants'][r'characters\sentinel\sentinel']
    for _u, _c in _G['unit_char'].items():
        if _u not in _G['bipeds'] or not os.path.exists(f'{OUT}/models/{_c}/{_c}.json'): continue
        CHAR_OF_UNIT[_u] = _c; TEAM[_c] = 'SENTINEL'; GALAP_CHARS.add(_c)
        _b = copy.deepcopy(AI['bipeds'][_base['unit_reference']]); _b.update({k: v for k, v in _G['bipeds'][_u].items() if v is not None})
        _b['change_colors_list'] = _G['bipeds'][_u].get('change_colors_list') or []
        AI['bipeds'][_u] = _b
    for _k, _v in _G['variants'].items():
        _leaf = _k.split('\\')[-1]
        if _v['unit_reference'] not in CHAR_OF_UNIT or _leaf not in GALAP_NAMES: continue
        _v = copy.deepcopy(_v)
        _ar = _v['actor_reference']
        AI['actors'][_ar] = _G['actors'].get(_ar) or AI['actors'].get(_ar) or copy.deepcopy(AI['actors'][_base['actor_reference']])
        _w = (_v['ranged_combat'].get('reference') or 'sentinel').split('\\')[-1]
        _v['ranged_combat']['reference'] = GALAP_WEAPONS.get(_w, r'characters\sentinel\sentinel')
        for _f in ('items', 'grenade_combat'):
            if not isinstance(_v.get(_f), dict): _v[_f] = copy.deepcopy(_base[_f])
        _v['items']['grenades_lower_bound'] = 0; _v['items']['grenades_upper_bound'] = 0
        _v['grenade_combat']['throw_grenade_chance'] = 0.0
        if not _v['unit'].get('maximum_body_vitality'): _v['unit'] = dict(_v['unit'], maximum_body_vitality=60.0 if 'heavy' in GALAP_NAMES[_leaf] else 35.0)
        _v['_late'] = True; _v['_rank'] = 'sentinel_minor'
        _v['_ov'] = dict(ally=True) if 'ally' in GALAP_NAMES[_leaf] else {}
        _code = ''
        if (_v['unit'].get('maximum_shield_vitality') or 0) > 0: _code += SENTINEL_BUBBLE
        if 'ally' in GALAP_NAMES[_leaf]:       # on the human team, it would roll a Marine's name: a Monitor's designation instead
            _code += ('\toverride void HCE_RollName() { String l = "ABCDEFGH"; hce_rankName = String.Format("Sentinel %d-%s%d", '
                      'random(100, 999), l.Mid(random(0, 7), 1), random(1, 9)); }\n')
        if _code: _v['_ov']['code'] = _code
        AI['variants'][rf'characters\{GALAP_NAMES[_leaf]}\{GALAP_NAMES[_leaf]}'] = _v

# Halo weapon -> (pack projectile class, HDE base class, Halo impact damage, Halo projectile speed WU/tick)
# The key is the weapon tag's leaf name (wname of ranged_combat.reference). Damage None keeps the HDE base's own.
# A new weapon needs an entry here and in PATTERNS and FIRE_SOUNDS (DROP_WEAPON if the body drops it, FIRE_CODE if its
# fire animation has its own code); the projectile class is written by build() into hce_projectiles.zsc
WEAPONS = {
    'plasma pistol':    ('HCE_PlasmaPistolBolt', 'HaloPlasma_Proj', 18, 0.83),
    'plasma rifle':     ('HCE_PlasmaRifleBolt', 'HaloPlasmaRifle_Proj', 13, 1.67),
    'needler':          ('HCE_Needle', 'HCE_NeedleScaled', None, 0.13),
    'fuel rod':         ('HCE_FuelRodBolt', 'HCE_FuelRodScaled', None, 0.47),
    'hunter fuel rod':  ('HCE_FuelRodBolt', 'HCE_FuelRodScaled', None, 0.47),
    'assault rifle':    ('HCE_ARBullet', 'HaloMAB_Bullet', 10, 10.8),
    'pistol':           ('HCE_PistolBullet', 'HaloSidekick_Bullet', 25, 10.0),
    'shotgun':          ('HCE_ShotgunPellet', 'HaloShotgun_Bullet', 20, 4.67),
    'sniper rifle':     ('HCE_SniperBullet', 'HaloSniper_Bullet', 101, 33.3),
    'rocket launcher':  ('HCE_Rocket', 'HCE_RocketScaled', None, 0.4),
    'flamethrower':     ('HCE_Flame', 'HaloFlames', None, 0.33),
    'plasma caster':    ('HCE_PlasmaCasterGrenade', 'HCE_PlasmaCasterScaled', None, 0.28),   # White Hunter (HDE weapon)
    # the Sentinel Knights' Forerunner arm guns: hard-light bolts (HDE's Scattershot bolt, in each gun's light colour;
    # HARDLIGHT_CODE). The Light Rifle fires three-round bursts, the Scattershot six bouncing bolts, the Binary Rifle one
    # heavy bolt, the Suppressor long automatic strings
    'light rifle':      ('HCE_LightRifleBolt', 'HCE_HardlightBlue', 18, 6.0),
    'scattershot':      ('HCE_ScattershotBolt', 'HCE_HardlightViolet', 9, 2.4),
    'binary rifle':     ('HCE_BinaryRifleBolt', 'HCE_HardlightGreen', 90, 16.0),
    'suppressor':       ('HCE_SuppressorBolt', 'HCE_HardlightCyan', 8, 4.0),
    'enforcer needler': ('HCE_EnforcerNeedle', 'HCE_HardlightCyan', 6, 3.0),     # the Sentinel Enforcer's needle bolts
}
# hard-light bolt bases (in the core, with the projectiles): HDE's Scattershot bolt; only the Scattershot's keep its bounce
HARDLIGHT_CODE = '''
// Forerunner hard light (the Sentinel Knights' arm guns): HaloDoom Evolved's Scattershot bolt sprite and burst,
// recoloured per gun, with a trail sized to the bolt (HDE's trail is fixed for its own big Scattershot ball)
class HCE_Hardlight : HaloSlowProjectile
{
	Color hce_burst;
	class<LightningBiri> hce_arc;
	Property Burst : hce_burst;
	Property Arc : hce_arc;
	Default
	{
		RenderStyle "Add";
		Alpha 1.0;
		Scale 0.009;
		DamageType "Plasma";
		+ROLLSPRITE;
		+INTERPOLATEANGLES;
		HCE_Hardlight.Burst "Blue";
		HCE_Hardlight.Arc "LightRifle_Lightning";
	}
	override void Tick()
	{
		super.Tick();
		if(level.isFrozen() || !bMISSILE) return;
		A_SetRoll(roll + 5, SPF_INTERPOLATE);
		let tr = Spawn("HCE_HardlightTrail", pos);
		if(tr) { tr.translation = translation; tr.A_SetScale(scale.x * 0.9); }
	}
	States
	{
	Spawn:
		ELBL AB 2 Bright A_JumpIf(!bMISSILE, "Death");
		loop;
	Death:
	XDeath:
	Crash:
		TNT1 A 1
		{
			HaloMath.ParticlesFX(self, hce_burst, 20, 3, 8);
			for(int i = 0; i < 3; i++)
				BiriBiri.DoLightning(pos, (angle + frandom(-60, 60) + 180, pitch + frandom(-35, 35)), hce_arc, 20, 0.5, 20.0, 10.0, 30, 0);
		}
		stop;
	}
}
class HCE_HardlightTrail : CheapActor
{
	Default { RenderStyle "Add"; Alpha 0.8; +ROLLSPRITE; +NOGRAVITY; }
	override void Tick()
	{
		super.Tick();
		A_SetRoll(roll + 5, SPF_INTERPOLATE);
		A_SetScale(scale.x * 0.88);
		alpha *= 0.85;
		if(alpha <= 0.05) Destroy();
	}
	States { Spawn: ELBL AB 2 Bright; loop; }
}
class HCE_HardlightBlue : HCE_Hardlight { Default { Translation "0:255=@64[0,97,255]"; } }
class HCE_HardlightGreen : HCE_Hardlight { Default { Scale 0.014; Translation "0:255=@64[0,255,76]"; HCE_Hardlight.Burst "Green"; HCE_Hardlight.Arc "BinaryRifle_Lightning"; } }
class HCE_HardlightCyan : HCE_Hardlight { Default { Scale 0.007; Translation "0:255=@64[0,150,255]"; HCE_Hardlight.Burst "LightBlue"; } }
class HCE_HardlightViolet : HCE_Hardlight
{
	Default
	{
		Scale 0.010; Translation "0:255=@64[145,0,249]"; HCE_Hardlight.Burst "Purple"; HCE_Hardlight.Arc "ScatterShot_PurpleLightning";
		BounceType "Doom"; BounceCount 3; +BOUNCEONWALLS; +BOUNCEONFLOORS; +BOUNCEONCEILINGS; -BOUNCEONACTORS;
	}
}
'''
# projectile bases that are HaloSlowProjectile (their damage property is HaloSlowProjectile.BaseDamage, not HaloProjectile's)
SLOW_PROJ = {'HCE_HardlightBlue', 'HCE_HardlightGreen', 'HCE_HardlightCyan', 'HCE_HardlightViolet'}
# weapon -> the two-letter code in Halo CE's fire animation names ('stand rifle fire-1 pr baked'): anim_table picks the
# stance's fire animation shot with this code first. A weapon with no code takes any fire animation of the stance
FIRE_CODE = {'plasma pistol': 'pp', 'plasma rifle': 'pr', 'needler': 'ne', 'fuel rod': 'fr', 'hunter fuel rod': 'fr',
             'assault rifle': 'ar', 'shotgun': 'sg', 'pistol': 'hp', 'sniper rifle': 'sr'}
# Fire patterns (Doom-paced; Halo's per-variant numbers only stretch them):
# weapon: (shots min, shots max, tics between shots, pause min s, pause max s,
#          overcharge wind-up tics, scale shots with Halo burst length,
#          Halo baseline separation s, Halo baseline burst s)
# build() writes them as HCE_FirePattern: the pause is scaled by the variant's burst separation against the baseline
# (0.75x to 1.3x), the shot count by its burst length when the scale flag is set (0.75x to 1.6x). To make a gun fire
# faster or longer for everyone carrying it, edit its row here; for one variant, its burst_geometry in the add_*
PATTERNS = {
    'needler':         (3, 3, 12, 1.6, 2.6, 0, False, 1.0, 1.1),   # semi-auto cadence
    'plasma pistol':   (2, 4, 7, 1.1, 1.9, 28, False, 1.2, 0.5),
    'plasma rifle':    (4, 7, 4, 0.9, 1.6, 0, True, 0.9, 0.9),
    'fuel rod':        (1, 1, 1, 2.6, 3.4, 0, False, 2.5, 0.1),
    'hunter fuel rod': (1, 1, 1, 2.2, 3.2, 0, False, 2.0, 0.1),
    'assault rifle':   (5, 9, 3, 0.8, 1.4, 0, True, 1.0, 2.0),
    'pistol':          (2, 3, 9, 0.9, 1.5, 0, False, 1.0, 2.0),
    'shotgun':         (1, 1, 1, 1.4, 2.0, 0, False, 2.2, 0.1),
    'sniper rifle':    (1, 1, 1, 2.6, 3.6, 0, False, 1.0, 0.1),
    'rocket launcher': (1, 1, 1, 3.2, 4.2, 0, False, 3.5, 0.1),
    'flamethrower':    (18, 30, 2, 1.2, 2.0, 0, True, 2.5, 4.5),
    'sentinel beam':   (20, 35, 1, 1.0, 1.8, 0, False, 1.0, 1.0),
    'plasma caster':   (1, 2, 18, 2.4, 3.4, 30, False, 2.0, 0.1),   # lobbed; charged = 3-grenade cluster
    'light rifle':     (3, 6, 3, 1.2, 2.0, 0, False, 1.0, 0.3),    # three-round bursts, a pull or two (HCE_TriggerBurst)
    'scattershot':     (1, 1, 1, 1.4, 2.2, 0, False, 2.0, 0.1),
    'binary rifle':    (1, 1, 1, 3.0, 4.2, 0, False, 1.0, 0.1),
    'suppressor':      (8, 14, 3, 1.0, 1.6, 0, True, 1.0, 2.0),
    'enforcer needler': (10, 16, 2, 1.4, 2.4, 0, True, 1.0, 2.0),   # long strings from both arms
}
# HDE SNDINFO names: fire, fire bass, special (overcharge / loop end), charge (overcharge / loop start), looping
# (weapon -> HCE_FireSounds and HCE_FireLoop; '' for none). The HCE/... names are shipped by split_factions.py
W = 'Halo/Weapons/'
FIRE_SOUNDS = {
    'plasma pistol':   (W + 'PlasmaPistol/Fire', W + 'PlasmaPistol/Fire/Bass', W + 'PlasmaPistol/Fire/Charged', W + 'PlasmaPistol/Charge/Start', False),
    'plasma rifle':    (W + 'PlasmaRifle/Fire', W + 'PlasmaRifle/Fire/Bass', '', '', False),
    'needler':         (W + 'Needler/Fire', W + 'Needler/Fire/Bass', '', '', False),
    'fuel rod':        (W + 'FuelRod/Fire', W + 'FuelRod/Fire/Bass', '', '', False),
    'hunter fuel rod': (W + 'FuelRod/Fire', W + 'FuelRod/Fire/Bass', '', '', False),
    'assault rifle':   (W + 'MA5B/Fire', W + 'MA5B/Fire/Bass', '', '', False),
    'pistol':          (W + 'Mag_MD6/Fire', W + 'Mag_MD6/Fire/Bass', '', '', False),
    'shotgun':         (W + 'Shotgun/Fire', W + 'Shotgun/Fire/Bass', '', '', False),
    'sniper rifle':    (W + 'Sniper/Fire', W + 'Sniper/Fire/Bass', '', '', False),
    'rocket launcher': (W + 'RocketLauncher/Fire', '', '', '', False),
    'flamethrower':    (W + 'Flamer/Fire/Loop', '', W + 'Flamer/Fire/End', W + 'Flamer/Fire/Start', True),
    'plasma caster':   (W + 'PlasmaCaster/Fire', '', W + 'PlasmaCaster/ChargedFire', W + 'PlasmaCaster/ChargeBegin', False),
    'sentinel beam':   (W + 'SentinelBeam/Fire/Loop', '', W + 'SentinelBeam/Fire/End', W + 'SentinelBeam/Fire/Begin', True),   # HDE's Sentinel Beam
    'light rifle':     (W + 'LightRifle/Fire', W + 'LightRifle/Fire/Bass', '', '', False),
    'scattershot':     (W + 'ScatterShot/Fire', W + 'ScatterShot/Fire/Bass', '', '', False),
    'binary rifle':    (W + 'BinaryRifle/Fire', W + 'BinaryRifle/Fire/Bass', '', '', False),
    'suppressor':      ('HCE/Suppressor/Fire', 'HCE/Suppressor/Fire/Bass', '', '', False),   # HDE's Suppressor (split_factions.py ships it)
    'enforcer needler': ('HCE/Suppressor/Fire', 'HCE/Suppressor/Fire/Bass', '', '', False),   # the Enforcer's hard-light bolts: HDE's Suppressor
}
# Halo-style drops: HDE Local_DEV pickup classes (Covenant always drop theirs, the energy sword included -- HDE has
# one to pick up; Hunters' fuel rod arms and Sentinels drop nothing)
DROP_WEAPON = {'energy sword': 'Halo_EnergySword', 'plasma pistol': 'Halo_PlasmaPistol', 'plasma rifle': 'Halo_PlasmaRifle', 'needler': 'Halo_Needler',
               'fuel rod': 'Halo_FuelRod', 'assault rifle': 'Halo_MA5B', 'pistol': 'Halo_Magnum', 'shotgun': 'Halo_Shotgun',
               'sniper rifle': 'Halo_SniperRifle', 'rocket launcher': 'Halo_RocketLauncher', 'flamethrower': 'Halo_Flamethrower',
               'light rifle': 'Halo_LightRifle', 'scattershot': 'Halo_ScatterShot', 'binary rifle': 'Halo_BinaryRifle'}
# Doom boss stand-ins: unique subclasses so CheckReplacee can map them back to the Doom boss
# (A_BossDeath map specials: E1M8/E4M6 Barons, MAP07 Mancubi/Arachnotrons, Cyberdemon/Spider levels)
# (the handler spawns these in place of the Doom boss on those maps; add an entry to give another level's boss a stand-in)
BOSS_ALIASES = {  # alias class: (base class, Doom class, health multiplier)
    'HCE_BossBaronEliteMajorPlasmaRifle': ('HCE_EliteMajorPlasmaRifle', 'BaronOfHell', 1.5),
    'HCE_BossBaronEliteMajorNeedler': ('HCE_EliteMajorNeedler', 'BaronOfHell', 1.5),
    'HCE_BossFatsoHunter': ('HCE_Hunter', 'Fatso', 1.0),
    'HCE_BossArachnotronEliteSpecopsPlasmaRifle': ('HCE_EliteSpecopsPlasmaRifle', 'Arachnotron', 1.0),
    'HCE_BossArachnotronEliteSpecopsNeedler': ('HCE_EliteSpecopsNeedler', 'Arachnotron', 1.0),
    'HCE_BossCyberdemonHunter': ('HCE_Hunter', 'Cyberdemon', 3.0),
    'HCE_BossCyberdemonHunterMajor': ('HCE_HunterMajor', 'Cyberdemon', 3.0),
    'HCE_BossCyberdemonHunterUltra': ('HCE_HunterUltra', 'Cyberdemon', 3.0),
    'HCE_BossFatsoHunterMajor': ('HCE_HunterMajor', 'Fatso', 1.0),
    'HCE_BossFatsoHunterUltra': ('HCE_HunterUltra', 'Fatso', 1.0),
    'HCE_BossSpiderEliteCommanderPlasmaRifle': ('HCE_EliteCommanderPlasmaRifle', 'SpiderMastermind', 4.0),
    'HCE_BossBaronFloodJuggernaut': ('HCE_FloodJuggernaut', 'BaronOfHell', 1.0),
}
# character -> its voice sets (HCE_Voices: comma-separated, one rolled per enemy at spawn; the names are the SNDINFO
# prefixes build_voices.py / split_factions.py ship). A variant's '_ov' voices key overrides its character's
VOICES = {'Grunt': 'Grunt_Crazy,Grunt_Whiley,Grunt_Whimpy', 'GruntSpecOps': 'Grunt_Crazy,Grunt_Whiley,Grunt_Whimpy',
          'Elite': 'Elite_Dogmatic,Elite_Loose', 'EliteSpecial': 'Elite_Dogmatic,Elite_Loose',
          'Jackal': 'Jackal', 'JackalMajor': 'Jackal', 'Hunter': 'Hunter',
          # Marines: a random white Marine's voice from Halo CE and Halo 2 (Sergeant Johnson's face: always Johnson, marine_code)
          'Marine': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Cross,Marine_Perez,Marine_Timid,Marine_SgtCautious',
          'MarineArmored': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Cross,Marine_Perez,Marine_Timid,Marine_SgtCautious',
          'MarineODST': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Cross,Marine_Perez,Marine_Timid,Marine_SgtCautious',
          # the Flood (extract_spv3.flood_sounds, shipped in the Flood pack by split_factions.py): the combat forms' growls,
          # the infection forms' squeals and the carriers' gurgles, and the XAM Campaign Overhaul's own (human and Elite idles,
          # the Flood Grunt's attack)
          'FloodHuman': 'Flood', 'FloodODST': 'Flood', 'FloodMarine': 'Flood', 'FloodArmored': 'Flood',
          'FloodElite': 'FloodElite', 'FloodEliteArmored': 'FloodElite', 'FloodEliteCommander': 'FloodElite', 'FloodEliteUltra': 'FloodElite',
          'FloodInfection': 'FloodInfection', 'FloodCarrier': 'FloodCarrier', 'FloodGrunt': 'FloodGrunt',
          'FloodJuggernaut': 'FloodJuggernaut', 'FloodBrute': 'Flood'}
from extract_weapons import WEAPONS as WEAPON_IDS     # Halo weapon tag path -> the extracted weapon's id (out/weapons/<id>)
# melee damage of a weapon swung as one (HCE_Melee); an unlisted gun hits for 55, an unarmed body by character (build)
MELEE = {'energy sword': 151, 'flamethrower': 75}
# projectile bases that aren't HDE HaloProjectile/HaloSlowProjectile (or already carry the nerf mixin)
NO_NERF_MIXIN = {'HCE_FuelRodScaled', 'HaloFlames', 'HCE_PlasmaCasterScaled', 'HCE_NeedleScaled', 'HCE_RocketScaled', 'HCE_BeamPuff', 'HCE_PulseCarbineHoming'}
# Halo's actor type field -> the kind whose behaviour flags build() gives the class (HCE_Surprise, HCE_Berserks, HCE_Panics
# ...: the 'emotions' block). A variant's '_ov' flags key replaces the set, add_flags extends it
ACTOR_TYPES = {0: 'elite', 1: 'jackal', 2: 'grunt', 3: 'hunter', 4: 'engineer', 7: 'marine', 8: 'crew',
               9: 'flood', 10: 'infection', 11: 'carrier', 12: 'monitor', 13: 'sentinel'}

# Blood by species (Halopedia, "Blood"; Halo CE colours where the games differ). NashGore and Doom's own
# blood both use BloodColor, so gore mods paint each race correctly. Sentinels are machines: no blood.
BLOOD = {
    'Elite': '3A1E8C', 'EliteSpecial': '3A1E8C', 'EliteRifle': '3A1E8C', 'EliteZealot': '3A1E8C',   # Sangheili: dark blue/purple (CE)
    'Jackal': '4A2A9A', 'JackalMajor': '4A2A9A', 'H2Jackal': '4A2A9A',    # Kig-Yar: dark blue/purple (CE)
    'Grunt': '40C8D0', 'GruntSpecOps': '40C8D0',                          # Unggoy: light blue / teal
    'Hunter': 'FF8C1A',                                                   # Mgalekgolo: bright orange
    'Brute': '161C40',                                                    # Jiralhanae (Halo 2): dark navy blue / black
    'Drone': 'DDF0D2',                                                    # Yanme'e: white, slight green tint
    'Engineer': 'E0607A',                                                 # Huragok: reddish pink
    'FloodInfection': '76703A', 'FloodCarrier': '76703A', 'FloodGrunt': '76703A', 'FloodODST': '76703A', 'FloodMarine': '76703A', 'FloodArmored': '76703A',
    'FloodEliteArmored': '76703A', 'FloodEliteCommander': '76703A', 'FloodEliteUltra': '76703A', 'FloodJuggernaut': '76703A', 'FloodElite': '76703A', 'FloodHuman': '76703A', 'FloodBrute': '76703A',  # Flood: brownish green
    'Marine': 'A01010', 'MarineArmored': 'A01010', 'MarineODST': 'A01010',   # human: red
    'SlugMan': 'FF8C1A',                                                  # Slug Men: a Mgalekgolo sub-species, Hunter orange
    'Drinol': '8A1A10', 'BlindWolf': 'A01010',  # Digsite / SPV3 creatures
}
NO_BLOOD = {'Sentinel'}     # characters that get +NOBLOOD (machines); the optional Sentinel bodies add themselves below
SENTINEL_LIKE = {'Sentinel'} | (GALAP_CHARS - {'SentinelCrawler'})     # flying Sentinel bodies: the fixed stance, hovering, the beam
# the Sentinels' own sounds from the official games (extract_sentinel_sounds.py, shipped by split_factions.py as
# HCE/Sentinel/<event>): engine hum, a hit on the hull, the death. Halo CE's for its Sentinel and Galap's (the Crawler
# walks: no hum), Halo 2's for its Enforcer and Constructor
SENTINEL_UNIT_SOUNDS = {c: ('HCE/Sentinel/Engine', 'HCE/Sentinel/Hit', 'HCE/Sentinel/Death') for c in SENTINEL_LIKE}
SENTINEL_UNIT_SOUNDS['SentinelCrawler'] = ('', 'HCE/Sentinel/Hit', 'HCE/Sentinel/Death')
SENTINEL_UNIT_SOUNDS['SentinelEnforcer'] = ('HCE/Sentinel/EnforcerEngine', 'HCE/Sentinel/Hit', 'HCE/Sentinel/H2Death')
SENTINEL_UNIT_SOUNDS['SentinelConstructor'] = ('HCE/Sentinel/ConstructorEngine', 'HCE/Sentinel/Hit', 'HCE/Sentinel/H2Death')
if H2_SENTINEL:          # the Sentinel wears Halo 2's Aggressor: Halo 2's Aggressor engine hum
    SENTINEL_UNIT_SOUNDS['Sentinel'] = ('HCE/Sentinel/H2Engine', 'HCE/Sentinel/Hit', 'HCE/Sentinel/Death')
# every Sentinel with unit sounds swings with Halo 2's Sentinel melee sound (HCE_MeleeSound)
SENTINEL_MELEE = 'HCE/Sentinel/H2Melee'

def blood_props(char):
    """the Default lines giving a character's base class its blood: +NOBLOOD (NO_BLOOD), else BloodColor from BLOOD and
    the Halo blood type; '' for a character in neither table"""
    if char in NO_BLOOD: return '\t\t+NOBLOOD\n'
    c = BLOOD.get(char)
    if not c: return ''
    # Halo blood with NashGore loaded (hce_core.zsc HCE_HaloBlood; the Flood keep NashGore's own)
    bt = '' if char.startswith('Flood') else '\t\tBloodType "HCE_HaloBlood";\n'
    return f'\t\tBloodColor "{c[0:2]} {c[2:4]} {c[4:6]}";\n' + bt

# Ruby's Rebalance's armoured Flood Elites (build_digsite.py) keep their rank's change colour on the armour
FLOOD_RANKED = ('FloodEliteArmored', 'FloodEliteCommander', 'FloodEliteUltra')

def cname(s):
    """a variant's tag path -> its class name: the leaf, each word capitalised, 'HCE_' in front
    ('characters\\elite\\elite minor\\elite minor plasma rifle' -> 'HCE_EliteMinorPlasmaRifle')"""
    s = s.split('\\')[-1]
    return 'HCE_' + ''.join(w.capitalize() for w in re.split(r'[^a-zA-Z0-9]+', s) if w)

def wname(ref):
    """a weapon tag path -> the weapon's name, the key of WEAPONS / PATTERNS / FIRE_SOUNDS ('weapons\\needler\\needler'
    -> 'needler'); None for no weapon"""
    return ref.split('\\')[-1] if ref else None

# ---------------------------------------------------------------- animations
class AnimSet:
    """the animations a model's JSON lists (meta['anims']: name -> frames, speed, move), looked up by name"""
    def __init__(s, meta):
        """meta: the model's JSON (out/models/<Char>/<Char>.json)"""
        s.meta = meta; s.names = list(meta['anims'])
    def find(s, *pats):
        """first pattern that matches; returns list of variants (name%0, name%1 ...)"""
        for p in pats:
            exact = [n for n in s.names if n == p or re.fullmatch(re.escape(p) + r'(%\d+)?', n)]
            if exact: return sorted(exact)
        return []
    def find_contains(s, *parts, suffix=''):
        """every animation name containing all the parts (and ending with suffix), sorted"""
        return sorted(n for n in s.names if all(x in n for x in parts) and n.endswith(suffix))
    def tics(s, n):
        """an animation's length in Doom tics (Halo runs 30 frames a second, Doom 35 tics)"""
        return max(1, int(round(s.meta['anims'][n]['frames'] / TICK)))
    def speed(s, n):
        """how fast an animation moves the body, in map units per tic (0 for an unknown name)"""
        return s.meta['anims'][n]['speed'] * S / TICK if n in s.meta['anims'] else 0

def anim_table(A, w, weapon):
    """{kind (KINDS): [animation names]} for a body in stance w ('pistol', 'rifle', 'unarmed', 'fixed', 'sword',
    'missle', the Halo 2 'h2...' stances) carrying weapon: Halo CE's names ('stand rifle move-front', 's-kill front',
    'h-ping back' ...) matched per kind, with fallbacks to the pistol / rifle / unarmed stances. A kind with an empty
    list has no animation (zs_anim_funcs leaves it out). A variant's '_ov' anims / anims_by_weapon overrides entries.
    To give a kind another animation for every body, change its patterns here"""
    m = {}
    st = ['stand', 'alert']
    def f(*pats): return A.find(*pats)
    m['IDLE'] = f(f'stand {w} idle', f'alert {w} idle', 'stand unarmed idle', 'stand pistol idle', 'stand rifle idle', 'stand fixed overlay baked', 'stand fixed idle')
    # Halo CE's Marines and Jackals: 'stand' is weapon (shield) up, 'alert' is their low ready (used out of combat:
    # LOW_IDLE / LOW_MOVE)
    marine = any(n.startswith('stand h2missile') for n in A.names) or getattr(A, 'jackal', False)
    m['ALERT'] = (f(f'stand {w} idle') if marine else []) or f(f'alert {w} idle', f'stand {w} idle') or m['IDLE']
    for k, n in [('MOVE_F', 'move-front'), ('MOVE_B', 'move-back'), ('MOVE_L', 'move-left'), ('MOVE_R', 'move-right')]:
        m[k] = f(f'stand {w} {n}', f'alert {w} {n}', f'stand unarmed {n}', f'stand pistol {n}')
    if not m['MOVE_F']: m['MOVE_F'] = m['IDLE']
    m['CROUCH_IDLE'] = f(f'crouch {w} idle')
    m['CROUCH_MOVE'] = f(f'crouch {w} move-front')
    m['FLEE'] = f(f'flee {w} move-front', 'flee pistol move-front', 'flee rifle move-front')
    # SOI7's (be_anims.py): the Grunt's grenade pull for its suicide run, a cornered panic, the Elite's sword draw
    m['KAMIKAZE'] = f('suicide enter')
    m['FLEE_IDLE'] = f(f'flee {w} idle', 'flee pistol idle')
    m['DRAW'] = f(f'stand {w} enter')
    code = FIRE_CODE.get(weapon or '', '')
    fires = [n for n in A.names if n.endswith('baked') and 'fire-' in n]
    pick = [n for n in fires if f' {w} ' in n and f' {code} ' in n] or [n for n in fires if f' {w} ' in n] or fires
    m['FIRE'] = pick[:1]
    # Halo CE's Marines have no melee animation in either stance: Halo 2's rifle / pistol melee (the h2 sets' butt strike)
    m['MELEE'] = f(f'stand {w} melee', f'stand h2{w} melee', 'stand pistol melee', 'stand unarmed melee')
    m['THROW'] = f(f'stand {w} throw-grenade', 'stand pistol throw-grenade', 'stand rifle throw-grenade')
    for k, n in [('DIVE_L', 'dive-left'), ('DIVE_R', 'dive-right'), ('DIVE_F', 'dive-front'),
                 ('EVADE_L', 'evade-left'), ('EVADE_R', 'evade-right'), ('SURPRISE_F', 'surprise-front'),
                 ('SURPRISE_B', 'surprise-back'), ('BERSERK', 'berserk'), ('WARN', 'warn'), ('SIGNAL', 'signal-attack'),
                 ('AIRBORNE', 'airborne'), ('CELEBRATE', 'celebrate'), ('TURN_L', 'turn-left'), ('TURN_R', 'turn-right')]:
        m[k] = f(f'stand {w} {n}', f'stand pistol {n}', f'stand rifle {n}', f'stand unarmed {n}')
    m['LAND'] = f(f'stand {w} land-soft', f'stand {w} land-hard', 'stand unarmed land-soft', 'stand pistol land-soft')
    m['LEAP_START'] = f(f'stand {w} leap-start', 'stand pistol leap-start')
    m['LEAP_AIR'] = f(f'stand {w} leap-airborne', 'stand pistol leap-airborne', 'stand unarmed airborne')
    m['LEAP_MELEE'] = f(f'stand {w} leap-melee', 'stand pistol leap-melee', 'stand unarmed leap-melee', 'stand unarmed melee')
    pings = [n for n in A.names if n.startswith('s-ping') and n.endswith('baked')]
    for k, d in [('PING_F', 'front'), ('PING_B', 'back'), ('PING_L', 'left'), ('PING_R', 'right')]:
        m[k] = sorted(n for n in pings if f' {d} ' in n)[:3]
    m['HPING_F'] = sorted(n for n in A.names if n.startswith('h-ping front'))[:4]
    m['HPING_B'] = sorted(n for n in A.names if n.startswith('h-ping back'))[:3]
    for k, d in [('DIE_F', 'front'), ('DIE_B', 'back'), ('DIE_L', 'left'), ('DIE_R', 'right')]:
        m[k] = sorted(n for n in A.names if n.startswith(f's-kill {d}')) or sorted(n for n in A.names if n.startswith(f'h-kill {d}'))
    m['DIE_HARD_F'] = sorted(n for n in A.names if n.startswith('h-kill front')) or m['DIE_F']
    m['DIE_HARD_B'] = sorted(n for n in A.names if n.startswith('h-kill back')) or m['DIE_B']
    if not m['DIE_F']: m['DIE_F'] = m['DIE_HARD_F'] or sorted(n for n in A.names if 'dead' in n)
    m['DIE_AIR'] = sorted(n for n in A.names if n.startswith('stand airborne-dead'))
    m['DIE_LAND'] = sorted(n for n in A.names if n.startswith('stand landing-dead'))
    m['RESURRECT_F'] = f('stand unarmed resurrect-front')
    m['RESURRECT_B'] = f('stand unarmed resurrect-back')
    m['FEED'] = f('stand unarmed feeding')
    m['SLEEP'] = f(f'asleep {w} idle', 'asleep any idle')      # (the Brutes' Halo 3-style sleep: be_anims.py)
    # Halo CE's burning animations (Elites, Grunts and Jackals flail in place; Jackals, Marines and Slug Men also run)
    m['FLAME_IDLE'] = f(f'flaming {w} idle', 'flaming pistol idle', 'flaming rifle idle', 'flaming unarmed idle')
    m['FLAME_MOVE'] = f(f'flaming {w} move-front', 'flaming pistol move-front', 'flaming rifle move-front', 'flaming unarmed move-front')
    # Halo 2's reloads and plasma vents (reload_anims.py): the gun's own (the needler's, the shotguns' shells), else the stance's
    fam = 'pistol' if 'pistol' in w else 'missle' if 'missile' in w else 'rifle' if w.startswith('h2') else w
    # Halo 2's corner cover (cover_anims.py): step in beside a corner, lean out past it to shoot, lean back; and its
    # hoist onto a ledge and vault over a low wall. The stance's own, else the nearest Halo 2 stance's
    for k, n in [('COVER_L_ENTER', 'cover-left-enter'), ('COVER_L_IDLE', 'cover-left-idle'), ('COVER_L_PEEK', 'cover-left-peek'),
                 ('COVER_L_OPEN', 'cover-left-open'), ('COVER_L_UNPEEK', 'cover-left-unpeek'), ('COVER_L_EXIT', 'cover-left-exit'),
                 ('COVER_R_ENTER', 'cover-right-enter'), ('COVER_R_IDLE', 'cover-right-idle'), ('COVER_R_PEEK', 'cover-right-peek'),
                 ('COVER_R_OPEN', 'cover-right-open'), ('COVER_R_UNPEEK', 'cover-right-unpeek'), ('COVER_R_EXIT', 'cover-right-exit'),
                 ('HOIST', 'hoist'), ('VAULT', 'vault')]:
        m[k] = f(f'stand {w} {n}', f'stand {fam} {n}', f'stand rifle {n}', f'stand pistol {n}', f'stand support {n}', f'stand missle {n}')
    rc = {'needler': 'ne', 'shotgun': 'sg', 'bulldog': 'sg', 'double barrel': 'sg'}.get(weapon or '', '1')
    m['RELOAD'] = f(f'stand {w} reload-{rc}', f'stand {fam} reload-{rc}', f'stand {w} reload-1', f'stand {fam} reload-1')
    m['VENT'] = f(f'stand {w} overheat', f'stand {fam} overheat')
    # the low-ready idle and walk, out of combat: Halo CE's own for its Marines and Jackals, else Halo 2's (low_ready_anims.py)
    m['LOW_IDLE'] = (f(f'alert {w} idle') if marine else []) or f(f'stand {w} low-idle')
    m['LOW_MOVE'] = (f(f'alert {w} move-front') if marine else []) or f(f'stand {w} low-move')
    # a guard stance taken up in cover, under fire (the Ultra Zealot's shield held out: extract_ultra_zealot.py)
    for k, n in [('GUARD_IDLE', 'idle'), ('GUARD_MOVE_F', 'move-front'), ('GUARD_MOVE_B', 'move-back'),
                 ('GUARD_MOVE_L', 'move-left'), ('GUARD_MOVE_R', 'move-right')]:
        m[k] = f(f'guard {w} {n}')
    m['GUARD_CROUCH_IDLE'] = f(f'crouch guard {w} idle')
    m['GUARD_CROUCH_MOVE'] = f(f'crouch guard {w} move-front')
    return m

# every animation kind the AI asks for (HCE_A_<kind> in enemies_base.zsc), the order they are written in HCE_AnimName.
# A new kind needs an entry here, a line in anim_table and its HCE_A_ constant in the ZScript
KINDS = ['IDLE', 'ALERT', 'MOVE_F', 'MOVE_B', 'MOVE_L', 'MOVE_R', 'CROUCH_IDLE', 'CROUCH_MOVE', 'FLEE', 'FIRE', 'MELEE',
         'THROW', 'DIVE_L', 'DIVE_R', 'DIVE_F', 'EVADE_L', 'EVADE_R', 'SURPRISE_F', 'SURPRISE_B', 'BERSERK', 'WARN',
         'SIGNAL', 'AIRBORNE', 'LAND', 'LEAP_START', 'LEAP_AIR', 'LEAP_MELEE', 'PING_F', 'PING_B', 'PING_L', 'PING_R',
         'HPING_F', 'HPING_B', 'DIE_F', 'DIE_B', 'DIE_L', 'DIE_R', 'DIE_HARD_F', 'DIE_HARD_B', 'DIE_AIR', 'DIE_LAND',
         'RESURRECT_F', 'RESURRECT_B', 'FEED', 'CELEBRATE', 'SLEEP', 'TURN_L', 'TURN_R', 'FLAME_IDLE', 'FLAME_MOVE',
         'RELOAD', 'VENT', 'LOW_IDLE', 'LOW_MOVE', 'GUARD_IDLE', 'GUARD_MOVE_F', 'GUARD_MOVE_B', 'GUARD_MOVE_L',
         'GUARD_MOVE_R', 'GUARD_CROUCH_IDLE', 'GUARD_CROUCH_MOVE',
         'COVER_L_ENTER', 'COVER_L_IDLE', 'COVER_L_PEEK', 'COVER_L_OPEN', 'COVER_L_UNPEEK', 'COVER_L_EXIT',
         'COVER_R_ENTER', 'COVER_R_IDLE', 'COVER_R_PEEK', 'COVER_R_OPEN', 'COVER_R_UNPEEK', 'COVER_R_EXIT', 'HOIST', 'VAULT',
         'KAMIKAZE', 'FLEE_IDLE', 'DRAW']

def zs_anim_move(A, used, msc=1.0):
    """HCE_AnimMove: how far a hoist / vault carries the body (cover_anims.py's 'move', Halo world units forward, left,
    up), in map units: the model's own scale, with the 1.2 vertical stretch every Halo model gets"""
    mv = [(n, A.meta['anims'][n]['move']) for n in used if 'move' in A.meta['anims'].get(n, {})]
    if not mv:   # no hoist or vault of its own: no switch (an empty one is a compile warning)
        return ['\t// the ground each moving clip covers (none here: the AI moves the body itself)', '\toverride vector3 HCE_AnimMove(Name anim)', '\t{', '\t\treturn (0, 0, 0);', '\t}']
    out = ['\t// the ground each moving clip covers in map units a tic (its root motion), so the stride matches the walk',
           '\toverride vector3 HCE_AnimMove(Name anim)', '\t{', '\t\tswitch(anim)', '\t\t{']
    for n, (x, y, z) in mv:
        out.append(f"\t\tcase '{n}': return ({x * S * msc:.1f}, {y * S * msc:.1f}, {z * S * msc * 1.2:.1f});")
    return out + ['\t\t}', '\t\treturn (0, 0, 0);', '\t}']

def zs_anim_funcs(A, table, bers=None, msc=1.0):
    """the class's animation overrides as ZScript: HCE_AnimName (kind -> a name, rolled when the kind has several;
    bers: the table used instead while hce_berserk is set), HCE_AnimTics (name -> length) and HCE_AnimMove
    (zs_anim_move). A gun picked up (hce_hasLoadout) asks the loadout's table first"""
    lines = ['\t// the animation table: which IQM clip plays for each of the AI\'s animation kinds (HCE_A_IDLE, HCE_A_MOVE_F ...;',
             '\t// the list is in the enemy API). A kind with several clips rolls one each time. To swap a clip, change its name here',
             '\toverride Name HCE_AnimName(int kind)', '\t{',
             "\t\tif(hce_hasLoadout) { Name ln = HCE_LoadoutAnim(hce_loadout, kind); if(ln != 'None') return ln; }   // a gun picked up"]
    if bers:
        lines += ['\t\tif(hce_berserk) switch(kind)', '\t\t{']
        for k in KINDS:
            opts = [o for o in bers.get(k) or [] if o in A.names]
            if not opts: continue
            if len(opts) == 1: lines.append(f"\t\tcase HCE_A_{k}: return '{opts[0]}';")
            else: lines.append(f"\t\tcase HCE_A_{k}: {{ static const Name o[] = {{ {', '.join(repr(x).replace(chr(34), '') for x in opts)} }}; return o[random(0, {len(opts) - 1})]; }}")
        lines += ['\t\t}']
    lines += ['\t\tswitch(kind)', '\t\t{']
    for k in KINDS:
        opts = table.get(k) or []
        if not opts: continue
        if len(opts) == 1:
            lines.append(f"\t\tcase HCE_A_{k}: return '{opts[0]}';")
        else:
            lines.append(f"\t\tcase HCE_A_{k}: {{ static const Name o[] = {{ {', '.join(repr(x).replace(chr(34), '') for x in opts)} }}; return o[random(0, {len(opts) - 1})]; }}")
    lines += ['\t\t}', "\t\treturn 'None';", '\t}', '']
    used = sorted({n for k in KINDS for n in (table.get(k) or [])} | {n for k in KINDS for n in ((bers or {}).get(k) or []) if n in A.names})
    lines += ['\t// how long each clip plays, in tics (its Halo frame count at 30 fps, in Doom\'s 35 tics a second)',
              '\toverride int HCE_AnimTics(Name anim)', '\t{',
              '\t\tif(hce_hasLoadout) { int lt = HCE_LoadoutAnimTics(anim); if(lt > 0) return lt; }', '\t\tswitch(anim)', '\t\t{']
    for n in used:
        lines.append(f"\t\tcase '{n}': return {A.tics(n)};")
    lines += ['\t\t}', '\t\treturn 30;', '\t}']
    lines += zs_anim_move(A, used, msc)
    return '\n'.join(lines)

# ---------------------------------------------------------------- skins
def variant_color(v, b):
    """the variant's armour colour (RGB 0..1): the middle of its actor variant's first change-colour range, else the
    biped's (its first permutation's); None when neither has one (the skin is baked uncoloured)"""
    cl = v.get('change_colors_list') or []
    if cl:
        lo, hi = cl[0]['color_lower_bound'], cl[0]['color_upper_bound']
        return [(a + c) / 2 for a, c in zip(lo, hi)]
    bl = b.get('change_colors_list') or []
    if bl:
        c = bl[0]
        if c.get('perms'):
            p = c['perms'][0]
            return [(a + d) / 2 for a, d in zip(p['color_lower_bound'], p['color_upper_bound'])]
        return [(a + d) / 2 for a, d in zip(c['color_lower_bound'], c['color_upper_bound'])]
    return None

# SHIELD_TINT: variants.py
# character -> the material of its hand-held energy shield (the Jackals'): baked per rank by bake_shield in the
# rank's SHIELD_TINT and given the shield shader
SHIELD_MAT = {'Jackal': 'Jackal_5', 'JackalMajor': 'JackalMajor_5'}

def bake_shield(char, mat, tint, outpath):
    """energy shield: the noise map becomes a bright rank-coloured field with a hot core"""
    n = np.asarray(Image.open(f'{OUT}/models/{char}/{mat}.png').convert('L').resize((128, 128))).astype(np.float32) / 255.0
    col = np.array(tint, dtype=np.float32).reshape(1, 1, 3)
    o = col * (0.55 + 0.6 * n[..., None]) + (n[..., None] ** 3) * 0.35
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

_SHIELD_MASK = {}

def hunter_shield_mask(char, mat, size):
    """the Hunter's shield and its shoulder plating (the surfaces on its left arm) as a mask over this texture (W x H, 0..1), its edges
    grown a few texels so the island's border is in it; None if the shield isn't on this texture"""
    key = (char, mat, size)
    if key in _SHIELD_MASK: return _SHIELD_MASK[key]
    from iqm import read_iqm
    from PIL import ImageDraw
    from scipy import ndimage
    joints, meshes, _ = read_iqm(f'{OUT}/models/{char}/{char}.iqm')
    names = [j[0] for j in joints]
    mats = json.load(open(f'{OUT}/models/{char}/{char}.json'))['meshes']
    keep = {names.index(n) for n in ('bip01 l upperarm', 'bip01 l forearm', 'bip01 l hand') if n in names}   # its shoulder plating too
    W, H = size
    img = Image.new('L', (W, H), 0); d = ImageDraw.Draw(img)
    for mi, M in enumerate(meshes):
        if mats[mi][:-4] != mat: continue
        dom = M['bidx'][np.arange(len(M['bidx'])), M['bw'].argmax(1)]
        for t in M['tris']:
            if all(dom[v] in keep for v in t):
                d.polygon([(M['uv'][v][0] % 1 * W, M['uv'][v][1] % 1 * H) for v in t], fill=255)
    a = np.asarray(img, np.float32) / 255
    out = None
    if a.max() > 0:
        out = np.clip(ndimage.gaussian_filter(ndimage.grey_dilation(a, size=(5, 5)), 1.0) * 1.2, 0, 1)
    _SHIELD_MASK[key] = out
    return out


def bake_hunter(char, mat, mode, outpath):
    """Hunter armour is painted blue in the base map; recolour the blue armour by hue (worm flesh/cannon untouched)."""
    im = Image.open(f'{OUT}/models/{char}/{mat}.png').convert('RGB')
    hsv = np.asarray(im.convert('HSV')).astype(np.float32)
    rgb = np.asarray(im).astype(np.float32) / 255.0
    h, sv, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    # the blue paint, as a soft mask: a ramp in from the edges of the blue hues and from low saturation, smoothed, so the
    # shield rims and plate edges (blue near the cut-off) don't flip texel by texel between recoloured and not
    from scipy import ndimage
    hue_in = np.clip(np.minimum(h - 175, 275 - h) / 20.0, 0, 1)
    sat_in = np.clip((sv - 0.10) / 0.14, 0, 1)
    armour = np.clip(ndimage.gaussian_filter(hue_in * sat_in, 1.2) * 1.25, 0, 1)[..., None]
    # the shield takes no rank colour: its painted rim (a thin blue line) came out patchy, half recoloured, half not;
    # it is plain dark metal like the plate it frames (shield: the shield's own texels, a little past their edges)
    shield = hunter_shield_mask(char, mat, im.size)
    if shield is not None:
        armour = armour * (1 - shield[..., None])
    lum = (0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2])[..., None]
    # the colour laid on as the Elites' rank colours are (bake_vivid): the paint's light and shade kept, a highlight on
    # the edges, not a flat fill at full saturation; then the same cube-map armour reflection as the Elites (add_shine,
    # Halo CE's Hunter specular mask), in the rank's own cube map, its hue held to the armour colour (hue_lock)
    col = np.array(HUNTER_COLOURS[mode], np.float32).reshape(1, 1, 3)
    a0, a1 = HUNTER_TONE[mode]
    new = np.clip(col * (a0 + a1 * lum) + np.clip(lum - 0.42, 0, 1) * 0.55, 0, 1)
    o = rgb * (1 - armour) + new * armour
    # the rank's cube map on the recoloured armour; the cannon, the worms and the rest keep the blue Hunter's
    o = add_shine(char, mat, o, HUNTER_COLOURS[mode]) * armour + add_shine(char, mat, o, None) * (1 - armour)
    o = hue_lock(o, armour[..., 0].astype(np.float32), HUNTER_COLOURS[mode])
    if shield is not None:
        # the whole shield in neutral metal (its rim, stray paint and the blue reflection off its edges), all but its own
        # glowing lights (bright and saturated in the paint)
        glow = np.clip((v - 0.5) / 0.15, 0, 1) * np.clip((sv - 0.35) / 0.15, 0, 1)
        k = (shield * (1 - glow))[..., None]
        metal = o.mean(axis=2, keepdims=True) * np.array([0.97, 0.98, 1.0], np.float32)
        o = o * (1 - k) + metal * k
    if mode == 'red' and mat == 'Hunter_4':
        # the Major's arm cannon: the body painted the blue Hunter's blue, with the red rank's reflection on it (the
        # nozzle, on the arm's other texture, is red with the armour)
        green = np.clip(np.minimum(h - 70, 170 - h) / 15.0, 0, 1) * np.clip((sv - 0.25) / 0.15, 0, 1)   # its lights
        paint = ndimage.gaussian_filter(1 - green, 0.8)[..., None]
        blue = np.clip(np.array([0.10, 0.22, 0.62], np.float32) * (0.30 + 1.9 * lum), 0, 1)
        glint = np.clip(add_shine(char, mat, blue, HUNTER_COLOURS['red']) - blue, 0, 1).max(axis=2, keepdims=True)
        shone = np.clip(blue + glint * np.array([1.0, 0.12, 0.06], np.float32) * 1.5, 0, 1)    # the reflection pure red
        o = rgb * (1 - paint) + shone * paint
    if mode == 'white':
        # white paint: the reflection's blue taken out and the plates lifted to a bright off-white, keeping their shading
        g = o.mean(axis=2, keepdims=True)
        paint = np.clip(0.38 + 0.72 * g, 0, 1) * np.array([1.0, 0.985, 0.95], np.float32)
        o = o * (1 - armour * 0.9) + paint * armour * 0.9
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

# HUNTER_COLOURS: variants.py
# HUNTER_TONE: variants.py

# SHINE: variants.py
# SHINE_CUBE: variants.py
_normal_maps = {}

def normal_map(char, mat, size):
    """(H, W, 3) model-space normals per texel of 'mat' (zero where no triangle covers it, then grown into the gaps)"""
    key = (char, mat, size)
    if key in _normal_maps: return _normal_maps[key]
    from iqm import read_iqm
    from scipy import ndimage
    _, meshes, _ = read_iqm(f'{OUT}/models/{char}/{char}.iqm')
    N = raster_normals(meshes, mat + '.png', size)
    _normal_maps[key] = N
    return N


_cubes = {}

def cube_faces(name, index):
    """Halo's cube map as six 256x256 float faces (+x -x +y -y +z -z), smoothed up from 64x64"""
    key = (name, index)
    if key not in _cubes:
        d = f'{OUT}/cubemaps/{name}'
        _cubes[key] = [np.asarray(Image.open(f'{d}/{index}_{f}.png').convert('RGB').resize((256, 256), Image.BICUBIC)).astype(np.float32) / 255
                       for f in range(6)] if os.path.exists(f'{d}/{index}_0.png') else None
    return _cubes[key]

# The Minor (blue) and Major (red) Elites wear hand-painted skins with Halo's cube-map shine baked in
# (assets/elite_skins/<blue|red>/Elite_<k>.png, one per Elite material; any Elite-layout body: Elite, EliteRifle).
# Halo's black Spec Ops armour reads as a hole against the dark undersuit, so the Spec Ops wear a vibrant dark
# purple instead: the blue skins hue-turned to purple on the Elite bodies, the change colour on the Spec Ops body.
ELITE_SKINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'elite_skins')
ELITE_LAYOUT = ('Elite', 'EliteRifle')

# the Spec Ops body (EliteSpecial) shares three of its textures with the Elite: those take the purple-turned skins too
SPECOPS_SHARED = {'0': '0', '3': '5', '5': '5'}
# MINOR_BLUE: variants.py

def elite_skin(char, mat, color, outpath, specops=False):
    """write the hand-painted skin for this Elite rank's material; False when there is none"""
    k = mat.rsplit('_', 1)[-1]
    if char == 'EliteSpecial' and specops and k in SPECOPS_SHARED:
        char, k, color = 'Elite', SPECOPS_SHARED[k], (0, 0, 0)
    if char not in ELITE_LAYOUT: return False
    ci = cube_index(char, color)
    src = {0: 'blue', 1: 'red', 3: 'blue'}.get(ci)
    if not src or not os.path.exists(f'{ELITE_SKINS}/{src}/Elite_{k}.png'): return False
    im = Image.open(f'{ELITE_SKINS}/{src}/Elite_{k}.png').convert('RGB')
    if ci == 3: im = ultra_white(im, char, mat) if is_white(color) else purple(im)
    elif ci == 0 and is_green(color): im = heavy_green(im, char, mat)    # the Heavy: the blue skin's armour in green
    im.save(outpath)
    return True

# HEAVY_HUE: variants.py

def heavy_green(im, char, mat):
    """the blue Minor skin's armour plates turned green, only where Halo's colour-change mask is (the armour): the
    undersuit, hands and the rest keep their own colours"""
    from scipy import ndimage
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if not os.path.exists(mp): return im
    m = np.asarray(Image.open(mp).convert('RGBA').resize(im.size)).astype(np.float32)[..., 2] / 255.0
    m = np.clip(ndimage.gaussian_filter(m, 0.6), 0, 1)
    hsv = np.asarray(im.convert('HSV')).astype(np.float32)
    h, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    blue = np.clip(1 - (np.abs(h * 360 / 255 - 210) - 45) / 20, 0, 1)            # the plates' blues and cyans
    arm = m * blue
    near = ndimage.grey_dilation(m, size=(7, 7))                                   # the plates' edges the mask misses:
    arm = np.maximum(arm, near * blue * np.clip((sat - 110) / 40, 0, 1))          # only their vivid blues, not the suit
    h = h * (1 - arm) + (HEAVY_HUE * 255 / 360) * arm
    sat = np.clip(sat * (1 + 0.1 * arm), 0, 255); val = val * (1 - 0.3 * arm)
    return Image.fromarray(np.stack([h, sat, val], -1).astype(np.uint8), 'HSV').convert('RGB')

def ultra_white(im, char, mat):
    """the blue Minor skin's armour plates whitened for the Ultras (Halo 2's white rank), only where Halo's colour-change
    mask is: the plates' shading and baked shine kept as brightness, their colour taken out"""
    from scipy import ndimage
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    hsv = np.asarray(im.convert('HSV')).astype(np.float32)
    h, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    blue = np.clip(1 - (np.abs(h * 360 / 255 - 210) - 45) / 20, 0, 1)
    if os.path.exists(mp):
        m = np.asarray(Image.open(mp).convert('RGBA').resize(im.size)).astype(np.float32)[..., 2] / 255.0
        m = np.clip(ndimage.gaussian_filter(m, 0.6), 0, 1)
        arm = m * blue
        near = ndimage.grey_dilation(m, size=(7, 7))
        arm = np.maximum(arm, near * blue * np.clip((sat - 110) / 40, 0, 1))
    else:                                   # no colour-change mask for this material: the plates by their vivid blue
        arm = blue * np.clip((sat - 90) / 40, 0, 1)
    rgb = np.asarray(im).astype(np.float32)
    lum = val[..., None] / 255.0
    white = np.clip((0.35 + 0.75 * lum) * np.array(ULTRA_WHITE) * 255 / max(ULTRA_WHITE), 0, 255)
    out = rgb * (1 - arm[..., None]) + white * arm[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def is_white(color):
    """whether an armour colour (RGB 0..1) is a light grey-white (the Ultra Elites')"""
    import colorsys
    if color is None: return False
    h, l, sat = colorsys.rgb_to_hls(*[float(c) for c in color[:3]])
    return sat < 0.25 and l > 0.6

def is_green(color):
    """whether an armour colour (RGB 0..1) is a saturated green (the Heavy Elites': hue 75..170)"""
    import colorsys
    if color is None: return False
    h, l, sat = colorsys.rgb_to_hls(*[float(c) for c in color[:3]])
    return sat >= 0.25 and 75 <= h * 360 <= 170

def grunt_purple(char, mat, path):
    """the Spec Ops Grunts' armour in the Spec Ops Elites' violet. Their CE textures are grimy and blotchy (the painted
    Elite skins aren't), so rather than shifting hues (purple() misses the greyed patches) the whole armour, by the
    colour-change mask, is repainted: one violet, its shading from the softened brightness, only the reflection's
    highlights going pale"""
    from scipy import ndimage
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if not os.path.exists(mp): return
    im = Image.open(path).convert('RGB')
    rgb = np.asarray(im).astype(np.float32) / 255.0
    H_, W_ = rgb.shape[:2]
    m = np.asarray(Image.open(mp).convert('RGBA').resize((W_, H_))).astype(np.float32)[..., 2] / 255.0
    m = ndimage.gaussian_filter(m, 0.7)
    v = rgb.max(2)
    v = ndimage.median_filter(v, 5)                                        # the grime's speckle
    v = ndimage.gaussian_filter(v, 1.6) * 0.75 + v * 0.25                  # broad, smooth shading like the painted skins
    hi = np.clip((ndimage.gaussian_filter(v, 2.5) - 0.78) / 0.2, 0, 1) * 0.7  # soft reflection highlights
    base = np.array([0.43, 0.10, 0.78], np.float32)                        # the Spec Ops Elites' violet (hue ~282)
    pale = np.array([0.86, 0.72, 1.00], np.float32)
    shade = np.clip(0.12 + 0.95 * v, 0, 1)[..., None]
    col = base * shade * (1 - hi[..., None]) + pale * hi[..., None] * np.clip(v, 0, 1)[..., None]
    out = rgb * (1 - m[..., None]) + col * m[..., None]
    Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8)).save(path)


def purple(im, to_hue=282, darken=0.25):
    """the blue Minor skin turned vibrant dark purple (or another hue): the armour's blues and cyans coloured violet
    (their shading and shine kept), a little darker and richer"""
    hsv = np.asarray(im.convert('HSV')).astype(np.float32)
    h, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    hue = np.abs(h * 360 / 255 - 205) < 60
    arm = np.clip((sat - 95) / 50, 0, 1) * hue                                   # the armour's blues and cyans (not the undersuit)
    arm = np.maximum(arm, np.clip((val - 170) / 40, 0, 1) * np.clip((sat - 25) / 30, 0, 1) * hue)   # and its pale cyan glints
    h = h * (1 - arm) + (to_hue * 255 / 360) * arm
    sat = np.clip(sat * (1 + 0.2 * arm), 0, 255); val = val * (1 - darken * arm)
    return Image.fromarray(np.stack([h, sat, val], -1).astype(np.uint8), 'HSV').convert('RGB')

def cube_index(char, color):
    """which of the Elites' four cube maps a rank wears, from its armour colour: blue, magenta/red, gold, silver"""
    if SHINE_CUBE.get(char) != 'elite' or color is None: return 0 if char != 'EliteSpecial' else 3
    import colorsys
    h, l, sat = colorsys.rgb_to_hls(*[float(c) for c in color[:3]])
    if sat < 0.25 or l < 0.08: return 3
    h *= 360
    if h < 25 or h > 300: return 1
    if h < 75: return 2
    return 0

def add_shine(char, mat, rgb, color=None, scale=1.0):
    """rgb (H, W, 3) floats 0..1, the finished skin colours -> with Halo's armour reflection baked in"""
    k = SHINE.get(char)
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if not k or not os.path.exists(mp): return rgb
    faces = cube_faces(SHINE_CUBE[char], cube_index(char, color))
    if faces is None: return rgb
    from scipy import ndimage
    H_, W_ = rgb.shape[:2]
    spec = np.asarray(Image.open(mp).convert('RGBA').resize((W_, H_))).astype(np.float32)[..., 0] / 255.0
    if spec.max() < 0.05: return rgb
    n = normal_map(char, mat, (W_, H_)).copy()
    # the paint's relief (panel lines, plate edges) bends the reflection like a bump map would
    lum = ndimage.gaussian_filter(rgb.mean(axis=2), 1.2)
    gy, gx = np.gradient(lum)
    t1 = np.cross(n, np.array([0, 0, 1.0], np.float32)); t1 /= np.maximum(np.linalg.norm(t1, axis=2, keepdims=True), 1e-3)
    t2 = np.cross(n, t1)
    n = n + (gx[..., None] * t1 + gy[..., None] * t2) * 6.0
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    view = np.array([-1.0, 0.0, -0.25], np.float32); view /= np.linalg.norm(view)      # looking at the model's front
    r = view - 2 * (n @ view)[..., None] * n
    env = sample_cube(faces, r)
    fres = 0.75 + 0.5 * (1 - np.abs(n @ view)) ** 2                               # brighter towards grazing angles
    env = np.clip(env * 1.15, 0, 1) ** 1.35 * 1.7                                   # Halo adds it bright: its swirls read as liquid metal
    spec = spec * scale
    s = env * (spec * k * fres)[..., None]
    if char in HUE_LOCK:
        # the Grunts: the Elites' rank cube only on the painted armour (Halo's colour-change mask); their bare metal,
        # masks and hoses keep Halo CE's own dull grey reflection, as before
        cm = np.asarray(Image.open(mp).convert('RGBA').resize((W_, H_))).astype(np.float32)[..., 2] / 255.0
        grey = np.clip(sample_cube(cube_faces('dark_gray', 0), r) * 1.15, 0, 1) ** 1.35 * 1.7
        s = env * (spec * k * fres * cm)[..., None] + grey * (spec * 0.85 * fres * (1 - cm))[..., None]
    return np.clip(rgb * (1 - 0.3 * spec[..., None]) + s, 0, 1)                    # the metal darkens a little under its reflection


# ---------------------------------------------------------------- Covenant weapon shine
# Halo CE's Covenant weapons reflect a cube map on their painted metal (shader_model: the multipurpose map's red is the
# reflection mask; extract_weapon_shine.py). It's baked into the colourful parts of their textures: CE's own cube map
# and mask where the weapon has one (plasma pistol, plasma rifle, needler), the plasma rifle's cube map and the paint's
# saturation for the rest (fuel rod, sword hilt, the Halo 2 and Digsite weapons, the Plasma Caster). Lights, glows and
# grey metal stay as they are.
COVENANT_WEAPONS = ('plasma_pistol', 'plasma_rifle', 'needler', 'fuel_rod', 'energy_sword', 'h2_beam_rifle', 'beam_rifle',
                    'cmt_carbine', 'plasma_caster', 'brute_plasma_rifle', 'brute_shot', 'spiker', 'plasma_carbine',
                    'particle_beam_dig', 'gravity_hammer')
NO_SHINE = ('glow', 'lights', 'icon', 'meter', 'heat')
_shine_mats = None

def shine_materials():
    """weapon texture file -> (weapon id, the material its normals come from)"""
    global _shine_mats
    if _shine_mats is None:
        import pickle
        _shine_mats = {}
        for wid in COVENANT_WEAPONS:
            pk = f'{OUT}/weapons/{wid}/{wid}.pkl'
            if not os.path.exists(pk): continue
            for m in pickle.load(open(pk, 'rb'))['meshes']:
                if not any(k in m['material'] for k in NO_SHINE): _shine_mats[m['material']] = (wid, m['material'])
        for skins in WEAPON_SKIN.values():                   # re-coloured variants: the original's normals
            for orig, new in skins.items():
                if orig in _shine_mats: _shine_mats[new] = _shine_mats[orig]
    return _shine_mats


def weapon_shine(name, im):
    """a Covenant weapon texture (PIL) -> with Halo's reflection baked into its colourful parts (others unchanged)"""
    hit = shine_materials().get(name)
    if not hit: return im
    import pickle
    wid, mat = hit
    spec = json.load(open(f'{OUT}/weapons/{wid}/shine.json')).get(mat) if os.path.exists(f'{OUT}/weapons/{wid}/shine.json') else None
    alpha = im.getchannel('A') if im.mode == 'RGBA' else None
    rgb = np.asarray(im.convert('RGB')).astype(np.float32) / 255.0
    H_, W_ = rgb.shape[:2]
    mx, mn = rgb.max(2), rgb.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    colourful = np.clip((sat - 0.28) / 0.22, 0, 1) * np.clip((mx - 0.08) / 0.15, 0, 1)
    colourful *= 1 - np.clip((mx - 0.68) / 0.12, 0, 1) * np.clip((sat - 0.4) / 0.15, 0, 1)    # bright saturated: a light
    if spec:
        mu = np.asarray(Image.open(f'{OUT}/weapons/{wid}/{spec["multi"]}').convert('RGBA').resize((W_, H_))).astype(np.float32) / 255.0
        mask = mu[..., 0] * colourful * (1 - np.clip(mu[..., 1] * 3, 0, 1))      # CE's reflection mask, not the lights
        cube, perp, par = spec['cube'], spec['perpendicular'], spec['parallel']
    else:
        mask = colourful
        cube, perp, par = 'w_plasma_rifle', 0.22, 0.45          # no mask of Halo's: kept gentler
    if mask.max() < 0.05: return im
    faces = cube_faces(cube, 0)
    meshes = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))['meshes']
    n = raster_normals(meshes, mat, (W_, H_))
    from scipy import ndimage
    lum = ndimage.gaussian_filter(rgb.mean(axis=2), 1.0)                  # the paint's relief bends the reflection
    gy, gx = np.gradient(lum)
    t1 = np.cross(n, np.array([0, 0, 1.0], np.float32)); t1 /= np.maximum(np.linalg.norm(t1, axis=2, keepdims=True), 1e-3)
    t2 = np.cross(n, t1)
    n = n + (gx[..., None] * t1 + gy[..., None] * t2) * 5.0
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    view = np.array([-0.7, -0.55, -0.35], np.float32); view /= np.linalg.norm(view)   # seen from the front and side
    r = view - 2 * (n @ view)[..., None] * n
    env = sample_cube(faces, r)
    fres = (1 - np.abs(n @ view)) ** 2
    bright = perp + (par - perp) * fres                                    # Halo: perpendicular -> parallel brightness
    env = np.clip(env * 1.1, 0, 1) ** 1.3 * 1.5
    out = np.clip(rgb * (1 - 0.2 * mask[..., None]) + env * (mask * bright)[..., None], 0, 1)
    res = Image.fromarray((out * 255).astype(np.uint8))
    if alpha is not None: res.putalpha(alpha)
    return res


def copy_weapon_tex(src, dst):
    """a weapon texture into the pack (the Covenant ones with their reflection baked in)"""
    name = os.path.basename(dst)
    if name not in shine_materials(): shutil.copy(src, dst); return
    weapon_shine(name, Image.open(src)).save(dst)


def bake_skin(char, mat, color, outpath, shine=1.0):
    """the default skin bake: the material's texture with the variant's colour multiplied in where Halo's colour-change
    mask (the multipurpose map's blue) says, the cube-map reflection added (add_shine, SHINE / SHINE_CUBE in variants.py,
    shine scaling its strength: RANK_SHINE) and, for HUE_LOCK characters, the painted armour held to the colour's hue.
    A cutout texture (alpha, no mask) or one with no mask / no colour is copied with only the shine"""
    src = Image.open(f'{OUT}/models/{char}/{mat}.png')
    if src.mode == 'RGBA' and np.asarray(src)[..., 3].min() < 128 and not os.path.exists(f'{OUT}/models/{char}/{mat}_multi.png'):
        src.save(outpath); return                 # a cutout (the Drones' wings): alpha kept, UZDoom alpha-tests it
    base = src.convert('RGB')
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if color is None or not os.path.exists(mp):
        if char in SHINE: base = Image.fromarray((add_shine(char, mat, np.asarray(base).astype(np.float32) / 255.0, color, shine) * 255).astype(np.uint8))
        base.save(outpath); return
    mask = Image.open(mp).convert('RGBA').resize(base.size)
    b = np.asarray(base).astype(np.float32) / 255.0
    msk = np.asarray(mask).astype(np.float32)[..., 2:3] / 255.0   # Xbox: blue = colour change
    col = np.array(color, dtype=np.float32).reshape(1, 1, 3)
    o = add_shine(char, mat, b * (1 - msk) + b * col * msk, color, shine)
    if char in HUE_LOCK: o = hue_lock(o, msk[..., 0], color)
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

# HUE_LOCK: variants.py
# RANK_SHINE: variants.py

def hue_lock(rgb, mask, color):
    """rgb (H, W, 3) floats -> the same with the hue turned most of the way (0.8 x mask) toward the colour's: the baked
    reflection's own colours can't drift a rank's armour off its colour. Nothing for a grey or black colour"""
    import colorsys
    h0, l0, s0 = colorsys.rgb_to_hls(*[float(c) for c in color[:3]])
    if s0 < 0.25: return rgb                                              # black / grey ranks: nothing to hold
    hsv = np.asarray(Image.fromarray(np.clip(rgb * 255, 0, 255).astype(np.uint8)).convert('HSV')).astype(np.float32)
    w = np.clip(mask, 0, 1) * 0.8
    hh = hsv[..., 0]; t = h0 * 255
    d = (t - hh + 128) % 256 - 128                                        # shortest way round the hue circle
    hsv[..., 0] = (hh + d * w) % 256
    return np.asarray(Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB')).astype(np.float32) / 255.0

# VIVID: variants.py
# VIVID_SHINE: variants.py
# UNDERSUIT: variants.py

def bake_vivid(char, mat, color, outpath, shine=1.0):
    """the gold Elites' bake (VIVID in variants.py: variant name part -> colour): the armour painted the colour outright
    (its shading from the texture's brightness, a highlight on the edges) rather than multiplied in, the undersuit
    tinted toward UNDERSUIT, the hands left dark, then the reflection (add_shine, VIVID_SHINE)"""
    base = Image.open(f'{OUT}/models/{char}/{mat}.png').convert('RGB')
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if not os.path.exists(mp):
        base.save(outpath); return
    mask = Image.open(mp).convert('RGBA').resize(base.size)
    b = np.asarray(base).astype(np.float32) / 255.0
    msk = np.asarray(mask).astype(np.float32)[..., 2:3] / 255.0
    lum = b.mean(axis=2, keepdims=True)
    col = np.array(color, dtype=np.float32).reshape(1, 1, 3)
    gold = col * (0.12 + 1.15 * lum) + np.clip(lum - 0.62, 0, 1) * 0.8          # body colour + highlight on the edges
    # the bodysuit between the plates: the dark slate of the Elite Special read as a black hole next to the gold;
    # tinted toward the regular Elites' teal undersuit so the Commander matches its lower ranks
    teal = np.array(UNDERSUIT, dtype=np.float32).reshape(1, 1, 3) * (0.25 + 2.2 * lum)
    suit = b * 0.45 + teal * 0.55
    # the hands stay out of the gold: Halo's gold Elites have dark gauntlets, like the lower ranks' hands
    hm = hand_mask(char, mat, base.size)[..., None]
    msk = msk * (1 - hm)
    o = suit * (1 - msk) + gold * msk
    glove = np.array(UNDERSUIT, dtype=np.float32).reshape(1, 1, 3) * (0.18 + 0.55 * lum)   # dark slate, shading kept
    o = add_shine(char, mat, o * (1 - hm) + glove * hm, color, shine)
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

def hand_mask(char, mat, size):
    """0..1 mask of the texture area the model's hands use (triangles skinned to the hand bones), slightly grown"""
    from iqm import read_iqm
    from PIL import ImageDraw, ImageFilter
    W, H = size
    m = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(m)
    J, M, _ = read_iqm(f'{OUT}/models/{char}/{char}.iqm')
    hand = {i for i, j in enumerate(J) if 'hand' in j[0] or 'finger' in j[0] or 'thumb' in j[0]}
    for x in M:
        if x['material'] != f'{mat}.png': continue
        dom = x['bidx'][np.arange(len(x['bidx'])), x['bw'].argmax(1)]
        for t in x['tris']:
            if all(dom[v] in hand for v in t):
                dr.polygon([(x['uv'][v][0] * W, x['uv'][v][1] * H) for v in t], fill=255)
    m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    return np.asarray(m).astype(np.float32) / 255.0

# SHELL_TINT: variants.py

def bake_shell(tint, outpath):
    """the shield flare's skin: its colour, flat (PLASMA_SHADER draws the plasma in it). Every one goes in SHELL_TEX
    (pack-relative paths, models/...) for its plasma material (shader_gl)"""
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    Image.new('RGB', (4, 4), tuple(int(round(c * 255)) for c in tint)).save(outpath)
    SHELL_TEX.add(outpath[outpath.index('models/'):])

SHELL_TEX = set()            # every shield flare skin (bake_shell): the plasma shader's
# Halo's own shield shaders, ported (templates/shaders; their textures from extract_shader_maps.py in shader_maps/):
# the shield flares (Halo CE's shield plasma), the Sentinels' bubbles (Halo 2's plasma_shield), the Jackals' and the
# Sentinel Enforcer's shields (Halo CE's Jackal shield combiner) drawn by their field (HCE_ShieldField)
SHADER_MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shader_maps')
FIELD_CHARS = {'Jackal', 'JackalMajor'}      # bodies whose arm shield is drawn by a shield field (build_digsite adds the Halo 2 Jackal)
ENFORCER_FIELD_TINT = (132, 148, 255)    # Halo 2's energy_shield: its constant colour 2
def mesh_layers(iqm_path, si):
    """how many times surface si of an IQM draws each of its triangles (Halo 2's Jackal shield: four copies, both
    faces of two layers): an additive field over it is divided by that, so it shows as one layer"""
    from iqm import read_iqm
    from collections import Counter
    x = read_iqm(iqm_path)[1][si]
    pos = np.round(np.array(x['pos'], dtype=np.float64), 3)
    return max(Counter(tuple(sorted(map(tuple, pos[t]))) for t in x['tris']).values())

FIELD_TEX = {}               # field skin (models/...) -> (its maps' prefix in shader_maps ('jshield' or 'enf'), the mesh's layers, its own mask or None)
FIELD_UV_MASK = set()        # field bodies whose shield isn't laid out like the Jackal's: a mask baked from its own UVs (field_mask)

def field_mask(iqm_path, si, dst):
    """a Jackal-shield mask for surface si laid out its own way (the Ultra Zealot's arm shield, three diamonds): the
    alpha the CE mask's body grey (0.72) inside the surface's UV shapes, rising to white at their edges (Halo's rim),
    the rgb a faint pale-blue rim; outside, white (nothing drawn there)"""
    from iqm import read_iqm
    from scipy import ndimage
    from PIL import ImageDraw
    x = read_iqm(iqm_path)[1][si]
    N = 256
    im = Image.new('L', (N, N), 0); d = ImageDraw.Draw(im)
    for t in x['tris']:
        d.polygon([(x['uv'][v][0] % 1 * N, x['uv'][v][1] % 1 * N) for v in t], fill=255)
    inside = np.asarray(im) > 0
    rim = 1.0 - np.clip(ndimage.distance_transform_edt(inside) / (N * 0.035), 0, 1)
    a = np.where(inside, 0.72 + 0.28 * rim, 1.0)
    rgb = np.stack([rim * 0.35, rim * 0.55, rim * 0.6], 2) * inside[..., None]
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray((np.concatenate([rgb, a[..., None]], 2) * 255).astype(np.uint8), 'RGBA').save(dst)

# Active camo shimmer (GLSL material shader on the camo variants' skins; the actor itself is translucent)
SHIELD_SHADER = template('shaders/shield.fp')
BUBBLE_SHADER = template('shaders/bubble.fp')
JSHIELD_SHADER = template('shaders/jshield.fp')
PLASMA_SHADER = template('shaders/plasma.fp').replace('{REF}', '0.45, 0.70, 1.00')          # SHELL_TINT['Elite']
PLASMA_H2_SHADER = '#define HCE_H2\n' + template('shaders/plasma.fp').replace('{REF}', '0.45, 0.75, 1.00')  # SHIELD_TINT['sentinel_minor']

SWORD_SHADER = template('shaders/sword.fp')

CAMO_SHADER = template('shaders/camo.fp')

# ---------------------------------------------------------------- generation
# gore_kit.py's limb names -> the API's limb numbers (HCE_LIMB_HEAD, HCE_LIMB_LARM, HCE_LIMB_RARM, HCE_LIMB_BACK)
GORE_LIMBS = {'head': 0, 'larm': 1, 'rarm': 2, 'back': 3}

# HDE plasma bolt classes the enemies fire -> also thin out the smoke trail (their own Tick does only that)
LITE_PLASMA = {'HaloPlasma_Proj': True, 'HaloPlasmaRifle_Proj': True, 'HaloPulseCarbine_Proj': False, 'HaloChargedPlasma_Proj': False}

# a body whose shell slot holds its energy-shield flare and whose arm shield has a shield field (the Ultra Zealot): the
# field rides as its hologram companion (hce_holoActor: placed by the field, animated with the body), spawned once
FIELD_HOLO_CODE = '''	// its arm shield: drawn by its own shield field (HCE_ShieldField, one class per variant), its hologram companion
	bool hce_fieldTried;
	override void Tick()
	{
		super.Tick();
		if(hce_fieldTried || bDestroyed || health <= 0) return;
		hce_fieldTried = true;
		Name fn = String.Format("%sShieldField", GetClassName());
		class<Actor> fc = (class<Actor>)(fn);
		if(fc && !hce_holoActor) { hce_holoActor = Spawn(fc, pos, NO_REPLACE); if(hce_holoActor) { hce_holoActor.master = self; hce_holoActor.angle = angle; } }
	}
'''

def machine_code(char, mdir, ov):
    """a Sentinel's machine death (HaloDoom_EnemyBase.HCE_MachineBurst): knocked out of the air with a pop of sparks,
    then blown apart where it lands, its hull in pieces cut from its own model. Its size (1-3, the blast's and the
    debris's) from its radius: the Enforcer's 3"""
    r = ov.get('radius_fixed') or ov.get('radius') or 20
    size = 3 if r >= 44 else 2 if r >= 28 else 1
    return (f"\t// no death in the games but an explosion and debris (HCE_MachineBurst), its hull's pieces from its own model\n"
            f"\toverride int HCE_MachineSize() {{ return {size}; }}\n"
            f"\toverride String HCE_ModelPath() {{ return \"models/{mdir}/{char}\"; }}\n"
            f"\toverride Name HCE_ModelFile() {{ return '{char}.iqm'; }}\n")

def gore_code(char, meta, mdir, sc):
    """HCE_SeverLimb for a character with gore_kit.py's dismemberment data: hide the limb's surfaces (and what it
    holds), show its gore stump, throw the gib"""
    g = meta.get('gore')
    if not g: return ''
    mw = meta.get('mesh_weapon') or []
    out = ['\toverride bool HCE_SeverLimb(int limb)\n\t{\n\t\tif(hce_severed & (1 << limb)) return false;\n\t\tswitch(limb)\n\t\t{\n']
    perms = body_perms(meta)
    def stub_and_gib(x, ind):
        """the lines showing a limb's stump (x: its gore entry) and throwing its gib, at indent ind ({L}: the limb number)"""
        c = x['center']
        show = (f'{ind}HCE_ShowStumps(hce_severed | (1 << {{L}}));\n' if g.get('cap_model') else
                ''.join(f'{ind}A_ChangeModel(\'None\', 0, "", \'None\', {si}, "", \'None\', CMDL_USESURFACESKIN);\n' for si in x['swap'])
                if x.get('swap') else       # the limb's damaged permutation: back to its MODELDEF skin
                f'{ind}A_ChangeModel(\'None\', 0, "", \'None\', {x["stub"]}, "models/{mdir}/{char}", \'{g["tex"]}\', CMDL_USESURFACESKIN);\n')
        return (show +
                f'{ind}HCE_SpawnLimb({{L}}, ({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}), {sc:.2f}, "models/{mdir}/{char}", \'{x["gib"]}\', {x.get("gib_stub", x["stub"])}, \'{g["tex"]}\', {x.get("rest", 0):.4f});\n')
    for L, d in g['limbs'].items():
        gun = any(si < len(mw) and mw[si] for si in d['surfaces'])
        out.append(f'\t\tcase {GORE_LIMBS[L]}:\n')
        for si in d['surfaces']:
            out.append(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n')
            # the shield flare loses the limb too
            out.append(f'\t\t\tif(hce_shellActor) hce_shellActor.A_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n')
            if char in FIELD_CHARS and char in SHELL_TINT:      # and its arm shield's field (FIELD_HOLO_CODE)
                out.append(f'\t\t\tif(hce_holoActor) hce_holoActor.A_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n')
        if d.get('bone'):                          # a collapsed limb (gore_kit.py: the Brute's arms): its bone scaled to
            out.append(f'\t\t\tif(bDECOUPLEDANIMATIONS) SetNamedBoneScaling(\'{d["bone"]}\', (0, 0, 0), SB_REPLACE, 0);\n')   # nothing, and all it carries
            out.append(f'\t\t\tif(hce_shellActor) hce_shellActor.SetNamedBoneScaling(\'{d["bone"]}\', (0, 0, 0), SB_REPLACE, 0);\n')
        vs = d.get('variants')
        if vs and perms:
            # one stump and gib per permutation (the Grunts' two backs): the one this enemy wears
            for k, q in enumerate(perms):
                if q not in vs: continue
                out.append(f'\t\t\t{"if" if k == 0 else "else if"}(hce_perm == {k})\n\t\t\t{{\n'
                           + stub_and_gib(vs[q], '\t\t\t\t').replace('{L}', str(GORE_LIMBS[L])) + '\t\t\t}\n')
        else:
            out.append(stub_and_gib(d, '\t\t\t').replace('{L}', str(GORE_LIMBS[L])))
        out.append(f'\t\t\tHCE_OnSever({GORE_LIMBS[L]}, {"true" if gun else "false"});\n\t\t\treturn true;\n')
    out.append('\t\t}\n\t\treturn false;\n\t}\n')
    swaps = sorted(si for d in g['limbs'].values() for si in d.get('swap', []))
    if swaps:
        # Halo CE's damaged permutations (gore_kit.py's swapped limbs): drawn with their skins in the MODELDEF, hidden
        # from the first tic until their limb comes off
        out.append('\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n'
                   f'\t\tstatic const int D[] = {{ {", ".join(map(str, swaps))} }};\n'
                   f'\t\tfor(int i = 0; i < D.Size(); i++) A_ChangeModel(\'None\', 0, "", \'None\', D[i], "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n'
                   '\t\tHCE_ResumeAnim();\n\t}\n')
    if g.get('cap_model'):
        # the stumps are a model of their own (gore_kit.py cap_model), attached at model slot cap_slot once a limb is off:
        # the severed limbs' stumps shown, the rest hidden
        cs, cm = g['cap_slot'], g['cap_model']
        out.append('\tvoid HCE_ShowStumps(int sev)\n\t{\n')
        for L, d in g['limbs'].items():
            out.append(f'\t\tif(sev & (1 << {GORE_LIMBS[L]})) A_ChangeModel(\'None\', {cs}, "models/{mdir}/{char}", \'{cm}\', {d["stub"]}, "models/{mdir}/{char}", \'{g["tex"]}\', CMDL_USESURFACESKIN);\n'
                       f'\t\telse A_ChangeModel(\'None\', {cs}, "models/{mdir}/{char}", \'{cm}\', {d["stub"]}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n')
        out.append('\t}\n')
    # limb centres in map units (hit location: which limb a shot struck) and the arm holding the gun
    out.append('\toverride vector3 HCE_LimbOffset(int limb)\n\t{\n\t\tswitch(limb)\n\t\t{\n')
    for L, d in g['limbs'].items():
        c = d['center']
        out.append(f'\t\tcase {GORE_LIMBS[L]}: return ({c[0] * sc:.1f}, {c[1] * sc:.1f}, {c[2] * sc * 1.2:.1f});\n')
    out.append('\t\t}\n\t\treturn (0, 0, -1000);\n\t}\n')
    guns = [GORE_LIMBS[L] for L, d in g['limbs'].items() if L != 'head' and any(si < len(mw) and mw[si] for si in d['surfaces'])]
    if guns: out.append(f'\toverride int HCE_GunLimb() {{ return {guns[0]}; }}\n')
    return ''.join(out)


def body_perms(meta):
    """the permutations of a body region rolled per enemy at run time, other than the Marines' cosmetics (the Grunts'
    regular and 'shellback' backs: mesh_names 'perm head and back.<perm>'), in a fixed order"""
    names = meta.get('mesh_names') or []
    return sorted({n.split('.', 1)[1] for n in names if n.startswith('perm head and back.')})


def perm_code(meta, mdir):
    """each Grunt wears one of Halo CE's two backs, the regular methane tank or the rounded 'shellback', rolled when
    it spawns: the other back's surfaces (and its blood overlay) are hidden"""
    perms = body_perms(meta)
    if len(perms) < 2: return ''
    names = meta['mesh_names']
    hid = f'"models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN'
    sets = []
    for k, q in enumerate(perms):
        other = [i for i, n in enumerate(names) if n.startswith('perm head and back.') and not n.endswith('.' + q)]
        sets.append(f'\t\tcase {k}: {{ static const int H[] = {{ {", ".join(map(str, other))} }}; for(int i = 0; i < H.Size(); i++) hce_permHide.Push(H[i]); break; }}\n')
    return ('\t// Halo CE\'s two Grunt backs (' + ', '.join(perms) + '), one rolled per Grunt\n'
            '\tint hce_perm;\n\tArray<int> hce_permHide;\n'
            '\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n'
            f'\t\thce_perm = random[HCEPerm](0, {len(perms) - 1});\n\t\thce_permHide.Clear();\n\t\tswitch(hce_perm)\n\t\t{{\n' + ''.join(sets) + '\t\t}\n'
            f'\t\tfor(int i = 0; i < hce_permHide.Size(); i++) A_ChangeModel(\'None\', 0, "", \'None\', hce_permHide[i], {hid});\n'
            '\t\tHCE_ResumeAnim();        // A_ChangeModel resets the animation the spawn started (idle, sleeping)\n\t}\n'
            f'\toverride void HCE_BloodHideClass()\n\t{{\n\t\tsuper.HCE_BloodHideClass();\n'
            f'\t\tfor(int i = 0; i < hce_permHide.Size(); i++) A_ChangeModel(\'None\', {BLOOD_IDX}, "", \'None\', hce_permHide[i], {hid});\n\t}}\n'
            '\toverride void HCE_DressShell(Actor s)       // the shield flare wears the same permutation\n\t{\n\t\tsuper.HCE_DressShell(s);\n'
            f'\t\tfor(int i = 0; i < hce_permHide.Size(); i++) s.A_ChangeModel(\'None\', 0, "", \'None\', hce_permHide[i], {hid});\n\t}}\n')


def gun_code(meta, mdir, slot=None):
    """HCE_ShowGun: the gun surfaces baked into the body (mesh_weapon), hidden when it dies or loses its gun arm,
    back to the MODELDEF's skins ('None') when a Flood form gets up again"""
    ws = [i for i, w in enumerate(meta.get('mesh_weapon') or []) if w]
    if not ws: return ''
    return ('\toverride void HCE_ShowGun(bool show)\n\t{\n\t\tsuper.HCE_ShowGun(show);\n'
            f'\t\tstatic const int W[] = {{ {", ".join(map(str, ws))} }};\n'
            '\t\tfor(int i = 0; i < W.Size(); i++)\n'
            '\t\t{\n\t\t\tif(show) A_ChangeModel(\'None\', 0, "", \'None\', W[i], "", \'None\', CMDL_USESURFACESKIN);\n'
            '\t\t\telse HCE_HideSurface(W[i]);    // the guns it never held stay undrawn\n\t\t}\n'
            + (f'\t\tif(!show && hce_hasLoadout) A_ChangeModel(\'None\', {slot}, "", \'None\', 0, "", \'None\', CMDL_HIDEMODEL);   // a picked-up overlay gun\n'
               if slot is not None else '') + '\t}\n')


def overlay_gun_code(char, meta, mdir, ov, pack=None):
    """HCE_ShowGun for a variant whose gun is an overlay model (the Marine arsenal, the Plasma Casters). Showing it
    again puts back its own skins too: a gun traded or picked up in the meantime left its own on the slot's
    surfaces, and the class's gun would wear them"""
    oi = ov.get('overlay_idx', ARSENAL_IDX)
    own = ''.join('\t' + l for l in overlay_swap(char, meta, mdir, ov['overlay'], oi, pack).splitlines(True))
    return ('\toverride void HCE_ShowGun(bool show)\n\t{\n\t\tsuper.HCE_ShowGun(show);\n'
            f'\t\tif(show)\n\t\t{{\n{own}\t\t}}\n'
            f'\t\telse A_ChangeModel(\'None\', {oi}, "", \'None\', 0, "", \'None\', CMDL_HIDEMODEL);\n\t}}\n')


# a Hunter's severed cannon arm comes off as HaloDoom's own weapon (the right arm, limb 2)
HUNTER_ARM_WEAPON = {'hunter fuel rod': 'Halo_FuelRod', 'fuel rod': 'Halo_FuelRod', 'plasma caster': 'Halo_PlasmaCaster',
                     'flamethrower': 'Halo_Flamethrower'}


# Sergeant Stacker's face: Halo CE's white face under the sergeant's cap (his and nobody else's, like Johnson's)
STACKER_HEAD = 'head_marcus_cap-101'

# Lip-sync: Halo CE moved the Marines' jaw ('bip01 ponytail1') with their dialogue; the animations hold it shut
# (extract_chars.py). While a Marine's voice channel plays, the jaw flaps open and shut in a speech rhythm, opening
# about its local +z axis (the chin down), added on top of the animation (SetNamedBoneRotation, SB_ADD: animation *
# this). The heads' bind pose has the mouth hanging some 10 degrees open, so at rest the jaw is held 10 degrees shut
# (HCE_JAW_SHUT) and speech opens it up to 4 past the bind. jaw_weights.py gives the jaw a clean hinge, so only the
# lower lip and chin move
LIP_CODE = template('zscript/lip.zs')


MARINE_KIT = f'{OUT}/models/MarineKit'
# the kit's slots in the order hce_kit[] holds them (index 0 head, 1 face, 3 back ...: the ZScript overrides index it
# by position, so keep the order); each is a model attachment (MarineKit.json 'slots' gives the model index)
KIT_SLOT_ORDER = ('head', 'face', 'chest', 'back', 'shoulders', 'arms', 'legs', 'wrists', 'waist')
MEDIC_KIT = ('first_aid',)          # the corpsmen's kit pieces (the red-cross first-aid kit): theirs only


def marine_kit_code(char, names, mdir, sis):
    """Elefant's Marine kit (extract_marine_kit.py): per Marine, a roll per slot for a kit piece drawn as a model
    attachment on the Marine's skeleton, or (now and then) a whole outfit (the ODST). Headgear either replaces the
    whole head or (a helmet shell) only Halo CE's helmet; gloves replace the arms. A rocket launcher's Marine always
    wears the launcher tube on his back, a flamethrower's the fuel tanks. Returns (fields and functions, the call
    made while dressing)"""
    kj = f'{MARINE_KIT}/MarineKit.json'
    if not os.path.exists(kj): return '', ''
    kit = json.load(open(kj))
    pools = kit['pools'].get(char)
    if not pools: return '', ''
    # the first-aid kit (its red cross) is the corpsmen's alone: off everyone else's rolls, always on a corpsman
    pools = {sl: dict(p, picks=[(pid, w) for pid, w in p['picks'] if pid not in MEDIC_KIT]) for sl, p in pools.items()}
    P = kit['pieces']
    NS = len(KIT_SLOT_ORDER)
    out = ['\t// ---- Elefant\'s Marine kit (extract_marine_kit.py): headgear, face and head add-ons, chest rigs and pouches,\n'
           '\t// packs, shoulder pads, gloves and the ODST\'s armour, each a model attachment riding the Marine\'s skeleton\n']
    def weighted(fn, picks, chance=None):
        """a ZScript function fn() rolling one piece id from picks [(id, weight)] ("" for none); chance: the odds of
        wearing anything in the slot at all"""
        tot = sum(w for _, w in picks)
        b = [f'\tString {fn}()\n\t{{\n']
        if chance is not None: b.append(f'\t\tif(frandom[HCEKit](0, 1) >= {chance:.2f}) return "";\n')
        b.append(f'\t\tdouble x = frandom[HCEKit](0, {tot:g});\n')     # (the weights may be fractional)
        acc = 0
        for pid, w in picks:
            acc += w
            b.append(f'\t\tif(x < {acc:g}) return "{pid}";\n')
        b.append('\t\treturn "";\n\t}\n')
        return b
    for slot in KIT_SLOT_ORDER:
        pool = pools.get(slot)
        if pool and pool['picks']: out += weighted(f'HCE_Kit_{slot}', pool['picks'], pool['chance'])
    outfits = kit.get('outfits', {}).get(char, [])
    for k, o in enumerate(outfits):
        for slot, picks in o['slots'].items():
            if picks: out += weighted(f'HCE_KitOutfit{k}_{slot}', picks)
    def flag(fn, key):
        """a static ZScript predicate fn(piece) true for the pieces whose kit entry has the flag key set"""
        ids = [pid for pid, d in P.items() if d.get(key)]
        return f'\tstatic bool {fn}(String p) {{ ' + ('return ' + ' || '.join(f'p == "{i}"' for i in ids) + ';' if ids else 'return false;') + ' }\n'
    out += [flag('HCE_KitShell', 'shell'), flag('HCE_KitEnclosed', 'enclosed'), flag('HCE_KitNeedsHelmet', 'needs_helmet')]
    heads = sis(lambda n: n.startswith('head.'))
    shared = sis(lambda n: n == 'head.shared')
    arms = sis(lambda n: n.startswith('arms.'))
    def ints(v): return ', '.join(map(str, v or [-1]))
    SI = {sl: k for k, sl in enumerate(KIT_SLOT_ORDER)}
    d = [f'\tString hce_kit[{NS}];\n', '\tvoid HCE_DressKit(bool helmetFace)\n\t{\n',
         f'\t\tfor(int i = 0; i < {NS}; i++) hce_kit[i] = "";\n', '\t\tbool outfit = false;\n']
    for k, o in enumerate(outfits):
        d.append(f'\t\tif(!outfit && frandom[HCEKit](0, 1) < {o["chance"]:.2f})\n\t\t{{\n\t\t\toutfit = true;\n')
        for slot, picks in o['slots'].items():
            if picks: d.append(f'\t\t\thce_kit[{SI[slot]}] = HCE_KitOutfit{k}_{slot}();\n')
        d.append('\t\t}\n')
    d.append('\t\tif(!outfit)\n\t\t{\n')
    for slot in KIT_SLOT_ORDER:
        if pools.get(slot) and pools[slot]['picks']: d.append(f'\t\t\thce_kit[{SI[slot]}] = HCE_Kit_{slot}();\n')
    d.append('\t\t}\n')
    for pid in MEDIC_KIT:
        if pid in P: d.append(f'\t\tif(hce_isMedic) hce_kit[{SI[P[pid]["slot"]]}] = "{pid}";     // a corpsman\'s first-aid kit, always\n')
    wb = kit.get('weapon_backs', {})
    if wb:
        d.append('\t\tName w = default.hce_dropWeapon;          // a weapon\'s own back piece, always\n')
        for wn, pid in wb.items():
            d.append(f'\t\tif(w == \'{wn}\') hce_kit[{SI["back"]}] = "{pid}";\n')
    d.append('\t\tHCE_KitOverride();                       // a class\'s own kit (the Pilots\' heads, the radio operator\'s set)\n')
    out.append('\tvirtual void HCE_KitOverride() {}\n')
    d.append('\t\tString h = hce_kit[0];\n'
             '\t\tif(h.Length() && HCE_KitShell(h) && !helmetFace) { h = ""; hce_kit[0] = ""; }     // a helmet shell only where Halo CE\'s helmet was\n'
             '\t\tif(h.Length())\n\t\t{\n'
             f'\t\t\tstatic const int HS[] = {{ {ints(shared)} }};\n'
             f'\t\t\tstatic const int HA[] = {{ {ints(heads)} }};\n'
             '\t\t\tif(HCE_KitShell(h)) { for(int i = 0; i < HS.Size(); i++) if(HS[i] >= 0) hce_hideSurf.Push(HS[i]); }\n'
             '\t\t\telse { for(int i = 0; i < HA.Size(); i++) if(HA[i] >= 0 && hce_hideSurf.Find(HA[i]) == hce_hideSurf.Size()) hce_hideSurf.Push(HA[i]); }\n'
             '\t\t}\n'
             '\t\tString f = hce_kit[1];\n'
             '\t\tif(HCE_KitEnclosed(h)) f = "";                      // no face showing\n'
             '\t\tif(f.Length() && HCE_KitNeedsHelmet(f) && (!helmetFace || h.Length())) f = "";\n'
             '\t\thce_kit[1] = f;\n'
             f'\t\tif(hce_kit[{SI["arms"]}].Length())\n\t\t{{\n'
             f'\t\t\tstatic const int AR[] = {{ {ints(arms)} }};\n'
             '\t\t\tfor(int i = 0; i < AR.Size(); i++) if(AR[i] >= 0 && hce_hideSurf.Find(AR[i]) == hce_hideSurf.Size()) hce_hideSurf.Push(AR[i]);\n'
             '\t\t}\n')
    slots = [kit['slots'][sl] for sl in KIT_SLOT_ORDER]
    d.append(f'\t\tstatic const int SL[] = {{ {", ".join(map(str, slots))} }};\n'
             f'\t\tfor(int i = 0; i < {NS}; i++)\n'
             f'\t\t\tif(hce_kit[i].Length()) A_ChangeModel(\'None\', SL[i], "models/{mdir}/MarineKit", hce_kit[i] .. ".iqm", SL[i], "", \'None\');\n'
             '\t}\n')
    return ''.join(out + d), '\t\tif(!hce_johnsonArms) HCE_DressKit(HCE_HELMET_FACE[hce_face] != 0);\n'


def jaw_shut(char, heads):
    """per face, the jaw rotation (degrees, negative closing) that shuts its mouth: the gap at the bind pose between its
    lower lip (the front of the jaw-weighted vertices on the midline) and the upper lip just above it, seen from the jaw's hinge, and 1.5
    degrees more so the lips meet. Faces without a jaw (or no gap) get a small closing turn"""
    from iqm import read_iqm
    import preview as pv
    joints, meshes, _ = read_iqm(f'{OUT}/models/{char}/{char}.iqm')
    names = [j[0] for j in joints]
    if 'bip01 ponytail1' not in names: return [-10.0] * len(heads)
    J = names.index('bip01 ponytail1')
    W = pv.world([j[1] for j in joints], [(j[2], j[3]) for j in joints])
    piv = np.asarray(W[J][0])
    mn = json.load(open(f'{OUT}/models/{char}/{char}.json'))['mesh_names']
    out = []
    for h in heads:
        P = [m['pos'] for i, m in enumerate(meshes) if mn[i] == f'head.{h}']
        Wj = [(m['bw'] * (m['bidx'] == J)).sum(1) / 255.0 for i, m in enumerate(meshes) if mn[i] == f'head.{h}']
        if not P: out.append(-6.0); continue
        P = np.concatenate(P); Wj = np.concatenate(Wj)
        mid = np.abs(P[:, 1] - piv[1]) < 0.006                      # the midline: the corners of the mouth curl up
        jaw, other = P[(Wj > 0.5) & mid], P[(Wj < 0.1) & mid]
        if len(jaw) < 3 or not len(other): out.append(-6.0); continue
        def ang(Q): return np.degrees(np.arctan2(Q[:, 2] - piv[2], Q[:, 0] - piv[0]))
        lo = jaw[jaw[:, 0] > jaw[:, 0].max() - 0.012]                # the lower lip
        a_lo = ang(lo).max(); top = lo[np.argmax(ang(lo))]
        up = other[(other[:, 0] > top[0] - 0.0025)]                  # its front edge (not the inside of the mouth)
        up = up[ang(up) > a_lo]                                      # the upper lip just above it
        if not len(up): out.append(-6.0); continue
        a_up = ang(up).min()
        out.append(-float(np.clip(a_up - a_lo + 1.5, 3.0, 12.0)))
    return out


def marine_code(meta, mdir, char='Marine'):
    """Halo CE's Marine cosmetics, rolled per Marine (extract_chars.MULTI_PERMS): a random face (bare heads, boonie
    hats, bandanas, caps, helmets), sleeves rolled down on some, the battle-damaged vest on some Armored Marines.
    Sergeant Johnson's face (the dark-skinned one) brings his full-sleeved arms and always his own voice"""
    names = meta.get('mesh_names') or []
    heads = sorted({n.split('.', 1)[1] for n in names if n.startswith('head.') and n != 'head.shared'})
    if len(heads) < 2: return ''
    def sis(pred): return sorted(i for i, n in enumerate(names) if pred(n))
    def jarms(n): return 'johnson' in n or 'sleeve-100' in n
    arms = sorted({n for n in names if n.startswith('arms.') and not jarms(n)})
    torsos = sorted({n for n in names if n.startswith('torso.')})
    cases = []
    for k, h in enumerate(heads):
        johnson = 'johnson' in h
        sergeant = johnson or h == STACKER_HEAD           # the sergeants wear the full-sleeved arms
        helmet = 'cap' not in h and not johnson
        hide = sis(lambda n: n.startswith('head.') and n != 'head.shared' and n != f'head.{h}')
        if not helmet: hide += sis(lambda n: n == 'head.shared')
        if johnson: hide += sis(lambda n: n.startswith('arms.') and not jarms(n))
        elif sergeant:
            # Stacker is white: the full sleeves without Johnson's dark hands (the regular Marines' full sleeves),
            # else the plain arms; never Johnson's
            full = [n for n in names if n.startswith('arms.') and 'sleeve' in n and not jarms(n)]
            keep = full[0] if full else 'arms.__base'
            hide += sis(lambda n, keep=keep: n.startswith('arms.') and n != keep)
        else: hide += sis(jarms)
        cases.append(f'\t\tcase {k}: {{ static const int H[] = {{ {", ".join(map(str, sorted(hide)))} }}; for(int i = 0; i < H.Size(); i++) hce_hideSurf.Push(H[i]);'
                     + (" hce_voice = 'Marine_Johnson';" if johnson else '') + ' break; }\n')
    roll = ''
    if len(arms) > 1:            # sleeves: rolled up (the base arms) on most, down on about a third
        sets = [sis(lambda n, a=a: n.startswith('arms.') and not jarms(n) and n != a) for a in arms]
        pick = 'random(0, 2) == 2 ? 1 : 0' if len(arms) == 2 else f'random(0, {len(arms) - 1})'
        roll += (f'\t\tif(!hce_johnsonArms)\n\t\t{{\n\t\t\tint a = {pick};\n'
                 + ''.join(f'\t\t\tif(a == {k}) {{ static const int A{k}[] = {{ {", ".join(map(str, st))} }}; for(int i = 0; i < A{k}.Size(); i++) hce_hideSurf.Push(A{k}[i]); }}\n'
                           for k, st in enumerate(sets)) + '\t\t}\n')
    if len(torsos) > 1:          # the Armored Marines' vest: battle-damaged on about one in five
        base = next(t for t in torsos if '__base' in t)
        dmg = [t for t in torsos if t != base]
        hb = sis(lambda n: n == base); hd = sis(lambda n: n in dmg)
        roll += (f'\t\tif(!hce_johnsonArms && random(0, 4) == 0) {{ static const int T[] = {{ {", ".join(map(str, hb))} }}; for(int i = 0; i < T.Size(); i++) hce_hideSurf.Push(T[i]); }}\n'
                 f'\t\telse {{ static const int T[] = {{ {", ".join(map(str, hd))} }}; for(int i = 0; i < T.Size(); i++) hce_hideSurf.Push(T[i]); }}\n')
    hid = f'"models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN'
    kit_fns, kit_call = marine_kit_code(char, names, mdir, sis)
    helmet_face = ['1' if ('cap' not in h and 'johnson' not in h and 'head.shared' in names) else '0' for h in heads]
    jk = next((k for k, h in enumerate(heads) if 'johnson' in h), -1)
    sk = next((k for k, h in enumerate(heads) if h == STACKER_HEAD), -1)
    others = [k for k in range(len(heads)) if k not in (jk, sk)]
    shut = jaw_shut(char, heads)
    jaw_fn = ('\tstatic const double HCE_JAW_SHUT_FACE[] = { ' + ', '.join(f'{x:.1f}' for x in shut) + ' };   // jaw_shut, per face\n'
              '\tdouble HCE_JawShut() { return hce_face >= 0 && hce_face < HCE_JAW_SHUT_FACE.Size() ? HCE_JAW_SHUT_FACE[hce_face] : -10.0; }\n')
    return (LIP_CODE + jaw_fn + '\t// Halo CE\'s Marine cosmetics, rolled per Marine: face and headgear, sleeves, the damaged vest. Sergeant\n'
            '\t// Johnson\'s face (with his own voice and sleeves) is his alone: only HCE_SgtJohnson wears it\n'
            f'\tconst HCE_JOHNSON_FACE = {jk};\n\tconst HCE_STACKER_FACE = {sk};\n'
            f'\tstatic const int HCE_HELMET_FACE[] = {{ {", ".join(helmet_face)} }};\n' + kit_fns +
            '\tArray<int> hce_hideSurf;\n\tint hce_face;\n\tbool hce_johnsonArms;\n'
            '\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n\t\tHCE_DressMarine();\n\t}\n'
            f'\tvirtual int HCE_PickFace() {{ static const int F[] = {{ {", ".join(map(str, others))} }}; return F[random(0, {len(others) - 1})]; }}\n'
            '\tvoid HCE_DressMarine()\n\t{\n\t\thce_hideSurf.Clear();\n'
            f'\t\thce_face = HCE_PickFace();\n\t\thce_johnsonArms = hce_face == HCE_JOHNSON_FACE || hce_face == HCE_STACKER_FACE;\n\t\tswitch(hce_face)\n\t\t{{\n' + ''.join(cases) + '\t\t}\n'
            + roll + kit_call +
            f'\t\tfor(int i = 0; i < hce_hideSurf.Size(); i++) A_ChangeModel(\'None\', 0, "", \'None\', hce_hideSurf[i], {hid});\n'
            '\t\tHCE_ResumeAnim();        // A_ChangeModel resets the animation the spawn started\n\t}\n'
            f'\toverride void HCE_BloodHideClass()\n\t{{\n\t\tfor(int i = 0; i < hce_hideSurf.Size(); i++) A_ChangeModel(\'None\', {BLOOD_IDX}, "", \'None\', hce_hideSurf[i], {hid});\n\t}}\n')


# Halo's collision_height_standing stops at the shoulders (Halo hit-tests the head with its own bone collision): in
# their stances the heads stand above it, so shots at the top of a head passed over the box and headshots and
# beheadings were rare. Heights up to the top of the head in the idle stances (head bone + its geometry)
HEAD_CLEAR = {'Elite': 68, 'EliteSpecial': 68, 'Grunt': 48, 'GruntSpecOps': 48, 'Jackal': 54, 'JackalMajor': 54,
              'Marine': 58, 'MarineArmored': 58, 'MarineODST': 58}

BLOOD_IDX = 7     # model attachment index of the blood overlay (the Brutes' armour kit uses 1-6)

def blood_code(char, meta, mdir):
    """HCE_BloodModel / HCE_BloodHideLimb for a character with blood_kit.py's overlay, and HCE_ResumeAnim"""
    out = ['\toverride void HCE_ResumeAnim()\n\t{\n\t\tif(hce_curAnim == \'None\') return;\n'
           '\t\tint len = max(1, int(HCE_AnimTics(hce_curAnim) * 30.0 / 35.0));\n'
           '\t\tint f = int((level.maptime - hce_animStartTic) * 30.0 / 35.0);\n'
           '\t\tSetAnimation(hce_curAnim, -1, hce_curLoop ? f % len : min(f, len - 1), -1, -1, 0, hce_curLoop ? SAF_LOOP : 0);\n\t}\n']
    b = meta.get('blood')
    if not b: return ''.join(out)
    out.append('\toverride void HCE_BloodModel(int stage)\n\t{\n\t\tswitch(stage)\n\t\t{\n')
    for k, m in enumerate(b['models']):
        out.append(f'\t\tcase {k + 1}: A_ChangeModel(\'None\', {BLOOD_IDX}, "models/{mdir}/{char}", \'{m}\'); break;\n')
    out.append('\t\t}\n\t}\n')
    g = meta.get('gore')
    if g:
        out.append('\toverride void HCE_BloodHideLimb(int limb)\n\t{\n\t\tswitch(limb)\n\t\t{\n')
        for L, d in g['limbs'].items():
            sis = [si for si in d['surfaces'] if si in b['surfaces']]
            out.append(f'\t\tcase {GORE_LIMBS[L]}:\n' + ''.join(blood_hide(si, mdir) for si in sis) + '\t\t\tbreak;\n')
        out.append('\t\t}\n\t}\n')
    return ''.join(out)

def blood_hide(si, mdir):
    """the ZScript line hiding surface si of the blood overlay (model BLOOD_IDX)"""
    return f'\t\t\tA_ChangeModel(\'None\', {BLOOD_IDX}, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n'


# ---------------------------------------------------------------- weapons off the ground
# Every gun a body can be seen with (its own model surfaces for the Covenant, the arsenal overlays for the Marines)
# becomes a loadout the body's base class can switch to at run time when it picks that HDE weapon up
# (HaloDoom_EnemyBase.HCE_ScavengeScan): the firing data, sounds and animations of the pack's own class that carries
# it. Guns with their own extra code (beam rifle, sticky detonator, Stanchion), the energy sword and the Plasma Caster
# stay with the classes that are built around them.
PICKUP_TEAMS = ('HUMAN', 'COVENANT')
# bodies that carry some guns as overlay models: the slot (hidden when a baked-in gun is picked up), and the bodies
# whose every class gets that slot in its MODELDEF (an empty gun until it picks one up)
OVERLAY_SLOT = {'EliteSpecial': 6}
OVERLAY_PLACEHOLDER = set()
# the Covenant only ever pick up Covenant guns -- except the Brutes, the one Covenant race that uses human guns too
COVENANT_GUNS = {'Halo_PlasmaPistol', 'Halo_PlasmaRifle', 'Halo_Needler', 'Halo_FuelRod', 'Halo_BeamRifle', 'Halo_Carbine',
                 'Halo_PlasmaCaster', 'Halo_Spiker', 'Halo_PulseCarbine', 'Halo_NeedlerJavelin'}
PICKUP_SKIP = {'energy sword', 'hunter fuel rod', 'stanchion'}       # melee, the Hunters' arm, the BFG-class Stanchion


def loadout_code(char, prof, A):
    """the base class's loadouts: prof {HDE weapon class: the firing data, sounds, animation table and the model
    changes (visual) of the pack's class that carries it, gathered in build()} -> HCE_LoadoutIndex / HCE_ApplyLoadout
    / HCE_LoadoutVisual / HCE_LoadoutAnim / HCE_LoadoutAnimTics, one function per loadout (one big switch runs out of
    VM registers). Which guns a body can pick up is decided in build(), not here"""
    los = sorted(prof)
    out = [f'\t// guns it can pick up off the ground (HaloDoom_EnemyBase.HCE_ScavengeScan): {", ".join(los)}',
           '\toverride bool HCE_HasLoadouts() { return true; }',
           '\toverride int HCE_LoadoutIndex(Name w)', '\t{', '\t\tswitch(w)', '\t\t{']
    out += [f"\t\tcase '{w}': return {i};" for i, w in enumerate(los)]
    out += ['\t\t}', '\t\treturn -1;', '\t}', '\toverride void HCE_ApplyLoadout(int lo)', '\t{', '\t\tswitch(lo)', '\t\t{']
    out += [f'\t\tcase {i}: HCE_ApplyLoadout{i}(); return;' for i in range(len(los))]     # one function each (VM registers)
    out += ['\t\t}', '\t}']
    for i, w in enumerate(los):
        p = prof[w]
        out += [f'\tvoid HCE_ApplyLoadout{i}()', '\t{', '\t\t{']
        out.append(f"\t\t\thce_projectile = '{p['proj']}'; hce_projectilesPerShot = {p['pps']}; hce_rateOfFire = {p['rof']:.2f}; "
                   f"hce_errorAngle = {p['err']:.2f}; hce_maxRange = {p['maxrange']:.0f}; hce_projSpeed = {p['projspeed']:.1f};")
        out.append(f"\t\t\thce_rangeMin = {p['rlo']:.0f}; hce_rangeMax = {p['rhi']:.0f}; hce_damageMod = {p['dmgmod']:.2f}; "
                   f"hce_specialFire = {p['sf']}; hce_specialChance = {p['sc']}; bHCE_Lobbed = {'true' if p['lobbed'] else 'false'};")
        if p['pattern']:
            v = [x.strip() for x in p['pattern'].split(',')]
            out.append(f"\t\t\thce_patShotsMin = {v[0]}; hce_patShotsMax = {v[1]}; hce_patInterval = {v[2]}; "
                       f"hce_patPauseMin = {v[3]}; hce_patPauseMax = {v[4]}; hce_patChargeTics = {v[5]};")
        else:
            out.append('\t\t\thce_patShotsMax = 0;')
        snd = p['sounds'] or ('', '', '', '')
        out.append(f'\t\t\thce_fireSound = "{snd[0]}"; hce_fireSoundBass = "{snd[1]}"; hce_specialSound = "{snd[2]}"; '
                   f'hce_chargeSound = "{snd[3]}"; hce_fireLoop = {"true" if p["loop"] else "false"};')
        out.append(f"\t\t\thce_specialProj = '{p['special'][0]}'; hce_specialCount = {p['special'][1]};")
        out += ['\t\t}', '\t}']
    out += ['\toverride void HCE_LoadoutVisual(int lo)', '\t{', '\t\tswitch(lo)', '\t\t{']
    out += [f'\t\tcase {i}: HCE_LoadoutVisual{i}(); return;' for i in range(len(los))]
    out += ['\t\t}', '\t}']
    for i, w in enumerate(los):
        out += [f'\tvoid HCE_LoadoutVisual{i}()', '\t{', '\t\t{', prof[w]['visual'].rstrip('\n'), '\t\t}', '\t}']
    out += ['\toverride Name HCE_LoadoutAnim(int lo, int kind)', '\t{', '\t\tswitch(lo)', '\t\t{']
    out += [f'\t\tcase {i}: return HCE_LoadoutAnim{i}(kind);' for i in range(len(los))]
    out += ['\t\t}', "\t\treturn 'None';", '\t}']
    names = set()
    for i, w in enumerate(los):                 # one function per loadout (one big one runs out of VM registers)
        t = prof[w]['table']
        out += [f'\tName HCE_LoadoutAnim{i}(int kind)', '\t{', '\t\tswitch(kind)', '\t\t{']
        for k in KINDS:
            opts = [o for o in (t.get(k) or []) if o in A.names]
            if not opts: continue
            names |= set(opts)
            if len(opts) == 1: out.append(f"\t\tcase HCE_A_{k}: return '{opts[0]}';")
            else: out.append(f"\t\tcase HCE_A_{k}: {{ static const Name o[] = {{ {', '.join(repr(x).replace(chr(34), '') for x in opts)} }}; return o[random(0, {len(opts) - 1})]; }}")
        out += ['\t\t}', "\t\treturn 'None';", '\t}']
    out += ['\toverride int HCE_LoadoutAnimTics(Name anim)', '\t{', '\t\tswitch(anim)', '\t\t{']
    out += [f"\t\tcase '{n}': return {A.tics(n)};" for n in sorted(names)]
    out += ['\t\t}', '\t\treturn 0;', '\t}', '']
    return '\n'.join(out)



# ---------------- Ultimate Doom Builder: editor keys and thing icons
# Every placeable class carries UDB's editor keys (//$Category, //$Title, //$Sprite), so mappers find the enemies in the
# thing browser by faction and kind, named and pictured. The pictures are udb_icons.py's photos of each enemy
# ($HCE_OUT/udb_icons), shipped as sprites HUxxA0 (xx: the class's place in icons.json, base 36) in its faction's pack.
UDB_ICONS = f'{OUT}/udb_icons'
# TEAM -> the thing browser's category under 'Halo CE' (and the bestiary's faction, in this order)
UDB_CATEGORY = {'COVENANT': 'Covenant', 'FLOOD': 'Flood', 'SENTINEL': 'Sentinels', 'HUMAN': 'Marines (allies)'}
_udb = None

def udb_sprites():
    """class -> its icon's sprite name (HUxx), from udb_icons.py's index (empty before it has run)"""
    global _udb
    if _udb is None:
        ij = f'{UDB_ICONS}/icons.json'
        names = sorted(json.load(open(ij))) if os.path.exists(ij) else []
        digits = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        _udb = {c: 'HU' + digits[i // 36] + digits[i % 36] for i, c in enumerate(names)}
    return _udb

def words(name):
    """'EliteMinorPlasmaRifle' -> 'Elite Minor Plasma Rifle'"""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', name)

def thing_title(cls, weapon=None):
    """'HCE_EliteMinorPlasmaRifle' -> 'Elite Minor (Plasma Rifle)'"""
    title = words(cls[4:] if cls.startswith('HCE_') else cls)
    if weapon:
        w = ' '.join(x.capitalize() for x in weapon.split())
        if title.endswith(w) and title != w: title = f'{title[:-len(w)].strip()} ({w})'
    return title.replace('Specops', 'Spec Ops')

BESTIARY = []          # (class, team, character, title, sprite): every class editor_keys was written for (bestiary_lump)

def editor_keys(cls, char, team, title=None, sprite_of=None, weapon=None):
    """UDB editor keys for a placeable class (inside its class body, before Default)"""
    title = title or thing_title(cls, weapon)
    BESTIARY.append((cls, team, char, title, udb_sprites().get(sprite_of or cls, '')))
    keys = [f'\t//$Category "Halo CE/{UDB_CATEGORY.get(team, "Other")}/{words(char)}"',
            f'\t//$Title "{title or words(cls[4:] if cls.startswith("HCE_") else cls)}"']
    spr = udb_sprites().get(sprite_of or cls)
    if spr: keys.append(f'\t//$Sprite "{spr}A0"')
    return '\n'.join(keys) + '\n'

# ---------------- the bestiary (Options > Halo CE Bestiary: hce_bestiary.zsc)
# Each pack carries an HCEBEST lump (hcebest.<pack>) of its own placeable enemies, tab-separated:
#   E <class> <faction> <group> <title> <icon sprite or -> <lore keys, rank's first> <DoomEdNum> <guns it carries, or ->
#     (one entry per kind and rank: its weapon variants are listed, not given entries of their own)
#   L <key> <lore text, paragraphs split by |>
# The lore is pack/bestiary_lore.txt; a class gets the entry whose key is the longest found in its class name, else its
# character's. Random spawners and the variant things are left out (the variants from HCEVARS are listed at run time).
# character -> its group heading in the bestiary where the character name split into words won't do (words(char))
BESTIARY_GROUP = {'EliteSpecial': 'Spec Ops Elite', 'GruntSpecOps': 'Spec Ops Grunt', 'JackalMajor': 'Jackal Major',
                  'H2Jackal': 'Jackal (Halo 2)', 'FloodHuman': 'Flood (human host)', 'FloodElite': 'Flood (Elite host)',
                  'FloodInfection': 'Flood infection form', 'FloodCarrier': 'Flood carrier form', 'FloodGrunt': 'Flood (Grunt host)',
                  'FloodODST': 'Flood (ODST host)', 'FloodMarine': 'Flood (Marine host)', 'FloodArmored': 'Flood (Armored Marine host)',
                  'FloodEliteArmored': 'Flood (shielded Elite host)', 'FloodEliteCommander': 'Flood (Elite Commander host)',
                  'FloodEliteUltra': 'Flood (Elite Ultra host)', 'FloodJuggernaut': 'Flood Juggernaut', 'FloodBrute': 'Flood (Brute host)', 'MarineArmored': 'Armored Marine',
                  'MarineODST': 'ODST', 'EliteRifle': 'Elite (carbines)', 'EliteZealot': 'Elite Zealot'}

def read_lore():
    """pack/bestiary_lore.txt -> {key: text (paragraphs joined by |)}"""
    lore, key, buf = {}, None, []
    def flush():
        """store the entry read so far (buf) under key, its paragraphs joined by |"""
        if key: lore[key] = '|'.join(p.strip().replace('\n', ' ') for p in '\n'.join(buf).strip().split('\n\n') if p.strip())
    for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pack', 'bestiary_lore.txt')):
        if line.startswith('#'): continue
        m = re.match(r'\[(\w+)\]\s*$', line)
        if m: flush(); key, buf = m.group(1), []
        else: buf.append(line.rstrip('\n'))
    flush()
    return lore

# kinds named by the class rather than the body it's built on (the Honor Guard and Rangers wear Spec Ops / Elite bodies)
BESTIARY_RANK_GROUP = (('HonorGuard', 'Honor Guard'), ('Ranger', 'Elite Ranger'), ('StealthElite', 'Stealth Elite'),
                       ('BruteStalker', 'Brute Stalker'), ('Hellbringer', 'ODST Hellbringer'), ('MarinePilot', 'Pilot'))

# the guns as the bestiary names them (from the class names)
BESTIARY_GUN_NAME = {'Flame Thrower': 'Flamethrower', 'Dmr': 'DMR', 'Gpmg': 'GPMG', 'Smg': 'SMG', 'Ma37': 'MA37', 'Rocketeer': 'Rocket Launcher', 'Sniper': 'Sniper Rifle'}

def bestiary_title(t):
    """the bestiary's name for a kind, in universe ('Floodcombat Odst' -> 'Combat Form: ODST', 'Sgt Johnson' -> 'Sergeant Johnson')"""
    t = re.sub(r'\bOdst\b', 'ODST', t)
    if t == 'Marine ODST Halo2': return 'ODST Shock Trooper'
    t = re.sub(r'^Marine ODST\b', 'ODST', t)
    t = re.sub(r'^Floodcombat (.*)$', r'Combat Form: \1', t)
    t = t.replace('Combat Form: Elite Stealth Unarmed', 'Combat Form: Stealth Elite')
    t = {'Floodcarrier': 'Carrier Form', 'Flood Infection': 'Infection Form', 'Flood Grunt': 'Combat Form: Grunt'}.get(t, t)
    t = re.sub(r'^Grunt Flee (\w+)$', r'Grunt \1 (Skittish)', t)
    t = re.sub(r'^Marine Field Medic\b', 'Field Medic', t)
    t = re.sub(r'^Marine Medic\b', 'Corpsman', t)
    t = re.sub(r'^Marine Pilot\b', 'Pilot', t)
    if t == 'Artybug': return 'Beetle'                    # the UNSC designation (the lore gives the Covenant one)
    return t.replace('Sgt ', 'Sergeant ')

def bestiary_lump(classes, path):
    """write the HCEBEST lump for these placeable classes ({class: DoomEdNum}, from BESTIARY) to path; returns how many.
    An entry's lore is its rank's, then its character's (keys joined by commas)"""
    lore = read_lore()
    ents, keys = [], set()
    for cls, team, char, title, spr in BESTIARY:
        if cls not in classes or cls.startswith('HCE_Random'): continue
        name = cls[4:]
        key = max([k for k in lore if k in name], key=len, default='')
        ks = [k for k in (key, char) if k in lore]
        ks = list(dict.fromkeys(ks))
        group = next((g for sub, g in BESTIARY_RANK_GROUP if sub in name), BESTIARY_GROUP.get(char, words(char)))
        ents.append([UDB_CATEGORY.get(team, 'Other'), group, title, cls, spr or '-', ','.join(ks) or '-', str(classes[cls])])
        keys.update(ks)
    order = list(UDB_CATEGORY.values())
    ents.sort(key=lambda e: (order.index(e[0]) if e[0] in order else 9, e[1], e[2]))
    # one entry per kind and rank: the same enemy with another gun ('Elite Minor (Needler)', 'Elite Minor (Plasma
    # Rifle)') is one entry listing the guns it carries; the first class stands for its numbers
    merged, keyorder = {}, []
    guns = {m.group(1) for e in ents for m in [re.search(r'\(([^)]*)\)$', e[2])] if m} | {'Magnum', 'Sniper', 'Rocketeer', 'Unarmed', 'Flame Thrower'}
    for e in ents:
        m = re.match(r'(.*) \(([^)]*)\)$', e[2])
        base, wpn = (m.group(1), m.group(2)) if m else (e[2], '')
        if not m:                                   # 'Elite Minor Plasma Rifle Ranged': a rank already listed, its gun unbracketed
            pre = next((kk for kk in keyorder if kk[:2] == (e[0], e[1]) and base.startswith(kk[2] + ' ')
                        and any(base[len(kk[2]) + 1:].startswith(gn) for gn in guns)), None)   # (a gun, not another rank: Hunter Major stays)
            if pre:
                rest = base[len(pre[2]) + 1:]
                base, wpn = pre[2], max((gn for gn in guns if rest.startswith(gn)), key=len)    # 'Plasma Rifle Ranged': the gun
        k = (e[0], e[1], base)
        if k not in merged: merged[k] = dict(e=list(e), weps=[]); merged[k]['e'][2] = base; keyorder.append(k)
        g = merged[k]
        wpn = BESTIARY_GUN_NAME.get(wpn, wpn)
        if wpn and wpn != 'Unarmed' and wpn not in g['weps']: g['weps'].append(wpn)
        if g['e'][4] == '-' and e[4] != '-': g['e'][4] = e[4]
    rows = ['\t'.join(['E', g['e'][3], g['e'][0], g['e'][1], bestiary_title(g['e'][2]), g['e'][4], g['e'][5], g['e'][6], ', '.join(g['weps']) or '-'])
            for g in (merged[k] for k in keyorder)]
    rows += ['\t'.join(['L', k, lore[k]]) for k in sorted(keys)]
    if rows: open(path, 'w').write('// the Halo CE enemies bestiary (hce_bestiary.zsc), generated by build_pack.py\n' + '\n'.join(rows) + '\n')
    return len(keyorder)

def ship_udb_icons(classes, sprites_dir):
    """copy the icons of these classes into a pack's sprites folder as their HUxxA0 sprites"""
    sp = udb_sprites()
    have = [c for c in classes if c in sp]
    if not have: return 0
    os.makedirs(sprites_dir, exist_ok=True)
    for c in have: shutil.copy(f'{UDB_ICONS}/{c}.png', f'{sprites_dir}/{sp[c]}A0.png')
    return len(have)

def check_steps(metas):
    """stops the build when a body was re-extracted and a post-extraction step not re-run after it (lib/steps.py: each
    step stamps the animations it added; a fresh extraction drops the stamp or the animations). Which bodies each step
    covers comes from the step's own CHARS table, so a body added there is checked from then on"""
    import steps, low_ready_anims, reload_anims, cover_anims, marine_h2_grips
    required = {}
    import draeth_stances, flood_leap_anims, be_anims, cursed_anims
    for step, chars in [('draeth_stances', draeth_stances.CHARS), ('flood_leap_anims', flood_leap_anims.CHARS), ('be_anims', be_anims.CHARS), ('cursed_anims', cursed_anims.CHARS), ('low_ready_anims', low_ready_anims.CHARS), ('reload_anims', reload_anims.CHARS),
                        ('cover_anims', cover_anims.CHARS), ('marine_h2_grips', marine_h2_grips.CHARS)]:
        for c in chars: required.setdefault(c, {})[step] = f'python3 {step}.py' + ('' if step == 'marine_h2_grips' else f' {c}') + (' (then low_ready_anims.py Draeth)' if step == 'draeth_stances' else '')
    problems = [x for c, meta in sorted(metas.items()) for x in steps.check(meta, c, required.get(c, {}))]
    if problems:
        raise SystemExit('models out of date (a body re-extracted without its steps re-run):\n  ' + '\n  '.join(problems))


def build(cfg=None):
    """Write the pack. cfg (MAIN, or an add-on's: build_digsite.py): char_of_unit and team (the characters to build),
    ai (the patched AI data), pack (the pk3 source tree), mdir (the models/ subfolder), tag (the lump suffix:
    hce_enemies.zsc, modeldef.hce ...), ed0 (the first DoomEdNum), main (the core pack: the hard-light bases, the boss
    stand-ins, the placeholder sprite), handler, index, late_chars / late_order (the numbering of what came after the
    first release), and the optional nerf_mixin, lite_mixin, glow, gl_title.

    Per character (sorted by name): copies the model, kit and gore files into the pack and writes the abstract
    HCE_<Char>Base class (collision box, blood, the gore / blood / gun / permutation / Marine code; a bubble flare for
    the shielded Sentinels), then every variant drawn on that body (the per-variant loop: stance and animations,
    speed, vitality, the weapon's numbers and pattern, melee, leaps, grenades, perception, the behaviour flags, the
    skins, the Default block, the extra ZScript, the MODELDEF block, a loadout other bodies of its kind can pick up),
    then the base class gets its loadouts. After all characters: the projectile classes, the random spawners, the
    Doom boss stand-ins, the late classes' numbers, GLDEFS (brightmaps, shaders, visors), the lumps, mapinfo.txt,
    the UDB icons, the bestiary and the skin check"""
    cfg = cfg or MAIN
    char_of_unit, team, ai, pack, mdir = cfg['char_of_unit'], cfg['team'], cfg['ai'], cfg['pack'], cfg['mdir']
    main = cfg.get('main', False)
    if os.path.exists(f'{pack}/models'): shutil.rmtree(f'{pack}/models')
    os.makedirs(f'{pack}/ZScript/HaloCE', exist_ok=True)
    metas = {c: json.load(open(f'{OUT}/models/{c}/{c}.json')) for c in set(char_of_unit.values())}
    check_steps(metas)
    zs = []; md = []; ednums = []; spawners = {}; late = []; brightmaps = []; shells = set(); camo = []; shield_tex = []; bubbles = []
    projectiles_used = set()
    ed = cfg['ed0']
    # ---------------- per character base classes
    based = set()
    for unit, char in sorted(char_of_unit.items(), key=lambda x: x[1]):
        if char in based: continue                 # several units on one body (Galap's allies): one base class
        based.add(char)
        meta = metas[char]
        b = ai['bipeds'][unit]
        ov = CHAR_OVERRIDES.get(char, {})
        os.makedirs(f'{pack}/models/{mdir}/{char}/skins', exist_ok=True)
        shutil.copy(f'{OUT}/models/{char}/{char}.iqm', f'{pack}/models/{mdir}/{char}/{char}.iqm')
        if meta.get('gore'):                       # the stumps are skinned by name when shown: undrawn until then
            modeldef_prune.unresolve_material(f'{pack}/models/{mdir}/{char}/{char}.iqm', meta['gore']['tex'])
        if char.startswith('Elite') and mdir == 'hce' and os.path.exists(f'{ELITE_KIT}/EliteKit.json'):   # Halo 2's Elite armour (the main pack's; the add-on's carbine Elites use it from there)
            os.makedirs(f'{pack}/models/{mdir}/EliteKit', exist_ok=True)
            for f in os.listdir(ELITE_KIT):
                if f.endswith(('.iqm', '.png')) and not f.endswith('_spec.png'): shutil.copy(f'{ELITE_KIT}/{f}', f'{pack}/models/{mdir}/EliteKit/{f}')
            kit_shine(f'{pack}/models/{mdir}/EliteKit')
        if char.startswith('Marine') and os.path.exists(f'{MARINE_KIT}/MarineKit.json'):    # Elefant's Marine kit
            os.makedirs(f'{pack}/models/{mdir}/MarineKit', exist_ok=True)
            for f in os.listdir(MARINE_KIT):
                if f.endswith(('.iqm', '.png')): shutil.copy(f'{MARINE_KIT}/{f}', f'{pack}/models/{mdir}/MarineKit/{f}')
        if meta.get('gore') or meta.get('blood'):
            os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
            if not os.path.exists(f'{pack}/models/{mdir}/weapons/hce_hidden.png'): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(f'{pack}/models/{mdir}/weapons/hce_hidden.png')
        if meta.get('gore'):                       # dismemberment (gore_kit.py): the gibs and the stump texture
            for d in meta['gore']['limbs'].values():       # the limb's gib, and one per back permutation (the Grunts' shellback)
                for gib in {d['gib']} | {v['gib'] for v in (d.get('variants') or {}).values()}:
                    shutil.copy(f'{OUT}/models/{char}/{gib}', f'{pack}/models/{mdir}/{char}/{gib}')
            shutil.copy(f'{OUT}/models/{char}/{meta["gore"]["tex"]}', f'{pack}/models/{mdir}/{char}/{meta["gore"]["tex"]}')
            if meta['gore'].get('cap_model'):     # the stumps' own model (the Brute's: attached when a limb comes off)
                shutil.copy(f'{OUT}/models/{char}/{meta["gore"]["cap_model"]}', f'{pack}/models/{mdir}/{char}/{meta["gore"]["cap_model"]}')
        if meta.get('blood'):                      # blood on the body (blood_kit.py): overlay models and textures
            for f in meta['blood']['models'] + meta['blood']['textures']: shutil.copy(f'{OUT}/models/{char}/{f}', f'{pack}/models/{mdir}/{char}/{f}')
            # (the overlay's empty surfaces keep their material 'hce_noblood.png', no file: the engine skips them)
            os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
            hid = f'{pack}/models/{mdir}/weapons/hce_hidden.png'
            if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        h = max(meta['bounds'][1][2] - max(0, meta['bounds'][0][2]), b.get('collision_height_standing') or 0.3)
        r = b.get('collision_radius') or 0.2
        flying = char in SENTINEL_LIKE or ov.get('flying', False)
        height = int(round((b.get('collision_height_standing') or h) * S)) if not flying else int(h * S * 0.8)
        if char == 'FloodInfection': height = int(h * S)
        radius = int(round(max(r, 0.12) * S))
        msc = ov.get('scale', 1.0)          # oversized creatures are shrunk to fit Doom's corridors
        if msc != 1.0: height = int(round(height * msc)); radius = int(round(radius * msc))
        if ov.get('radius'): radius = min(radius, ov['radius'])
        if ov.get('radius_fixed'): radius = ov['radius_fixed']
        if ov.get('height_fixed'): height = ov['height_fixed']
        height = max(height, HEAD_CLEAR.get(char, 0))
        base_idx = len(zs); prof = {}
        zs.append(f'// ---- {char}: the body every {char} variant below is drawn with ({unit}): its size, blood and gore, the skins it\n'
                  f'// rolls and its cosmetics. Changing a number here changes every {char}; one variant\'s numbers are in its own class\n'
                  f'class HCE_{char}Base : HaloDoom_EnemyBase abstract\n{{\n\tDefault\n\t{{\n'
                  f'\t\tMonster;\n\t\t+DECOUPLEDANIMATIONS\n\t\t+FLOORCLIP\n\t\t+DONTHARMSPECIES\n\t\t+NOINFIGHTSPECIES\n'
                  f'\t\tSpecies "HCE_{team[char]}";\n\t\tHaloDoom_EnemyBase.HCE_Enabled true;\n'
                  f'\t\tHaloDoom_EnemyBase.HCE_Team HCE_TEAM_{team[char]};\n'
                  f'\t\tHeight {height};\n\t\tRadius {radius};\n\t\tMass {int(100 * (h / 0.6) ** 2)};\n'
                  f'\t\tPainChance 0;\n\t\tTag "{char}";\n{blood_props(char)}\t}}\n'
                  f'\tStates\n\t{{\n\tSpawn:\n\t\tHCEM A 1 HCE_Look();\n\t\tLoop;\n\tSee:\n\t\tHCEM A 1 HCE_Think();\n\t\tLoop;\n'
                  f'\tDeath:\n\t\tHCEM A 1 HCE_Die();\n\t\tHCEM A 2 A_NoBlocking;\n'            # no XDeath: gore stays blood-only (see HCE_Gore)
                  f'\tDead:\n\t\tHCEM A 1 HCE_CorpseTick();\n\t\tLoop;\n'
                  f'\tRaise:\n\t\tHCEM A 1;\n\t\tGoto See;\n'
                  # HDE's grenades push what they hit into Pain (frag) / Pain.PlasmaStuck (plasma): a corpse stays dead
                  f'\tPain:\n\t\tHCEM A 0 A_JumpIf(health <= 0, "Dead");\n\t\tGoto See;\n'
                  f'\tPain.PlasmaStuck:\n\t\tHCEM A 0 A_JumpIf(health <= 0, "Dead");\n\t\tHCEM A 1 HCE_OnStuck();\n\t\tGoto See;\n\t}}\n'
                  f'\toverride void HCE_ApplyAnim(Name n, int blend, bool loop)\n\t{{\n\t\tSetAnimation(n, -1, hce_applyFrame, -1, -1, blend, loop ? SAF_LOOP : 0);\n'
                  f'\t\tif(hce_shellActor) hce_shellActor.SetAnimation(n, -1, hce_applyFrame, -1, -1, blend, loop ? SAF_LOOP : 0);   // the shield flare moves with it\n'
                  f'\t\tif(hce_holoActor) hce_holoActor.SetAnimation(n, -1, hce_applyFrame, -1, -1, blend, loop ? SAF_LOOP : 0);   // and a hologram companion\n\t}}\n'
                  + (f"\toverride Name HCE_ShellClass() {{ return 'HCE_{char}ShieldShell'; }}\n" if char in SHELL_TINT else '')
                  + ("\t// its arm shield is drawn by its own shield field (HCE_ShieldField), one class per variant (its rank's colour)\n"
                     "\toverride Name HCE_ShellClass() { return String.Format(\"%sShieldField\", GetClassName()); }\n" if char in FIELD_CHARS and char not in SHELL_TINT else '')
                  + (FIELD_HOLO_CODE if char in FIELD_CHARS and char in SHELL_TINT else '')
                  + (f'\toverride Sound HCE_MeleeSound() {{ return "{SENTINEL_MELEE}"; }}     // Halo 2\'s Sentinel melee\n' if char in SENTINEL_UNIT_SOUNDS else '')
                  + (machine_code(char, mdir, ov) if char in SENTINEL_UNIT_SOUNDS else '')
                  + BASE_CODE.get(char, '') + gore_code(char, meta, mdir, S * msc) + blood_code(char, meta, mdir) + gun_code(meta, mdir, OVERLAY_SLOT.get(char)) + perm_code(meta, mdir)
                  + (marine_code(meta, mdir, char) if char.startswith('Marine') else '') + '}\n')
        if char in BUBBLE_CHARS and meta.get('shield_surface') is not None:
            # the Sentinels' shield bubble as a flare (HCE_ShieldShell: unseen until a hit lights it, then fading, like
            # the Covenant's): the body's model with only its shield surface drawn, in Halo 2's plasma_shield
            fn = 'bubble_shell.png'
            bubble = f'{pack}/models/{mdir}/{char}/skins/{fn}'
            # the shield's colour, flat: PLASMA_H2_SHADER draws the plasma in it (shader_gl)
            Image.new('RGB', (4, 4), tuple(int(c * 255) for c in SHIELD_TINT['sentinel_minor'])).save(bubble)
            bubbles.append(f'models/{mdir}/{char}/skins/{fn}')
            sl = [f'\tSurfaceSkin 0 {i} "skins/{fn if i == meta["shield_surface"] else "hce_hidden.png"}"' for i in range(len(meta['meshes']))]
            hid = f'{pack}/models/{mdir}/{char}/skins/hce_hidden.png'
            if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
            zs.append(f'// the {char}s\' shield bubble flare\nclass HCE_{char}BubbleShell : HCE_ShieldShell {{}}\n')
            md.append(f'Model HCE_{char}BubbleShell\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(sl) +
                      f'\n\tScale {S * msc:.1f} {S * msc:.1f} {S * msc * 1.2:.1f}'
                      + (f'\n\tZOffset {-meta["bounds"][0][2] * S * msc * 1.2:.0f}' if ov.get('lift') else '')     # as the body's (lift)
                      + '\n\tUseActorPitch\n\tBaseFrame\n\tFrameIndex HCEM A 0 0\n}\n')
        if char == 'SentinelEnforcer' and meta.get('shield_surfaces'):
            # its two shields drawn by a shield field (HCE_ShieldField, spawned by its own code): Halo 2's energy_shield
            # (the Jackal shield's combiner over the Enforcer's maps), in its colour (the shader's constant colour 2)
            fn = 'enforcer_field.png'
            os.makedirs(f'{pack}/models/{mdir}/{char}/skins', exist_ok=True)
            Image.new('RGB', (4, 4), ENFORCER_FIELD_TINT).save(f'{pack}/models/{mdir}/{char}/skins/{fn}')
            FIELD_TEX[f'models/{mdir}/{char}/skins/{fn}'] = ('enf', max(mesh_layers(f'{OUT}/models/{char}/{char}.iqm', i) for i in meta['shield_surfaces'].values()), None)
            hid = f'{pack}/models/{mdir}/{char}/skins/hce_hidden.png'
            if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
            shs = set(meta['shield_surfaces'].values())
            sl = [f'\tSurfaceSkin 0 {i} "skins/{fn if i in shs else "hce_hidden.png"}"' for i in range(len(meta['meshes']))]
            zs.append(f'// the {char}\'s two shields\nclass HCE_{char}ShieldField : HCE_ShieldField {{}}\n')
            md.append(f'Model HCE_{char}ShieldField\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(sl) +
                      f'\n\tScale {S * msc:.0f} {S * msc:.0f} {S * msc * 1.2:.0f}'
                      + (f'\n\tZOffset {-meta["bounds"][0][2] * S * msc * 1.2:.0f}' if ov.get('lift') else '')
                      + '\n\tUseActorPitch\n\tUseActorRoll\n\tDontCullBackfaces\n\tBaseFrame\n\tFrameIndex HCEM A 0 0\n}\n')   # (seen from behind too)
        # ---------------- variants
        for vname, v in sorted(ai['variants'].items()):
            if char_of_unit.get(v['unit_reference']) != char: continue      # every unit drawn as this body
            ov = dict(CHAR_OVERRIDES.get(char, {}), **v.get('_ov', {}))     # per-variant overrides (add-ons)
            a = ai['actors'][v['actor_reference']]
            rc = v['ranged_combat']; gc = v['grenade_combat']; un = v['unit']
            weapon = wname(rc['reference'])
            wd = ai['weapons'].get(rc['reference']) if rc['reference'] else None
            coll = ai['collisions'].get(b.get('collision_model'), {}).get('resistance', {})
            atype = a['type']
            cls = cname(vname)
            # stance used for animations
            if ov.get('stance'): w = ov['stance'].get(weapon, ov['stance'].get(None)) if isinstance(ov['stance'], dict) else ov['stance']
            elif char in ('Hunter', 'FloodInfection', 'FloodCarrier'): w = 'unarmed'
            elif char in SENTINEL_LIKE: w = 'fixed'
            elif (char.startswith('Grunt') or char.startswith('Elite')) and weapon and 'fuel rod' in weapon: w = 'missle'
            elif char.startswith('Elite') and weapon == 'energy sword': w = 'sword'
            elif char.startswith('Elite') and weapon == 'beam rifle': w = 'rifle'
            # the Draeth: Halo 2's Elite fuel-rod and rifle stances (draeth_stances.py) for its two-handed guns, else its own pistol stance
            elif char == 'Draeth' and weapon and 'fuel rod' in weapon: w = 'missle'
            elif char == 'Draeth' and weapon in ('beam rifle', 'plasma caster', 'plasma carbine', 'carbine'): w = 'rifle'
            elif char.startswith('Flood'): w = 'pistol' if weapon else 'unarmed'
            elif char.startswith('Marine') and weapon == 'plasma rifle': w = 'h2plasma'      # Halo 2's rifle stance, the left hand under the gun (marine_plasma_grip.py)
            elif char.startswith('Marine'): w = 'pistol' if weapon in ('pistol', 'needler', 'plasma pistol') else 'rifle'
            else: w = 'pistol'
            A = AnimSet(meta); A.jackal = char.startswith('Jackal')
            table = anim_table(A, w, weapon)
            # a stance the body has no animations for would fall through to the pistol set (a Marine holding a
            # shotgun one-handed): the Halo 2 ODSTs' stances are made by marine_h2_grips.py after extract_odst.py
            if w.startswith('h2') and not A.find(f'stand {w} idle'):
                raise SystemExit(f"{cls}: {char} has no '{w}' animations (stance of {vname!r}); run marine_h2_grips.py after re-extracting the body")
            for k, names in list(ov.get('anims', {}).items()) + list(ov.get('anims_by_weapon', {}).get(weapon, {}).items()):
                table[k] = [n for n in names if n in A.names]
            # Cursed Halo's leaping spin (cursed_anims.py): the Hunter springs and spins through the air into its target;
            # the spin is the strike (no swing after it)
            hunter_spin = char == 'Hunter' and HUNTER_SPIN in A.names
            if hunter_spin and 'LEAP_AIR' not in ov.get('anims', {}): table['LEAP_AIR'] = [HUNTER_SPIN]; table['LEAP_MELEE'] = []
            # speed: the run animation's own pace (map units a tic), the walk and low-ready walk from it; ov 'speed' overrides
            mv = (table.get('MOVE_F') or [None])[0]
            run = A.speed(mv) if mv else 0
            if run < 1.5: run = 6.0 if char in SENTINEL_LIKE else {'FloodInfection': 7.0}.get(char, 5.0)
            run = min(run, 14)
            run *= msc                     # scaled-down model: scaled-down stride
            if 'speed' in ov: run = ov['speed']
            if char in SENTINEL_LIKE and 'speed' not in ov:
                run = max(4.0, (b.get('flying_velocity') or 2.25) / 30 * S / TICK)
            walk = run * 0.65
            lmv = (table.get('LOW_MOVE') or [None])[0]
            low = min(walk, A.speed(lmv) * msc) if lmv else 0      # the low-ready walk's own pace
            # vitality: Halo's body and shield (the unit's, else its collision model's); ov 'health' / 'shield' override
            body = un['maximum_body_vitality'] or coll.get('maximum_body_vitality') or 0
            shield = un['maximum_shield_vitality'] or coll.get('maximum_shield_vitality') or 0
            if 'shield' in ov: shield = ov['shield']
            # Stealth Elites: the camo is their protection -- no energy shield and a fragile body
            if 'stealth elite' in vname and char.startswith('Elite'): shield = 0; body = body * 0.45
            if char == 'FloodInfection': body = max(body, 3)
            body = max(1, int(round(ov.get('health', body))))
            # weapon: the projectile and its speed from WEAPONS, shots per pull, rate and spread from Halo's trigger data
            # (ov 'pellets' / 'spread' override), then the Doom-paced fire pattern (PATTERNS), sounds (FIRE_SOUNDS) and
            # the other extra Default lines gathered in pat
            proj = 'None'; pps = 1; rof = rc['rate_of_fire']; err = rc['projectile_error_angle'] * DEG
            projspeed = 0; dmgmod = rc.get('weapon_damage_modifier') or 1.0
            trig = (wd or {}).get('triggers_list') or []
            if weapon in WEAPONS:
                pc, base_cls, dmg, sp = WEAPONS[weapon]
                proj = pc; projectiles_used.add(weapon); projspeed = sp * S / TICK
                if trig:
                    pps = max(1, trig[0].get('projectiles_per_shot') or 1)
                    if not rof: rof = trig[0].get('initial_rate_of_fire') or 0
                    err = max(err, (trig[0].get('projectile_error_angle_lower_bound') or 0) * DEG)
                    if pps > 1: err = max(err, (trig[0].get('projectile_distribution_angle') or 0) * DEG * 0.5, 4)
            if ov.get('pellets'): pps = ov['pellets']                 # Marine arsenal shotguns (no Halo CE trigger data)
            if ov.get('spread') is not None: err = ov['spread']
            if not rof: rof = {'fuel rod': 0.6, 'hunter fuel rod': 0.7, 'rocket launcher': 0.4, 'needler': 6, 'plasma pistol': 4, 'sniper rifle': 0.6}.get(weapon, 3)
            if weapon in ('fuel rod', 'hunter fuel rod', 'rocket launcher', 'sniper rifle'): rof = min(rof, 0.8)
            beam = char in SENTINEL_LIKE and weapon == 'sentinel'
            if beam: rof = 30; err = 0.6
            bg = rc['burst_geometry']
            bmin, bmax = bg['burst_duration_lower_bound'] or 0.6, bg['burst_duration_upper_bound'] or 1.2
            smin, smax = bg['burst_separation_lower_bound'] or 0.8, bg['burst_separation_upper_bound'] or 1.8
            if weapon in ('fuel rod', 'hunter fuel rod', 'rocket launcher', 'sniper rifle', 'shotgun'):
                bmin, bmax = 0.05, 0.1
            pkey = 'sentinel beam' if beam else weapon
            pat = ''
            if pkey in PATTERNS:
                p_smin, p_smax, p_int, p_pmin, p_pmax, p_charge, p_scale, base_sep, base_burst = PATTERNS[pkey]
                rp = min(1.3, max(0.75, ((smin + smax) / 2) / base_sep))
                if pkey == 'needler': rp = max(rp, 1.0)   # needles home and supercombine: never faster than baseline
                rb = min(1.6, max(0.75, ((bmin + bmax) / 2) / base_burst)) if p_scale else 1.0
                p_smin = max(1, round(p_smin * rb)); p_smax = max(p_smin, round(p_smax * rb))
                pat = (f'\t\tHaloDoom_EnemyBase.HCE_FirePattern {p_smin}, {p_smax}, {p_int}, {p_pmin * rp:.2f}, {p_pmax * rp:.2f}, {p_charge};\n')
            if pkey in FIRE_SOUNDS:
                f1, f2, f3, f4, loop = FIRE_SOUNDS[pkey]
                pat += f'\t\tHaloDoom_EnemyBase.HCE_FireSounds "{f1}", "{f2}", "{f3}", "{f4}";\n'
                if loop: pat += '\t\tHaloDoom_EnemyBase.HCE_FireLoop true;\n'
            us = SENTINEL_UNIT_SOUNDS.get(char)
            if us: pat += f'\t\tHaloDoom_EnemyBase.HCE_UnitSounds "{us[0]}", "{us[1]}", "{us[2]}";\n'
            # Halo 3 kamikaze run: Grunts carrying plasma grenades, rarer for Minors (rolled once a second)
            if char.startswith('Grunt') and gtype == 2:
                kc = 0.012 if char == 'GruntSpecOps' else 0.008 if ' major' in vname else 0.004
                pat += f'\t\tHaloDoom_EnemyBase.HCE_Kamikaze {kc};\n'
            if weapon == 'plasma caster':
                pat += '\t\tHaloDoom_EnemyBase.HCE_SpecialShot "HCE_PlasmaCasterClusterScaled", 3;\n'
            if ov.get('voices') or char in VOICES: pat += f'\t\tHaloDoom_EnemyBase.HCE_Voices "{ov.get("voices") or VOICES[char]}";\n'
            # ranges: how far it fires and the distance it tries to fight at (Halo world units -> map units)
            maxrange = max(rc['maximum_firing_range'], 4) * S
            rlo, rhi = rc['combat_range_lower_bound'] * S, rc['combat_range_upper_bound'] * S
            if rhi <= 0: rlo, rhi = 0, maxrange * 0.6
            if weapon == 'energy sword' or not weapon or ov.get('melee_only'): rlo, rhi = 0, 32
            # a fighting distance past the gun's reach left it holding where it couldn't fire (Halo CE's shotgun
            # Marines: 320-480 against a 400 reach): kept inside it
            if rhi > maxrange * 0.85 and weapon != 'energy sword' and weapon:
                rhi = maxrange * 0.85; rlo = min(rlo, rhi * 0.6)
            gun = rc.get('gun_offset_stand') or [0.1, 0, 0]
            gun = [max(radius, gun[0] * S), -gun[1] * S, gun[2] * S - height * 0.5 + height * 0.25]
            # melee
            meleer = (rc['melee_range'] or (a['berserk']['melee_attack_range'] if a['berserk']['melee_attack_range'] else 0.9)) * S
            meleed = MELEE.get(weapon, 55 if weapon else {'Hunter': 80, 'FloodInfection': 3, 'FloodCarrier': 40, 'FloodHuman': 25, 'FloodElite': 35}.get(char, 30))
            if char == 'Hunter': meleed, meleer = 80, max(meleer, 1.3 * S)
            if weapon == 'energy sword': meleer = max(meleer, 1.6 * S)
            if char == 'FloodCarrier': meleer = 1.0 * S
            # Doom-scale reach beyond both bodies' edges (Halo's melee_range is a decision radius, not arm length)
            meleer = {'Hunter': 56, 'FloodCarrier': 20, 'FloodInfection': 8}.get(char, 64 if weapon == 'energy sword' else 40 if char.startswith('Flood') else 36)
            if 'melee' in ov: meleer, meleed = ov['melee']
            # leaps (the Flood's, the infection forms'): Halo's berserk leap, with defaults for the Flood that have none
            bz = a['berserk']
            leapmin, leapmax = bz['melee_leap_range_lower_bound'] * S, bz['melee_leap_range_upper_bound'] * S
            leapchance = bz['melee_leap_chance']; leapvel = (bz['melee_leap_velocity'] or b.get('jump_velocity') or 0.1) * S / TICK
            if char == 'FloodInfection': leapmin, leapmax, leapchance, leapvel = 24, 3.5 * S, 1.0, max(8, 0.12 * S / TICK)
            if char.startswith('Flood') and char not in ('FloodInfection', 'FloodCarrier') and leapmax <= 0:
                leapmin, leapmax, leapchance, leapvel = 1.5 * S, 5 * S, 0.5, 0.16 * S / TICK
            if hunter_spin: leapmin, leapmax, leapchance, leapvel = HUNTER_LEAP
            if 'leap' in ov: leapmin, leapmax, leapchance, leapvel = ov['leap']
            # grenades
            gtype = 0
            gchance = gc['throw_grenade_chance']
            if gchance > 0: gtype = 2 if gc['grenade_type'] == 1 else 1
            gcount = max(v['items']['grenades_upper_bound'], 1 if gtype else 0)
            overcharge = weapon == 'plasma pistol' and char.startswith('Jackal')   # only Jackals overcharge
            # drops: the gun (DROP_WEAPON) and the grenades it dies with (ov 'drops' False for none)
            dw = DROP_WEAPON.get(weapon or '') if ov.get('drops', True) else None
            if char == 'Hunter': dw = None if weapon == 'plasma caster' else dw     # the White Hunter's is its arm cannon
            dg = {2: 'PlasmaGrenades', 1: 'FragGrenades'}.get(gtype) if gcount else None
            if dw or dg: pat += f'\t\tHaloDoom_EnemyBase.HCE_Drops "{dw or "None"}", "{dg or "None"}";\n'
            if char == 'Hunter' and HUNTER_ARM_WEAPON.get(weapon) and not dw:   # the gun its arm is (HDE weapon presets: hce_presets)
                pat += f'\t\tHaloDoom_EnemyBase.HCE_ArmWeapon "{HUNTER_ARM_WEAPON[weapon]}";\n'
            gmin, gmax = gc['grenade_range_lower_bound'] * S, (gc['grenade_range_upper_bound'] or 12) * S
            gvel = min(26, max(12, (b.get('grenade_velocity') or 0.2) * S / TICK))
            # perception
            pe = a['perception']
            vision = (pe['maximum_vision_distance'] or 30) * S
            fov = min(360, 2 * (pe['maximum_vision_angle'] or 1.2) * DEG)
            hearing = (pe['hearing_distance'] or 20) * S
            surprise = (a['panic']['surprise_distance'] or 2) * S
            # emotions: Halo's panic / defensive / moving blocks (written below as HCE_Panic, HCE_Defensive) and the
            # behaviour flags by kind (ACTOR_TYPES); ov 'flags' replaces the set, 'add_flags' extends it
            pa = a['panic']; df = a['defensive']; mvp = a['moving']
            flags = []
            t = ACTOR_TYPES.get(atype, '')
            if t in ('elite',): flags += ['HCE_Surprise', 'HCE_Berserks', 'HCE_SeeksCover', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_Leader']
            if t == 'jackal': flags += ['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades', 'HCE_FrontShield']
            if t == 'grunt': flags += ['HCE_Surprise', 'HCE_Panics', 'HCE_Evades', 'HCE_ThrowsGrenades']
            if t == 'hunter': flags += ['HCE_Berserks', 'HCE_FrontArmor', 'HCE_PairBond'] + (['HCE_Leaps'] if hunter_spin else [])
            if t == 'marine': flags += ['HCE_Panics', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_FollowPlayer']
            if t == 'flood': flags += ['HCE_Surprise', 'HCE_Berserks', 'HCE_Leaps', 'HCE_Resurrects']
            if t == 'infection': flags += ['HCE_Swarm', 'HCE_Leaps', 'HCE_Explodes']
            if t == 'carrier': flags += ['HCE_Surprise', 'HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Explodes']
            if char in SENTINEL_LIKE: flags += ['HCE_Surprise', 'HCE_Evades', 'HCE_Flying'] + (['HCE_Beam'] if beam else [])
            if a['flags'] >> 19 & 1 or weapon == 'energy sword': flags.append('HCE_AlwaysBerserk')
            if v['flags'] >> 4 & 1 or v['flags'] >> 5 & 1: flags.append('HCE_ActiveCamo')
            if not gtype and 'HCE_ThrowsGrenades' in flags: flags.remove('HCE_ThrowsGrenades')
            if weapon in LOBBED: flags.append('HCE_Lobbed')
            if 'flags' in ov: flags = list(ov['flags'])
            if weapon in LOBBED and 'HCE_Lobbed' not in flags: flags.append('HCE_Lobbed')
            if char.startswith('Elite') and shield > 0: flags.append('HCE_ShieldStun')   # hard-ping stun when the shield pops
            flags += [f for f in ov.get('add_flags', ()) if f not in flags]
            flags = sorted(set(flags))
            # skins: one baked texture per material into models/<mdir>/<Char>/skins (shared where variants look the same),
            # weapon textures into models/<mdir>/weapons; skin_lines / weapon_lines become the MODELDEF's SurfaceSkins.
            # Which bake: a SKIN_HOOK, bake_hunter, bake_vivid, the painted Elite skins, the Spec Ops purple, else bake_skin
            color = variant_color(v, b)
            # Flood: the change colour covers nearly the whole body on Xbox and turns them green;
            # the base maps already carry the right flesh/fatigue/armour colours
            if char.startswith('Flood') and char not in FLOOD_RANKED: color = None
            skin_lines = []; weapon_lines = []; field_skin = None
            wid_equipped = WEAPON_IDS.get(rc['reference'] or '')
            if not ov.get('overlay') and meta.get('hand_frame') and wid_equipped:
                # a body without baked guns (extract_chars.OVERLAY_GUNS): Halo CE's own gun as its overlay too
                ars = meta.get('arsenal') or {}
                hit = sorted((k != wid_equipped, k) for k, a in ars.items() if a.get('wid') == wid_equipped)
                if hit: ov = dict(ov, overlay=hit[0][1])
            # the shot leaves the barrel: the gun's tip as the body holds it aiming (its firing pose, else its alert
            # stance), from the feet; HCE_GunOffset is from mid-height (HDE's Fire3DProjectile)
            ovm = ((meta.get('arsenal') or {}).get(ov['overlay']) or {}).get('model') if ov.get('overlay') else None
            aim = ((table.get('FIRE') or []) + (table.get('ALERT') or []) + (table.get('IDLE') or []) + [None])[0]
            lift = -meta['bounds'][0][2] if ov.get('lift') else 0.0
            def to_doom(p, lift=lift, height=height, radius=radius, msc=msc):
                """a point in Halo model space (feet, +x forward, +y left) -> HCE_GunOffset's frame (map units, from
                mid-height, +y right), at this model's scale"""
                return [max(radius * 0.5, p[0] * S * msc), -p[1] * S * msc, (p[2] + lift) * S * msc * 1.2 - height * 0.5]
            anchor = None if 'gun' in ov else gun_anchor(char, meta, pack, mdir, aim, wid_equipped, ovm)
            mz = muzzle_point(anchor, aim)
            if mz is not None: gun = to_doom(mz)
            if 'gun' in ov: gun = list(ov['gun'])
            muzzle_zs = '' if mz is None else muzzle_code(anchor, table, to_doom, gun)
            mesh_weapon = meta.get('mesh_weapon') or [None] * len(meta['meshes'])
            stubs = {d['stub'] for d in meta.get('gore', {}).get('limbs', {}).values() if d.get('stub') is not None} if not meta.get('gore', {}).get('cap_model') else set()
            stubs |= {x['stub'] for d in meta.get('gore', {}).get('limbs', {}).values() for x in d.get('variants', {}).values()}
            blood_hidden = []
            for si, mat in enumerate(meta['meshes']):
                matn = mat[:-4]
                if si in stubs:                    # gore stumps: hidden until the limb comes off (HCE_SeverLimb)
                    weapon_lines.append(f'\tSurfaceSkin 0 {si} "hce_hidden.png"')
                    continue
                if si < len(mesh_weapon) and mesh_weapon[si]:
                    # weapon textures are shared by every character: one copy in models/hce/weapons
                    os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
                    if mesh_weapon[si] == wid_equipped:
                        wmat = WEAPON_SKIN.get(weapon or '', {}).get(mat, mat)   # re-coloured weapon variants
                        dst = f'{pack}/models/{mdir}/weapons/{wmat}'
                        src = f'{OUT}/models/{char}/{wmat}'
                        if not os.path.exists(src): src = f'{OUT}/weapons/{wid_equipped}/{wmat}'
                        if not os.path.exists(dst): copy_weapon_tex(src, dst)
                        weapon_lines.append(f'\tSurfaceSkin 0 {si} "{wmat}"')
                    else:
                        hid = f'{pack}/models/{mdir}/weapons/hce_hidden.png'
                        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
                        weapon_lines.append(f'\tSurfaceSkin 0 {si} "hce_hidden.png"')
                    continue
                if SHIELD_MAT.get(char) == matn and v.get('_rank') in SHIELD_TINT and char in FIELD_CHARS:
                    # drawn by the shield field (HCE_ShieldField), not on the body: the field's skin is the rank's colour
                    fn = f'{cls[4:].lower()}_field.png'
                    Image.new('RGB', (4, 4), tuple(int(round(c * 255)) for c in SHIELD_TINT[v['_rank']])).save(f'{pack}/models/{mdir}/{char}/skins/{fn}')
                    own = None
                    if char in FIELD_UV_MASK:
                        own = f'models/{mdir}/{char}/skins/field_mask.png'
                        field_mask(f'{OUT}/models/{char}/{char}.iqm', si, f'{pack}/{own}')
                    FIELD_TEX[f'models/{mdir}/{char}/skins/{fn}'] = ('jshield', mesh_layers(f'{OUT}/models/{char}/{char}.iqm', si), own)
                    field_skin = (si, fn)
                    hid = f'{pack}/models/{mdir}/{char}/skins/hce_hidden.png'
                    if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
                    skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/hce_hidden.png"')
                    continue
                if SHIELD_MAT.get(char) == matn and v.get('_rank') in SHIELD_TINT:
                    fn = f'{cls[4:].lower()}_shield.png'
                    dst = f'{pack}/models/{mdir}/{char}/skins/{fn}'
                    bake_shield(char, matn, SHIELD_TINT[v['_rank']], dst)
                    shield_tex.append(f'models/{mdir}/{char}/skins/{fn}')
                    skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/{fn}"')
                    continue
                hook = SKIN_HOOK.get(char)
                if hook:
                    r = hook(cls=cls, v=v, si=si, mat=mat, meta=meta, skin_dir=f'{pack}/models/{mdir}/{char}/skins')
                    if r is not None and 'hce_hidden' in r and si in (meta.get('blood') or {}).get('surfaces', []):
                        blood_hidden.append(si)
                    if r is not None:
                        skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/{r}"')
                        continue
                fn = f'{ov.get("skin_as", cls)[4:].lower()}_{matn.lower()}.png'     # arsenal Marines share their AR twin's
                if char.startswith('Flood') and char not in FLOOD_RANKED and 'HCE_ActiveCamo' not in flags:
                    fn = f'{char.lower()}_{matn.lower()}.png'      # the Flood's skins are the same for every gun: one copy
                dst = f'{pack}/models/{mdir}/{char}/skins/{fn}'
                if not os.path.exists(dst):
                    vivid = next((c for k, c in VIVID.items() if k in vname), None)
                    if v.get('_hunter_color'): bake_hunter(char, matn, v['_hunter_color'], dst)
                    elif vivid: bake_vivid(char, matn, vivid, dst, next((x for k, x in VIVID_SHINE.items() if k in vname), 1.0))
                    elif elite_skin(char, matn, color, dst, specops='specops' in vname): pass
                    elif 'specops' in vname and (char.startswith('Elite') or (char == 'GruntSpecOps' and max(color or (1,)) < 0.2)):
                        # the Spec Ops body's own textures: baked as a blue Minor (the blue cube-map sheen the painted
                        # skins have), then turned purple the same way as the painted skins. The black Spec Ops Grunts
                        # get the same purple (the red anti-air ones keep their red)
                        bake_skin(char, matn, MINOR_BLUE, dst)
                        if char == 'GruntSpecOps': grunt_purple(char, matn, dst)
                        else: purple(Image.open(dst).convert('RGB')).save(dst)
                    else: bake_skin(char, matn, color, dst, RANK_SHINE.get((char, v.get('_rank')), 1.0))
                SKIN_PAIRS.append((f'{OUT}/models/{char}/{matn}.png', dst))        # skin_check: the bake against its source
                skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/{fn}"')
            friendly = '\t\t+FRIENDLY\n' if team[char] == 'HUMAN' else ''
            if ov.get('ally'): friendly = '\t\t+FRIENDLY\n\t\tHaloDoom_EnemyBase.HCE_Team HCE_TEAM_HUMAN;\n'   # fights on the player's side
            # the class's Default block: everything above as HaloDoom_EnemyBase properties (enemies_base.zsc reads them),
            # then pat (pattern, sounds, drops, voices) and the flags
            props = f'''\t\tHealth {body};
{friendly}\t\tSpeed {run:.1f};
\t\tHaloDoom_EnemyBase.HCE_Type {atype};
\t\tHaloDoom_EnemyBase.HCE_Variant "{vname.split(chr(92))[-1]}";
\t\tHaloDoom_EnemyBase.HCE_Perception {vision:.0f}, {fov:.0f}, {hearing:.0f}, {surprise:.0f};
\t\tHaloDoom_EnemyBase.HCE_Movement {walk:.2f}, {run:.2f}, {12 if char != 'Hunter' else 7};
\t\tHaloDoom_EnemyBase.HCE_LowWalk {low:.2f};
\t\tHaloDoom_EnemyBase.HCE_Weapon "{proj}", {pps}, {rof:.2f}, {err:.2f}, {maxrange:.0f};
\t\tHaloDoom_EnemyBase.HCE_ProjectileSpeed {projspeed:.1f};
\t\tHaloDoom_EnemyBase.HCE_DamageModifier {dmgmod:.2f};
\t\tHaloDoom_EnemyBase.HCE_CombatRange {rlo:.0f}, {rhi:.0f};
\t\tHaloDoom_EnemyBase.HCE_Burst {bmin:.2f}, {bmax:.2f}, {smin:.2f}, {smax:.2f}, {rc['first_burst_delay_lower_bound']:.2f}, {rc['target_lead_fraction']:.2f};
\t\tHaloDoom_EnemyBase.HCE_GunOffset ({gun[0]:.1f}, {gun[1]:.1f}, {gun[2]:.1f});
\t\tHaloDoom_EnemyBase.HCE_SpecialFire {1 if overcharge or weapon == 'plasma caster' or weapon in SPECIAL_FIRE else 0}, {0.2 if overcharge else 0.3 if weapon == 'plasma caster' else SPECIAL_FIRE.get(weapon, 0)};
\t\tHaloDoom_EnemyBase.HCE_Melee {meleer:.0f}, {meleed};
\t\tHaloDoom_EnemyBase.HCE_Leap {leapmin:.0f}, {leapmax:.0f}, {leapchance:.2f}, {leapvel:.1f};
\t\tHaloDoom_EnemyBase.HCE_Grenades {gtype}, {gcount}, {gchance:.2f}, {gc['throw_grenade_delay']:.1f}, {gmin:.0f}, {gmax:.0f}, {gvel:.1f};
\t\tHaloDoom_EnemyBase.HCE_Panic {pa['panic_damage_threshold']:.2f}, {pa['panic_chance_leader_type_killed']:.2f}, {pa['cower_time_lower_bound']:.1f}, {pa['cower_time_upper_bound']:.1f};
\t\tHaloDoom_EnemyBase.HCE_Berserk {bz['damage_berserk_amount']:.2f}, {bz['damage_berserk_threshold']:.2f}, {bz['proximity_berserk_distance'] * S:.0f};
\t\tHaloDoom_EnemyBase.HCE_Defensive {df['shield_fraction_hide']:.2f}, {df['shield_fraction_emerge_attack']:.2f}, {mvp['cover_dive_chance']:.2f}, {mvp['grenade_dive_chance']:.2f}, {mvp['cover_emerge_chance']:.2f};
\t\tHaloDoom_EnemyBase.HCE_Feign {b.get('feign_death_chance') or 0:.2f}, {b.get('feign_death_time') or 0:.1f};
\t\tHaloDoom_EnemyBase.HCE_Shield {shield:.0f}, {min(5.0, coll.get('shield_stun_time') or 3):.1f}, {min(6.0, coll.get('shield_recharge_time') or 4):.1f};
\t\tHaloDoom_EnemyBase.HCE_FlyHeight {48 if char in SENTINEL_LIKE or ov.get('flying') else 0};
''' + pat + ''.join(f'\t\t+HaloDoom_EnemyBase.{f}\n' for f in flags)
            # the class body after Default: the character's / weapon's / variant's own ZScript (TYPE_CODE, WEAPON_CODE,
            # ov 'code' with its {HCE_...} placeholders filled in), the overlay gun, gunner seats, the shield flare's
            # hidden surfaces, the camo blade and plain shaders, then the animation functions and the muzzle table
            extra = ('' if char in BASE_CODE else TYPE_CODE.get(char, '')) + WEAPON_CODE.get(weapon or '', '') + ov.get('code', '')
            if '{HCE_BODY_SURFS}' in extra:      # a whole Halo 2 body over this model: its own body surfaces (no guns, no gore)
                mw = meta.get('mesh_weapon') or []
                bsurf = [i for i, n in enumerate(meta.get('mesh_names') or []) if not n.startswith(('weapon_', 'gore.')) and not (mw[i] if i < len(mw) else None)]
                extra = extra.replace('{HCE_CHAR}', char).replace('{HCE_BODY_SURFS}', ', '.join(map(str, bsurf)) or '-1').replace('{HCE_BLOOD_IDX}', str(BLOOD_IDX))
                gl = (meta.get('gore') or {}).get('limbs', {})
                for L, nm in ((1, 'larm'), (2, 'rarm'), (3, 'head')):       # the CE Elite's own stumps (hidden under a Halo 2 body's)
                    extra = extra.replace(f'{{HCE_STUB_{L}}}', str(gl.get(nm, {}).get('stub', -1)))
            extra = extra.replace('{HCE_MODEL_SCALE}', f'{S * msc:.1f}')
            if not char.startswith('Marine') and (ov.get('unique') or weapon in WEAPON_CODE or weapon in PICKUP_SKIP):
                extra += '\toverride bool HCE_HasLoadouts() { return false; }      // keeps the gun it is built around\n'
            if ov.get('overlay'): extra += overlay_gun_code(char, meta, mdir, ov, pack)
            extra += gunner_code(vname.split(chr(92))[-1], meta, S * msc, ov)
            # the shield flare is one model per body: it hides what this variant's MODELDEF hides (another rank's
            # armour, the Knights' other guns), so its shape is this variant's
            shell_hid = sorted({int(m.group(1)) for l in skin_lines for m in [re.match(r'\tSurfaceSkin 0 (\d+) "[^"]*hce_hidden[^"]*"', l)] if m})
            if char in SHELL_TINT and shell_hid:
                extra += ('\toverride void HCE_DressShellVariant(Actor s)\n\t{\n'
                          f'\t\tstatic const int H[] = {{ {", ".join(map(str, shell_hid))} }};\n'
                          f'\t\tfor(int i = 0; i < H.Size(); i++) s.A_ChangeModel(\'None\', 0, "", \'None\', H[i], "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n\t}}\n')
            if char == 'Hunter' and HUNTER_ARM_WEAPON.get(weapon):
                extra += f'\toverride Name HCE_LimbReplacement(int limb) {{ if(limb != HCE_LIMB_RARM) return \'None\'; return "{HUNTER_ARM_WEAPON[weapon]}"; }}\n'
            if '%STICKY_LOADED%' in extra:
                extra = (extra.replace('%STICKY_LOADED%', overlay_swap(char, meta, mdir, 'sticky_detonator'))
                              .replace('%STICKY_FIRED%', overlay_swap(char, meta, mdir, 'sticky_detonator_fired')))
            if ov.get('weapon_toss'):
                # hide the held weapon's surfaces at runtime (a Brute throwing its gun away to go berserk)
                ws = [si for si, wv in enumerate(mesh_weapon) if wv]
                extra += '\tvoid HCE_HideWeaponSurfaces()\n\t{\n' + ''.join(
                    f'\t\tA_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n' for si in ws) + '\t}\n'
            if blood_hidden:                       # the blood overlay skips surfaces this variant doesn't wear
                extra += '\toverride void HCE_BloodHideClass()\n\t{\n' + ''.join(blood_hide(si, mdir).replace('\t\t\t', '\t\t', 1) for si in blood_hidden) + '\t}\n'
            blade = 'HCE_ActiveCamo' in flags and weapon == 'energy sword'
            if blade:
                # the energy sword's blade isn't cloaked (Halo shows it): a second copy of the model, only the blade
                # surface drawn, at full brightness, playing the Elite's animations
                extra += (f'\tActor hce_bladeActor;\n\toverride void PostBeginPlay()\n\t{{\n'
                          f'\t\thce_bladeActor = Spawn("{cls}Blade", pos, NO_REPLACE);\n'
                          f'\t\tif(hce_bladeActor) hce_bladeActor.master = self;\n\t\tsuper.PostBeginPlay();\n\t}}\n'
                          f'\toverride void HCE_ApplyAnim(Name n, int blend, bool loop)\n\t{{\n\t\tsuper.HCE_ApplyAnim(n, blend, loop);\n'
                          f'\t\tif(hce_bladeActor) hce_bladeActor.SetAnimation(n, -1, hce_applyFrame, -1, -1, blend, loop ? SAF_LOOP : 0);\n\t}}\n'
                          f'\toverride void HCE_OnSever(int limb, bool gunArm)\n\t{{\n\t\tif(gunArm && hce_bladeActor) {{ hce_bladeActor.Destroy(); hce_bladeActor = null; }}\n\t}}\n')
            animtxt = zs_anim_funcs(A, table, ov.get('berserk_anims', BERSERK_ANIMS.get(char)), msc)
            if ov.get('johnson'): animtxt, jx = johnson_code(A, animtxt, char, meta, mdir); extra += jx
            if ov.get('stacker'): animtxt, jx = stacker_code(A, animtxt, char, meta, mdir); extra += jx
            extra += muzzle_zs
            if 'HCE_ActiveCamo' in flags:
                # cheaper shading (hce_simpleshaders): plain copies of the camo skins, with no shader on them
                plain = []
                for line in skin_lines:
                    m = re.match(r'\tSurfaceSkin 0 (\d+) "skins/(.*)"', line)
                    if not m: continue
                    pn = m.group(2)[:-4] + '_plain.png'
                    shutil.copy(f'{pack}/models/{mdir}/{char}/skins/{m.group(2)}', f'{pack}/models/{mdir}/{char}/skins/{pn}')
                    line_ = f"A_ChangeModel('None', 0, \"\", 'None', {m.group(1)}, \"models/{mdir}/{char}/skins\", '{pn}', CMDL_USESURFACESKIN);\n"
                    lsw = next((GORE_LIMBS[L] for L, d in (meta.get('gore') or {}).get('limbs', {}).items() if int(m.group(1)) in d.get('swap', [])), None)
                    plain.append(f"\t\t{'' if lsw is None else f'if(hce_severed & (1 << {lsw})) '}{line_}")   # a damaged permutation: once its limb is off
                if plain: extra += '\toverride void HCE_PlainShaders()      // hce_simpleshaders: the camo skins without the camo shader\n\t{\n' + ''.join(plain) + '\t}\n'
            # the class itself, then its companions: the camo blade, the shield flare (one per body, from the first
            # shielded variant) and the Halo 2 bodies' own flares
            zs.append(f'// {cls}: Halo variant "{vname}"' + (f', {weapon}' if weapon else ', no gun') + f', {body} body'
                      + (f' / {shield:.0f} shield' if shield else '') + ', ' + (f'{len(flags)} behaviour flags' if flags else 'no behaviour flags') + '\n'
                      f'// (the editor keys below are Ultimate Doom Builder\'s; the numbers are explained at the top of this file)\n'
                      f'class {cls} : HCE_{char}Base\n{{\n{editor_keys(cls, char, team[char], weapon=weapon)}\tDefault\n\t{{\n{props}\t}}\n{animtxt}\n{extra}}}\n')
            if blade:
                zs.append(f'class {cls}Blade : HCE_BladeShell {{}}\n')
                bl = [f'\tSurfaceSkin 0 {si} "hce_hidden.png"' for si in range(len(meta['meshes']))]
                for si, mat in enumerate(meta['meshes']):
                    if si < len(mesh_weapon) and mesh_weapon[si] == 'energy_sword' and 'glow' in mat: bl[si] = f'\tSurfaceSkin 0 {si} "{mat}"'
                md.append(f'Model {cls}Blade\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n\tPath "models/{mdir}/weapons"\n' + '\n'.join(bl) +
                          f'\n\tScale {S * msc:.0f} {S * msc:.0f} {S * msc * 1.2:.0f}\n\tUseActorPitch\n\tBaseFrame\n\tFrameIndex HCEM A 0 0\n}}\n')
            if char in SHELL_TINT and shield > 0 and char not in shells:
                shells.add(char)
                zs.append(f'// energy-shield flare for the {char}s: the same model, every surface the glowing shield texture\n'
                          f'class HCE_{char}ShieldShell : HCE_ShieldShell {{}}\n')
                tex = f'{pack}/models/{mdir}/{char}/skins/shieldshell.png'
                bake_shell(SHELL_TINT[char], tex)
                sl = []
                for line in skin_lines:
                    m = re.match(r'\tSurfaceSkin 0 (\d+) "(.*)"', line)
                    if m: sl.append(f'\tSurfaceSkin 0 {m.group(1)} "skins/shieldshell.png"')
                if weapon_lines:
                    sl += [f'\tPath "models/{mdir}/weapons"'] + [re.sub(r'"[^"]*"$', '"hce_hidden.png"', w) for w in weapon_lines]
                scs = S * msc * 1.035
                md.append(f'Model HCE_{char}ShieldShell\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(sl) +
                          f'\n\tScale {scs:.1f} {scs:.1f} {scs * 1.2:.1f}\n\tUseActorPitch\n\tBaseFrame\n\tFrameIndex HCEM A 0 0\n}}\n')
            if ov.get('h2_pieces') and char in SHELL_TINT and shield > 0:
                sz_, sm_ = h2_shell_code(char, ov['h2_pieces'], meta, pack, mdir, S * msc * 1.035, shells)
                zs += sz_; md += sm_
            if 'HCE_ActiveCamo' in flags:
                for line in skin_lines:
                    m = re.match(r'\tSurfaceSkin 0 \d+ "(skins/.*)"', line)
                    if m and 'hce_hidden' not in m.group(1): camo.append(f'models/{mdir}/{char}/{m.group(1)}')
            # the MODELDEF block: the body with its skins and weapon textures, an overlay gun as a second model
            if weapon_lines: skin_lines += [f'\tPath "models/{mdir}/weapons"'] + weapon_lines
            frames = '\tFrameIndex HCEM A 0 0'
            if ov.get('overlay'):
                # the Marine arsenal (marine_arsenal.py): the gun is its own model on the body's skeleton, model 6
                oi = ov.get('overlay_idx', ARSENAL_IDX)
                skin_lines += arsenal_lines(char, ov['overlay'], meta, pack, mdir, oi)
                frames += f'\n\tFrameIndex HCEM A {oi} 0'
            elif char in OVERLAY_PLACEHOLDER and meta.get('arsenal'):
                # its overlay slot, empty (every surface hidden) until it picks up a gun drawn as an overlay
                oi = OVERLAY_SLOT[char]
                first = sorted(meta['arsenal'])[0]
                skin_lines += [re.sub(r'"[^"]*"$', '"hce_hidden.png"', l) if l.startswith(f'\tSurfaceSkin {oi} ') else l
                               for l in arsenal_lines(char, first, meta, pack, mdir, oi)]
                frames += f'\n\tFrameIndex HCEM A {oi} 0'
            sc = S * msc
            # 'lift': a model built round its middle (the Sentinel Enforcer's hull) raised so its underside sits at the actor's feet
            zoff = f'\n\tZOffset {-meta["bounds"][0][2] * sc * 1.2:.0f}' if ov.get('lift') else ''
            md.append(f'Model {cls}\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(skin_lines) +
                      f'\n\tScale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}{zoff}\n\tUseActorPitch\n\tUseActorRoll\n\tBaseFrame\n{frames}\n}}\n')   # roll: the severed pieces tumble with it
            if field_skin and not ov.get('loadout_only'):
                # its shield field: the body's model with only the shield surface drawn (HCE_ShieldField)
                fl = [f'\tSurfaceSkin 0 {i} "skins/{field_skin[1] if i == field_skin[0] else "hce_hidden.png"}"' for i in range(len(meta['meshes']))]
                md.append(f'Model {cls}ShieldField\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(fl) +
                          f'\n\tScale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}{zoff}\n\tUseActorPitch\n\tUseActorRoll\n\tDontCullBackfaces\n\tBaseFrame\n\tFrameIndex HCEM A 0 0\n}}\n')   # (one-sided plate, drawn from behind too: the engine culls translucent models' back faces)
                zs.append(f'// the {cls[4:]}\'s arm shield\nclass {cls}ShieldField : HCE_ShieldField {{}}\n')
            # a loadout other bodies of this kind can switch to (loadout_code)
            marine = char.startswith('Marine')
            if team[char] in PICKUP_TEAMS and dw and weapon and weapon not in PICKUP_SKIP and (marine or weapon not in WEAPON_CODE and weapon != 'plasma caster' and (dw in COVENANT_GUNS or char == 'Brute')) and \
                    not ov.get('unique') and dw not in prof and proj != 'None':
                pm = re.search(r'HCE_FirePattern ([^;]+);', pat)
                sf = 1 if overcharge or weapon == 'plasma caster' or weapon in SPECIAL_FIRE else 0
                if ov.get('overlay'):
                    # an overlay gun: the gun surfaces baked into the body (if any) hidden, the overlay model on its slot
                    oi = ov.get('overlay_idx', ARSENAL_IDX)
                    vis = ''.join(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n'
                                  for si, w_ in enumerate(meta.get('mesh_weapon') or []) if w_)
                    vis += overlay_swap(char, meta, mdir, ov['overlay'], oi, pack).replace('\t\t', '\t\t\t', 1).replace('\n\t\t', '\n\t\t\t')
                else:
                    # a gun baked into the body: its surfaces shown, the others and any overlay gun hidden
                    shown = {int(m.group(1)): m.group(2) for m in (re.match(r'\tSurfaceSkin 0 (\d+) "(.*)"', l) for l in weapon_lines) if m}
                    vis = ''.join(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'{tx}\', CMDL_USESURFACESKIN);\n'
                                  for si, tx in sorted(shown.items()))
                    if char in OVERLAY_SLOT and vis:
                        vis += f'\t\t\tA_ChangeModel(\'None\', {OVERLAY_SLOT[char]}, "", \'None\', 0, "", \'None\', CMDL_HIDEMODEL);\n'
                if vis:
                    prof[dw] = dict(proj=proj, pps=pps, rof=rof, err=err, maxrange=maxrange, projspeed=projspeed, rlo=rlo, rhi=rhi,
                                    dmgmod=dmgmod, sf=sf, sc=0.2 if overcharge else SPECIAL_FIRE.get(weapon, 0), lobbed=weapon in LOBBED,
                                    pattern=pm.group(1) if pm else None, sounds=FIRE_SOUNDS.get(pkey), loop=bool(FIRE_SOUNDS.get(pkey, [0] * 5)[4]),
                                    table=table, visual=vis, special=('HCE_PlasmaCasterClusterScaled', 3) if weapon == 'plasma caster' else ('None', 0))
            if ov.get('loadout_only'):             # a Covenant gun for the Marines: its loadout only, no class of its own
                zs.pop(); md.pop()
                continue
            # bookkeeping: its DoomEdNum now, or after the first release's classes ('_late'); its place in the random spawner
            if v.get('_late'): late.append(cls)
            else: ednums.append((ed, cls)); ed += 1
            if not ov.get('unique') and not ov.get('ally') and char not in NO_RANDOM and cls not in RANDOM_EXCLUDE: spawners.setdefault(char, []).append(cls)
        if len(prof) > 1:              # more than its own gun to choose from
            zs[base_idx] = zs[base_idx][:-2] + loadout_code(char, prof, AnimSet(meta)) + '}\n'
    # ---------------- projectiles with Halo damage
    pz = ['// Enemy projectiles: HDE visuals, Halo CE impact damage']
    if main and any(w in projectiles_used for w in list(KNIGHT_GUNS) + ['enforcer needler'] + HARDLIGHT_WEAPONS): pz.append(HARDLIGHT_CODE)
    done = set()
    for wn in sorted(projectiles_used):
        pc, base_cls, dmg, sp = WEAPONS[wn]
        if pc in done or (not main and wn in MAIN_WEAPONS): continue
        done.add(pc)
        body = ''
        if dmg is not None:
            prop = 'HaloSlowProjectile' if base_cls in ('HaloNeedler_Proj', 'HaloRocketProj', 'HaloSpiker_Bullet', 'HCE_NeedleScaled', 'HCE_RocketScaled') or base_cls in SLOW_PROJ else 'HaloProjectile'
            body = f'\t\t{prop}.BaseDamage {dmg};\n'
        # HDE projectiles (not grenades / fuel rods / flames) re-apply the enemy damage nerf when they hit
        mix = f'\tmixin {cfg.get("nerf_mixin", "HCE_NerfMixin")};\n' if base_cls not in NO_NERF_MIXIN else ''
        if base_cls in LITE_PLASMA:            # HDE's plasma bolts with far fewer effect actors (hce_explosives.zsc)
            lite = cfg.get('lite_mixin', 'HCE_LitePlasma')
            mix += f'\tmixin {lite};\n' + (f'\tmixin {lite}Smoke;\n' if LITE_PLASMA[base_cls] else '')
        pz.append(f'class {pc} : {base_cls}\n{{\n{mix}\tDefault\n\t{{\n{body}\t}}\n}}\n')
    if main: pz.append('class HCE_ChargedPlasma : HaloChargedPlasma_Proj\n{\n\tmixin HCE_NerfMixin;\n\tmixin HCE_LitePlasma;\n\tDefault\n\t{\n\t\tHaloProjectile.BaseDamage 70;\n\t}\n}\n')
    # ---------------- random spawners per character
    late_chars = cfg.get('late_chars', [])      # characters added after a release: numbered after everything else
    def spawner(char, lst):
        """HCE_Random<char>: a RandomSpawner over the character's classes lst, weighted by RANDOM_WEIGHTS, with the
        next DoomEdNum"""
        nonlocal ed
        weights = {c: RANDOM_WEIGHTS.get(c, 1) for c in lst}
        pz_ = '\n'.join(f'\t\tDropItem "{c}", 255, {weights[c]};' for c in lst)
        keys = editor_keys(f'HCE_Random{char}', char, team[char], f'Random {words(char)}', sprite_of=lst[0])
        zs.append(f'class HCE_Random{char} : RandomSpawner\n{{\n{keys}\tDefault\n\t{{\n{pz_}\n\t}}\n}}\n')
        ednums.append((ed, f'HCE_Random{char}')); ed += 1
    for char, lst in sorted(spawners.items()):
        if char not in late_chars: spawner(char, lst)
    # Doom boss stand-ins (spawned only by HCE_ReplaceHandler; no DoomEdNums)
    blocks = {re.match(r'Model (\w+)', b).group(1): b for b in md}
    for alias, (base, doom, hmul) in sorted(BOSS_ALIASES.items() if main else []):
        if base not in blocks: continue
        m = re.search(r'class ' + base + r' : \w+\n\{\n(?:\t//\$[^\n]*\n)*\tDefault\n\t\{\n\t\tHealth (\d+);', '\n'.join(zs))
        hp = int(int(m.group(1)) * hmul) if m else 100
        zs.append(f'// stands in for Doom\'s {doom}: CheckReplacee maps it back so A_BossDeath map specials fire\n'
                  f'class {alias} : {base}\n{{\n\tDefault\n\t{{\n\t\tHealth {hp};\n\t}}\n}}\n')
        md.append(blocks[base].replace(f'Model {base}\n', f'Model {alias}\n', 1))
    # classes added after the first release keep their numbers: appended in release order, never re-sorted
    LATE_ORDER = cfg.get('late_order', ['HCE_JackalMajorNeedler', 'HCE_HunterUltra'])
    late_items = late + [f'HCE_Random{c}' for c in late_chars if c in spawners]
    late_items.sort(key=lambda c: (LATE_ORDER.index(c) if c in LATE_ORDER else len(LATE_ORDER), c))
    for cls in late_items:                 # classes added after the first release keep old numbers stable
        if cls.startswith('HCE_Random') and cls[10:] in late_chars: spawner(cls[10:], spawners[cls[10:]])
        else: ednums.append((ed, cls)); ed += 1
    # glow: shields, needles, sword blade (the blade has its own shader below)
    for w in ('w_needler_glow.png',):
        if os.path.exists(f'{pack}/models/{mdir}/weapons/{w}'): brightmaps.append(f'models/{mdir}/weapons/{w}')
    swords = [f'models/{mdir}/weapons/w_energy_sword_glow.png'] if os.path.exists(f'{pack}/models/{mdir}/weapons/w_energy_sword_glow.png') else []
    for w in cfg.get('glow', []):
        if os.path.exists(f'{pack}/models/{mdir}/weapons/{w}'): brightmaps.append(f'models/{mdir}/weapons/{w}')
    gl = [cfg.get('gl_title', '// Halo CE enemy pack: glowing surfaces (energy shields, needles, sword blade)')]
    full = f'{pack}/models/{mdir}/brightmap_full.png'
    Image.new('RGB', (8, 8), (255, 255, 255)).save(full)
    for t in sorted(set(brightmaps)):
        gl.append(f'brightmap texture "{t}"\n{{\n\tmap "models/{mdir}/brightmap_full.png"\n}}')
    gl += glow_maps(pack, mdir, cfg['team'], set(camo))
    gl += selfillum_gl(pack, mdir, set(camo))
    # Jackal energy shields: the baked rank-coloured field animated by a shader (a drifting field, a hex lattice whose
    # cells flicker, light sweeping over it, a pulse), drawn fullbright
    if shield_tex:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_shield.fp', 'w').write(SHIELD_SHADER)
        for t in sorted(set(shield_tex)):
            gl.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_shield.fp"\n\tspeed 1.0\n\tbrightmap "models/{mdir}/brightmap_full.png"\n}}')
    # Halo's shield shaders: the flares' plasma, the Sentinels' bubbles (Halo 2's), the Jackals' and Enforcer's shield fields
    gl += shader_gl(pack, mdir, bubbles)
    # the energy sword's blade: plasma streaming up it, a white-hot core, shimmering edges (fullbright)
    if swords:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_sword.fp', 'w').write(SWORD_SHADER)
        for t in swords:
            gl.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_sword.fp"\n\tspeed 1.0\n\tbrightmap "models/{mdir}/brightmap_full.png"\n}}')
    # active camo: a shimmer shader on the camo variants' own skins (bands of light running over a faint body)
    if camo:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_camo.fp', 'w').write(CAMO_SHADER)
        for t in sorted(set(camo)):
            gl.append(f'HardwareShader Texture "{t}"\n{{\n\tShader "shaders/hce_camo.fp"\n\tSpeed 1.0\n}}')
    # the ODSTs' visors: Halo CE's visor reflection, a cube map looked up per pixel (extract_odst.py)
    gl += odst_visors(pack, mdir, md)
    # the Marine kit's enclosed helmets: the same reflection on their orange visor
    gl += kit_visors(pack, mdir)
    gl += elite_lens_visors(pack, mdir)
    gl += EXTRA_GL
    tg = cfg['tag']
    open(f'{pack}/gldefs.{tg}', 'w').write('\n'.join(gl) + '\n')
    # HCEM A: placeholder sprite. Models draw instead, but the map spawner rejects actors whose sprite
    # has no frames ("has no frames" -> Unknown), so DoomEdNum things and replacements need a real lump.
    if main:
        os.makedirs(f'{pack}/sprites', exist_ok=True)
        Image.new('RGBA', (4, 4), (0, 0, 0, 0)).save(f'{pack}/sprites/HCEMA0.png')
    # hidden surfaces not drawn at all (lib/modeldef_prune.py): the MODELDEF lines hiding them dropped, each enemy
    # class told which of its surfaces those are (HCE_HideSurface) and its own run-time hides routed through it
    other = '\n'.join(open(f).read() for d in {pack, PACK} for f in glob.glob(f'{d}/ZScript/**/*.zsc', recursive=True)
                      if not f.endswith((f'{tg}_enemies.zsc', f'{tg}_projectiles.zsc')))
    other += '\n'.join(open(f).read() for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'addons', 'localdev', 'ZScript', '**', '*.zsc'), recursive=True))
    md_text, zs_text = modeldef_prune.apply(pack, '\n'.join(md), '\n'.join(zs), other)
    open(f'{pack}/ZScript/HaloCE/{tg}_enemies.zsc', 'w').write(zs_text)
    open(f'{pack}/ZScript/HaloCE/{tg}_projectiles.zsc', 'w').write('\n'.join(pz))
    open(f'{pack}/modeldef.{tg}', 'w').write(md_text)
    ednums = pin_ednums(ednums)
    if os.path.exists(f'{pack}/sprites/udb'): shutil.rmtree(f'{pack}/sprites/udb')
    n_icons = ship_udb_icons([c for _, c in ednums], f'{pack}/sprites/udb')     # UDB thing icons (split_factions.py: per faction)
    if n_icons: print(f'UDB icons: {n_icons} of {len(ednums)} placeable classes')
    # the bestiary: the main pack's goes out per faction (split_factions.py), an add-on's in its own pack
    best = f'{pack}/bestiary.txt' if main else f'{pack}/hcebest.{os.path.basename(pack.rstrip("/"))}'
    print('bestiary:', bestiary_lump({c: n for n, c in ednums}, best), 'entries')
    mi = ['DoomEdNums', '{'] + [f'\t{n} = {c}' for n, c in ednums] + ['}', '', 'GameInfo', '{', f'\tAddEventHandlers = "{cfg["handler"]}"', '}', '']
    open(f'{pack}/mapinfo.txt', 'w').write('\n'.join(mi))
    json.dump(dict(ednums=ednums, spawners=spawners), open(f'{OUT}/{cfg["index"]}', 'w'), indent=1)
    print('classes', len(ednums), 'projectiles', len(done))
    # deep-fried skins: every baked skin against the texture it was baked from (skin_check.py; HCE_STRICT_SKINS=1 fails
    # the build on one)
    import skin_check
    skin_check.report_pairs(SKIN_PAIRS)
    SKIN_PAIRS.clear()

# per-character extra ZScript (Flood corpse feeding, carrier pop, infection pop)
BASE_CODE = {}       # char -> ZScript put in its abstract base class once (shared by all its variants)
TYPE_CODE = {
    'FloodInfection': template('zscript/flood_infection.zs'),
    'FloodCarrier': template('zscript/flood_carrier.zs'),
    'FloodGrunt': template('zscript/flood_grunt.zs'),      # bursts like a carrier, a smaller one: 2-4 infection forms
}

# Halo 2's beam rifle (extract_h2_jackal.py extracts it): the Sniper Jackal (build_digsite.py) and the Spec Ops Elite
# carry it. It behaves like HaloDoom's: a held beam whose damage climbs while it stays on a target, fired in ~1 s
# bursts (one trace a tic) with a cool-down between them; HDE's laser sounds; drops HDE's beam rifle.
H2BEAM = H2BEAM_REF
WEAPONS['beam rifle'] = ('HCE_H2BeamShot', 'HCE_BeamPuff', None, 30.0)
PATTERNS['beam rifle'] = (60, 75, 1, 2.4, 3.4, 0, False, 1.0, 1.0)     # 30 tics of aiming (glint + laser), then 30-45 of beam
FIRE_SOUNDS['beam rifle'] = (W + 'BeamRifle/Laser/Loop', '', W + 'BeamRifle/Laser/LoopEnd', W + 'BeamRifle/Laser/Fire', True)
FIRE_CODE['beam rifle'] = 'csr'
DROP_WEAPON['beam rifle'] = 'Halo_BeamRifle'
DROP_WEAPON['plasma caster'] = 'Halo_PlasmaCaster'
WEAPON_IDS[H2BEAM] = 'h2_beam_rifle'
WEAPON_IDS[CASTER_REF] = 'plasma_caster'      # bodies with the Caster baked in (the Draeth) show that surface
# Halo 2's beam rifle fires through the API now (HaloDoom_EnemyBase.HCE_FireBeamRifle, for anything carrying one)
BEAMRIFLE_CODE = ''


MAIN_WEAPONS = set(WEAPONS)     # the weapons whose projectile classes the main pack writes (an add-on skips them)
# the main pack's build configuration (see build(): the keys it reads). DoomEdNums start at 30200; late_chars /
# late_order are the characters and classes added since the first release, numbered after everything else
MAIN = dict(char_of_unit=CHAR_OF_UNIT, team=TEAM, ai=AI, pack=PACK, mdir='hce', tag='hce', ed0=30200, main=True,
            handler='HCE_ReplaceHandler', index='pack_index.json',
            late_chars=[c for c in dict.fromkeys(SPV3_FLOOD.values()) if c in TEAM] + (['SentinelKnight'] if 'SentinelKnight' in TEAM else [])
                       + [c for c in ('SentinelEnforcer', 'SentinelConstructor') if c in TEAM],
            late_order=['HCE_JackalMajorNeedler', 'HCE_HunterUltra'] + SPV3_FLOOD_ORDER + KNIGHT_ORDER + SENTINEL_ORDER + GALAP_ORDER)
# The override keys build() reads, here per character and in a variant's '_ov' (which wins; the add_* functions set
# them): stance (the animation stance, or {weapon: stance}); anims / anims_by_weapon ({kind: [names]}); scale (shrink
# the model); height_fixed / radius_fixed / radius (the collision box); health / shield; speed (map units a tic);
# melee (reach, damage); leap (min, max, chance, velocity); flags (the whole behaviour set) / add_flags; melee_only;
# gun (HCE_GunOffset by hand); flying; lift (a model built round its middle raised onto its feet); overlay /
# overlay_idx (an arsenal gun model on the body); pellets / spread (the shot); skin_as (share another class's skins);
# loadout_only (a Marine loadout with no class); unique (no loadouts, not in the random spawner); ally (+FRIENDLY on
# the Covenant / Sentinel side); drops False; voices; code (ZScript appended to the class); berserk_anims; weapon_toss;
# johnson / stacker (the sergeants' two-gun code); h2_pieces (a Halo 2 body's own shield flare); raven (an ODST skin)
# Cursed Halo's Hunter leap (cursed_anims.py): the spin animation, and the leap's (min, max distance, chance, speed in
# map units a tic): from 120 to 320 units away, half as eager as the Flood, a heavy spring
HUNTER_SPIN = 'stand unarmed melee-airborne'
HUNTER_LEAP = (120, 320, 0.5, 11.0)
CHAR_OVERRIDES = {    # per-character tweaks (add-on packs add their own: see build_digsite.py)
    # the XAM Flood Grunt: Halo CE's carrier AI in an Unggoy body. It runs at you, claws, and bursts when it dies,
    # letting out a few infection forms (TYPE_CODE)
    'FloodGrunt': dict(stance='unarmed', melee=(36, 18), flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Explodes']),
    # SOI's Flood Juggernaut: Halo 2's, a hulking tank form nearly twice a Hunter's height, shrunk to fit Doom's doors.
    # It charges, leaps in from 3-9 m and swats with its long arms; SOI's 500 body and 200 shield as one tough body
    'FloodJuggernaut': dict(stance='unarmed', scale=0.6, height_fixed=96, radius_fixed=36, health=700, shield=0,
                            melee=(64, 85), speed=7.0, leap=(140, 420, 0.6, 12.0),
                            flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Leaps']),
    # Ruby's Flood Elite Commander: the sword in Ruby's own sword melee and dives
    'FloodEliteCommander': dict(stance='pistol', anims={'MELEE': ['stand sword melee%0', 'stand sword melee%1'],
                                                       'DIVE_F': ['stand sword dive-front'], 'DIVE_L': ['stand sword dive-left'],
                                                       'DIVE_R': ['stand sword dive-right'], 'EVADE_L': ['stand sword evade-left'],
                                                       'EVADE_R': ['stand sword evade-right']}),
}
WEAPON_CODE = {}      # extra ZScript for every variant carrying a weapon
SPECIAL_FIRE = {}     # weapon -> chance a burst becomes the charged special shot
WEAPON_SKIN = {}      # weapon -> {weapon surface texture: replacement} (recoloured variants of one mesh)
RANDOM_WEIGHTS = {}   # class -> its weight in its character's random spawner (default 1)
SKIN_HOOK = {}        # char -> f(cls, v, si, mat, meta, skin_dir) -> skin file name (or None for the default bake)
BERSERK_ANIMS = {}    # char -> {kind: [names]} used instead of the normal table while hce_berserk is set
LOBBED = {'plasma caster'}   # weapons fired in an arc

# ---------------------------------------------------------------- the Marine arsenal
# HaloDoom Evolved's human weapons as Marine weapons, each with the Halo model the user picked (marine_arsenal.py
# builds the models: Halo CE's, Halo 2's and the Digsite prototypes', with the MA37 repainted and the grenade
# launcher kitbashed). Each Marine body gets a class per weapon; the gun is an overlay model (model 6) on the body's
# skeleton. The pistols use Halo 2's Marine pistol stance (h2_elite_anims.py, 'h2pistol'). Projectiles subclass
# HDE's own rounds (the standalone build maps them to its HCES_ ones); fire sounds and drops are HDE's.
ARSENAL_IDX = 6
H2PISTOL_STANCE = 'h2pistol'
#  weapon key: overlay model (marine_arsenal.ARSENAL), stance, combat range lo/hi and max range (WU),
#              pellets, spread (deg; None = the base variant's), drop
MARINE_ARSENAL = {
    'pistol':           ('magnum', H2PISTOL_STANCE, 2, 12, 30, None, None, 'Halo_Magnum'),
    'sidekick':         ('sidekick', H2PISTOL_STANCE, 2, 10, 25, None, None, 'Halo_Sidekick'),
    'ma37':             ('ma37', 'rifle', 3, 15, 30, None, None, 'Halo_AssaultRifle'),
    'commando':         ('commando', 'rifle', 3, 16, 32, None, None, 'Halo_Commando'),
    'battle rifle':     ('battle_rifle', 'h2br', 5, 22, 45, None, 1.0, 'Halo_BattleRifle'),
    'dmr':              ('dmr', 'rifle', 6, 26, 50, None, 0.6, 'Halo_DMR'),
    'smg':              ('smg', 'h2smg', 2, 10, 22, None, None, 'Halo_SMG'),         # H2 rifle stance, left hand on the foregrip (marine_grip.py)
    'bulldog':          ('bulldog', 'h2bulldog', 1, 6, 14, 8, 5.0, 'Halo_Bulldog'),  # H2 rifle stance, stock in the shoulder, foregrip
    'double barrel':    ('double_barrel', 'rifle', 1, 4, 10, 14, 7.0, 'Halo_DBLShotgun'),
    'sniper rifle':     ('sniper', 'rifle', 8, 35, 70, None, 0.25, 'Halo_SniperRifle'),
    'rocket launcher':  ('rocket_launcher', 'h2missile', 7, 25, 45, None, 0.5, 'Halo_RocketLauncher'),   # Halo 2's launcher stance (marine_stances.py)
    'hydra':            ('hydra', 'rifle', 6, 24, 45, None, 1.5, 'Halo_Hydra'),         # held like a rifle
    'grenade launcher': ('grenade_launcher', 'rifle', 5, 18, 30, None, 1.0, 'Halo_GrenadeLauncher'),
    'sticky detonator': ('sticky_detonator', 'h2pistol', 4, 14, 25, None, 1.0, 'Halo_StickyDetonator'),   # a pistol-sized launcher
    'gpmg':             ('gpmg', 'rifle', 3, 18, 35, None, None, 'Halo_GPMG'),
    'flamethrower':     ('flamethrower', 'support', 1, 5, 8, None, None, 'Halo_Flamethrower'),   # the cyborg's support stance (cyborg_flame_anims.py)
    # the Covenant's guns: no Marine class carries them, but any Marine can pick one up or be traded one
    # (COV_LOADOUT: loadouts only)
    'plasma pistol':    ('plasma_pistol', H2PISTOL_STANCE, 2, 12, 25, None, None, 'Halo_PlasmaPistol'),
    'fuel rod':         ('fuel_rod', 'h2missile', 6, 22, 40, None, 1.0, 'Halo_FuelRod'),
    'beam rifle':       ('beam_rifle', 'rifle', 8, 30, 60, None, 0.3, 'Halo_BeamRifle'),
    'plasma caster':    ('plasma_caster', 'rifle', 4, 14, 20, None, 1.0, 'Halo_PlasmaCaster'),
    'plasma carbine':   ('carbine', 'rifle', 6, 26, 50, None, 0.6, 'Halo_Carbine'),
    'spiker':           ('spiker', H2PISTOL_STANCE, 2, 12, 25, None, 2.0, 'Halo_Spiker'),
    'marine pulse carbine': ('pulse_carbine', 'rifle', 4, 18, 35, None, 1.0, 'Halo_PulseCarbine'),
    'needle ballista':  ('needle_ballista', 'rifle', 6, 24, 45, None, 1.0, 'Halo_NeedlerJavelin'),
}
COV_LOADOUT = {'plasma pistol', 'fuel rod', 'beam rifle', 'plasma caster', 'plasma carbine', 'spiker', 'marine pulse carbine',
               'needle ballista'}
# Halo CE's own refs where CE has the weapon (its trigger data and projectile); new ones get an hde\ ref
ARSENAL_REF = {'pistol': r'weapons\pistol\pistol', 'sniper rifle': r'weapons\sniper rifle\sniper rifle',
               'plasma pistol': r'weapons\plasma pistol\plasma pistol', 'fuel rod': r'weapons\fuel rod gun\fuel rod',
               'beam rifle': r'h2\weapons\beam rifle', 'plasma caster': r'hde\plasma caster',
               'rocket launcher': r'weapons\rocket launcher\rocket launcher', 'flamethrower': r'weapons\flamethrower\flamethrower'}
# new weapons: (pack projectile, HDE base, damage (None: HDE's own), speed WU/tick). Class names matter: the API's
# HCE_WeaponKind reads them (pistolbullet / arbullet / sniperbullet / shotgunpellet dismember, gpmg / hydra /
# stanchion / stickydet / dblshotgun gib, grenade takes limbs).
WEAPONS.update({
    'sidekick':         ('HCE_SidekickRound', 'HaloSidekick_Bullet', 18, 10.0),
    'ma37':             ('HCE_MA37Round', 'HaloRifle_Bullet', 9, 10.8),
    'commando':         ('HCE_CommandoARBullet', 'HaloCommando_Bullet', 14, 11.0),
    'battle rifle':     ('HCE_BattleRifleARBullet', 'HaloBattleRifle_Bullet', 12, 13.0),
    'dmr':              ('HCE_DMRSniperBullet', 'HaloDMR_Bullet', 24, 16.0),
    'smg':              ('HCE_SMGRound', 'HaloSMG_Bullet', 6, 10.0),
    'bulldog':          ('HCE_BulldogBuckshot', 'HaloBulldog_Bullet', 7, 4.67),
    'double barrel':    ('HCE_DBLShotgunPellet', 'HaloDBLShotgun_Bullet', 9, 4.67),
    'hydra':            ('HCE_HydraMissile', 'HydraMissile', None, 0.6),
    'grenade launcher': ('HCE_40mmGrenade', 'Halo_40MM_Proj', None, 0.5),
    'sticky detonator': ('HCE_StickyDetCharge', 'HaloStickyDetProj', None, 0.5),
    'gpmg':             ('HCE_GPMGBullet', 'HaloGPMG_Bullet', 15, 12.0),
    'stanchion':        ('HCE_StanchionRail', 'HaloSniper_Bullet', 150, 33.3),
    # Covenant guns for the Marines (the carbine and spiker are the Digsite add-on's too, same classes: built here)
    'plasma carbine':   ('HCE_CarbineRound', 'HaloCarbine_Bullet', 15, 6.0),
    'spiker':           ('HCE_SpikerSpike', 'HaloSpiker_Bullet', 10, 2.0),
    'marine pulse carbine': ('HCE_MarinePulseBolt', 'HaloPulseCarbine_Proj', 8, 1.2),   # its homing locks on the Marine's target (HCE_FireShot)
    'needle ballista':  ('HCE_BallistaNeedle', 'HaloNeedlerJavelin_Proj', None, 0.26),
})
NO_NERF_MIXIN |= {'HydraMissile', 'Halo_40MM_Proj', 'HaloStickyDetProj'}
PATTERNS.update({
    'sidekick':         (2, 4, 7, 0.9, 1.5, 0, False, 1.0, 2.0),
    'ma37':             (5, 10, 3, 0.8, 1.4, 0, True, 1.0, 2.0),
    'commando':         (3, 6, 4, 0.7, 1.3, 0, False, 1.0, 1.0),
    'battle rifle':     (3, 6, 3, 0.6, 1.1, 0, False, 1.0, 1.0),      # Halo's three-round burst, a pull or two (HCE_TriggerBurst)
    'dmr':              (1, 3, 11, 1.0, 1.6, 0, False, 1.0, 1.0),
    'smg':              (8, 14, 2, 0.8, 1.4, 0, True, 1.0, 2.0),
    'bulldog':          (2, 4, 9, 1.2, 1.8, 0, False, 1.0, 1.0),
    'double barrel':    (1, 1, 1, 1.6, 2.2, 0, False, 1.0, 1.0),
    'hydra':            (4, 4, 5, 2.8, 3.6, 0, False, 1.0, 1.0),      # a four-missile salvo
    'grenade launcher': (1, 2, 20, 2.2, 3.0, 0, False, 1.0, 1.0),
    'sticky detonator': (1, 1, 1, 2.6, 3.4, 0, False, 1.0, 1.0),
    'gpmg':             (10, 20, 3, 1.0, 1.6, 0, True, 1.0, 2.0),
    'stanchion':        (25, 25, 1, 2.8, 3.8, 0, False, 1.0, 1.0),     # 24 tics of aiming, then the rail
    'plasma carbine':   (2, 3, 9, 1.0, 1.7, 0, False, 1.0, 1.0),
    'spiker':           (5, 9, 3, 0.8, 1.4, 0, True, 1.0, 2.0),
    'marine pulse carbine': (5, 10, 3, 1.4, 2.3, 0, False, 1.0, 1.0),   # five-bolt bursts (HCE_TriggerBurst)
    'needle ballista':  (1, 1, 1, 2.4, 3.2, 0, False, 1.0, 1.0),
})
for _k, _snd in {'sidekick': 'Sidekick', 'ma37': 'Rifle', 'commando': 'Commando', 'battle rifle': 'BattleRifle', 'dmr': 'DMR',
                 'smg': 'SMG', 'bulldog': 'Bulldog', 'double barrel': 'SuperShotgun', 'hydra': 'Hydra',
                 'sticky detonator': 'StickyDet', 'gpmg': 'GPMG', 'stanchion': 'Stanchion'}.items():
    FIRE_SOUNDS[_k] = (W + _snd + '/Fire', W + _snd + '/Fire/Bass' if _k not in ('hydra', 'sticky detonator') else '', '', '', False)
FIRE_SOUNDS['grenade launcher'] = (W + 'GrenadeLauncher/Fire', '', '', '', False)
FIRE_SOUNDS['plasma carbine'] = (W + 'Carbine/Fire', W + 'Carbine/Fire/Bass', '', '', False)
FIRE_SOUNDS['spiker'] = (W + 'Spiker/Fire', W + 'Spiker/Fire/Bass', '', '', False)
FIRE_SOUNDS['marine pulse carbine'] = (W + 'PulseCarbine/Fire', W + 'PulseCarbine/Fire/Bass', '', '', False)
FIRE_SOUNDS['needle ballista'] = (W + 'NeedlerJavelin/Fire', '', '', '', False)
FIRE_CODE.update({'plasma carbine': 'cr', 'spiker': 'sk', 'marine pulse carbine': 'cr', 'needle ballista': 'ne'})
FIRE_SOUNDS['stanchion'] = (W + 'Stanchion/Fire', W + 'Stanchion/Fire/Bass', '', W + 'Stanchion/Charge/PreFire', False)
LOBBED.add('grenade launcher')
DROP_WEAPON.update({k: d[7] for k, d in MARINE_ARSENAL.items() if k not in DROP_WEAPON})
DROP_WEAPON['stanchion'] = 'Halo_Stanchion'

STICKY_CODE = template('zscript/sticky.zs')
WEAPON_CODE['sticky detonator'] = STICKY_CODE

STANCHION_CODE = template('zscript/stanchion.zs')
WEAPON_CODE['stanchion'] = STANCHION_CODE

STACKER_CODE = """
	// Sergeant Stacker: always his own face (the white face under the sergeant's cap) and voice
	override int HCE_PickFace() { return HCE_STACKER_FACE; }
"""

# Corpsman (new): a Marine with the Sidekick who answers the "medic" order (HCE_MedicOrder): he runs to the Marine
# the player has in the crosshair, crouches beside him and patches him up. A Navy corpsman's rank (HM3)
MEDIC_CODE = """
	// the squad's corpsman: answers "medic" (HCE_SpawnAllHandler.SquadOrder -> HCE_MedicOrder)
	override void PostBeginPlay()
	{
		hce_isMedic = true;
		super.PostBeginPlay();
	}
"""


MEDIC_GUNS = ('assault rifle', 'shotgun', 'ma37', 'smg', 'magnum')     # the other corpsmen's guns (HCE_MarineMedic<Gun>)


def add_marine_arsenal(variants):
    """The Marine arsenal classes: for each Marine body and each MARINE_ARSENAL gun a copy of the body's assault-rifle
    variant with the gun's ranges, overlay model and stance (the Covenant guns as loadouts only), then Sergeant Johnson,
    Sergeant Stacker and the corpsmen. To add a Marine gun: a row in MARINE_ARSENAL, its WEAPONS / PATTERNS /
    FIRE_SOUNDS entries below, and marine_arsenal.py's overlay model"""
    import copy
    for body in ('marine', 'marine_armored'):
        base = variants.get(f'characters\\{body}\\{body} assault rifle')
        if not base: continue
        for key, (ovl, stance, lo, hi, mx, pellets, spread, _drop) in MARINE_ARSENAL.items():
            vn = f'characters\\{body}\\{body} {ovl.replace("_", " ")}'      # class named after the gun (HCE_MarineMagnum)
            if vn in variants: continue
            v = copy.deepcopy(base)
            v['ranged_combat']['reference'] = ARSENAL_REF.get(key, 'hde\\' + key)
            v['ranged_combat'].update(combat_range_lower_bound=lo, combat_range_upper_bound=hi, maximum_firing_range=mx)
            v['_late'] = True
            v['_ov'] = dict(overlay=ovl, stance=stance, pellets=pellets, spread=spread, skin_as=cname(f'{body} assault rifle'),
                            loadout_only=key in COV_LOADOUT)
            variants[vn] = v
    # Sergeant Johnson: his own face and voice, the Stanchion, and the Magnum for close quarters (with a harder punch)
    base = variants.get('characters\\marine\\marine assault rifle')
    if base and 'characters\\marine\\sgt johnson' not in variants:
        v = copy.deepcopy(base)
        v['ranged_combat']['reference'] = 'hde\\stanchion'
        v['ranged_combat'].update(combat_range_lower_bound=6, combat_range_upper_bound=30, maximum_firing_range=70)
        v['_late'] = True
        v['_ov'] = dict(overlay='stanchion', stance='rifle', spread=0.2, unique=True, johnson=True, melee=(40, 90), health=75, skin_as='HCE_MarineAssaultRifle')
        variants['characters\\marine\\sgt johnson'] = v
    # Sergeant Stacker: the white sergeant (Halo CE's second sergeant's voice, 'sarge2', merged with Halo 2's gruff
    # sergeant, the same actor),
    # the sergeant's cap, full sleeves and the Battle Rifle he carries in Halo 2
    if base and 'characters\\marine\\sgt stacker' not in variants:
        v = copy.deepcopy(base)
        ovl, stance, lo, hi, mx, pellets, spread, _drop = MARINE_ARSENAL['double barrel']
        v['ranged_combat']['reference'] = ARSENAL_REF.get('double barrel', 'hde\\double barrel')
        v['ranged_combat'].update(combat_range_lower_bound=lo, combat_range_upper_bound=hi, maximum_firing_range=mx)
        v['_late'] = True
        v['_ov'] = dict(overlay=ovl, stance=stance, pellets=pellets, spread=spread, unique=True, melee=(40, 75), health=60,
                        skin_as='HCE_MarineAssaultRifle', code=STACKER_CODE, stacker=True)
        variants['characters\\marine\\sgt stacker'] = v
    # the corpsman: the Sidekick Marine's kit, in the random pool
    sk = variants.get('characters\\marine\\marine sidekick')
    if sk and 'characters\\marine\\marine medic' not in variants:
        v = copy.deepcopy(sk)
        v['_ov'] = dict(v['_ov'], code=MEDIC_CODE)
        variants['characters\\marine\\marine medic'] = v
    # more corpsmen, each with another gun (HCE_MarineMedic<Gun>): the CE assault rifle and shotgun, the MA37, the SMG
    # and the Magnum
    for gun in MEDIC_GUNS:
        src = variants.get(f'characters\\marine\\marine {gun}')
        vn = f'characters\\marine\\marine medic {gun}'
        if not src or vn in variants: continue
        v = copy.deepcopy(src)
        ov = dict(v.get('_ov') or {}, code=MEDIC_CODE)
        if 'skin_as' not in ov: ov['skin_as'] = cname(f'marine {gun}')
        v['_ov'] = ov; v['_late'] = True
        variants[vn] = v

add_marine_arsenal(AI['variants'])

# Pilots (new): Halo 2's Pelican crews, Marines in the flight helmet with its smoked visor over one of Halo 2's faces
# (extract_h2_pilot.py: a whole head from the kit, the CE head hidden), nothing else of the kit but a sidearm or an
# SMG; lighter on their feet than a rifleman and a little less tough (no armour)
PILOT_FACES = ('smith', 'banks', 'dion', 'morgan', 'perez', 'walter')     # Halo 2's faces (h2_pilot_<face>.iqm), one rolled per pilot
PILOT_GUNS = {'magnum': 'marine magnum', 'smg': 'marine smg'}            # pilot gun -> the Marine variant it copies
PILOT_CODE = """
	// a pilot (extract_h2_pilot.py): Halo 2's flight helmet over one of its faces, and none of the field kit
	override void HCE_KitOverride()
	{
		static const String F[] = { %s };
		for(int i = 0; i < hce_kit.Size(); i++) hce_kit[i] = "";
		hce_kit[0] = "h2_pilot_" .. F[random[HCEKit](0, F.Size() - 1)];
	}
""" % ', '.join(f'"{f}"' for f in PILOT_FACES)
# The radio operator (new): a Marine with the radio pack on his back. Once a fight is on (an enemy in sight) he
# calls it in; some seconds later a fire team of three Marines comes up from behind him, out of the enemy's sight,
# and joins in (Marines are allies: they fall in with the squad like any other). Once per operator.
RADIO_TEAM = ('HCE_MarineAssaultRifle', 'HCE_MarineAssaultRifle', 'HCE_MarineBattleRifle', 'HCE_MarineShotgun',
              'HCE_MarineSmg', 'HCE_MarineArmoredAssaultRifle', 'HCE_MarineMa37')
RADIO_CODE = """
	// the radio operator: the radio pack always, and one call for a fire team per fight
	override void HCE_KitOverride()
	{
		hce_kit[3] = "radio_pack";
		hce_kit[2] = "";
	}
	bool hce_radioCalled;
	int hce_radioTics;
	override void Tick()
	{
		super.Tick();
		if(health <= 0 || IsFrozen()) return;
		if(!hce_radioCalled && target && target.health > 0 && hce_canSee && !target.bFRIENDLY)
		{
			hce_radioCalled = true;
			hce_radioTics = random[HCERadio](35 * 4, 35 * 7);
			HCE_Say('JoinMe', 1.0, 70, true);
		}
		if(hce_radioTics > 0 && --hce_radioTics == 0) HCE_RadioTeam();
	}
	void HCE_RadioTeam()
	{
		static const Name T[] = { %s };
		double away = target ? AngleTo(target) + 180 : angle + 180;
		int n = 0;
		for(int tries = 0; tries < 40 && n < 3; tries++)
		{
			double a = away + frandom[HCERadio](-70, 70);
			double r = tries < 28 ? frandom[HCERadio](192, 448) : frandom[HCERadio](64, 160);
			vector3 p = (pos.xy + AngleToVector(a, r), 0);
			p.z = GetZAt(p.x, p.y, 0, GZF_ABSOLUTEPOS);
			if(abs(p.z - pos.z) > 96 || !level.IsPointInLevel(p)) continue;
			class<Actor> c = (class<Actor>)(T[random[HCERadio](0, T.Size() - 1)]);
			if(!c) continue;
			let m = Actor.Spawn(c, p);
			if(!m) continue;
			if(!m.TestMobjLocation() || (tries < 28 && target && target.CheckSight(m)) || !m.CheckSight(self))
			{
				m.ClearCounters(); m.Destroy(); continue;
			}
			m.ClearCounters();
			m.bFRIENDLY = bFRIENDLY;
			m.angle = m.AngleTo(self);
			if(target) m.target = target;
			n++;
			let h = HaloDoom_EnemyBase(m);
			if(h && n == 1) h.HCE_Say('Acknowledge', 1.0, 70, true);
		}
	}
""" % ', '.join(f"'{c}'" for c in RADIO_TEAM)

def add_pilots_and_radio(variants):
    """The Pilots (PILOT_GUNS: the Magnum and SMG Marines at 85% health, in Halo 2's flight helmet: PILOT_CODE) and
    the radio operator (the assault-rifle Marine with RADIO_CODE: the radio pack and the fire team he calls in)"""
    import copy
    for gun, src in PILOT_GUNS.items():
        vn = f'characters\\marine\\marine pilot {gun}'
        sv = variants.get('characters\\marine\\' + src)
        if not sv or vn in variants: continue
        v = copy.deepcopy(sv)
        v['unit']['maximum_body_vitality'] = v['unit']['maximum_body_vitality'] * 0.85
        v['_late'] = True
        v['_ov'] = dict(v.get('_ov') or {}, code=PILOT_CODE)
        variants[vn] = v
    sv = variants.get('characters\\marine\\marine assault rifle')
    vn = 'characters\\marine\\marine radio operator'
    if sv and vn not in variants:
        v = copy.deepcopy(sv)
        v['_late'] = True
        v['_ov'] = dict(v.get('_ov') or {}, code=RADIO_CODE, skin_as='HCE_MarineAssaultRifle')
        variants[vn] = v

add_pilots_and_radio(AI['variants'])

# ODSTs (new): Spiral's Halo CE ODST (extract_odst.py: its own model on the Marine's skeleton and animations) with the
# a50 ODSTs' loadouts -- the assault rifle (a Private and a Major) and the shotgun -- and Fire Team Raven, Connor Dawn's four
# ODSTs in their own colours from a10: green with the shotgun, orange with the battle rifle, blue with the assault
# rifle and purple with the sniper rifle. They fight as Armored Marines do (the same combat data and collision,
# so the same toughness) and wear their textures as they are: no colour change.
ODST_UNIT = r'characters\marine_odst\odst'
ODST = {  # pack variant -> (Armored Marine variant it copies, Fire Team Raven colour or None)
    'marine odst assault rifle':       ('marine_armored assault rifle', None),
    'marine odst assault rifle major': ('marine_armored assault rifle major', None),
    'marine odst shotgun':             ('marine_armored shotgun major', None),
    'marine odst ma37':                ('marine_armored ma37', None),          # Shigure's MA37
    'marine odst raven green':         ('marine_armored shotgun major', 'green'),
    'marine odst raven orange':        ('marine_armored battle rifle', 'orange'),
    'marine odst raven blue':          ('marine_armored assault rifle', 'blue'),
    'marine odst raven purple':        ('marine_armored sniper', 'purple'),
    # the double barrel is Fire Team Raven's and Stacker's alone (RANDOM_EXCLUDE): each of Raven with it, in their own
    # skins (add_odsts: skin_as the colour's own class)
    'marine odst raven blue double barrel':   ('marine_armored double barrel', 'blue'),
    'marine odst raven green double barrel':  ('marine_armored double barrel', 'green'),
    'marine odst raven orange double barrel': ('marine_armored double barrel', 'orange'),
    'marine odst raven purple double barrel': ('marine_armored double barrel', 'purple'),
    # Halo 2's ODSTs: their own body (extract_h2_odst.py: the Halo 2 Marine's ODST body and head on the CE skeleton)
    # worn in place of all of Spiral's
    'marine odst halo2':               ('marine_armored assault rifle', None, 'h2_odst_body'),
    'marine odst halo2 shotgun':       ('marine_armored shotgun major', None, 'h2_odst_body'),
    'marine odst halo2 battle rifle':  ('marine_armored battle rifle', None, 'h2_odst_body'),
    'marine odst halo2 ma37':          ('marine_armored ma37', None, 'h2_odst_body'),
    # Elefant's two closed kit helmets on Spiral's body in place of its own helmet (odst_helmet_code)
    'marine odst closed helmet':       ('marine_armored battle rifle', None, 'helmet_closed', 'silver'),
    'marine odst enclosed helmet':     ('marine_armored shotgun major', None, 'helmet_enclosed'),
    # the Hellbringer: an ODST flame trooper in Halo Wars 2's flamethrower helmet (Elefant's kit), with the fuel tank
    # on his back (ODST_EXTRAS)
    'marine odst hellbringer':         ('marine_armored flamethrower', None, 'helmet_hellbringer', 'red'),
    # the Rocketeer (the enclosed helmet, the launcher's spare-rocket tube on his back) and the Sniper (the closed
    # helmet, silver visor), on Spiral's body
    'marine odst rocketeer':           ('marine_armored rocket launcher', None, 'helmet_enclosed'),
    'marine odst sniper':              ('marine_armored sniper', None, 'helmet_closed', 'silver'),
}
# Fire Team Raven by name: colour -> (the name over them, voice set or None for the usual random Marine voice). Their
# a10 colours: blue (Raven Actual), orange (called red), green, purple. Lang speaks with Halo 2's female Marine voice
# (marine_tough: extract_marine_voices.py's Marine_Tough)
RAVEN_NAMES = {'blue':   ('SSGT. Ethan A. Graves', None),
               'orange': ('SGT. Marcus B. Hudson', None),
               'green':  ('CPL. Victor C. Ramos', None),
               'purple': ('CPL. Ava D. Lang', 'Marine_Tough')}
def raven_code(colour):
    """ZScript giving a Fire Team Raven member his (or her) own name in place of a rolled one"""
    name = RAVEN_NAMES[colour][0]
    return (f'\t// Fire Team Raven: {name}\n'
            f'\toverride void HCE_RollName() {{ hce_rankName = "{name}"; }}\n')
ODST_HELMET_SURFS = (1, 2)        # Spiral's ODST: its helmet and visor surfaces (MarineODST.iqm meshes head_1, head_2)
ODST_ALL_SURFS = (0, 1, 2, 3, 4)  # all of it (arms, head_1, head_2, legs_3, legs_4): hidden under a whole body
ODST_BODIES = {'h2_odst_body'}    # kit pieces that are a whole body, not a helmet
# more kit pieces on an ODST variant (model attachments 2, 3...) and which of Spiral's surfaces its helmet hides
ODST_EXTRAS = {'marine odst hellbringer': (('flamer_tank', 'gas_mask'), None),
               'marine odst rocketeer': (('launcher_tube',), None)}   # the helmet's own amber lens in place of Spiral's helmet and visor
# the Halo 2 ODSTs fight in Halo 2's rifle set, re-posed per gun (marine_h2_grips.py); the battle rifle keeps 'h2br'
ODST_BODY_STANCE = {'assault rifle': 'h2ar', 'shotgun': 'h2shotgun', None: 'h2ar'}
KIT_VISOR_SURF = 1                # the visor is surface 1 of each enclosed kit helmet
# other visor colours (odst_helmet_code): the orange visor texture's shading, recoloured; same shader and cube map
KIT_VISOR_TINTS = {'silver': 'mk_visor_silver.png', 'h2odst': 'mk_h2_odst_visor.png', 'red': 'mk_hellbringer_visor_red.png'}
# tints shaded from another visor texture than the enclosed helmets' (the Hellbringer's lens has its own UVs)
KIT_VISOR_TINT_SRC = {'red': 'mk_hellbringer_visor.png'}
# h2odst: Halo 2's ODST visor, a dark bluish purple (extract_h2_odst.py puts it on the Halo 2 ODST's visor)
KIT_VISOR_COLOURS = {'silver': (0.80, 0.83, 0.88), 'h2odst': (0.16, 0.15, 0.40), 'red': (0.85, 0.10, 0.07)}   # red: the Hellbringer ODSTs

def odst_helmet_code(piece, mdir='hce', visor=None, extras=(), surfs=None):
    """ZScript for an ODST wearing a Marine kit piece in place of its own helmet (or, for ODST_BODIES, its whole
    body): Spiral's surfaces surfs (default: the helmet's, or all of them) hidden on the body and its blood overlay,
    the piece attached as model 1, extras as models 2.., the visor (KIT_VISOR_TINTS) recoloured"""
    hid = f'"models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN'
    surfs = surfs or (ODST_ALL_SURFS if piece in ODST_BODIES else ODST_HELMET_SURFS)
    hide = ''.join(f"\t\tA_ChangeModel('None', {{idx}}, \"\", 'None', {k}, {hid});\n" for k in surfs)
    tint = (f'\t\tA_ChangeModel(\'None\', 1, "", \'None\', {KIT_VISOR_SURF}, "models/{mdir}/MarineKit", '
            f'\'{KIT_VISOR_TINTS[visor]}\', CMDL_USESURFACESKIN);\n') if visor else ''
    what = ('a whole body in place of Spiral\'s ODST' if piece in ODST_BODIES else
            'another sealed helmet in place of the ODST\'s own')
    return (f'\t// {what}: {piece} (a Marine kit piece on the Marine\'s skeleton)'
            + (f', {visor} visor' if visor else '') + '\n'
            '\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n'
            + hide.replace('{idx}', '0') +
            f'\t\tA_ChangeModel(\'None\', 1, "models/{mdir}/MarineKit", "{piece}.iqm", 1, "", \'None\');\n'
            + ''.join(f'\t\tA_ChangeModel(\'None\', {2 + k}, "models/{mdir}/MarineKit", "{x}.iqm", 1, "", \'None\');\n' for k, x in enumerate(extras))
            + tint +
            '\t\tHCE_ResumeAnim();\n\t}\n'
            '\toverride void HCE_BloodHideClass()\n\t{\n' + hide.replace('{idx}', str(BLOOD_IDX)) + '\t}\n')
def add_odsts(ai):
    """The ODST variants from ODST (pack variant -> (the Armored Marine variant it copies, Raven colour, kit helmet or
    body, visor tint)) on the MarineODST body (the Armored Marine's biped, no colour change). Skipped without
    extract_odst.py's model. To add an ODST, add a row to ODST (and ODST_EXTRAS for more kit on it)"""
    import copy
    if not os.path.exists(f'{OUT}/models/MarineODST/MarineODST.json'): return
    b = copy.deepcopy(ai['bipeds'].get(r'characters\marine_armored\marine_armored'))
    if not b: return
    b['change_colors_list'] = []
    ai['bipeds'][ODST_UNIT] = b
    minor = ai['variants'].get(r'characters\marine_armored\marine_armored assault rifle', {}).get('actor_reference')
    for vn, spec in ODST.items():
        src, raven = spec[0], spec[1]
        helmet = spec[2] if len(spec) > 2 else None
        visor = spec[3] if len(spec) > 3 else None
        base = ai['variants'].get('characters\\marine_armored\\' + src)
        key = 'characters\\marine_odst\\' + vn
        if not base or key in ai['variants']: continue
        v = copy.deepcopy(base)
        v['unit_reference'] = ODST_UNIT
        if vn == 'marine odst shotgun' and minor: v['actor_reference'] = minor      # a Private, as a50's shotgun ODST
        v['change_colors'] = None; v['change_colors_list'] = []
        v['_late'] = True
        ov = dict(v.get('_ov') or {})
        own = 'characters\\marine_odst\\marine odst raven ' + raven if raven else None
        ov['skin_as'] = (cname(own) if raven and own != key and own[len('characters\\marine_odst\\'):] in ODST else
                         cname(key) if raven else 'HCE_MarineOdstAssaultRifle')    # (a Raven member's other gun: his own skins)
        if raven:
            ov['raven'] = raven
            ov['code'] = ov.get('code', '') + raven_code(raven)
            if RAVEN_NAMES[raven][1]: ov['voices'] = RAVEN_NAMES[raven][1]
        ex, sf = ODST_EXTRAS.get(vn, ((), None))
        if helmet: ov['code'] = ov.get('code', '') + odst_helmet_code(helmet, visor=visor, extras=ex, surfs=sf)
        if helmet in ODST_BODIES and ov.get('stance') in (None, '', 'rifle'): ov['stance'] = dict(ODST_BODY_STANCE)   # (an arsenal gun's CE rifle stance too)
        v['_ov'] = ov
        ai['variants'][key] = v

add_odsts(AI)

def odst_skin(cls, v, si, mat, meta, skin_dir):
    """Fire Team Raven's own textures (extract_odst.py), copied as they are"""
    raven = (v.get('_ov') or {}).get('raven')
    fn = (meta.get('raven') or {}).get(raven, {}).get(mat) if raven else None
    if not fn: return None
    os.makedirs(skin_dir, exist_ok=True)
    if not os.path.exists(f'{skin_dir}/{fn.lower()}'): shutil.copy(f'{OUT}/models/MarineODST/{fn}', f'{skin_dir}/{fn.lower()}')
    return fn.lower()
SKIN_HOOK['MarineODST'] = odst_skin

# ---------------------------------------------------------------- the Sentinel Knights
# their skins (extract_sentinel_knight.py baked them per rank), the arm gun the variant carries (the other three hidden),
# brightmaps for their lights, and their core: the energy shader (templates/shaders/core.fp: plasma bands, a pulse, a hot
# rim, the room in its shell from the visor's cube map), its colour rolled at spawn from the rank's palette (BASE_CODE)
EXTRA_GL = []          # GLDEFS entries the skin hooks add (written with the rest)
CORE_SHADER = template('shaders/core.fp')
DEREZ_SHADER = template('shaders/derez.fp')      # Halo 4's Promethean derez, recreated: the dying Knight burns away


def modeldef_skins(md):
    """every skin a MODELDEF text puts on a model (Path + SurfaceSkin / Skin), as 'path/file' names"""
    out, path = set(), None
    for line in md.split('\n'):
        m = re.match(r'\s*Path "(.*)"', line)
        if m: path = m.group(1); continue
        m = re.match(r'\s*(?:SurfaceSkin \d+ \d+|Skin \d+) "(.*\.(?:png|jpg))"', line, re.I)
        if m and path: out.add(f'{path}/{m.group(1)}')
    return out


def shader_gl(pack, mdir, bubbles):
    """GLDEFS for the ported Halo shield shaders on this pack's skins, with their shaders and textures written into it:
    the shield flares (SHELL_TEX: shaders/hce_plasma.fp, Halo CE's shield plasma), the Sentinels' bubbles (bubbles:
    hce_plasma_h2.fp, Halo 2's plasma_shield) and the shield fields (FIELD_TEX: hce_jshield.fp, Halo CE's Jackal shield
    over the Jackal's or the Enforcer's maps). The maps go to models/<mdir>/hce_fx/"""
    pre = f'models/{mdir}/'
    shells = sorted(t for t in SHELL_TEX if t.startswith(pre) and os.path.exists(f'{pack}/{t}'))
    fields = sorted((t, k) for t, k in FIELD_TEX.items() if t.startswith(pre) and os.path.exists(f'{pack}/{t}'))   # (maps prefix, layers)
    bubbles = sorted(set(bubbles))
    if not (shells or fields or bubbles): return []
    fx = f'{pack}/{pre}hce_fx'; os.makedirs(fx, exist_ok=True); os.makedirs(f'{pack}/shaders', exist_ok=True)
    for f in os.listdir(SHADER_MAPS):
        if f.endswith('.png'): shutil.copy(f'{SHADER_MAPS}/{f}', f'{fx}/{f}')
    full = f'{pre}brightmap_full.png'
    out = []
    if shells or bubbles:
        open(f'{pack}/shaders/hce_plasma.fp', 'w').write(PLASMA_SHADER)
        open(f'{pack}/shaders/hce_plasma_h2.fp', 'w').write(PLASMA_H2_SHADER)
    for t in shells:
        out.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_plasma.fp"\n\tspeed 1.0\n\tbrightmap "{full}"\n'
                   f'\ttexture pl_noise "{pre}hce_fx/plasma_noise.png"\n}}')
    for t in bubbles:
        out.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_plasma_h2.fp"\n\tspeed 1.0\n\tbrightmap "{full}"\n'
                   f'\ttexture pl_noise "{pre}hce_fx/plasma_noise.png"\n}}')
    if fields:
        open(f'{pack}/shaders/hce_jshield.fp', 'w').write(JSHIELD_SHADER)
    for t, (k, layers, own) in fields:
        out.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_jshield.fp"\n\tspeed 1.0\n\tbrightmap "{full}"\n'
                   + (f'\tdefine "JS_LAYERS" = "{layers}"\n' if layers > 1 else '') +
                   f'\ttexture js_noise "{pre}hce_fx/{k}_noise.png"\n\ttexture js_offset "{pre}hce_fx/{k}_offset.png"\n'
                   f'\ttexture js_mask "{own or f"{pre}hce_fx/{k}_mask.png"}"\n}}')
    return out

def derez_materials(gl, skins, black):
    """GLDEFS text gl with the derez shader (shaders/hce_derez.fp: a Forerunner weapon's kill, a Knight's death) on
    every skin in skins that has no shader of its own: its brightmap entry becomes the material's brightmap, the rest
    get black (a brightmap path: the shader reads one either way). Gib pieces and the hidden skin are left out (gibs
    fade on their own; hce_hidden draws nothing)"""
    shaded = set(t.lower() for t in re.findall(r'(?:material|HardwareShader) [Tt]exture "([^"]+)"', gl))
    bm = {t.lower(): b for t, b in re.findall(r'brightmap texture "([^"]+)"\n\{\n\tmap "([^"]+)"\n\}', gl)}
    todo = sorted(t for t in skins if t.lower() not in shaded and t.lower().endswith(('.png', '.jpg'))
                  and not t.endswith('hce_hidden.png') and '_gib_' not in t)
    done = set(t.lower() for t in todo)
    gl = re.sub(r'brightmap texture "([^"]+)"\n\{\n\tmap "[^"]+"\n\}\n?', lambda m: '' if m.group(1).lower() in done else m.group(0), gl)
    add = [f'material texture "{t}"\n{{\n\tshader "shaders/hce_derez.fp"\n\tbrightmap "{bm.get(t.lower(), black)}"\n}}' for t in todo]
    return gl.rstrip('\n') + '\n' + '\n'.join(add) + '\n', set(bm.get(t.lower(), black) for t in todo)
KNIGHT_CORE_PALETTE = {'minor': 0, 'major': 0, 'commander': 1}     # 0 cold, 1 warm (HCE_KnightPalette)


def knight_skin(cls, v, si, mat, meta, skin_dir):
    """SKIN_HOOK for the Sentinel Knights: surface si's skin file. The arm guns: the variant's own (_knight_gun) in its
    rank's texture, the other three hidden; the core: the rank's palette of core textures with the core shader (an
    EXTRA_GL material each); the rest: extract_sentinel_knight.py's per-rank bake, with its brightmap in EXTRA_GL"""
    src = f'{OUT}/models/SentinelKnight'
    name = meta['mesh_names'][si]; rank = v.get('_rank', 'minor')
    os.makedirs(skin_dir, exist_ok=True)
    rel = skin_dir[skin_dir.index('models/'):]
    def ship(fn):
        """copy texture fn (and its _bm brightmap, if any) into the skins folder; returns the brightmap's name or None"""
        if not os.path.exists(f'{skin_dir}/{fn}'): shutil.copy(f'{src}/{fn}', f'{skin_dir}/{fn}')
        bm = fn[:-4] + '_bm.png'
        if os.path.exists(f'{src}/{bm}'):
            if not os.path.exists(f'{skin_dir}/{bm}'): shutil.copy(f'{src}/{bm}', f'{skin_dir}/{bm}')
            return bm
        return None
    if name.startswith('gun_'):
        if name != f'gun_{v.get("_knight_gun")}':
            hid = f'{skin_dir}/hce_hidden.png'
            if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
            return 'hce_hidden.png'
        fn = f'w_sk_{name[4:]}_0_{rank}.png'
    elif name == 'Core':
        pal = meta['cores']['warm' if KNIGHT_CORE_PALETTE.get(rank) else 'cold']
        cube = f'{skin_dir}/core_cube.png'
        if not os.path.exists(cube): shutil.copy(f'{MARINE_KIT}/{KIT_VISOR_CUBE}', cube)
        pack = skin_dir[:skin_dir.index('/models/')]
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_core.fp', 'w').write(CORE_SHADER)
        for c in pal:
            bm = ship(f'core_{c}.png')
            e = (f'material texture "{rel}/core_{c}.png"\n{{\n\tshader "shaders/hce_core.fp"\n\tbrightmap "{rel}/{bm}"\n'
                 f'\ttexture tex_cube "{rel}/core_cube.png"\n}}')
            if e not in EXTRA_GL: EXTRA_GL.append(e)
        return f'core_{pal[0]}.png'
    else:
        fn = f'{name}_{rank}.png'
    bm = ship(fn)
    # the derez shader (templates/shaders/derez.fp) on every body and gun skin, with its brightmap (or a black one:
    # the shader reads the brightmap either way)
    pack = skin_dir[:skin_dir.index('/models/')]
    os.makedirs(f'{pack}/shaders', exist_ok=True)
    open(f'{pack}/shaders/hce_derez.fp', 'w').write(DEREZ_SHADER)
    if not bm:
        bm = 'brightmap_none.png'
        if not os.path.exists(f'{skin_dir}/{bm}'): Image.new('RGB', (8, 8), (0, 0, 0)).save(f'{skin_dir}/{bm}')
    e = f'material texture "{rel}/{fn}"\n{{\n\tshader "shaders/hce_derez.fp"\n\tbrightmap "{rel}/{bm}"\n}}'
    if e not in EXTRA_GL: EXTRA_GL.append(e)
    return fn


def knight_code(meta, mdir):
    """the Knights' shared ZScript (templates/zscript/sentinel_knight.zs) with their core surface, skin folder and the
    phase animations' lengths filled in"""
    tics = lambda n: max(1, int(round(meta['anims'][n]['frames'] / TICK)))
    return (template('zscript/sentinel_knight.zs').replace('{CORE}', str(meta['mesh_names'].index('Core')))
            .replace('{SKINS}', f'models/{mdir}/SentinelKnight/skins')
            .replace('{OUT_TICS}', str(tics('knight phase-out'))).replace('{IN_TICS}', str(tics('knight phase-in'))))


if os.path.exists(KNIGHT_JSON):
    SKIN_HOOK['SentinelKnight'] = knight_skin
    BASE_CODE['SentinelKnight'] = knight_code(json.load(open(KNIGHT_JSON)), 'hce')
    NO_BLOOD.add('SentinelKnight')
    VOICES['SentinelKnight'] = 'SentinelKnight'          # REV's lines (split_factions.knight_voice, the Knight's HCE_Say)
    SHELL_TINT['SentinelKnight'] = (0.55, 0.85, 1.00)
    CHAR_OVERRIDES['SentinelKnight'] = dict(stance='pistol', height_fixed=84, radius_fixed=30, melee=(110, 45), speed=7.0,
                                            flags=['HCE_Surprise', 'HCE_Evades', 'HCE_Berserks'])

# ---------------------------------------------------------------- Halo 2's Sentinels
# the Aggressor's body in its rank's change colour with the Elites' cube reflection on its metal (minor: steel blue under
# the silver cube, captain: gold under the gold); its shield bubble (the shielded ranks only) and the Enforcer's shields
# are see-through hex lattices in the shield colour (hex_lattice), fully lit, as are the Enforcer's hover jets and eye
SENTINEL_CC = {'sentinel_minor': 'minor', 'sentinel_captain': 'captain'}     # rank key -> the biped's change-colour name (the skin's colour)
SENTINEL_LOOK = {'sentinel_captain': (0.7, 0.35)}     # rank: (how much of its colour, how much reflection): the gold glared
ENFORCER_SHIELD_HP = 260      # each of the Enforcer's two front shields (sentinel_enforcer.zs {SHP})


def full_bright(skin_dir, fn):
    """add a GLDEFS brightmap making skin fn (in skin_dir) fully lit (EXTRA_GL), writing the white brightmap if needed"""
    rel = skin_dir[skin_dir.index('models/'):]
    mdir = rel.split('/')[1]
    e = f'brightmap texture "{rel}/{fn}"\n{{\n\tmap "models/{mdir}/brightmap_full.png"\n}}'
    if e not in EXTRA_GL: EXTRA_GL.append(e)
    pack = skin_dir[:skin_dir.index('/models/')]
    bf = f'{pack}/models/{mdir}/brightmap_full.png'
    if not os.path.exists(bf): os.makedirs(os.path.dirname(bf), exist_ok=True); Image.new('RGB', (8, 8), (255, 255, 255)).save(bf)


def hex_lattice(tint, path, n=128, cells=4, width=0.09):
    """an energy shield we can see through: a hex lattice in the shield's colour, its cells cut out (UZDoom alpha-tests
    model skins; a surface can't be blended on its own), the edges brighter where the noise of Halo's shield map runs"""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / n * cells
    # hex grid: distance to the nearest cell centre against the second nearest gives the edges
    pts = []
    for i in range(-1, cells + 2):
        for j in range(-1, cells * 2 + 2):
            pts.append((i + (0.5 if j % 2 else 0.0), j * 0.866))          # rows of a hex grid, every other one offset
    pts = np.array(pts, np.float32)
    d = np.sqrt((x[..., None] - pts[:, 0]) ** 2 + (y[..., None] - pts[:, 1]) ** 2)
    d.sort(axis=2)
    edge = (d[..., 1] - d[..., 0]) < width
    col = np.array(tint, np.float32)
    rgb = np.clip(col * 0.85 + 0.25, 0, 1) * np.ones((n, n, 3), np.float32)
    a = np.where(edge, 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([(rgb * 255).astype(np.uint8), a]), 'RGBA').save(path)


def copy_skin(char, mat, skin_dir):
    """a SKIN_HOOK helper: the character's texture mat copied into the skins folder as it is; returns its file name"""
    os.makedirs(skin_dir, exist_ok=True)
    fn = mat.lower()
    if not os.path.exists(f'{skin_dir}/{fn}'): shutil.copy(f'{OUT}/models/{char}/{mat}', f'{skin_dir}/{fn}')
    return fn


BUBBLE_CHARS = set()          # Sentinel bodies with a shield bubble surface: their shield flare is the bubble


_MUZZLE_CACHE = {}     # gun_anchor's results per (char, stance, gun): the models are posed once per build
_IQM_CACHE = {}        # path -> read_iqm's (joints, meshes, anims)

def _iqm(path):
    """read_iqm, cached per path"""
    from iqm import read_iqm
    if path not in _IQM_CACHE: _IQM_CACHE[path] = read_iqm(path)
    return _IQM_CACHE[path]

def _posed_world(joints, pose):
    """every joint's world transform (translation, rotation) in a pose (a frame's local transforms), or the bind pose"""
    import preview as pv
    return pv.world([j[1] for j in joints], pose if pose is not None else [(j[2], j[3]) for j in joints])

def _poses(anims, anim):
    """the first, middle and last frames of an animation as poses (the bind pose, as [None], for no animation)"""
    fr = anims.get(anim) if anim else None
    return [[(t, q) for (t, q, s) in fr[i]] for i in sorted({0, len(fr) // 2, len(fr) - 1})] if fr else [None]

def gun_anchor(char, meta, pack, mdir, ref, wid, overlay=None):
    """the barrel's tip fixed to the bone that carries the gun: (iqm path, joint, point in the joint's frame). Found in
    the aiming stance 'ref' (the gun's surfaces posed -- the baked gun, or the overlay model on the same skeleton --
    and the centre of its foremost vertices); no gun drawn -> its 'primary trigger' marker, else the gun hand"""
    key = ('anchor', char, mdir, ref, wid, overlay)
    if key in _MUZZLE_CACHE: return _MUZZLE_CACHE[key]
    import preview as pv
    res = None
    path = next((p for p in (f'{pack}/models/{mdir}/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.iqm') if os.path.exists(p)), None)
    if path:
        joints, meshes, anims = _iqm(path)
        pose = _poses(anims, ref)[0]
        gm = None
        if overlay:
            op = next((p for p in (f'{pack}/models/{mdir}/{char}/{overlay}', f'{OUT}/models/{char}/{overlay}') if os.path.exists(p)), None)
            if op:
                oj, om, _ = _iqm(op)
                if len(oj) == len(joints): gm = om
        elif wid:
            gm = [meshes[si] for si, w in enumerate(meta.get('mesh_weapon') or []) if w == wid and si < len(meshes)] or None
        if gm:
            P = np.concatenate(pv.skin(joints, gm, pose))
            tip = P[P[:, 0] >= P[:, 0].max() - 0.015].mean(0)
            bi = np.concatenate([m['bidx'][:, 0] for m in gm]); bw = np.concatenate([m['bw'][:, 0] for m in gm])
            j = int(np.bincount(bi[bw > 0]).argmax())
            wt, wq = _posed_world(joints, pose)[j]
            R = pv.qmat(wq).T
            res = (path, j, R @ (tip - np.asarray(wt, float)), R @ (P.mean(0) - np.asarray(wt, float)))
        else:
            mk = meta.get('markers') or {}
            for name in ('primary trigger', 'right hand elite', 'right hand jackal', 'right hand'):
                m = mk.get(name)
                if not m: continue
                if isinstance(m[0], (int, float)): res = (None, -1, np.array(m[:3], float), None); break     # Galap's: model space already
                if m[0]['node'] < len(joints): res = (path, m[0]['node'], np.asarray(m[0]['t'], float), None); break
    _MUZZLE_CACHE[key] = res
    return res

def muzzle_point(anchor, anim, aimed=False):
    """the barrel's tip in the animation 'anim' (Halo model space: origin at the feet, +x forward), the mean over its
    start, middle and end. aimed: None when the gun doesn't point ahead there (held low, swinging on the run: a shot
    from there would leave from the knees; the class's aiming barrel stands in)"""
    if anchor is None: return None
    path, j, loc, mid = anchor
    if j < 0: return loc
    import preview as pv
    joints, _, anims = _iqm(path)
    out, ahead = [], []
    for pose in _poses(anims, anim):
        wt, wq = _posed_world(joints, pose)[j]
        R = pv.qmat(wq)
        out.append(np.asarray(wt, float) + R @ loc)
        if mid is not None:
            d = R @ (loc - mid); ahead.append(d[0] / max(1e-6, np.linalg.norm(d)))
    if aimed and ahead and np.mean(ahead) < 0.6: return None
    return np.mean(out, 0)

# the stances a shot can be fired from (HCE_MuzzleAt: the barrel where that animation holds it)
MUZZLE_KINDS = ['FIRE', 'ALERT', 'IDLE', 'MOVE_F', 'MOVE_B', 'MOVE_L', 'MOVE_R', 'CROUCH_IDLE', 'CROUCH_MOVE', 'LOW_IDLE',
                'LOW_MOVE', 'FLEE', 'COVER_L_PEEK', 'COVER_R_PEEK', 'COVER_L_OPEN', 'COVER_R_OPEN', 'GUARD_IDLE', 'GUARD_MOVE_F',
                'GUARD_MOVE_B', 'GUARD_MOVE_L', 'GUARD_MOVE_R', 'GUARD_CROUCH_IDLE', 'GUARD_CROUCH_MOVE']

def muzzle_code(anchor, table, to_doom, base):
    """HCE_MuzzleAt: the barrel's tip per firing stance, where it differs from HCE_GunOffset (base) by 2 units or more"""
    cases = {}
    for k in MUZZLE_KINDS:
        for n in table.get(k) or []:
            if n in cases: continue
            mz = muzzle_point(anchor, n, aimed=True)
            if mz is None: continue
            g = to_doom(mz)
            if max(abs(g[i] - base[i]) for i in range(3)) >= 2: cases[n] = g
    if not cases: return ''
    return ('\toverride vector3 HCE_MuzzleAt(Name anim)\n\t{\n\t\tswitch(anim)\n\t\t{\n'
            + ''.join(f"\t\tcase '{n}': return ({g[0]:.1f}, {g[1]:.1f}, {g[2]:.1f});\n" for n, g in sorted(cases.items()))
            + '\t\t}\n\t\treturn hce_gunOffset;\n\t}\n')


def gunner_code(leaf, meta, sc, ov):
    """a Galap Sentinel's gunner seats (GALAP_GUNNERS): an extra beam from each marker, on the gunner's own bursts"""
    g = GALAP_GUNNERS.get(leaf)
    if not g or not os.path.exists(GALAP_AI): return ''
    gv = next((v for k, v in json.load(open(GALAP_AI))['variants'].items() if k.split('\\')[-1] == g[1]), None)
    if not gv: return ''
    rc = gv['ranged_combat']; bg = rc['burst_geometry']
    zoff = -meta['bounds'][0][2] * sc * 1.2 if ov.get('lift') else 0.0
    lines = []
    for mk in g[0]:
        p = (meta.get('markers') or {}).get(mk)
        if not p: continue
        lines.append(f'\t\tHCE_AddGunner(({p[0] * sc:.1f}, {p[1] * sc:.1f}, {p[2] * sc * 1.2 + zoff:.1f}), {rc["weapon_damage_modifier"]:.2f}, '
                     f'{bg["burst_duration_lower_bound"]:.2f}, {bg["burst_duration_upper_bound"]:.2f}, '
                     f'{bg["burst_separation_lower_bound"]:.2f}, {bg["burst_separation_upper_bound"]:.2f}, {rc["maximum_firing_range"] * S:.0f});   // {mk}\n')
    if not lines: return ''
    return (f'\t// Galap\'s gunner seats ({g[1].replace("_", " ")}): beams of their own beside its weapon\n'
            '\toverride void HCE_GunnerSetup()\n\t{\n' + ''.join(lines) + '\t}\n')


def bubble_code(char):
    """the shielded ranks (HCE_HasBubble) flare their bubble when hit (HCE_<char>BubbleShell); the body's own bubble
    surface stays hidden"""
    BUBBLE_CHARS.add(char)
    return ("\t// the shield bubble (shielded ranks: HCE_HasBubble) is a flare: lit by hits, fading, shattering when it fails\n"
            "\tvirtual bool HCE_HasBubble() { return false; }\n"
            f"\toverride Name HCE_ShellClass() {{ return HCE_HasBubble() ? 'HCE_{char}BubbleShell' : 'None'; }}\n")


def h2sentinel_skin(cls, v, si, mat, meta, skin_dir):
    """SKIN_HOOK for Halo 2's Aggressor body: the shield surface hidden (the bubble flare draws it), the body baked
    once per rank in its change colour (SENTINEL_CC, toned by SENTINEL_LOOK) with the Elites' cube reflection; None
    (the default bake) for anything else"""
    name = meta['mesh_names'][si]
    rank = v.get('_rank', 'sentinel_minor')
    os.makedirs(skin_dir, exist_ok=True)
    if name.startswith('shield.'):              # drawn by the bubble flare (bubble_code), never on the body
        hid = f'{skin_dir}/hce_hidden.png'
        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        return 'hce_hidden.png'
    if not name.startswith('body.'): return None
    fn = f'{rank}_body.png'; dst = f'{skin_dir}/{fn}'
    if not os.path.exists(dst):
        col = (meta.get('change_colors') or {}).get(SENTINEL_CC.get(rank, 'minor'), [None])[0]
        k = SENTINEL_LOOK.get(rank, (1.0, 1.0))
        if col: col = [c * k[0] + 0.8 * (1 - k[0]) for c in col]       # toward pale metal: the gold read as paint
        bake_skin('Sentinel', 'Sentinel_body', col, dst, k[1])
    return fn


def enforcer_skin(cls, v, si, mat, meta, skin_dir):
    """SKIN_HOOK for the Enforcer: its shield surfaces hidden (its shield field draws them), the rest its own textures
    as they are; the eye and hover jets fully lit"""
    name = meta['mesh_names'][si]
    os.makedirs(skin_dir, exist_ok=True)
    if name.startswith('shield_'):              # drawn by its shield field (HCE_SentinelEnforcerShieldField)
        if not os.path.exists(f'{skin_dir}/hce_hidden.png'): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(f'{skin_dir}/hce_hidden.png')
        return 'hce_hidden.png'
    fn = mat.lower()
    if not os.path.exists(f'{skin_dir}/{fn}'): shutil.copy(f'{OUT}/models/SentinelEnforcer/{mat}', f'{skin_dir}/{fn}')
    if name.startswith(('eye.', 'hover.')): full_bright(skin_dir, fn)
    return fn


if H2_SENTINEL:
    _sm = json.load(open(SENTINEL_JSON))
    SKIN_HOOK['Sentinel'] = h2sentinel_skin
    SHINE['Sentinel'] = 0.6; SHINE_CUBE['Sentinel'] = 'elite'
    if _sm.get('shield_surface') is not None:
        BASE_CODE['Sentinel'] = bubble_code('Sentinel')
if os.path.exists(ENFORCER_JSON):
    _em = json.load(open(ENFORCER_JSON))
    SKIN_HOOK['SentinelEnforcer'] = enforcer_skin
    NO_BLOOD.add('SentinelEnforcer')
    BASE_CODE['SentinelEnforcer'] = (template('zscript/sentinel_enforcer.zs').replace('{SL}', str(_em['shield_surfaces']['left']))
                                     .replace('{SR}', str(_em['shield_surfaces']['right'])).replace('{SHP}', str(ENFORCER_SHIELD_HP))
                                     .replace('{MDIR}', 'hce'))
    CHAR_OVERRIDES['SentinelEnforcer'] = dict(stance='fixed', flying=True, scale=0.6, height_fixed=96, radius_fixed=48,
                                              melee=(170, 50), speed=4.0, shield=0, lift=True)
def galap_skin(cls, v, si, mat, meta, skin_dir):
    """Galap's Sentinels: the shield surface the hard-light lattice (shielded variants) or hidden; the Gold's own gold
    as it is; the rest the default bake (Halo CE's Sentinel metal in the variant's change colour)"""
    name = meta['mesh_names'][si]
    os.makedirs(skin_dir, exist_ok=True)
    if name.startswith('shield.'):              # drawn by the bubble flare (bubble_code), never on the body
        if not os.path.exists(f'{skin_dir}/hce_hidden.png'): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(f'{skin_dir}/hce_hidden.png')
        return 'hce_hidden.png'
    # Forerunner metal: Halo CE's Sentinel sheet (or the Gold's) as it is, its metal (the multipurpose map's red) given a
    # soft cool steel sheen. No baked cube-map reflection: on these flat-shaded bodies it broke up into iridescent facets
    fn = mat.lower()
    dst = f'{skin_dir}/{fn}'
    if not os.path.exists(dst):
        src = f'{OUT}/models/{meta["id"]}/{mat}'
        base = Image.open(src).convert('RGB')
        a = np.asarray(base).astype(np.float32) / 255
        mp = src[:-4] + '_multi.png'
        m = np.asarray(Image.open(mp).convert('RGB').resize(base.size)).astype(np.float32)[..., 0:1] / 255 if os.path.exists(mp) else np.zeros(a.shape[:2] + (1,))
        tint = np.array([1.0, 0.92, 0.6]) if mat.endswith('_gold.png') else np.array([0.88, 0.93, 1.04])
        lum = a.mean(2, keepdims=True)
        sheen = np.clip(lum * tint * 1.08 + 0.05 * tint, 0, 1)
        out = a * (1 - 0.45 * m) + sheen * 0.45 * m
        Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(dst)
    return fn


for _c in GALAP_CHARS:
    _gm = json.load(open(f'{OUT}/models/{_c}/{_c}.json'))
    SKIN_HOOK[_c] = galap_skin
    NO_BLOOD.add(_c)
    if _gm.get('shield_surface') is not None:
        BASE_CODE[_c] = bubble_code(_c)
    _r = max(12, min(48, int(_gm['collision_radius'] * S * 0.6)))
    CHAR_OVERRIDES[_c] = dict(stance='fixed', flying=True, radius_fixed=_r, height_fixed=max(24, _r * 2), lift=True)   # built round their middle: raised so they hover clear of the floor
if 'SentinelCrawler' in GALAP_CHARS:
    # the Crawler walks (Galap's crawling set: idle, move, turns, a melee lunge) and keeps its beam
    CHAR_OVERRIDES['SentinelCrawler'] = dict(stance='unarmed', radius_fixed=24, height_fixed=24, melee=(64, 20), speed=8.0, lift=True)

if os.path.exists(CONSTRUCTOR_JSON):
    SKIN_HOOK['SentinelConstructor'] = lambda cls, v, si, mat, meta, skin_dir: copy_skin('SentinelConstructor', mat, skin_dir)
    NO_BLOOD.add('SentinelConstructor')
    BASE_CODE['SentinelConstructor'] = template('zscript/sentinel_constructor.zs')
    CHAR_OVERRIDES['SentinelConstructor'] = dict(stance='fixed', flying=True, scale=2.5, height_fixed=32, radius_fixed=16,
                                                 melee=(72, 12), speed=9.0, shield=0, lift=True)

# Halo CE's visor shader (shader_model with a reflection cube map): the reflection direction per pixel (the view ray
# off the surface normal), its cube face and texel looked up in the six faces laid side by side (Halo's axes, Direct3D
# face layout), tinted by the visor's texture (its perpendicular / parallel tints, extract_odst.py) and brighter toward
# grazing angles (Halo's fresnel blend), over the visor's own dark glass
VISOR_SHADER = template('shaders/visor.fp')

# the Marine kit's enclosed helmets (helmet_closed, helmet_enclosed and the two ODST helmets) share one orange visor
# texture: it gets the ODSTs' visor shader, tinted by its own orange, over the ODST visor's cube map
KIT_VISOR = 'mk_innie_visor_diff.png'
KIT_VISOR_CUBE = 'mk_visor_cube.png'
# KIT_OWN_VISORS: variants.py

def kit_visor_tint(src, dst, rgb):
    """write dst: the visor texture src's light and shade in the colour rgb (0..1), for KIT_VISOR_TINTS"""
    from PIL import Image
    l = np.asarray(Image.open(src).convert('L'), float)
    l = l / max(l.max(), 1)                               # the orange texture's light and shade, normalised
    im = np.clip(l[..., None] * np.array(rgb) * 255 * 1.05, 0, 255).astype(np.uint8)
    Image.fromarray(im).save(dst)

def kit_visors(pack, mdir):
    """the GLDEFS material giving the Marine kit's helmet visor the visor shader and a cube map"""
    d = f'{pack}/models/{mdir}/MarineKit'
    if not os.path.exists(f'{d}/{KIT_VISOR}'): return []
    if not os.path.exists(f'{MARINE_KIT}/{KIT_VISOR_CUBE}'):
        from extract_odst import cube_strip
        cube_strip('cyborg', f'{MARINE_KIT}/{KIT_VISOR_CUBE}')
    shutil.copy(f'{MARINE_KIT}/{KIT_VISOR_CUBE}', f'{d}/{KIT_VISOR_CUBE}')
    os.makedirs(f'{pack}/shaders', exist_ok=True)
    open(f'{pack}/shaders/hce_visor.fp', 'w').write(VISOR_SHADER)
    out = []
    for name, tex in [(None, KIT_VISOR)] + [(None, t) for t in KIT_OWN_VISORS if os.path.exists(f'{d}/{t}')] + list(KIT_VISOR_TINTS.items()):
        if name: kit_visor_tint(f'{d}/{KIT_VISOR_TINT_SRC.get(name, KIT_VISOR)}', f'{d}/{tex}', KIT_VISOR_COLOURS[name])
        out.append(f'material texture "models/{mdir}/MarineKit/{tex}"\n{{\n\tshader "shaders/hce_visor.fp"\n'
                   f'\ttexture tex_cube "models/{mdir}/MarineKit/{KIT_VISOR_CUBE}"\n}}')
    return out

ELITE_LENSES = ('ek_ranger_lens.png',)   # Halo 2's Ranger's gold eye lenses (extract_h2_elite_kit.py)
ELITE_LENS_CUBE = 'ek_visor_cube.png'

# GLOW_MIN: variants.py
# GLOW_STRENGTH: variants.py
# GLOW_SOFT: variants.py
# KIT_GLOW_STRENGTH: variants.py
_glow_colours = None

def glow_tint(mat):
    """Halo CE's self-illumination colour for a material (glow_colours.py: its shader's animation colours, the brighter
    bound), or None when it is plain white (Halo lights the paint itself there) or unknown"""
    global _glow_colours
    if _glow_colours is None:
        p = f'{OUT}/glow_colours.json'
        _glow_colours = json.load(open(p)) if os.path.exists(p) else {}
    d = _glow_colours.get(mat)
    if not d: return None
    c = max((d['lower'], d['upper']), key=sum)
    if min(c) > 0.9 or max(c) < 0.05: return None
    return [x / max(c) for x in c]           # its hue at full strength (the brightmap sets how bright)

def selfillum_anim(char, mat):
    """Halo CE's self-illumination animation for a material of an animated body (SELFILLUM_CHARS): its glow_colours
    entry when its shader animates its light (a periodic function between two different colours), else None"""
    if char not in SELFILLUM_CHARS: return None
    glow_tint('')                                   # (loads glow_colours.json)
    d = _glow_colours.get(mat)
    if not d or d.get('function', 0) in (0, 1) or d['lower'] == d['upper']: return None
    return d

def selfillum_gl(pack, mdir, camo=()):
    """GLDEFS for the animated self-illumination (SELFILLUM_CHARS): each baked skin (SKIN_PAIRS) whose material's
    shader animates its light gets the derez shader with HCE_SELFILLUM, Halo's function, period and colours as defines,
    and its glow mask (the multipurpose map's green, feathered as glow_maps does: <skin>_si.png) as si_mask; the
    cloaked skins (camo) are left to their camo shader"""
    out = []; done = set()
    black = f'models/{mdir}/hce_fx/black.png'
    for src, dst in SKIN_PAIRS:
        if not dst.startswith(pack + '/') or dst in done or os.path.relpath(dst, pack) in camo: continue   # (cloaked: their shader)
        char = os.path.basename(os.path.dirname(src)); mat = os.path.basename(src)[:-4]
        d = selfillum_anim(char, mat)
        mp = src[:-4] + '_multi.png'
        if not d or not os.path.exists(mp) or not os.path.exists(dst): continue
        done.add(dst)
        from scipy import ndimage
        g = np.asarray(Image.open(mp).convert('RGBA')).astype(np.float32)[..., 1] / 255.0
        k = ndimage.gaussian_filter(np.clip((g - 0.12) / 0.6, 0, 1), GLOW_SOFT)
        si = dst[:-4] + '_si.png'
        Image.fromarray((k * 255).astype(np.uint8)).resize(Image.open(dst).size, Image.BILINEAR).save(si)
        os.makedirs(f'{pack}/models/{mdir}/hce_fx', exist_ok=True)
        if not os.path.exists(f'{pack}/{black}'): Image.new('RGB', (8, 8), (0, 0, 0)).save(f'{pack}/{black}')
        v3 = lambda c: '"vec3(%.4f, %.4f, %.4f)"' % tuple(c)
        rel = os.path.relpath(dst, pack)
        out.append(f'material texture "{rel}"\n{{\n\tshader "shaders/hce_derez.fp"\n\tdefine "HCE_SELFILLUM"\n'
                   f'\tdefine "SI_FN" = "{d["function"]}"\n\tdefine "SI_PERIOD" = "{max(0.05, d["period"]):.3f}"\n'
                   f'\tdefine "SI_LO" = {v3(d["lower"])}\n\tdefine "SI_HI" = {v3(d["upper"])}\n\tdefine "SI_GAIN" = "{SELFILLUM_GAIN:.3f}"\n'
                   f'\tspeed 1.0\n\tbrightmap "{black}"\n\ttexture si_mask "{os.path.relpath(si, pack)}"\n}}')
    if out:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_derez.fp', 'w').write(DEREZ_SHADER)
    return out

def glow_maps(pack, mdir, team, camo):
    """GLDEFS brightmap entries for the Covenant's self-lit parts: for every baked skin (SKIN_PAIRS) whose multipurpose
    map has a glow channel (its green, at least GLOW_MIN), a feathered <material>_bm.png (GLOW_SOFT, GLOW_STRENGTH in
    variants.py) and, where Halo lit it in colour (glow_tint), that colour painted into the skin; the camo skins are
    left out (their shader). Then the Elite kit's own brightmaps. To make the lights stronger or softer, edit
    GLOW_STRENGTH / GLOW_SOFT"""
    out = []; made = {}
    for src, dst in SKIN_PAIRS:
        if not dst.startswith(pack + '/'): continue
        rel = os.path.relpath(dst, pack)
        char = os.path.basename(os.path.dirname(src))
        if team.get(char) != 'COVENANT' or rel in camo: continue
        if selfillum_anim(char, os.path.basename(src)[:-4]): continue      # its lights animated instead (selfillum_gl)
        mp = src[:-4] + '_multi.png'
        if mp not in made:
            made[mp] = None
            if os.path.exists(mp):
                g = np.asarray(Image.open(mp).convert('RGBA')).astype(np.float32)[..., 1] / 255.0
                if g.max() >= GLOW_MIN:
                    from scipy import ndimage
                    sz = Image.open(src).size
                    # a light given off, not a lamp pointed at the paint: partly fullbright (GLOW_STRENGTH), feathered
                    # out at its edges, so the glow sits in the lit scene instead of punching a hard flat patch out of it
                    bm = ndimage.gaussian_filter(np.clip((g - 0.12) / 0.6, 0, 1), GLOW_SOFT) * GLOW_STRENGTH
                    fn = f'models/{mdir}/{char}/{os.path.basename(src)[:-4]}_bm.png'
                    Image.fromarray((bm * 255).astype(np.uint8)).convert('RGB').resize(sz, Image.BILINEAR).save(f'{pack}/{fn}')
                    made[mp] = (fn, np.asarray(Image.fromarray((np.clip((g - 0.12) / 0.6, 0, 1) * 255).astype(np.uint8)).resize(sz, Image.BILINEAR)).astype(np.float32) / 255.0)
        if made[mp]:
            fn, gm = made[mp]
            tint = glow_tint(os.path.basename(src)[:-4])
            if tint is not None:                  # Halo's own self-illumination colour, where it isn't plain white
                im = Image.open(dst).convert('RGB')
                c = np.asarray(im).astype(np.float32) / 255.0
                k = gm[..., None] if gm.shape[:2] == c.shape[:2] else np.asarray(Image.fromarray((gm * 255).astype(np.uint8)).resize(im.size)).astype(np.float32)[..., None] / 255.0
                glow = np.clip(c * np.array(tint, np.float32) * 1.25, 0, 1)        # Halo: the paint times the light's colour
                Image.fromarray((np.clip(c * (1 - k) + glow * k, 0, 1) * 255).astype(np.uint8)).save(dst)
            out.append(f'brightmap texture "{rel}"\n{{\n\tmap "{fn}"\n}}')
    d = f'{pack}/models/{mdir}/EliteKit'
    if os.path.isdir(d) and os.path.exists(f'{ELITE_KIT}/EliteKit.json'):
        for tex, bm in json.load(open(f'{ELITE_KIT}/EliteKit.json')).get('brightmaps', {}).items():
            if os.path.exists(f'{d}/{tex}') and os.path.exists(f'{d}/{bm}'):
                from scipy import ndimage                 # feathered and partly fullbright, as the Covenant's own
                b = np.asarray(Image.open(f'{d}/{bm}').convert('L')).astype(np.float32) / 255.0
                b = ndimage.gaussian_filter(b, GLOW_SOFT) * KIT_GLOW_STRENGTH
                Image.fromarray((np.clip(b, 0, 1) * 255).astype(np.uint8)).convert('RGB').save(f'{d}/{bm}')
                out.append(f'brightmap texture "models/{mdir}/EliteKit/{tex}"\n{{\n\tmap "models/{mdir}/EliteKit/{bm}"\n}}')
    return out

def elite_lens_visors(pack, mdir):
    """the Ranger's eye lenses get the visors' cube-map reflection (VISOR_SHADER, tinted by the lens's own gold, over
    Halo CE's cyborg reflection cube map, as the ODST and kit visors)"""
    d = f'{pack}/models/{mdir}/EliteKit'
    lenses = [t for t in ELITE_LENSES if os.path.exists(f'{d}/{t}')]
    if not lenses: return []
    if not os.path.exists(f'{MARINE_KIT}/{KIT_VISOR_CUBE}'):
        from extract_odst import cube_strip
        cube_strip('cyborg', f'{MARINE_KIT}/{KIT_VISOR_CUBE}')
    shutil.copy(f'{MARINE_KIT}/{KIT_VISOR_CUBE}', f'{d}/{ELITE_LENS_CUBE}')
    os.makedirs(f'{pack}/shaders', exist_ok=True)
    open(f'{pack}/shaders/hce_visor.fp', 'w').write(VISOR_SHADER)
    return [f'material texture "models/{mdir}/EliteKit/{t}"\n{{\n\tshader "shaders/hce_visor.fp"\n'
            f'\ttexture tex_cube "models/{mdir}/EliteKit/{ELITE_LENS_CUBE}"\n}}' for t in lenses]

def odst_visors(pack, mdir, md):
    """GLDEFS materials giving each ODST visor skin the visor shader and its cube map"""
    j = f'{OUT}/models/MarineODST/MarineODST.json'
    if not os.path.exists(j) or 'MarineODST' not in '\n'.join(md): return []
    meta = json.load(open(j)); vis = meta.get('visor')
    if not vis: return []
    si = meta['meshes'].index(vis['mat'])
    d = f'{pack}/models/{mdir}/MarineODST'
    out = []; done = set()
    for blk in md:
        if f'"models/{mdir}/MarineODST"' not in blk: continue
        m = re.search(rf'SurfaceSkin 0 {si} "([^"]+)"', blk)
        if not m or m.group(1) in done: continue
        done.add(m.group(1))
        rv = re.search(r'raven_(\w+?)\.png', m.group(1))
        cube = vis['raven'][rv.group(1)]['cube'] if rv and rv.group(1) in vis['raven'] else vis['base']['cube']
        cf = f'MarineODST_cube_{cube}.png'
        if not os.path.exists(f'{d}/{cf}'): shutil.copy(f'{OUT}/models/MarineODST/{cf}', f'{d}/{cf}')
        out.append(f'material texture "models/{mdir}/MarineODST/{m.group(1)}"\n{{\n\tshader "shaders/hce_visor.fp"\n'
                   f'\ttexture tex_cube "models/{mdir}/MarineODST/{cf}"\n}}')
    if out:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_visor.fp', 'w').write(VISOR_SHADER)
    return out

def arsenal_lines(char, name, meta, pack, mdir, idx=None):
    """MODELDEF lines attaching a Marine arsenal overlay (model 6) and copying its files into the pack"""
    a = (meta.get('arsenal') or {}).get(name)
    if not a: raise SystemExit(f'{char}: no arsenal overlay {name!r} (run marine_arsenal.py overlays after blood_kit.py)')
    os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
    dst = f'{pack}/models/{mdir}/{char}/{a["model"]}'
    if not os.path.exists(dst): shutil.copy(f'{OUT}/models/{char}/{a["model"]}', dst)
    for m in a['materials']:
        d = f'{pack}/models/{mdir}/weapons/{m}'
        if not os.path.exists(d): copy_weapon_tex(f'{OUT}/models/{char}/{m}', d)
    idx = ARSENAL_IDX if idx is None else idx
    return ([f'\tPath "models/{mdir}/{char}"', f'\tModel {idx} "{a["model"]}"', f'\tPath "models/{mdir}/weapons"']
            + [f'\tSurfaceSkin {idx} {k} "{m}"' for k, m in enumerate(a['materials'])])

def overlay_swap(char, meta, mdir, name, idx=None, pack=None):
    """ZScript lines putting arsenal overlay 'name' on the gun model slot (and its files into the pack)"""
    a = meta['arsenal'][name]
    idx = ARSENAL_IDX if idx is None else idx; pack = pack or PACK
    for m in a['materials']:
        dd = f'{pack}/models/{mdir}/weapons/{m}'
        if not os.path.exists(dd): os.makedirs(os.path.dirname(dd), exist_ok=True); copy_weapon_tex(f'{OUT}/models/{char}/{m}', dd)
    dd = f'{pack}/models/{mdir}/{char}/{a["model"]}'
    if not os.path.exists(dd): os.makedirs(os.path.dirname(dd), exist_ok=True); shutil.copy(f'{OUT}/models/{char}/{a["model"]}', dd)
    out = [f'\t\tA_ChangeModel(\'None\', {idx}, "models/{mdir}/{char}", \'{a["model"]}\');\n']
    out += [f'\t\tA_ChangeModel(\'None\', {idx}, "", \'None\', {k}, "models/{mdir}/weapons", \'{m}\', CMDL_USESURFACESKIN);\n'
            for k, m in enumerate(a['materials'])]
    return ''.join(out)

def johnson_code(A, animtxt, char, meta, mdir):
    """Sergeant Johnson: the Stanchion at range, the Magnum (Halo 2's pistol stance) when an enemy closes in"""
    cqc = zs_anim_funcs(A, anim_table(A, H2PISTOL_STANCE, 'pistol'))
    animtxt = (animtxt.replace('override Name HCE_AnimName(int kind)', 'Name HCE_AnimNameLong(int kind)')
                      .replace('override int HCE_AnimTics(Name anim)', 'int HCE_AnimTicsLong(Name anim)')
                      .replace('override vector3 HCE_AnimMove(Name anim)', 'vector3 HCE_AnimMoveLong(Name anim)'))
    cqc = (cqc.replace('override Name HCE_AnimName(int kind)', 'Name HCE_AnimNameCQC(int kind)')
              .replace('override int HCE_AnimTics(Name anim)', 'int HCE_AnimTicsCQC(Name anim)')
              .replace('override vector3 HCE_AnimMove(Name anim)', 'vector3 HCE_AnimMoveCQC(Name anim)'))
    def swap(name):
        """the ZScript lines putting arsenal overlay name on the gun slot (overlay_swap without the file copies)"""
        a = meta['arsenal'][name]
        out = [f'\t\tA_ChangeModel(\'None\', {ARSENAL_IDX}, "models/{mdir}/{char}", \'{a["model"]}\');\n']
        out += [f'\t\tA_ChangeModel(\'None\', {ARSENAL_IDX}, "", \'None\', {k}, "models/{mdir}/weapons", \'{m}\', CMDL_USESURFACESKIN);\n'
                for k, m in enumerate(a['materials'])]
        return ''.join(out)
    pp = PATTERNS['pistol']; ps = FIRE_SOUNDS['pistol']
    code = f"""
	// Sergeant Johnson: always his own face and voice. The Stanchion at range; when an enemy gets within ~6 m he
	// switches to the Magnum (Halo 2's pistol stance) and back again once it's past ~9 m
	override int HCE_PickFace() {{ return HCE_JOHNSON_FACE; }}
	override Name HCE_AnimName(int kind) {{ return hce_cqc ? HCE_AnimNameCQC(kind) : HCE_AnimNameLong(kind); }}
	override int HCE_AnimTics(Name anim) {{ int t = HCE_AnimTicsLong(anim); return t != 30 ? t : HCE_AnimTicsCQC(anim); }}
	override vector3 HCE_AnimMove(Name anim) {{ vector3 m = HCE_AnimMoveLong(anim); return m != (0, 0, 0) ? m : HCE_AnimMoveCQC(anim); }}
	override void HCE_OwnGunBack() {{ hce_cqc = false; }}          // the Stanchion back in his hands (a trade)
	Name hce_longProj; int hce_longShots[3]; double hce_longPause[2]; double hce_longErr, hce_longSpeed, hce_longRange[2];
	String hce_longSound[3];
	override void PostBeginPlay()
	{{
		super.PostBeginPlay();
		hce_voice = 'Marine_Johnson';
		hce_rankName = "SGT. Avery J. Johnson";
		hce_longProj = hce_projectile; hce_longErr = hce_errorAngle; hce_longSpeed = hce_projSpeed;
		hce_longShots[0] = hce_patShotsMin; hce_longShots[1] = hce_patShotsMax; hce_longShots[2] = hce_patInterval;
		hce_longPause[0] = hce_patPauseMin; hce_longPause[1] = hce_patPauseMax;
		hce_longRange[0] = hce_rangeMin; hce_longRange[1] = hce_rangeMax;
		hce_longSound[0] = hce_fireSound; hce_longSound[1] = hce_fireSoundBass; hce_longSound[2] = hce_chargeSound;
	}}
	override void Tick()
	{{
		super.Tick();
		if(health <= 0 || !target || level.maptime % 6 || hce_hasLoadout) return;     // carrying a gun he picked up or was traded
		double d = Distance3D(target);
		if(!hce_cqc && d < 192) HCE_CloseQuarters(true);
		else if(hce_cqc && d > 288) HCE_CloseQuarters(false);
	}}
	void HCE_CloseQuarters(bool on)
	{{
		hce_cqc = on;
		hce_burstShot = 0;
		if(on)
		{{
{swap('magnum')}			hce_projectile = '{WEAPONS['pistol'][0]}'; hce_errorAngle = 1.5; hce_projSpeed = {WEAPONS['pistol'][3] * S / TICK:.1f};
			hce_patShotsMin = {pp[0]}; hce_patShotsMax = {pp[1]}; hce_patInterval = {pp[2]}; hce_patPauseMin = {pp[3]}; hce_patPauseMax = {pp[4]};
			hce_rangeMin = 0; hce_rangeMax = 160;
			hce_fireSound = "{ps[0]}"; hce_fireSoundBass = "{ps[1]}"; hce_chargeSound = "";
		}}
		else
		{{
{swap('stanchion')}			hce_projectile = hce_longProj; hce_errorAngle = hce_longErr; hce_projSpeed = hce_longSpeed;
			hce_patShotsMin = hce_longShots[0]; hce_patShotsMax = hce_longShots[1]; hce_patInterval = hce_longShots[2];
			hce_patPauseMin = hce_longPause[0]; hce_patPauseMax = hce_longPause[1];
			hce_rangeMin = hce_longRange[0]; hce_rangeMax = hce_longRange[1];
			hce_fireSound = hce_longSound[0]; hce_fireSoundBass = hce_longSound[1]; hce_chargeSound = hce_longSound[2];
		}}
		HCE_Play(target ? HCE_A_ALERT : HCE_A_IDLE);
	}}
"""
    return animtxt + '\n' + cqc, code
def stacker_code(A, animtxt, char, meta, mdir):
    """Sergeant Stacker: the double barrel, and the SMG (Halo 2's rifle stance, hand on its foregrip) as his backup
    up close: when both barrels are spent with an enemy within ~11 m he draws the SMG instead of reloading, and goes
    back to the (reloaded) double barrel once the enemy is past ~13 m or after 6 seconds"""
    smg_table = zs_anim_funcs(A, anim_table(A, MARINE_ARSENAL['smg'][1], 'smg'))
    animtxt = (animtxt.replace('override Name HCE_AnimName(int kind)', 'Name HCE_AnimNameMain(int kind)')
                      .replace('override int HCE_AnimTics(Name anim)', 'int HCE_AnimTicsMain(Name anim)')
                      .replace('override vector3 HCE_AnimMove(Name anim)', 'vector3 HCE_AnimMoveMain(Name anim)'))
    smg_table = (smg_table.replace('override Name HCE_AnimName(int kind)', 'Name HCE_AnimNameSMG(int kind)')
                          .replace('override int HCE_AnimTics(Name anim)', 'int HCE_AnimTicsSMG(Name anim)')
                          .replace('override vector3 HCE_AnimMove(Name anim)', 'vector3 HCE_AnimMoveSMG(Name anim)'))
    sp = PATTERNS['smg']; ss = FIRE_SOUNDS['smg']; smg = WEAPONS['smg']
    code = f"""
	// Sergeant Stacker's double barrel, with the SMG as his close-range backup (stacker_code)
	bool hce_onBackup; int hce_backupUntil;
	override Name HCE_AnimName(int kind) {{ return hce_onBackup ? HCE_AnimNameSMG(kind) : HCE_AnimNameMain(kind); }}
	override int HCE_AnimTics(Name anim) {{ int t = HCE_AnimTicsMain(anim); return t != 30 ? t : HCE_AnimTicsSMG(anim); }}
	override vector3 HCE_AnimMove(Name anim) {{ vector3 m = HCE_AnimMoveMain(anim); return m != (0, 0, 0) ? m : HCE_AnimMoveSMG(anim); }}
	override void HCE_OwnGunBack() {{ hce_onBackup = false; }}       // the double barrel back in his hands (a trade)
	Name hce_mainProj; int hce_mainShots[3], hce_mainPellets; double hce_mainPause[2]; double hce_mainErr, hce_mainSpeed, hce_mainRange[2];
	String hce_mainSound[2];
	override void PostBeginPlay()
	{{
		super.PostBeginPlay();
		hce_voice = 'Marine_Sarge';
		hce_rankName = "MSG. Marcus P. Stacker";
		hce_mainProj = hce_projectile; hce_mainErr = hce_errorAngle; hce_mainSpeed = hce_projSpeed; hce_mainPellets = hce_projectilesPerShot;
		hce_mainShots[0] = hce_patShotsMin; hce_mainShots[1] = hce_patShotsMax; hce_mainShots[2] = hce_patInterval;
		hce_mainPause[0] = hce_patPauseMin; hce_mainPause[1] = hce_patPauseMax;
		hce_mainRange[0] = hce_rangeMin; hce_mainRange[1] = hce_rangeMax;
		hce_mainSound[0] = hce_fireSound; hce_mainSound[1] = hce_fireSoundBass;
	}}
	override bool HCE_OnEmpty()
	{{
		if(hce_onBackup || hce_hasLoadout || !target || Distance3D(target) > 384) return false;
		HCE_Backup(true);
		return true;
	}}
	override void Tick()
	{{
		super.Tick();
		if(!hce_onBackup || health <= 0 || level.maptime % 6) return;
		if(hce_hasLoadout || !target || Distance3D(target) > 448 || level.maptime > hce_backupUntil) HCE_Backup(false);
	}}
	void HCE_Backup(bool on)
	{{
		hce_onBackup = on;
		hce_burstShot = 0; hce_shotsLeft = 0;
		if(on)
		{{
			hce_backupUntil = level.maptime + 35 * 6;
{overlay_swap(char, meta, mdir, 'smg')}			hce_projectile = '{smg[0]}'; hce_projectilesPerShot = 1; hce_errorAngle = 2.0; hce_projSpeed = {smg[3] * S / TICK:.1f};
			hce_patShotsMin = {sp[0]}; hce_patShotsMax = {sp[1]}; hce_patInterval = {sp[2]}; hce_patPauseMin = {sp[3]}; hce_patPauseMax = {sp[4]};
			hce_rangeMin = 0; hce_rangeMax = 320;
			hce_fireSound = "{ss[0]}"; hce_fireSoundBass = "{ss[1]}";
			hce_sepTics = 6;                      // the SMG comes up fast
		}}
		else if(!hce_hasLoadout)
		{{
{overlay_swap(char, meta, mdir, 'double_barrel')}			hce_projectile = hce_mainProj; hce_errorAngle = hce_mainErr; hce_projSpeed = hce_mainSpeed; hce_projectilesPerShot = hce_mainPellets;
			hce_patShotsMin = hce_mainShots[0]; hce_patShotsMax = hce_mainShots[1]; hce_patInterval = hce_mainShots[2];
			hce_patPauseMin = hce_mainPause[0]; hce_patPauseMax = hce_mainPause[1];
			hce_rangeMin = hce_mainRange[0]; hce_rangeMax = hce_mainRange[1];
			hce_fireSound = hce_mainSound[0]; hce_fireSoundBass = hce_mainSound[1];
		}}
		HCE_SetupAmmo();                          // a full SMG magazine; the double barrel comes back reloaded
		HCE_Play(target ? HCE_A_ALERT : HCE_A_IDLE);
	}}
"""
    return animtxt + '\n' + smg_table, code

# ---------------------------------------------------------------- Mercury Rising's units
# aLTis's Mercury Rising (Steam Workshop 3021510694; extract_spv3.py 'mr1' / 'mr2' -> spv3_ai.json, keys under 'mercury\'):
#  * six Sentinels of its own (Sentinels pack), each on its own body with Halo CE's Sentinel animations, flying like
#    Galap's. Their guns are the bipeds' own (the actor variants carry none): the Artillery lobs a hard-light mortar
#    (0.5 a second, a gravity shell), the Brute a heavy beam with the same mortar between its bursts, the Canoneer
#    and the Omega a heavy beam, the Compiler a spread of ten hard-light bolts, the Scout strings of needle bolts
#  * the Artybug (Covenant): a big Covenant war beast with a plasma shotgun (ten plasma-rifle bolts a shot)
#  * CMT's Geist (Covenant): a little Covenant drone with a plasma rifle, in the Lost Souls' place
#  * the 1999 Elite (Digsite's 99_mac, as Mercury Rising fields it): the Draeth, a race of its own, the UNSC's
#    Reavers, armed with every Covenant gun the Elites carry but the sword (extract_spv3.MAP_EXTRA_WEAPONS bakes the
#    ones Mercury Rising's variants don't): Minors and Majors with the plasma rifle and the needler, Majors with the
#    fuel rod, Commanders (cloaked or not) with the beam rifle, the Plasma Caster and the fuel rod. Mercury Rising's
#    Excavator (its scatter gun) isn't used
#  * the medic (Marines pack): a whole body over the CE Marine (extract_mr_marines.py), so he fights with all the
#    Marines have; the field medics are corpsmen (they answer the "medic" order). Mercury Rising's female Marine isn't used
MR = 'mercury\\'
MR_SENTINELS = {r'characters\sentinel\variants\artillery\artillery': ('SentinelArtillery', 'sentinel artillery'),
                r'characters\sentinel\variants\brute\brute': ('SentinelBrute', 'sentinel brute'),
                r'characters\sentinel\variants\canoneer\canoneer': ('SentinelCanoneer', 'sentinel canoneer'),
                r'characters\sentinel\variants\compiler\compiler': ('SentinelCompiler', 'sentinel compiler'),
                r'characters\sentinel\variants\omega\omega': ('SentinelOmega', 'sentinel omega'),
                r'characters\sentinel\variants\scout\scout': ('SentinelScout', 'sentinel scout')}
MR_SENTINEL_GUNS = {'sentinel artillery': (r'mercury\sentinel artillery', 1.0),       # the mortar (WEAPONS below)
                    'sentinel brute': (r'characters\sentinel\sentinel', 2.0),          # a heavy beam (+ the mortar: MR_BRUTE_CODE)
                    'sentinel canoneer': (r'characters\sentinel\sentinel', 1.5),
                    'sentinel compiler': (r'mercury\sentinel compiler', 1.0),
                    'sentinel omega': (r'characters\sentinel\sentinel', 1.5),
                    'sentinel scout': (r'weapons\enforcer needler\enforcer needler', 0.8)}
MR_ARTYBUG = r'characters\artybug\artybug'
MR_GEIST = r'cmt\characters\geist\geist'
MR_DRAETH = r'digsite\characters\elite\99_mac\elite_99'
# Mercury Rising's variant (leaf) -> the pack's (the class name: HCE_Draeth...)
MR_DRAETH_NAMES = {'elite minor plasma rifle': 'draeth minor plasma rifle', 'elite major plasma rifle': 'draeth major plasma rifle',
                   'elite minor needler': 'draeth minor needler', 'elite commander excavator camo': 'draeth commander beam rifle camo'}
# the Draeth classes the pack adds beyond Mercury Rising's: (name, the variant it is cut from, the gun's tag, the Elite
# variant whose ranged_combat (ranges, bursts, rate of fire) it takes, or None to keep its own)
MR_DRAETH_EXTRA = [('draeth major needler', 'draeth major plasma rifle', r'weapons\needler\needler', r'characters\elite\elite minor\elite minor needler'),
                   ('draeth major fuel rod', 'draeth major plasma rifle', r'weapons\fuel rod gun\fuel rod', r'characters\elite\elite major\elite major fuel rod'),
                   ('draeth commander beam rifle', None, None, None),          # the cloaked Commander without the cloak (below)
                   ('draeth commander plasma caster', 'draeth commander beam rifle', r'hde\plasma caster', r'characters\elite\elite specops\elite specops plasma caster'),
                   ('draeth commander plasma caster camo', 'draeth commander beam rifle camo', r'hde\plasma caster', r'characters\elite\elite specops\elite specops plasma caster'),
                   ('draeth commander fuel rod', 'draeth commander beam rifle', r'weapons\fuel rod gun\fuel rod', r'characters\elite\elite major\elite major fuel rod')]
# the Draeth Zealots, gold, above the Commanders: (name, the gun's tag), each cut from the Commander with that gun
MR_DRAETH_ZEALOT = [('draeth zealot beam rifle', H2BEAM_REF), ('draeth zealot plasma caster', r'hde\plasma caster'),
                    ('draeth zealot fuel rod', r'weapons\fuel rod gun\fuel rod')]
MR_ZEALOT_VITALITY = (120.0, 300.0)   # body, shield (the Commander: 100, 200; the Elites' Ultra Zealot: 130, 400)
MR_ZEALOT_GOLD = (1.00, 0.78, 0.22)  # the Elite Commander's vivid gold (variants.VIVID)
MR_MEDIC_GUNS = ('magnum', 'smg')     # the field medics' (HCE_MarineFieldMedic<Gun>)
MR_CHARS = []                         # the Mercury Rising characters whose models exist (add_mercury fills it)
# their DoomEdNum order (late_order): the Sentinels, the beasts, the Draeth, then the Marines
MR_ORDER = (['HCE_SentinelArtillery', 'HCE_SentinelBrute', 'HCE_SentinelCanoneer', 'HCE_SentinelCompiler', 'HCE_SentinelOmega',
             'HCE_SentinelScout', 'HCE_Artybug', 'HCE_Geist']
            + [cname(n) for n in MR_DRAETH_NAMES.values()] + [cname(n) for n, _, _, _ in MR_DRAETH_EXTRA] + [cname(n) for n, _ in MR_DRAETH_ZEALOT] + ['HCE_RandomDraeth']
            + [cname(f'marine field medic {g}') for g in MR_MEDIC_GUNS])

# the Brute Sentinel's second gun: Mercury Rising's brute_gun fires the beam and, on its other trigger, the Artillery's shell
MR_BRUTE_CODE = """
	// the Brute Sentinel's second trigger: an artillery shell lobbed now and then between its beam bursts
	int hce_mortarTics;
	override void Tick()
	{
		super.Tick();
		if(health <= 0 || IsFrozen() || !target || target.health <= 0 || !hce_canSee) return;
		if(--hce_mortarTics > 0) return;
		hce_mortarTics = random[HCEMortar](35 * 3, 35 * 5);
		if(Distance3D(target) < 256) return;                  // too close to be safe for itself
		class<Actor> pc = (class<Actor>)('HCE_SentinelMortar');
		if(!pc) return;
		let g = Spawn(pc, Vec3Angle(hce_gunOffset.x, angle, height * 0.5 + hce_gunOffset.z), ALLOW_REPLACE);
		if(!g) return;
		g.target = self;
		if(!HCE_LobAt(g, g.pos, 48)) { g.Destroy(); return; }     // no arc under this ceiling
		HCE_ScaleShot(g);
		A_StartSound("Halo/Weapons/FuelRod/Fire", CHAN_WEAPON, CHANF_OVERLAP);
	}
"""
# the Artillery Sentinel's shell (HARDLIGHT_CODE's): a heavy green hard-light bolt that falls (Halo's gravity scale 1.1)
# and bursts where it lands
HARDLIGHT_CODE += '''
// Mercury Rising's Artillery Sentinel: a hard-light mortar shell on an arc, bursting where it comes down
class HCE_HardlightMortar : HCE_HardlightGreen
{
	Default { Scale 0.024; -NOGRAVITY; Gravity 0.43; }
	// the lob's velocity is set right after the spawn (HCE_LobAt): kept through HDE's own set-up (which aims it straight)
	override void PostBeginPlay()
	{
		vector3 v = vel;
		super.PostBeginPlay();
		if(v.Length() > 0) { vel = v; angle = atan2(v.y, v.x); }
	}
	States
	{
	Death:
	XDeath:
	Crash:
		TNT1 A 0
		{
			A_Explode(int(40 * max(0.1, DamageMultiply)), 112, 0);
			A_StartSound("Halo/Wraith/MissileExplosion", CHAN_BODY, CHANF_OVERLAP);
		}
		Goto Super::Death;
	}
}
'''
SLOW_PROJ.add('HCE_HardlightMortar')
HARDLIGHT_WEAPONS = ['sentinel artillery', 'sentinel compiler']   # weapons needing HARDLIGHT_CODE besides the Knights' and the Enforcer's
WEAPONS['sentinel artillery'] = ('HCE_SentinelMortar', 'HCE_HardlightMortar', 30, 0.53)
PATTERNS['sentinel artillery'] = (1, 1, 1, 1.6, 2.6, 0, False, 2.0, 0.1)
FIRE_SOUNDS['sentinel artillery'] = (W + 'FuelRod/Fire', W + 'FuelRod/Fire/Bass', '', '', False)
LOBBED.add('sentinel artillery')
WEAPONS['sentinel compiler'] = ('HCE_CompilerBolt', 'HCE_HardlightBlue', 8, 4.0)
PATTERNS['sentinel compiler'] = (1, 1, 1, 1.0, 1.6, 0, False, 1.0, 0.1)
FIRE_SOUNDS['sentinel compiler'] = FIRE_SOUNDS['scattershot']
# the Artybug's plasma shotgun: ten plasma-rifle bolts a shot, about 2 a second in Mercury Rising
WEAPONS['plasma shotgun'] = ('HCE_PlasmaShotgunBolt', 'HaloPlasmaRifle_Proj', 13, 1.67)
PATTERNS['plasma shotgun'] = (1, 2, 16, 1.4, 2.2, 0, False, 1.75, 0.1)
FIRE_SOUNDS['plasma shotgun'] = FIRE_SOUNDS['plasma rifle']
FIRE_CODE['plasma shotgun'] = 'pp'

# the medic's and the women's bodies: hide the CE Marine (every body surface) and wear the whole body at the kit's
# head slot (model 1; no kit is rolled for them)
MR_BODY_CODE = """
	// %s (Mercury Rising's body: extract_mr_marines.py), a whole body on the Marine's skeleton in place of Halo CE's,
	// and none of the field kit
	override void HCE_KitOverride() { for(int i = 0; i < hce_kit.Size(); i++) hce_kit[i] = ""; }
	override void PostBeginPlay()
	{
%s		super.PostBeginPlay();
		static const int BS[] = { {HCE_BODY_SURFS} };
		for(int i = 0; i < BS.Size(); i++)
		{
			if(BS[i] < 0) continue;
			A_ChangeModel('None', 0, "", 'None', BS[i], "models/hce/weapons", 'hce_hidden.png', CMDL_USESURFACESKIN);
			if(hce_hideSurf.Find(BS[i]) == hce_hideSurf.Size()) hce_hideSurf.Push(BS[i]);
		}
		A_ChangeModel('None', 1, "models/hce/MarineKit", "%s.iqm", 1, "", 'None');
		HCE_ResumeAnim();
	}
"""
MR_MEDIC_CODE = MR_BODY_CODE % ('a field medic: a corpsman who answers "medic" (HCE_MedicOrder)', '\t\thce_isMedic = true;\n', 'mr_medic_body')


def add_mercury(ai):
    """Mercury Rising's units into the pack's AI data (spv3_ai.json's 'mercury\\' keys: their actors and collision
    models under 'mercury\\' too, clear of Halo CE's own of the same names)"""
    sp = f'{OUT}/spv3_ai.json'
    if not os.path.exists(sp): return
    S3 = json.load(open(sp))
    mv = {k[len(MR):]: v for k, v in S3['variants'].items() if k.startswith(MR)}
    def body(unit, char, team):
        """register a Mercury Rising biped as character char on side team (CHAR_OF_UNIT, TEAM, its collision model
        under 'mercury\\'); False when its model or biped is missing"""
        if unit not in S3['bipeds'] or not os.path.exists(f'{OUT}/models/{char}/{char}.json'): return False
        CHAR_OF_UNIT[unit] = char; TEAM[char] = team; MR_CHARS.append(char)
        b = copy.deepcopy(S3['bipeds'][unit])
        cm = b.get('collision_model')
        if cm and cm in S3['collisions']:
            b['collision_model'] = MR + cm; ai['collisions'][MR + cm] = S3['collisions'][cm]
        ai['bipeds'][unit] = b
        return True
    def variant(src, key, ref=None, **kw):
        """a copy of variant src stored as ai['variants'][key] (its actor brought under 'mercury\\', weapon ref set,
        marked late, kw fields set); returns it"""
        v = copy.deepcopy(src)
        ar = v['actor_reference']
        if not ar.startswith(MR): ai['actors'][MR + ar] = copy.deepcopy(S3['actors'][ar]); ar = MR + ar
        v['actor_reference'] = ar
        if ref is not None: v['ranged_combat']['reference'] = ref
        v['_late'] = True
        v.update(kw)
        ai['variants'][key] = v
        return v
    # the Sentinels
    for unit, (char, name) in MR_SENTINELS.items():
        src = next((v for v in mv.values() if v['unit_reference'] == unit), None)
        if src is None or not body(unit, char, 'SENTINEL'): continue
        ref, dmg = MR_SENTINEL_GUNS[name]
        v = variant(src, rf'characters\{name}\{name}', ref, _rank='sentinel_minor', _ov={})
        v['ranged_combat']['weapon_damage_modifier'] = dmg
        v['grenade_combat']['throw_grenade_chance'] = 0.0; v['items']['grenades_upper_bound'] = 0
        if name == 'sentinel brute': v['_ov'] = dict(code=MR_BRUTE_CODE)
        if name == 'sentinel compiler': v['_ov'] = dict(pellets=10, spread=6.0)
    # the Artybug and the Geist
    src = mv.get(r'characters\artybug\bug')
    if src and body(MR_ARTYBUG, 'Artybug', 'COVENANT'):
        v = variant(src, r'characters\artybug\artybug', r'characters\artybug\plasma shotgun')
        v['ranged_combat'].update(rate_of_fire=2.2, weapon_damage_modifier=0.6)
        v['_ov'] = dict(pellets=10, spread=8.0)
    src = mv.get(r'cmt\characters\geist\geist')
    if src and body(MR_GEIST, 'Geist', 'COVENANT'):
        v = variant(src, r'characters\geist\geist')
        v['grenade_combat']['throw_grenade_chance'] = 0.0; v['items']['grenades_upper_bound'] = 0
        v['_ov'] = dict(drops=False)
    # the Draeth
    if body(MR_DRAETH, 'Draeth', 'COVENANT'):
        D = 'characters\\draeth\\'
        for leaf, name in MR_DRAETH_NAMES.items():
            src = next((v for k, v in mv.items() if k.split('\\')[-1] == leaf), None)
            if src is None: continue
            v = variant(src, D + name)
            if 'beam rifle' in name:
                # the cloaked Commander: Mercury Rising's Excavator traded for Halo 2's beam rifle, the Spec Ops
                # Elite's ranges and bursts (add_beam_rifle_specops), and a shield like a Major's under the cloak
                v['ranged_combat']['reference'] = H2BEAM_REF
                sp = ai['variants'].get(r'characters\elite\elite specops\elite specops beam rifle')
                if sp: v['ranged_combat'] = dict(copy.deepcopy(sp['ranged_combat']), reference=H2BEAM_REF)
        # the Draeth the pack adds: the Elites' other guns (MR_DRAETH_EXTRA), their ranges and bursts the Elites' own
        for name, src_name, ref, elite in MR_DRAETH_EXTRA:
            if name == 'draeth commander beam rifle':
                b = ai['variants'].get(D + 'draeth commander beam rifle camo')
                if not b: continue
                c = variant(b, D + name)                # the Commander without the cloak, his shield up instead
                c['flags'] = b['flags'] & ~0x30
                c['unit'] = dict(b['unit'], maximum_body_vitality=100.0, maximum_shield_vitality=200.0)
                continue
            src = ai['variants'].get(D + src_name)
            if not src: continue
            n = variant(src, D + name, ref)
            e = ai['variants'].get(elite) or mv.get(elite)
            if e: n['ranged_combat'] = dict(copy.deepcopy(e['ranged_combat']), reference=ref)
        # only the high ranks wear energy shields: the Minors and Majors fight on their body alone, and the cloaked
        # Commanders on their camo alone (the 'shield' override: a variant's 0 means 'the collision model's' to build(),
        # as in Halo's tags)
        for k, v in ai['variants'].items():
            if k.startswith(D) and (' minor ' in k or ' major ' in k or k.endswith(' camo')):
                v['_ov'] = dict(v.get('_ov') or {}, shield=0)
        # the Zealots (MR_DRAETH_ZEALOT): a gold rank above the Commanders, cut from the uncloaked Commander with the
        # Commanders' guns, tougher and with a stronger shield
        b = ai['variants'].get(D + 'draeth commander beam rifle')
        if b:
            for name, ref in MR_DRAETH_ZEALOT:
                src = ai['variants'].get(D + name.replace('zealot', 'commander'))
                if not src: continue
                z = variant(src, D + name, ref)
                z['unit'] = dict(src['unit'], maximum_body_vitality=MR_ZEALOT_VITALITY[0], maximum_shield_vitality=MR_ZEALOT_VITALITY[1])
                z['change_colors_list'] = [dict(color_lower_bound=list(MR_ZEALOT_GOLD), color_upper_bound=list(MR_ZEALOT_GOLD))]
    # the medic, on the CE Marine
    for gun in MR_MEDIC_GUNS:
        src = ai['variants'].get(f'characters\\marine\\marine {gun}')
        if not src or not os.path.exists(f'{MARINE_KIT}/mr_medic_body.iqm'): continue
        v = copy.deepcopy(src); v['_late'] = True
        ov = dict(v.get('_ov') or {})
        ov['code'] = ov.get('code', '') + MR_MEDIC_CODE
        ov.setdefault('skin_as', cname(f'marine {gun}'))
        v['_ov'] = ov
        ai['variants'][f'characters\\marine\\marine field medic {gun}'] = v

add_mercury(AI)
for _c in MR_CHARS:
    _gm = json.load(open(f'{OUT}/models/{_c}/{_c}.json'))
    if _c.startswith('Sentinel') or _c == 'Geist':
        # flying bodies built round their middle (Halo CE's Sentinel rig): raised clear of the floor like Galap's
        SENTINEL_LIKE.add(_c); NO_BLOOD.add(_c); NO_RANDOM.add(_c)
        _r = max(12, min(48, int(_gm['collision_radius'] * S * 0.6)))
        CHAR_OVERRIDES[_c] = dict(stance='fixed', flying=True, radius_fixed=_r, height_fixed=max(24, _r * 2), lift=True)
        if _c.startswith('Sentinel'):
            SENTINEL_UNIT_SOUNDS[_c] = ('HCE/Sentinel/Engine', 'HCE/Sentinel/Hit', 'HCE/Sentinel/Death')
if 'SentinelBrute' in MR_CHARS:      # a flying fortress two and a half metres across: shrunk to fit Doom's halls
    CHAR_OVERRIDES['SentinelBrute'] = dict(stance='fixed', flying=True, scale=0.55, radius_fixed=40, height_fixed=64, lift=True)
if 'Geist' in MR_CHARS:
    CHAR_OVERRIDES['Geist'] = dict(CHAR_OVERRIDES['Geist'], radius_fixed=14, height_fixed=28)
if 'Artybug' in MR_CHARS:
    NO_RANDOM.add('Artybug')
    # its own voice (voice_extra/Artybug, REV's): alerts, pain and deaths, a call as it opens fire, another on finding a lost foe
    VOICES['Artybug'] = 'Artybug'
    BASE_CODE['Artybug'] = BASE_CODE.get('Artybug', '') + (
        "\t// the barrage call as it opens fire (its GrenadeThrow lines): about one shot in three (checked per bolt)\n"
        "\toverride void HCE_OnShot(Actor shot) { super.HCE_OnShot(shot); HCE_Say('GrenadeThrow', 0.04, 35 * 4); }\n"
        "\t// no death animation: it blows apart (HCE_ShatterBody), the pieces cut from its own model\n"
        "\toverride String HCE_ModelPath() { return \"models/hce/Artybug\"; }\n"
        "\toverride Name HCE_ModelFile() { return 'Artybug.iqm'; }\n")
    BOSS_ALIASES['HCE_BossArachnotronArtybug'] = ('HCE_Artybug', 'Arachnotron', 2.0)   # the Arachnotrons' stand-in (MAP07)
    BLOOD['Artybug'] = 'FF8C1A'            # its blood is the Hunters' (Mercury Rising's own damage effects)
    CHAR_OVERRIDES['Artybug'] = dict(stance='pistol', radius_fixed=30, height_fixed=52, melee=(56, 60),
                                     flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Evades'])
if 'Draeth' in MR_CHARS:
    BLOOD['Draeth'] = '1FA055'            # emerald green: a colour of their own among the Covenant races
    # their own voice (voice_extra/Reaver, Black Mesa's Alien Grunt: growls, roars, pain and death cries, no words) and heavy steps (reaver_steps/,
    # split_factions.py's 'reaver' footstep set)
    VOICES['Draeth'] = 'Reaver'
    BASE_CODE['Draeth'] = BASE_CODE.get('Draeth', '') + "\toverride Name HCE_StepSet() { return 'reaver'; }    // the Reavers' own steps\n"
    HEAD_CLEAR['Draeth'] = HEAD_CLEAR['Elite']
    BESTIARY_GROUP['Draeth'] = 'Draeth (Reaver)'
    SHELL_TINT['Draeth'] = SHELL_TINT['Elite']   # the shielded ranks' (Commanders', Zealots') flare: the Covenant's blue
BESTIARY_RANK_GROUP += (('MarineFieldMedic', 'Field Medic'),)
MAIN['late_chars'] = MAIN['late_chars'] + [c for c in MR_CHARS if c not in NO_RANDOM]
MAIN['late_order'] = MAIN['late_order'] + MR_ORDER

# Shigure's Marine rifleman (extract_shigure_marine.py: from Sabopool's Halo CE Overhaul 2.0, his armour brown and his
# hands in the ODST's gloves), a whole body on the CE Marine like the field medic: a Marine like the others (their AI,
# voices, arsenal and pick-ups), with the assault rifle, the battle rifle or the shotgun (HCE_MarineRifleman<Gun>)
SHIGURE_GUNS = ('assault rifle', 'battle rifle', 'shotgun')
SHIGURE_ORDER = [cname(f'marine rifleman {g}') for g in SHIGURE_GUNS]
SHIGURE_CODE = MR_BODY_CODE.replace("(Mercury Rising's body: extract_mr_marines.py)", "(Shigure's body: extract_shigure_marine.py)") \
    % ("a rifleman in Shigure's armour", '', 'shigure_body')
for _g in SHIGURE_GUNS:
    _src = AI['variants'].get(f'characters\\marine\\marine {_g}')
    if not _src or not os.path.exists(f'{MARINE_KIT}/shigure_body.iqm'): continue
    _v = copy.deepcopy(_src); _v['_late'] = True
    _ov = dict(_v.get('_ov') or {})
    _ov['code'] = _ov.get('code', '') + SHIGURE_CODE
    _ov.setdefault('skin_as', cname(f'marine {_g}'))
    _v['_ov'] = _ov
    AI['variants'][f'characters\\marine\\marine rifleman {_g}'] = _v
BESTIARY_RANK_GROUP += (('MarineRifleman', 'Rifleman'),)
MAIN['late_order'] = MAIN['late_order'] + SHIGURE_ORDER

MAIN_WEAPONS |= set(WEAPONS)

# Texture size: body and armour skins are capped at SKIN_CAP px (the Draeth's, the Flood's and a few more came at 1024:
# at Doom's distances 512 reads the same and loads faster). Weapons, faces, visors and cube maps keep their size
SKIN_CAP = 512
SKIN_CAP_KEEP = ('face', 'visor', 'cube', 'glass', 'lens')       # file-name parts left at full size

def cap_skins(root):
    """every model texture under root/models wider or taller than SKIN_CAP shrunk to fit it (aspect kept), but those
    in a weapons folder or named with a SKIN_CAP_KEEP part; prints what it changed"""
    n = saved = 0
    for p in glob.glob(f'{root}/models/**/*.png', recursive=True):
        rel = os.path.relpath(p, root).lower()
        if '/weapons/' in rel or any(k in os.path.basename(rel) for k in SKIN_CAP_KEEP): continue
        with Image.open(p) as im:
            im.load()
            if max(im.size) <= SKIN_CAP: continue
            k = SKIN_CAP / max(im.size)
            before = os.path.getsize(p)
            im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS).save(p, optimize=True)
        n += 1; saved += before - os.path.getsize(p)
    if n: print(f'skins capped at {SKIN_CAP}px: {n} textures, {saved // 1024} KB smaller')


if __name__ == '__main__':
    build()
    cap_skins(PACK)
    # editor icons are taken by udb_icons.py from the built packs; a class added since has none until it is run again
    written = set(re.findall(r'\nclass (HCE_\w+)', open(f'{PACK}/ZScript/HaloCE/hce_enemies.zsc').read()))
    noicon = [c for c, _, _, _, spr in BESTIARY if not spr and c in written and not c.startswith('HCE_Variant')]
    if noicon: print(f'{len(noicon)} classes without an editor icon ({", ".join(noicon[:6])}{", ..." if len(noicon) > 6 else ""}): run udb_icons.py --missing, then build again', file=sys.stderr)
