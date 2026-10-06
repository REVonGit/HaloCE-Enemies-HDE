#!/usr/bin/env python3
"""Standalone Halo CE enemy packs: no HaloDoom Evolved, no separate enemy-API pk3.

Takes the regular pack source trees (factions/<core|covenant|flood|sentinels|marines>, addons/digsite) and the
enemy API, and writes standalone/out/<pack>/ trees + HaloCE_Standalone_<Pack>.pk3:

  * the enemy API (HaloDoom_EnemyBase -> HCES_EnemyBase) and hces_lib.zsc go into the standalone core
  * every HDE class the enemies used is swapped for its HCES_ counterpart (projectiles, grenades, shields,
    explosions); weapon drops become Doom ammo (other mods' ammo replacements pick these up)
  * HDE's sounds, sprites and models those classes need are copied in under unique names
    (sounds HCES/..., sprites HZ**, models/hces/...), so nothing collides with HDE or other mods
"""
import os, re, shutil, sys, zipfile
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HDE = os.environ.get('HCE_HDE_PK3', os.path.join(HERE, 'HDE_LocalDEV.pk3'))   # HaloDoom Evolved Local_DEV: its pk3 or unpacked folder
API = os.environ.get('HCE_API') or next((p for p in (os.path.join(HERE, 'api', 'enemies_base.zsc'),
    os.path.join(HERE, 'addons', 'localdev', 'ZScript', 'BaseAI', 'enemies_base.zsc')) if os.path.exists(p)), None)
FACTIONS = os.environ.get('HCE_FACTIONS', os.path.join(HERE, 'factions'))
DIGSITE = os.environ.get('HCE_DIG_PACK', os.path.join(HERE, 'addons', 'digsite'))
OUTDIR = os.environ.get('HCE_SA_OUT', os.path.join(HERE, 'standalone', 'out'))
PK3DIR = os.environ.get('HCE_SA_PK3', HERE)
LIB = os.path.join(HERE, 'standalone', 'hces_lib.zsc')
LOOT = os.path.join(HERE, 'standalone', 'hces_loot.zsc')
VERSION = 'version "4.15.1"\n'
PACKS = {'core': 'Core', 'covenant': 'Covenant', 'flood': 'Flood', 'sentinels': 'Sentinels', 'marines': 'Marines',
         'digsite': 'Enemies_Digsite'}

