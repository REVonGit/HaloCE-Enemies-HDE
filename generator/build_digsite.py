"""Digsite add-on pack: Drinol, Slug Man (particle beam rifle / plasma pistol) and plasma-carbine Elites in a
rifle stance.  Generated with build_pack.build() so the classes behave exactly like the main pack's.

Needs out/models/{Drinol,SlugMan,EliteRifle} (extract_digsite.py, extract_elite_rifle.py) and the weapon pkls
(extract_weapons.py, extract_h2.py; the Covenant carbine is CMT's, the beam rifle Halo 2's: nothing from Sketchfab
ships any more).  Digsite content is licensed for MCC projects only: never part of a public release.

    python3 build_digsite.py        # after build_pack.py, gore_kit.py, blood_kit.py and marine_arsenal.py overlays

Since the first release the add-on has grown past Digsite's three: SPV3's Blind Wolf and Engineer
(extract_spv3.py), Halo 2's Drones, Brutes and Jackals (extract_h2*.py) and the Ultra Zealot (extract_ultra_zealot.py)
are built here too, each when its out/models/<Char>/<Char>.json exists. Everything is written to addons/digsite/
(hce_paths.DIG_PACK), wiped first: the ZScript (bp.build with cfg tag 'dig'), modeldef.dig, gldefs.dig, sndinfo.dig,
models/hce_dig/ and the hand-written digsite_src/ files copied in.

How it works: configure() extends build_pack's tables (weapons, fire patterns, sounds, skin hooks, per-character
overrides) with the add-on's guns and characters; load_ai() builds the add-on's variant / actor / biped tables, partly
from Digsite's tags and partly by copying and re-statting the main pack's (bp.AI); build() hands both to
build_pack.build() and then adds what the generic builder doesn't do (helmet debris, the Captain's flag, the kit).
The *_skin functions are build_pack.SKIN_HOOK callbacks: (class, variant, surface index, material, model json, skin
dir) -> the skin file name to use, or None for the default bake. DoomEdNums start at 30400; classes marked _late keep
the first release's numbers (digsite_index.json, bp.build's late_order)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, copy, shutil, subprocess, glob
import numpy as np
from templates import template   # templates/: the ZScript and GLSL written into the pack as-is
from PIL import Image, ImageFilter
import build_pack as bp
from looset import LooseMap
from extract_ai import dump, flatten_obj
from halosound import parse as parse_sound, decode, to_wav

from hce_paths import DIGSITE, DIG_PACK as PACK, HERE, OUT
T = DIGSITE + '/tags/'
S = bp.S

# weapon and character references as the variant tables name them (Halo tag paths, or made-up ones for guns Halo CE
# never had); bp.WEAPON_IDS maps a weapon reference to its pkl under out/weapons (configure)
CARBINE = r'digsite\weapons\plasma carbine'
BEAM = r'digsite\weapons\particle beam'
PULSE = r'digsite\weapons\pulse carbine'
DRONE = r'characters\drone\drone'
BRUTE = r'characters\brute\brute'
CE_PR = r'weapons\plasma rifle\plasma rifle'
CE_AR = r'weapons\assault rifle\assault rifle'
CE_SG = r'weapons\shotgun\shotgun'
SPIKER = r'h3\weapons\spiker'
HAMMER = r'h2\weapons\gravity hammer'
CASTER = r'hde\plasma caster'           # HDE's Plasma Caster as a Halo CE gun (plasma_caster_ce.py): an overlay model
BRUTE_HUMAN_GUNS = ('bulldog', 'double_barrel', 'gpmg', 'rocket_launcher', 'grenade_launcher', 'hydra', 'flamethrower', 'ma37', 'smg')
BRUTE_SUPPORT = ('gpmg', 'flamethrower')  # held in Halo 2's Brute Shot stance; the rest one-handed (the rifle stance)
CASTER_IDX = 8                          # its model attachment (the armour kit uses 1-6, blood 7)
FUEL_ROD = r'weapons\fuel rod gun\fuel rod'
# the Covenant's two-handed guns the Brutes carry (Halo 2 and 3's Brutes do), held in the two-handed carbine stance:
# weapon reference -> (its overlay model: marine_arsenal.BRUTE_COV_GUNS, combat range low / high, firing range, in
# world units: the carbine like the Jackal Marksmen's, the beam rifle like the Jackal Snipers', the fuel rod mid-range)
BRUTE_COV_TWO_HANDED = {r'digsite\weapons\plasma carbine': ('plasma_carbine', 6.0, 22.0, 40.0),
                        r'h2\weapons\beam rifle': ('beam_rifle', 8.0, 28.0, 48.0),
                        FUEL_ROD: ('fuel_rod', 4.0, 16.0, 30.0)}
# Halo 2 Brute ranks: body vitality from their char tags (08b: the honor guard inherits brute_major's); hlmt
# variant -> region permutations they wear; fur colours come from the biped's per-variant change colours.
# Loadouts (all rifle stance): CE plasma rifle / assault rifle / shotgun, the Majors carry the Spiker, Captains
# may carry the Plasma Caster.
# Minors, Majors and Captains wear only their body here: their helmets and armour come from the armour kit
# (extract_brute_kit.py, KIT_JSON), rolled per Brute when it spawns (brute_code / kit_code).
# The Chieftain is a custom rank: Tartarus's look, hammer stance and gravity hammer.
# rank -> body (health), variants (the hlmt variants whose fur colours the loadouts cycle through), weapons (one class
# per weapon reference), wear {(region, permutation)} the body shows (brute_skin hides the rest). To make a rank
# tougher raise body; to arm it add a reference to weapons (and the gun to bp.WEAPONS / PATTERNS / FIRE_SOUNDS if it
# is new); a new rank also needs its name in the class-name tests of kit_code / brute_code and in build()'s late_order.
BRUTE_RANKS = {
    'minor': dict(body=175, variants=('minor_bth', 'minor_crl'), weapons=(CE_PR, CE_AR),
                  wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default')}),
    'major': dict(body=150, variants=('major_bth', 'major_crl'), weapons=(SPIKER, CE_SG, CARBINE),
                  wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default')}),
    'captain': dict(body=200, variants=('captain_bth', 'captain_crl'), weapons=(CE_PR, CE_SG, CASTER, bp.H2BEAM_REF),
                    wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default'), ('flag', 'captain')}),
    'honor guard': dict(body=150, variants=('minor_bth', 'minor_crl'), weapons=(CE_PR, CE_AR, FUEL_ROD),
                        wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'honor_on'), ('sensors', 'honor_on'),
                              ('sh_armor', 'honor_on'), ('hg_arm', 'honor_on'), ('hg_legs', 'honor_on')}),
    # the Stalker (Halo 3): a Major in active camo with the Spiker, no armour kit (its camo would show the pieces up)
    'stalker': dict(body=150, variants=('major_bth',), weapons=(SPIKER,),
                    wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default')}),
    # the jump-pack Brute (Halo 3): a Major always in the kit's Halo 3 jump-pack suit, hopping about the fight on it
    # (HCE_Jetpack: the Elite Rangers' jump-pack hops), with the Spiker or the plasma rifle
    'jump pack': dict(body=150, variants=('major_bth', 'major_crl'), weapons=(SPIKER, CE_PR),
                      wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default')}),
    'chieftain': dict(body=350, variants=('tartarus',), weapons=(HAMMER,),
                      wear={('body', 'default'), ('head', 'default'), ('helmet', 'honor_off'), ('helmet', 'tartarus'),
                            ('sensors', 'default'), ('sh_armor', 'skull'), ('hg_arm', 'honor_off'), ('hg_legs', 'honor_off')}),
}
ELITE_RIFLE = r'characters\elite\elite rifle'
ULTRA_ZEALOT = r'characters\elite\elite ultra zealot'
ZEALOT_RED = (0.55, 0.06, 0.14)          # Reach's Field Marshal maroon, deeper and richer
ZEALOT_BLUE = (0.22, 0.55, 1.00)         # its shield, as its lights
KIT_DIR = f'{bp.OUT}/models/BruteKit'
KIT_JSON = f'{KIT_DIR}/BruteKit.json'
KIT_RANKS = ['minor', 'major', 'captain', 'chieftain']     # the kit's rank tables in order: index r in kit_code's ZScript
# Halo 2 Jackals (extract_h2_jackal.py): one model, three ranks. Ultra (the CE pack's plasma-rifle Ultra moved onto
# the Halo 2 body, same class and DoomEdNum), Zealot (Spiker, gold shield) and Sniper (Halo 2's beam rifle, no shield)
H2JACKAL = r'objects\characters\jackal\jackal'
H2BEAM = bp.H2BEAM
H2J_JSON = f'{bp.OUT}/models/H2Jackal/H2Jackal.json'
H2J_NO_SHIELD = ('sniper', 'marksman')        # ranks that carry no arm shield (Halo 3's long-range Jackals)
# armour change colours per rank (primary, secondary, tertiary): Ultra and Sniper take the Halo 2 major / minor
# biped colours; the Zealot is a custom gold with pale trim
# the Halo 2 Jackals' outfit rendered like Halo CE's Jackal (h2jackal_skin): its suit in CE's dark navy leather with the
# rank colour tinting it (k: how much), its plates in CE's beige steel, Halo's silver cube reflection on them
# (rank: (how much, how bright)); the tint is the rank's tertiary change colour, its vivid one (Halo 2's suit shader takes
# only the primary, a pale orange or steel blue that turns muddy on the dark leather): red for Majors, deep blue for Minors
H2J_SUIT, H2J_PLATE = (0.18, 0.19, 0.22), (0.52, 0.47, 0.45)
H2J_SUIT_TINT = {'default': (0.55, 0.45), 'zealot': (0.8, 0.62)}
bp.SHINE['H2Jackal'] = 0.3; bp.SHINE_CUBE['H2Jackal'] = 'elite'
# rank -> either a Halo 2 biped variant name (its change colours, read from H2Jackal.json) or an explicit
# [primary, secondary, tertiary] colour list; h2jackal_skin tints the suit with the tertiary
H2J_COLOURS = {'ultra': 'major', 'major': 'major', 'sniper': 'minor', 'marksman': 'major',
               'zealot': [[1.0, 0.84, 0.32], [0.95, 0.92, 0.80], [0.85, 0.62, 0.16]]}

# Slug Man ranks: health and aim (error-angle multiplier) and the armour colour repainted over the skin (slug_skin)
SLUG_RANKS = {'minor': dict(health=1.0, accuracy=1.0, tint=bp.MINOR_BLUE),          # the Elites' Minor blue
              'major': dict(health=1.35, accuracy=0.9, tint=(0.58, 0.17, 0.15)),
              'ultra': dict(health=1.8, accuracy=0.75, tint=(0.80, 0.82, 0.88)),
              'zealot': dict(health=2.2, accuracy=0.65, tint=(0.86, 0.64, 0.16))}       # gold, the top rank (rarest)
# weapon key -> (its reference, which of the two Digsite Slug Man variants it copies: the 'pistol' one or the 'rifle'
# one, which sets the stance and the combat data); SLUG_RANK_WEAPONS says which keys each rank fields (one class each)
SLUG_WEAPONS = {'plasma pistol': (r'weapons\plasma pistol\plasma pistol', 'pistol'), 'needler': (r'weapons\needler\needler', 'pistol'),
                'plasma rifle': (r'weapons\plasma rifle\plasma rifle', 'pistol'), 'particle beam': (r'digsite\weapons\particle beam', 'rifle'),
                'plasma carbine': (r'digsite\weapons\plasma carbine', 'rifle'), 'pulse carbine': (r'digsite\weapons\pulse carbine', 'rifle')}
SLUG_RANK_WEAPONS = {'minor': ['needler', 'plasma rifle', 'plasma carbine'],
                     'major': ['plasma pistol', 'needler', 'plasma rifle', 'particle beam', 'plasma carbine', 'pulse carbine'],
                     'ultra': ['plasma rifle', 'particle beam', 'plasma carbine'],
                     'zealot': ['plasma rifle', 'particle beam', 'pulse carbine']}

# the Slug Men's armour reflection (slug_skin_act): the Elite cube of each rank's colour, and its strength
SLUG_CUBE = {'minor': 0, 'major': 1, 'ultra': 3, 'zealot': 2}
SLUG_SHINE_K = 0.3


def slug_skin_act(rank, mat, act, skin_dir):
    """the Slug Man's skin from the Assorted Character Tags Pack's multipurpose map (act_slugman.py): its plates
    (alpha) repainted in the rank's colour over the map's clean armour shading (blue), the flesh and the dark metal
    left as Digsite's colour map has them, then the Elites' baked cube-map reflection on the plates"""
    from scipy import ndimage
    from texmath import bake_reflection
    fn = f'slugman_{rank}_{mat[:-4].lower()}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    os.makedirs(skin_dir, exist_ok=True)
    a = np.asarray(Image.open(f'{bp.OUT}/models/SlugMan/{mat}').convert('RGB')).astype(float) / 255.0
    mu = np.asarray(Image.open(act).convert('RGBA').resize(a.shape[1::-1])).astype(float) / 255.0
    shade, m = mu[..., 2], ndimage.gaussian_filter(mu[..., 3], 0.7)
    c = np.array(SLUG_RANKS[rank]["tint"])[None, None] * (0.15 + 0.8 * shade[..., None]) + shade[..., None] ** 4 * 0.08
    out = a * (1 - m[..., None]) + np.clip(c, 0, 1) * m[..., None]
    faces = bp.cube_faces('elite', SLUG_CUBE.get(rank, 0))
    if faces is not None:
        n = bp.normal_map('SlugMan', mat[:-4], out.shape[1::-1]).copy()
        out = bake_reflection(out.astype(np.float32), n, (m * 0.75).astype(np.float32), faces, SLUG_SHINE_K)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(dst)
    return fn


def slug_skin(cls, v, si, mat, meta, skin_dir):
    """Slug Man armour, repainted clean. Digsite's armour texture is grainy and scuffed; the plates (where the
    multipurpose map's specular mask says metal, the flesh it marks green left alone) are repainted in the rank's
    colour over smooth shading: the base map's light and shade with the grain taken out (a median filter, then a
    light blur) blended with the multipurpose map's own smooth shading, and a soft highlight on the raised parts.
    Every Slug Man gets it; the original two (no rank) are Minors."""
    rank = v.get('_slug_rank') or 'minor'
    if not mat.startswith('SlugMan_'): return None
    act = f'{bp.OUT}/models/SlugMan/{mat[:-4]}_act_multi.png'
    if os.path.exists(act): return slug_skin_act(rank, mat, act, skin_dir)
    multi = f'{bp.OUT}/models/SlugMan/{mat[:-4]}_multi.png'
    if not os.path.exists(multi): return None
    fn = f'slugman_{rank}_{mat[:-4].lower()}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    os.makedirs(skin_dir, exist_ok=True)
    from scipy import ndimage
    a = np.asarray(Image.open(f'{bp.OUT}/models/SlugMan/{mat}').convert('RGB')).astype(float) / 255.0
    mu = np.asarray(Image.open(multi).convert('RGBA').resize(a.shape[1::-1])).astype(float) / 255.0
    r, g = mu[..., 0], mu[..., 1]
    m = np.clip((r - 0.06) / 0.1, 0, 1) * np.clip(1 - (g - r * 0.6) / 0.15, 0, 1)
    m = ndimage.gaussian_filter(m, 0.8)
    def norm(x):
        """stretch x to 0..1 over the plate region (3rd..97th percentile where the mask m is on)"""
        w = m > 0.5
        lo, hi = np.percentile(x[w], 3), np.percentile(x[w], 97)
        return np.clip((x - lo) / max(hi - lo, 1e-3), 0, 1)
    sm = ndimage.gaussian_filter(ndimage.median_filter(a.mean(2), 5), 1.2)
    shade = (0.55 * norm(sm) + 0.45 * norm(ndimage.gaussian_filter(r, 0.8)))[..., None]
    c = np.array(SLUG_RANKS[rank]['tint'])[None, None] * (0.35 + 0.85 * shade) + shade ** 4 * 0.18
    out = a * (1 - m[..., None]) + np.clip(c, 0, 1) * m[..., None]
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(dst)
    return fn

# the Chieftain's animation table while berserk (the Brute's own, bp.BERSERK_ANIMS['Brute'], is the bare-handed
# charge): action -> the Halo 2 animation names rolled for it ('name%4': the extractors' name for a multi-take
# animation's fifth permutation)
CHIEFTAIN_BERSERK = {
    'IDLE': ['berserk hammer idle'], 'ALERT': ['berserk hammer idle'], 'MOVE_F': ['berserk hammer move-front'],
    'MOVE_B': ['berserk hammer move-front'], 'MOVE_L': ['berserk hammer move-front'], 'MOVE_R': ['berserk hammer move-front'],
    'FLEE': ['berserk hammer move-front'], 'TURN_L': ['stand melee turn-left'], 'TURN_R': ['stand melee turn-right'],
    'MELEE': ['berserk hammer melee 1', 'berserk hammer melee 2', 'stand melee melee%4', 'stand melee melee%5']}

def load_ai():
    """the add-on's AI tables in build_pack's layout: dict(variants, actors, bipeds, collisions, weapons). Digsite's
    Drinol and Slug Man come from its loose tags; everything else is a deep copy of a main-pack variant (bp.AI)
    re-pointed at the add-on's body and gun and re-statted (health, shield, ranges, grenades), with the private
    keys the builder reads (_late, _rank, _ov overrides, _brute_rank / _brute_variant, _slug_rank, _helmet). Each
    Halo 2 / SPV3 character is added only when its extracted model is present."""
    m = LooseMap()
    variants, actors, bipeds = {}, {}, {}
    for vp in [r'digsite\characters\drinol\00_mac\drinol', r'digsite\characters\slug_man\slug_man particle beam',
               r'digsite\characters\slug_man\slug_man plasma pistol']:
        t = m.load(T + vp.replace('\\', '/') + '.actor_variant', vp)
        v = dump(m, 'actor_variant_definition', t['data'])
        v['change_colors_list'] = []
        ref = v['ranged_combat']['reference'] or ''
        if 'particle_beam' in ref: v['ranged_combat']['reference'] = BEAM
        ar, ur = v['actor_reference'], v['unit_reference']
        if ar not in actors:
            ta = m.load(T + ar.replace('\\', '/') + '.actor', ar)
            actors[ar] = dump(m, 'actor_definition', ta['data'])
        if ur not in bipeds:
            tb = m.load(T + ur.replace('\\', '/') + '.biped', ur)
            b = flatten_obj(dump(m, 'biped_definition', tb['data']))
            b['change_colors_list'] = []
            bipeds[ur] = b
        variants[vp] = v
    # Slug Man ranks (added after the first add-on release): Minor / Major / Ultra in the pistol stance (plasma
    # pistol, needler, plasma rifle) and the rifle stance (particle beam, plasma carbine, pulse carbine), each rank's
    # armour repainted in its colour (slug_skin); the two original Slug Men are painted as Minors
    pp, pb = variants[r'digsite\characters\slug_man\slug_man plasma pistol'], variants[r'digsite\characters\slug_man\slug_man particle beam']
    for rank, weps in SLUG_RANK_WEAPONS.items():
        hp, err = SLUG_RANKS[rank]['health'], SLUG_RANKS[rank]['accuracy']
        for key in weps:
            ref, src = SLUG_WEAPONS[key]
            sv = copy.deepcopy(pp if src == 'pistol' else pb)
            sv['ranged_combat']['reference'] = ref
            sv['unit'] = dict(sv['unit'], maximum_body_vitality=(sv['unit']['maximum_body_vitality'] or 60) * hp)
            sv['ranged_combat']['projectile_error_angle'] = sv['ranged_combat']['projectile_error_angle'] * err
            if key in ('plasma carbine', 'pulse carbine'):
                rc = sv['ranged_combat']
                rc['combat_range_lower_bound'] = max(rc['combat_range_lower_bound'], 3.0)
                rc['combat_range_upper_bound'] = max(rc['combat_range_upper_bound'], 12.0)
            sv['_slug_rank'] = rank
            sv['_late'] = True
            variants[rf'digsite\characters\slug_man\slug_man {rank} {key}'] = sv
    # Elites with the plasma carbine: the CE plasma-rifle ranks re-armed (longer reach, same colours)
    A = bp.AI
    for src in [r'characters\elite\elite minor\elite minor plasma rifle', r'characters\elite\elite major\elite major plasma rifle',
                r'characters\elite\elite specops\elite specops plasma rifle', r'characters\elite\elite commander\elite commander plasma rifle',
                r'characters\elite\elite honor guard\elite honor guard plasma rifle', r'characters\elite\elite ranger\elite ranger plasma rifle']:
        if src not in A['variants']: continue
        v = copy.deepcopy(A['variants'][src])
        v['unit_reference'] = ELITE_RIFLE
        rc = v['ranged_combat']
        rc['reference'] = CARBINE
        rc['combat_range_lower_bound'] = max(rc['combat_range_lower_bound'], 3.0)
        rc['combat_range_upper_bound'] = max(rc['combat_range_upper_bound'] * 1.4, 12.0)
        rc['maximum_firing_range'] = max(rc['maximum_firing_range'], 25.0)
        variants[src.replace('plasma rifle', 'plasma carbine')] = v
        actors[v['actor_reference']] = A['actors'][v['actor_reference']]
        if 'honor guard' in src or 'ranger' in src: v['_late'] = True; continue    # Halo 2's ranks: the plasma carbine only
        # blue Pulse Carbine version of the same rank (added after the first add-on release)
        p = copy.deepcopy(v)
        p['ranged_combat']['reference'] = PULSE
        p['_late'] = True
        variants[src.replace('plasma rifle', 'pulse carbine')] = p
    bipeds[ELITE_RIFLE] = copy.deepcopy(A['bipeds'][r'characters\elite\elite'])
    colls = dict(A['collisions'])
    sp = OUT + '/spv3_ai.json'           # extract_spv3.py (Blind Wolf from SPV3's a30)
    if os.path.exists(sp):
        S3 = json.load(open(sp))
        for v in S3['variants'].values(): v['_late'] = True    # keeps the first add-on release's DoomEdNums
        # the Engineer carries no weapon: a harmless floating hazard (class HCE_Engineer)
        eng = S3['variants'].pop(r'characters\engineer\engineer major plasma pistol', None)
        if eng:
            eng = copy.deepcopy(eng)
            eng['ranged_combat']['reference'] = None
            eng['items']['grenades_upper_bound'] = 0; eng['items']['grenades_lower_bound'] = 0
            S3['variants'][r'characters\engineer\engineer'] = eng
        variants.update(S3['variants']); actors.update(S3['actors']); bipeds.update(S3['bipeds']); colls.update(S3['collisions'])
    # Halo 2 Drone (extract_h2.py): its character tag only sets 30 body / no shield and evasion; the rest of its AI
    # comes from ai\generic, so it starts from the CE minor Jackal's plasma-pistol combat data
    if os.path.exists(OUT + '/models/Drone/Drone.json'):
        jv = copy.deepcopy(A['variants'][r'characters\jackal\jackal minor plasma pistol'])
        jv['unit_reference'] = DRONE; jv['actor_reference'] = DRONE
        jv['unit'] = dict(jv['unit'], maximum_body_vitality=30.0, maximum_shield_vitality=0.0)
        jv['items']['grenades_upper_bound'] = 0; jv['items']['grenades_lower_bound'] = 0
        jv['grenade_combat']['throw_grenade_chance'] = 0.0
        rc = jv['ranged_combat']
        rc['combat_range_lower_bound'] = 2.5; rc['combat_range_upper_bound'] = 7.0
        jv['change_colors_list'] = []
        jv['_late'] = True
        variants[DRONE + ' plasma pistol'] = jv
        # the other one-handed Covenant guns the Drone model carries (extract_h2.DRONE_WEAPONS)
        for wref, key in ((r'weapons\needler\needler', 'needler'), (CE_PR, 'plasma rifle'), (SPIKER, 'spiker')):
            dv = copy.deepcopy(jv)
            dv['ranged_combat']['reference'] = wref
            variants[DRONE + ' ' + key] = dv
        # Halo 2's Drone ranks (extract_h2_drone_ranks.py: Ruby of Blue's rank tags): the Minors above are the plain
        # Drones; each other rank gets its legendary body/shield and its plate colour (drone_skin), with two loadouts
        for rank, guns in DRONE_RANKS.items():
            rd = drone_ranks().get(rank)
            if not rd: continue
            for wref in guns:
                dv = copy.deepcopy(jv)
                dv['ranged_combat']['reference'] = wref
                dv['unit'] = dict(dv['unit'], maximum_body_vitality=float(rd['body']), maximum_shield_vitality=float(rd['shield']))
                dv['_rank'] = rank
                if rd['shield'] > 0: dv['_ov'] = dict(shield=int(rd['shield']))
                variants[f'{DRONE} {rank.replace("_", " ")} {wref.split(chr(92))[-1]}'] = dv
        actors[DRONE] = copy.deepcopy(A['actors'][r'characters\jackal\jackal minor'])
        jb = copy.deepcopy(A['bipeds'][r'characters\jackal\jackal'])
        jb.update(collision_height_standing=0.55, collision_radius=0.27, flying_velocity=2.6)
        jb['change_colors_list'] = []
        bipeds[DRONE] = jb
    # Halo 2 Brutes (extract_h2_brute.py): Elite-major combat data, re-armed and re-statted from the Brute char tags
    if os.path.exists(OUT + '/models/Brute/Brute.json'):
        base_v = A['variants'][r'characters\elite\elite major\elite major plasma rifle']
        ba = copy.deepcopy(A['actors'][base_v['actor_reference']])
        bz = ba['berserk']
        bz.update(damage_berserk_amount=0.25, damage_berserk_threshold=0.45, proximity_berserk_distance=0.0,
                  melee_attack_range=1.5, melee_attack_delay_timer=4.0)
        actors[BRUTE] = ba
        bb = copy.deepcopy(A['bipeds'][r'characters\elite\elite'])
        bb.update(collision_height_standing=0.95, collision_radius=0.32); bb['change_colors_list'] = []
        bipeds[BRUTE] = bb
        for rank, rd in BRUTE_RANKS.items():
            for fur, wref in enumerate(rd['weapons']):
                v = copy.deepcopy(base_v)
                v['unit_reference'] = BRUTE; v['actor_reference'] = BRUTE
                v['unit'] = dict(v['unit'], maximum_body_vitality=float(rd['body']), maximum_shield_vitality=0.0)
                v['ranged_combat']['reference'] = wref
                gc = v['grenade_combat']                       # char tag: plasma grenades, 10%/s, 3-20 WU, 6 s apart
                gc.update(grenade_type=1, throw_grenade_chance=0.1, throw_grenade_delay=6.0,
                          grenade_range_lower_bound=3.0, grenade_range_upper_bound=20.0, grenade_velocity=10.0)
                v['items']['grenades_lower_bound'] = 1; v['items']['grenades_upper_bound'] = 2
                v['change_colors'] = None; v['change_colors_list'] = []
                v['_late'] = True; v['_brute_rank'] = rank; v['_brute_variant'] = rd['variants'][fur % len(rd['variants'])]
                if wref == CASTER:
                    v['_ov'] = dict(overlay='plasma_caster', overlay_idx=CASTER_IDX)
                if wref in BRUTE_COV_TWO_HANDED:                 # the Covenant long guns: drawn in the hand (overlay),
                    ovl, lo, hi, mx = BRUTE_COV_TWO_HANDED[wref]   # their own combat ranges
                    v['_ov'] = dict(overlay=ovl, overlay_idx=CASTER_IDX)
                    v['ranged_combat'].update(combat_range_lower_bound=lo, combat_range_upper_bound=hi, maximum_firing_range=mx)
                if rank == 'jump pack':    # the Rangers' jump-pack hops (enemies_base.zsc HCE_TryJet)
                    v['_ov'] = dict(v.get('_ov') or {}, add_flags=['HCE_Jetpack'])
                if rank == 'stalker':      # active camo (the Brutes' class flags replace the variant's: added on top)
                    v['flags'] = v.get('flags', 0) | (1 << 4)
                    v['_ov'] = dict(v.get('_ov') or {}, add_flags=['HCE_ActiveCamo'])
                if rank == 'chieftain':
                    # brute_tartarus char: 350 body (his 1000-point overshield cut to a breakable 150), no grenades,
                    # leaps 2.5-6 WU at 50%, smashes with the hammer's gravity shockwave (brute_code)
                    gc['throw_grenade_chance'] = 0.0; v['items']['grenades_lower_bound'] = v['items']['grenades_upper_bound'] = 0
                    v['_ov'] = dict(shield=150, melee=(60, 70), melee_only=True, speed=6.0, leap=(150, 400, 0.5, 13.0),
                                    flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Leaps', 'HCE_Leader'],
                                    berserk_anims=CHIEFTAIN_BERSERK)
                variants[f'{BRUTE} {rank} {wref.split(chr(92))[-1]}'] = v
        # human guns a Brute would take (the one Covenant race that uses them): loadouts only, no classes -- what a Brute
        # can pick up off the ground, drawn as overlay models in its overlay slot (marine_arsenal.brute_overlays)
        src = variants.get(f'{BRUTE} minor assault rifle')
        bmeta = json.load(open(OUT + '/models/Brute/Brute.json'))
        for key, (ovl, *_r) in bp.MARINE_ARSENAL.items():
            if not src or ovl not in BRUTE_HUMAN_GUNS or ovl not in (bmeta.get('arsenal') or {}): continue
            lo, hi, mx = _r[1], _r[2], _r[3]
            v = copy.deepcopy(src)
            v['ranged_combat']['reference'] = bp.ARSENAL_REF.get(key, 'hde\\' + key)
            v['ranged_combat'].update(combat_range_lower_bound=lo, combat_range_upper_bound=hi, maximum_firing_range=mx)
            v['_ov'] = dict(overlay=ovl, overlay_idx=CASTER_IDX, loadout_only=True, pellets=_r[4], spread=_r[5],
                            stance='support' if ovl in BRUTE_SUPPORT else 'carbine')    # human guns are two-handed
            variants[f'{BRUTE} minor {key} loadout'] = v
    # Halo 2 Jackals: the Ultra keeps the CE Ultra's combat data (moved out of the main pack, build_pack.MOVED); the
    # Zealot is a tougher Ultra with the Spiker; the Sniper starts from the CE Minor and keeps its distance
    ultra = bp.MOVED.get(r'characters\jackal\jackal ultra plasma rifle')
    if ultra and os.path.exists(H2J_JSON):
        actors[H2JACKAL] = copy.deepcopy(A['actors'][ultra['actor_reference']])
        jb = copy.deepcopy(A['bipeds'][ultra['unit_reference']]); jb['change_colors_list'] = []
        bipeds[H2JACKAL] = jb
        def h2j(src, rank, body, shield, wref, **kw):
            """a Halo 2 Jackal variant copied from CE variant src, with this rank, vitality and gun (kw: more keys)"""
            v = copy.deepcopy(src)
            v['unit_reference'] = H2JACKAL; v['actor_reference'] = H2JACKAL
            v['unit'] = dict(v['unit'], maximum_body_vitality=float(body), maximum_shield_vitality=float(shield))
            v['ranged_combat']['reference'] = wref
            v['change_colors'] = None; v['change_colors_list'] = []
            v['_rank'] = rank; v['_late'] = True
            v.update(kw)
            return v
        variants[H2JACKAL + '\\jackal ultra plasma rifle'] = h2j(ultra, 'ultra', 100, 350, CE_PR)
        variants[H2JACKAL + '\\jackal zealot spiker'] = h2j(ultra, 'zealot', 120, 450, SPIKER)
        sn = h2j(A['variants'][r'characters\jackal\jackal minor plasma pistol'], 'sniper', 60, 0, H2BEAM,
                 _ov=dict(stance='rifle', shield=0, flags=['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades']))
        sn['ranged_combat'].update(combat_range_lower_bound=8.0, combat_range_upper_bound=28.0, maximum_firing_range=48.0)
        sn['items']['grenades_lower_bound'] = 0; sn['items']['grenades_upper_bound'] = 0
        variants[H2JACKAL + '\\jackal sniper beam rifle'] = sn
        # Marksmen (Halo 3's carbine Jackals): the Sniper's build with the plasma carbine or the pulse carbine, a
        # little closer in; no shield, rifle stance
        for wref, key in ((CARBINE, 'plasma carbine'), (PULSE, 'pulse carbine')):
            mk = h2j(A['variants'][r'characters\jackal\jackal minor plasma pistol'], 'marksman', 70, 0, wref,
                     _ov=dict(stance='rifle', shield=0, flags=['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades']))
            mk['ranged_combat'].update(combat_range_lower_bound=6.0, combat_range_upper_bound=22.0, maximum_firing_range=40.0)
            mk['items']['grenades_lower_bound'] = 0; mk['items']['grenades_upper_bound'] = 0
            variants[H2JACKAL + f'\\jackal marksman {key}'] = mk
        # helmets (IanLacksMods' Characters+: extract_h2_jackal.plus_meshes): only helmeted Jackals carry the long guns,
        # so the Sniper and the Marksmen wear Halo 3's sniper helmet with its glowing lenses; and a Major of its own in
        # Halo CE's helmet (the CE Major's health and shield, its pink shield; the plasma rifle, the one one-handed gun
        # the model carries). The bare-headed Ultra and Zealot keep the quills. (The helmeted copies of the Sniper and
        # Marksmen released briefly as 30498-30500 are gone; ednum_pins.json keeps those numbers retired.)
        if json.load(open(H2J_JSON)).get('helmet_cells'):
            for key in ('sniper beam rifle', 'marksman plasma carbine', 'marksman pulse carbine'):
                variants[H2JACKAL + f'\\jackal {key}']['_helmet'] = 'sniper'
            mj = h2j(A['variants'][r'characters\jackal\jackal major needler'], 'major', 75, 250, CE_PR, _helmet='ce')
            variants[H2JACKAL + '\\jackal major helmet plasma rifle'] = mj
        # the Needle Javelin as a loadout (needle_rifle_ce.py's model in its overlay slot, model 6), in the rifle stance
        # its long guns use, as the main pack's Elites and Jackals have it (build_pack.add_needle_rifle)
        bp.add_needle_rifle(variants, {'H2Jackal': 'rifle'}, char_of_unit={H2JACKAL: 'H2Jackal'})
    # The Ultra Zealot (Shigure's Zealot Elite, extract_ultra_zealot.py): the gold Elite's sword build made tougher,
    # a diamond energy shield on its left arm; armour in a Field Marshal crimson-maroon with blue lights
    zs = A['variants'].get(r'characters\elite\elite commander\elite commander energy sword')
    if zs and os.path.exists(f'{bp.OUT}/models/EliteZealot/EliteZealot.json'):
        v = copy.deepcopy(zs)
        v['unit_reference'] = ULTRA_ZEALOT
        v['unit'] = dict(v['unit'], maximum_body_vitality=130.0, maximum_shield_vitality=400.0)
        v['change_colors_list'] = [dict(color_lower_bound=list(ZEALOT_RED), color_upper_bound=list(ZEALOT_RED))]
        v['_rank'] = 'field marshal'; v['_late'] = True
        variants[ULTRA_ZEALOT + '\\elite ultra zealot energy sword'] = v
        actors[v['actor_reference']] = A['actors'][v['actor_reference']]
        bipeds[ULTRA_ZEALOT] = copy.deepcopy(A['bipeds'][r'characters\elite\elite'])
    # the Flood Brute: Ruby's armored Flood human's Flood AI on the Brute's frame, per rank (FLOOD_BRUTE_RANKS)
    fb_ar, fb_un = variants.get(FLOOD_BRUTE_BASE + ' assault rifle'), variants.get(FLOOD_BRUTE_BASE + ' unarmed')
    if os.path.exists(FLOOD_BRUTE_JSON) and fb_ar and fb_un:
        actors[FLOOD_BRUTE] = copy.deepcopy(actors[fb_ar['actor_reference']])
        fbb = copy.deepcopy(bipeds[fb_ar['unit_reference']])
        fbb.update(collision_height_standing=0.95, collision_radius=0.32); fbb['change_colors_list'] = []
        bipeds[FLOOD_BRUTE] = fbb
        for rank, rd in FLOOD_BRUTE_RANKS.items():
            for wref in rd['weapons'] + (None,):
                v = copy.deepcopy(fb_ar if wref else fb_un)
                v['unit_reference'] = FLOOD_BRUTE; v['actor_reference'] = FLOOD_BRUTE
                v['unit'] = dict(v['unit'], maximum_body_vitality=float(rd['body']), maximum_shield_vitality=0.0)
                v['ranged_combat']['reference'] = wref
                if wref == SPIKER:     # (its combat ranges: the Brute Major's Spiker's)
                    v['ranged_combat'].update({k: A['variants'][r'characters\elite\elite major\elite major plasma rifle']['ranged_combat'][k]
                                               for k in ('combat_range_lower_bound', 'combat_range_upper_bound', 'maximum_firing_range')})
                v['change_colors'] = None; v['change_colors_list'] = []
                v['_late'] = True; v['_brute_rank'] = rank
                variants[f'{FLOOD_BRUTE} {rank} {wref.split(chr(92))[-1] if wref else "unarmed"}'] = v
    return dict(variants=variants, actors=actors, bipeds=bipeds, collisions=colls,
                weapons={k: A['weapons'][k] for k in (CE_PR, CE_AR, CE_SG)})     # shotgun pellets per shot etc.

# the add-on's hand-written ZScript, pasted into the generated classes (configure: bp.BASE_CODE / TYPE_CODE /
# WEAPON_CODE); edit the files under templates/zscript/, not these names
DRONE_CODE = template('zscript/drone.zs')

ENGINEER_CODE = template('zscript/engineer.zs')


BRUTE_SCALE = 1.15     # Halo 2 Brutes are drawn at 115% (model, armour kit and helmet debris)
# The Flood Brute (extract_flood_brute.py: Halo 2's cut Brute combat form, from blackandfan's H2EK-Tags), with the Brutes
# it is made from: Flood AI (Ruby's Rebalance's armored Flood human's actor and combat data), the Brute's ranks and fur
# colours (extract_flood_brute.RANKS: what each rank wears), each rank with two guns and bare-handed. Infection forms
# raise a fallen Brute as the Flood Brute of its rank (flood_infection.zs)
FLOOD_BRUTE = r'characters\floodcombat_brute\floodcombat_brute'
FLOOD_BRUTE_JSON = f'{bp.OUT}/models/FloodBrute/FloodBrute.json'
FLOOD_BRUTE_BASE = r'characters\floodcombat_human\armored\floodcombat_human armored'    # + ' assault rifle' / ' unarmed'
FLOOD_BRUTE_RANKS = {'minor': dict(body=175, weapons=(CE_AR, CE_PR)), 'major': dict(body=200, weapons=(SPIKER, CE_SG)),
                     'captain': dict(body=250, weapons=(CE_PR, CE_SG)), 'honor guard': dict(body=250, weapons=(CE_AR, SPIKER))}
FLOOD_BRUTE_ORDER = [f'HCE_FloodcombatBrute{"".join(w.capitalize() for w in r.split())}{"".join(w.capitalize() for w in g.split(chr(92))[-1].split())}'
                     for r, rd in FLOOD_BRUTE_RANKS.items() for g in rd['weapons'] + ('unarmed',)] + ['HCE_RandomFloodBrute']

CARBINE_CODE = template('zscript/carbine.zs')

BEAM_CODE = template('zscript/beam.zs')

def voices():
    """Slug Man dialogue from Digsite's sound tags (Xbox ADPCM) -> ogg + SNDINFO events"""
    # Digsite sound tag name -> the HCE_Say events it serves (every permutation of the tag goes in each event's
    # $random); events with no tag borrow by build_voices.FALLBACK
    cat = {'sighted': ['Alert'], 'sighted_re': ['Alert'], 'taunting': ['Taunt'], 'pain': ['Pain', 'PainMed', 'PainHeavy'],
           'death_short': ['Death'], 'death_long': ['Death'], 'retreat': ['Flee', 'Panic'], 'communication': ['Regroup'],
           'evade': ['EnemyGrenade'], 'searching': ['Search'], 'idle_combat': ['Taunt']}
    out = f'{PACK}/sounds/hce_dig/slug'
    os.makedirs(out, exist_ok=True)
    import tempfile; tmp = tempfile.mkdtemp(); os.makedirs(tmp, exist_ok=True)
    events = {}
    for name, evs in cat.items():
        s = parse_sound(f'{T}digsite/sound/dialog/slug/{name}.sound')
        for p in s['pitch_ranges'][0]['perms']:
            a = decode(p, s['rate'], s['channels'])
            fn = f'{name}_{p["name"]}.ogg'
            wav = f'{tmp}/{fn[:-4]}.wav'
            to_wav(a, s['rate'], s['channels'], wav)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '3', f'{out}/{fn}'], check=True)
            for ev in evs: events.setdefault(ev, []).append(f'sounds/hce_dig/slug/{fn}')
    lines = ['// Slug Man dialogue (Digsite sound tags). HCE/<voice>/<event> as played by HCE_Say().']
    for ev in sorted(events):
        ids = []
        for i, pth in enumerate(events[ev]):
            sid = f'HCE/Slug/{ev}/{i}'; lines.append(f'{sid} "{pth}"'); ids.append(sid)
        lines.append(f'$random HCE/Slug/{ev} {{ {" ".join(ids)} }}')
    for ev, fb in bp_fallback().items():
        if ev not in events and fb in events: lines.append(f'$alias HCE/Slug/{ev} HCE/Slug/{fb}')
    return lines

