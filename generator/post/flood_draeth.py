"""flood_draeth.py: the Flood Dr'aeth, the combat form a Dr'aeth (Reaver) becomes when the Flood take it. Run from
generator/ after flood_variants.py:  python3 post/flood_draeth.py [the Standalone repo's packs/HaloCE_Standalone_Flood]

Its body is the pack author's (Raw Assets/Flood Draeth/fish_combat_form.blend, Blender 5, read without Blender by
lib/brute_kit.py): Halo CE's Flood combat Elite with the Dr'aeth's 1999 armour and helmet grown into it, rigged to the
Flood Elite's own skeleton (its bip01 bones and antenna / spike frames), its armour in a Flood-stained copy of the
Dr'aeth's skin (textures/covenant_master.png). So it is the Flood Elite in everything but its looks:
  * models/hce/FloodDraeth/FloodDraeth.iqm: the Flood Elite's model (packs/HaloCE_Flood/models/hce/FloodElite) with
    its five whole-body surfaces (head, arms, legs and torso flesh, torso fronds) swapped for the blend's, in the same
    surface order, so every surface number in the Flood Elite's code (gore, baked guns, blood) still holds: its torn
    stumps (the damaged head and arms), its baked guns and its animations are the Flood Elite's. Flesh and armour
    share one surface each (head; legs and torso) on a two-cell skin, skins/flooddraeth_0.png: the Flood Elite's flesh
    skin on the left, the Dr'aeth's stained armour on the right (UVs moved into their cells); the fronds keep the
    Flood Elite's cut-out tendril skin
  * FloodDraeth_gib_head.iqm (its head, flying off: the Flood Elite's neck cap on it), _gib_larm / _gib_rarm (the
    Flood Elite's, the arms being its), FloodDraeth_blood<k>.iqm (its body under the Flood Elite's blood, the
    armour cells left clean)
  * the classes (HCE_FloodcombatDraeth<gun>, one over each Flood Elite class: zscript between the FLOOD DRAETH markers
    of hce_flood.zsc), their MODELDEF (modeldef.hce_flood_draeth), editor numbers and the bestiary rows. The
    infection forms raise a dead Dr'aeth as one (hce_flood.zsc HCE_CanInfect / HCE_HostForm).
Runs again cleanly."""
import os, re, sys, struct
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); GEN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(GEN, 'lib'))
from iqm import read_iqm, write_iqm
import brute_kit as bk
ROOT = os.path.join(GEN, '..')
RAW = os.path.join(ROOT, 'Raw Assets', 'Flood Draeth')
HDE_FLOOD = os.path.join(ROOT, 'packs', 'HaloCE_Flood')
FLOOD = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else HDE_FLOOD     # (or the Standalone repo's HaloCE_Standalone_Flood)
FE = os.path.join(FLOOD, 'models', 'hce', 'FloodElite')
OUTD = os.path.join(FLOOD, 'models', 'hce', 'FloodDraeth')
# the Flood Elite's surfaces -> the blend's object for it (None: kept as the Flood Elite's)
SURFACES = {0: 'head base superhigh.001', 2: 'left arm base superhigh', 4: ('legs base superhigh.001', 'torso base superhigh.001'),
            5: 'right arm base superhigh', 7: 'torso base superhigh.001'}
FRONDS = 'flood fronds'                   # (the torso's fronds: surface 7; its flesh goes to surface 4)
ARMOUR = 'armor superhigh'                # (the right cell of the two-cell skin)

def anim_info(path):
    """the IQM's animations' (name, fps, loop) in order (read_iqm drops them)"""
    d = open(path, 'rb').read()
    h = struct.unpack_from('<16sII' + 'I' * 27, d, 0)
    ofs_text, num_anims, ofs_anims = h[5], h[18], h[19]
    out = []
    for i in range(num_anims):
        n, first, num, fps, fl = struct.unpack_from('<IIIfI', d, ofs_anims + i * 20)
        out.append((d[ofs_text + n:d.index(b'\0', ofs_text + n)].decode('latin1'), fps, bool(fl & 1)))
    return out

