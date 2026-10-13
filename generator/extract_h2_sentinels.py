"""Halo 2's Sentinels from 06b_floodzone.map (Quarantine Zone, MCC) -> the Sentinels pack.

    HCE_H2_MAP06B=/path/to/06b_floodzone.map HCE_H2_TEXTURES=/path/to/textures.dat python3 extract_h2_sentinels.py

Run after extract_chars.py (it replaces the Halo CE Sentinel's model) and before build_pack.py.

* The Aggressor (objects\\characters\\sentinel_aggressor): Halo 2's remake of the CE Sentinel (the same size and shape)
  -> $HCE_OUT/models/Sentinel, in place of the CE model (kept as models/Sentinel_CE), so the CE Sentinel classes keep
  their names and DoomEdNums and wear it. Its base permutations (gun, head, hull, arms) on one surface, its shield
  bubble on another (the shielded ranks show it while the shield holds); its idles and flinches renamed onto the
  pack's names (the 'fixed' stance), and a tumble and a landing made from its idle for the death fall (Halo 2's
  Sentinels have no death animations: they break apart). Its two change colours (minor: steel blue, captain: gold)
  go in the json for the rank skins (build_pack.h2sentinel_skin).
* The Enforcer (objects\\characters\\sentinel_enforcer) -> $HCE_OUT/models/SentinelEnforcer: hull, arms, thrusters,
  rocket pods, shield generators and eye (base permutations), its two energy shields (the left_shield / right_shield
  objects, placed on their generators' markers, each on its own surface so a drained one can be hidden), its idles,
  melee (the grapple) and flinches, and the same made-up death fall.
* The Constructor (objects\\characters\\sentinel_constructor) -> $HCE_OUT/models/SentinelConstructor: Halo 2's little
  builder drone, in the Aggressor's texture, with its idle, flinches and its own falling death (the Lost Souls' stand-in).
* The characters' vitality (normal body and shield) into each json's 'ranks'.

Textures: MCC keeps them in textures.dat (HCE_H2_TEXTURES). With a copy that stops short of a model's main textures that
model is left out (the Halo CE Sentinel kept, no Enforcer); HCE_H2_SENTINELS_FORCE=1 builds it anyway with plain grey in
their place (listed in the json's 'missing_textures').
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, shutil, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from h2map import H2Map, render_model, mcc_bitmap, shader_bitmaps
import h2anim
from iqm import write_iqm
from extract_h2 import qmul, qrot
from extract_h2_brute import model_meshes

from hce_paths import OUT
MAP06B = os.environ.get('HCE_H2_MAP06B', '06b_floodzone.map')
CACHE06B = os.environ.get('HCE_H2_CACHE06B') or None
TEXTURES = os.environ.get('HCE_H2_TEXTURES', 'textures.dat')
AGG = r'objects\characters\sentinel_aggressor\sentinel_aggressor'
ENF = r'objects\characters\sentinel_enforcer\sentinel_enforcer'
CON = r'objects\characters\sentinel_constructor\sentinel_constructor'
SHIELDS = {'left': (r'objects\characters\sentinel_enforcer\left_shield\left_shield', 'left_shield_gen'),
           'right': (r'objects\characters\sentinel_enforcer\right_shield\right_shield', 'right_shield_gen')}
CHARS = {'sentinel': r'objects\characters\sentinel_aggressor\ai\sentinel_aggressor',
         'major': r'objects\characters\sentinel_aggressor\ai\sentinel_aggressor_major',
         'eliminator': r'objects\characters\sentinel_aggressor\ai\sentinel_aggressor_eliminator',
         'enforcer': r'objects\characters\sentinel_enforcer\ai\sentinel_enforcer'}
missing = []


def texture(m, name, size=None):
    """an MCC bitmap (RGBA) or, when textures.dat doesn't reach it, plain grey"""
    try:
        im = mcc_bitmap(m, name, TEXTURES)
    except Exception as e:
        if e.__class__.__name__ == 'MissingPart': print('  ', e)      # a piece of a split textures.dat to fetch
        missing.append(name); im = Image.new('RGBA', (64, 64), (128, 128, 132, 255))
    return im.resize(size, Image.LANCZOS) if size and im.size != size else im


def world(nodes):
    W = []
    for n in nodes:
        t = np.array(n['t']); q = np.array(n['q'])
        if n['parent'] < 0: W.append((t, q))
        else:
            pt, pq = W[n['parent']]; W.append((pt + qrot(pq, t), qmul(pq, q)))
    return W


