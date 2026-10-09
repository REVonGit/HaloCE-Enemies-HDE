"""Generate the Halo CE enemy pack: ZScript classes, MODELDEF, skins, projectiles."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, re, math, shutil, glob, zipfile, sys
import numpy as np
from PIL import Image

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
    E = 'characters\\elite\\elite major\\elite major '
    base, fr = variants.get(E + 'plasma rifle'), variants.get('characters\\grunt\\grunt specops fuel rod')
    if not (base and fr) or (E + 'fuel rod') in variants: return
    import copy
    v = copy.deepcopy(base)
    v['ranged_combat'] = copy.deepcopy(fr['ranged_combat'])
    v['_late'] = True
    variants[E + 'fuel rod'] = v

add_fuel_rod_elite(AI['variants'])

# More Grunt ranks (new): Halo 2's Ultra (grunt_ultra: white armour, the toughest of the regular Grunts) with the
# needler or the plasma pistol, and the Heavy (Halo 2's grunt_heavy, in Halo 3's green) with the fuel rod on the Spec
# Ops body (the one with the fuel rod model). Ultras fight like Majors with a third more health; Heavies like the
# Spec Ops fuel-rod Grunts.
GRUNT_RANKS = {'ultra': ((0.86, 0.88, 0.92), (0.70, 0.72, 0.78)), 'heavy': ((0.30, 0.52, 0.14), (0.20, 0.38, 0.08))}
def add_grunt_ranks(variants):
    import copy
    G = 'characters\\grunt\\grunt '
    def colour(v, lo_hi):
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
    base = variants.get(G + 'specops fuel rod')
    if base and (G + 'heavy fuel rod') not in variants:
        v = copy.deepcopy(base)
        colour(v, GRUNT_RANKS['heavy'])
        v['_rank'] = 'heavy'; v['_late'] = True
        variants[G + 'heavy fuel rod'] = v

add_grunt_ranks(AI['variants'])

# Elite Heavy (new): a green rank between the Major and the Commander, carrying heavier guns: the fuel rod (in Halo 2's
# fuel-rod stance), the plasma rifle and the needler. 125 body and a 200-point shield (the Spec Ops Elite's), the
# Major's combat data
HEAVY_GREEN = (0.16, 0.36, 0.10)
def add_elite_heavy(variants):
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

# Beam-rifle Spec Ops Elite (new): the Spec Ops plasma-rifle Elite's stats with Halo 2's beam rifle, in Halo 2's own
# Elite rifle stance (h2_elite_anims.py), fighting from further back
def add_beam_rifle_specops(variants):
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
    pins = json.load(open(PINS_PATH)) if os.path.exists(PINS_PATH) else {}
    used = set(pins.values())
    out = []
    for n, cls in ednums:
        if cls in pins: out.append((pins[cls], cls)); continue
        while n in used: n += 1
        used.add(n); out.append((n, cls))
    return sorted(out)
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
TEAM = {'Grunt': 'COVENANT', 'GruntSpecOps': 'COVENANT', 'Jackal': 'COVENANT', 'JackalMajor': 'COVENANT',
        'Elite': 'COVENANT', 'EliteSpecial': 'COVENANT', 'Hunter': 'COVENANT', 'FloodInfection': 'FLOOD',
        'FloodCarrier': 'FLOOD', 'FloodElite': 'FLOOD', 'FloodHuman': 'FLOOD', 'Sentinel': 'SENTINEL',
        'Marine': 'HUMAN', 'MarineArmored': 'HUMAN', 'MarineODST': 'HUMAN'}

# Halo weapon -> (pack projectile class, HDE base class, Halo impact damage, Halo projectile speed WU/tick)
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
}
FIRE_CODE = {'plasma pistol': 'pp', 'plasma rifle': 'pr', 'needler': 'ne', 'fuel rod': 'fr', 'hunter fuel rod': 'fr',
             'assault rifle': 'ar', 'shotgun': 'sg', 'pistol': 'hp', 'sniper rifle': 'sr'}
# Fire patterns (Doom-paced; Halo's per-variant numbers only stretch them):
# weapon: (shots min, shots max, tics between shots, pause min s, pause max s,
#          overcharge wind-up tics, scale shots with Halo burst length,
#          Halo baseline separation s, Halo baseline burst s)
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
}
# HDE SNDINFO names: fire, fire bass, special (overcharge / loop end), charge (overcharge / loop start), looping
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
    'rocket launcher': (W + 'RocketLauncher/Fire', W + 'RocketLauncher/Fire/Bass', '', '', False),
    'flamethrower':    (W + 'Flamer/Fire/Loop', '', W + 'Flamer/Fire/End', W + 'Flamer/Fire/Start', True),
    'plasma caster':   (W + 'PlasmaCaster/Fire', '', W + 'PlasmaCaster/ChargedFire', W + 'PlasmaCaster/ChargeBegin', False),
    'sentinel beam':   (W + 'SentinelBeam/Fire/Loop', '', W + 'SentinelBeam/Fire/End', W + 'SentinelBeam/Fire/Begin', True),
}
# Halo-style drops: HDE Local_DEV pickup classes (Covenant always drop theirs, the energy sword included -- HDE has
# one to pick up; Hunters' fuel rod arms and Sentinels drop nothing)
DROP_WEAPON = {'energy sword': 'Halo_EnergySword', 'plasma pistol': 'Halo_PlasmaPistol', 'plasma rifle': 'Halo_PlasmaRifle', 'needler': 'Halo_Needler',
               'fuel rod': 'Halo_FuelRod', 'assault rifle': 'Halo_MA5B', 'pistol': 'Halo_Magnum', 'shotgun': 'Halo_Shotgun',
               'sniper rifle': 'Halo_SniperRifle', 'rocket launcher': 'Halo_RocketLauncher', 'flamethrower': 'Halo_Flamethrower'}
# Doom boss stand-ins: unique subclasses so CheckReplacee can map them back to the Doom boss
# (A_BossDeath map specials: E1M8/E4M6 Barons, MAP07 Mancubi/Arachnotrons, Cyberdemon/Spider levels)
BOSS_ALIASES = {  # alias class: (base class, Doom class, health multiplier)
    'HCE_BossBaronEliteMajorPlasmaRifle': ('HCE_EliteMajorPlasmaRifle', 'BaronOfHell', 1.5),
    'HCE_BossBaronEliteMajorNeedler': ('HCE_EliteMajorNeedler', 'BaronOfHell', 1.5),
    'HCE_BossFatsoHunter': ('HCE_Hunter', 'Fatso', 1.0),
    'HCE_BossArachnotronEliteSpecopsPlasmaRifle': ('HCE_EliteSpecopsPlasmaRifle', 'Arachnotron', 1.0),
    'HCE_BossArachnotronEliteSpecopsNeedler': ('HCE_EliteSpecopsNeedler', 'Arachnotron', 1.0),
    'HCE_BossCyberdemonHunterMajor': ('HCE_HunterMajor', 'Cyberdemon', 2.0),
    'HCE_BossCyberdemonHunterWhite': ('HCE_HunterWhite', 'Cyberdemon', 3.0),
    'HCE_BossCyberdemonHunterRed': ('HCE_HunterRed', 'Cyberdemon', 3.0),
    'HCE_BossFatsoHunterWhite': ('HCE_HunterWhite', 'Fatso', 1.0),
    'HCE_BossFatsoHunterRed': ('HCE_HunterRed', 'Fatso', 1.0),
    'HCE_BossSpiderEliteCommanderPlasmaRifle': ('HCE_EliteCommanderPlasmaRifle', 'SpiderMastermind', 4.0),
}
VOICES = {'Grunt': 'Grunt_Crazy,Grunt_Whiley,Grunt_Whimpy', 'GruntSpecOps': 'Grunt_Crazy,Grunt_Whiley,Grunt_Whimpy',
          'Elite': 'Elite_Dogmatic,Elite_Loose', 'EliteSpecial': 'Elite_Dogmatic,Elite_Loose',
          'Jackal': 'Jackal', 'JackalMajor': 'Jackal', 'Hunter': 'Hunter',
          # Marines: a random white Marine's voice from Halo CE and Halo 2 (Sergeant Johnson's face: always Johnson, marine_code)
          'Marine': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Cross,Marine_Perez,Marine_Timid,Marine_SgtCautious,Marine_SgtGruff',
          'MarineArmored': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Cross,Marine_Perez,Marine_Timid,Marine_SgtCautious,Marine_SgtGruff',
          'MarineODST': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Cross,Marine_Perez,Marine_Timid,Marine_SgtCautious,Marine_SgtGruff'}
from extract_weapons import WEAPONS as WEAPON_IDS
MELEE = {'energy sword': 151, 'flamethrower': 75}
# projectile bases that aren't HDE HaloProjectile/HaloSlowProjectile (or already carry the nerf mixin)
NO_NERF_MIXIN = {'HCE_FuelRodScaled', 'HaloFlames', 'HCE_PlasmaCasterScaled', 'HCE_NeedleScaled', 'HCE_RocketScaled', 'HCE_BeamPuff', 'HCE_PulseCarbineHoming'}
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
    'FloodInfection': '76703A', 'FloodCarrier': '76703A', 'FloodElite': '76703A', 'FloodHuman': '76703A',  # Flood: brownish green
    'Marine': 'A01010', 'MarineArmored': 'A01010', 'MarineODST': 'A01010',   # human: red
    'SlugMan': 'FF8C1A',                                                  # Slug Men: a Mgalekgolo sub-species, Hunter orange
    'Drinol': '8A1A10', 'BlindWolf': 'A01010', 'ThornBeast': '7A1A30',  # Digsite / SPV3 creatures
}
NO_BLOOD = {'Sentinel'}

def blood_props(char):
    if char in NO_BLOOD: return '\t\t+NOBLOOD\n'
    c = BLOOD.get(char)
    if not c: return ''
    # Halo blood with NashGore loaded (hce_core.zsc HCE_HaloBlood; the Flood keep NashGore's own)
    bt = '' if char.startswith('Flood') else '\t\tBloodType "HCE_HaloBlood";\n'
    return f'\t\tBloodColor "{c[0:2]} {c[2:4]} {c[4:6]}";\n' + bt

def cname(s):
    s = s.split('\\')[-1]
    return 'HCE_' + ''.join(w.capitalize() for w in re.split(r'[^a-zA-Z0-9]+', s) if w)

def wname(ref):
    return ref.split('\\')[-1] if ref else None

# ---------------------------------------------------------------- animations
class AnimSet:
    def __init__(s, meta):
        s.meta = meta; s.names = list(meta['anims'])
    def find(s, *pats):
        """first pattern that matches; returns list of variants (name%0, name%1 ...)"""
        for p in pats:
            exact = [n for n in s.names if n == p or re.fullmatch(re.escape(p) + r'(%\d+)?', n)]
            if exact: return sorted(exact)
        return []
    def find_contains(s, *parts, suffix=''):
        return sorted(n for n in s.names if all(x in n for x in parts) and n.endswith(suffix))
    def tics(s, n):
        return max(1, int(round(s.meta['anims'][n]['frames'] / TICK)))
    def speed(s, n):
        return s.meta['anims'][n]['speed'] * S / TICK if n in s.meta['anims'] else 0

def anim_table(A, w, weapon):
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
    code = FIRE_CODE.get(weapon or '', '')
    fires = [n for n in A.names if n.endswith('baked') and 'fire-' in n]
    pick = [n for n in fires if f' {w} ' in n and f' {code} ' in n] or [n for n in fires if f' {w} ' in n] or fires
    m['FIRE'] = pick[:1]
    m['MELEE'] = f(f'stand {w} melee', 'stand pistol melee', 'stand unarmed melee')
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
    m['SLEEP'] = f(f'asleep {w} idle')
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

KINDS = ['IDLE', 'ALERT', 'MOVE_F', 'MOVE_B', 'MOVE_L', 'MOVE_R', 'CROUCH_IDLE', 'CROUCH_MOVE', 'FLEE', 'FIRE', 'MELEE',
         'THROW', 'DIVE_L', 'DIVE_R', 'DIVE_F', 'EVADE_L', 'EVADE_R', 'SURPRISE_F', 'SURPRISE_B', 'BERSERK', 'WARN',
         'SIGNAL', 'AIRBORNE', 'LAND', 'LEAP_START', 'LEAP_AIR', 'LEAP_MELEE', 'PING_F', 'PING_B', 'PING_L', 'PING_R',
         'HPING_F', 'HPING_B', 'DIE_F', 'DIE_B', 'DIE_L', 'DIE_R', 'DIE_HARD_F', 'DIE_HARD_B', 'DIE_AIR', 'DIE_LAND',
         'RESURRECT_F', 'RESURRECT_B', 'FEED', 'CELEBRATE', 'SLEEP', 'TURN_L', 'TURN_R', 'FLAME_IDLE', 'FLAME_MOVE',
         'RELOAD', 'VENT', 'LOW_IDLE', 'LOW_MOVE', 'GUARD_IDLE', 'GUARD_MOVE_F', 'GUARD_MOVE_B', 'GUARD_MOVE_L',
         'GUARD_MOVE_R', 'GUARD_CROUCH_IDLE', 'GUARD_CROUCH_MOVE',
         'COVER_L_ENTER', 'COVER_L_IDLE', 'COVER_L_PEEK', 'COVER_L_OPEN', 'COVER_L_UNPEEK', 'COVER_L_EXIT',
         'COVER_R_ENTER', 'COVER_R_IDLE', 'COVER_R_PEEK', 'COVER_R_OPEN', 'COVER_R_UNPEEK', 'COVER_R_EXIT', 'HOIST', 'VAULT']

def zs_anim_move(A, used, msc=1.0):
    """HCE_AnimMove: how far a hoist / vault carries the body (cover_anims.py's 'move', Halo world units forward, left,
    up), in map units: the model's own scale, with the 1.2 vertical stretch every Halo model gets"""
    mv = [(n, A.meta['anims'][n]['move']) for n in used if 'move' in A.meta['anims'].get(n, {})]
    out = ['\toverride vector3 HCE_AnimMove(Name anim)', '\t{', '\t\tswitch(anim)', '\t\t{']
    for n, (x, y, z) in mv:
        out.append(f"\t\tcase '{n}': return ({x * S * msc:.1f}, {y * S * msc:.1f}, {z * S * msc * 1.2:.1f});")
    return out + ['\t\t}', '\t\treturn (0, 0, 0);', '\t}']

