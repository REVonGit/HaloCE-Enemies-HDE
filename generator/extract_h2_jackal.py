"""Halo 2 (MCC) Jackal from 08a_deltacliffs.map -> IQM + skins/masks + JSON, the Halo 2 beam rifle, and the
Jackal shield's pop sound.

One IQM for every Halo 2 Jackal class: the body, the arm shield (its emitter and its energy surface as separate
surfaces, so the shield can be switched off when it's drained), and the weapons in the left hand (the gun hand; the shield is on the right forearm) shown one at a
time per class: the CE plasma rifle (Ultra), the Spiker (Zealot) and Halo 2's beam rifle (Sniper).
Animations: the pistol stance (one-handed: plasma rifle, Spiker) and the rifle stance (the sniper's beam rifle),
crouches, dives, evades, surprise, flinches and deaths, with the fire overlays baked onto the idles.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import splitfile        # MCC's big data files, whole or in their numbered pieces
import json, os, pickle, shutil, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from h2map import H2Map, render_model, mcc_bitmap
import h2anim
from iqm import write_iqm
from extract_h2 import qmul, qrot
from extract_h2_brute import model_meshes, tag_oggs, SOUNDS_DIR, MAP08A, CACHE08A

from hce_paths import OUT
TEXTURES = os.environ.get('HCE_H2_TEXTURES', 'textures.dat')
JACKAL = r'objects\characters\jackal\jackal'
BEAM = r'objects\weapons\rifle\beam_rifle\beam_rifle'
BMP = r'objects\characters\jackal\bitmaps' + '\\'
HAND_WEAPONS = ['plasma_rifle', 'spiker', 'cmt_carbine']   # + the CMT carbine (the Marksmen; blue-skinned for the pulse carbine)                 # out/weapons/<id>/<id>.pkl (CE weapon space: origin = grip)
KEEP = {('body', 'standard'), ('shield', 'active')}
# shader -> (base bitmap, change-colour mask or None)
SHADER_MAPS = {
    'jackal_torso': ('torso', 'torso_change_color'), 'jackal_legs': ('legs', 'legs_change_color'),
    'jackal_armor_torso': ('torso', 'torso_change_color'), 'jackal_armor_legs': ('legs', 'legs_change_color'),
    'jackal_head': ('head', None), 'jackal_arms': ('arms', None), 'jackal_teethandspikes': ('head', None),
    'jackal_eyes': ('eyes', None), 'jackal_pupils': ('eyes_specular', None),
    'jackal_shield_emitter': ('torso', None),
    'jackal_shield': ('jackal_shield_noise', None),       # the energy surface: baked per rank by build_digsite
}
SHIELD_SHADER = 'jackal_shield'


def anim_plan():
    """Halo 2 name -> CE-style name, and overlays to bake: overlay -> (base anim, CE-style name)"""
    ren, ovl = {}, {}
    for w in ('pistol', 'rifle'):
        c = f'combat:{w}:'
        ren[c + ('idle' if w == 'rifle' else 'idle')] = f'stand {w} idle'
        for d in ('front', 'back', 'left', 'right'): ren[c + f'move_{d}'] = f'stand {w} move-{d}'
        for d in ('left', 'right'): ren[c + f'turn_{d}'] = f'stand {w} turn-{d}'; ren[c + f'evade_{d}'] = f'stand {w} evade-{d}'
        for d in ('front', 'left', 'right'): ren[c + f'dive_{d}'] = f'stand {w} dive-{d}'
        ren[c + 'airborne'] = f'stand {w} airborne'
        ren[c + 'land_soft'] = f'stand {w} land-soft'
        ren[c + 'land_hard'] = f'stand {w} land-hard'
        ren[c + 'surprise_front:var0'] = f'stand {w} surprise-front'
        ren[c + 'surprise_back'] = f'stand {w} surprise-back'
        ren[c + 'signal_attack'] = f'stand {w} signal-attack'
        ren[c + 'warn'] = f'stand {w} warn'
        ren[f'crouch:{w}:idle'] = f'crouch {w} idle'
        ren[f'crouch:{w}:move_front'] = f'crouch {w} move-front'
    ren['combat:pistol:cheer'] = 'stand pistol celebrate'
    ren['combat:rifle:celebrate'] = 'stand rifle celebrate'
    ren['combat:pistol:taunt'] = 'stand pistol taunt'
    ren['combat:pistol:shakefist'] = 'stand pistol melee'           # Halo 2's Jackal has no melee: it shakes its fist
    ren['flee:pistol:idle'] = 'flee pistol idle'
    ren['flee:pistol:move_front'] = 'flee pistol move-front'
    ren['combat:airborne_dead'] = 'stand airborne-dead'
    ren['combat:landing_dead'] = 'stand landing-dead'
    for d in ('front', 'back', 'left', 'right'):
        ren[f's_kill:{d}:gut' if d != 'front' else 's_kill:front:gut:var0'] = f's-kill {d} gut'
    for d in ('front', 'back', 'left'): ren[f'h_kill:{d}:gut'] = f'h-kill {d} gut'
    for d in ('front', 'back', 'left', 'right'): ren[f'h_ping:{d}:gut'] = f'h-ping {d} gut'
    ren['h_ping:front:chest'] = 'h-ping front chest'
    ren['h_ping:front:r_hand'] = 'h-ping front r-hand'
    for d in ('front', 'back', 'left', 'right'):
        ovl[f's_ping:{d}:gut:var0'] = ('combat:pistol:idle', f's-ping {d} gut baked')
    ovl['combat:pistol:pr:fire_1:var0'] = ('combat:pistol:idle', 'stand pistol fire-1 pr baked')
    ovl['crouch:rifle:csr:fire_1:var0'] = ('combat:rifle:idle', 'stand rifle fire-1 csr baked')     # the sniper's shot
    return ren, ovl


def bitmap(m, name):
    return mcc_bitmap(m, name, TEXTURES) if splitfile.exists(TEXTURES) else Image.new('RGBA', (16, 16), (110, 100, 90, 255))


def find_bitmap(m, short, under='objects\\characters\\jackal'):
    names = [t['name'] for t in m.tags if t['cls'] == 'bitm' and t['name'].endswith('\\' + short)]
    pref = [n for n in names if under in n]
    return (pref or names)[0]


def extract_beam_rifle(m, wid='h2_beam_rifle'):
    """Halo 2's beam rifle in weapon space (origin = the grip the hand marker holds)"""
    od = f'{OUT}/weapons/{wid}'; os.makedirs(od, exist_ok=True)
    M = render_model(m, BEAM)
    bitmap(m, find_bitmap(m, 'beam_rifle', 'beam_rifle\\bitmaps')).convert('RGB').save(f'{od}/w_{wid}_0.png')
    meshes = [dict(material=f'w_{wid}_0.png', pos=mm['pos'], nrm=mm['nrm'], uv=mm['uv'], tris=mm['tris'][:, [0, 2, 1]])
              for mm in model_meshes(m, M)]
    pickle.dump(dict(id=wid, meshes=meshes), open(f'{od}/{wid}.pkl', 'wb'))
    return wid