def blend_surfaces(J):
    """the blend's meshes as the five surfaces: {surface: mesh dict on J's joints, UVs in the two-cell skin}"""
    nodes = [j[0].lower().replace('bip01 ', '').replace(' ', '_') for j in J]
    K = bk.Kit(os.path.join(RAW, 'fish_combat_form.blend'))
    parts = {}
    for k, objs in SURFACES.items():
        objs = objs if isinstance(objs, tuple) else (objs,)
        ms = []
        for ob in objs:
            p = K.piece(ob, nodes)
            assert not p['missing'] and not p['unweighted'], (ob, p['missing'], p['unweighted'])
            for s, mn in enumerate(p['mats']):
                if (k == 7) != (mn == FRONDS): continue          # (fronds on 7 only, flesh and armour elsewhere)
                sel = p['tmat'] == s
                if not sel.any(): continue
                uv = p['uv'].copy(); uv[:, 1] = 1 - uv[:, 1]         # (Blender's V up -> the IQM's down)
                if k != 7:
                    # into the skin's cell: each face's U brought back into the texture's first tile first (the
                    # Flood Elite's flesh is mapped one tile over, 1 to 2, for a repeating texture; no face crosses a
                    # tile's edge)
                    T = p['tris'][sel]; sh = np.zeros(len(uv)); sh[T.ravel()] = np.repeat(np.floor(uv[T][..., 0].min(1)), 3)
                    uv[:, 0] = np.clip(uv[:, 0] - sh, 0, 1) * 0.5 + (0.5 if mn == ARMOUR else 0)
                ms.append((p, p['tris'][sel], uv))
        # one mesh of the corners the faces use
        pos, nrm, uvs, bi, bw, tris, base = [], [], [], [], [], [], 0
        for p, t, uv in ms:
            used = np.unique(t); remap = np.full(len(p['pos']), -1); remap[used] = np.arange(len(used)) + base
            pos.append(p['pos'][used]); nrm.append(p['nrm'][used]); uvs.append(uv[used])
            bi.append(p['bi'][used]); bw.append(p['bw'][used]); tris.append(remap[t]); base += len(used)
        w = np.concatenate(bw); w8 = np.round(w * 255).astype(int)
        w8[:, 0] += 255 - w8.sum(1)                              # (the weights summing to 255)
        parts[k] = dict(pos=np.concatenate(pos), nrm=np.concatenate(nrm), uv=np.concatenate(uvs), tris=np.concatenate(tris),
                        bidx=np.concatenate(bi).astype(np.uint8), bw=w8.clip(0, 255).astype(np.uint8))
    return parts

def gib_head(fe_head, fe_gib, head):
    """the head gib as gore_kit.py makes them, on our head: the Flood Elite's gib (its head and its neck cap, rigid,
    turned to lie flat: thinnest axis up, centred on its bounds) put back where its head sits on the body (the rigid
    fit of its head onto the body's), our head swapped in, and the pair laid flat again the same way"""
    used = np.unique(fe_head['tris'])
    A = fe_gib[0]['pos'][used]; B = fe_head['pos'][used]            # (the gib's head: the body's, vertex for vertex)
    ca, cb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb)); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))])
    R = (U @ D @ Vt).T                                             # local -> body: B = (A - ca) R^T + cb
    cap = fe_gib[24]; cap_w = (cap['pos'] - ca) @ R.T + cb
    P = head['pos'][np.unique(head['tris'])]; ctr = P.mean(0)
    Pa = np.concatenate([P, cap_w])
    ev, evec = np.linalg.eigh(np.cov((Pa - ctr).T))
    Rg = evec[:, ::-1].T
    if np.linalg.det(Rg) < 0: Rg[1] *= -1
    Q = (Pa - ctr) @ Rg.T; mid = (Q.min(0) + Q.max(0)) / 2
    rigid = lambda m, pos, nrm: dict(m, pos=(pos - ctr) @ Rg.T - mid, nrm=nrm @ Rg.T,
                                     bidx=np.zeros((len(pos), 4), np.uint8), bw=np.tile(np.array([255, 0, 0, 0], np.uint8), (len(pos), 1)))
    out = list(fe_gib)
    out[0] = rigid(dict(head, name=fe_gib[0]['name'], material='FloodDraeth_0.png'), head['pos'], head['nrm'])
    out[24] = rigid(cap, cap_w, cap['nrm'] @ R.T)
    return out

