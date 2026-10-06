"""Generate the Halo CE enemy pack: ZScript classes, MODELDEF, skins, projectiles."""
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
}
TEAM = {'Grunt': 'COVENANT', 'GruntSpecOps': 'COVENANT', 'Jackal': 'COVENANT', 'JackalMajor': 'COVENANT',
        'Elite': 'COVENANT', 'EliteSpecial': 'COVENANT', 'Hunter': 'COVENANT', 'FloodInfection': 'FLOOD',
        'FloodCarrier': 'FLOOD', 'FloodElite': 'FLOOD', 'FloodHuman': 'FLOOD', 'Sentinel': 'SENTINEL',
        'Marine': 'HUMAN', 'MarineArmored': 'HUMAN'}

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
          'Marine': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Sarge,Marine_Cross,Marine_Perez,Marine_Timid,Marine_Tough,Marine_SgtCautious,Marine_SgtGruff',
          'MarineArmored': 'Marine_Aussie,Marine_Bisenti,Marine_Fitzgerald,Marine_Mendoza,Marine_Sarge,Marine_Cross,Marine_Perez,Marine_Timid,Marine_Tough,Marine_SgtCautious,Marine_SgtGruff'}
from extract_weapons import WEAPONS as WEAPON_IDS
MELEE = {'energy sword': 151, 'flamethrower': 75}
# projectile bases that aren't HDE HaloProjectile/HaloSlowProjectile (or already carry the nerf mixin)
NO_NERF_MIXIN = {'HCE_FuelRodScaled', 'HaloFlames', 'HCE_PlasmaCasterScaled', 'HCE_NeedleScaled', 'HCE_RocketScaled', 'HCE_BeamPuff', 'HCE_PulseCarbineHoming'}
ACTOR_TYPES = {0: 'elite', 1: 'jackal', 2: 'grunt', 3: 'hunter', 4: 'engineer', 7: 'marine', 8: 'crew',
               9: 'flood', 10: 'infection', 11: 'carrier', 12: 'monitor', 13: 'sentinel'}

# Blood by species (Halopedia, "Blood"; Halo CE colours where the games differ). NashGore and Doom's own
# blood both use BloodColor, so gore mods paint each race correctly. Sentinels are machines: no blood.
BLOOD = {
    'Elite': '3A1E8C', 'EliteSpecial': '3A1E8C', 'EliteRifle': '3A1E8C',   # Sangheili: dark blue/purple (CE)
    'Jackal': '4A2A9A', 'JackalMajor': '4A2A9A', 'H2Jackal': '4A2A9A',    # Kig-Yar: dark blue/purple (CE)
    'Grunt': '40C8D0', 'GruntSpecOps': '40C8D0',                          # Unggoy: light blue / teal
    'Hunter': 'FF8C1A',                                                   # Mgalekgolo: bright orange
    'Brute': '161C40',                                                    # Jiralhanae (Halo 2): dark navy blue / black
    'Drone': 'DDF0D2',                                                    # Yanme'e: white, slight green tint
    'Engineer': 'E0607A',                                                 # Huragok: reddish pink
    'FloodInfection': '76703A', 'FloodCarrier': '76703A', 'FloodElite': '76703A', 'FloodHuman': '76703A',  # Flood: brownish green
    'Marine': 'A01010', 'MarineArmored': 'A01010',                        # human: red
    'SlugMan': 'FF8C1A',                                                  # Slug Men: a Mgalekgolo sub-species, Hunter orange
    'Drinol': '8A1A10', 'BlindWolf': 'A01010', 'ThornBeast': '7A1A30',  # Digsite / SPV3 creatures
}
NO_BLOOD = {'Sentinel'}

def blood_props(char):
    if char in NO_BLOOD: return '\t\t+NOBLOOD\n'
    c = BLOOD.get(char)
    return f'\t\tBloodColor "{c[0:2]} {c[2:4]} {c[4:6]}";\n' if c else ''

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
    m['ALERT'] = f(f'alert {w} idle', f'stand {w} idle') or m['IDLE']
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
    return m