def extract_sounds(m, od):
    """the shield popping (jackal_shield_death) -> sounds/shield_pop_N.ogg"""
    files = {k: splitfile.open(os.path.join(SOUNDS_DIR, fn)) for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if splitfile.exists(os.path.join(SOUNDS_DIR, fn))}
    out = []
    os.makedirs(f'{od}/sounds', exist_ok=True)
    for i, data in enumerate(tag_oggs(m, r'sound\characters\jackal\jackal_shield_death', files) or []):
        fn = f'sounds/shield_pop_{i}.ogg'; open(f'{od}/{fn}', 'wb').write(data); out.append(fn)
    return out


# Halo CE's Jackal helmet (the armored_head permutation; ce_jackal_helmet.py) on the Halo 2 head: the two rigs share
# the head bone's axes; the Halo 2 head is a little larger and its snout sits further forward
HELMET_SCALE, HELMET_OFFSET = 1.12, (0.012, 0.032, 0.0)
from hce_paths import MAPS_DIR as CE_MAPS
# The Halo 2 Jackals go bare-headed, as Halo 2 draws them: the helmet surface is kept (so every surface index the build
# and gore_kit.py use stays as it was) but with no triangles. True puts Halo CE's helmet back on.
CE_HELMET = False


def add_ce_helmet(meshes, nodes, od, pid):
    try:
        import ce_jackal_helmet as cj
        h = cj.helmet(CE_MAPS)
    except Exception as e:
        print('  no CE Jackal helmet:', e); return
    from preview import qmat
    W = []
    for n in nodes:
        t = np.array(n['t']); q = np.array(n['q'])
        if n['parent'] < 0: W.append((t, q))
        else:
            pt, pq = W[n['parent']]; W.append((pt + qrot(pq, t), qmul(pq, q)))
    hi = next(i for i, n in enumerate(nodes) if n['name'] == 'head')
    t, q = W[hi]; R = qmat(q)
    pos = (h['pos'] * HELMET_SCALE + np.array(HELMET_OFFSET)) @ R.T + t
    n = len(pos)
    bidx = np.zeros((n, 4), np.uint8); bidx[:, 0] = hi
    bw = np.zeros((n, 4), np.uint8); bw[:, 0] = 255
    h['base'].convert('RGB').save(f'{od}/{pid}_jackal_helmet.png')
    if h['multi'] is not None:                     # the multipurpose map's red marks the helmet plate: rank colour
        r = h['multi'].convert('RGBA').split()[0]
        Image.merge('RGB', (r, Image.new('L', r.size, 0), Image.new('L', r.size, 0))).save(f'{od}/{pid}_jackal_helmet_mask.png')
    meshes.append(dict(name='helmet.jackal_helmet', material=f'{pid}_jackal_helmet.png', pos=pos, nrm=h['nrm'] @ R.T,
                       uv=h['uv'], bidx=bidx, bw=bw, tris=h['tris'] if CE_HELMET else np.zeros((0, 3), int)))


