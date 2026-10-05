"""Extract Halo CE campaign enemies (+ marines) to IQM + PNG skins + JSON stats."""
import os, sys, json, re, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import halomodel as hm
from tags import tag, HMap, Tag, LAYOUT
from bitmaps import bitmap_image
from iqm import write_iqm

MAPS = ['a10', 'a30', 'a50', 'b30', 'b40', 'c10', 'c20', 'c40', 'd20', 'd40']
CHARS = {  # biped tag name -> pack id
    r'characters\grunt\grunt': 'Grunt',
    r'characters\grunt\grunt specops': 'GruntSpecOps',
    r'characters\jackal\jackal': 'Jackal',
    r'characters\jackal\jackal major': 'JackalMajor',
    r'characters\elite\elite': 'Elite',
    r'characters\elite\elite special': 'EliteSpecial',
    r'characters\hunter\hunter': 'Hunter',
    r'characters\flood_infection\flood_infection': 'FloodInfection',
    r'characters\floodcarrier\floodcarrier': 'FloodCarrier',
    r'characters\floodcombat elite\floodcombat elite': 'FloodElite',
    r'characters\floodcombat_human\floodcombat_human': 'FloodHuman',
    r'characters\sentinel\sentinel': 'Sentinel',
    r'characters\marine\marine': 'Marine',
    r'characters\marine_armored\marine_armored': 'MarineArmored',
}
from hce_paths import OUT, MAPS_DIR

def sanitize(n):
    return re.sub(r'[^a-z0-9_]+', '_', n.lower()).strip('_')

def shader_maps(m, sh):
    t = m.byid.get(sh['id']) if isinstance(sh, dict) else None
    if not t: return None, None, (1, 1)
    if t['cls'] == 'soso':
        base = m.u('I', t['data'] + 0xA4 + 12)[0]
        multi = m.u('I', t['data'] + 0xBC + 12)[0]
        us, vs = m.u('2f', t['data'] + 0x9C)
        return (base if base in m.byid else None), (multi if multi in m.byid else None), (us or 1, vs or 1)
    from render import shader_basemap
    ref, _ = shader_basemap(m, t['id'])
    return ref, None, (1, 1)

# hand marker each species attaches its weapon to (animation graph weapon_class.hand_marker_name)
HAND_MARKER = {'Elite': 'right hand elite', 'EliteSpecial': 'right hand elite',
               'Jackal': 'left hand jackal', 'JackalMajor': 'left hand jackal'}

def char_weapons(name):
    """weapon ids this biped carries in any actor variant (needs ai_data.json from extract_ai.py)"""
    import pickle
    from extract_weapons import WEAPONS
    p = f'{OUT}/ai_data.json'
    if not os.path.exists(p): return []
    AI = json.load(open(p))
    out = []
    for v in AI['variants'].values():
        if v['unit_reference'] != name: continue
        w = WEAPONS.get((v.get('ranged_combat') or {}).get('reference') or '')
        if w and w not in out and os.path.exists(f'{OUT}/weapons/{w}/{w}.pkl'): out.append(w)
    return sorted(out)

def attach_weapons(pid, name, model, markers, meshes):
    """Bake each weapon rigidly onto the hand node at Halo's hand marker (weapon origin = marker)."""
    import pickle
    if pid in ('Hunter', 'Sentinel'): return []   # weapon is part of the body (arm cannon / beam)
    mk = markers.get(HAND_MARKER.get(pid, 'right hand'))
    if not mk: return []
    node, mt, mq = mk[0]['node'], np.array(mk[0]['t']), hm.hq(mk[0]['q'])
    W = model.world_bind()
    wt, wq = W[node]
    tq = hm.qnorm(hm.qmul(wq, mq))
    added = []
    for wid in char_weapons(name):
        wd = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
        for k, wm in enumerate(wd['meshes']):
            pos = np.array([wt + hm.qrot(wq, mt + hm.qrot(mq, v)) for v in wm['pos']])
            nrm = np.array([hm.qrot(tq, n) for n in wm['nrm']])
            n = len(pos)
            bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8)
            bidx[:, 0] = node; bw[:, 0] = 255
            shutil.copy(f'{OUT}/weapons/{wid}/{wm["material"]}', f'{OUT}/models/{pid}/{wm["material"]}')
            meshes.append(dict(name=f'weapon_{wid}_{k}', material=wm['material'], pos=pos, nrm=nrm,
                               uv=wm['uv'], bidx=bidx, bw=bw, tris=wm['tris']))
            added.append(wid)
    return added