# HDE class -> standalone class (word-boundary replace in every ZScript / text lump)
CLASS_MAP = {
    'HaloDoom_EnemyBase': 'HCES_EnemyBase', 'LastDamageInfo': 'HCES_LastDamageInfo', 'HaloMath': 'HCES_Math',
    'BulletCasing': 'Actor', 'ShieldProcessor': 'HCES_ShieldProcessor',
    'PlasmaGrenade_Proj': 'HCES_PlasmaGrenade', 'FragGrenade_Proj': 'HCES_FragGrenade', 'HaloGrenade_Proj': 'HCES_Grenade',
    'HaloProjectile': 'HCES_Projectile', 'HaloSlowProjectile': 'HCES_SlowProjectile',
    'HaloShotgun_Bullet': 'HCES_ShotgunPellet', 'HaloMAB_Bullet': 'HCES_ARBullet', 'HaloSidekick_Bullet': 'HCES_PistolBullet',
    'HaloSniper_Bullet': 'HCES_SniperBullet', 'HaloPlasma_Proj': 'HCES_PlasmaPistolBolt',
    'HaloChargedPlasma_Proj': 'HCES_ChargedPlasma', 'HaloPlasmaRifle_Proj': 'HCES_PlasmaRifleBolt',
    'HaloNeedler_Proj': 'HCES_Needle', 'FuelrodPlasma': 'HCES_FuelRod', 'HaloRocketProj': 'HCES_Rocket',
    'HaloFlames': 'HCES_Flame', 'PlasmaCasterProj': 'HCES_PlasmaCasterProj',
    'PlasmaCasterClusterProj': 'HCES_PlasmaCasterCluster', 'HaloCarbine_Bullet': 'HCES_CarbineBullet',
    'HaloPulseCarbine_Proj': 'HCES_PulseCarbineProj', 'HaloSpiker_Bullet': 'HCES_SpikerSpike',
    'GravityHammerExplosion': 'HCES_HammerBlast', 'HaloNeedleProjectile': 'HCES_Needle',
    # the regular core's nerfable explosive subclasses (hce_explosives.zsc) -> the standalone classes, which
    # already scale their blasts by DamageMultiply
    'HCE_NeedleScaled': 'HCES_Needle', 'HCE_FuelRodScaled': 'HCES_FuelRod', 'HCE_RocketScaled': 'HCES_Rocket',
    'HCE_PlasmaCasterScaled': 'HCES_PlasmaCasterProj', 'HCE_PlasmaCasterClusterScaled': 'HCES_PlasmaCasterCluster',
    'HCE_PlasmaCasterMiniScaled': 'HCES_PlasmaCasterMini', 'HCE_FragGrenade': 'HCES_FragGrenade',
    'HCE_PlasmaGrenade': 'HCES_PlasmaGrenade',
}
# HDE weapon / grenade pickups: nothing in the standalone packs -- hces_loot.zsc hands out weapons, ammo,
# health and armor by what the player needs instead (the old one-to-one map is kept for reference)
DROP_TO_NONE = True
DROP_MAP = {
    'Halo_PlasmaPistol': 'Cell', 'Halo_PlasmaRifle': 'Cell', 'Halo_Needler': 'Cell', 'Halo_Carbine': 'Cell',
    'Halo_PulseCarbine': 'Cell', 'Halo_BeamRifle': 'Cell', 'Halo_Flamethrower': 'Cell', 'Halo_FuelRod': 'RocketAmmo',
    'Halo_RocketLauncher': 'RocketAmmo', 'Halo_MA5B': 'Clip', 'Halo_Magnum': 'Clip', 'Halo_SniperRifle': 'Clip',
    'Halo_Spiker': 'Clip', 'Halo_Shotgun': 'Shell', 'Halo_GravityHammer': 'None', 'Halo_EnergySword': 'None',
    'PlasmaGrenades': 'None', 'FragGrenades': 'None',
}
# sprites copied from HDE, renamed to unique HZ** names
SPRITES = {'SX04': 'HZX4', 'FSH1': 'HZF1', 'IPF2': 'HZIP', 'SMOK': 'HZSM', 'L2NB': 'HZL2', 'FRAG': 'HZFG', 'PLGN': 'HZPG',
           'XTH1': 'HZT1', 'XTH2': 'HZT2', 'FSP2': 'HZFP', 'FX58': 'HZ58'}
MODELS = ['Models/Weapons/tracer.md3', 'Models/Weapons/tracer1.tga', 'Models/Weapons/plasma.md3',
          'Models/Weapons/plasma_core.md3', 'Models/Weapons/laser.png', 'Models/Weapons/needle_crystal.MD3',
          'Models/Weapons/needle_crystal.png', 'Models/Weapons/rocket.MD3', 'Models/Weapons/rocket.png',
          'Models/Weapons/spike_shard.MD3', 'Models/Weapons/spike_shard.png', 'Models/Title/sky_sphere.md3',
          'Models/Lasers/lazer.png', 'Models/Lasers/beam_simple.md3', 'Models/Lasers/BEAM_detailed.png']