# IanLacksMods' Halo 2 Characters+ tag pack (its Jackal: HCE_H2_CHARACTERS_PLUS, the pack's folder): the body re-cut
# from its source JMS (L5_jackal.JMS: the stock body to within a millimetre, with arm armour added and the head's quills
# split off into a 'hair' region so a helmet can take their place) and its helmets: Halo CE's for Majors and Halo 3's
# sniper helmet (glowing lenses) for snipers. The JMS shares MCC's bind pose, so its vertices are skinned onto the MCC
# skeleton by bone name (b_ dropped) and keep MCC's animations and stock textures. The model has no room for more
# surfaces (30 of UZDoom's 32 with the gore kit's), so the arm armour joins the arms (the same texture) and the quills
# and both helmets share the helmet surface as one 2x2 atlas (HELMET_CELLS); each class's skin keeps one cell opaque
# (build_digsite.h2jackal_skin), the sniper's lenses lit by the atlas's brightmap.
PLUS = os.environ.get('HCE_H2_CHARACTERS_PLUS', 'H2 - Characters Plus Tag Pack v1.2')
PLUS_JMS = 'data/lacks/objects/characters/jackal/render/L5_jackal.JMS'
PLUS_BMP = 'data/lacks/objects/characters/jackal/'
HELMET_CELLS = {'hair': (0, 0), 'ce': (1, 0), 'sniper': (0, 1)}      # cell (column, row) in the helmet atlas
HELMET_MATS = {'jackal_teethandspikes!%': ('hair', 'hair'), 'jackal_helmet': ('helmet', 'ce'),
               'sniper_helmet': ('helmet', 'sniper'), 'sniper_helmet_illum': ('helmet', 'sniper')}
HELMET_TEX = {'hair': ('_bitmaps/head.tif', True), 'ce': ('_bitmaps/ce/jackal_helmet.tif', False),
              'sniper': ('_bitmaps/h3/helmet_hair_shield_emitter.tif', False)}   # (source, its alpha cuts out)
HELMET_ILLUM = 'bitmaps/h3/helmet_hair_shield_emitter_illum.tif'
CELL = 256