def head_numbers(head, gib):
    """HCE_SpawnLimb's numbers for the head: its centre on the body and its half thickness lying flat"""
    P = head['pos'][np.unique(head['tris'])]
    Q = np.concatenate([gib[0]['pos'][np.unique(gib[0]['tris'])], gib[24]['pos']])
    return P.mean(0), float((Q[:, 2].max() - Q[:, 2].min()) / 2)

def two_cell(left, right, size=512):
    """the two-cell skin: left and right images side by side, each size x size"""
    out = Image.new('RGBA', (size * 2, size), (0, 0, 0, 0))
    if left: out.paste(left.convert('RGBA').resize((size, size), Image.LANCZOS), (0, 0))
    if right: out.paste(right.convert('RGBA').resize((size, size), Image.LANCZOS), (size, 0))
    return out

def build_model():
    os.makedirs(os.path.join(OUTD, 'skins'), exist_ok=True)
    src = os.path.join(FE, 'FloodElite.iqm')
    J, M, A = read_iqm(src)
    info = anim_info(src)
    anims = [dict(name=n, fps=fps, loop=loop, frames=A[n]) for n, fps, loop in info]
    parts = blend_surfaces(J)
    body = []
    for i, m in enumerate(M):
        if i in parts:
            mat = 'FloodDraeth_2.png' if i == 7 else 'FloodDraeth_0.png'
            body.append(dict(parts[i], name=m['name'], material=mat))
        else: body.append(m)
    write_iqm(os.path.join(OUTD, 'FloodDraeth.iqm'), J, body, anims)
    print('FloodDraeth.iqm', [(i, m['name'], len(m['tris'])) for i, m in enumerate(body) if i < 8])
    sk = os.path.join(FE, 'skins')
    two_cell(Image.open(os.path.join(sk, 'floodelite_floodelite_0.png')), Image.open(os.path.join(RAW, 'textures', 'covenant_master.png'))) \
        .convert('RGB').save(os.path.join(OUTD, 'skins', 'flooddraeth_0.png'), optimize=True)
    # the gibs: its own head with the Flood Elite's neck cap; the arms are the Flood Elite's
    bind = [dict(name='bind', fps=30.0, loop=True, frames=[[(j[2], j[3], j[4]) for j in J]])]
    for g in ('head', 'larm', 'rarm'):
        Jg, Mg, _ = read_iqm(os.path.join(FE, f'FloodElite_gib_{g}.iqm'))
        if g == 'head': Mg = gib_head(M[0], Mg, parts[0]); head = head_numbers(parts[0], Mg)
        write_iqm(os.path.join(OUTD, f'FloodDraeth_gib_{g}.iqm'), Jg, Mg, bind)
    # the blood: its body under the Flood Elite's blood (the flesh cell; the armour cell clean)
    for k in (1, 2, 3):
        Jb, Mb, _ = read_iqm(os.path.join(FE, f'FloodElite_blood{k}.iqm'))
        Mb = [dict(parts[i], name=m['name'], material=f'blood{k}_FloodDraeth_{2 if i == 7 else 0}.png') if i in parts else m for i, m in enumerate(Mb)]
        write_iqm(os.path.join(OUTD, f'FloodDraeth_blood{k}.iqm'), Jb, Mb, bind)
        two_cell(Image.open(os.path.join(FE, f'blood{k}_FloodElite_0.png')), None).save(os.path.join(OUTD, f'blood{k}_FloodDraeth_0.png'), optimize=True)
        Image.open(os.path.join(FE, f'blood{k}_FloodElite_2.png')).save(os.path.join(OUTD, f'blood{k}_FloodDraeth_2.png'), optimize=True)
    Image.open(os.path.join(FE, 'gore_FloodElite.png')).save(os.path.join(OUTD, 'gore_FloodDraeth.png'), optimize=True)
    return head

