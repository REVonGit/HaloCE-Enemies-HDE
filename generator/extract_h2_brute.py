"""Halo 2 (MCC) Brutes from 08b_deltacontrol.map -> IQM + base skins/masks + JSON, plus the pop-off helmet.

Every rank (minor, major, captain, honor guard and the custom Tartarus-styled Chieftain) shares one IQM: all
armour permutations are separate surfaces, and build_digsite.py's skin hook shows/hides them per rank and bakes
each variant's fur change colours. Weapons baked into the right hand (shown one at a time per class): the CE
plasma rifle, assault rifle and shotgun, the Spiker (cmt_weapon.py spiker) and Halo 2's gravity hammer.
08b carries Tartarus's hammer stance (combat:melee / berserk:melee) on top of the regular Brute animations."""
import sys, os, json, pickle, shutil
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from h2map import H2Map, render_model, mcc_bitmap
import h2anim
from iqm import write_iqm
from extract_h2 import qmul, qrot

from hce_paths import OUT
MAP = os.environ.get('HCE_H2_MAP08B', '08b_deltacontrol.map')   # MCC halo2\\h2_maps_win64_dx11
CACHE = os.environ.get('HCE_H2_CACHE08B') or None
TEXTURES = os.environ.get('HCE_H2_TEXTURES', 'textures.dat')
BRUTE = r'objects\characters\brute\brute'
TARTARUS = r'objects\characters\brute\tartarus\brute_tartarus'
HELMET = r'objects\characters\brute\garbage\brute_helmet\brute_helmet'
WEAPONS = {'brute_shot': r'objects\weapons\support_low\brute_shot\brute_shot',
           'brute_plasma_rifle': r'objects\weapons\rifle\brute_plasma_rifle\brute_plasma_rifle',
           'gravity_hammer': r'objects\weapons\melee\gravity_hammer\gravity_hammer'}
