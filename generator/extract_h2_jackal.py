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
    return mcc_bitmap(m, name, TEXTURES) if os.path.exists(TEXTURES) else Image.new('RGBA', (16, 16), (110, 100, 90, 255))


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
    files = {k: open(os.path.join(SOUNDS_DIR, fn), 'rb') for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat'))
             if os.path.exists(os.path.join(SOUNDS_DIR, fn))}
    out = []
    os.makedirs(f'{od}/sounds', exist_ok=True)
    for i, data in enumerate(tag_oggs(m, r'sound\characters\jackal\jackal_shield_death', files) or []):
        fn = f'sounds/shield_pop_{i}.ogg'; open(f'{od}/{fn}', 'wb').write(data); out.append(fn)
    return out


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
    for mm in model_meshes(m, M, KEEP):
        sh = mm['shader']
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
                shield_bone='shield', hand_bone='l_hand', sounds=sounds)
    json.dump(meta, open(f'{od}/{pid}.json', 'w'), indent=1)
    return meta


if __name__ == '__main__':
    meta = extract_jackal()
    print('H2 Jackal anims', len(meta['anims']), 'joints', len(meta['joints']), 'surfaces', len(meta['meshes']),
          'iqm', meta['iqm_bytes'] // 1024, 'KB', 'bounds', np.round(meta['bounds'], 2).tolist(),
          'shield surface', meta['shield_surface'], 'colours', list(meta['change_colors']), 'sounds', meta['sounds'])