KINDS = ['IDLE', 'ALERT', 'MOVE_F', 'MOVE_B', 'MOVE_L', 'MOVE_R', 'CROUCH_IDLE', 'CROUCH_MOVE', 'FLEE', 'FIRE', 'MELEE',
         'THROW', 'DIVE_L', 'DIVE_R', 'DIVE_F', 'EVADE_L', 'EVADE_R', 'SURPRISE_F', 'SURPRISE_B', 'BERSERK', 'WARN',
         'SIGNAL', 'AIRBORNE', 'LAND', 'LEAP_START', 'LEAP_AIR', 'LEAP_MELEE', 'PING_F', 'PING_B', 'PING_L', 'PING_R',
         'HPING_F', 'HPING_B', 'DIE_F', 'DIE_B', 'DIE_L', 'DIE_R', 'DIE_HARD_F', 'DIE_HARD_B', 'DIE_AIR', 'DIE_LAND',
         'RESURRECT_F', 'RESURRECT_B', 'FEED', 'CELEBRATE', 'SLEEP', 'TURN_L', 'TURN_R', 'FLAME_IDLE', 'FLAME_MOVE']

def zs_anim_funcs(A, table, bers=None):
    lines = ['\toverride Name HCE_AnimName(int kind)', '\t{']
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
    lines += ['\toverride int HCE_AnimTics(Name anim)', '\t{', '\t\tswitch(anim)', '\t\t{']
    for n in used:
        lines.append(f"\t\tcase '{n}': return {A.tics(n)};")
    lines += ['\t\t}', '\t\treturn 30;', '\t}']
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
# multipurpose map's specular mask (red channel on Xbox), which gives the metal its glossy, sky-lit look. Doom's
# renderer has no cube maps, so a stylised version is baked into the skin: every armour texel gets the model's surface
# normal there (the triangles rasterised into texture space, bind pose), lit by a fixed studio sky - a bright overhead
# reflection, a sharp horizon streak and two specular lobes, brighter towards grazing angles - tinted by the
# armour's own colour and masked by Halo's specular mask.
SHINE = {'Elite': 0.95, 'EliteSpecial': 0.95, 'EliteRifle': 0.95, 'Grunt': 0.8, 'GruntSpecOps': 0.8}
_normal_maps = {}

def normal_map(char, mat, size):
    """(H, W, 3) model-space normals per texel of 'mat' (zero where no triangle covers it, then grown into the gaps)"""
    key = (char, mat, size)
    if key in _normal_maps: return _normal_maps[key]
    from iqm import read_iqm
    from scipy import ndimage
    W_, H_ = size
    N = np.zeros((H_, W_, 3), np.float32); hit = np.zeros((H_, W_), bool)
    _, meshes, _ = read_iqm(f'{OUT}/models/{char}/{char}.iqm')
    for m in meshes:
        if m['material'] != mat + '.png' or not len(m['tris']): continue
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
    _normal_maps[key] = N
    return N

def add_shine(char, mat, rgb):
    """rgb (H, W, 3) floats 0..1, the finished skin colours -> with the baked armour shine"""
    k = SHINE.get(char)
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if not k or not os.path.exists(mp): return rgb
    H_, W_ = rgb.shape[:2]
    spec = np.asarray(Image.open(mp).convert('RGBA').resize((W_, H_))).astype(np.float32)[..., 0] / 255.0
    if spec.max() < 0.05: return rgb
    n = normal_map(char, mat, (W_, H_))
    def lobe(d, p):
        d = np.array(d, np.float32); d /= np.linalg.norm(d)
        return np.clip(n @ d, 0, 1) ** p
    sky = 0.18 + 0.55 * np.clip(n[..., 2], 0, 1) ** 1.5                       # overhead sky
    horizon = 0.45 * np.exp(-((n[..., 2] - 0.12) / 0.07) ** 2)                 # the cube map's horizon streak
    key = 1.4 * lobe((0.55, 0.35, 0.75), 28) + 0.6 * lobe((0.35, -0.65, 0.45), 14)
    graze = 0.35 * (1 - np.abs(n[..., 0])) ** 3                                # facing away from the front: more reflective
    env = sky + horizon + key + graze
    lum = rgb.mean(axis=2, keepdims=True)
    tint = 0.45 + 0.55 * rgb / np.maximum(lum, 0.05) * 0.6                     # the armour's own colour, washed toward white
    s = (env * spec * k)[..., None] * np.clip(tint, 0, 1.6)
    return np.clip(rgb + s * (1 - rgb * 0.5), 0, 1)                           # screen-ish: highlights don't clip flat