def engineer_sounds():
    """Engineer dialogue + death burst from SPV3's b30 (16-bit PCM / Xbox ADPCM -> ogg)"""
    import extract_spv3
    got = extract_spv3.export_sounds('Engineer', f'{PACK}/sounds/hce_dig/engineer')
    ev = {'engineer_noncombat': ['Idle'], 'engineer_combat': ['Taunt', 'Regroup'], 'engineer_surprise': ['Alert', 'Panic', 'Flee'],
          'engineer_pain_minor': ['Pain'], 'engineer_pain_major': ['PainMed', 'PainHeavy', 'Death', 'DeathHard'],
          'engineer_explosion': ['Explode']}
    lines = ['', '// Engineer (SPV3 b30 sound tags)']
    for base, files in sorted(got.items()):
        ids = []
        for i, f in enumerate(files):
            sid = f'HCE/Engineer/{base.replace(" ", "_")}/{i}'; lines.append(f'{sid} "sounds/hce_dig/engineer/{f}"'); ids.append(sid)
        for e in ev.get(base.replace(' ', '_'), []):
            lines.append(f'$random HCE/Engineer/{e} {{ {" ".join(ids)} }}')
    return lines

def drone_sounds():
    """Halo 2 Drone dialogue (extract_h2_sounds / out/sounds/Drone: MCC sounds_en.dat Opus -> Ogg) -> HCE/Drone/<event>"""
    src = OUT + '/sounds/Drone'
    if not os.path.exists(f'{src}/index.json'): return []
    idx = json.load(open(f'{src}/index.json'))
    dst = f'{PACK}/sounds/hce_dig/drone'; os.makedirs(dst, exist_ok=True)
    ev = {'seefoe': ['Alert'], 'foundfoe': ['Alert'], 'hrdfoe': ['Alert'], 'srprs': ['Alert'],
          'tnt': ['Taunt'], 'thrtn': ['Taunt'], 'crs': ['Taunt'], 'chr': ['Taunt', 'Berserk'], 'strk': ['Taunt'],
          'glt': ['KillPlayer'], 'pain': ['Pain'], 'pain_shld': ['Pain'], 'pain_mdm': ['PainMed'], 'pain_mjr': ['PainHeavy'],
          'pain_fall': ['PainHeavy'], 'dth': ['Death'], 'dth_slw': ['Death'], 'dth_fall': ['Death', 'DeathHard'],
          'dth_mjr': ['DeathHard'], 'flee': ['Flee'], 'panic': ['Panic'], 'cower': ['Panic'], 'whn': ['Panic'],
          'pstcmbt': ['Regroup'], 'warn': ['EnemyGrenade'], 'fall': ['Panic'],
          # effects (sounds_neutral.dat)
          'flying': ['Fly'], 'long_move': ['Whoosh'], 'bugger_stick': ['Stick'], 'bugger_melees': ['Claw'],
          'bugger_bodyfalls_havok': ['BodyFall'], 'bugger_bodyfalls_non_havok': ['BodyFall']}
    lines = ['', '// Drone (Halo 2 MCC: dialogue from sounds_en.dat, effects from sounds_neutral.dat)']
    per_ev = {}
    for base, files in sorted(idx.items()):
        ids = []
        for i, f in enumerate(files):
            shutil.copy(f'{src}/{f}', f'{dst}/{f}')
            sid = f'HCE/Drone/{base}/{i}'; lines.append(f'{sid} "sounds/hce_dig/drone/{f}"'); ids.append(sid)
        for e in ev.get(base, []): per_ev.setdefault(e, []).extend(ids)
    for e, ids in sorted(per_ev.items()):
        lines.append(f'$random HCE/Drone/{e} {{ {" ".join(ids)} }}')
    return lines