ZS = os.path.join(FLOOD, 'ZScript', 'HaloCE')
ED0 = 30940                               # (editor numbers: 30940 up, the random one last)
SKIP = ('StealthUnarmed',)                # (the stealth Flood Elite: a Stealth Elite's host, not a Dr'aeth's)
TITLES = {'AssaultRifle': 'Assault Rifle', 'FlameThrower': 'Flamethrower', 'PlasmaPistol': 'Plasma Pistol', 'PlasmaRifle': 'Plasma Rifle',
          'RocketLauncher': 'Rocket Launcher', 'SniperRifle': 'Sniper Rifle'}

def elite_classes():
    """the Flood Elite's classes (gun suffix -> its UDB sprite), in file order"""
    zs = open(os.path.join(ZS, 'hce_flood.zsc')).read()
    out = {}
    for m in re.finditer(r'^class HCE_FloodcombatElite(\w+) : HCE_FloodEliteBase\n\{(.*?)^\}', zs, re.S | re.M):
        if m.group(1) in SKIP: continue
        sp = re.search(r'//\$Sprite "(\w+)"', m.group(2))
        out[m.group(1)] = sp.group(1) if sp else 'HU38A0'
    return out

def write_code(head):
    ctr, rest = head
    guns = elite_classes()
    z = ['// The Flood Dr\'aeth (generator/post/flood_draeth.py; written by it, edit there): a Dr\'aeth (Reaver) taken by the Flood.',
         '// One class over each Flood Elite class: the Flood Elite in everything but its body (models/hce/FloodDraeth, the',
         '// pack author\'s: the Flood Elite with the Dr\'aeth\'s 1999 armour and helmet grown into it). The infection forms raise a',
         '// dead Dr\'aeth as one (HCE_HostForm).', '',
         'mixin class HCE_FloodDraethBody', '{',
         '\t// its own head flies off (the arms are the Flood Elite\'s), its own body under the blood, an Elite\'s footsteps',
         '\toverride bool HCE_SeverLimb(int limb)', '\t{',
         '\t\tif(limb != 0 || (hce_severed & 1)) return super.HCE_SeverLimb(limb);',
         '\t\tHCE_HideSurface(0);',
         '\t\tif(hce_shellActor) hce_shellActor.A_ChangeModel(\'None\', 0, "", \'None\', 0, "models/hce/weapons", \'hce_hidden.png\', CMDL_USESURFACESKIN);',
         '\t\tHCE_ShowSurface(1);',
         f'\t\tHCE_SpawnLimb(0, ({ctr[0]:.4f}, {ctr[1]:.4f}, {ctr[2]:.4f}), 80.00, "models/hce/FloodDraeth", \'FloodDraeth_gib_head.iqm\', 24, \'gore_FloodDraeth.png\', {rest:.4f});',
         '\t\tHCE_OnSever(0, false);', '\t\treturn true;', '\t}',
         '\toverride void HCE_BloodModel(int stage)', '\t{', '\t\tswitch(stage)', '\t\t{']
    z += [f'\t\tcase {k}: A_ChangeModel(\'None\', 7, "models/hce/FloodDraeth", \'FloodDraeth_blood{k}.iqm\'); break;' for k in (1, 2, 3)]
    z += ['\t\t}', '\t}', '\toverride Name HCE_StepSet() { return \'elite\'; }', '}', '']
    md = ['// the Flood Dr\'aeth (generator/post/flood_draeth.py): the Flood Elite\'s MODELDEF on its own body']
    ed = ['// ---- FLOOD DRAETH (generator/post/flood_draeth.py) ----', 'DoomEdNums', '{']
    names = []
    for i, (g, sprite) in enumerate(guns.items()):
        cls = f'HCE_FloodcombatDraeth{g}'; names.append(cls)
        title = "Floodcombat Dr'aeth Unarmed" if g == 'Unarmed' else f"Floodcombat Dr'aeth ({TITLES.get(g, g)})"
        z += [f'class {cls} : HCE_FloodcombatElite{g}', '{', '\tmixin HCE_FloodDraethBody;',
              '\t//$Category "Halo CE/Flood/Flood Dr\'aeth"', f'\t//$Title "{title}"', f'\t//$Sprite "{sprite}"',
              '\tDefault', '\t{', '\t\tTag "FloodDraeth";',
              f'\t\tHaloDoom_EnemyBase.HCE_Variant "floodcombat draeth {re.sub(r"(?<!^)([A-Z])", r" \1", g).lower()}";',
              '\t}', '}', '']
        md += [f'Model {cls}', '{', '\tPath "models/hce/FloodDraeth"', '\tModel 0 "FloodDraeth.iqm"']
        md += [f'\tSurfaceSkin 0 {k} "skins/flooddraeth_0.png"' for k in (0, 2, 4, 5)]
        md += ['\tPath "models/hce/FloodElite"', '\tSurfaceSkin 0 7 "skins/floodelite_floodelite_2.png"',      # (the fronds: the Flood Elite's tendrils)
               '\tPath "models/hce/weapons"', '\tScale 80 80 96', '\tUseActorPitch', '\tUseActorRoll', '\tBaseFrame', '\tFrameIndex HCEM A 0 0', '}', '']
        ed.append(f'\t{ED0 + i} = {cls}')
    z += ['class HCE_RandomFloodDraeth : RandomSpawner', '{', '\t//$Category "Halo CE/Flood/Flood Dr\'aeth"', '\t//$Title "Random Flood Dr\'aeth"',
          f'\t//$Sprite "{guns["Unarmed"]}"', '\tDefault', '\t{'] + [f'\t\tDropItem "{n}", 255, 1;' for n in names] + ['\t}', '}', '']
    ed += [f'\t{ED0 + len(names)} = HCE_RandomFloodDraeth', '}', '// ---- FLOOD DRAETH END ----']
    zt = '\n'.join(z)
    if FLOOD != HDE_FLOOD: zt = zt.replace('HaloDoom_EnemyBase.', 'HCES_EnemyBase.')     # (the Standalone's enemy base: build_standalone.py)
    open(os.path.join(ZS, 'hce_flood_draeth.zsc'), 'w').write(zt)
    open(os.path.join(FLOOD, 'modeldef.hce_flood_draeth'), 'w').write('\n'.join(md))
    inc = os.path.join(FLOOD, 'zscript.txt'); t = open(inc).read()
    if 'hce_flood_draeth.zsc' not in t:
        last = [l for l in t.split('\n') if l.startswith('#include')][-1]
        t = t.replace(last, last + '\n#include "ZScript/HaloCE/hce_flood_draeth.zsc"')
        open(inc, 'w').write(t)
    mi = os.path.join(FLOOD, 'mapinfo.txt'); t = open(mi).read()
    t = re.sub(r'\n?// ---- FLOOD DRAETH \(.*?// ---- FLOOD DRAETH END ----\n?', '\n', t, flags=re.S).rstrip('\n') + '\n\n' + '\n'.join(ed) + '\n'
    open(mi, 'w').write(t)
    # the materials: the Flood Elite's (its self-illuminated flesh: the mask in the flesh cell, none on the armour)
    sk = os.path.join(FE, 'skins')
    two_cell(Image.open(os.path.join(sk, 'floodelite_floodelite_0_si.png')), Image.new('RGB', (8, 8))).convert('RGB') \
        .save(os.path.join(OUTD, 'skins', 'flooddraeth_0_si.png'), optimize=True)
    gl = open(os.path.join(FLOOD, 'gldefs.hce_flood')).read()
    blk = re.search(r'material texture "models/hce/FloodElite/skins/floodelite_floodelite_0.png"\n\{.*?\n\}', gl, re.S).group(0)
    g = ['// the Flood Dr\'aeth (generator/post/flood_draeth.py): the Flood Elite\'s materials on its skins',
         blk.replace('FloodElite/skins/floodelite_floodelite_0', 'FloodDraeth/skins/flooddraeth_0')]
    for f in [f'blood{k}_FloodDraeth_{n}.png' for k in (1, 2, 3) for n in (0, 2)] + ['gore_FloodDraeth.png']:
        g += [f'material texture "models/hce/FloodDraeth/{f}"', '{', '\tshader "shaders/hce_derez.fp"', '\tbrightmap "models/hce/brightmap_none.png"', '}']
    open(os.path.join(FLOOD, 'gldefs.hce_flood_draeth'), 'w').write('\n'.join(g) + '\n')
    # the bestiary
    bp = os.path.join(FLOOD, 'hcebest.flood'); t = open(bp).read()
    t = '\n'.join(l for l in t.split('\n') if 'FloodcombatDraeth' not in l and not l.startswith('L\tFloodDraeth\t'))
    e = (f"E\tHCE_FloodcombatDraethPlasmaRifle\tFlood\tFlood (Dr'aeth host)\tCombat Form: Dr'aeth\t{guns['PlasmaRifle'][:4]}\tDraeth,FloodDraeth\t"
         f"{ED0 + list(guns).index('PlasmaRifle')}\tAny gun but the Forerunners'")
    lore = ("L\tFloodDraeth\tA Dr'aeth taken by the Flood, its old armour split and grown through, its helmet still on. It fights as "
            "a Flood Elite does, with whatever gun it held, and leaps on its prey; a fallen one rises again unless it is torn apart.")
    lines = t.split('\n')
    ei = max(i for i, l in enumerate(lines) if l.startswith('E\t')); lines.insert(ei + 1, e)
    li = max(i for i, l in enumerate(lines) if l.startswith('L\t')); lines.insert(li + 1, lore)
    open(bp, 'w').write('\n'.join(lines))
    print('classes', names)