def plus_meshes(nodes, od, pid):
    """(body surfaces {shader: mesh}, the helmet atlas surface) from the Characters+ JMS, or None without the pack"""
    path = os.path.join(PLUS, PLUS_JMS)
    if not os.path.exists(path): return None
    from h2jms import read_jms
    J = read_jms(open(path, encoding='latin1').read())
    idx = {n['name']: i for i, n in enumerate(nodes)}
    bone = np.array([idx[n['name'][2:] if n['name'].startswith('b_') else n['name']] for n in J['nodes']])
    P = np.asarray(J['pos']); N = np.asarray(J['nrm']); UV = np.asarray(J['uv'], np.float64).copy()
    UV[:, 1] = 1 - UV[:, 1]
    BI = bone[np.asarray(J['bidx'])].astype(np.uint8); BW = np.clip(np.round(np.asarray(J['bw']) * 255), 0, 255).astype(np.uint8)
    T = np.asarray(J['tris']); TM = np.asarray(J['tri_mat'])
    def piece(sel, uv=None):
        v, inv = np.unique(T[sel].ravel(), return_inverse=True)
        return dict(pos=P[v], nrm=N[v], uv=(UV if uv is None else uv)[v], bidx=BI[v], bw=BW[v],
                    tris=inv.reshape(-1, 3)[:, [0, 2, 1]])
    def join(a, b):
        n0 = len(a['pos'])
        out = {k: np.concatenate([a[k], b[k]]) for k in ('pos', 'nrm', 'uv', 'bidx', 'bw')}
        out['tris'] = np.concatenate([a['tris'], b['tris'] + n0]); return out
    body, helmet = {}, None
    for mi, mat in enumerate(J['materials']):
        sel = TM == mi
        if not sel.any(): continue
        if mat['region'] == 'body' and mat['perm'] == 'standard':
            sh = mat['name'].rstrip('!%')
            if sh == 'jackal_armor_arms': sh = 'jackal_arms'             # the arm armour: on the arms' texture
            p = piece(sel); body[sh] = join(body[sh], p) if sh in body else p
        elif mat['name'] in HELMET_MATS and (mat['region'], mat['perm']) in (('hair', 'base'), ('helmet', 'standard'), ('helmet', 'sniper')):
            cell = HELMET_MATS[mat['name']][1]; cx, cy = HELMET_CELLS[cell]
            uv = UV.copy(); v = np.unique(T[sel].ravel())
            uv[v] -= np.floor(uv[v].min(0) + 1e-6)                      # (the CE helmet's UVs sit one tile over)
            uv[v] = (np.clip(uv[v], 0, 1) + [cx, cy]) / 2
            p = piece(sel, uv)
            if cell == 'hair': p['tris'] = np.concatenate([p['tris'], p['tris'][:, [0, 2, 1]]])   # quill cards: both sides
            helmet = join(helmet, p) if helmet else p
    # the atlas: the quills keep the head texture's cut-out alpha; the helmets are opaque (their alpha is a gloss mask)
    from PIL import Image
    atlas = Image.new('RGBA', (CELL * 2, CELL * 2), (0, 0, 0, 0)); bm = Image.new('RGB', atlas.size, (0, 0, 0))
    illum = np.asarray(Image.open(os.path.join(PLUS, PLUS_BMP, HELMET_ILLUM)).convert('RGB').resize((CELL, CELL), Image.LANCZOS)).astype(np.float64) / 255
    for cell, (f, cut) in HELMET_TEX.items():
        im = Image.open(os.path.join(PLUS, PLUS_BMP, f)).convert('RGBA').resize((CELL, CELL), Image.LANCZOS)
        if not cut: im.putalpha(255)
        if cell == 'sniper':
            # Halo 3's sniper helmet: a greyscale map the shader tints and shines (near black on its own), lifted to
            # gunmetal; its lenses take the self-illumination map's colour, which the brightmap then keeps lit
            a = np.asarray(im).astype(np.float64) / 255
            rgb = (0.16 + 0.84 * a[..., :3] ** 0.75) * np.array([0.92, 0.95, 1.0])
            rgb = np.clip(rgb + illum * 1.2, 0, 1)
            im = Image.fromarray((np.dstack([rgb, a[..., 3:]]) * 255).astype(np.uint8), 'RGBA')
        cx, cy = HELMET_CELLS[cell]; atlas.paste(im, (cx * CELL, cy * CELL))
    cx, cy = HELMET_CELLS['sniper']
    bm.paste(Image.fromarray((np.clip(illum.max(2) * 1.5, 0, 1) * 255).astype(np.uint8)).convert('RGB'), (cx * CELL, cy * CELL))
    atlas.save(f'{od}/{pid}_helmet_atlas.png'); bm.save(f'{od}/{pid}_helmet_atlas_bm.png')
    return body, dict(helmet, name='helmet.jackal_helmet', material=f'{pid}_helmet_atlas.png')