# Drone ranks past the Minor: their loadouts (Halo 2's Drones fly with plasma pistols and needlers; the officers
# bring plasma rifles)
DRONE_RANKS = {'major': (r'weapons\plasma pistol\plasma pistol', r'weapons\needler\needler'),
               'ultra': (r'weapons\needler\needler', CE_PR),
               'captain': (r'weapons\plasma pistol\plasma pistol', CE_PR),
               'captain_major': (r'weapons\needler\needler', CE_PR)}
DRONE_SHELL = (1.00, 0.62, 0.22)       # the Captains' shield flare: the amber of the Drones' eyes


def drone_ranks():
    """the extracted Drone's 'ranks' table (rank -> colour/mask info) from Drone.json, {} when it hasn't been built"""
    j = f'{bp.OUT}/models/Drone/Drone.json'
    return (json.load(open(j)).get('ranks') or {}) if os.path.exists(j) else {}


def drone_skin(cls, v, si, mat, meta, skin_dir):
    """a ranked Drone's skin: the plain bake with its exoskeleton plates (the rank tags' change-colour map) in the
    rank's colour, shaded by the skin under them"""
    rank = v.get('_rank'); rd = drone_ranks().get(rank)
    matn = mat[:-4] if mat.endswith('.png') else mat
    mp = f'{bp.OUT}/models/Drone/Drone_rank_mask.png'
    if not rd or rank == 'minor' or matn not in ('Drone_0', 'Drone_1', 'Drone_2') or not os.path.exists(mp): return None
    fn = f'drone_{rank}_{matn.lower()}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    os.makedirs(skin_dir, exist_ok=True)
    bp.bake_skin('Drone', matn, None, dst)
    im = Image.open(dst).convert('RGB')
    d = np.asarray(im).astype(np.float64) / 255.0
    m = np.asarray(Image.open(mp).convert('L').resize(im.size)).astype(np.float64)[..., None] / 255.0
    lum = d.mean(2, keepdims=True)
    ref = lum[m[..., 0] > 0.5].mean() if (m > 0.5).any() else 0.5
    tint = lum / max(ref, 1e-3) * 0.75 * np.array(rd['colour'])
    Image.fromarray((np.clip(d * (1 - m) + tint * m, 0, 1) * 255).astype(np.uint8)).save(dst)
    return fn