# the infection forms take a dead (or dying) Dr'aeth too: its Flood form carrying its gun if one does, else unarmed (and
# its gun in hand all the same, through the Flood arsenal: the fuel rod, beam rifle and Plasma Caster)
PATCHES = [
    ("Brute with a Flood form of its own (not the Draeth; the Brutes only with the Digsite add-on's Flood Brute loaded)",
     "Brute or Dr'aeth with a Flood form of its own (the Brutes only with the Digsite add-on's Flood Brute loaded)"),
    ('if(cn.IndexOf("Draeth") >= 0) return false;', 'if(cn.IndexOf("Draeth") >= 0) return c.hce_team == HCE_TEAM_COVENANT;'),
    ('\t\tString GRUNT = "HCE_FloodGruntPlasmaPistol HCE_FloodGruntNeedler HCE_FloodGrunt";',
     '\t\tString GRUNT = "HCE_FloodGruntPlasmaPistol HCE_FloodGruntNeedler HCE_FloodGrunt";\n'
     '\t\t// a Dr\'aeth: the Flood Dr\'aeth (generator/post/flood_draeth.py)\n'
     '\t\tString DRAETH = "HCE_FloodcombatDraethNeedler HCE_FloodcombatDraethPlasmaRifle HCE_FloodcombatDraethUnarmed";'),
    ('\t\tif(c.hce_type == 2) return HCE_PickForm(GRUNT, wn);',
     '\t\tif(cn.IndexOf("Draeth") >= 0) return HCE_PickForm(DRAETH, wn);\n\t\tif(c.hce_type == 2) return HCE_PickForm(GRUNT, wn);'),
]

def patch_infection():
    for f in [os.path.join(ZS, 'hce_flood.zsc')] + ([os.path.join(GEN, 'templates', 'zscript', 'flood_infection.zs')] if FLOOD == HDE_FLOOD else []):
        t = open(f).read()
        for a, b in PATCHES:
            if b in t: continue
            assert a in t, (f, a)
            t = t.replace(a, b)
        open(f, 'w').write(t)

if __name__ == '__main__':
    write_code(build_model())
    patch_infection()