HAND_WEAPONS = ['plasma_rifle', 'assault_rifle', 'shotgun', 'spiker']     # out/weapons/<id>/<id>.pkl (CE weapon space)
# region permutations any of our ranks wears (hlmt variants minor/major/captain/honor_guard)
KEEP = {('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'default'), ('helmet', 'honor_on'),
        ('sensors', 'default'), ('sensors', 'honor_on'), ('sh_armor', 'default'), ('sh_armor', 'honor_on'),
        ('hg_arm', 'honor_on'), ('hg_legs', 'honor_on'), ('flag', 'captain'),
        # Chieftain (custom): Tartarus's crested helmet and gold armour, the skull-trophy pauldron
        ('helmet', 'honor_off'), ('helmet', 'tartarus'), ('hg_arm', 'honor_off'), ('hg_legs', 'honor_off'), ('sh_armor', 'skull')}
# shader -> (base bitmap, change-colour mask or None, keep alpha)
SHADER_MAPS = {
    'brute': ('brute', 'brute_change_color', False),
    'brute_head': ('brute_head', 'brute_head_change_color', False),
    'brute_hair': ('brute_hair', 'brute_hair_change_color', True),
    'brute_shoulder_armor': ('brute', None, False),
    'brute_honor_armor': ('brute_honor_armor', None, False),
    'brute_honor_inset_lights': ('brute_honor_armor_illum', None, False),
    'captain_flag': ('captain_flag_mask', None, True),
    'tartarus_shoulder_armor': ('brute', None, False),
    'tartarus_mohawk': ('tartarus_mohawk', 'brute_hair_change_color', True),
    'elite_skull': ('elite_skull', None, False),
    'tartarus_eyes': (None, None, False),          # additive optics: a flat glowing amber (brightmapped)
}
BMP = r'objects\characters\brute\bitmaps' + '\\'

def anim_plan():
    """Halo 2 name -> CE-style name (base), and overlays to bake: name -> (base anim, CE-style name)"""
    ren, ovl = {}, {}
    for w, code in (('rifle', 'pr'),):
        c = f'combat:{w}:'
        ren[c + 'idle'] = f'stand {w} idle'
        for d in ('front', 'back', 'left', 'right'): ren[c + f'move_{d}'] = f'stand {w} move-{d}'
        for d in ('front', 'left', 'right'): ren[c + f'dive_{d}'] = f'stand {w} dive-{d}'
        for d in ('left', 'right'): ren[c + f'evade_{d}'] = f'stand {w} evade-{d}'; ren[c + f'turn_{d}'] = f'stand {w} turn-{d}'
        ren[c + 'throw_grenade:var1'] = f'stand {w} throw-grenade'
        ren[c + 'cheer'] = f'stand {w} celebrate'
        ren[c + 'taunt'] = f'stand {w} warn'
        ren[c + 'point'] = f'stand {w} signal-attack'
        ren[c + 'airborne'] = f'stand {w} airborne'
        ren[c + 'land_soft'] = f'stand {w} land-soft'
        ren[f'berserk:{w}:any:berserk:var1'] = f'stand {w} berserk'
        ren[c + ('any:melee:var1' if w == 'rifle' else 'bs:melee:var1')] = f'stand {w} melee'
        ovl[c + 'pr:fire_1:var1'] = (c + 'idle', 'stand rifle fire-1 pr baked')
    ovl['combat:rifle:any:fire_1'] = ('combat:rifle:idle', 'stand rifle fire-1 ar baked')
    ovl['combat:rifle:any:fire_2'] = ('combat:rifle:idle', 'stand rifle fire-1 sk baked')     # Spiker
    ovl['combat:rifle:sg:fire_1:var1'] = ('combat:rifle:idle', 'stand rifle fire-1 sg baked')
    # Tartarus's gravity hammer stance (stance 'melee'; the left hand's grip pose is applied on top)
    c = 'combat:melee:'
    ren[c + 'idle:var1'] = 'stand melee idle'
    for d in ('front', 'back', 'left', 'right'): ren[c + f'move_{d}'] = f'stand melee move-{d}'
    for d in ('left', 'right'): ren[c + f'turn_{d}'] = f'stand melee turn-{d}'
    ren[c + 'throw_grenade:var1'] = 'stand melee throw-grenade'
    ren[c + 'airborne'] = 'stand melee airborne'
    ren[c + 'land_soft'] = 'stand melee land-soft'
    for i in (1, 2, 3): ren[c + f'melee:var{i}'] = f'stand melee melee%{i}'
    ren[c + 'smash_left:var1'] = 'stand melee melee%4'
    ren[c + 'smash_right:var1'] = 'stand melee melee%5'
    ren['berserk:melee:leap_start'] = 'stand melee leap-start'
    ren['berserk:melee:leap_airborne'] = 'stand melee leap-airborne'
    ren['berserk:melee:leap_melee'] = 'stand melee leap-melee'          # upper-body replacement (legs: airborne)
    ren['berserk:melee:idle:var1'] = 'berserk hammer idle'
    ren['berserk:melee:move_front:var1'] = 'berserk hammer move-front'
    ren['berserk:melee:melee_tackle:var1'] = 'berserk hammer melee 1'
    ren['berserk:melee:melee_back:var1'] = 'berserk hammer melee 2'
    ren['combat:airborne_dead'] = 'stand airborne-dead'
    ren['combat:landing_dead'] = 'stand landing-dead'
    for d in ('front', 'back'): ren[f'h_kill:{d}:gut'] = f'h-kill {d} gut'
    for d in ('front', 'back', 'left', 'right'):
        ren[f's_kill:{d}:gut'] = f's-kill {d} gut'
        ren[f'h_ping:{d}:gut:var0' if d != 'back' else 'h_ping:back:gut:var0'] = f'h-ping {d} gut'
    for src, d in (('s_ping:front:gut:var0', 'front'), ('s_ping:back:gut:var0', 'back'), ('s_ping:left:gut:var0', 'left'),
                   ('s_ping:right:gut:var0', 'right')):
        ovl[src] = ('combat:rifle:idle', f's-ping {d} gut baked')
    # berserk: weaponless charge on all fours (played through build_pack's berserk table)
    ren['berserk:unarmed:idle:var1'] = 'berserk idle'
    ren['berserk:unarmed:move_front:var1'] = 'berserk move-front'
    for i in range(1, 6): ren[f'berserk:unarmed:melee:var{i}'] = f'berserk melee {i}'
    for i in (1, 2): ren[f'berserk:unarmed:melee_tackle:var{i}'] = f'berserk tackle {i}'
    ren['berserk:unarmed:turn_left'] = 'berserk turn-left'
    ren['berserk:unarmed:turn_right'] = 'berserk turn-right'
    return ren, ovl

def bitmap(m, name):
    return mcc_bitmap(m, name, TEXTURES) if os.path.exists(TEXTURES) else Image.new('RGBA', (16, 16), (110, 100, 90, 255))

def find_bitmap(m, short):
    names = [t['name'] for t in m.tags if t['cls'] == 'bitm' and t['name'].endswith('\\' + short)]
    pref = [n for n in names if 'characters\\brute' in n]
    return (pref or names)[0]

def model_meshes(m, M, keep=None, name_fn=None):
    """meshes for the highest-detail section of each kept (region, permutation)"""
    out = []; seen = set()
    for r in M['regions']:
        for p in r['perms']:
            if keep is not None and (r['name'], p['name']) not in keep: continue
            si = max(i for i in p['lods'] if i >= 0)
            if si in seen: continue
            seen.add(si); sec = M['sections'][si]
            for shi, tris in sec['parts']:
                sh = (M['shaders'][shi] or 'unknown').split('\\')[-1]
                used = np.unique(tris); remap = -np.ones(sec['vc'], np.int64); remap[used] = np.arange(len(used))
                out.append(dict(region=r['name'], perm=p['name'], shader=sh, pos=sec['pos'][used], nrm=sec['nrm'][used],
                                uv=sec['uv'][used], bi=sec['bi'][used], bw=sec['bw'][used], tris=remap[tris]))
    return out

def extract_weapon(m, wid):
    od = f'{OUT}/weapons/{wid}'; os.makedirs(od, exist_ok=True)
    M = render_model(m, WEAPONS[wid])
    meshes = []
    for k, mm in enumerate(model_meshes(m, M)):
        sh = m.tag('shad', [s for s in M['shaders'] if s and s.endswith('\\' + mm['shader'])][0])['addr']
        bms = []
        for pp in m.block(sh + 0x20, 0x7C)[:1]:
            for b in m.block(pp + 4, 0xC):
                t = m.u('I', b)[0]
                if t in m.byid: bms.append(m.byid[t]['name'])
        # the shader's diffuse is its third bitmap for these templates (bump, vector/camo, diffuse, ...)
        cands = [n for n in bms if not any(x in n for x in ('bump', 'default_', 'linear_corner', 'detail', 'cube_map', 'noise',
                                                              'clouds', 'gunmetal', 'metal_dirty', 'carapace', 'dark_gray'))]
        mat = f'w_{wid}_{k}.png'
        im = bitmap(m, cands[0]) if cands else Image.new('RGBA', (8, 8), (90, 80, 90, 255))
        im.convert('RGB').save(f'{od}/{mat}')
        meshes.append(dict(pos=mm['pos'], nrm=mm['nrm'], uv=mm['uv'], tris=mm['tris'][:, [0, 2, 1]], material=mat))
    pickle.dump(dict(meshes=meshes), open(f'{od}/{wid}.pkl', 'wb'))
    return meshes

def extract_hammer(m):
    """Halo 2 gravity hammer in Brute-grip space: origin and axes = its right_hand_brute marker"""
    wid = 'gravity_hammer'
    od = f'{OUT}/weapons/{wid}'; os.makedirs(od, exist_ok=True)
    M = render_model(m, WEAPONS[wid])
    a = m.tag('mode', WEAPONS[wid])['addr']; mk = None
    for g in m.block(a + 0x58, 0xC):
        if m.sid(m.u('I', g)[0]) == 'right_hand_brute':
            x = m.block(g + 4, 0x24)[0]; mk = (np.array(m.u('3f', x + 4)), np.array(m.u('4f', x + 0x10)))
    gt, gq = mk; gi = np.array([-gq[0], -gq[1], -gq[2], gq[3]])
    base = bitmap(m, find_bitmap(m, 'gravity_hammer')).convert('RGB')
    illum = bitmap(m, find_bitmap(m, 'gravity_hammer_illum')).convert('RGB').resize(base.size)
    b = np.asarray(base).astype(np.float32); il = np.asarray(illum).astype(np.float32)
    glow = il.max(2, keepdims=True) / 255.0
    tex = np.clip(b * (1 - glow) + glow * np.array([120, 200, 255]) * 1.2, 0, 255).astype(np.uint8)
    Image.fromarray(tex).save(f'{od}/w_{wid}_0.png')
    out = []
    for mm in model_meshes(m, M):
        pos = np.array([qrot(gi, v - gt) for v in mm['pos']]); nrm = np.array([qrot(gi, v) for v in mm['nrm']])
        out.append(dict(material=f'w_{wid}_0.png', pos=pos, nrm=nrm, uv=mm['uv'], tris=mm['tris'][:, [0, 2, 1]]))
    pickle.dump(dict(id=wid, meshes=out), open(f'{od}/{wid}.pkl', 'wb'))
    return out

def extract_helmet(m, pid='BruteHelmet'):
    od = f'{OUT}/models/{pid}'; os.makedirs(od, exist_ok=True)
    M = render_model(m, HELMET)
    mm = model_meshes(m, M)[0]
    bitmap(m, BMP + 'brute').convert('RGB').save(f'{od}/{pid}_0.png')
    n = len(mm['pos'])
    bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8); bw[:, 0] = 255
    mesh = dict(name='helmet', material=f'{pid}_0.png', pos=mm['pos'] - mm['pos'].mean(0), nrm=mm['nrm'], uv=mm['uv'],
                bidx=bidx, bw=bw, tris=mm['tris'][:, [0, 2, 1]])
    write_iqm(f'{od}/{pid}.iqm', [('root', -1, (0, 0, 0), (0, 0, 0, 1), (1, 1, 1))], [mesh],
              [dict(name='idle', fps=30.0, loop=True, frames=[[((0, 0, 0), (0, 0, 0, 1), (1, 1, 1))]])])