def extract_jackal(pid='H2Jackal'):
    m = H2Map(MAP08A, CACHE08A)
    M = render_model(m, JACKAL)
    nodes = M['nodes']; NJ = len(nodes)
    od = f'{OUT}/models/{pid}'
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    for sh, (base, mask) in SHADER_MAPS.items():
        bitmap(m, find_bitmap(m, base)).convert('RGB').save(f'{od}/{pid}_{sh}.png')
        if mask: bitmap(m, find_bitmap(m, mask)).convert('RGB').save(f'{od}/{pid}_{sh}_mask.png')
    meshes = []
    plus = plus_meshes(nodes, od, pid)
    for mm in model_meshes(m, M, KEEP):
        sh = mm['shader']
        if plus and mm['region'] == 'body':                 # Characters+: its body in place of MCC's (same order)
            nm = f'body.{sh}'
            if sh in plus[0] and not any(x['name'] == nm for x in meshes):
                meshes.append(dict(plus[0][sh], name=nm, material=f'{pid}_{sh}.png'))
            continue
        if sh == 'jackal_shield_major': sh = SHIELD_SHADER
        if sh not in SHADER_MAPS: continue
        bidx = np.clip(mm['bi'], 0, NJ - 1).astype(np.uint8)
        bw = np.clip(np.round(mm['bw'] * 255), 0, 255).astype(np.uint8)
        tris = mm['tris'][:, [0, 2, 1]]
        if sh == SHIELD_SHADER: tris = np.concatenate([tris, tris[:, [0, 2, 1]]])      # seen from both sides
        nm = f"{mm['region']}.{sh}"
        prev = [x for x in meshes if x['name'] == nm]
        if prev:
            x = prev[0]; n0 = len(x['pos'])
            for k in ('pos', 'nrm', 'uv'): x[k] = np.concatenate([x[k], mm[k]])
            x['bidx'] = np.concatenate([x['bidx'], bidx]); x['bw'] = np.concatenate([x['bw'], bw])
            x['tris'] = np.concatenate([x['tris'], tris + n0]); continue
        meshes.append(dict(name=nm, material=f'{pid}_{sh}.png', pos=mm['pos'], nrm=mm['nrm'], uv=mm['uv'],
                           bidx=bidx, bw=bw, tris=tris))
    if plus: meshes.append(plus[1])
    else: add_ce_helmet(meshes, nodes, od, pid)
    mesh_weapon = [None] * len(meshes)
    # world bind pose, markers
    W = []
    for n in nodes:
        t = np.array(n['t']); q = np.array(n['q'])
        if n['parent'] < 0: W.append((t, q))
        else:
            pt, pq = W[n['parent']]; W.append((pt + qrot(pq, t), qmul(pq, q)))
    a = m.tag('mode', JACKAL)['addr']; markers = {}
    for g in m.block(a + 0x58, 0xC):
        nm = m.sid(m.u('I', g)[0])
        for mk in m.block(g + 4, 0x24):
            markers.setdefault(nm.replace('_', ' '), []).append(dict(node=m.b[m.o(mk) + 2], t=list(m.u('3f', mk + 4)), q=list(m.u('4f', mk + 0x10))))
    mk = markers['left hand jackal'][0]                   # the gun hand (the shield rides the right forearm)
    wt, wq = W[mk['node']]; mt = np.array(mk['t']); mq = np.array(mk['q'])
    tq = qmul(wq, mq); tq /= np.linalg.norm(tq)
    beam = extract_beam_rifle(m)
    for wid in HAND_WEAPONS + [beam]:
        wd = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
        groups = {}
        for x in wd['meshes']: groups.setdefault(x['material'], []).append(x)
        for k, (mat, xs) in enumerate(groups.items()):
            base = 0; tri = []
            for x in xs: tri.append(x['tris'] + base); base += len(x['pos'])
            P = np.concatenate([x['pos'] for x in xs]); Nn = np.concatenate([x['nrm'] for x in xs]); UV = np.concatenate([x['uv'] for x in xs])
            pos = np.array([wt + qrot(wq, mt + qrot(mq, v)) for v in P])
            nrm = np.array([qrot(tq, v) for v in Nn])
            bidx = np.zeros((len(pos), 4), np.uint8); bw = np.zeros((len(pos), 4), np.uint8)
            bidx[:, 0] = mk['node']; bw[:, 0] = 255
            shutil.copy(f'{OUT}/weapons/{wid}/{mat}', f'{od}/{mat}')
            meshes.append(dict(name=f'weapon_{wid}_{k}', material=mat, pos=pos, nrm=nrm, uv=UV, bidx=bidx, bw=bw,
                               tris=np.concatenate(tri)))
            mesh_weapon.append(wid)
    assert len(meshes) <= 32, f'{len(meshes)} surfaces: UZDoom draws at most 32'
    # animations
    skel, an = h2anim.graph(m, JACKAL)
    assert skel == [n['name'] for n in nodes], 'skeleton mismatch'
    defaults = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
    byname = {x['name']: x for x in an}
    dec = {}
    def get(nm):
        if nm not in dec:
            x = byname[nm]; dec[nm] = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], defaults)
        return dec[nm]
    alist = []; info = {}
    def add(name, frames, mv, loop):
        speed = float(np.hypot(mv[:, 0], mv[:, 1]).sum() / max(1, len(frames)))
        info[name] = dict(frames=len(frames), speed=speed, yaw=float(np.degrees(mv[:, 3].sum())), loop=loop, key=-1, next=-1,
                          dx=[float(mv[:, 0].sum()), float(mv[:, 1].sum())])
        alist.append(dict(name=name, fps=30.0, loop=True, frames=frames))
    ren, ovl = anim_plan()
    for src, dst in ren.items():
        if src not in byname: print('missing anim', src); continue
        fr, mv = get(src)
        add(dst, fr, mv, byname[src]['loop'])
    ident = [(np.zeros(3), np.array([0, 0, 0, 1.0]))] * NJ
    for src, (basen, dst) in ovl.items():
        if src not in byname: print('missing overlay', src); continue
        o = byname[src]
        ofr, _ = h2anim.decode(o['data'], o['sizes'], o['frames'], o['nodes'], ident)
        b0 = get(basen)[0][0]
        frames = []
        for f in ofr:
            row = []
            for j in range(NJ):
                bt, bq, bs = b0[j]; ot, oq, _ = f[j]
                q = qmul(np.array(bq), np.array(oq)); q /= np.linalg.norm(q)
                row.append((tuple(np.array(bt) + np.array(ot)), tuple(q), bs))
            frames.append(row)
        add(dst, frames, np.zeros((len(frames), 4)), 0)
    joints = [(n['name'], n['parent'], tuple(n['t']), tuple(n['q']), (1, 1, 1)) for n in nodes]
    size = write_iqm(f'{od}/{pid}.iqm', joints, meshes, alist)
    allp = np.concatenate([x['pos'] for x, w in zip(meshes, mesh_weapon) if not w])
    # change colours per variant (bipd: primary / secondary)
    b = m.tag('bipd', JACKAL)['addr']; cc = {}
    for ci, c in enumerate(m.block(b + 0xAC, 0x10)):
        for p in m.block(c, 0x20):
            vn = m.sid(m.u('I', p + 0x1C)[0]); lo = m.u('3f', p + 4); hi = m.u('3f', p + 0x10)
            r = cc.setdefault(vn, []); r += [None] * (ci + 1 - len(r)); r[ci] = [(x + y) / 2 for x, y in zip(lo, hi)]
    sounds = extract_sounds(m, od)
    meta = dict(id=pid, tag=JACKAL, maps=['08a_deltacliffs'], joints=[j[0] for j in joints],
                bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info, materials=sorted({x['material'][:-4] for x in meshes}),
                iqm_bytes=size, meshes=[x['material'] for x in meshes], mesh_names=[x['name'] for x in meshes],
                has_multi={}, collision_height=0.6, collision_radius=0.2, markers=markers, mesh_weapon=mesh_weapon,
                change_colors=cc, shield_surface=[x['name'] for x in meshes].index(f'shield.{SHIELD_SHADER}'),
                shield_bone='shield', hand_bone='l_hand', sounds=sounds,
                helmet_cells=HELMET_CELLS if plus else {}, helmet_surface=[x['name'] for x in meshes].index('helmet.jackal_helmet'))
    json.dump(meta, open(f'{od}/{pid}.json', 'w'), indent=1)
    return meta


if __name__ == '__main__':
    meta = extract_jackal()
    print('H2 Jackal anims', len(meta['anims']), 'joints', len(meta['joints']), 'surfaces', len(meta['meshes']),
          'iqm', meta['iqm_bytes'] // 1024, 'KB', 'bounds', np.round(meta['bounds'], 2).tolist(),
          'shield surface', meta['shield_surface'], 'colours', list(meta['change_colors']), 'sounds', meta['sounds'])