def zs_anim_funcs(A, table, bers=None, msc=1.0):
    lines = ['\toverride Name HCE_AnimName(int kind)', '\t{',
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
    lines += ['\toverride int HCE_AnimTics(Name anim)', '\t{',
              '\t\tif(hce_hasLoadout) { int lt = HCE_LoadoutAnimTics(anim); if(lt > 0) return lt; }', '\t\tswitch(anim)', '\t\t{']
    for n in used:
        lines.append(f"\t\tcase '{n}': return {A.tics(n)};")
    lines += ['\t\t}', '\t\treturn 30;', '\t}']
    lines += zs_anim_move(A, used, msc)
    return '\n'.join(lines)

# ---------------------------------------------------------------- skins
def variant_color(v, b):
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

# Jackal energy shield colour by rank (Halo shows it through a translucent shader we can't use, so it's baked + brightmapped)
SHIELD_TINT = {'minor': (0.20, 0.35, 1.00), 'ultra': (1.00, 0.55, 0.10), 'major': (1.00, 0.30, 0.85),   # Ultra orange, Major pink
               'zealot': (1.00, 0.84, 0.30)}   # Zealot (the Halo 2 Spiker Jackal): gold, the colour of Covenant zealots
SHIELD_MAT = {'Jackal': 'Jackal_5', 'JackalMajor': 'JackalMajor_5'}

def bake_shield(char, mat, tint, outpath):
    """energy shield: the noise map becomes a bright rank-coloured field with a hot core"""
    n = np.asarray(Image.open(f'{OUT}/models/{char}/{mat}.png').convert('L').resize((128, 128))).astype(np.float32) / 255.0
    col = np.array(tint, dtype=np.float32).reshape(1, 1, 3)
    o = col * (0.55 + 0.6 * n[..., None]) + (n[..., None] ** 3) * 0.35
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

def bake_hunter(char, mat, mode, outpath):
    """Hunter armour is painted blue in the base map; recolour the blue armour by hue (worm flesh/cannon untouched)."""
    im = Image.open(f'{OUT}/models/{char}/{mat}.png').convert('RGB')
    hsv = np.asarray(im.convert('HSV')).astype(np.float32)
    rgb = np.asarray(im).astype(np.float32) / 255.0
    h, sv, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    armour = ((h > 185) & (h < 265) & (sv > 0.22))[..., None]
    lum = (0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2])[..., None]
    if mode == 'white':
        new = np.clip(lum * 2.1 + 0.08, 0, 1) * np.array([0.93, 0.95, 1.0])
    else:  # red
        new = np.clip(lum * 2.3, 0, 1) * np.array([1.0, 0.16, 0.10])
    o = np.where(armour, new, rgb)
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