def extract_brute(pid='Brute'):
    m = H2Map(MAP, CACHE)
    M = render_model(m, BRUTE)
    nodes = M['nodes']; NJ = len(nodes)
    od = f'{OUT}/models/{pid}'; os.makedirs(od, exist_ok=True)
    # base maps and change-colour masks (baked per rank by the pack builder)
    for sh, (base, mask, alpha) in SHADER_MAPS.items():
        if base is None:
            Image.new('RGB', (8, 8), (255, 190, 90)).save(f'{od}/{pid}_{sh}.png'); continue
        im = bitmap(m, find_bitmap(m, base))
        (im if alpha else im.convert('RGB')).save(f'{od}/{pid}_{sh}.png')
        if mask: bitmap(m, find_bitmap(m, mask)).convert('RGB').save(f'{od}/{pid}_{sh}_mask.png')
    meshes = []; parts = []
    for mm in model_meshes(m, M, KEEP):
        if mm['shader'] not in SHADER_MAPS: continue
        bidx = np.clip(mm['bi'], 0, NJ - 1).astype(np.uint8)
        bw = np.clip(np.round(mm['bw'] * 255), 0, 255).astype(np.uint8)
        tris = mm['tris'][:, [0, 2, 1]]
        if mm['shader'] in ('brute_hair', 'captain_flag', 'tartarus_mohawk'): tris = np.concatenate([tris, tris[:, [0, 2, 1]]])
        nm = f"{mm['region']}.{mm['perm']}.{mm['shader']}"
        prev = [x for x in meshes if x['name'] == nm]
        if prev:                                   # one surface per piece (UZDoom: 32 surfaces per model)
            x = prev[0]; n0 = len(x['pos'])
            for k in ('pos', 'nrm', 'uv', 'bidx', 'bw'): x[k] = np.concatenate([x[k], {'bidx': bidx, 'bw': bw}.get(k, mm.get(k))])
            x['tris'] = np.concatenate([x['tris'], tris + n0]); continue
        meshes.append(dict(name=f"{mm['region']}.{mm['perm']}.{mm['shader']}", material=f"{pid}_{mm['shader']}.png",
                           pos=mm['pos'], nrm=mm['nrm'], uv=mm['uv'], bidx=bidx, bw=bw, tris=tris))
    # world bind + weapons in the right hand
    W = []
    for n in nodes:
        t = np.array(n['t']); q = np.array(n['q'])
        if n['parent'] < 0: W.append((t, q))
        else:
            pt, pq = W[n['parent']]; W.append((pt + qrot(pq, t), qmul(pq, q)))
    a = m.tag('mode', BRUTE)['addr']; markers = {}
    for g in m.block(a + 0x58, 0xC):
        nm = m.sid(m.u('I', g)[0])
        for mk in m.block(g + 4, 0x24):
            markers.setdefault(nm.replace('_', ' '), []).append(dict(node=m.b[m.o(mk) + 2], t=list(m.u('3f', mk + 4)), q=list(m.u('4f', mk + 0x10))))
    mesh_weapon = [None] * len(meshes)
    mk = markers['right hand'][0]
    wt, wq = W[mk['node']]; mt = np.array(mk['t']); mq = np.array(mk['q'])
    tq = qmul(wq, mq); tq /= np.linalg.norm(tq)
    def by_material(ms):
        g = {}
        for x in ms: g.setdefault(x['material'], []).append(x)
        out = []
        for mat, xs in g.items():
            base = 0; tris = []
            for x in xs: tris.append(x['tris'] + base); base += len(x['pos'])
            out.append(dict(material=mat, tris=np.concatenate(tris), **{k: np.concatenate([x[k] for x in xs]) for k in ('pos', 'nrm', 'uv')}))
        return out
    def qinv(q): return np.array([-q[0], -q[1], -q[2], q[3]])
    wsets = []
    for wid in HAND_WEAPONS:
        wd = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
        wsets.append((wid, by_material(wd['meshes'])))
    # gravity hammer: Halo 2 aligns the weapon's right_hand_brute marker with the Brute's hand marker
    hm_ = extract_hammer(m)
    wsets.append(('gravity_hammer', hm_))
    for wid, wms in wsets:
        for k, wm in enumerate(wms):
            pos = np.array([wt + qrot(wq, mt + qrot(mq, v)) for v in wm['pos']])
            nrm = np.array([qrot(tq, v) for v in wm['nrm']])
            bidx = np.zeros((len(pos), 4), np.uint8); bw = np.zeros((len(pos), 4), np.uint8)
            bidx[:, 0] = mk['node']; bw[:, 0] = 255
            shutil.copy(f'{OUT}/weapons/{wid}/{wm["material"]}', f'{od}/{wm["material"]}')
            meshes.append(dict(name=f'weapon_{wid}_{k}', material=wm['material'], pos=pos, nrm=nrm, uv=wm['uv'],
                               bidx=bidx, bw=bw, tris=wm['tris']))
            mesh_weapon.append(wid)
    assert len(meshes) <= 32, f'{len(meshes)} surfaces: UZDoom draws at most 32'
    extract_helmet(m)
    # animations
    skel, an = h2anim.graph(m, BRUTE)
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
    # left-hand grip (replacement) for the hammer stance: the nodes it animates override the base pose
    g = byname['combat:melee:grip']
    nanq = [(np.full(3, np.nan), np.full(4, np.nan))] * NJ
    gfr, _ = h2anim.decode(g['data'], g['sizes'], g['frames'], g['nodes'], nanq)
    grip = {j: gfr[0][j] for j in range(NJ) if not np.isnan(np.array(gfr[0][j][1], float)).any()}
    for src, dst in ren.items():
        if src not in byname: print('missing anim', src); continue
        if src == 'berserk:melee:leap_melee':            # replacement: unanimated nodes keep the airborne pose
            la = get('berserk:melee:leap_airborne')[0][-1]
            x = byname[src]
            fr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], [(np.array(t), np.array(q)) for t, q, _ in la])
        else:
            fr, mv = get(src)
        if 'melee' in src.split(':')[1:2]:
            fr = [[(row[j][0], tuple(grip[j][1]), row[j][2]) if j in grip else row[j] for j in range(NJ)] for row in fr]
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
    path = f'{od}/{pid}.iqm'
    size = write_iqm(path, joints, meshes, alist)
    if os.environ.get('HCE_DEBUG_PKL'): pickle.dump((joints, meshes, alist, mesh_weapon), open(os.environ['HCE_DEBUG_PKL'], 'wb'))
    allp = np.concatenate([x['pos'] for x, w in zip(meshes, mesh_weapon) if not w])
    # change colours per hlmt variant (bipd: primary = fur/skin, secondary = hair)
    b = m.tag('bipd', BRUTE)['addr']; cc = {}
    for ci, c in enumerate(m.block(b + 0xAC, 0x10)):
        for p in m.block(c, 0x20):
            vn = m.sid(m.u('I', p + 0x1C)[0]); lo = m.u('3f', p + 4); hi = m.u('3f', p + 0x10)
            cc.setdefault(vn, [None, None])[ci] = [(x + y) / 2 for x, y in zip(lo, hi)]
    tb = m.tag('bipd', TARTARUS)['addr']                   # the Chieftain wears Tartarus's grey fur / white crest
    for ci, c in enumerate(m.block(tb + 0xAC, 0x10)):
        for p in m.block(c, 0x20):
            lo = m.u('3f', p + 4); hi = m.u('3f', p + 0x10)
            cc.setdefault('tartarus', [None, None])[ci] = [(x + y) / 2 for x, y in zip(lo, hi)]
    meta = dict(id=pid, tag=BRUTE, maps=['08b_deltacontrol'], joints=[j[0] for j in joints],
                bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info, materials=sorted({x['material'][:-4] for x in meshes}),
                iqm_bytes=size, meshes=[x['material'] for x in meshes], mesh_names=[x['name'] for x in meshes],
                has_multi={}, collision_height=0.95, collision_radius=0.32, markers=markers, mesh_weapon=mesh_weapon,
                change_colors=cc)
    json.dump(meta, open(f'{od}/{pid}.json', 'w'), indent=1)
    return meta