# The Brutes' coloured armour (the Honor Guard's red-and-blue plate, the Halo 3-style kit's blue, red, gold and teal)
# shines like the Elites' armour: the same cube-map reflection (texmath.bake_reflection), the Elite cube of the paint's
# colour (blue, red / magenta, gold) on its painted parts. BRUTE_SHINE: the body's armour textures; the kit's are
# matched by KIT_SHINE_TEX. k: the reflection's strength (the Elites' armour: 1.0)
BRUTE_SHINE = ('brute_honor_armor',)
KIT_SHINE_TEX = 'armorwork'
BRUTE_SHINE_K = 0.4


def armour_shine(rgb, n, k=BRUTE_SHINE_K):
    """rgb (H, W, 3) 0..1 and its model-space normals -> the Elites' armour reflection baked onto its painted parts:
    each paint colour reflects its own Elite cube map (blue 0, red 1, gold 2); grey metal, leather, fur and the green
    lights stay as they are"""
    import colorsys
    from texmath import bake_reflection
    hsv = np.asarray(Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).convert('HSV')).astype(np.float32) / 255.0
    h, sat, val = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
    paint = np.clip((sat - 0.22) / 0.3, 0, 0.8) * np.clip((val - 0.12) / 0.25, 0, 1)
    paint *= 1 - ((h > 80) & (h < 170) & (val > 0.55)).astype(np.float32)        # the inset lights' greens
    hues = {0: (h > 170) & (h < 290), 1: (h >= 290) | (h < 22), 2: (h >= 22) & (h <= 80)}
    out = rgb.copy()
    for cube, m in hues.items():
        spec = paint * m.astype(np.float32)
        if spec.max() < 0.05: continue
        faces = bp.cube_faces('elite', cube)
        if faces is None: continue
        baked = bake_reflection(rgb, n, spec, faces, k)
        out = out * (1 - spec[..., None]) + baked * spec[..., None]
    return out


def brute_skin(cls, v, si, mat, meta, skin_dir):
    """per-rank Brute skins: hide the armour pieces a rank doesn't wear, bake the variant's fur change colours"""
    names = meta.get('mesh_names')
    if not names or 'Brute' not in mat and not mat.startswith('Brute_'): return None
    region, perm, shader = names[si].split('.')
    rank = BRUTE_RANKS[v['_brute_rank']]
    os.makedirs(skin_dir, exist_ok=True)
    if (region, perm) not in rank['wear']:
        hid = f'{skin_dir}/hce_hidden.png'
        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        return 'hce_hidden.png'
    var = v['_brute_variant']
    # the Stalker's skins are its own copies: the camo shader goes on its textures, never on the Majors' it shares
    fn = f'brute_{"stalker_" if v["_brute_rank"] == "stalker" else ""}{var}_{shader}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    src = f'{OUT}/models/Brute/Brute_{shader}.png'
    im = Image.open(src); has_a = im.mode == 'RGBA'
    a = np.asarray(im.convert('RGBA')).astype(np.float64) / 255.0
    mp = f'{OUT}/models/Brute/Brute_{shader}_mask.png'
    cols = meta['change_colors'].get(var) or meta['change_colors']['minor_bth']
    if os.path.exists(mp):
        mk = np.asarray(Image.open(mp).convert('RGB').resize(im.size)).astype(np.float64) / 255.0
        rgb = a[..., :3]
        for ch, col in ((0, cols[0]), (1, cols[1])):           # red = primary (fur/skin), green = secondary (hair)
            if col is None: continue
            m_ = mk[..., ch:ch + 1] if shader in ('brute_hair', 'tartarus_mohawk') else mk[..., :1] if ch == 0 else None
            if m_ is None: continue
            rgb = rgb * (1 - m_) + rgb * np.array(col) * 1.5 * m_
        a[..., :3] = rgb
    if shader in BRUTE_SHINE:                                       # the coloured armour shines like the Elites'
        a[..., :3] = armour_shine(a[..., :3], bp.normal_map('Brute', f'Brute_{shader}', im.size).copy())
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), 'RGBA')
    (out if has_a else out.convert('RGB')).save(dst)
    return fn

def flood_brute_skin(cls, v, si, mat, meta, skin_dir):
    """SKIN_HOOK for the Flood Brute: the pieces its rank doesn't wear (meta 'wear', extract_flood_brute.RANKS) hidden;
    the fur and hair in the rank's own tint (the extractor's per-rank bakes); the rest as extracted (None)"""
    names = meta.get('mesh_names')
    if not names or si >= len(names) or names[si].startswith('weapon_'): return None
    region, perm = names[si].split('.')[:2]
    rank = v['_brute_rank']
    os.makedirs(skin_dir, exist_ok=True)
    if region != 'body' and [region, perm] not in meta['wear'][rank]:
        hid = f'{skin_dir}/hce_hidden.png'
        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        return 'hce_hidden.png'
    fn = mat.replace('_minor.png', f'_{rank.replace(" ", "_")}.png')
    if fn == mat: return None
    if not os.path.exists(f'{skin_dir}/{fn}'): shutil.copy(f'{bp.OUT}/models/FloodBrute/{fn}', f'{skin_dir}/{fn}')
    return fn


H2J_BRIGHT = []          # helmet skins with lit parts (the sniper helmet's lenses): (skin file, its brightmap)


def h2jackal_helmet(kind, meta, skin_dir):
    """the helmet surface's atlas (extract_h2_jackal.plus_meshes) with only one cell left opaque: 'hair' (the quills,
    bare-headed ranks), 'ce' (Halo CE's helmet) or 'sniper' (Halo 3's, its lenses lit by the atlas's brightmap)"""
    fn = f'h2jackal_helmet_{kind}.png'; dst = f'{skin_dir}/{fn}'
    if not os.path.exists(dst):
        im = Image.open(f'{bp.OUT}/models/H2Jackal/H2Jackal_helmet_atlas.png').convert('RGBA')
        a = np.asarray(im).copy(); h, w = a.shape[0] // 2, a.shape[1] // 2
        cx, cy = meta['helmet_cells'][kind]
        keep = np.zeros(a.shape[:2], bool); keep[cy * h:(cy + 1) * h, cx * w:(cx + 1) * w] = True
        a[~keep, 3] = 0
        Image.fromarray(a).save(dst)
    if kind == 'sniper':
        bm = f'{skin_dir}/h2jackal_helmet_sniper_bm.png'
        shutil.copy(f'{bp.OUT}/models/H2Jackal/H2Jackal_helmet_atlas_bm.png', bm)
        if (dst, bm) not in H2J_BRIGHT: H2J_BRIGHT.append((dst, bm))
    return fn