# Baked armour shine (Elites and Grunts): Halo CE draws their armour with a cube-map reflection under the
# multipurpose map's specular mask (red channel on Xbox): the swirling liquid-metal sheen. Doom's renderer has no cube
# maps, so the reflection is baked into the skin with Halo's own cube maps (extract_cubemaps.py): every armour texel
# gets the model's surface normal there (the triangles rasterised into texture space, bind pose), nudged by the paint's
# own relief, and reflects a view from the front into the cube map; the result is added under the specular mask. The
# Elites' cube map follows their rank colour (blue, magenta, gold, silver); the Grunts wear the same ones (below).
SHINE = {'Elite': 1.0, 'EliteSpecial': 1.0, 'EliteRifle': 1.0, 'Grunt': 1.0, 'GruntSpecOps': 1.0}
# the Grunts wear the Elites' rank cube maps (gold for the orange Minors, red for the Majors, silver for Spec Ops) so their
# armour reads like the Elites' painted skins; Halo CE gave them its dull 'cubemap dark gray'
SHINE_CUBE = {'Elite': 'elite', 'EliteSpecial': 'elite', 'EliteRifle': 'elite', 'Grunt': 'elite', 'GruntSpecOps': 'elite'}
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


def raster_normals(meshes, matfile, size):
    """(H, W, 3) normals per texel of the meshes using 'matfile' (gaps filled from the nearest covered texel)"""
    from scipy import ndimage
    W_, H_ = size
    N = np.zeros((H_, W_, 3), np.float32); hit = np.zeros((H_, W_), bool)
    for m in meshes:
        if m['material'] != matfile or not len(m['tris']): continue
        uv = m['uv'] % 1.0 * np.array([W_ - 1, H_ - 1]); nr = m['nrm']
        for t in m['tris']:
            p = uv[t]; n = nr[t]
            x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
            if x1 - x0 > W_ * 0.6 or y1 - y0 > H_ * 0.6: continue        # wraps across the seam
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            v0, v1 = p[1] - p[0], p[2] - p[0]
            den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-9: continue
            dx, dy = xs - p[0][0], ys - p[0][1]
            b1 = (dx * v1[1] - v1[0] * dy) / den; b2 = (v0[0] * dy - dx * v0[1]) / den; b0 = 1 - b1 - b2
            ins = (b0 >= -0.02) & (b1 >= -0.02) & (b2 >= -0.02)
            xi, yi = xs[ins] % W_, ys[ins] % H_
            N[yi, xi] = b0[ins, None] * n[0] + b1[ins, None] * n[1] + b2[ins, None] * n[2]
            hit[yi, xi] = True
    if hit.any():
        _, (iy, ix) = ndimage.distance_transform_edt(~hit, return_indices=True)
        N = N[iy, ix]
    N /= np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-6)
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

def sample_cube(faces, r):
    """r (..., 3) directions -> colours (Direct3D cube face layout, Halo's axes)"""
    ax = np.abs(r); out = np.zeros(r.shape, np.float32)
    big = np.argmax(ax, -1); sgn = np.take_along_axis(r, big[..., None], -1)[..., 0] >= 0
    x, y, z = r[..., 0], r[..., 1], r[..., 2]
    for f, (axis, pos) in enumerate(((0, True), (0, False), (1, True), (1, False), (2, True), (2, False))):
        sel = (big == axis) & (sgn == pos)
        if not sel.any(): continue
        ma = ax[..., axis][sel]
        sc, tc = {0: (-z, -y) if pos else (z, -y), 1: (x, z) if pos else (x, -z), 2: (x, -y) if pos else (-x, -y)}[axis]
        u = (sc[sel] / ma + 1) / 2; v = (tc[sel] / ma + 1) / 2
        F = faces[f]; h, w = F.shape[:2]
        out[sel] = F[np.clip((v * (h - 1)).astype(int), 0, h - 1), np.clip((u * (w - 1)).astype(int), 0, w - 1)]
    return out

# The Minor (blue) and Major (red) Elites wear hand-painted skins with Halo's cube-map shine baked in
# (assets/elite_skins/<blue|red>/Elite_<k>.png, one per Elite material; any Elite-layout body: Elite, EliteRifle).
# Halo's black Spec Ops armour reads as a hole against the dark undersuit, so the Spec Ops wear a vibrant dark
# purple instead: the blue skins hue-turned to purple on the Elite bodies, the change colour on the Spec Ops body.
ELITE_SKINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'elite_skins')
ELITE_LAYOUT = ('Elite', 'EliteRifle')

# the Spec Ops body (EliteSpecial) shares three of its textures with the Elite: those take the purple-turned skins too
SPECOPS_SHARED = {'0': '0', '3': '5', '5': '5'}
MINOR_BLUE = (0.31, 0.30, 0.53)

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
    if ci == 3: im = purple(im)
    elif ci == 0 and is_green(color): im = heavy_green(im, char, mat)    # the Heavy: the blue skin's armour in green
    im.save(outpath)
    return True

HEAVY_HUE = 104          # the Elite Heavy's green (Halo 3's Heavy green), degrees

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

def is_green(color):
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

def add_shine(char, mat, rgb, color=None):
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


def bake_skin(char, mat, color, outpath):
    src = Image.open(f'{OUT}/models/{char}/{mat}.png')
    if src.mode == 'RGBA' and np.asarray(src)[..., 3].min() < 128 and not os.path.exists(f'{OUT}/models/{char}/{mat}_multi.png'):
        src.save(outpath); return                 # a cutout (the Drones' wings): alpha kept, UZDoom alpha-tests it
    base = src.convert('RGB')
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if color is None or not os.path.exists(mp):
        if char in SHINE: base = Image.fromarray((add_shine(char, mat, np.asarray(base).astype(np.float32) / 255.0, color) * 255).astype(np.uint8))
        base.save(outpath); return
    mask = Image.open(mp).convert('RGBA').resize(base.size)
    b = np.asarray(base).astype(np.float32) / 255.0
    msk = np.asarray(mask).astype(np.float32)[..., 2:3] / 255.0   # Xbox: blue = colour change
    col = np.array(color, dtype=np.float32).reshape(1, 1, 3)
    o = add_shine(char, mat, b * (1 - msk) + b * col * msk, color)
    if char in HUE_LOCK: o = hue_lock(o, msk[..., 0], color)
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

# the Grunts' armour keeps its rank colour's hue under the Elites' cube maps (the gold one would turn the orange
# Minors yellow): the hue of the painted parts is pulled back to the rank colour, the reflection's brightness kept
HUE_LOCK = ('Grunt', 'GruntSpecOps')

def hue_lock(rgb, mask, color):
    import colorsys
    h0, l0, s0 = colorsys.rgb_to_hls(*[float(c) for c in color[:3]])
    if s0 < 0.25: return rgb                                              # black / grey ranks: nothing to hold
    hsv = np.asarray(Image.fromarray(np.clip(rgb * 255, 0, 255).astype(np.uint8)).convert('HSV')).astype(np.float32)
    w = np.clip(mask, 0, 1) * 0.8
    hh = hsv[..., 0]; t = h0 * 255
    d = (t - hh + 128) % 256 - 128                                        # shortest way round the hue circle
    hsv[..., 0] = (hh + d * w) % 256
    return np.asarray(Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB')).astype(np.float32) / 255.0

# Elite Commander (the gold Elite): its tag colour is a dark ochre that, multiplied into the dark Elite Special
# armour, came out a muddy olive. Halo draws it with a bright specular sheen we can't, so the armour is re-baked as
# a vibrant gold that keeps the armour's shading (dark creases stay darker, raised edges catch the light).
VIVID = {'elite commander': (1.00, 0.78, 0.22)}
UNDERSUIT = (0.30, 0.52, 0.52)

def bake_vivid(char, mat, color, outpath):
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
    o = add_shine(char, mat, o * (1 - hm) + glove * hm, color)
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

# Energy-shield flare (the shell actor drawn additively over a shielded unit when it's hit): tint per character
SHELL_TINT = {'Elite': (0.45, 0.70, 1.00), 'EliteSpecial': (0.45, 0.70, 1.00), 'Brute': (1.00, 0.78, 0.30)}

def bake_shell(tint, outpath):
    """a shimmering energy texture: soft cells of light with bright sparks, in the shield's colour"""
    if os.path.exists(outpath): return
    rng = np.random.default_rng(7)
    n = rng.random((32, 32)).astype(np.float32)
    big = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((128, 128), Image.BICUBIC)).astype(np.float32) / 255.0
    fine = rng.random((128, 128)).astype(np.float32)
    v = np.clip(big * 0.85 + (fine > 0.985) * 0.9, 0, 1) ** 1.4
    col = np.array(tint, dtype=np.float32).reshape(1, 1, 3)
    o = col * (0.25 + 0.85 * v[..., None]) + (v[..., None] ** 4) * 0.5
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