if __name__ == '__main__':
    meta = extract_brute()
    print('Brute anims', len(meta['anims']), 'joints', len(meta['joints']), 'surfaces', len(meta['meshes']),
          'iqm', meta['iqm_bytes'] // 1024, 'KB', 'bounds', np.round(meta['bounds'], 2).tolist())
    print('change colours', list(meta['change_colors']))

# ---------------------------------------------------------------- sounds
SOUNDS_DIR = os.environ.get('HCE_H2_SOUNDS', '.')   # folder with sounds_en.dat and sounds_neutral.dat
VOICES = {'Brute_Bloodthirsty': 'sound\\dialog\\combat\\brute_bloodthirsty\\', 'Brute_Cruel': 'sound\\dialog\\combat\\brute_cruel\\'}
FX = {'thump': r'sound\characters\brute\brute_thump', 'melee_moves': r'sound\characters\brute\brute_melee_moves',
      'step_walk': r'sound\characters\footsteps\brute\grtcement\walk', 'step_run': r'sound\characters\footsteps\brute\grtcement\run',
      'bodyfall': r'sound\characters\bodyfalls\brute_bodyfalls\generic_non_havok',
      'shot_fire': r'sound\weapons\brute_shot\brute_shot_fire', 'shot_explode': r'sound\weapons\brute_shot\brute_round_explode',
      'shot_bounce': r'sound\weapons\brute_shot\brute_shot_bounce'}

def tag_oggs(m, name, files):
    import h2opus
    from h2map import sound_chunks
    out = []
    for pi, (pn, codec, locs) in enumerate(sound_chunks(m, name)):
        ch = [l for l in locs if l[0] == 0][0][1]
        src = 'neutral' if any(fl & 0x2000 for _, _, fl, _, _ in ch) else 'en'
        if src not in files: return None
        f = files[src]; pk = []
        for o, cs, fl, us, ri in ch:
            f.seek(o); pk += h2opus.packets(f.read(cs & 0xFFFF), strict=True)
        out.append(h2opus.to_ogg(pk, channels=2 if codec[1] == 1 else 1))
    return out

MAP08A = os.environ.get('HCE_H2_MAP08', '08a_deltacliffs.map')
CACHE08A = os.environ.get('HCE_H2_CACHE08') or None

def extract_brute_sounds(pid='Brute'):
    """Brute dialogue + effects from 08a (its Brute dialogue set is fuller than 08b's)"""
    maps = [H2Map(MAP08A, CACHE08A)]
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    od = f'{OUT}/sounds/{pid}'
    if os.path.exists(od): shutil.rmtree(od)
    idx = {}
    def save(group, leaf, oggs):
        os.makedirs(f'{od}/{group}', exist_ok=True)
        for i, data in enumerate(oggs):
            fn = f'{group}/{leaf}_{i:02d}.ogg'
            open(f'{od}/{fn}', 'wb').write(data); idx.setdefault(group, {}).setdefault(leaf, []).append(fn)
    done = set()
    for m in maps:
        names = {t['name'] for t in m.tags if t['cls'] == 'snd!'}
        for voice, prefix in VOICES.items():
            for t in m.tags:
                if t['cls'] != 'snd!' or not t['name'].startswith(prefix): continue
                leaf = t['name'].split('\\')[-1]
                if t['name'] in done: continue
                done.add(t['name'])
                oggs = tag_oggs(m, t['name'], files)
                if oggs: save(voice, leaf, oggs)
        for leaf, name in FX.items():
            if leaf in idx.get('fx', {}) or name not in names: continue
            oggs = tag_oggs(m, name, files)
            if oggs: save('fx', leaf, oggs)
    json.dump(idx, open(f'{od}/index.json', 'w'), indent=1)
    return idx