# model per standalone class (subclasses in the packs get the same entry: MODELDEF is per class)
MODEL_OF = {
    'HCES_Bullet': ('tracer.md3', 'tracer1.tga', '3.0 3.0 1.5', 'PITCHFROMMOMENTUM'),
    'HCES_ShotgunPellet': ('tracer.md3', 'tracer1.tga', '3.0 1.5 1.5', 'PITCHFROMMOMENTUM'),
    'HCES_SniperBullet': ('tracer.md3', 'tracer1.tga', '3.0 1.5 1.5', 'PITCHFROMMOMENTUM'),
    'HCES_PlasmaBolt': ('plasma.md3', 'laser.png', '5.0 10.0 10.0', 'USEACTORPITCH\n\tUSEACTORROLL\n\tCORRECTPIXELSTRETCH'),
    'HCES_PlasmaCore': ('plasma_core.md3', 'laser.png', '5.0 10.0 10.0', 'USEACTORPITCH\n\tUSEACTORROLL\n\tCORRECTPIXELSTRETCH'),
    'HCES_Needle': ('needle_crystal.MD3', 'needle_crystal.png', '4.0 4.0 2.5', 'PITCHFROMMOMENTUM\n\tAngleOffset 90'),
    'HCES_Rocket': ('rocket.MD3', 'rocket.png', '10.0 10.0 10.0', 'AngleOffset 90\n\tUSEACTORPITCH'),
    'HCES_SpikerSpike': ('spike_shard.MD3', 'spike_shard.png', '4.0 4.0 2.5', 'AngleOffset 90\n\tUSEACTORPITCH'),
    'HCES_Shockwave': ('sky_sphere.md3', 'lazer.png', '50.0 50.0 50.0', 'DONTCULLBACKFACES'),
    'HCE_EnemyLaser': ('beam_simple.md3', 'BEAM_detailed.png', '1.0 1.0 1.0', 'USEACTORPITCH'),   # enemy laser tracers
}
LIGHT_OF = {'HCES_PlasmaPistolBolt': 'HCES_GreenLight', 'HCES_ChargedPlasma': 'HCES_GreenLightBig',
            'HCES_PlasmaRifleBolt': 'HCES_BlueLight', 'HCES_PulseCarbineProj': 'HCES_BlueLight',
            'HCES_Needle': 'HCES_PinkLight', 'HCES_Bullet': 'HCES_YellowLight', 'HCES_CarbineBullet': 'HCES_GreenLight',
            'HCES_FuelRod': 'HCES_GreenLightBig', 'HCES_Rocket': 'HCES_OrangeLight', 'HCES_Flame': 'HCES_OrangeLight',
            'HCES_PlasmaGrenade': 'HCES_BlueLight', 'HCES_SpikerSpike': 'HCES_OrangeLight'}
LIGHT_DEFS = '''pointlight HCES_GreenLight { color 0.1 1.0 0.3 size 40 }
pointlight HCES_GreenLightBig { color 0.1 1.0 0.3 size 72 }
pointlight HCES_BlueLight { color 0.2 0.5 1.0 size 40 }
pointlight HCES_PinkLight { color 0.9 0.2 1.0 size 24 }
pointlight HCES_YellowLight { color 1.0 0.85 0.3 size 16 }
pointlight HCES_OrangeLight { color 1.0 0.55 0.15 size 48 }
'''
LIGHT_FRAMES = {'HCES_FuelRod': 'HZFP', 'HCES_Flame': ('HZT1', 'HZT2'), 'HCES_PlasmaGrenade': 'HZPG'}


CREDITS = """Halo CE enemy packs, standalone build
=====================================
These packs run without HaloDoom Evolved. The projectile, grenade, explosion and shield code in
ZScript/HaloCE/hces_lib.zsc is ported from HaloDoom Evolved (Local_DEV branch), and the sounds (sounds/hces),
sprites (sprites/hces, renamed HZ**) and projectile models (models/hces) are copied from it. All credit for
those assets and the original code goes to the HaloDoom Evolved team. HDE was made under Microsoft's Game
Content Usage Rules; Halo is a trademark of Microsoft. Not for sale.
"""


class DirZip:
    """an unpacked HDE folder read like its pk3"""
    def __init__(self, root):
        self.root = root
        self.files = [os.path.relpath(os.path.join(r, f), root).replace(os.sep, '/') for r, _, fs in os.walk(root) for f in fs]
    def namelist(self): return self.files
    def read(self, n): return open(os.path.join(self.root, n), 'rb').read()


def wordmap(text, mapping):
    pat = re.compile(r'\b(' + '|'.join(sorted(map(re.escape, mapping), key=len, reverse=True)) + r')\b')
    return pat.sub(lambda m: mapping[m.group(1)], text)


def convert_text(t):
    t = re.sub(r'\tmixin HCE_(Dig)?NerfMixin;\n', '', t)     # HDE-only hook; HCES projectiles keep their fire-time damage
    t = re.sub(r'(?s)// the core.s HCE_NerfMixin, repeated here.*?\nmixin class HCE_DigNerfMixin\n\{.*?\n\}\n', '', t)
    t = wordmap(t, CLASS_MAP)
    t = re.sub(r'"(' + '|'.join(DROP_MAP) + r')"', lambda m: '"None"' if DROP_TO_NONE else f'"{DROP_MAP[m.group(1)]}"', t)
    t = re.sub(r'(?<!HCES/)\b(Halo|Shield)/', r'HCES/\1/', t)          # HDE sound names -> our copies
    return t