def merge_meshes(meshes, mesh_weapon):
    """One surface per (material, weapon): UZDoom models allow at most 32 surfaces (MD3_MAX_SURFACES)."""
    groups = {}
    for mm, w in zip(meshes, mesh_weapon):
        groups.setdefault((mm['material'], w), []).append(mm)
    out, ow = [], []
    for (mat, w), ms in groups.items():
        base = 0; tris = []
        for mm in ms:
            tris.append(mm['tris'] + base); base += len(mm['pos'])
        out.append(dict(name=ms[0]['name'], material=mat,
                        pos=np.concatenate([x['pos'] for x in ms]), nrm=np.concatenate([x['nrm'] for x in ms]),
                        uv=np.concatenate([x['uv'] for x in ms]), bidx=np.concatenate([x['bidx'] for x in ms]),
                        bw=np.concatenate([x['bw'] for x in ms]), tris=np.concatenate(tris)))
        ow.append(w)
    assert len(out) <= 32, f'{len(out)} surfaces > 32'
    return out, ow

def extract(name, pid, sources, maps):
    os.makedirs(f'{OUT}/models/{pid}', exist_ok=True)
    m = maps[sources[0]]
    bt = [t for t in m.find('bipd') if t['name'] == name][0]
    B = tag(m, bt, 'biped_definition')
    model = hm.Model(m, B['model'])
    NJ = len(model.nodes)
    # choose permutation per region: 'base'-like first permutation; highest-detail geometry
    parts_all = []
    for r in model.regions:
        perm = next((p for p in r['perms'] if p['name'].startswith('base')), r['perms'][0])
        best = None
        for gi in sorted(set(perm['geoms'])):
            g = model.geometry(gi)
            nt = sum(len(p['tris']) for p in g)
            if best is None or nt > best[0]: best = (nt, g)
        for p in best[1]:
            p['region'] = r['name']
        parts_all += best[1]
    # materials
    mats = {}
    meshes = []
    bms = model.base_map_scale
    for pi, p in enumerate(parts_all):
        sh = model.shaders[p['shader']] if p['shader'] < len(model.shaders) else None
        if sh and sh['cls'] in ('spla', 'sgla', 'schi', 'scex', 'swat', 'smet'):
            continue  # transparent effect shells (sentinel shield etc.)
        base, multi, (us, vs) = shader_maps(m, sh) if sh else (None, None, (1, 1))
        key = (base, multi)
        if key not in mats:
            mn = f'{pid}_{len(mats)}'
            im = bitmap_image(m, base) if base else None
            mim = bitmap_image(m, multi) if multi else None
            if im is None: im = Image.new('RGBA', (16, 16), (128, 128, 128, 255))
            im.convert('RGB').save(f'{OUT}/models/{pid}/{mn}.png')
            if mim is not None: mim.save(f'{OUT}/models/{pid}/{mn}_multi.png')
            mats[key] = mn
        uv = p['uv'] * np.array([bms[0] * us, bms[1] * vs])
        uv = np.stack([uv[:, 0], uv[:, 1]], 1)
        bidx = np.zeros((len(p['pos']), 4), np.uint8); bw = np.zeros((len(p['pos']), 4), np.uint8)
        nd = np.clip(p['nodes'], 0, NJ - 1)
        w = np.clip(p['w'], 0, 1)
        same = nd[:, 0] == nd[:, 1]
        w0 = np.where(same, 1.0, w[:, 0]); w1 = np.where(same, 0.0, w[:, 1])
        wb0 = np.round(w0 * 255).astype(int); wb1 = 255 - wb0
        bidx[:, 0] = nd[:, 0]; bidx[:, 1] = np.where(same, 0, nd[:, 1])
        bw[:, 0] = wb0; bw[:, 1] = np.where(same, 0, wb1)
        meshes.append(dict(name=f'{p["region"]}_{pi}', material=f'{mats[key]}.png', pos=p['pos'], nrm=p['nrm'],
                           uv=uv, bidx=bidx, bw=bw, tris=p['tris'][:, [0, 2, 1]]))
    markers = read_markers(m, model)
    mesh_weapon = [None] * len(meshes)
    mesh_weapon += attach_weapons(pid, name, model, markers, meshes)
    meshes, mesh_weapon = merge_meshes(meshes, mesh_weapon)
    joints = [(n['name'], n['parent'], tuple(n['t']), tuple(n['q']), (1, 1, 1)) for n in model.nodes]
    # animations, merged across every map that carries this biped
    anims = {}; info = {}; overlays = {}
    for mapn in sources:
        mm = maps[mapn]
        bts = [t for t in mm.find('bipd') if t['name'] == name]
        if not bts: continue
        BB = tag(mm, bts[0], 'biped_definition')
        if not BB['animation_graph']: continue
        for a in hm.read_animations(mm, BB['animation_graph'], NJ):
            if a.name in anims: continue
            if a.type == 0:
                anims[a.name] = a
            elif a.type == 1:
                overlays.setdefault(a.name, a)
    # bake fire / flinch / motor overlays onto the matching idle pose
    import copy
    for on, ov in overlays.items():
        if not re.search(r'fire-|s-ping|overlay|reload', on): continue
        words = on.split(' ')
        mode = ' '.join(words[:2]) if len(words) >= 2 else 'stand'
        if on.startswith('s-ping'):
            mode = None
        cands = [k for k in anims if mode and k.startswith(mode + ' idle')] or \
                [k for k in anims if k.startswith('stand') and ' idle' in k] or \
                [k for k in anims if 'idle' in k]
        if not cands: continue
        base = anims[sorted(cands)[0]]
        b = copy.copy(base)
        b.name = on + ' baked'
        b.frames = hm.bake_overlay(base.frames[0], ov.frames)
        b.nframes = len(b.frames); b.dx = np.zeros((b.nframes, 4))
        anims[b.name] = b
    alist = []
    for nm in sorted(anims):
        a = anims[nm]
        speed = float(np.hypot(a.dx[:, 0], a.dx[:, 1]).sum() / max(1, a.nframes))  # WU per frame (30 Hz)
        yaw = float(a.dx[:, 3].sum())
        info[nm] = dict(frames=a.nframes, speed=speed, yaw=yaw, loop=a.loop, key=a.key,
                        next=a.next, dx=[float(a.dx[:, 0].sum()), float(a.dx[:, 1].sum())])
        alist.append(dict(name=nm, fps=30.0, loop=True,
                          frames=[[(t, q, sc) for (t, q, sc) in fr] for fr in a.frames]))
    path = f'{OUT}/models/{pid}/{pid}.iqm'
    size = write_iqm(path, joints, meshes, alist)
    # bounds in bind pose
    allp = np.concatenate([p['pos'] for p in parts_all])
    meta = dict(id=pid, tag=name, maps=sources, joints=[j[0] for j in joints],
                bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info,
                materials=sorted(mats.values()), iqm_bytes=size, meshes=[mm['material'] for mm in meshes],
                has_multi={v: os.path.exists(f'{OUT}/models/{pid}/{v}_multi.png') for v in mats.values()},
                collision_height=B['collision_height_standing'], collision_radius=B['collision_radius'],
                markers=markers, mesh_weapon=mesh_weapon)
    json.dump(meta, open(f'{OUT}/models/{pid}/{pid}.json', 'w'), indent=1)
    return meta

def read_markers(m, model):
    out = {}
    for mk in model.tag.block('markers', 'model_marker'):
        nm = hm.cstr(m, mk.addr)
        insts = []
        for ins in mk.block('instances', 'model_marker_instance'):
            insts.append(dict(node=ins['node_index'], t=list(ins['translation']), q=list(ins['rotation'])))
        out[nm] = insts
    return out

if __name__ == '__main__':
    only = sys.argv[1:]
    maps = {n: HMap(f'{MAPS_DIR}/{n}.map') for n in MAPS}
    where = {}
    for n in MAPS:
        for t in maps[n].find('bipd'):
            where.setdefault(t['name'], []).append(n)
    for name, pid in CHARS.items():
        if only and pid not in only: continue
        srcs = where.get(name)
        if not srcs: print('missing', name); continue
        meta = extract(name, pid, srcs, maps)
        print(pid, 'anims', len(meta['anims']), 'joints', len(meta['joints']), 'iqm', meta['iqm_bytes'] // 1024, 'KB',
              'bounds', np.round(meta['bounds'], 2).tolist(), 'h', round(meta['collision_height'], 2), 'r', round(meta['collision_radius'], 2), flush=True)