def markers(m, name, nodes):
    a = m.tag('mode', name)['addr']; out = {}
    for g in m.block(a + 0x58, 0xC):
        nm = m.sid(m.u('I', g)[0])
        for mk in m.block(g + 4, 0x24):
            out.setdefault(nm, []).append(dict(node=m.b[m.o(mk) + 2], t=list(m.u('3f', mk + 4)), q=list(m.u('4f', mk + 0x10))))
    return out


def vitality(m):
    """{rank: (normal body, normal shield)} from the character tags' vitality blocks"""
    out = {}
    for r, n in CHARS.items():
        (p,) = m.block(m.tag('char', n)['addr'] + 0x3C, 0x70)
        out[r] = [round(x, 1) for x in m.u('2f', p + 4)]
    return out


def change_colours(m, bipd):
    b = m.tag('bipd', bipd)['addr']; cc = {}
    for ci, c in enumerate(m.block(b + 0xAC, 0x10)):
        for p in m.block(c, 0x20):
            vn = m.sid(m.u('I', p + 0x1C)[0]); lo = m.u('3f', p + 4); hi = m.u('3f', p + 0x10)
            r = cc.setdefault(vn, []); r += [None] * (ci + 1 - len(r)); r[ci] = [round((x + y) / 2, 3) for x, y in zip(lo, hi)]
    return cc


def surface(name, material, parts):
    """meshes (pos, nrm, uv, bi, bw, tris) merged into one IQM surface"""
    pos, nrm, uv, bi, bw, tris, n0 = [], [], [], [], [], [], 0
    for x in parts:
        pos.append(x['pos']); nrm.append(x['nrm']); uv.append(x['uv'])
        bi.append(np.clip(x['bi'], 0, 255).astype(np.uint8)); bw.append(np.clip(np.round(x['bw'] * 255), 0, 255).astype(np.uint8))
        tris.append(x['tris'][:, [0, 2, 1]] + n0); n0 += len(x['pos'])
    return dict(name=name, material=material, pos=np.concatenate(pos), nrm=np.concatenate(nrm), uv=np.concatenate(uv),
                bidx=np.concatenate(bi), bw=np.concatenate(bw), tris=np.concatenate(tris))


def death_anims(idle_frame, root, n):
    """Halo 2's Sentinels have no death animations: a tumble (the idle pose rolling and pitching over, looped while it
    falls) and the landing (on its side)"""
    import math
    def turned(deg_roll, deg_pitch):
        qr = np.array([math.sin(math.radians(deg_roll) / 2), 0, 0, math.cos(math.radians(deg_roll) / 2)])
        qp = np.array([0, math.sin(math.radians(deg_pitch) / 2), 0, math.cos(math.radians(deg_pitch) / 2)])
        rot = qmul(qp, qr)
        row = list(idle_frame)
        t, q, s = row[root]
        row[root] = (tuple(qrot(rot, np.array(t))), tuple(qmul(rot, np.array(q)) / np.linalg.norm(qmul(rot, np.array(q)))), s)
        return row
    fall = [turned(12 * k, 7 * k) for k in range(30)]
    land = [turned(80, 20)] * 2
    return fall, land


def anims_of(m, name, nodes, plan, base):
    """{pack name: (frames, movement, loop)} for plan {Halo 2 name: pack name}. Halo 2's overlays (type 1: the
    Aggressor's flinches) are laid over the base animation's first frame, and its partial replacements (type 2: the
    Enforcer's grapple) keep that frame's pose on the bones they leave alone"""
    skel, an = h2anim.graph(m, name)
    assert skel == [n['name'] for n in nodes], 'skeleton mismatch'
    defaults = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
    byname = {x['name']: x for x in an}
    b = byname[base]
    b0 = h2anim.decode(b['data'], b['sizes'], b['frames'], b['nodes'], defaults)[0][0]
    pose = [(np.array(t), np.array(q)) for t, q, _ in b0]
    ident = [(np.zeros(3), np.array([0, 0, 0, 1.0]))] * len(nodes)
    out = {}
    for src, dst in plan.items():
        if src not in byname: print('  missing anim', src); continue
        x = byname[src]
        if x['type'] == 1:
            ofr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], ident)
            fr = []
            for f in ofr:
                row = []
                for j in range(len(nodes)):
                    bt, bq, bs = b0[j]; ot, oq, _ = f[j]
                    q = qmul(np.array(bq), np.array(oq)); q /= np.linalg.norm(q)
                    row.append((tuple(np.array(bt) + np.array(ot)), tuple(q), bs))
                fr.append(row)
            mv = np.zeros((len(fr), 4))
        else:
            fr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], pose if x['type'] == 2 else defaults)
        out[dst] = (fr, mv, x['loop'])
    return out