def class_tree(texts):
    """class -> parent over all given ZScript sources"""
    par = {}
    for t in texts:
        for m in re.finditer(r'^\s*class\s+(\w+)\s*(?::\s*(\w+))?', t, re.M):
            par[m.group(1)] = m.group(2)
    return par


def ancestor_in(cls, par, keys):
    seen = 0
    while cls and seen < 50:
        if cls in keys: return cls
        cls = par.get(cls); seen += 1
    return None


# ---------------------------------------------------------------- HDE sound resolution
class Sounds:
    def __init__(self, z):
        self.z = z
        self.names = {n.lower(): n for n in z.namelist()}
        self.base = {}
        for n in z.namelist():
            b = os.path.splitext(n.split('/')[-1])[0].lower()
            if n.lower().startswith('sounds/'): self.base.setdefault(b, n)
        self.defs, self.extra = {}, {}
        src = z.read(next(n for n in z.namelist() if n.lower() == 'sndinfo.txt')).decode('utf-8', 'replace')
        src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
        for line in src.split('\n'):
            line = line.split('//')[0].strip()
            if not line: continue
            m = re.match(r'\$random\s+(\S+)\s*\{([^}]*)\}', line, re.I)
            if m: self.defs[m.group(1).lower()] = ('random', m.group(2).split()); continue
            m = re.match(r'\$alias\s+(\S+)\s+(\S+)', line, re.I)
            if m: self.defs[m.group(1).lower()] = ('alias', [m.group(2)]); continue
            m = re.match(r'\$(volume|limit|attenuation|rolloff|pitchshift|singular)\s+(\S+)(.*)', line, re.I)
            if m: self.extra.setdefault(m.group(2).lower(), []).append((m.group(1), m.group(3).strip())); continue
            if line.startswith('$'): continue
            m = re.match(r'(\S+)\s+"?([^"]+?)"?\s*$', line)
            if m: self.defs[m.group(1).lower()] = ('file', [m.group(2)])

    def lump(self, ref):
        r = ref.replace('\\', '/').lower()
        if r in self.names: return self.names[r]
        return self.base.get(os.path.splitext(r.split('/')[-1])[0])

    def emit(self, wanted, sound_dir):
        """wanted: HDE logical names -> (sndinfo lines with HCES/ names, files to copy {zip name: pack path})"""
        lines, files, done, missing = [], {}, set(), []
        def walk(name):
            k = name.lower()
            if k in done: return True
            d = self.defs.get(k)
            if not d: missing.append(name); return False
            done.add(k)
            kind, refs = d
            if kind == 'file':
                src = self.lump(refs[0])
                if not src: missing.append(f'{name} ({refs[0]})'); return False
                dst = f'{sound_dir}/' + src.split('/', 1)[1].lower() if '/' in src else f'{sound_dir}/{src.lower()}'
                files[src] = dst
                lines.append(f'HCES/{name} "{dst}"')
            else:
                ok = [r for r in refs if walk(r)]
                if not ok: return False
                lines.append(f'$random HCES/{name} {{ {" ".join("HCES/" + r for r in ok)} }}' if kind == 'random'
                             else f'$alias HCES/{name} HCES/{ok[0]}')
            for cmd, rest in self.extra.get(k, []):
                lines.append(f'${cmd} HCES/{name} {rest}')
            return True
        for w in wanted: walk(w)
        return lines, files, missing


# ---------------------------------------------------------------- build
def standalone_defaults(t):
    """a plain Doom player has no energy shield: a slightly stronger default projectile nerf"""
    return re.sub(r'(server float hce_nerf_projectiles = )[\d.]+;', r'\g<1>0.3;', t)


