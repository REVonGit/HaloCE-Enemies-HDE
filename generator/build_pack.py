"""Generate the Halo CE enemy pack: ZScript classes, MODELDEF, skins, projectiles."""
import json, os, re, math, shutil, glob, zipfile, sys
import numpy as np
from PIL import Image

from hce_paths import OUT, PACK
S = 80.0                     # map units per Halo world unit
TICK = 30.0 / 35.0           # Halo ticks per Doom tic
DEG = 180.0 / math.pi

AI = json.load(open(f'{OUT}/ai_data.json'))
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
          'Jackal': 'Jackal', 'JackalMajor': 'Jackal', 'Hunter': 'Hunter'}
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
    'Jackal': '4A2A9A', 'JackalMajor': '4A2A9A',                          # Kig-Yar: dark blue/purple (CE)
    'Grunt': '40C8D0', 'GruntSpecOps': '40C8D0',                          # Unggoy: light blue / teal
    'Hunter': 'FF8C1A',                                                   # Mgalekgolo: bright orange
    'Brute': '161C40',                                                    # Jiralhanae (Halo 2): dark navy blue / black
    'Drone': 'DDF0D2',                                                    # Yanme'e: white, slight green tint
    'Engineer': 'E0607A',                                                 # Huragok: reddish pink
    'FloodInfection': '76703A', 'FloodCarrier': '76703A', 'FloodElite': '76703A', 'FloodHuman': '76703A',  # Flood: brownish green
    'Marine': 'A01010', 'MarineArmored': 'A01010',                        # human: red
    'SlugMan': '9AB040', 'Drinol': '8A1A10', 'BlindWolf': 'A01010', 'ThornBeast': '7A1A30',  # Digsite / SPV3 creatures
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
    return m

KINDS = ['IDLE', 'ALERT', 'MOVE_F', 'MOVE_B', 'MOVE_L', 'MOVE_R', 'CROUCH_IDLE', 'CROUCH_MOVE', 'FLEE', 'FIRE', 'MELEE',
         'THROW', 'DIVE_L', 'DIVE_R', 'DIVE_F', 'EVADE_L', 'EVADE_R', 'SURPRISE_F', 'SURPRISE_B', 'BERSERK', 'WARN',
         'SIGNAL', 'AIRBORNE', 'LAND', 'LEAP_START', 'LEAP_AIR', 'LEAP_MELEE', 'PING_F', 'PING_B', 'PING_L', 'PING_R',
         'HPING_F', 'HPING_B', 'DIE_F', 'DIE_B', 'DIE_L', 'DIE_R', 'DIE_HARD_F', 'DIE_HARD_B', 'DIE_AIR', 'DIE_LAND',
         'RESURRECT_F', 'RESURRECT_B', 'FEED', 'CELEBRATE', 'SLEEP', 'TURN_L', 'TURN_R']

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
SHIELD_TINT = {'minor': (0.20, 0.35, 1.00), 'major': (1.00, 0.55, 0.10), 'ultra': (1.00, 0.30, 0.85)}
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

def bake_skin(char, mat, color, outpath):
    base = Image.open(f'{OUT}/models/{char}/{mat}.png').convert('RGB')
    mp = f'{OUT}/models/{char}/{mat}_multi.png'
    if color is None or not os.path.exists(mp):
        base.save(outpath); return
    mask = Image.open(mp).convert('RGBA').resize(base.size)
    b = np.asarray(base).astype(np.float32) / 255.0
    msk = np.asarray(mask).astype(np.float32)[..., 2:3] / 255.0   # Xbox: blue = colour change
    col = np.array(color, dtype=np.float32).reshape(1, 1, 3)
    o = b * (1 - msk) + b * col * msk
    Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8)).save(outpath)