# Active camo shimmer (GLSL material shader on the camo variants' skins; the actor itself is translucent)
SHIELD_SHADER = '''// Halo energy shield (Jackal gauntlets): the field drifts and folds over itself, a hex lattice shows through
// with cells flickering on and off, bands of light sweep across it and the whole thing pulses
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	float t = timer;
	vec4 c = getTexel(uv + vec2(t * 0.06, sin(t * 0.7) * 0.03));
	vec4 c2 = getTexel(uv * 1.7 - vec2(t * 0.09, t * 0.04));
	vec3 base = (c.rgb + c2.rgb) * 0.5;
	vec2 h = uv * vec2(12.0, 20.0);
	h.x += mod(floor(h.y), 2.0) * 0.5;
	vec2 f = abs(fract(h) - 0.5);
	float edge = smoothstep(0.36, 0.5, max(f.x * 1.15 + f.y * 0.6, f.y * 1.2));
	float id = dot(floor(h), vec2(7.13, 3.71));
	float flick = 0.5 + 0.5 * sin(t * 3.0 + id * 1.7);
	float sweep = smoothstep(0.86, 1.0, sin(uv.y * 8.0 + uv.x * 3.0 - t * 2.6));
	float pulse = 0.82 + 0.18 * sin(t * 4.5);
	vec3 hue = base / max(0.001, max(base.r, max(base.g, base.b)));
	vec3 col = base * pulse + hue * (edge * (0.35 + 0.55 * flick) * 0.6 + sweep * 0.45);
	return vec4(min(col, vec3(1.0)), c.a);
}
'''

SWORD_SHADER = '''// Halo energy sword blade: plasma flowing up the blade in streaks, a white-hot core along its length, the edges
// shimmering and the whole blade breathing; drawn fullbright
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	float t = timer;
	vec4 c = getTexel(uv);
	float w = sin(uv.y * 22.0 + t * 5.0) * 0.004 + sin(uv.y * 57.0 - t * 9.0) * 0.0025;
	vec4 c2 = getTexel(uv + vec2(w, 0.0));
	vec3 base = mix(c.rgb, c2.rgb, 0.6);
	float lum = max(base.r, max(base.g, base.b));
	vec3 hue = base / max(0.001, lum);
	float flow = 0.5 + 0.5 * sin(uv.y * 40.0 - t * 7.0 + sin(uv.x * 9.0 + t * 2.0) * 1.5);
	float streak = smoothstep(0.75, 1.0, flow);
	float core = smoothstep(0.55, 0.95, lum);
	float n = fract(sin(dot(floor(uv * vec2(48.0, 160.0)) + floor(t * 20.0), vec2(12.9898, 78.233))) * 43758.5453);
	float spark = step(0.97, n) * (1.0 - core);
	float breathe = 0.88 + 0.12 * sin(t * 3.3) + 0.05 * sin(t * 13.0);
	vec3 col = base * breathe * (0.85 + 0.35 * flow) + hue * streak * 0.35 + vec3(core * 0.55) + hue * spark * 0.6;
	return vec4(min(col, vec3(1.0)), c.a);
}
'''

CAMO_SHADER = '''// Halo active camo: the body almost vanishes; slow bands of light ripple over it, with a fine sparkle
vec4 ProcessTexel()
{
	vec2 uv = vTexCoord.st;
	vec4 c = getTexel(uv);
	float t = timer;
	float w = sin(uv.y * 34.0 - t * 4.0 + sin(uv.x * 11.0 + t * 1.3) * 2.2);
	float band = smoothstep(0.80, 1.0, w);
	float n = fract(sin(dot(floor(uv * 64.0) + floor(t * 14.0), vec2(12.9898, 78.233))) * 43758.5453);
	vec3 body = c.rgb * 0.35 + vec3(0.30, 0.36, 0.42);
	vec3 col = mix(body, vec3(0.80, 0.92, 1.0), band);
	float a = 0.30 + band * 0.70 + step(0.93, n) * 0.25;
	return vec4(col, c.a * a);
}
'''

# ---------------------------------------------------------------- generation
GORE_LIMBS = {'head': 0, 'larm': 1, 'rarm': 2, 'back': 3}

# HDE plasma bolt classes the enemies fire -> also thin out the smoke trail (their own Tick does only that)
LITE_PLASMA = {'HaloPlasma_Proj': True, 'HaloPlasmaRifle_Proj': True, 'HaloPulseCarbine_Proj': False, 'HaloChargedPlasma_Proj': False}

def gore_code(char, meta, mdir, sc):
    """HCE_SeverLimb for a character with gore_kit.py's dismemberment data: hide the limb's surfaces (and what it
    holds), show its gore stump, throw the gib"""
    g = meta.get('gore')
    if not g: return ''
    mw = meta.get('mesh_weapon') or []
    out = ['\toverride bool HCE_SeverLimb(int limb)\n\t{\n\t\tif(hce_severed & (1 << limb)) return false;\n\t\tswitch(limb)\n\t\t{\n']
    perms = body_perms(meta)
    def stub_and_gib(x, ind):
        c = x['center']
        return (f'{ind}A_ChangeModel(\'None\', 0, "", \'None\', {x["stub"]}, "models/{mdir}/{char}", \'{g["tex"]}\', CMDL_USESURFACESKIN);\n'
                f'{ind}HCE_SpawnLimb({{L}}, ({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}), {sc:.2f}, "models/{mdir}/{char}", \'{x["gib"]}\', {x["stub"]}, \'{g["tex"]}\', {x.get("rest", 0):.4f});\n')
    for L, d in g['limbs'].items():
        gun = any(si < len(mw) and mw[si] for si in d['surfaces'])
        out.append(f'\t\tcase {GORE_LIMBS[L]}:\n')
        for si in d['surfaces']:
            out.append(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n')
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
            f'\t\tfor(int i = 0; i < hce_permHide.Size(); i++) A_ChangeModel(\'None\', {BLOOD_IDX}, "", \'None\', hce_permHide[i], {hid});\n\t}}\n')