def copytree_text(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.loudened.json'))
    for root, _, fs in os.walk(dst):
        for f in fs:
            p = os.path.join(root, f)
            low = f.lower()
            if low.endswith(('.zsc', '.txt')) or low.split('.')[0] in ('modeldef', 'gldefs', 'sndinfo', 'mapinfo', 'cvarinfo'):
                t = convert_text(open(p, errors='replace').read())
                if low.startswith('cvarinfo'): t = standalone_defaults(t)
                open(p, 'w').write(t)


def model_and_light_defs(pack_texts, lib_par):
    """MODELDEF / GLDEFS entries for every class in these sources that derives from a modelled HCES class"""
    par = dict(lib_par); par.update(class_tree(pack_texts))
    mine = list(class_tree(pack_texts))
    md, gl = [], []
    for cls in mine:
        a = ancestor_in(cls, par, MODEL_OF)
        if a:
            mdl, skin, sc, extra = MODEL_OF[a]
            md.append(f'Model {cls}\n{{\n\tPath "models/hces"\n\tModel 0 "{mdl}"\n\tSkin 0 "{skin}"\n\tScale {sc}\n\t{extra}\n'
                      f'\tFrameIndex HCEM A 0 0\n}}\n')
        l = ancestor_in(cls, par, LIGHT_OF)
        if l:
            fr = LIGHT_FRAMES.get(l, 'HCEM')
            fr = fr if isinstance(fr, tuple) else (fr,)
            gl.append(f'object {cls}\n{{\n' + ''.join(f'\tframe {f} {{ light {LIGHT_OF[l]} }}\n' for f in fr) + '}\n')
    return md, gl


def build():
    if os.path.exists(OUTDIR): shutil.rmtree(OUTDIR)
    os.makedirs(OUTDIR)
    z = DirZip(HDE) if os.path.isdir(HDE) else zipfile.ZipFile(HDE)
    lib = open(LIB).read()
    lib_par = class_tree([lib])
    sources = {k: os.path.join(FACTIONS, k) for k in ('core', 'covenant', 'flood', 'sentinels', 'marines')}
    sources['digsite'] = DIGSITE
    sounds_used = set()
    for key, src in sources.items():
        if not os.path.isdir(src): print('skip (not built):', src); continue
        dst = os.path.join(OUTDIR, key)
        copytree_text(src, dst)
        zs_dir = os.path.join(dst, 'ZScript', 'HaloCE')
        texts = [open(os.path.join(r, f)).read() for r, _, fs in os.walk(dst) for f in fs if f.endswith('.zsc')]
        if key == 'core':
            api = convert_text(open(API).read())
            open(os.path.join(zs_dir, 'hces_api.zsc'), 'w').write(api)
            shutil.copy(LIB, os.path.join(zs_dir, 'hces_lib.zsc'))
            shutil.copy(LOOT, os.path.join(zs_dir, 'hces_loot.zsc'))
            mi = open(os.path.join(dst, 'mapinfo.txt')).read()
            mi = mi.replace('AddEventHandlers = "HCE_ReplaceHandler"', 'AddEventHandlers = "HCE_ReplaceHandler", "HCES_LootHandler"')
            open(os.path.join(dst, 'mapinfo.txt'), 'w').write(mi)
            with open(os.path.join(dst, 'cvarinfo.txt'), 'a') as cf:
                cf.write('server float hces_loot = 1.0;           // standalone loot: 0 = enemies drop nothing, 1 = balanced, 2 = generous\n'
                         'server bool hces_loot_weapons = true;    // standalone loot: enemies can drop Doom weapons the player is missing\n')
            zt = open(os.path.join(dst, 'zscript.txt')).read()
            zt = zt.replace('// Needs HaloDoom_EnemyBase from HCE_EnemyAPI_LocalDEV.pk3 (loaded before this file); add any faction packs after it.',
                            '// Standalone: carries the enemy API and the HDE-derived projectiles/effects; needs no other pk3.')
            zt = zt.replace('// Needs HCES_EnemyBase from HCE_EnemyAPI_LocalDEV.pk3 (loaded before this file); add any faction packs after it.',
                            '// Standalone: carries the enemy API and the HDE-derived projectiles/effects; needs no other pk3.')
            zt = zt.replace('#include "ZScript/HaloCE/hce_explosives.zsc"\n', '')   # HDE-only; hces_lib has its own
            lm = os.path.join(dst, 'modeldef.hce_lasers')            # HDE's paths: the standalone entry comes from MODEL_OF
            if os.path.exists(lm): os.remove(lm)
            ex = os.path.join(zs_dir, 'hce_explosives.zsc')
            if os.path.exists(ex): os.remove(ex)
            zt = re.sub(r'(#include "ZScript/HaloCE/hce_projectiles.zsc")',
                        '#include "ZScript/HaloCE/hces_api.zsc"\n#include "ZScript/HaloCE/hces_lib.zsc"\n#include "ZScript/HaloCE/hces_loot.zsc"\n\\1', zt)
            open(os.path.join(dst, 'zscript.txt'), 'w').write(zt)
            texts += [api, lib]
            # assets: models, sprites
            md_dir = os.path.join(dst, 'models', 'hces'); os.makedirs(md_dir, exist_ok=True)
            for m in MODELS:
                real = next(n for n in z.namelist() if n.lower() == m.lower())
                open(os.path.join(md_dir, os.path.basename(m)), 'wb').write(z.read(real))
            sp_dir = os.path.join(dst, 'sprites', 'hces'); os.makedirs(sp_dir, exist_ok=True)
            n_spr = 0
            for n in z.namelist():
                b = n.split('/')[-1]
                if not n.lower().startswith('sprites/') or len(b) < 6 or b[:4].upper() not in SPRITES: continue
                new = SPRITES[b[:4].upper()] + b[4:]
                open(os.path.join(sp_dir, new), 'wb').write(z.read(n)); n_spr += 1
            open(os.path.join(dst, 'gldefs.hces_lights'), 'w').write('// standalone projectile lights\n' + LIGHT_DEFS)
            open(os.path.join(dst, 'CREDITS_STANDALONE.txt'), 'w').write(CREDITS)
            print('core: models', len(MODELS), 'sprites', n_spr)
        # per-pack model / light entries for HCES-derived classes
        own = [open(os.path.join(r, f)).read() for r, _, fs in os.walk(zs_dir) for f in fs if f.endswith('.zsc')]
        md, gl = model_and_light_defs(own, lib_par)
        if md: open(os.path.join(dst, f'modeldef.hces_{key}'), 'w').write(f'// standalone: projectile models ({key})\n' + '\n'.join(md))
        if gl: open(os.path.join(dst, f'gldefs.hces_{key}'), 'w').write(f'// standalone: projectile lights ({key})\n' + '\n'.join(gl))
        for t in texts:
            sounds_used.update(re.findall(r'"HCES/((?:Halo|Shield|Needler|Ricochet)/[^"]+)"', t))
        for r, _, fs in os.walk(dst):
            for f in fs:
                if f.lower().startswith('sndinfo'):
                    for line in open(os.path.join(r, f)):
                        sounds_used.update(re.findall(r'HCES/((?:Halo|Shield)/\S+)', line))
    # HDE sounds -> core
    lib_snd = re.findall(r'"HCES/([^"]+)"', lib)
    sounds_used.update(lib_snd)
    snd = Sounds(z)
    lines, files, missing = snd.emit(sorted(sounds_used), 'sounds/hces')
    core = os.path.join(OUTDIR, 'core')
    for src, dstp in files.items():
        p = os.path.join(core, dstp); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(z.read(src))
    open(os.path.join(core, 'sndinfo.hces_hde'), 'w').write(
        '// HaloDoom Evolved sounds used by the enemies and their projectiles (copied, renamed HCES/...)\n' + '\n'.join(lines) + '\n')
    print('sounds', len(sounds_used), 'files', len(files), 'missing', missing)
    # pk3s
    for key, name in PACKS.items():
        d = os.path.join(OUTDIR, key)
        if not os.path.isdir(d): continue
        out = os.path.join(PK3DIR, f'HaloCE_Standalone_{name.replace("Enemies_", "")}.pk3')
        if os.path.exists(out): os.remove(out)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for r, _, fs in os.walk(d):
                for f in sorted(fs):
                    p = os.path.join(r, f); zf.write(p, os.path.relpath(p, d))
        print(f'{os.path.basename(out)}: {os.path.getsize(out) / 1e6:.1f} MB')


if __name__ == '__main__':
    build()