def h2jackal_skin(cls, v, si, mat, meta, skin_dir):
    """Halo 2 Jackal skins: armour change colours per rank; the Sniper carries no shield (its surfaces hidden); the
    helmet surface shows the class's helmet (v['_helmet']: 'ce', 'sniper') or, bare-headed, the quills"""
    names = meta.get('mesh_names')
    if not names or not mat.startswith('H2Jackal_'): return None
    nm = names[si]
    os.makedirs(skin_dir, exist_ok=True)
    rank = v.get('_rank')
    if nm == 'helmet.jackal_helmet' and meta.get('helmet_cells'):
        return h2jackal_helmet(v.get('_helmet') or 'hair', meta, skin_dir)
    if nm.startswith('shield.') and rank in H2J_NO_SHIELD:
        hid = f'{skin_dir}/hce_hidden.png'
        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        return 'hce_hidden.png'
    shader = nm.split('.', 1)[1]
    src = f'{bp.OUT}/models/H2Jackal/H2Jackal_{shader}.png'
    mp = f'{bp.OUT}/models/H2Jackal/H2Jackal_{shader}_mask.png'
    if not os.path.exists(mp):
        fn = f'h2jackal_{shader}.png'
        if not os.path.exists(f'{skin_dir}/{fn}'): shutil.copy(src, f'{skin_dir}/{fn}')
        return fn
    fn = f'h2jackal_{rank}_{shader}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    cols = H2J_COLOURS.get(rank, 'minor')
    if isinstance(cols, str): cols = meta['change_colors'][cols]
    tint = np.array(cols[2] if len(cols) > 2 and cols[2] is not None else cols[0], np.float64)   # the vivid tertiary
    im = Image.open(src).convert('RGB')
    rgb = np.asarray(im).astype(np.float64) / 255.0
    mk = np.asarray(Image.open(mp).convert('RGB').resize(im.size)).astype(np.float64) / 255.0
    m = np.clip(mk.max(2), 0, 1)[..., None]               # the change-colour areas: the suit; the rest: the plates
    L = rgb.mean(2, keepdims=True)
    def detail(sel):                                      # the texture's shading, about 1 over the region
        """the bake's luminance L divided by its mean where the mask sel is on: shading normalised to ~1 there"""
        w = sel[..., 0]
        return L / max(float((L[..., 0] * w).sum() / max(w.sum(), 1)), 1e-3)
    # the suit as Halo CE's Jackal wears it: dark navy leather, its folds kept; the rank colour tints it
    k, bright = H2J_SUIT_TINT.get(rank, H2J_SUIT_TINT['default'])
    tone = np.array(H2J_SUIT) * (1 - k) + tint * bright * k
    suit = tone * detail(m) ** 1.6
    # the plates: CE's beige steel, keeping some of their own colour
    pm = (1 - m)[..., 0] > 0.5
    pmean = rgb[pm].mean(0) if pm.any() else rgb.reshape(-1, 3).mean(0)
    plate = rgb * (np.array(H2J_PLATE) / np.maximum(pmean, 1e-3)) * 0.6 + rgb * 0.4
    out = suit * m + plate * (1 - m)
    # Halo's reflection on them (build_pack.add_shine): the silver Elite cube, full on the plates, a dull sheen on the suit
    multi = f'{bp.OUT}/models/H2Jackal/H2Jackal_{shader}_multi.png'
    spec = (1 - m[..., 0]) * 0.6 + m[..., 0] * 0.12
    Image.fromarray((np.dstack([spec, np.zeros_like(spec), m[..., 0], np.ones_like(spec)]) * 255).astype(np.uint8), 'RGBA').save(multi)
    out = bp.add_shine('H2Jackal', f'H2Jackal_{shader}', out.astype(np.float32), (0.5, 0.5, 0.5), 1.0)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(dst)
    return fn

def h2jackal_code():
    """ZScript for the Halo 2 Jackal class: the shield bone, gun-hand bone and shield surface from H2Jackal.json"""
    meta = json.load(open(H2J_JSON))
    return f'''
	// ---- Halo 2 Jackal: its arm shield rides the 'shield' node of the right forearm, the gun is in the left hand
	override Name HCE_ShieldBone() {{ return '{meta['shield_bone']}'; }}
	override Name HCE_GunHandBone() {{ return '{meta['hand_bone']}'; }}
	override int HCE_ShieldSurface() {{ return {meta['shield_surface']}; }}
'''

def h2jackal_sounds():
    """Halo 2's Jackal shield popping (jackal_shield_death) -> HCE/Jackal/ShieldPop (played for every Jackal's shield)"""
    if not os.path.exists(H2J_JSON): return []
    meta = json.load(open(H2J_JSON))
    dst = f'{PACK}/sounds/hce_dig/jackal'; os.makedirs(dst, exist_ok=True)
    lines = ['', "// Jackal shield pop (Halo 2's jackal_shield_death)"]; ids = []
    for i, f in enumerate(meta.get('sounds', [])):
        shutil.copy(f'{bp.OUT}/models/H2Jackal/{f}', f'{dst}/{os.path.basename(f)}')
        sid = f'HCE/Jackal/ShieldPop/{i}'; lines.append(f'{sid} "sounds/hce_dig/jackal/{os.path.basename(f)}"'); ids.append(sid)
    if ids: lines.append(f'$random HCE/Jackal/ShieldPop {{ {" ".join(ids)} }}')
    return lines

# The kit's grey helmets and shoulders (King Hit's and Halo 2's: KIT_GREY) come in each rank's colour too: per rank a
# copy of the piece (and of its knocked-off debris) on a copy of its texture, the grey metal tinted the rank's colour
# (the median colour of the rank's own Halo 3 armour texture, KIT_TINT_FROM, so the pieces match it) and given the
# Elites' shine (armour_shine). kit_rank_file names the copy, kit_tint_pieces makes them.
KIT_GREY_SLOTS = ('helmet', 'shoulders')
KIT_GREY_PREFIX = ('kh_', 'h2_')
KIT_TINT_FROM = {'minor': 'kit_minor_major_armorwork_minor.jpg', 'major': 'kit_minor_major_armorwork_major.jpg',
                 'captain': 'kit_minor_major_armorwork_captain.jpg'}


def kit_grey(kit):
    """the grey helmet and shoulder piece files that get rank-coloured copies"""
    return {f for p in kit['pieces'].values() if p['slot'] in KIT_GREY_SLOTS for f in p['files'].values()
            if f.startswith(KIT_GREY_PREFIX)}


def kit_rank_file(rank, f, grey):
    """the file a rank wears for kit piece f: its rank-coloured copy for a grey helmet or shoulder piece"""
    return f'{f[:-4]}_{rank}.iqm' if f in grey and rank in KIT_TINT_FROM else f


def kit_tint_pieces(kd):
    """the rank-coloured copies of the grey pieces, their debris and their textures, into the pack's kit folder kd"""
    from iqm import read_iqm, write_iqm
    from texmath import raster_normals
    kit = json.load(open(KIT_JSON))
    grey = kit_grey(kit)
    texs = set()
    for rank in KIT_TINT_FROM:
        for f in sorted(grey):
            for src in (f, 'debris_' + f):
                if not os.path.exists(f'{KIT_DIR}/{src}'): continue
                joints, meshes, anims = read_iqm(f'{KIT_DIR}/{src}')
                for m in meshes:
                    if 'chain' in m['material']: continue          # chain mail stays bare metal
                    texs.add(m['material'])
                    stem, ext = os.path.splitext(m['material']); m['material'] = f'{stem}_{rank}{ext}'
                alist = [dict(name=k, fps=30.0, loop=True, frames=v) for k, v in anims.items()]
                dst = ('debris_' if src != f else '') + kit_rank_file(rank, f, grey)
                write_iqm(f'{kd}/{dst}', [(n, p, tuple(t), tuple(q), tuple(sc)) for n, p, t, q, sc in joints], meshes, alist)
    meshes_of = {}
    for f in sorted(grey):
        for m in read_iqm(f'{KIT_DIR}/{f}')[1]: meshes_of.setdefault(m['material'], []).append(m)
    for rank, ref in KIT_TINT_FROM.items():
        rim = np.asarray(Image.open(f'{KIT_DIR}/{ref}').convert('RGB')).astype(np.float32) / 255.0
        hsv = np.asarray(Image.open(f'{KIT_DIR}/{ref}').convert('HSV')).astype(np.float32) / 255.0
        col = np.median(rim[hsv[..., 1] > 0.3], axis=0)                     # the rank's paint colour
        for tex in sorted(texs):
            im = Image.open(f'{KIT_DIR}/{tex}').convert('RGB')
            rgb = np.asarray(im).astype(np.float32) / 255.0
            th = np.asarray(im.convert('HSV')).astype(np.float32) / 255.0
            lum = rgb.mean(2)
            m = np.clip((lum - 0.08) / 0.15, 0, 1) * np.clip(1 - (th[..., 1] - 0.15) / 0.2, 0, 1)    # the grey metal
            ref_l = np.median(lum[m > 0.5]) if (m > 0.5).any() else 0.5
            tint = np.clip((lum / max(ref_l, 1e-3))[..., None] * col[None, None] * 0.9, 0, 1)
            n, cov = raster_normals(meshes_of.get(tex, []), tex, im.size, coverage=True) if meshes_of.get(tex) else (None, None)
            if n is not None and cov.any():                                   # only where the grey pieces map onto it
                cov = cov.astype(np.float32)
                m = m * np.asarray(Image.fromarray((cov * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))).astype(np.float32) / 255.0
            out = rgb * (1 - m[..., None]) + tint * m[..., None]
            if n is not None and np.abs(n).sum(): out = armour_shine(out, n.copy())
            stem, ext = os.path.splitext(tex)
            Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(f'{kd}/{stem}_{rank}{ext}', quality=95)
    print('kit: rank-coloured grey pieces', len(grey), 'x', len(KIT_TINT_FROM), 'textures', len(texs))