def gun_code(meta, mdir, slot=None):
    """HCE_ShowGun: the gun surfaces baked into the body (mesh_weapon), hidden when it dies or loses its gun arm,
    back to the MODELDEF's skins ('None') when a Flood form gets up again"""
    ws = [i for i, w in enumerate(meta.get('mesh_weapon') or []) if w]
    if not ws: return ''
    return ('\toverride void HCE_ShowGun(bool show)\n\t{\n\t\tsuper.HCE_ShowGun(show);\n'
            "\t\tName sk = show ? 'None' : 'hce_hidden.png';\n"
            f'\t\tstatic const int W[] = {{ {", ".join(map(str, ws))} }};\n'
            f'\t\tfor(int i = 0; i < W.Size(); i++) A_ChangeModel(\'None\', 0, "", \'None\', W[i], "models/{mdir}/weapons", sk, CMDL_USESURFACESKIN);\n'
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
# about its local +z axis (the chin down; up to 10 degrees), added on top of the animation (SetNamedBoneRotation,
# SB_ADD: animation * this). jaw_weights.py gives the jaw a clean hinge, so only the lower lip and chin move
LIP_CODE = """
	int hce_lipPhase;
	double hce_lipOpen;
	override void Tick()
	{
		super.Tick();
		if((level.maptime + hce_lipPhase) % 3) return;
		double want = 0;
		if(health > 0 && IsActorPlayingSound(CHAN_VOICE))
		{
			// syllables: two out-of-step waves, so the mouth opens irregularly, never wide for long
			double t = (level.maptime + hce_lipPhase) * 9.0;
			want = clamp(0.25 + 0.55 * abs(sin(t)) * (0.6 + 0.4 * abs(sin(t * 0.37 + 40))) + frandom[HCELip](-0.1, 0.15), 0, 1);
		}
		if(want == 0 && hce_lipOpen == 0) return;
		hce_lipOpen = want;
		double a = want * 10.0;
		SetNamedBoneRotation('bip01 ponytail1', Quat(0, 0, sin(a / 2), cos(a / 2)), SB_ADD, 3);
	}
"""


MARINE_KIT = f'{OUT}/models/MarineKit'
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
        tot = sum(w for _, w in picks)
        b = [f'\tString {fn}()\n\t{{\n']
        if chance is not None: b.append(f'\t\tif(frandom[HCEKit](0, 1) >= {chance:.2f}) return "";\n')
        b.append(f'\t\tint x = random[HCEKit](0, {tot - 1});\n')
        acc = 0
        for pid, w in picks:
            acc += w
            b.append(f'\t\tif(x < {acc}) return "{pid}";\n')
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
    return (LIP_CODE + '\t// Halo CE\'s Marine cosmetics, rolled per Marine: face and headgear, sleeves, the damaged vest. Sergeant\n'
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


def build(cfg=None):
    cfg = cfg or MAIN
    char_of_unit, team, ai, pack, mdir = cfg['char_of_unit'], cfg['team'], cfg['ai'], cfg['pack'], cfg['mdir']
    main = cfg.get('main', False)
    if os.path.exists(f'{pack}/models'): shutil.rmtree(f'{pack}/models')
    os.makedirs(f'{pack}/ZScript/HaloCE', exist_ok=True)
    metas = {c: json.load(open(f'{OUT}/models/{c}/{c}.json')) for c in set(char_of_unit.values())}
    zs = []; md = []; ednums = []; spawners = {}; late = []; brightmaps = []; shells = set(); camo = []; shield_tex = []
    projectiles_used = set()
    ed = cfg['ed0']
    # ---------------- per character base classes
    for unit, char in sorted(char_of_unit.items(), key=lambda x: x[1]):
        meta = metas[char]
        b = ai['bipeds'][unit]
        ov = CHAR_OVERRIDES.get(char, {})
        os.makedirs(f'{pack}/models/{mdir}/{char}/skins', exist_ok=True)
        shutil.copy(f'{OUT}/models/{char}/{char}.iqm', f'{pack}/models/{mdir}/{char}/{char}.iqm')
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
        if meta.get('blood'):                      # blood on the body (blood_kit.py): overlay models and textures
            for f in meta['blood']['models'] + meta['blood']['textures']: shutil.copy(f'{OUT}/models/{char}/{f}', f'{pack}/models/{mdir}/{char}/{f}')
            Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(f'{pack}/models/{mdir}/{char}/hce_noblood.png')
            os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
            hid = f'{pack}/models/{mdir}/weapons/hce_hidden.png'
            if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        h = max(meta['bounds'][1][2] - max(0, meta['bounds'][0][2]), b.get('collision_height_standing') or 0.3)
        r = b.get('collision_radius') or 0.2
        flying = char == 'Sentinel' or ov.get('flying', False)
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
        zs.append(f'class HCE_{char}Base : HaloDoom_EnemyBase abstract\n{{\n\tDefault\n\t{{\n'
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
                  f'\toverride void HCE_ApplyAnim(Name n, int blend, bool loop)\n\t{{\n\t\tSetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);\n'
                  f'\t\tif(hce_shellActor) hce_shellActor.SetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);   // the shield flare moves with it\n'
                  f'\t\tif(hce_holoActor) hce_holoActor.SetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);   // and a hologram companion\n\t}}\n'
                  + (f"\toverride Name HCE_ShellClass() {{ return 'HCE_{char}ShieldShell'; }}\n" if char in SHELL_TINT else '')
                  + BASE_CODE.get(char, '') + gore_code(char, meta, mdir, S * msc) + blood_code(char, meta, mdir) + gun_code(meta, mdir, OVERLAY_SLOT.get(char)) + perm_code(meta, mdir)
                  + (marine_code(meta, mdir, char) if char.startswith('Marine') else '') + '}\n')
        # ---------------- variants
        for vname, v in sorted(ai['variants'].items()):
            if v['unit_reference'] != unit: continue
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
            elif char == 'Sentinel': w = 'fixed'
            elif (char.startswith('Grunt') or char.startswith('Elite')) and weapon and 'fuel rod' in weapon: w = 'missle'
            elif char.startswith('Elite') and weapon == 'energy sword': w = 'sword'
            elif char.startswith('Elite') and weapon == 'beam rifle': w = 'rifle'
            elif char.startswith('Flood'): w = 'pistol' if weapon else 'unarmed'
            elif char.startswith('Marine') and weapon == 'plasma rifle': w = 'h2plasma'      # Halo 2's rifle stance, the left hand under the gun (marine_plasma_grip.py)
            elif char.startswith('Marine'): w = 'pistol' if weapon in ('pistol', 'needler', 'plasma pistol') else 'rifle'
            else: w = 'pistol'
            A = AnimSet(meta); A.jackal = char.startswith('Jackal')
            table = anim_table(A, w, weapon)
            for k, names in list(ov.get('anims', {}).items()) + list(ov.get('anims_by_weapon', {}).get(weapon, {}).items()):
                table[k] = [n for n in names if n in A.names]
            mv = (table.get('MOVE_F') or [None])[0]
            run = A.speed(mv) if mv else 0
            if run < 1.5: run = {'Sentinel': 6.0, 'FloodInfection': 7.0}.get(char, 5.0)
            run = min(run, 14)
            run *= msc                     # scaled-down model: scaled-down stride
            if 'speed' in ov: run = ov['speed']
            if char == 'Sentinel':
                run = max(4.0, (b.get('flying_velocity') or 2.25) / 30 * S / TICK)
            walk = run * 0.65
            lmv = (table.get('LOW_MOVE') or [None])[0]
            low = min(walk, A.speed(lmv) * msc) if lmv else 0      # the low-ready walk's own pace
            body = un['maximum_body_vitality'] or coll.get('maximum_body_vitality') or 0
            shield = un['maximum_shield_vitality'] or coll.get('maximum_shield_vitality') or 0
            if 'shield' in ov: shield = ov['shield']
            # Stealth Elites: the camo is their protection -- no energy shield and a fragile body
            if 'stealth elite' in vname and char.startswith('Elite'): shield = 0; body = body * 0.45
            if char == 'FloodInfection': body = max(body, 3)
            body = max(1, int(round(ov.get('health', body))))
            # weapon
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
            beam = char == 'Sentinel'
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
            # Halo 3 kamikaze run: Grunts carrying plasma grenades, rarer for Minors (rolled once a second)
            if char.startswith('Grunt') and gtype == 2:
                kc = 0.012 if char == 'GruntSpecOps' else 0.008 if ' major' in vname else 0.004
                pat += f'\t\tHaloDoom_EnemyBase.HCE_Kamikaze {kc};\n'
            if weapon == 'plasma caster':
                pat += '\t\tHaloDoom_EnemyBase.HCE_SpecialShot "HCE_PlasmaCasterClusterScaled", 3;\n'
            if ov.get('voices') or char in VOICES: pat += f'\t\tHaloDoom_EnemyBase.HCE_Voices "{ov.get("voices") or VOICES[char]}";\n'
            maxrange = max(rc['maximum_firing_range'], 4) * S
            rlo, rhi = rc['combat_range_lower_bound'] * S, rc['combat_range_upper_bound'] * S
            if rhi <= 0: rlo, rhi = 0, maxrange * 0.6
            if weapon == 'energy sword' or not weapon or ov.get('melee_only'): rlo, rhi = 0, 32
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
            bz = a['berserk']
            leapmin, leapmax = bz['melee_leap_range_lower_bound'] * S, bz['melee_leap_range_upper_bound'] * S
            leapchance = bz['melee_leap_chance']; leapvel = (bz['melee_leap_velocity'] or b.get('jump_velocity') or 0.1) * S / TICK
            if char == 'FloodInfection': leapmin, leapmax, leapchance, leapvel = 24, 3.5 * S, 1.0, max(8, 0.12 * S / TICK)
            if char.startswith('Flood') and char not in ('FloodInfection', 'FloodCarrier') and leapmax <= 0:
                leapmin, leapmax, leapchance, leapvel = 1.5 * S, 5 * S, 0.5, 0.16 * S / TICK
            if 'leap' in ov: leapmin, leapmax, leapchance, leapvel = ov['leap']
            # grenades
            gtype = 0
            gchance = gc['throw_grenade_chance']
            if gchance > 0: gtype = 2 if gc['grenade_type'] == 1 else 1
            gcount = max(v['items']['grenades_upper_bound'], 1 if gtype else 0)
            overcharge = weapon == 'plasma pistol' and char.startswith('Jackal')   # only Jackals overcharge
            dw = DROP_WEAPON.get(weapon or '') if ov.get('drops', True) else None
            if char == 'Hunter': dw = None if weapon == 'plasma caster' else dw     # the White Hunter's is its arm cannon
            dg = {2: 'PlasmaGrenades', 1: 'FragGrenades'}.get(gtype) if gcount else None
            if dw or dg: pat += f'\t\tHaloDoom_EnemyBase.HCE_Drops "{dw or "None"}", "{dg or "None"}";\n'
            gmin, gmax = gc['grenade_range_lower_bound'] * S, (gc['grenade_range_upper_bound'] or 12) * S
            gvel = min(26, max(12, (b.get('grenade_velocity') or 0.2) * S / TICK))
            # perception
            pe = a['perception']
            vision = (pe['maximum_vision_distance'] or 30) * S
            fov = min(360, 2 * (pe['maximum_vision_angle'] or 1.2) * DEG)
            hearing = (pe['hearing_distance'] or 20) * S
            surprise = (a['panic']['surprise_distance'] or 2) * S
            # emotions
            pa = a['panic']; df = a['defensive']; mvp = a['moving']
            flags = []
            t = ACTOR_TYPES.get(atype, '')
            if t in ('elite',): flags += ['HCE_Surprise', 'HCE_Berserks', 'HCE_SeeksCover', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_Leader']
            if t == 'jackal': flags += ['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades', 'HCE_FrontShield']
            if t == 'grunt': flags += ['HCE_Surprise', 'HCE_Panics', 'HCE_Evades', 'HCE_ThrowsGrenades']
            if t == 'hunter': flags += ['HCE_Berserks', 'HCE_FrontArmor', 'HCE_PairBond']
            if t == 'marine': flags += ['HCE_Panics', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_FollowPlayer']
            if t == 'flood': flags += ['HCE_Surprise', 'HCE_Berserks', 'HCE_Leaps', 'HCE_Resurrects']
            if t == 'infection': flags += ['HCE_Swarm', 'HCE_Leaps', 'HCE_Explodes']
            if t == 'carrier': flags += ['HCE_Surprise', 'HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Explodes']
            if char == 'Sentinel': flags += ['HCE_Surprise', 'HCE_Evades', 'HCE_Flying', 'HCE_Beam']
            if a['flags'] >> 19 & 1 or weapon == 'energy sword': flags.append('HCE_AlwaysBerserk')
            if v['flags'] >> 4 & 1 or v['flags'] >> 5 & 1: flags.append('HCE_ActiveCamo')
            if not gtype and 'HCE_ThrowsGrenades' in flags: flags.remove('HCE_ThrowsGrenades')
            if weapon in LOBBED: flags.append('HCE_Lobbed')
            if 'flags' in ov: flags = list(ov['flags'])
            if weapon in LOBBED and 'HCE_Lobbed' not in flags: flags.append('HCE_Lobbed')
            if char.startswith('Elite') and shield > 0: flags.append('HCE_ShieldStun')   # hard-ping stun when the shield pops
            flags = sorted(set(flags))
            # skins
            color = variant_color(v, b)
            # Flood: the change colour covers nearly the whole body on Xbox and turns them green;
            # the base maps already carry the right flesh/fatigue/armour colours
            if char.startswith('Flood'): color = None
            skin_lines = []; weapon_lines = []
            wid_equipped = WEAPON_IDS.get(rc['reference'] or '')
            if not ov.get('overlay') and meta.get('hand_frame') and wid_equipped:
                # a body without baked guns (extract_chars.OVERLAY_GUNS): Halo CE's own gun as its overlay too
                ars = meta.get('arsenal') or {}
                hit = sorted((k != wid_equipped, k) for k, a in ars.items() if a.get('wid') == wid_equipped)
                if hit: ov = dict(ov, overlay=hit[0][1])
            mesh_weapon = meta.get('mesh_weapon') or [None] * len(meta['meshes'])
            stubs = {d['stub'] for d in meta.get('gore', {}).get('limbs', {}).values()}
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
                dst = f'{pack}/models/{mdir}/{char}/skins/{fn}'
                if not os.path.exists(dst):
                    vivid = next((c for k, c in VIVID.items() if k in vname), None)
                    if v.get('_hunter_color'): bake_hunter(char, matn, v['_hunter_color'], dst)
                    elif vivid: bake_vivid(char, matn, vivid, dst)
                    elif elite_skin(char, matn, color, dst, specops='specops' in vname): pass
                    elif 'specops' in vname and (char.startswith('Elite') or (char == 'GruntSpecOps' and max(color or (1,)) < 0.2)):
                        # the Spec Ops body's own textures: baked as a blue Minor (the blue cube-map sheen the painted
                        # skins have), then turned purple the same way as the painted skins. The black Spec Ops Grunts
                        # get the same purple (the red anti-air ones keep their red)
                        bake_skin(char, matn, MINOR_BLUE, dst)
                        if char == 'GruntSpecOps': grunt_purple(char, matn, dst)
                        else: purple(Image.open(dst).convert('RGB')).save(dst)
                    else: bake_skin(char, matn, color, dst)
                skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/{fn}"')
            friendly = '\t\t+FRIENDLY\n' if team[char] == 'HUMAN' else ''
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
\t\tHaloDoom_EnemyBase.HCE_FlyHeight {48 if char == 'Sentinel' or ov.get('flying') else 0};
''' + pat + ''.join(f'\t\t+HaloDoom_EnemyBase.{f}\n' for f in flags)
            extra = ('' if char in BASE_CODE else TYPE_CODE.get(char, '')) + WEAPON_CODE.get(weapon or '', '') + ov.get('code', '')
            if not char.startswith('Marine') and (ov.get('unique') or weapon in WEAPON_CODE or weapon in PICKUP_SKIP):
                extra += '\toverride bool HCE_HasLoadouts() { return false; }      // keeps the gun it is built around\n'
            if ov.get('overlay'): extra += overlay_gun_code(char, meta, mdir, ov, pack)
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
                          f'\t\tif(hce_bladeActor) hce_bladeActor.SetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);\n\t}}\n'
                          f'\toverride void HCE_OnSever(int limb, bool gunArm)\n\t{{\n\t\tif(gunArm && hce_bladeActor) {{ hce_bladeActor.Destroy(); hce_bladeActor = null; }}\n\t}}\n')
            animtxt = zs_anim_funcs(A, table, ov.get('berserk_anims', BERSERK_ANIMS.get(char)), msc)
            if ov.get('johnson'): animtxt, jx = johnson_code(A, animtxt, char, meta, mdir); extra += jx
            if ov.get('stacker'): animtxt, jx = stacker_code(A, animtxt, char, meta, mdir); extra += jx
            zs.append(f'// {vname}\nclass {cls} : HCE_{char}Base\n{{\n\tDefault\n\t{{\n{props}\t}}\n{animtxt}\n{extra}}}\n')
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
            if 'HCE_ActiveCamo' in flags:
                for line in skin_lines:
                    m = re.match(r'\tSurfaceSkin 0 \d+ "(skins/.*)"', line)
                    if m: camo.append(f'models/{mdir}/{char}/{m.group(1)}')
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
            md.append(f'Model {cls}\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(skin_lines) +
                      f'\n\tScale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}\n\tUseActorPitch\n\tUseActorRoll\n\tBaseFrame\n{frames}\n}}\n')   # roll: the severed pieces tumble with it
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
            if v.get('_late'): late.append(cls)
            else: ednums.append((ed, cls)); ed += 1
            if not ov.get('unique'): spawners.setdefault(char, []).append(cls)
        if len(prof) > 1:              # more than its own gun to choose from
            zs[base_idx] = zs[base_idx][:-2] + loadout_code(char, prof, AnimSet(meta)) + '}\n'
    # ---------------- projectiles with Halo damage
    pz = ['// Enemy projectiles: HDE visuals, Halo CE impact damage']
    done = set()
    for wn in sorted(projectiles_used):
        pc, base_cls, dmg, sp = WEAPONS[wn]
        if pc in done or (not main and wn in MAIN_WEAPONS): continue
        done.add(pc)
        body = ''
        if dmg is not None:
            prop = 'HaloSlowProjectile' if base_cls in ('HaloNeedler_Proj', 'HaloRocketProj', 'HaloSpiker_Bullet', 'HCE_NeedleScaled', 'HCE_RocketScaled') else 'HaloProjectile'
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
        nonlocal ed
        weights = {c: 1 for c in lst}
        pz_ = '\n'.join(f'\t\tDropItem "{c}", 255, {weights[c]};' for c in lst)
        zs.append(f'class HCE_Random{char} : RandomSpawner\n{{\n\tDefault\n\t{{\n{pz_}\n\t}}\n}}\n')
        ednums.append((ed, f'HCE_Random{char}')); ed += 1
    for char, lst in sorted(spawners.items()):
        if char not in late_chars: spawner(char, lst)
    # Doom boss stand-ins (spawned only by HCE_ReplaceHandler; no DoomEdNums)
    blocks = {re.match(r'Model (\w+)', b).group(1): b for b in md}
    for alias, (base, doom, hmul) in sorted(BOSS_ALIASES.items() if main else []):
        if base not in blocks: continue
        m = re.search(r'class ' + base + r' : \w+\n\{\n\tDefault\n\t\{\n\t\tHealth (\d+);', '\n'.join(zs))
        hp = int(int(m.group(1)) * hmul) if m else 100
        zs.append(f'// stands in for Doom\'s {doom}: CheckReplacee maps it back so A_BossDeath map specials fire\n'
                  f'class {alias} : {base}\n{{\n\tDefault\n\t{{\n\t\tHealth {hp};\n\t}}\n}}\n')
        md.append(blocks[base].replace(f'Model {base}\n', f'Model {alias}\n', 1))
    # classes added after the first release keep their numbers: appended in release order, never re-sorted
    LATE_ORDER = cfg.get('late_order', ['HCE_JackalMajorNeedler', 'HCE_HunterWhite', 'HCE_HunterRed'])
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
    # Jackal energy shields: the baked rank-coloured field animated by a shader (a drifting field, a hex lattice whose
    # cells flicker, light sweeping over it, a pulse), drawn fullbright
    if shield_tex:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_shield.fp', 'w').write(SHIELD_SHADER)
        for t in sorted(set(shield_tex)):
            gl.append(f'material texture "{t}"\n{{\n\tshader "shaders/hce_shield.fp"\n\tspeed 1.0\n\tbrightmap "models/{mdir}/brightmap_full.png"\n}}')
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
    tg = cfg['tag']
    open(f'{pack}/gldefs.{tg}', 'w').write('\n'.join(gl) + '\n')
    # HCEM A: placeholder sprite. Models draw instead, but the map spawner rejects actors whose sprite
    # has no frames ("has no frames" -> Unknown), so DoomEdNum things and replacements need a real lump.
    if main:
        os.makedirs(f'{pack}/sprites', exist_ok=True)
        Image.new('RGBA', (4, 4), (0, 0, 0, 0)).save(f'{pack}/sprites/HCEMA0.png')
    open(f'{pack}/ZScript/HaloCE/{tg}_enemies.zsc', 'w').write('\n'.join(zs))
    open(f'{pack}/ZScript/HaloCE/{tg}_projectiles.zsc', 'w').write('\n'.join(pz))
    open(f'{pack}/modeldef.{tg}', 'w').write('\n'.join(md))
    ednums = pin_ednums(ednums)
    mi = ['DoomEdNums', '{'] + [f'\t{n} = {c}' for n, c in ednums] + ['}', '', 'GameInfo', '{', f'\tAddEventHandlers = "{cfg["handler"]}"', '}', '']
    open(f'{pack}/mapinfo.txt', 'w').write('\n'.join(mi))
    json.dump(dict(ednums=ednums, spawners=spawners), open(f'{OUT}/{cfg["index"]}', 'w'), indent=1)
    print('classes', len(ednums), 'projectiles', len(done))

# per-character extra ZScript (Flood corpse feeding, carrier pop, infection pop)
BASE_CODE = {}       # char -> ZScript put in its abstract base class once (shared by all its variants)
TYPE_CODE = {
    'FloodInfection': '''
	// infection forms hunt for dead humans / elites and reanimate them
	override bool HCE_SeekCorpse()
	{
		if(++hce_actionTics < 20) return false;
		hce_actionTics = 0;
		let it = BlockThingsIterator.Create(self, 512);
		Actor best = null; double bd = 1e9;
		while(it.Next())
		{
			let c = HaloDoom_EnemyBase(it.thing);
			if(!c || !c.bCORPSE || !c.hce_enabled || c.bHCE_Resurrects || c.hce_gibbed) continue;
			if(c.hce_team != HCE_TEAM_HUMAN && c.hce_team != HCE_TEAM_COVENANT) continue;
			if(c.hce_type != 0 && c.hce_type != 7) continue;   // elites and marines only
			double d = Distance2D(c);
			if(d < bd) { bd = d; best = c; }
		}
		if(!best) return false;
		hce_feedTarget = best;
		hce_action = HCE_ACT_FEED;
		return true;
	}
	override void HCE_Feed()
	{
		let c = hce_feedTarget;
		if(!c || !c.bCORPSE) { hce_action = HCE_ACT_IDLE; hce_feedTarget = null; return; }
		if(Distance2D(c) > radius + c.radius + 4)
		{
			HCE_Move(AngleTo(c), hce_runSpeed);
			A_SetAngle(AngleTo(c), SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		if(hce_curAnimKind != HCE_A_FEED) { HCE_Play(HCE_A_FEED, true, true); hce_leapState = 0; hce_reviveTics = 35 * 3; return; }
		if(--hce_reviveTics > 0) return;
		Name nc = HaloDoom_EnemyBase(c).hce_type == 0 ? 'HCE_FloodcombatEliteUnarmed' : 'HCE_FloodcombatHumanUnarmed';
		class<Actor> cc = (class<Actor>)(nc);
		if(cc)
		{
			let f = Spawn(cc, c.pos, ALLOW_REPLACE);
			if(f)
			{
				f.angle = c.angle;
				let fe = HaloDoom_EnemyBase(f);
				if(fe && fe.HCE_HasAnim(HCE_A_RESURRECT_F)) fe.HCE_PlayLocked(HCE_A_RESURRECT_F);
				f.SetStateLabel("See");
			}
			c.Destroy();
		}
		Destroy();
	}
''',
    'FloodCarrier': '''
	// carrier pop: releases infection forms
	override void HCE_OnDetonate()
	{
		Name n = 'HCE_FloodInfection';
		class<Actor> ic = (class<Actor>)(n);
		if(!ic) return;
		int count = random(5, 9);
		for(int i = 0; i < count; i++)
		{
			let f = Spawn(ic, pos + (frandom(-12, 12), frandom(-12, 12), height * 0.5), ALLOW_REPLACE);
			if(f)
			{
				f.vel = (frandom(-5, 5), frandom(-5, 5), frandom(3, 7));
				f.target = target;
				f.SetStateLabel("See");
			}
		}
	}
''',
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
# Halo 2's beam rifle fires through the API now (HaloDoom_EnemyBase.HCE_FireBeamRifle, for anything carrying one)
BEAMRIFLE_CODE = ''


MAIN_WEAPONS = set(WEAPONS)
MAIN = dict(char_of_unit=CHAR_OF_UNIT, team=TEAM, ai=AI, pack=PACK, mdir='hce', tag='hce', ed0=30200, main=True,
            handler='HCE_ReplaceHandler', index='pack_index.json')
CHAR_OVERRIDES = {}   # per-character tweaks (used by add-on packs: see build_digsite.py)
WEAPON_CODE = {}      # extra ZScript for every variant carrying a weapon
SPECIAL_FIRE = {}     # weapon -> chance a burst becomes the charged special shot
WEAPON_SKIN = {}      # weapon -> {weapon surface texture: replacement} (recoloured variants of one mesh)
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
    'battle rifle':     (3, 3, 2, 0.6, 1.1, 0, False, 1.0, 1.0),      # Halo's three-round burst
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
    'marine pulse carbine': (3, 5, 3, 1.4, 2.3, 0, False, 1.0, 1.0),
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
FIRE_SOUNDS['needle ballista'] = (W + 'NeedlerJavelin/Fire', W + 'NeedlerJavelin/Fire/Bass', '', '', False)
FIRE_CODE.update({'plasma carbine': 'cr', 'spiker': 'sk', 'marine pulse carbine': 'cr', 'needle ballista': 'ne'})
FIRE_SOUNDS['stanchion'] = (W + 'Stanchion/Fire', W + 'Stanchion/Fire/Bass', '', W + 'Stanchion/Charge/PreFire', False)
LOBBED.add('grenade launcher')
DROP_WEAPON.update({k: d[7] for k, d in MARINE_ARSENAL.items() if k not in DROP_WEAPON})
DROP_WEAPON['stanchion'] = 'Halo_Stanchion'

STICKY_CODE = """
	// the sticky detonator's muzzle: the charge seated in it when loaded, the empty muzzle once fired, until it
	// reloads (setting the charges off is the API's: HCE_StickyTick, for any Marine carrying one)
	int hce_stickyReload;
	override void HCE_OnShot(Actor shot)
	{
		super.HCE_OnShot(shot);
		if(hce_hasLoadout) return;             // traded / picked up something else: not this gun any more
		HCE_StickyFired();
		hce_stickyReload = level.maptime + 45;
	}
	void HCE_StickyLoaded()
	{
%STICKY_LOADED%	}
	void HCE_StickyFired()
	{
%STICKY_FIRED%	}
	override void Tick()
	{
		super.Tick();
		if(hce_stickyReload > 0 && level.maptime >= hce_stickyReload && health > 0) { hce_stickyReload = 0; if(!hce_hasLoadout) HCE_StickyLoaded(); }
	}
"""
WEAPON_CODE['sticky detonator'] = STICKY_CODE

STANCHION_CODE = """
	// the Stanchion: 24 tics of aiming (the glint and the targeting laser, the charge-up sound), then one rail
	// shot drawn with HDE's laser beam; it tears what it kills apart (HCE_StanchionRail, HCE_WeaponKind)
	const HCE_RAIL_AIM = 24;
	bool hce_cqc;
	void HCE_FireRail()
	{
		if(!target) return;
		vector3 ap = HCE_AimPoint();
		double gz = height * 0.5 + hce_gunOffset.z;
		vector3 from = Vec3Angle(hce_gunOffset.x, angle, gz);
		vector3 diff = level.Vec3Diff(from, ap);
		double ang = atan2(diff.y, diff.x);
		double pit = -atan2(diff.z, diff.xy.Length());
		FLineTraceData lt;
		LineTrace(ang, hce_maxRange, pit, TRF_THRUSPECIES, gz, hce_gunOffset.x, 0, lt);
		vector3 to = lt.HitType != TRACE_HitNone ? lt.HitLocation : from + (cos(ang) * cos(pit), sin(ang) * cos(pit), -sin(pit)) * hce_maxRange;
		if(hce_burstShot < HCE_RAIL_AIM)
		{
			if(hce_burstShot == 0 && hce_chargeSound.Length() > 0) A_StartSound(hce_chargeSound, CHAN_WEAPON, CHANF_OVERLAP, 0.9);
			HCE_SniperGlint(level.Vec3Diff(pos, from), hce_burstShot);
			if(level.Vec3Diff(from, to).Length() >= 1) HCE_AimLaser(from, to);
			hce_burstShot++;
			return;
		}
		HCE_EnemyLaser.Flash(from, to, Color(255, 255, 70, 20), 3.0, 0.08);
		HCE_EnemyLaser.Flash(from, to, Color(255, 255, 200, 120), 1.2, 0.12);
		for(int i = 0; i < 12; i++)
			A_SpawnParticle("FF9020", SPF_FULLBRIGHT, 14, 5, 0, to.x - pos.x, to.y - pos.y, to.z - pos.z, frandom(-2, 2), frandom(-2, 2), frandom(0, 3), 0, 0, -0.1, 1.0, -0.06);
		Actor hit = lt.HitActor;
		if(hit && hit != self && hit.bSHOOTABLE)
			hit.DamageMobj(self, self, max(1, int(round(150 * hce_damageMod * HCE_DamageScale()))), 'Railgun');
		HCE_PlayFireSound(false);
		if(hce_moveSpeed <= 0.1 && HCE_HasAnim(HCE_A_FIRE)) HCE_Play(HCE_A_FIRE, false, true, 2);
		hce_burstShot++;
	}
	override void HCE_FireShot(bool special)
	{
		if(hce_cqc || hce_hasLoadout) { super.HCE_FireShot(special); return; }
		HCE_FireRail();
	}
"""
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


MEDIC_GUNS = ('assault rifle', 'shotgun', 'ma37', 'smg', 'magnum')


def add_marine_arsenal(variants):
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
    # Sergeant Stacker: the white sergeant (Halo CE's second sergeant's voice, 'sarge2', recorded by Pete Stacker),
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
    'marine odst raven green':         ('marine_armored shotgun major', 'green'),
    'marine odst raven orange':        ('marine_armored battle rifle', 'orange'),
    'marine odst raven blue':          ('marine_armored assault rifle', 'blue'),
    'marine odst raven purple':        ('marine_armored sniper', 'purple'),
    # other sealed helmets on the ODST's body: Halo 2's ODST helmet (extract_h2_odst_helmet.py) and Elefant's two
    # closed kit helmets, in place of Spiral's own (ODST_HELMET_CODE)
    'marine odst halo2 helmet':        ('marine_armored assault rifle', None, 'h2_odst_helmet'),
    'marine odst closed helmet':       ('marine_armored battle rifle', None, 'helmet_closed'),
    'marine odst enclosed helmet':     ('marine_armored shotgun major', None, 'helmet_enclosed'),
}
ODST_HELMET_SURFS = (1, 2)        # Spiral's ODST: its helmet and visor surfaces (MarineODST.iqm meshes head_1, head_2)

def odst_helmet_code(piece, mdir='hce'):
    hid = f'"models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN'
    hide = ''.join(f"\t\tA_ChangeModel('None', {{idx}}, \"\", 'None', {k}, {hid});\n" for k in ODST_HELMET_SURFS)
    return (f'\t// another sealed helmet in place of the ODST\'s own: {piece} (a Marine kit piece on the head bone)\n'
            '\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n'
            + hide.replace('{idx}', '0') +
            f'\t\tA_ChangeModel(\'None\', 1, "models/{mdir}/MarineKit", "{piece}.iqm", 1, "", \'None\');\n'
            '\t\tHCE_ResumeAnim();\n\t}\n'
            '\toverride void HCE_BloodHideClass()\n\t{\n' + hide.replace('{idx}', str(BLOOD_IDX)) + '\t}\n')
def add_odsts(ai):
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
        base = ai['variants'].get('characters\\marine_armored\\' + src)
        key = 'characters\\marine_odst\\' + vn
        if not base or key in ai['variants']: continue
        v = copy.deepcopy(base)
        v['unit_reference'] = ODST_UNIT
        if vn == 'marine odst shotgun' and minor: v['actor_reference'] = minor      # a Private, as a50's shotgun ODST
        v['change_colors'] = None; v['change_colors_list'] = []
        v['_late'] = True
        ov = dict(v.get('_ov') or {})
        ov['skin_as'] = cname(key) if raven else 'HCE_MarineOdstAssaultRifle'
        if raven: ov['raven'] = raven
        if helmet: ov['code'] = ov.get('code', '') + odst_helmet_code(helmet)
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

# Halo CE's visor shader (shader_model with a reflection cube map): the reflection direction per pixel (the view ray
# off the surface normal), its cube face and texel looked up in the six faces laid side by side (Halo's axes, Direct3D
# face layout), tinted by the visor's texture (its perpendicular / parallel tints, extract_odst.py) and brighter toward
# grazing angles (Halo's fresnel blend), over the visor's own dark glass
VISOR_SHADER = '''// Halo CE visor: a reflection cube map (six faces in a strip: +x -x +y -y +z -z), tinted, with fresnel
vec4 ProcessTexel()
{
	vec4 tint = getTexel(vTexCoord.st);
	vec3 n = normalize(vWorldNormal.xyz);
	vec3 v = normalize(pixelpos.xyz - uCameraPos.xyz);
	vec3 r = reflect(v, n);
	vec3 h = vec3(r.x, r.z, r.y);                      // GL (x, up, y) -> Halo (x, y, up)
	vec3 a = abs(h);
	float face; float sc; float tc; float ma;
	if(a.x >= a.y && a.x >= a.z) { ma = a.x; if(h.x > 0.0) { face = 0.0; sc = -h.z; tc = -h.y; } else { face = 1.0; sc = h.z; tc = -h.y; } }
	else if(a.y >= a.z) { ma = a.y; if(h.y > 0.0) { face = 2.0; sc = h.x; tc = h.z; } else { face = 3.0; sc = h.x; tc = -h.z; } }
	else { ma = a.z; if(h.z > 0.0) { face = 4.0; sc = h.x; tc = -h.y; } else { face = 5.0; sc = -h.x; tc = -h.y; } }
	vec2 fuv = clamp(vec2(sc, tc) / max(ma, 0.0001) * 0.5 + 0.5, 0.002, 0.998);
	vec3 env = texture(tex_cube, vec2((face + fuv.x) / 6.0, fuv.y)).rgb;
	float fres = pow(1.0 - abs(dot(n, v)), 2.0);
	vec3 col = tint.rgb * 0.25 + env * tint.rgb * (1.1 + 1.4 * fres) + env * env * 0.25 * fres;
	return vec4(min(col, vec3(1.0)), 1.0);
}
'''

# the Marine kit's enclosed helmets (helmet_closed, helmet_enclosed and the two ODST helmets) share one orange visor
# texture: it gets the ODSTs' visor shader, tinted by its own orange, over the ODST visor's cube map
KIT_VISOR = 'mk_innie_visor_diff.png'
KIT_VISOR_CUBE = 'mk_visor_cube.png'

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
    return [f'material texture "models/{mdir}/MarineKit/{KIT_VISOR}"\n{{\n\tshader "shaders/hce_visor.fp"\n'
            f'\ttexture tex_cube "models/{mdir}/MarineKit/{KIT_VISOR_CUBE}"\n}}']

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

MAIN_WEAPONS |= set(WEAPONS)

if __name__ == '__main__':
    build()