def bake_skin(char, mat, color, outpath):
    base = Image.open(f'{OUT}/models/{char}/{mat}.png').convert('RGB')
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if color is None or not os.path.exists(mp):
        if char in SHINE: base = Image.fromarray((add_shine(char, mat, np.asarray(base).astype(np.float32) / 255.0) * 255).astype(np.uint8))
        base.save(outpath); return
    mask = Image.open(mp).convert('RGBA').resize(base.size)
    b = np.asarray(base).astype(np.float32) / 255.0
    msk = np.asarray(mask).astype(np.float32)[..., 2:3] / 255.0   # Xbox: blue = colour change
    col = np.array(color, dtype=np.float32).reshape(1, 1, 3)
    o = add_shine(char, mat, b * (1 - msk) + b * col * msk)
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

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
    o = add_shine(char, mat, o * (1 - hm) + glove * hm)
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
GORE_LIMBS = {'head': 0, 'larm': 1, 'rarm': 2}

def gore_code(char, meta, mdir, sc):
    """HCE_SeverLimb for a character with gore_kit.py's dismemberment data: hide the limb's surfaces (and what it
    holds), show its gore stump, throw the gib"""
    g = meta.get('gore')
    if not g: return ''
    mw = meta.get('mesh_weapon') or []
    out = ['\toverride bool HCE_SeverLimb(int limb)\n\t{\n\t\tif(hce_severed & (1 << limb)) return false;\n\t\tswitch(limb)\n\t\t{\n']
    for L, d in g['limbs'].items():
        gun = any(si < len(mw) and mw[si] for si in d['surfaces'])
        c = d['center']
        out.append(f'\t\tcase {GORE_LIMBS[L]}:\n')
        for si in d['surfaces']:
            out.append(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n')
        out.append(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {d["stub"]}, "models/{mdir}/{char}", \'{g["tex"]}\', CMDL_USESURFACESKIN);\n')
        out.append(f'\t\t\tHCE_SpawnLimb({GORE_LIMBS[L]}, ({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}), {sc:.2f}, "models/{mdir}/{char}", \'{d["gib"]}\', {d["stub"]}, \'{g["tex"]}\');\n')
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


def marine_code(meta, mdir):
    """a random face per Marine from Halo CE's head permutations (extract_chars.MULTI_PERMS); Sergeant Johnson's face
    (the dark-skinned one) brings his full-sleeved arms and always his own voice, the others a random Marine's"""
    names = meta.get('mesh_names') or []
    heads = sorted({n.split('.', 1)[1] for n in names if n.startswith('head.') and n != 'head.shared'})
    if len(heads) < 2: return ''
    def sis(pred): return [i for i, n in enumerate(names) if pred(n)]
    cases = []
    for k, h in enumerate(heads):
        johnson = 'johnson' in h
        helmet = 'cap' not in h and not johnson
        hide = sis(lambda n: n.startswith('head.') and n != 'head.shared' and n != f'head.{h}')
        if not helmet: hide += sis(lambda n: n == 'head.shared')
        hide += sis(lambda n: n.startswith('arms.') and (('johnson' in n or 'sleeve-100' in n) != johnson))
        cases.append(f'\t\tcase {k}: {{ static const int H[] = {{ {", ".join(map(str, sorted(hide)))} }}; for(int i = 0; i < H.Size(); i++) hce_hideSurf.Push(H[i]);'
                     + (" hce_voice = 'Marine_Johnson';" if johnson else '') + ' break; }\n')
    hid = f'"models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN'
    jk = next((k for k, h in enumerate(heads) if 'johnson' in h), -1)
    others = [k for k in range(len(heads)) if k != jk]
    return ('\t// a random face per Marine (Halo CE\'s head permutations). Sergeant Johnson\'s face (with his own voice) is his\n'
            '\t// alone: only HCE_SgtJohnson wears it\n'
            f'\tconst HCE_JOHNSON_FACE = {jk};\n'
            '\tArray<int> hce_hideSurf;\n\tint hce_face;\n'
            '\toverride void PostBeginPlay()\n\t{\n\t\tsuper.PostBeginPlay();\n\t\tHCE_DressMarine();\n\t}\n'
            f'\tvirtual int HCE_PickFace() {{ static const int F[] = {{ {", ".join(map(str, others))} }}; return F[random(0, {len(others) - 1})]; }}\n'
            '\tvoid HCE_DressMarine()\n\t{\n\t\thce_hideSurf.Clear();\n'
            f'\t\thce_face = HCE_PickFace();\n\t\tswitch(hce_face)\n\t\t{{\n' + ''.join(cases) + '\t\t}\n'
            f'\t\tfor(int i = 0; i < hce_hideSurf.Size(); i++) A_ChangeModel(\'None\', 0, "", \'None\', hce_hideSurf[i], {hid});\n\t}}\n'
            f'\toverride void HCE_BloodHideClass()\n\t{{\n\t\tfor(int i = 0; i < hce_hideSurf.Size(); i++) A_ChangeModel(\'None\', {BLOOD_IDX}, "", \'None\', hce_hideSurf[i], {hid});\n\t}}\n')


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


def build(cfg=None):
    cfg = cfg or MAIN
    char_of_unit, team, ai, pack, mdir = cfg['char_of_unit'], cfg['team'], cfg['ai'], cfg['pack'], cfg['mdir']
    main = cfg.get('main', False)
    if os.path.exists(f'{pack}/models'): shutil.rmtree(f'{pack}/models')
    os.makedirs(f'{pack}/ZScript/HaloCE', exist_ok=True)
    metas = {c: json.load(open(f'{OUT}/models/{c}/{c}.json')) for c in set(char_of_unit.values())}
    zs = []; md = []; ednums = []; spawners = {}; late = []; brightmaps = []; shells = set(); camo = []
    projectiles_used = set()
    ed = cfg['ed0']
    # ---------------- per character base classes
    for unit, char in sorted(char_of_unit.items(), key=lambda x: x[1]):
        meta = metas[char]
        b = ai['bipeds'][unit]
        ov = CHAR_OVERRIDES.get(char, {})
        os.makedirs(f'{pack}/models/{mdir}/{char}/skins', exist_ok=True)
        shutil.copy(f'{OUT}/models/{char}/{char}.iqm', f'{pack}/models/{mdir}/{char}/{char}.iqm')
        if meta.get('gore') or meta.get('blood'):
            os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
            if not os.path.exists(f'{pack}/models/{mdir}/weapons/hce_hidden.png'): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(f'{pack}/models/{mdir}/weapons/hce_hidden.png')
        if meta.get('gore'):                       # dismemberment (gore_kit.py): the gibs and the stump texture
            for d in meta['gore']['limbs'].values(): shutil.copy(f'{OUT}/models/{char}/{d["gib"]}', f'{pack}/models/{mdir}/{char}/{d["gib"]}')
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
        zs.append(f'class HCE_{char}Base : HaloDoom_EnemyBase abstract\n{{\n\tDefault\n\t{{\n'
                  f'\t\tMonster;\n\t\t+DECOUPLEDANIMATIONS\n\t\t+FLOORCLIP\n\t\t+DONTHARMSPECIES\n\t\t+NOINFIGHTSPECIES\n'
                  f'\t\tSpecies "HCE_{team[char]}";\n\t\tHaloDoom_EnemyBase.HCE_Enabled true;\n'
                  f'\t\tHaloDoom_EnemyBase.HCE_Team HCE_TEAM_{team[char]};\n'
                  f'\t\tHeight {height};\n\t\tRadius {radius};\n\t\tMass {int(100 * (h / 0.6) ** 2)};\n'
                  f'\t\tPainChance 0;\n\t\tTag "{char}";\n{blood_props(char)}\t}}\n'
                  f'\tStates\n\t{{\n\tSpawn:\n\t\tHCEM A 1 HCE_Look();\n\t\tLoop;\n\tSee:\n\t\tHCEM A 1 HCE_Think();\n\t\tLoop;\n'
                  f'\tDeath:\n\t\tHCEM A 1 HCE_Die();\n\t\tHCEM A 2 A_NoBlocking;\n'            # no XDeath: gore stays blood-only (see HCE_Gore)
                  f'\tDead:\n\t\tHCEM A 1 HCE_CorpseTick();\n\t\tLoop;\n'
                  f'\tRaise:\n\t\tHCEM A 1;\n\t\tGoto See;\n\tPain.PlasmaStuck:\n\t\tHCEM A 1 HCE_OnStuck();\n\t\tGoto See;\n\t}}\n'
                  f'\toverride void HCE_ApplyAnim(Name n, int blend, bool loop)\n\t{{\n\t\tSetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);\n'
                  f'\t\tif(hce_shellActor) hce_shellActor.SetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);   // the shield flare moves with it\n\t}}\n'
                  + (f"\toverride Name HCE_ShellClass() {{ return 'HCE_{char}ShieldShell'; }}\n" if char in SHELL_TINT else '')
                  + BASE_CODE.get(char, '') + gore_code(char, meta, mdir, S * msc) + blood_code(char, meta, mdir)
                  + (marine_code(meta, mdir) if char.startswith('Marine') else '') + '}\n')
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
            elif char.startswith('Marine'): w = 'pistol' if weapon in ('pistol', 'needler', 'plasma pistol') else 'rifle'
            else: w = 'pistol'
            A = AnimSet(meta)
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
            mesh_weapon = meta.get('mesh_weapon') or [None] * len(meta['meshes'])
            stubs = {d['stub'] for d in meta.get('gore', {}).get('limbs', {}).values()}
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
                        if not os.path.exists(dst): shutil.copy(src, dst)
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
                    brightmaps.append(f'models/{mdir}/{char}/skins/{fn}')
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
                    else: bake_skin(char, matn, color, dst)
                skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/{fn}"')
            friendly = '\t\t+FRIENDLY\n' if team[char] == 'HUMAN' else ''
            props = f'''\t\tHealth {body};
{friendly}\t\tSpeed {run:.1f};
\t\tHaloDoom_EnemyBase.HCE_Type {atype};
\t\tHaloDoom_EnemyBase.HCE_Variant "{vname.split(chr(92))[-1]}";
\t\tHaloDoom_EnemyBase.HCE_Perception {vision:.0f}, {fov:.0f}, {hearing:.0f}, {surprise:.0f};
\t\tHaloDoom_EnemyBase.HCE_Movement {walk:.2f}, {run:.2f}, {12 if char != 'Hunter' else 7};
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
            animtxt = zs_anim_funcs(A, table, ov.get('berserk_anims', BERSERK_ANIMS.get(char)))
            if ov.get('johnson'): animtxt, jx = johnson_code(A, animtxt, char, meta, mdir); extra += jx
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
                skin_lines += arsenal_lines(char, ov['overlay'], meta, pack, mdir)
                frames += f'\n\tFrameIndex HCEM A {ARSENAL_IDX} 0'
            sc = S * msc
            md.append(f'Model {cls}\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(skin_lines) +
                      f'\n\tScale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}\n\tUseActorPitch\n\tBaseFrame\n{frames}\n}}\n')
            if v.get('_late'): late.append(cls)
            else: ednums.append((ed, cls)); ed += 1
            if not ov.get('unique'): spawners.setdefault(char, []).append(cls)
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
        pz.append(f'class {pc} : {base_cls}\n{{\n{mix}\tDefault\n\t{{\n{body}\t}}\n}}\n')
    if main: pz.append('class HCE_ChargedPlasma : HaloChargedPlasma_Proj\n{\n\tmixin HCE_NerfMixin;\n\tDefault\n\t{\n\t\tHaloProjectile.BaseDamage 70;\n\t}\n}\n')
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
    # glow: shields, needles, sword blade
    for w in ('w_needler_glow.png', 'w_energy_sword_glow.png'):
        if os.path.exists(f'{pack}/models/{mdir}/weapons/{w}'): brightmaps.append(f'models/{mdir}/weapons/{w}')
    for w in cfg.get('glow', []):
        if os.path.exists(f'{pack}/models/{mdir}/weapons/{w}'): brightmaps.append(f'models/{mdir}/weapons/{w}')
    gl = [cfg.get('gl_title', '// Halo CE enemy pack: glowing surfaces (energy shields, needles, sword blade)')]
    full = f'{pack}/models/{mdir}/brightmap_full.png'
    Image.new('RGB', (8, 8), (255, 255, 255)).save(full)
    for t in sorted(set(brightmaps)):
        gl.append(f'brightmap texture "{t}"\n{{\n\tmap "models/{mdir}/brightmap_full.png"\n}}')
    # active camo: a shimmer shader on the camo variants' own skins (bands of light running over a faint body)
    if camo:
        os.makedirs(f'{pack}/shaders', exist_ok=True)
        open(f'{pack}/shaders/hce_camo.fp', 'w').write(CAMO_SHADER)
        for t in sorted(set(camo)):
            gl.append(f'HardwareShader Texture "{t}"\n{{\n\tShader "shaders/hce_camo.fp"\n\tSpeed 1.0\n}}')
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
WEAPON_IDS[H2BEAM] = 'h2_beam_rifle'
BEAMRIFLE_CODE = '''
	// Halo 2's beam rifle, the way HaloDoom's behaves: a held purple beam that cooks whatever it stays on. Each burst
	// is ~1 s of beam (one trace a tic); the damage climbs while it holds the same target (to 3x in half a second)
	// and resets when it slips off. Between bursts the rifle cools down. The aim is the API's slow-tracking aim
	// point, so strafing drags the beam off you.
	// Each burst opens with ~0.9 s of aiming: a purple sniper glint flashes at the rifle and a thin, harmless
	// targeting laser runs to where it's aiming; then the beam fires, drawn with HaloDoom Evolved's own beam rifle
	// laser (the purple beam with its pink core, fading and spreading when it stops).
	Actor hce_beamVictim;
	double hce_beamRamp;
	const HCE_BEAM_AIM = 30;
	override void HCE_FireShot(bool special)
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
		vector3 d = level.Vec3Diff(from, to);
		double len = d.Length();
		if(hce_burstShot < HCE_BEAM_AIM)
		{
			if(hce_burstShot == 0) A_StopSound(CHAN_WEAPON);               // the beam's hum starts with the beam
			HCE_SniperGlint(level.Vec3Diff(pos, from), hce_burstShot);
			if(len >= 1) HCE_AimLaser(from, to);                          // the targeting laser
			if(hce_burstShot == HCE_BEAM_AIM - 1 && hce_fireSound.Length() > 0) A_StartSound(hce_fireSound, CHAN_WEAPON, CHANF_LOOPING, 0.8);
			hce_burstShot++;
			return;
		}
		if(len >= 1)
		{
			HCE_HeldBeam(from, to);                                         // HDE's beam rifle laser: purple beam, pink core
			if(level.maptime % 3 == 0)
				A_SpawnParticle("D080FF", SPF_FULLBRIGHT, 10, 6, 0, to.x - pos.x, to.y - pos.y, to.z - pos.z, frandom(-0.5, 0.5), frandom(-0.5, 0.5), frandom(0.3, 1.0), 0, 0, 0, 0.8, -0.06);
		}
		Actor hit = lt.HitActor;
		if(hit && hit != self && hit.bSHOOTABLE && hit.health > 0)
		{
			hce_beamRamp = hit == hce_beamVictim ? min(3.0, hce_beamRamp + 2.0 / 17) : 1.0;
			hce_beamVictim = hit;
			int dmg = max(1, int(round(3.0 * hce_beamRamp * HCE_DamageScale())));
			hit.DamageMobj(self, self, dmg, 'Fire');
		}
		else { hce_beamVictim = null; hce_beamRamp = 1.0; }
		if(hce_moveSpeed <= 0.1 && hce_burstShot % 10 == 0 && HCE_HasAnim(HCE_A_FIRE)) HCE_Play(HCE_A_FIRE, false, true, 2);
		hce_burstShot++;
	}