def kit_code():
    """armour kit dressing: per rank, a weighted pick per slot (model attachments 1-6) or a whole outfit"""
    if not os.path.exists(KIT_JSON): return '\tvoid HCE_DressArmour() {}\n'
    kit = json.load(open(KIT_JSON))
    meta = json.load(open(OUT + '/models/Brute/Brute.json'))
    armour = [i for i, n in enumerate(meta['mesh_names']) if not n.startswith('weapon_') and n.split('.')[0] not in ('body', 'head', 'hair', 'sensors')]
    pools, outfits, keep = [], [], []
    grey = kit_grey(kit)
    for r in KIT_RANKS:
        rd = kit['ranks'][r]
        for slot in kit['slots']: pools.append('|'.join(f'{kit_rank_file(r, f, grey) if f else f}:{w}' for f, w in rd['slots'][slot]))
        outfits.append('|'.join(f'{c};' + ','.join(o[slot] for slot in kit['slots']) for c, o in rd['outfits']))
        keep.append(rd['keep_base'])
    pool_cases = ''.join(f'\t\t\tcase {i}: return "{p}";\n' for i, p in enumerate(pools))
    out_cases = ''.join(f'\t\t\tcase {i}: return "{o}";\n' for i, o in enumerate(outfits) if o)
    keep_cases = ''.join(f'\t\t\tcase {i}: return {k};\n' for i, k in enumerate(keep) if k)
    hide = ''.join(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {i}, "models/hce_dig/Brute/skins", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n' for i in armour)
    shell_hide = ''.join(f'\t\t\tsh.A_ChangeModel(\'None\', 0, "", \'None\', {i}, "models/hce_dig/Brute/skins", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n' for i in armour)
    n = len(kit['slots'])
    return f'''
	// ---- armour kit (extract_brute_kit.py): each Minor / Major / Captain rolls its own helmet, chest, shoulder,
	// arm, leg and waist pieces when it spawns (some ranks may also roll a whole outfit); the Chieftain keeps
	// Tartarus's look or wears one of the kit's chieftain sets. Pieces are model attachments {{1-{n}}} riding the
	// Brute's own bones; their textures are named in the piece models.
	String hce_kitHelmet;
	Array<String> hce_kitPick;                // the pieces worn, slot by slot (the shield flare wears them too)
	bool hce_kitChief;
	override void HCE_DressShell(Actor sh)
	{{
		super.HCE_DressShell(sh);
		if(hce_kitChief)
		{{
{shell_hide}		}}
		for(int s = 0; s < hce_kitPick.Size(); s++)
		{{
			if(hce_kitPick[s].Length() == 0) continue;
			sh.A_ChangeModel('None', s + 1, "models/hce_dig/BruteKit", hce_kitPick[s], s + 1, "", 'None');
			for(int k = 0; k < 8; k++) sh.A_ChangeModel('None', s + 1, "", 'None', k, "models/hce_dig/Brute/skins", 'shieldshell.png', CMDL_USESURFACESKIN);
		}}
	}}
	static String HCE_KitPool(int i)
	{{
		switch(i)
		{{
{pool_cases}		}}
		return "";
	}}
	static String HCE_KitOutfits(int r)
	{{
		switch(r)
		{{
{out_cases}		}}
		return "";
	}}
	static double HCE_KitKeepBase(int r)
	{{
		switch(r)
		{{
{keep_cases}		}}
		return 0;
	}}
	static String HCE_KitRoll(String pool)
	{{
		Array<String> opts; pool.Split(opts, "|");
		double tot = 0;
		for(int i = 0; i < opts.Size(); i++) {{ Array<String> p; opts[i].Split(p, ":"); if(p.Size() > 1) tot += p[1].ToDouble(); }}
		double x = frandom[HCEKit](0, tot);
		for(int i = 0; i < opts.Size(); i++)
		{{
			Array<String> p; opts[i].Split(p, ":");
			if(p.Size() < 2) continue;
			x -= p[1].ToDouble();
			if(x <= 0) return p[0];
		}}
		return "";
	}}
	override int HCE_LineupLooks()
	{{
		String cn = GetClassName();
		if(cn.IndexOf("Chieftain") < 0) return 1;
		Array<String> ol; HCE_KitOutfits(3).Split(ol, "|", TOK_SKIPEMPTY);
		return 1 + ol.Size();
	}}
	void HCE_DressArmour()
	{{
		String cn = GetClassName();
		bool jumper = cn.IndexOf("JumpPack") >= 0;      // the jump-pack Brutes: always the Majors' first outfit, the jump-pack suit
		int r = jumper || cn.IndexOf("Major") >= 0 ? 1 : cn.IndexOf("Minor") >= 0 ? 0 : cn.IndexOf("Captain") >= 0 ? 2 : cn.IndexOf("Chieftain") >= 0 ? 3 : -1;
		if(r < 0) return;
		double keep = HCE_KitKeepBase(r);
		int look = (r == 3) ? hce_lineupLook - 1 : jumper ? 1 : -1;   // punkassbitches: 0 his own look, 1.. the outfits in turn
		if(look == 0 || (look < 0 && keep > 0 && frandom[HCEKit](0, 1) < keep)) return;
		Array<String> pick;
		for(int s = 0; s < {n}; s++) pick.Push("");
		bool outfit = false;
		String outs = HCE_KitOutfits(r);
		if(outs.Length() > 0)
		{{
			Array<String> ol; outs.Split(ol, "|");
			double x = frandom[HCEKit](0, 1);
			for(int i = 0; i < ol.Size() && !outfit; i++)
			{{
				Array<String> p; ol[i].Split(p, ";");
				if(p.Size() < 2) continue;
				double c = p[0].ToDouble();
				if(look > 0 ? i == look - 1 : x < c)
				{{
					Array<String> f; p[1].Split(f, ",");
					for(int s = 0; s < {n} && s < f.Size(); s++) pick[s] = f[s];
					outfit = true;
				}}
				else x -= c;
			}}
		}}
		if(!outfit) for(int s = 0; s < {n}; s++) pick[s] = HCE_KitRoll(HCE_KitPool(r * {n} + s));
		if(r == 3)
		{{
{hide}		}}
		for(int s = 0; s < {n}; s++)
			if(pick[s].Length() > 0) A_ChangeModel('None', s + 1, "models/hce_dig/BruteKit", pick[s], s + 1, "", 'None');
		hce_kitPick.Copy(pick); hce_kitChief = r == 3;
		hce_kitHelmet = pick[0];
		if(hce_kitHelmet.Length() == 0 && r < 3) hce_helmetOff = true;     // bare-headed: nothing to knock off
	}}
'''

# Halo 2's plasma_mask_offset look for the Captain's flag: the pennant drifts through its own offset (the cloth's
# ripple), a band of noise crawls across it, scan lines roll down it and it pulses; drawn additively, so it is light
HOLOFLAG_SHADER = template('shaders/holoflag.fp')

def brute_code():
    """ZScript for the Brute class (bp.TYPE_CODE['Brute']): the armour kit code plus the Halo 2 Brute behaviour
    (berserk charge, weapon toss, helmet pop, Chieftain hammer shockwaves, pack morale on death).
    To change how Brutes fight, edit the ZScript string here"""
    return kit_code() + '''
	// ---- Halo 2 Brute behaviour ----------------------------------------------------------------------
	// berserk (badly hurt, or the pack is gone): roar, throw the gun away, charge on all fours with the
	// berserk swings and tackles. Headshots knock a Minor/Major/Captain's helmet off. Losing pack mates
	// can send the survivors berserk; the last Brute standing always goes.
	// The Chieftain (Tartarus's look and hammer) keeps his gravity hammer when berserk: every swing and every
	// landed leap ends in a gravity shockwave that hurts and throws back everything around the impact.
	bool hce_weaponTossed, hce_helmetOff, hce_chief;
	int hce_stepTics, hce_fallTics, hce_smashTics, hce_prevLeap;
	Name hce_lastSwing;
	override void PostBeginPlay()
	{
		HCE_DressArmour();                     // before any animation starts (A_ChangeModel resets the current one)
		String gn = GetClassName();
		if(gn.IndexOf("Captain") >= 0)         // Halo 2's Captains fly the hologram flag (dig_brute.zsc)
		{
			hce_holoActor = Spawn("HCE_BruteCaptainFlag", pos, NO_REPLACE);
			if(hce_holoActor) hce_holoActor.master = self;
		}
		super.PostBeginPlay();
		String cn = GetClassName();
		hce_chief = cn.IndexOf("Chieftain") >= 0;
	}
	override bool HCE_TryMelee()
	{
		if(!super.HCE_TryMelee()) return false;
		if(hce_chief) hce_smashTics = max(4, int(hce_animLock * 0.45));
		return true;
	}
	void HCE_HammerSmash(double reach)
	{
		vector3 at = Vec3Angle(radius + reach, angle, 0);
		A_StartSound("Halo/Weapons/GravityHammer/Fire", CHAN_WEAPON, CHANF_OVERLAP, 1.0);
		A_StartSound("Halo/Weapons/GravityHammer/Fire/Bass", CHAN_7, CHANF_OVERLAP, 1.0);
		Spawn("GravityHammerExplosion", at, ALLOW_REPLACE);
		let it = BlockThingsIterator.CreateFromPos(at.x, at.y, at.z, 64, 150, false);
		while(it.Next())
		{
			Actor mo = it.thing;
			if(!mo || mo == self || !mo.bSHOOTABLE || mo.health <= 0) continue;
			if(mo is "HaloDoom_EnemyBase" && !HCE_IsEnemy(mo)) continue;      // spare the pack
			double d = (mo.pos.xy - at.xy).Length();
			if(d > 150 || abs(mo.pos.z - at.z) > 96) continue;
			double f = 1.0 - d / 150.0;
			mo.DamageMobj(self, self, int(10 + 25 * f), 'Crush', DMG_THRUSTLESS);
			double a = atan2(mo.pos.y - at.y, mo.pos.x - at.x);
			if(mo.bSOLID && mo.mass < 2000) mo.vel += (AngleToVector(a, 6 + 10 * f), 4 + 5 * f);
		}
	}
	override void Tick()
	{
		super.Tick();
		if(hce_chief && health > 0 && !isFrozen())
		{
			if(hce_smashTics > 0 && --hce_smashTics == 0) HCE_HammerSmash(36);
			if(hce_prevLeap == 2 && hce_leapState == 0) HCE_HammerSmash(12);     // leap ends: ground pound
			hce_prevLeap = hce_leapState;
		}
		if(hce_fallTics > 0 && --hce_fallTics == 0) A_StartSound("HCE/Brute/BodyFall", CHAN_BODY, CHANF_OVERLAP, 0.9);
		// the Stalker's eye: a red glint on its head that its camo doesn't hide, flaring now and then
		if(bHCE_ActiveCamo && health > 0 && !(hce_severed & 1) && !isFrozen())
		{
			vector3 h = HCE_LimbOffset(HCE_LIMB_HEAD);
			vector2 fw = AngleToVector(angle), lf = AngleToVector(angle + 90);
			vector3 at = (fw * (h.x + radius * 0.35) + lf * h.y, h.z * 0.98);
			double fl = (level.maptime % 70 < 6) ? 2.0 : 1.0 + 0.2 * sin(level.maptime * 24.0);
			A_SpawnParticle("FF2010", SPF_FULLBRIGHT, 2, 5.0 * fl, 0, at.x, at.y, at.z, 0, 0, 0, 0, 0, 0, 0.95);
			A_SpawnParticle("FF9080", SPF_FULLBRIGHT, 2, 2.0 * fl, 0, at.x, at.y, at.z, 0, 0, 0, 0, 0, 0, 1.0);
		}
		if(health > 0 && !isFrozen())
		{
			// footfalls: the API's HCE_StepTick (Halo 2's Brute footsteps by surface, extract_footsteps.py)
			// swing whoosh on each melee / tackle, chest thump on the berserk roar
			if(hce_curAnim != hce_lastSwing)
			{
				String an = hce_curAnim;
				if(an.IndexOf("melee") >= 0 || an.IndexOf("tackle") >= 0) A_StartSound("HCE/Brute/MeleeMove", CHAN_6, CHANF_OVERLAP, 0.9);
				else if(an.IndexOf("berserk") >= 0 && an.IndexOf("stand") == 0) A_StartSound("HCE/Brute/Thump", CHAN_6, CHANF_OVERLAP, 1.0);
				hce_lastSwing = hce_curAnim;
			}
		}
		if(health > 0 && hce_berserk && !hce_weaponTossed && !hce_chief && hce_animLock <= 0) HCE_TossWeapon();
		// a Brute without its gun only charges
		if(hce_weaponTossed && health > 0 && target && hce_action != HCE_ACT_CHARGE) { hce_berserk = true; hce_action = HCE_ACT_CHARGE; }
	}
	void HCE_TossWeapon()
	{
		hce_weaponTossed = true;
		CVar cv = CVar.FindCVar("hce_dropweapons");
		class<Actor> wc = (class<Actor>)(hce_dropWeapon);
		if(wc && (!cv || cv.GetBool())) HCE_Toss(wc);
		hce_dropWeapon = 'None';
		HCE_HideWeaponSurfaces();
		HCE_StopFireLoop();
		hce_projectile = 'None';
		hce_runSpeed *= 1.35; hce_walkSpeed *= 1.35;
		hce_curAnimKind = -1;
	}
	override void HCE_OnDamaged(Actor inflictor, Actor source, int dealt, Name mod)
	{
		super.HCE_OnDamaged(inflictor, source, dealt, mod);
		if(health <= 0 || hce_helmetOff || dealt <= 0 || HCE_HelmetFixed()) return;
		bool head = mod == 'Headshot' || (inflictor && inflictor != source && inflictor.pos.z > pos.z + height * 0.8);
		if(!head) return;
		HCE_KnockHelmet(inflictor ? inflictor : source);
		HCE_Say('PainHeavy', 1.0, 0, true);
	}
	void HCE_KnockHelmet(Actor from)
	{
		hce_helmetOff = true;
		A_ChangeModel('None', 1, "", 'None', 1, "", 'None', CMDL_HIDEMODEL);           // the kit helmet (attachment 1) flies off
		let h = HCE_BruteHelmetDebris(Spawn("HCE_BruteHelmetDebris", pos + (0, 0, height * 0.95), ALLOW_REPLACE));
		if(h)
		{
			h.hce_piece = "debris_" .. hce_kitHelmet;
			double a = from ? from.AngleTo(self) : angle + 180;
			h.vel = (AngleToVector(a + frandom(-30, 30), frandom(3, 6)), frandom(4, 7));
			h.angle = angle;
		}
	}
	// decapitated with the kit helmet still on: it comes off too (the gib is the bare head)
	override void HCE_OnSever(int limb, bool gunArm)
	{
		if(limb == HCE_LIMB_HEAD && !hce_helmetOff && !HCE_HelmetFixed() && hce_kitHelmet.Length() > 0) HCE_KnockHelmet(target);
	}
	override color HCE_ShieldColor() { return Color(255, 255, 200, 90); }       // the Chieftain's gold overshield
	bool HCE_HelmetFixed() { String cn = GetClassName(); return hce_chief || cn.IndexOf("HonorGuard") >= 0; }   // honor guard helmets are part of the armour
	// the helmet takes the first head hit (it flies off instead): only a bare head can be headshot
	override bool HCE_HeadProtected() { return !hce_helmetOff || HCE_HelmetFixed(); }
	override void HCE_Die()
	{
		super.HCE_Die();
		hce_fallTics = 22;
		// pack morale: the last Brute nearby always goes berserk, others sometimes do
		Array<HaloDoom_EnemyBase> pack;
		let it = BlockThingsIterator.Create(self, 640);
		while(it.Next())
		{
			let b = HaloDoom_EnemyBase(it.thing);
			if(b && b != self && b.health > 0 && b.GetClassName() != 'None' && (b is "HCE_BruteBase")) pack.Push(b);
		}
		for(int i = 0; i < pack.Size(); i++)
			if(!pack[i].hce_berserk && (pack.Size() == 1 || frandom(0, 1) < 0.35)) pack[i].HCE_GoBerserk(true);
	}
'''

BRUTE_EVENTS = {
    'Alert': ['seefoe', 'seefoe_srprs', 'foundfoe', 'hrdfoe', 'morefoe', 'srprs'],
    'Taunt': ['tnt', 'thrtn', 'crs', 'cllcoward', 'cllwimp', 'strk'],
    'KillPlayer': ['glt', 'chr_kllfoe'],
    'Pain': ['pain', 'pain_shld'], 'PainMed': ['pain_mdm'], 'PainHeavy': ['pain_mjr', 'pain_fall'],
    'Death': ['dth', 'dth_slw'], 'DeathHard': ['dth_mjr', 'dth_hdsht', 'dth_fall'],
    'Berserk': ['brsrk', 'charge'], 'Melee': ['melee', 'meleeleap'],
    'Panic': ['panic'], 'Regroup': ['pstcmbt', 'newordr_charge'], 'LeaderDead': ['lmnt_deadally', 'lmnt'],
    'EnemyGrenade': ['warn_incmn_grnd', 'warn_incmn'], 'GrenadeThrow': ['strk_grnd'],
    'ManDown': ['lmnt_deadally', 'lmnt'], 'HeardGunfire': ['hrdfoe', 'srchstart'],
    # combat callouts (HCE_Say: Cover, SearchStart ...)
    'Cover': ['cvrme', 'cvrme_re'],
    'Uncovered': ['hlpme_uncovered'],
    'SearchStart': ['srchstart', 'srchpresrch'],
    'SearchClear': ['srch_allclr', 'prst_allclr'],
    'SearchFail': ['prstfail', 'prstfail_agg', 'prstfail_tim'],
    'KeepWatch': ['keepwatch'],
    'FoundFoe': ['foundfoe_srch', 'foundfoe'],
    'JoinMe': ['joinme', 'joinme_emrg'],
    'Charge': ['newordr_charge', 'charge'],
    'Investigate': ['cvrme_invsgt'],
    'Behind': ['seefoe_srprs', 'seefoe_too'],
    'Sniper': ['warn_wpn_snpr'],
    'Sword': ['warn_wpn_swrd'],
    'UpThere': ['seefoe_upthere'],
    'DownThere': ['seefoe_downthere'],
    'FallBack': ['newordr_fallback', 'newordr_retreat'],
    'Advance': ['newordr_advance', 'newordr_moveon'],
}
BRUTE_FX = {'Step': ['step_walk'], 'Run': ['step_run'], 'Thump': ['thump'], 'MeleeMove': ['melee_moves'],
            'BodyFall': ['bodyfall']}

def brute_sounds():
    """Halo 2 Brute voices (bloodthirsty, cruel) + effects (extract_h2_brute.extract_brute_sounds) -> HCE/<voice>/<event>"""
    src = OUT + '/sounds/Brute'
    if not os.path.exists(f'{src}/index.json'): return []
    idx = json.load(open(f'{src}/index.json'))
    lines = ['', '// Brutes (Halo 2 MCC: dialogue from sounds_en.dat, effects from sounds_neutral.dat)']
    def emit(group, prefix, table):
        """copy index.json's files for the group's leaves into the pack and add sndinfo lines: one id per file and
        a $random <prefix>/<event> per table entry"""
        for ev, leaves in sorted(table.items()):
            ids = []
            for leaf in leaves:
                for i, f in enumerate(idx.get(group, {}).get(leaf, [])):
                    dst = f'{PACK}/sounds/hce_dig/brute/{f}'
                    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(f'{src}/{f}', dst)
                    sid = f'{prefix}/{leaf}/{i}'; lines.append(f'{sid} "sounds/hce_dig/brute/{f}"'); ids.append(sid)
            if ids: lines.append(f'$random {prefix}/{ev} {{ {" ".join(ids)} }}')
    for voice in ('Brute_Bloodthirsty', 'Brute_Cruel'): emit(voice, f'HCE/{voice}', BRUTE_EVENTS)
    emit('fx', 'HCE/Brute', BRUTE_FX)
    return lines

def bp_fallback():
    """build_voices.FALLBACK (voice event -> the event to alias when a voice lacks it), imported lazily"""
    from build_voices import FALLBACK
    return FALLBACK

def zealot_skin(cls, v, si, mat, meta, skin_dir):
    """Ultra Zealot armour: the gold Elite's vivid bake (shading, edge highlights, the rank cube's sheen, dark gauntlets,
    teal undersuit) in crimson-maroon, then held to that hue with the sheen's pink pulled out (rich, not candy); its
    inset lights are already Reach blue (extract_ultra_zealot.py) and drawn bright"""
    if not mat.startswith('EliteZealot_'): return None
    os.makedirs(skin_dir, exist_ok=True)
    matn = mat[:-4]
    fn = f'{cls[4:].lower()}_{matn.lower()}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    C = 'EliteZealot'
    mp = f'{bp.OUT}/models/{C}/{matn}_multi.png'
    if not os.path.exists(mp):
        shutil.copy(f'{bp.OUT}/models/{C}/{mat}', dst)
        return fn
    bp.bake_vivid(C, matn, ZEALOT_RED, dst)
    im = Image.open(dst).convert('RGB'); rgb = np.asarray(im).astype(np.float32) / 255
    msk = np.asarray(Image.open(mp).convert('RGBA').resize(im.size)).astype(np.float32)[..., 2] / 255
    msk = msk * (1 - bp.hand_mask(C, matn, im.size))
    o = bp.hue_lock(rgb, msk / 0.8, ZEALOT_RED)
    hsv = np.asarray(Image.fromarray((np.clip(o, 0, 1) * 255).astype(np.uint8)).convert('HSV')).astype(np.float32)
    hsv[..., 1] = hsv[..., 1] * (1 - msk) + np.maximum(hsv[..., 1], 0.85 * 255) * msk
    hsv[..., 2] = hsv[..., 2] * (1 - msk * 0.32)
    Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB').save(dst)
    return fn


def configure():
    """register the Digsite add-on's weapons, skins, voices, ZScript and character overrides in build_pack's tables
    before bp.build() runs. To tune a Digsite character (health, scale, melee, flags), edit bp.CHAR_OVERRIDES here;
    to tune its guns, the bp.WEAPONS / PATTERNS / FIRE_SOUNDS entries"""
    W = bp.W
    bp.WEAPONS['plasma carbine'] = ('HCE_CarbineRound', 'HaloCarbine_Bullet', 15, 6.0)   # HDE's green carbine round
    bp.WEAPONS['particle beam'] = ('HCE_BeamRifleShot', 'HCE_BeamPuff', None, 30.0)
    bp.FIRE_CODE.update({'plasma carbine': 'cr', 'particle beam': 'sr', 'pulse carbine': 'cr'})
    # Pulse Carbine: HDE's homing, accelerating plasma bolts in bursts (its own gun fires five-bolt bursts)
    bp.WEAPONS['pulse carbine'] = ('HCE_PulseCarbineBolt', 'HCE_PulseCarbineHoming', 8, 1.2)
    bp.PATTERNS['pulse carbine'] = (5, 10, 3, 1.4, 2.3, 0, False, 1.0, 1.0)   # five-bolt bursts (HCE_TriggerBurst)
    bp.FIRE_SOUNDS['pulse carbine'] = (W + 'PulseCarbine/Fire', W + 'PulseCarbine/Fire/Bass', '', '', False)
    bp.DROP_WEAPON['pulse carbine'] = 'Halo_PulseCarbine'
    bp.WEAPON_IDS[PULSE] = 'cmt_carbine'
    bp.WEAPON_SKIN['pulse carbine'] = {f'w_cmt_carbine_{k}.png': f'w_cmt_carbine_blue_{k}.png' for k in ('purple', 'lights', 'icon', 'meter')}
    bp.PATTERNS['plasma carbine'] = (2, 3, 9, 1.0, 1.7, 0, False, 1.0, 1.0)      # semi-auto pairs/triples
    # Brute weapons: the CE plasma rifle / assault rifle / shotgun come from the main pack's tables; the Spiker fires
    # HDE's own spikes (Halo 3's Spiker is an automatic: AR-like bursts); the gravity hammer is melee only and drops
    # HDE's hammer
    bp.WEAPONS['spiker'] = ('HCE_SpikerSpike', 'HaloSpiker_Bullet', 10, 2.0)
    bp.PATTERNS['spiker'] = (5, 9, 3, 0.8, 1.4, 0, True, 1.0, 2.0)
    bp.FIRE_SOUNDS['spiker'] = (W + 'Spiker/Fire', W + 'Spiker/Fire/Bass', '', '', False)
    bp.DROP_WEAPON['spiker'] = 'Halo_Spiker'
    bp.DROP_WEAPON['gravity hammer'] = 'Halo_GravityHammer'
    bp.DROP_WEAPON['plasma caster'] = 'Halo_PlasmaCaster'
    bp.WEAPON_IDS[SPIKER] = 'spiker'
    bp.WEAPON_IDS[HAMMER] = 'gravity_hammer'
    bp.FIRE_CODE['spiker'] = 'sk'
    bp.SKIN_HOOK['Brute'] = brute_skin
    bp.SKIN_HOOK['FloodBrute'] = flood_brute_skin
    bp.SKIN_HOOK['SlugMan'] = slug_skin
    bp.OVERLAY_SLOT['Brute'] = CASTER_IDX            # its Plasma Caster's slot, which the human guns it picks up use too
    bp.OVERLAY_PLACEHOLDER.add('Brute')
    bp.BERSERK_ANIMS['Brute'] = {
        'IDLE': ['berserk idle'], 'ALERT': ['berserk idle'], 'MOVE_F': ['berserk move-front'], 'MOVE_B': ['berserk move-front'],
        'MOVE_L': ['berserk move-front'], 'MOVE_R': ['berserk move-front'], 'FLEE': ['berserk move-front'],
        'TURN_L': ['berserk turn-left'], 'TURN_R': ['berserk turn-right'],
        'MELEE': [f'berserk melee {i}' for i in range(1, 6)] + ['berserk tackle 1', 'berserk tackle 2']}
    bp.TYPE_CODE['Brute'] = brute_code()
    bp.PATTERNS['particle beam'] = (1, 1, 1, 2.2, 3.2, 35, False, 2.5, 0.7)      # 1 s aiming laser, then one beam
    bp.SPECIAL_FIRE['particle beam'] = 1.0
    bp.FIRE_SOUNDS['plasma carbine'] = (W + 'Carbine/Fire', W + 'Carbine/Fire/Bass', '', '', False)
    bp.FIRE_SOUNDS['particle beam'] = ('', '', W + 'BeamRifle/Laser/Fire', W + 'BeamRifle/Laser/Begin', False)
    bp.DROP_WEAPON.update({'plasma carbine': 'Halo_Carbine', 'particle beam': 'Halo_BeamRifle'})
    bp.WEAPON_IDS.update({CARBINE: 'cmt_carbine', BEAM: 'particle_beam_dig'})
    bp.VOICES.update({'SlugMan': 'Slug', 'EliteRifle': 'Elite_Dogmatic,Elite_Loose', 'Drinol': 'Drinol', 'BlindWolf': 'Blind_Wolf',
                      'Engineer': 'Engineer', 'Drone': 'Drone',
                      'Brute': 'Brute_Bloodthirsty,Brute_Cruel', 'FloodBrute': 'Flood'})
    # Halo 2 Jackals and Halo 2's beam rifle (it behaves like HaloDoom's: a held beam whose damage climbs while it
    # stays on a target, fired in ~1 s bursts with a cool-down between them; HDE's laser sounds)
    if os.path.exists(H2J_JSON):
        bp.SKIN_HOOK['H2Jackal'] = h2jackal_skin
        bp.TYPE_CODE['H2Jackal'] = h2jackal_code()
        bp.SHIELD_MAT['H2Jackal'] = 'H2Jackal_jackal_shield'
        bp.FIELD_CHARS.add('H2Jackal')        # its arm shield drawn by a shield field (Halo CE's Jackal shield: the same UV layout)
        bp.VOICES['H2Jackal'] = 'Jackal'
    # (the beam rifle itself is set up in build_pack.py: the Spec Ops Elite carries it too)
    if os.path.exists(f'{bp.OUT}/models/EliteZealot/EliteZealot.json'):
        zm = json.load(open(f'{bp.OUT}/models/EliteZealot/EliteZealot.json'))
        bp.SKIN_HOOK['EliteZealot'] = zealot_skin
        bp.SHIELD_MAT['EliteZealot'] = zm['shield']
        bp.FIELD_CHARS.add('EliteZealot'); bp.FIELD_UV_MASK.add('EliteZealot')   # its arm shield as the Jackals': a shield field, a mask from its own UVs
        bp.SHIELD_TINT['field marshal'] = ZEALOT_BLUE
        bp.SHINE['EliteZealot'] = 1.0; bp.SHINE_CUBE['EliteZealot'] = 'elite'
        bp.SHELL_TINT['EliteZealot'] = bp.SHELL_TINT['Elite']
        bp.VOICES['EliteZealot'] = 'Elite_Dogmatic,Elite_Loose'
        # the forearm shield's energy field goes out when the Zealot dies (its surface hidden, as a broken Jackal shield's)
        zsurf = zm['meshes'].index(zm['shield'] + '.png')
        bp.BASE_CODE['EliteZealot'] = bp.BASE_CODE.get('EliteZealot', '') + f"""
	override void HCE_Die()
	{{
		super.HCE_Die();
		A_ChangeModel('None', 0, "", 'None', {zsurf}, "models/hce/weapons", 'hce_hidden.png', CMDL_USESURFACESKIN);
		if(hce_holoActor) hce_holoActor.bInvisible = true;     // (its shield field)
		HCE_ResumeAnim();      // (A_ChangeModel restarts the model's animation: the death animation goes on)
	}}
"""
    bp.TYPE_CODE['Engineer'] = ENGINEER_CODE
    bp.SKIN_HOOK['Drone'] = drone_skin
    # a swarm is mostly Minors: they come up three times as often as each ranked loadout
    # the gold Zealot Slug Men are the rarest pick: every other Slug Man counts twice in HCE_RandomSlugMan
    bp.RANDOM_WEIGHTS.update({f'HCE_SlugMan{r.capitalize()}{"".join(w.title() for w in k.split())}': 2
                              for r, ks in SLUG_RANK_WEAPONS.items() if r != 'zealot' for k in ks})
    bp.RANDOM_WEIGHTS.update({c: 2 for c in ('HCE_SlugManParticleBeam', 'HCE_SlugManPlasmaPistol')})
    bp.RANDOM_WEIGHTS.update({c: 3 for c in ('HCE_DronePlasmaPistol', 'HCE_DroneNeedler', 'HCE_DronePlasmaRifle', 'HCE_DroneSpiker')})
    bp.SHELL_TINT['Drone'] = DRONE_SHELL
    bp.SHELL_TINT['Engineer'] = bp.SHELL_TINT['Elite']      # its 200-point shield flares in the Covenant's blue
    bp.BASE_CODE['Drone'] = DRONE_CODE    # every Drone shares it (the swarm finds its mates of any weapon)
    bp.WEAPON_CODE['particle beam'] = BEAM_CODE
    bp.WEAPON_CODE['plasma carbine'] = CARBINE_CODE
    bp.CHAR_OVERRIDES.update({
        # a war beast twice a Hunter's height: shrunk to fit Doom maps; charges, swats, pounces
        'Drinol': dict(stance='unarmed', health=320, scale=0.62, radius=34, melee=(44, 60),
                       flags=['HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Leaps'],
                       leap=(140, 420, 0.6, 13.0), anims={'LEAP_START': ['charging_jump']}),
        'SlugMan': dict(stance={'particle beam': 'rifle', 'plasma pistol': 'pistol', 'needler': 'pistol', 'plasma rifle': 'pistol',
                                'plasma carbine': 'rifle', 'pulse carbine': 'rifle'}, melee=(24, 20),
                        flags=['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades'],
                        anims_by_weapon={'plasma pistol': {'FIRE': ['stand pistol pp fire-1 baked']}}),
        'EliteRifle': dict(stance='rifle'),
        # SPV3 a30's Blind Wolf: a Pinky-style melee charger that also pounces (its leap-start/airborne/melee set)
        # SPV3 b30's Engineer: unarmed, harmless floater with Halo's 150 body / 200 shield; bursts into charged
        # Plasma Caster grenades when killed (an environmental hazard). Takes the Pain Elemental's slot.
        'Engineer': dict(stance='unarmed', flying=True, scale=1.25, radius_fixed=26, height_fixed=56, drops=False,
                         flags=['HCE_Flying']),
        # Halo 2 Drone (Yanme'e): fragile darting flier with a plasma pistol; perches on walls, scatters when the
        # swarm takes losses, falls out of the air when killed
        # Halo 2 Brutes: scaled to 115%, a head and more over an Elite (its rifle idle is 0.90 WU tall against the
        # Elite's 0.80), hulking as in Halo 2; the hitbox stays door-sized (76 high). Melee 2.0 WU / 1.5 WU from
        # their char tag, berserk charge that throws the gun away, plasma grenades
        # stances: the gravity hammer's ('melee'); the two-handed guns (assault rifle, shotgun) in the Halo 3-style
        # carbine stance (be_anims.py); the one-handed ones (plasma rifle, Spiker, Plasma Caster) in the rifle stance
        'Brute': dict(stance={'gravity hammer': 'melee', 'assault rifle': 'carbine', 'shotgun': 'carbine', 'plasma carbine': 'carbine',
                              'beam rifle': 'carbine', 'fuel rod': 'carbine', None: 'rifle'}, scale=BRUTE_SCALE,
                      height_fixed=76, radius_fixed=30, melee=(130, 35), weapon_toss=True, shield=0, speed=6.5,
                      flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_Leader']),
        'H2Jackal': dict(stance='pistol'),
        # the Flood Brute: a Brute's frame at the Brutes' scale and hitbox, the Flood combat forms' charge, leap and
        # claw (Halo 2's own leap set); its claw hits like the Brute's fist, a little harder
        'FloodBrute': dict(scale=BRUTE_SCALE, height_fixed=76, radius_fixed=30, melee=(130, 40), shield=0,
                           leap=(160, 400, 0.6, 14.0)),    # (its behaviour flags: the Flood actor's, as the other forms')
        'Drone': dict(stance='pistol', flying=True, radius_fixed=22, height_fixed=48, shield=0, speed=9.5, flags=['HCE_Flying']),
        'BlindWolf': dict(stance='unarmed', health=90, melee=(30, 22),
                          flags=['HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Leaps'], leap=(48, 300, 0.7, 14.0)),
    })

def build():
    """build the Digsite add-on pack: configure(), then bp.build() with its characters (DoomEdNums from 30400), then the
    extras bp doesn't know: brightmaps, the digsite_src ZScript, sndinfo.dig, the Cyberdemon Drinol, Brute helmet
    debris, the Captain's hologram flag and the Brute armour kit. To add a character, add it to cou/team here"""
    configure()
    ai = load_ai()
    if os.path.exists(PACK): shutil.rmtree(PACK)
    os.makedirs(PACK)
    cou = {r'digsite\characters\drinol\00_mac\drinol': 'Drinol', r'digsite\characters\slug_man\slug_man': 'SlugMan',
           ELITE_RIFLE: 'EliteRifle', r'characters\blind_wolf\blind_wolf': 'BlindWolf',
           r'characters\engineer\engineer': 'Engineer',     # (SPV3's Thorn Beast was taken out: too limited an enemy)
           DRONE: 'Drone', BRUTE: 'Brute', H2JACKAL: 'H2Jackal', ULTRA_ZEALOT: 'EliteZealot', FLOOD_BRUTE: 'FloodBrute'}
    team = {'EliteZealot': 'COVENANT', 'Drinol': 'COVENANT', 'SlugMan': 'COVENANT', 'EliteRifle': 'COVENANT', 'BlindWolf': 'COVENANT', 'Engineer': 'COVENANT', 'Drone': 'COVENANT', 'Brute': 'COVENANT', 'H2Jackal': 'COVENANT', 'FloodBrute': 'FLOOD'}
    cfg = dict(char_of_unit=cou, team=team, ai=ai, pack=PACK, mdir='hce_dig', tag='dig', ed0=30400, main=False,
               handler='HCE_DigsiteHandler', nerf_mixin='HCE_DigNerfMixin', lite_mixin='HCE_DigLitePlasma', late_chars=['BlindWolf', 'Engineer', 'Drone', 'Brute', 'H2Jackal', 'FloodBrute'],
               late_order=['HCE_BlindWolf', 'HCE_RandomBlindWolf',
                           'HCE_EliteMinorPulseCarbine', 'HCE_EliteMajorPulseCarbine', 'HCE_EliteSpecopsPulseCarbine',
                           'HCE_EliteCommanderPulseCarbine', 'HCE_Engineer', 'HCE_RandomEngineer', 'HCE_DronePlasmaPistol', 'HCE_RandomDrone',
                           'HCE_BruteMinorPlasmaRifle', 'HCE_BruteMinorAssaultRifle', 'HCE_BruteMajorSpiker', 'HCE_BruteMajorShotgun', 'HCE_BruteCaptainPlasmaRifle', 'HCE_BruteCaptainShotgun', 'HCE_BruteHonorGuardPlasmaRifle', 'HCE_BruteHonorGuardAssaultRifle', 'HCE_BruteChieftainGravityHammer', 'HCE_RandomBrute',
                           'HCE_JackalUltraPlasmaRifle', 'HCE_JackalZealotSpiker', 'HCE_JackalSniperBeamRifle', 'HCE_RandomH2Jackal',
                           'HCE_JackalMarksmanPlasmaCarbine', 'HCE_JackalMarksmanPulseCarbine',
                           'HCE_DroneNeedler', 'HCE_DronePlasmaRifle', 'HCE_DroneSpiker', 'HCE_BruteCaptainPlasmaCaster',
                           'HCE_BruteMajorPlasmaCarbine', 'HCE_BruteCaptainBeamRifle', 'HCE_BruteHonorGuardFuelRod',
                           'HCE_EliteUltraZealotEnergySword',
                           'HCE_DroneMajorPlasmaPistol', 'HCE_DroneMajorNeedler', 'HCE_DroneUltraNeedler', 'HCE_DroneUltraPlasmaRifle',
                           'HCE_DroneCaptainPlasmaPistol', 'HCE_DroneCaptainPlasmaRifle', 'HCE_DroneCaptainMajorNeedler',
                           'HCE_DroneCaptainMajorPlasmaRifle',
                           'HCE_JackalMajorHelmetPlasmaRifle',
                           'HCE_SlugManZealotParticleBeam', 'HCE_SlugManZealotPlasmaRifle', 'HCE_SlugManZealotPulseCarbine',
                           'HCE_BruteJumpPackSpiker', 'HCE_BruteJumpPackPlasmaRifle'] + FLOOD_BRUTE_ORDER, index='digsite_index.json', glow=[f'w_cmt_carbine_{b}{k}.png' for b in ('', 'blue_') for k in ('lights', 'icon', 'meter')] + ['w_spiker_heat.png'],
               gl_title='// Digsite add-on: glowing surfaces')
    bp.build(cfg)
    if H2J_BRIGHT:                               # the H2 sniper helmet's lenses glow
        open(f'{PACK}/gldefs.dig', 'a').write(''.join(f'brightmap texture "{f[len(PACK) + 1:]}"\n{{\n\tmap "{b[len(PACK) + 1:]}"\n}}\n' for f, b in H2J_BRIGHT))
    zj = f'{bp.OUT}/models/EliteZealot/EliteZealot.json'
    if os.path.exists(zj):                       # the Ultra Zealot's inset lights glow
        gl = []
        for g in json.load(open(zj)).get('glow', []):
            for f in sorted(glob.glob(f'{PACK}/models/hce_dig/EliteZealot/skins/*_{g.lower()}.png')):
                gl.append(f'brightmap texture "{f[len(PACK) + 1:]}"\n{{\n\tmap "models/hce_dig/brightmap_full.png"\n}}')
        if gl: open(f'{PACK}/gldefs.dig', 'a').write('\n'.join(gl) + '\n')
    src = os.path.join(HERE, 'digsite_src')
    for f in ('dig_handler.zsc', 'dig_boss.zsc', 'dig_pulse.zsc', 'dig_brute.zsc'):
        shutil.copy(f'{src}/{f}', f'{PACK}/ZScript/HaloCE/{f}')
    for f in ('zscript.txt', 'cvarinfo.txt', 'CREDITS.txt'):
        shutil.copy(f'{src}/{f}', f'{PACK}/{f}')
    open(f'{PACK}/sndinfo.dig', 'w').write('\n'.join(voices() + engineer_sounds() + drone_sounds() + brute_sounds() + h2jackal_sounds()) + '\n')
    # Cyberdemon stand-in: the Drinol at 78% instead of 62% (dig_boss.zsc)
    import re
    md = open(f'{PACK}/modeldef.dig').read()
    blk = re.search(r'Model HCE_Drinol\n\{.*?\n\}\n', md, re.S).group(0)
    sc = S * 0.78
    boss = re.sub(r'Scale [^\n]*', f'Scale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}', blk).replace('Model HCE_Drinol', 'Model HCE_BossCyberdemonDrinol')
    open(f'{PACK}/modeldef.dig', 'a').write('\n' + boss)
    # Brute helmet debris (pops off on headshots)
    hs = OUT + '/models/BruteHelmet'
    if os.path.exists(f'{hs}/BruteHelmet.iqm'):
        hd = f'{PACK}/models/hce_dig/BruteHelmet'; os.makedirs(hd, exist_ok=True)
        for f in ('BruteHelmet.iqm', 'BruteHelmet_0.png'): shutil.copy(f'{hs}/{f}', f'{hd}/{f}')
        # no Skin line: the model names its own texture, so the kit helmets swapped in keep theirs
        open(f'{PACK}/modeldef.dig', 'a').write('\nModel HCE_BruteHelmetDebris\n{\n\tPath "models/hce_dig/BruteHelmet"\n'
            f'\tModel 0 "BruteHelmet.iqm"\n\tScale {80 * BRUTE_SCALE:.0f} {80 * BRUTE_SCALE:.0f} {96 * BRUTE_SCALE:.0f}\n\tUseActorPitch\n\tUseActorRoll\n'
            '\tFrameIndex HCEM A 0 0\n}\n')
    # Halo 2's Brute Captain hologram flag (brute_captain_flag.py): a companion actor (dig_brute.zsc) with the Brute's
    # skeleton (every surface hidden) and the flag as its attachment, drawn additively with the hologram shader
    fsrc = f'{bp.OUT}/models/Brute'
    if os.path.exists(f'{fsrc}/Brute_captain_flag.iqm'):
        bd = f'{PACK}/models/hce_dig/Brute'
        shutil.copy(f'{fsrc}/Brute_captain_flag.iqm', f'{bd}/Brute_captain_flag.iqm')
        shutil.copy(f'{fsrc}/captain_flag.png', f'{bd}/skins/captain_flag.png')
        cap = re.search(r'Model HCE_BruteCaptainPlasmaRifle\n\{.*?\n\}\n', md, re.S).group(0)
        sc_line = re.search(r'\tScale [^\n]*', cap).group(0)
        nsurf = len(json.load(open(f'{fsrc}/Brute.json'))['meshes'])
        hide = ''.join(f'\tSurfaceSkin 0 {i} "hce_hidden.png"\n' for i in range(nsurf))
        open(f'{PACK}/modeldef.dig', 'a').write('\nModel HCE_BruteCaptainFlag\n{\n\tPath "models/hce_dig/Brute"\n\tModel 0 "Brute.iqm"\n'
            '\tPath "models/hce_dig/weapons"\n' + hide + '\tPath "models/hce_dig/Brute"\n\tModel 1 "Brute_captain_flag.iqm"\n'
            '\tSurfaceSkin 1 0 "skins/captain_flag.png"\n' + sc_line + '\n\tUseActorPitch\n\tUseActorRoll\n\tBaseFrame\n'
            '\tFrameIndex HCEM A 0 0\n\tFrameIndex HCEM A 1 0\n}\n')
        os.makedirs(f'{PACK}/shaders', exist_ok=True)
        open(f'{PACK}/shaders/hce_holoflag.fp', 'w').write(HOLOFLAG_SHADER)
        open(f'{PACK}/gldefs.dig', 'a').write('material texture "models/hce_dig/Brute/skins/captain_flag.png"\n{\n'
            '\tshader "shaders/hce_holoflag.fp"\n\tspeed 1.0\n\tbrightmap "models/hce_dig/brightmap_full.png"\n}\n')
    # Brute armour kit pieces (model attachments, swapped in by HCE_DressArmour)
    if os.path.exists(KIT_JSON):
        kd = f'{PACK}/models/hce_dig/BruteKit'; os.makedirs(kd, exist_ok=True)
        for f in os.listdir(KIT_DIR):
            if f.endswith(('.iqm', '.jpg', '.png')): shutil.copy(f'{KIT_DIR}/{f}', f'{kd}/{f}')
        # the coloured kit armour shines like the Elites' (armour_shine), its normals from the kit pieces wearing it
        from iqm import read_iqm
        from texmath import raster_normals
        kit_meshes = [m for f in sorted(os.listdir(KIT_DIR)) if f.endswith('.iqm') and not f.startswith('debris_')
                      for m in read_iqm(f'{KIT_DIR}/{f}')[1]]
        for f in sorted(os.listdir(KIT_DIR)):
            if KIT_SHINE_TEX not in f or not f.endswith(('.jpg', '.png')): continue
            im = Image.open(f'{KIT_DIR}/{f}').convert('RGB')
            n = raster_normals(kit_meshes, f, im.size)
            if not np.abs(n).sum(): continue
            rgb = armour_shine(np.asarray(im).astype(np.float32) / 255.0, n.copy())
            Image.fromarray((rgb * 255).astype(np.uint8)).save(f'{kd}/{f}', quality=95)
        kit_tint_pieces(kd)
    # the derez on every skin (build_pack.derez_materials): a Forerunner weapon's kill burns the body away in its colour
    skins = bp.modeldef_skins(open(f'{PACK}/modeldef.dig').read())
    kd = f'{PACK}/models/hce_dig/BruteKit'
    if os.path.isdir(kd): skins |= {f'models/hce_dig/BruteKit/{f}' for f in os.listdir(kd) if f.endswith(('.png', '.jpg'))}
    gl, _used = bp.derez_materials(open(f'{PACK}/gldefs.dig').read(), skins, 'models/hce_dig/brightmap_none.png')
    open(f'{PACK}/gldefs.dig', 'w').write(gl)
    os.makedirs(f'{PACK}/shaders', exist_ok=True)
    open(f'{PACK}/shaders/hce_derez.fp', 'w').write(bp.DEREZ_SHADER)
    os.makedirs(f'{PACK}/models/hce_dig', exist_ok=True)
    Image.new('RGB', (8, 8), (0, 0, 0)).save(f'{PACK}/models/hce_dig/brightmap_none.png')

if __name__ == '__main__':
    # the add-on's bodies (the Brute, the Halo 2 Jackal) checked for skipped post-extraction steps like the main pack's
    bp.check_steps({c: json.load(open(f'{bp.OUT}/models/{c}/{c}.json')) for c in ('Brute', 'H2Jackal')
                    if os.path.exists(f'{bp.OUT}/models/{c}/{c}.json')})
    build()
    bp.cap_skins(PACK)
    bp.modeldef_prune.prune(PACK)               # the blocks build() appended after the main build's pass too
    # both packs' code is final now: the bodies keep only the animations it names (lib/anim_trim.py)
    import anim_trim
    _HERE = os.path.dirname(os.path.abspath(__file__))
    anim_trim.trim([bp.PACK, PACK], [bp.PACK, PACK, os.path.join(_HERE, 'addons', 'localdev'), os.path.join(_HERE, 'standalone')])