# ---------------------------------------------------------------- generation
def build(cfg=None):
    cfg = cfg or MAIN
    char_of_unit, team, ai, pack, mdir = cfg['char_of_unit'], cfg['team'], cfg['ai'], cfg['pack'], cfg['mdir']
    main = cfg.get('main', False)
    if os.path.exists(f'{pack}/models'): shutil.rmtree(f'{pack}/models')
    os.makedirs(f'{pack}/ZScript/HaloCE', exist_ok=True)
    metas = {c: json.load(open(f'{OUT}/models/{c}/{c}.json')) for c in set(char_of_unit.values())}
    zs = []; md = []; ednums = []; spawners = {}; late = []; brightmaps = []
    projectiles_used = set()
    ed = cfg['ed0']
    # ---------------- per character base classes
    for unit, char in sorted(char_of_unit.items(), key=lambda x: x[1]):
        meta = metas[char]
        b = ai['bipeds'][unit]
        ov = CHAR_OVERRIDES.get(char, {})
        os.makedirs(f'{pack}/models/{mdir}/{char}/skins', exist_ok=True)
        shutil.copy(f'{OUT}/models/{char}/{char}.iqm', f'{pack}/models/{mdir}/{char}/{char}.iqm')
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
                  f'\toverride void HCE_ApplyAnim(Name n, int blend, bool loop)\n\t{{\n\t\tSetAnimation(n, -1, -1, -1, -1, blend, loop ? SAF_LOOP : 0);\n\t}}\n}}\n')
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
            elif char.startswith('Grunt') and weapon and 'fuel rod' in weapon: w = 'missle'
            elif char.startswith('Elite') and weapon == 'energy sword': w = 'sword'
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
            for si, mat in enumerate(meta['meshes']):
                matn = mat[:-4]
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
                    if r is not None:
                        skin_lines.append(f'\tSurfaceSkin 0 {si} "skins/{r}"')
                        continue
                fn = f'{cls[4:].lower()}_{matn.lower()}.png'
                dst = f'{pack}/models/{mdir}/{char}/skins/{fn}'
                if not os.path.exists(dst):
                    if v.get('_hunter_color'): bake_hunter(char, matn, v['_hunter_color'], dst)
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
            extra = TYPE_CODE.get(char, '') + WEAPON_CODE.get(weapon or '', '') + ov.get('code', '')
            if ov.get('weapon_toss'):
                # hide the held weapon's surfaces at runtime (a Brute throwing its gun away to go berserk)
                ws = [si for si, wv in enumerate(mesh_weapon) if wv]
                extra += '\tvoid HCE_HideWeaponSurfaces()\n\t{\n' + ''.join(
                    f'\t\tA_ChangeModel(\'\', 0, "", \'\', {si}, "models/{mdir}/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n' for si in ws) + '\t}\n'
            zs.append(f'// {vname}\nclass {cls} : HCE_{char}Base\n{{\n\tDefault\n\t{{\n{props}\t}}\n{zs_anim_funcs(A, table, ov.get('berserk_anims', BERSERK_ANIMS.get(char)))}\n{extra}}}\n')
            if weapon_lines: skin_lines += [f'\tPath "models/{mdir}/weapons"'] + weapon_lines
            sc = S * msc
            md.append(f'Model {cls}\n{{\n\tPath "models/{mdir}/{char}"\n\tModel 0 "{char}.iqm"\n' + '\n'.join(skin_lines) +
                      f'\n\tScale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}\n\tUseActorPitch\n\tBaseFrame\n\tFrameIndex HCEM A 0 0\n}}\n')
            if v.get('_late'): late.append(cls)
            else: ednums.append((ed, cls)); ed += 1
            spawners.setdefault(char, []).append(cls)
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
    LATE_ORDER = cfg.get('late_order', ['HCE_JackalUltraNeedler', 'HCE_HunterWhite', 'HCE_HunterRed'])
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
    mi = ['DoomEdNums', '{'] + [f'\t{n} = {c}' for n, c in ednums] + ['}', '', 'GameInfo', '{', f'\tAddEventHandlers = "{cfg["handler"]}"', '}', '']
    open(f'{pack}/mapinfo.txt', 'w').write('\n'.join(mi))
    json.dump(dict(ednums=ednums, spawners=spawners), open(f'{OUT}/{cfg["index"]}', 'w'), indent=1)
    print('classes', len(ednums), 'projectiles', len(done))

# per-character extra ZScript (Flood corpse feeding, carrier pop, infection pop)
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

if __name__ == '__main__':
    build()
