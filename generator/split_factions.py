"""Split the generated pack/ tree into a shared core + one pk3 source tree per faction.

  core       ZScript projectiles + replacement handler, CVARINFO, SNDINFO aliases, the HCEM sprite,
             MAPINFO event handler.  No Halo assets: safe to ship publicly.
  covenant   Grunts, Jackals, Elites, Hunters (+ Doom boss stand-ins)
  flood      infection, carrier and combat forms
  sentinels  Sentinels
  marines    Marines (Doom's marines and allied monsters become these)

Every faction pack only needs the core (and the enemy API addon); load any combination.
DoomEdNums are unchanged: each pack lists the numbers of its own classes."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, re, shutil, sys
import json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pack import PACK, TEAM

OUTDIR = os.environ.get('HCE_FACTIONS', os.path.join(os.path.dirname(PACK), 'factions'))
from build_pack import OUT
GORE = f'{OUT}/gore'                 # extract_halo_gore.py: the Covenant pack's NashGore patch
FACTION = {'COVENANT': 'covenant', 'FLOOD': 'flood', 'SENTINEL': 'sentinels', 'HUMAN': 'marines'}
TITLE = {'covenant': 'Covenant: Grunts, Jackals, Elites, Hunters', 'flood': 'Flood: infection, carrier and combat forms',
         'sentinels': 'Sentinels', 'marines': 'Marines'}
VERSION = 'version "4.15.1"\n'


def shard_texture(path):
    """a shard of glass: an irregular pale sliver, brighter at its edges, transparent around it"""
    from PIL import Image, ImageDraw, ImageFilter
    os.makedirs(os.path.dirname(path), exist_ok=True)
    S = 64
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pts = [(30, 2), (58, 40), (36, 61), (8, 47), (20, 22)]
    d.polygon(pts, fill=(170, 215, 255, 150))
    d.line(pts + [pts[0]], fill=(235, 248, 255, 255), width=3)
    d.line([(30, 2), (36, 61)], fill=(220, 240, 255, 200), width=1)       # a crack across it
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(path)


def glow_texture(path):
    """a soft white glow (a bright heart fading out to nothing): the Covenant muzzle flashes' and plasma bolts' halos,
    drawn as textured particles so they are round whatever the player's particle style"""
    import numpy as np
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    S = 64
    y, x = np.mgrid[0:S, 0:S]; r = np.hypot(x - (S - 1) / 2, y - (S - 1) / 2) / (S / 2)
    a = np.clip(1 - r, 0, 1) ** 2.2 * 0.85 + np.clip(1 - r * 3.0, 0, 1) ** 1.5 * 0.15
    im = np.zeros((S, S, 4), np.uint8); im[..., :3] = 255; im[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(im, 'RGBA').save(path)


def chunks(text):
    """split a generated ZScript file into (class name, parent, text) pieces (leading // comments kept)"""
    out = []
    pos = [m.start() for m in re.finditer(r'^(?://[^\n]*\n)*class ', text, re.M)]
    for i, p in enumerate(pos):
        body = text[p:pos[i + 1] if i + 1 < len(pos) else len(text)]
        m = re.search(r'^class (\w+)(?:\s*:\s*(\w+))?', body, re.M)
        out.append((m.group(1), m.group(2), body))
    return out

HEALTHBAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hud_healthbar')   # CE_HB1..9 from HDE
# the Master Chief's squad-order lines (file 'Follow Me 3.mp3' -> HCE/Chief/FollowMe), shipped in the Marines pack
CHIEF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chief_commands')
# Halo 2's footsteps (extract_footsteps.py): the sets each faction's bodies use (Jackals step as Grunts, Hunters as
# Brutes, the Flood's combat forms as the body they were)
from build_pack import OUT as _OUT
STEPS = f'{_OUT}/footsteps'
# Halo 2's jump pack (extract_h2_jetpack_sound.py): the Elite Rangers' HCE/Jetpack/In, Loop and Out
JETPACK = f'{_OUT}/sounds/H2Jetpack'
# the Flood's voices (build_pack.VOICES): event -> the sound sets it draws from (extract_spv3.flood_sounds' index keys)
FLOOD_SOUNDS = f'{_OUT}/sounds/Flood'
_GROWL = ['flood_flood_idle_combat', 'flood_new_combat']
def _combat():
    """a Flood combat form's voice (Halo CE's flood set and Ruby's flood_new set)"""
    return {'Alert': _GROWL, 'FoundFoe': _GROWL, 'HeardGunfire': _GROWL, 'Taunt': _GROWL, 'KillPlayer': _GROWL,
            'Idle': ['flood_flood_idle_noncombat', 'flood_new_noncombat'],
            'Charge': ['flood_new_berserk', 'flood_leap'], 'Berserk': ['flood_new_berserk'], 'Advance': ['flood_new_berserk'],
            'Melee': ['flood_melee', 'flood_new_melee'],
            'Pain': ['flood_pain', 'flood_new_pain'], 'PainMed': ['flood_pain', 'flood_new_pain'], 'PainHeavy': ['flood_new_pain'],
            'Wounded': ['flood_new_pain'], 'OnFire': ['flood_combat_elite_stand_pistol_onfire', 'flood_new_pain'],
            'Stuck': ['flood_new_pain'], 'Death': ['flood_death', 'flood_new_death'], 'DeathHard': ['flood_new_death']}
_CARRIER = {'Alert': ['carrier_idle', 'carrier_idle_27'], 'Taunt': ['carrier_idle', 'carrier_idle_27'],
            'Idle': ['carrier_idle'], 'Death': ['carrier_carrier_die'], 'DeathHard': ['carrier_carrier_die'],
            'Pop': ['carrier_carrier_boom']}
FLOOD_EVENTS = {
    'Flood': _combat(),
    'FloodElite': _combat(),
    'FloodInfection': {'Alert': ['infection_move'], 'Taunt': ['infection_move'], 'Charge': ['infection_move'],
                       'Melee': ['infection_stand_unarmed_melee'], 'Feed': ['infection_stand_unarmed_feeding'],
                       'Death': ['infection_die', 'infection_form_death'], 'DeathHard': ['infection_die', 'infection_form_death'],
                       'Pop': ['infection_die', 'infection_form_death']},
    'FloodCarrier': _CARRIER,
    # the XAM Flood Grunt: its own attack shriek, and the carrier's gurgles and burst
    'FloodGrunt': dict(_CARRIER, Alert=['grunt_attack'], Charge=['grunt_attack'], Melee=['grunt_attack'], Berserk=['grunt_attack'],
                       Taunt=['grunt_attack', 'carrier_idle']),
}
# the Sentinel Knights' voice (REV's lines, 'Kill Brute 3.ogg' -> HCE/SentinelKnight/KillBrute), shipped in the Sentinels
# pack and played by the Knight's HCE_Say (sentinel_knight.zs), which turns a sighting or a kill into the line for that
# kind of target. Each line is downmixed to mono so it comes from the Knight. Line set -> the events it plays for: the
# player is spotted by his HDE Spartan class (SpotSpartanII/III/IV: that class's lines, weighted twice, and the plain
# Player (Enemy) ones; SpotPlayer for Doom's marine)
KNIGHT_VOICES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knight_voices')
KNIGHT_LINES = {'Carrier form about to blow Call out': ['CarrierBlow'], 'Kill Brute': ['KillBrute'],
                'Kill Combat Form': ['KillCombatForm'], 'Kill Elite': ['KillElite'], 'Kill Flood (Generic)': ['KillFlood'],
                'Kill Grunt': ['KillGrunt'], 'Kill Heavy Unit': ['KillHeavy'], 'Kill Human': ['KillHuman'],
                'Kill Jackal': ['KillJackal'], 'Level start (First flood level)': ['FirstFlood'],
                'Plasma Stuck': ['PlasmaStuck'], 'Sanitize dead Flood': ['SanitizeFlood'], 'Search': ['Search'],
                'Spot Covenant': ['SpotCovenant'], 'Spot Drinol': ['SpotDrinol'], 'Spot Flood': ['SpotFlood'],
                'Spot Grenade': ['SpotGrenade'], 'Spot Human (Enemy)': ['SpotHuman'], 'Spot Hunter': ['SpotHunter'],
                'Spot Player (Ally)': ['SpotPlayerAlly'],
                'Spot Player (Enemy)': ['SpotPlayer', 'SpotSpartanII', 'SpotSpartanIII', 'SpotSpartanIV'],
                'Spot Player Spartan II (Enemy)': ['SpotSpartanII'] * 2, 'Spot Player Spartan III (Enemy)': ['SpotSpartanIII'] * 2,
                'Spot Player Spartan IV (Enemy)': ['SpotSpartanIV'] * 2}


def knight_voice(d):
    """the Knights' lines -> d/sounds/hce_knight (mono) and d/sndinfo.knight"""
    import subprocess
    os.makedirs(f'{d}/sounds/hce_knight', exist_ok=True)
    out = ["// the Sentinel Knights' voice (REV): HCE/SentinelKnight/<event> as the Knight's HCE_Say plays them"]
    ev = {}
    for fn in sorted(os.listdir(KNIGHT_VOICES)):
        m = re.match(r'(.+?)(?: (\d+))?\.ogg$', fn)
        if not m or m.group(1) not in KNIGHT_LINES: continue
        leaf = re.sub(r'\W+', '_', m.group(1).lower()).strip('_') + (f'_{m.group(2)}' if m.group(2) else '')
        dst = f'sounds/hce_knight/{leaf}.ogg'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{KNIGHT_VOICES}/{fn}', '-ac', '1', '-c:a', 'libvorbis', '-q:a', '5',
                        f'{d}/{dst}'], check=True)
        out.append(f'HCE/KnightSnd/{leaf} "{dst}"')
        for e in KNIGHT_LINES[m.group(1)]: ev.setdefault(e, []).append(f'HCE/KnightSnd/{leaf}')
    for e, ids in sorted(ev.items()): out.append(f'$random HCE/SentinelKnight/{e} {{ {" ".join(ids)} }}')
    open(f'{d}/sndinfo.knight', 'w').write('\n'.join(out) + '\n')