'''


MAIN_WEAPONS = set(WEAPONS)
MAIN = dict(char_of_unit=CHAR_OF_UNIT, team=TEAM, ai=AI, pack=PACK, mdir='hce', tag='hce', ed0=30200, main=True,
            handler='HCE_ReplaceHandler', index='pack_index.json')
CHAR_OVERRIDES = {}   # per-character tweaks (used by add-on packs: see build_digsite.py)
WEAPON_CODE = {'beam rifle': BEAMRIFLE_CODE}      # extra ZScript for every variant carrying a weapon
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
    'rocket launcher':  ('rocket_launcher', 'rifle', 7, 25, 45, None, 0.5, 'Halo_RocketLauncher'),
    'hydra':            ('hydra', 'rifle', 6, 24, 45, None, 1.5, 'Halo_Hydra'),
    'grenade launcher': ('grenade_launcher', 'rifle', 5, 18, 30, None, 1.0, 'Halo_GrenadeLauncher'),
    'sticky detonator': ('sticky_detonator', 'rifle', 4, 14, 25, None, 1.0, 'Halo_StickyDetonator'),
    'gpmg':             ('gpmg', 'rifle', 3, 18, 35, None, None, 'Halo_GPMG'),
    'flamethrower':     ('flamethrower', 'rifle', 1, 5, 8, None, None, 'Halo_Flamethrower'),
}
# Halo CE's own refs where CE has the weapon (its trigger data and projectile); new ones get an hde\ ref
ARSENAL_REF = {'pistol': r'weapons\pistol\pistol', 'sniper rifle': r'weapons\sniper rifle\sniper rifle',
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
})
for _k, _snd in {'sidekick': 'Sidekick', 'ma37': 'Rifle', 'commando': 'Commando', 'battle rifle': 'BattleRifle', 'dmr': 'DMR',
                 'smg': 'SMG', 'bulldog': 'Bulldog', 'double barrel': 'SuperShotgun', 'hydra': 'Hydra',
                 'sticky detonator': 'StickyDet', 'gpmg': 'GPMG', 'stanchion': 'Stanchion'}.items():
    FIRE_SOUNDS[_k] = (W + _snd + '/Fire', W + _snd + '/Fire/Bass' if _k not in ('hydra', 'sticky detonator') else '', '', '', False)
FIRE_SOUNDS['grenade launcher'] = (W + 'GrenadeLauncher/Fire', '', '', '', False)
FIRE_SOUNDS['stanchion'] = (W + 'Stanchion/Fire', W + 'Stanchion/Fire/Bass', '', W + 'Stanchion/Charge/PreFire', False)
LOBBED.add('grenade launcher')
DROP_WEAPON.update({k: d[7] for k, d in MARINE_ARSENAL.items() if k not in DROP_WEAPON})
DROP_WEAPON['stanchion'] = 'Halo_Stanchion'

STICKY_CODE = """
	// the sticky detonator: the Marine sets each charge off a second and a half after it lands
	Array<Actor> hce_stickies;
	Array<int> hce_stickyAt;
	override void HCE_OnShot(Actor shot)
	{
		if(shot) { hce_stickies.Push(shot); hce_stickyAt.Push(level.maptime + 52); }
	}
	override void Tick()
	{
		super.Tick();
		for(int i = hce_stickies.Size() - 1; i >= 0; i--)
		{
			Actor c = hce_stickies[i];
			if(c && level.maptime < hce_stickyAt[i]) continue;
			if(c) { State st = c.FindState("ExplodeAndDie"); if(st) c.SetState(st); }
			hce_stickies.Delete(i); hce_stickyAt.Delete(i);
		}
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
		if(hce_cqc) { super.HCE_FireShot(special); return; }
		HCE_FireRail();
	}
"""
WEAPON_CODE['stanchion'] = STANCHION_CODE

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
            v['_ov'] = dict(overlay=ovl, stance=stance, pellets=pellets, spread=spread, skin_as=cname(f'{body} assault rifle'))
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

add_marine_arsenal(AI['variants'])

def arsenal_lines(char, name, meta, pack, mdir):
    """MODELDEF lines attaching a Marine arsenal overlay (model 6) and copying its files into the pack"""
    a = (meta.get('arsenal') or {}).get(name)
    if not a: raise SystemExit(f'{char}: no arsenal overlay {name!r} (run marine_arsenal.py overlays after blood_kit.py)')
    os.makedirs(f'{pack}/models/{mdir}/weapons', exist_ok=True)
    dst = f'{pack}/models/{mdir}/{char}/{a["model"]}'
    if not os.path.exists(dst): shutil.copy(f'{OUT}/models/{char}/{a["model"]}', dst)
    for m in a['materials']:
        d = f'{pack}/models/{mdir}/weapons/{m}'
        if not os.path.exists(d): shutil.copy(f'{OUT}/models/{char}/{m}', d)
    return ([f'\tPath "models/{mdir}/{char}"', f'\tModel {ARSENAL_IDX} "{a["model"]}"', f'\tPath "models/{mdir}/weapons"']
            + [f'\tSurfaceSkin {ARSENAL_IDX} {k} "{m}"' for k, m in enumerate(a['materials'])])

def johnson_code(A, animtxt, char, meta, mdir):
    """Sergeant Johnson: the Stanchion at range, the Magnum (Halo 2's pistol stance) when an enemy closes in"""
    cqc = zs_anim_funcs(A, anim_table(A, H2PISTOL_STANCE, 'pistol'))
    animtxt = (animtxt.replace('override Name HCE_AnimName(int kind)', 'Name HCE_AnimNameLong(int kind)')
                      .replace('override int HCE_AnimTics(Name anim)', 'int HCE_AnimTicsLong(Name anim)'))
    cqc = (cqc.replace('override Name HCE_AnimName(int kind)', 'Name HCE_AnimNameCQC(int kind)')
              .replace('override int HCE_AnimTics(Name anim)', 'int HCE_AnimTicsCQC(Name anim)'))
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
	Name hce_longProj; int hce_longShots[3]; double hce_longPause[2]; double hce_longErr, hce_longSpeed, hce_longRange[2];
	String hce_longSound[3];
	override void PostBeginPlay()
	{{
		super.PostBeginPlay();
		hce_voice = 'Marine_Johnson';
		hce_longProj = hce_projectile; hce_longErr = hce_errorAngle; hce_longSpeed = hce_projSpeed;
		hce_longShots[0] = hce_patShotsMin; hce_longShots[1] = hce_patShotsMax; hce_longShots[2] = hce_patInterval;
		hce_longPause[0] = hce_patPauseMin; hce_longPause[1] = hce_patPauseMax;
		hce_longRange[0] = hce_rangeMin; hce_longRange[1] = hce_rangeMax;
		hce_longSound[0] = hce_fireSound; hce_longSound[1] = hce_fireSoundBass; hce_longSound[2] = hce_chargeSound;
	}}
	override void Tick()
	{{
		super.Tick();
		if(health <= 0 || !target || level.maptime % 6) return;
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
MAIN_WEAPONS |= set(WEAPONS)

if __name__ == '__main__':
    build()