def write(pid, tag, nodes, meshes, anims, extra, od):
    joints = [(n['name'], n['parent'], tuple(n['t']), tuple(n['q']), (1, 1, 1)) for n in nodes]
    alist, info = [], {}
    for name, (frames, mv, loop) in anims.items():
        speed = float(np.hypot(mv[:, 0], mv[:, 1]).sum() / max(1, len(frames)))
        info[name] = dict(frames=len(frames), speed=speed, yaw=float(np.degrees(mv[:, 3].sum())), loop=loop, key=-1, next=-1,
                          dx=[float(mv[:, 0].sum()), float(mv[:, 1].sum())])
        alist.append(dict(name=name, fps=30.0, loop=True, frames=frames))
    size = write_iqm(f'{od}/{pid}.iqm', joints, meshes, alist)
    allp = np.concatenate([x['pos'] for x in meshes])
    meta = dict(id=pid, tag=tag, maps=['06b_floodzone'], joints=[j[0] for j in joints],
                bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info,
                materials=sorted({x['material'][:-4] for x in meshes}), iqm_bytes=size, meshes=[x['material'] for x in meshes],
                mesh_names=[x['name'] for x in meshes], has_multi={}, mesh_weapon=[None] * len(meshes))
    meta.update(extra)
    json.dump(meta, open(f'{od}/{pid}.json', 'w'), indent=1)
    return meta


def aggressor(m, vit):
    pid = 'Sentinel'; od = f'{OUT}/models/{pid}'
    if os.path.exists(od) and not os.path.exists(f'{OUT}/models/Sentinel_CE'):
        shutil.copytree(od, f'{OUT}/models/Sentinel_CE')            # the Halo CE model, kept
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    M = render_model(m, AGG); nodes = M['nodes']
    keep = {(r['name'], 'base') for r in M['regions']}
    mm = model_meshes(m, M, keep)
    body = [x for x in mm if x['region'] != 'shield']; shield = [x for x in mm if x['region'] == 'shield']
    bmp = 'objects\\characters\\sentinel_aggressor\\bitmaps\\'
    base = texture(m, bmp + 'sentinel_aggressor').convert('RGB')
    base.save(f'{od}/{pid}_body.png')
    cc = texture(m, bmp + 'sentinel_aggressor_change_color', base.size).convert('RGB')
    # the multipurpose map build_pack.bake_skin / add_shine read: red the reflection mask (the metal), blue the change colour
    c = np.asarray(cc).astype(np.float32) / 255
    mask = c.max(2)
    multi = np.dstack([np.full_like(mask, 0.7), np.zeros_like(mask), mask, np.ones_like(mask)])
    Image.fromarray((multi * 255).astype(np.uint8), 'RGBA').save(f'{od}/{pid}_body_multi.png')
    sb = shader_bitmaps(m, M, 'sentinel_aggressor_shield')
    (texture(m, sb[0]) if sb else Image.new('RGB', (64, 64), (90, 160, 255))).convert('RGB').save(f'{od}/{pid}_shield.png')
    meshes = [surface('body.sentinel_aggressor', f'{pid}_body.png', body)]
    if shield: meshes.append(surface('shield.sentinel_aggressor_shield', f'{pid}_shield.png', shield))
    plan = {'combat:any:any:idle': 'stand fixed idle', 'crouch:idle': 'crouch fixed idle'}
    for d in ('front', 'back', 'left', 'right'):
        for k in (0, 1): plan[f'h_ping:{d}:gut:var{k}'] = f's-ping {d} gut%{k + 1} baked'
    A = anims_of(m, AGG, nodes, plan, 'combat:any:any:idle')
    A['alert fixed idle'] = A['stand fixed idle']
    fall, land = death_anims(A['stand fixed idle'][0][0], 0, len(nodes))
    A['stand airborne-dead'] = (fall, np.zeros((len(fall), 4)), 1); A['stand landing-dead'] = (land, np.zeros((len(land), 4)), 0)
    meta = write(pid, AGG, nodes, meshes, A, dict(
        collision_height=0.0, collision_radius=0.38, markers={k.replace('_', ' '): v for k, v in markers(m, AGG, nodes).items()},
        change_colors=change_colours(m, AGG), ranks={r: vit[r] for r in ('sentinel', 'major', 'eliminator')},
        shield_surface=len(meshes) - 1 if shield else None, has_multi={f'{pid}_body': True}, source='h2'), od)
    print(f'  Sentinel (Aggressor): {sum(len(x["tris"]) for x in meshes)} tris, surfaces {meta["mesh_names"]}, anims {sorted(A)}')
    return meta