STEP_SETS = {'covenant': ['elite', 'grunt', 'brute'], 'marines': ['marine'], 'flood': ['marine', 'elite']}
CHIEF_LINES = {'follow me': 'FollowMe', 'hold fire': 'HoldFire', 'open fire': 'OpenFire', 'focus single enemy': 'Focus',
               'focus': 'Focus', 'suppress': 'Suppress', 'medic': 'Medic', 'weapon order': 'Weapon', 'weapon': 'Weapon',
               'hold position': 'HoldPosition', 'pressbutton': 'PressButton', 'press button': 'PressButton',
               'regroup': 'Regroup'}

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
            m = re.fullmatch(r'HCE_(\w+)BubbleShell', cls)             # a Sentinel's shield bubble flare
            if m and m.group(1) in TEAM: char_of[cls] = m.group(1)
            if cls.endswith('BodyShieldShell'):          # a Halo 2 body's flare (HCE_<char><piece>ShieldShell): its Elite's pack
                ch = max((c for c in TEAM if cls.startswith(f'HCE_{c}')), key=len, default=None)
                if ch: char_of[cls] = ch
            m = re.fullmatch(r'(HCE_\w+)Blade', cls)              # a cloaked sword Elite's blade copy: its Elite's pack
            if m and m.group(1) in char_of: char_of[cls] = char_of[m.group(1)]
    fac_of = {c: FACTION[TEAM[ch]] for c, ch in char_of.items()}
    missing = [c for c, _, _ in parts if c not in fac_of]
    assert not missing, missing
    facs = sorted(set(fac_of.values()))
    # ---------------- core
    core = f'{OUTDIR}/core'
    os.makedirs(f'{core}/ZScript/HaloCE')
    for f in ('hce_projectiles.zsc', 'hce_explosives.zsc', 'hce_core.zsc', 'hce_handler.zsc', 'hce_hde.zsc', 'hce_variants.zsc', 'hce_bestiary.zsc'):
        shutil.copy(f'{PACK}/ZScript/HaloCE/{f}', f'{core}/ZScript/HaloCE/{f}')
    for f in ('cvarinfo.txt', 'sndinfo.hce'):
        shutil.copy(f'{PACK}/{f}', f'{core}/{f}')
    shutil.copytree(f'{PACK}/sprites', f'{core}/sprites', ignore=shutil.ignore_patterns('udb'))   # (the UDB icons: per faction, below)
    open(f'{core}/zscript.txt', 'w').write(VERSION + '\n// Halo CE enemies, core: shared projectiles and the Doom-monster replacement handler.\n'
        '// Needs HaloDoom_EnemyBase from HCE_EnemyAPI_LocalDEV.pk3 (loaded before this file); add any faction packs after it.\n'
        '#include "ZScript/HaloCE/hce_explosives.zsc"\n#include "ZScript/HaloCE/hce_core.zsc"\n#include "ZScript/HaloCE/hce_projectiles.zsc"\n#include "ZScript/HaloCE/hce_handler.zsc"\n#include "ZScript/HaloCE/hce_variants.zsc"\n#include "ZScript/HaloCE/hce_bestiary.zsc"\n#include "ZScript/HaloCE/hce_hde.zsc"\n')
    # the HCEVARS variant things (hce_variants.zsc): DoomEdNums 30900-30931
    open(f'{core}/mapinfo.txt', 'w').write('GameInfo\n{\n\tAddEventHandlers = "HCE_ReplaceHandler", "HCE_MissileTracker", "HCE_SpawnAllHandler", "HCE_SquadWheel", "HCE_Encounters"\n}\n\n'
        'DoomEdNums\n{\n' + ''.join(f'\t{30900 + n} = HCE_Variant{n}\n' for n in range(32)) + '}\n')
    # enemy laser tracers (HCE_EnemyLaser, in the API): HaloDoom Evolved's own beam model and texture
    open(f'{core}/modeldef.hce_lasers', 'w').write('// enemy laser tracers: HaloDoom Evolved\'s laser beam model (Models/Lasers, in HDE)\n'
        'Model HCE_EnemyLaser\n{\n\tModel 0 "Models/Lasers/beam_simple.md3"\n\tSkin 0 "Models/Lasers/BEAM_detailed.png"\n'
        '\tUSEACTORPITCH\n\tFrameIndex HCEM A 0 0\n}\n')
    # Options > Halo CE Gore: blood on the body (hce_bodyblood, blood_kit.py's overlays), off by default
    shutil.copy(f'{PACK}/menudef.hce', f'{core}/menudef.hce')      # pack/menudef.hce: Options > Halo CE AI / Gore / Performance
    shard_texture(f'{core}/graphics/HCESHARD.png')                  # the shield's glass shards (HCE_ShieldShatter)
    glow_texture(f'{core}/graphics/HCEGLOW.png')                    # the Covenant muzzle flashes' and bolts' glow
    # console command: punkassbitches -> one of every loaded enemy in a line (HCE_SpawnAllHandler)
    open(f'{core}/keyconf.txt', 'w').write('// Halo CE enemies: "punkassbitches" spawns one of every loaded enemy in a line in front of you,\n'
                                          '// "leatherneck" one of every loaded Marine (pinned to their spots), "leatherneck2" the same\n'
                                          '// Marines free to move (they follow you and take orders), "helljumpers" one of every ODST, "reclaimer" one of every\n'
                                          '// Sentinel\n'
                                          'alias punkassbitches "netevent hce_spawnall"\nalias leatherneck "netevent hce_spawnmarines"\n'
                                          'alias leatherneck2 "netevent hce_spawnmarines2"\nalias helljumpers "netevent hce_spawnodsts"\n'
                                          'alias reclaimer "netevent hce_spawnsentinels"\n'
                                          'alias hce_bestiary "openmenu HCE_Bestiary"\n'
                                          '\n// squad orders to the Marines following you (Options > Customize Controls > Halo CE Squad): every order is on\n'
                                          '// the order wheel (hold its key, point with the mouse, let go); only the combat orders have keys of their own.\n'
                                          '// The rest stay bindable from the console (bind <key> hce_regroup, and so on)\n'
                                          'alias +hce_wheel "event hce_wheel_open"\nalias -hce_wheel "event hce_wheel_close"\n'
                                          'alias hce_follow "netevent hce_squad 0"\nalias hce_hold "netevent hce_squad 1"\nalias hce_regroup "netevent hce_squad 2"\n'
                                          'alias hce_holdfire "netevent hce_squad 3"\nalias hce_openfire "netevent hce_squad 4"\nalias hce_focus "netevent hce_squad 5"\n'
                                          'alias hce_suppress "netevent hce_squad 6"\nalias hce_medic "netevent hce_squad 7"\nalias hce_weapon "netevent hce_squad 8"\n'
                                          'alias hce_button "netevent hce_squad 9"\n'
                                          'addkeysection "Halo CE Squad" hce_squad\n'
                                          'addmenukey "Squad: order wheel (hold)" +hce_wheel\n'
                                          'addmenukey "Squad: open fire" hce_openfire\naddmenukey "Squad: hold fire" hce_holdfire\n'
                                          'addmenukey "Squad: focus on my target" hce_focus\naddmenukey "Squad: suppress" hce_suppress\n'
                                          'addmenukey "Squad: medic" hce_medic\n')
    # ---------------- factions
    md = open(f'{PACK}/modeldef.hce').read()
    blocks = {re.match(r'Model (\w+)', b).group(1): b for b in re.findall(r'Model \w+\n\{.*?\n\}\n', md, re.S)}
    ed = re.findall(r'^\t(\d+) = (\w+)$', open(f'{PACK}/mapinfo.txt').read(), re.M)
    gl = open(f'{PACK}/gldefs.hce').read()
    bms = re.findall(r'brightmap texture "([^"]+)"\n\{\n\tmap "[^"]+"\n\}', gl)
    bmap = dict(re.findall(r'brightmap texture "([^"]+)"\n\{\n\tmap "([^"]+)"\n\}', gl))   # each texture's own brightmap (the full one or a glow map)
    camo = re.findall(r'HardwareShader Texture "([^"]+)"', gl)
    shields = re.findall(r'material texture "([^"]+)"\n\{\n\tshader "shaders/hce_shield.fp"', gl)
    swords = re.findall(r'material texture "([^"]+)"\n\{\n\tshader "shaders/hce_sword.fp"', gl)
    bubbles = re.findall(r'material texture "([^"]+)"\n\{\n\tshader "shaders/hce_bubble.fp"', gl)
    visors = re.findall(r'material texture "([^"]+)"\n\{\n\tshader "shaders/hce_visor.fp"\n\ttexture tex_cube "([^"]+)"', gl)
    # the Sentinel Knights' energy cores (build_pack.knight_skin): the core shader, its brightmap and cube map
    cores = re.findall(r'material texture "([^"]+)"\n\{\n\tshader "shaders/hce_core.fp"\n\tbrightmap "([^"]+)"\n\ttexture tex_cube "([^"]+)"', gl)
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
        # this faction's bestiary entries and the lore they use (build_pack.bestiary_lump)
        if os.path.exists(f'{PACK}/bestiary.txt'):
            rows = [l.rstrip('\n').split('\t') for l in open(f'{PACK}/bestiary.txt') if l[:2] in ('E\t', 'L\t')]
            ents = [r for r in rows if r[0] == 'E' and r[1] in fac_of and fac_of[r[1]] == fac]
            keys = {k for r in ents for k in r[6].split(',')}
            if ents:
                open(f'{d}/hcebest.{fac}', 'w').write('// the Halo CE enemies bestiary (hce_bestiary.zsc)\n' + ''.join(
                    '\t'.join(r) + '\n' for r in ents + [r for r in rows if r[0] == 'L' and r[1] in keys]))
        # this faction's Ultimate Doom Builder icons (build_pack.ship_udb_icons: sprites/udb/HUxxA0.png)
        import build_pack as _bp
        for c, _, _ in mine:
            spr = _bp.udb_sprites().get(c)
            if spr and os.path.exists(f'{PACK}/sprites/udb/{spr}A0.png'):
                os.makedirs(f'{d}/sprites/udb', exist_ok=True)
                shutil.copy(f'{PACK}/sprites/udb/{spr}A0.png', f'{d}/sprites/udb/{spr}A0.png')
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
        # Elefant's Marine kit: attachments the Marines pick from at run time (build_pack.marine_kit_code)
        for dn in sorted(set(re.findall(r'A_ChangeModel\([^;]*?"(models/[^"]+/(?:MarineKit|EliteKit))"', ztxt))):
            if os.path.isdir(f'{PACK}/{dn}'):
                for fn in os.listdir(f'{PACK}/{dn}'): need.add(f'{dn}/{fn}')
        for f in sorted(need):
            os.makedirs(os.path.dirname(f'{d}/{f}'), exist_ok=True)
            shutil.copy(f'{PACK}/{f}', f'{d}/{f}')
        mybms = [t for t in bms if t in need]
        mycamo = [t for t in camo if t in need]
        myshields = [t for t in shields if t in need]
        myswords = [t for t in swords if t in need]
        mybubbles = [t for t in bubbles if t in need]
        myvisors = [(t, c) for t, c in visors if t in need]
        mycores = [(t, b, c) for t, b, c in cores if t in need]
        if mybms or mycamo or myshields or myswords or myvisors or mycores or mybubbles:
            out = [f'// Halo CE enemies, {fac}: glowing surfaces' + (', active camo shimmer' if mycamo else '')]
            if mybms or myshields or myswords or mybubbles:
                shutil.copy(f'{PACK}/models/hce/brightmap_full.png', f'{d}/models/hce/brightmap_full.png')
                for t in mybms:
                    bm = bmap.get(t, 'models/hce/brightmap_full.png')
                    if not bm.endswith('brightmap_full.png'):
                        os.makedirs(os.path.dirname(f'{d}/{bm}'), exist_ok=True); shutil.copy(f'{PACK}/{bm}', f'{d}/{bm}')
                    else: bm = 'models/hce/brightmap_full.png'
                    out.append(f'brightmap texture "{t}"\n{{\n\tmap "{bm}"\n}}')
            if mycamo:
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_camo.fp', f'{d}/shaders/hce_camo.fp')
                out += [f'HardwareShader Texture "{t}"\n{{\n\tShader "shaders/hce_camo.fp"\n\tSpeed 1.0\n}}' for t in mycamo]
            if myshields:                      # the Jackals' animated energy shields
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_shield.fp', f'{d}/shaders/hce_shield.fp')
                out += [f'material texture "{t}"\n{{\n\tshader "shaders/hce_shield.fp"\n\tspeed 1.0\n\tbrightmap "models/hce/brightmap_full.png"\n}}' for t in myshields]
            if mybubbles:                      # the Sentinels' shield bubbles
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_bubble.fp', f'{d}/shaders/hce_bubble.fp')
                out += [f'material texture "{t}"\n{{\n\tshader "shaders/hce_bubble.fp"\n\tspeed 1.0\n\tbrightmap "models/hce/brightmap_full.png"\n}}' for t in mybubbles]
            if myswords:                       # the energy sword's blade
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_sword.fp', f'{d}/shaders/hce_sword.fp')
                out += [f'material texture "{t}"\n{{\n\tshader "shaders/hce_sword.fp"\n\tspeed 1.0\n\tbrightmap "models/hce/brightmap_full.png"\n}}' for t in myswords]
            if myvisors:                       # the ODSTs' and kit helmets' visors: the cube-map reflection shader and its cube map
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_visor.fp', f'{d}/shaders/hce_visor.fp')
                for t, c in myvisors:
                    os.makedirs(os.path.dirname(f'{d}/{c}'), exist_ok=True); shutil.copy(f'{PACK}/{c}', f'{d}/{c}')
                    out.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_visor.fp"\n\ttexture tex_cube "{c}"\n}}')
            if mycores:                        # the Sentinel Knights' cores: the energy shader, brightmap and cube map
                os.makedirs(f'{d}/shaders', exist_ok=True)
                shutil.copy(f'{PACK}/shaders/hce_core.fp', f'{d}/shaders/hce_core.fp')
                for t, b, c in mycores:
                    for f in (b, c):
                        os.makedirs(os.path.dirname(f'{d}/{f}'), exist_ok=True); shutil.copy(f'{PACK}/{f}', f'{d}/{f}')
                    out.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_core.fp"\n\tbrightmap "{b}"\n\ttexture tex_cube "{c}"\n}}')
            open(f'{d}/gldefs.hce_{fac}', 'w').write('\n'.join(out) + '\n')
        mynums = [(n, c) for n, c in ed if fac_of.get(c) == fac]
        mi = 'DoomEdNums\n{\n' + ''.join(f'\t{n} = {c}\n' for n, c in mynums) + '}\n'
        if fac == 'marines' and os.path.isdir(HEALTHBAR):
            # Halo CE's health bar (HaloDoom Evolved's CE HUD art) for the name / health overlay over a Marine
            os.makedirs(f'{d}/graphics/hce/healthbar', exist_ok=True)
            for fn in sorted(os.listdir(HEALTHBAR)): shutil.copy(f'{HEALTHBAR}/{fn}', f'{d}/graphics/hce/healthbar/{fn}')
        if fac == 'marines' and os.path.isdir(CHIEF):
            # the Master Chief's squad orders (HCE_SpawnAllHandler.SquadOrder plays them on the player)
            os.makedirs(f'{d}/sounds/hce_chief', exist_ok=True)
            groups = {}
            for fn in sorted(os.listdir(CHIEF), key=lambda f: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', f)]):
                m = re.fullmatch(r'(.+?) (\d+)\.(mp3|ogg|wav|flac)', fn, re.I)
                if not m or m.group(1).lower() not in CHIEF_LINES: continue
                key = CHIEF_LINES[m.group(1).lower()]
                dst = f'sounds/hce_chief/{key.lower()}_{int(m.group(2))}.{m.group(3).lower()}'
                shutil.copy(f'{CHIEF}/{fn}', f'{d}/{dst}')
                groups.setdefault(key, []).append(dst)
            out = ['// the Master Chief\'s squad orders (the Halo CE Squad keys)']
            for key, files in sorted(groups.items()):
                ids = [f'HCE/Chief/{key}/{i}' for i in range(len(files))]
                out += [f'{sid} "{f}"' for sid, f in zip(ids, files)]
                out.append(f'$random HCE/Chief/{key} {{ {" ".join(ids)} }}')
            open(f'{d}/sndinfo.chief', 'w').write('\n'.join(out) + '\n')
        if fac in STEP_SETS and os.path.exists(f'{STEPS}/index.json'):
            # footsteps: HCE/Step/<set>/<surface>_<walk|run>, one a stride (HaloDoom_EnemyBase.HCE_StepTick)
            idx = json.load(open(f'{STEPS}/index.json'))
            out = ["// Halo 2's footsteps (extract_footsteps.py): HCE/Step/<set>/<surface>_<walk|run>"]
            for st in STEP_SETS[fac]:
                for key, files in sorted(idx.get(st, {}).items()):
                    ids = []
                    for k, fn in enumerate(files):
                        dst = f'sounds/hce_steps/{fn}'
                        os.makedirs(os.path.dirname(f'{d}/{dst}'), exist_ok=True)
                        shutil.copy(f'{STEPS}/{fn}', f'{d}/{dst}')
                        ids.append(f'HCE/Step/{st}/{key}/{k}')
                        out.append(f'{ids[-1]} "{dst}"')
                    out.append(f'$random HCE/Step/{st}/{key} {{ {" ".join(ids)} }}')
            open(f'{d}/sndinfo.steps', 'w').write('\n'.join(out) + '\n')
        if fac == 'sentinels' and os.path.isdir(KNIGHT_VOICES) and any('SentinelKnight' in c for c, _, _ in mine):
            knight_voice(d)
        if fac == 'flood' and os.path.exists(f'{FLOOD_SOUNDS}/index.json'):
            idx = json.load(open(f'{FLOOD_SOUNDS}/index.json'))
            os.makedirs(f'{d}/sounds/hce_flood', exist_ok=True)
            out = ["// the Flood's voices and effects (extract_spv3.flood_sounds: Halo CE's and Ruby's Rebalance's, from its c40):",
                   "// HCE/<voice>/<event> as HCE_Say plays them, and each form's Pop (HCE_PopSound)"]
            ids = {}
            for key, files in sorted(idx.items()):
                k = re.sub(r'\W+', '_', key)
                for n, fn in enumerate(files):
                    shutil.copy(f'{FLOOD_SOUNDS}/{fn}', f'{d}/sounds/hce_flood/{fn}')
                    ids.setdefault(key, []).append(f'HCE/FloodSnd/{k}/{n}')
                    out.append(f'{ids[key][-1]} "sounds/hce_flood/{fn}"')
            for voice, events in FLOOD_EVENTS.items():
                for ev, keys in events.items():
                    pick = [i for key in keys for i in ids.get(key, [])]
                    if pick: out.append(f'$random HCE/{voice}/{ev} {{ {" ".join(pick)} }}')
            out += ['$volume HCE/FloodCarrier/Pop 0.9', '$rolloff HCE/FloodCarrier/Pop 200 1600', '$rolloff HCE/FloodGrunt/Pop 200 1400']
            open(f'{d}/sndinfo.flood', 'w').write('\n'.join(out) + '\n')
        if fac == 'covenant' and os.path.exists(f'{JETPACK}/loop.ogg'):
            os.makedirs(f'{d}/sounds/hce_jetpack', exist_ok=True)
            out = ["// Halo 2's jump pack (extract_h2_jetpack_sound.py): the Elite Rangers (HCE_TryJet, HCE_JumpTick)"]
            for leaf in ('in', 'loop', 'out'):
                shutil.copy(f'{JETPACK}/{leaf}.ogg', f'{d}/sounds/hce_jetpack/{leaf}.ogg')
                out.append(f'HCE/Jetpack/{leaf.capitalize()} "sounds/hce_jetpack/{leaf}.ogg"')
            out += ['$volume HCE/Jetpack/Loop 0.7', '$rolloff HCE/Jetpack/In 200 1400', '$rolloff HCE/Jetpack/Loop 200 1200',
                    '$rolloff HCE/Jetpack/Out 200 1200']
            open(f'{d}/sndinfo.jetpack', 'w').write('\n'.join(out) + '\n')
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