def enforcer(m, vit):
    pid = 'SentinelEnforcer'; od = f'{OUT}/models/{pid}'
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    M = render_model(m, ENF); nodes = M['nodes']
    keep = {(r['name'], 'base') for r in M['regions']}
    mm = model_meshes(m, M, keep)
    bmp = 'objects\\characters\\sentinel_enforcer\\bitmaps\\'
    texture(m, bmp + 'sentinel_enforcer').convert('RGB').save(f'{od}/{pid}_body.png')
    groups = {}
    for x in mm:
        k = 'eye' if 'eye' in x['shader'] else 'hover' if 'hover' in x['shader'] else 'body'
        groups.setdefault(k, []).append(x)
    meshes = [surface('body.sentinel_enforcer', f'{pid}_body.png', groups['body'])]
    for k in ('hover', 'eye'):
        if k not in groups: continue
        # the hover jets and the eyes paint the Enforcer's own texture (their shaders make it glow): its colour map, not
        # the first bitmap the shader names (a bump or reflection map)
        sb = [b for b in shader_bitmaps(m, M, groups[k][0]['shader']) if b == bmp + 'sentinel_enforcer'] or \
             [b for b in shader_bitmaps(m, M, groups[k][0]['shader']) if not b.endswith('_bump') and 'reflection' not in b and 'default' not in b]
        im = texture(m, sb[0]).convert('RGB') if sb else Image.new('RGB', (32, 32), (120, 200, 255))
        im.save(f'{od}/{pid}_{k}.png')
        meshes.append(surface(f'{k}.sentinel_enforcer_{k}', f'{pid}_{k}.png', groups[k]))
    # the two energy shields: their own models, on their generators' markers (rigid on the marker's node)
    W = world(nodes); mk = markers(m, ENF, nodes)
    snoise = texture(m, bmp + 'energy_shield_noise').convert('RGB'); snoise.save(f'{od}/{pid}_shield.png')
    shield_surfaces = {}
    for side, (sname, mname) in SHIELDS.items():
        S = render_model(m, sname)
        parts = [x for x in model_meshes(m, S) if x['perm'] == 'active']
        g = mk[mname][0]; wt, wq = W[g['node']]; mt = np.array(g['t']); mq = np.array(g['q'])
        tq = qmul(wq, mq); tq /= np.linalg.norm(tq)
        for x in parts:
            x['pos'] = np.array([wt + qrot(wq, mt + qrot(mq, v)) for v in x['pos']])
            x['nrm'] = np.array([qrot(tq, v) for v in x['nrm']])
            x['bi'] = np.zeros((len(x['pos']), 4), np.int32); x['bi'][:, 0] = g['node']
            x['bw'] = np.zeros((len(x['pos']), 4)); x['bw'][:, 0] = 1
            x['tris'] = np.concatenate([x['tris'], x['tris'][:, [0, 2, 1]]])       # seen from both sides
        shield_surfaces[side] = len(meshes)
        meshes.append(surface(f'shield_{side}.energy_shield', f'{pid}_shield.png', parts))
    plan = {'combat:any:any:idle:var0': 'stand fixed idle%0', 'combat:any:any:idle:var1': 'stand fixed idle%1',
            'crouch:any:any:idle': 'crouch fixed idle', 'combat:any:any:melee': 'stand fixed melee'}
    for d, ks in (('front', (0,)), ('back', (0, 1)), ('left', (0,)), ('right', (0,))):
        for k in ks: plan[f'h_ping:{d}:gut:var{k}'] = f's-ping {d} gut%{k + 1} baked'
    A = anims_of(m, ENF, nodes, plan, 'combat:any:any:idle:var0')
    A['alert fixed idle'] = A['stand fixed idle%0']
    fall, land = death_anims(A['stand fixed idle%0'][0][0], 0, len(nodes))
    A['stand airborne-dead'] = (fall, np.zeros((len(fall), 4)), 1); A['stand landing-dead'] = (land, np.zeros((len(land), 4)), 0)
    mks = {k.replace('_', ' '): v for k, v in mk.items()}
    meta = write(pid, ENF, nodes, meshes, A, dict(
        collision_height=0.0, collision_radius=0.9, markers=mks, ranks={'enforcer': vit['enforcer']},
        shield_surfaces=shield_surfaces, eye_surface=[x['name'] for x in meshes].index('eye.sentinel_enforcer_eye') if 'eye' in groups else None,
        rocket_ports=[[float(c) for c in W[g['node']][0] + qrot(W[g['node']][1], np.array(g['t']))] for g in mk.get('rocket_trigger', [])][:8],
        needler_ports=[[float(c) for c in W[g['node']][0] + qrot(W[g['node']][1], np.array(g['t']))] for g in mk.get('needler_trigger', [])][:2],
        source='h2'), od)
    print(f'  Enforcer: {sum(len(x["tris"]) for x in meshes)} tris, surfaces {meta["mesh_names"]}, anims {sorted(A)}')
    return meta


def constructor(m):
    """the Constructor: Halo 2's little builder drone (the Aggressor's texture), its idle, flinches and falling death"""
    pid = 'SentinelConstructor'; od = f'{OUT}/models/{pid}'
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    M = render_model(m, CON); nodes = M['nodes']
    texture(m, 'objects\\characters\\sentinel_aggressor\\bitmaps\\sentinel_aggressor').convert('RGB').save(f'{od}/{pid}_body.png')
    meshes = [surface('body.sentinel_constructor', f'{pid}_body.png', model_meshes(m, M))]
    plan = {'combat:any:any:idle': 'stand fixed idle', 'crouch:any:any:idle': 'crouch fixed idle',
            'h_ping:front:gut:var0': 's-ping front gut%1 baked', 'h_ping:back:gut:var0': 's-ping back gut%1 baked',
            'combat:airborne_dead': 'stand airborne-dead'}
    A = anims_of(m, CON, nodes, plan, 'combat:any:any:idle')
    A['alert fixed idle'] = A['stand fixed idle']
    fall, land = death_anims(A['stand fixed idle'][0][0], 0, len(nodes))
    A['stand landing-dead'] = (land, np.zeros((len(land), 4)), 0)
    meta = write(pid, CON, nodes, meshes, A, dict(collision_height=0.0, collision_radius=0.1,
                 markers={k.replace('_', ' '): v for k, v in markers(m, CON, nodes).items()}, source='h2'), od)
    print(f'  Constructor: {sum(len(x["tris"]) for x in meshes)} tris, anims {sorted(A)}')
    return meta


NEEDS = {'Sentinel': ['objects\\characters\\sentinel_aggressor\\bitmaps\\sentinel_aggressor',
                     'objects\\characters\\sentinel_aggressor\\bitmaps\\sentinel_aggressor_change_color'],
         'SentinelEnforcer': ['objects\\characters\\sentinel_enforcer\\bitmaps\\sentinel_enforcer'],
         'SentinelConstructor': ['objects\\characters\\sentinel_aggressor\\bitmaps\\sentinel_aggressor']}
FORCE = os.environ.get('HCE_H2_SENTINELS_FORCE') == '1'      # build them even with grey stand-in textures (testing)


def reachable(m, names):
    for n in names:
        try: mcc_bitmap(m, n, TEXTURES)
        except Exception as e:
            if e.__class__.__name__ == 'MissingPart': print('  ', e)
            return False
    return True


def main():
    if not os.path.exists(MAP06B): print('extract_h2_sentinels: no', MAP06B); return
    m = H2Map(MAP06B, CACHE06B)
    vit = vitality(m)
    print('  vitality (normal body, shield):', vit)
    # without its textures (a textures.dat that stops short of them) a model is left out, unless forced: the Halo CE
    # Sentinel stays as it was, and there is no Enforcer
    ok = {pid: FORCE or reachable(m, n) for pid, n in NEEDS.items()}
    done = []
    if ok['Sentinel']: done.append((aggressor(m, vit), 'Sentinel'))
    else:
        print('  Sentinel: its textures are past the end of', TEXTURES, '- the Halo CE Sentinel is kept')
        if os.path.exists(f'{OUT}/models/Sentinel_CE'):
            shutil.rmtree(f'{OUT}/models/Sentinel', ignore_errors=True); shutil.copytree(f'{OUT}/models/Sentinel_CE', f'{OUT}/models/Sentinel')
    if ok['SentinelEnforcer']: done.append((enforcer(m, vit), 'SentinelEnforcer'))
    else:
        print('  Enforcer: its textures are past the end of', TEXTURES, '- left out')
        shutil.rmtree(f'{OUT}/models/SentinelEnforcer', ignore_errors=True)
    if ok['SentinelConstructor']: done.append((constructor(m), 'SentinelConstructor'))
    else: shutil.rmtree(f'{OUT}/models/SentinelConstructor', ignore_errors=True)
    for meta, pid in done:
        meta['missing_textures'] = sorted(set(missing)); json.dump(meta, open(f'{OUT}/models/{pid}/{pid}.json', 'w'), indent=1)
    if missing: print('  textures past the end of', TEXTURES, '(drawn grey):', sorted(set(missing)))


if __name__ == '__main__':
    main()
