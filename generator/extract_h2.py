"""Halo 2 (MCC) characters -> IQM + skins + JSON, in the same layout extract_chars.py produces for Halo CE.
Currently: the Drone ("bugger") from 01b_spacestation.map. Animations are renamed onto the CE-style names
build_pack.py looks for; overlays (fire, soft flinches) are baked onto the flight idle like the CE ones.
Textures come from MCC's textures.dat when HCE_H2_TEXTURES points at it, otherwise placeholder skins."""
import sys, os, json, pickle, struct
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from h2map import H2Map, render_model
import h2anim
from iqm import write_iqm

from hce_paths import OUT
MAP = os.environ.get('HCE_H2_MAP', '01b_spacestation.map')   # MCC halo2\\h2_maps_win64_dx11
TEXTURES = os.environ.get('HCE_H2_TEXTURES', '')
DRONE = r'objects\characters\bugger\bugger'

# Halo 2 animation -> CE-style name used by build_pack.anim_table (or a custom name the drone's code plays)
RENAME = {
    'flight:pistol:idle:var0': 'stand pistol idle',
    'flight:pistol:move_front': 'stand pistol move-front',
    'flight:pistol:move_back': 'stand pistol move-back',
    'flight:pistol:move_left': 'stand pistol move-left',
    'flight:pistol:move_right': 'stand pistol move-right',
    'combat:pistol:evade_left:var0': 'stand pistol evade-left',
    'combat:pistol:evade_right': 'stand pistol evade-right',
    'combat:pistol:surprise_front': 'stand pistol surprise-front',
    'combat:pistol:surprise_back': 'stand pistol surprise-back',
    'combat:airborne_dead': 'stand airborne-dead',
    'combat:landing_dead': 'stand landing-dead',
    'h_kill:front:gut:var0': 'h-kill front gut',
    's_kill:front:gut:var0': 's-kill front gut',
    's_kill:back:gut:var0': 's-kill back gut',
    'h_ping:front:gut': 'h-ping front gut',
    'h_ping:front:head': 'h-ping front head',
    'h_ping:back:gut': 'h-ping back gut',
    'h_ping:left:gut': 'h-ping left gut',
    'h_ping:right:gut': 'h-ping right gut',
    # wall perching, take-off / landing (played by name from the drone's own code)
    'perch_wall_left:pistol:enter': 'perch left enter',
    'perch_wall_left:pistol:idle': 'perch left idle',
    'perch_wall_left:pistol:exit': 'perch left exit',
    'perch_wall_right:pistol:enter': 'perch right enter',
    'perch_wall_right:pistol:idle': 'perch right idle',
    'perch_wall_right:pistol:exit': 'perch right exit',
    'flight:pistol:takeoff:var0': 'flight takeoff',
    'flight:pistol:land': 'flight land',
    'combat:pistol:idle': 'ground pistol idle',
    'combat:pistol:walk_front': 'ground pistol walk-front',
}
# overlays baked onto a base pose -> name
OVERLAYS = {
    'flight:pistol:pp:fire_1:var0': ('flight:pistol:idle:var0', 'stand pistol fire-1 baked'),
    'perch_wall_left:pistol:pp:fire_1:var0': ('perch_wall_left:pistol:idle', 'perch left fire baked'),
    'perch_wall_right:pistol:pp:fire_1:var1': ('perch_wall_right:pistol:idle', 'perch right fire baked'),
    's_ping:front:gut': ('flight:pistol:idle:var0', 's-ping front gut baked'),
    's_ping:back:gut': ('flight:pistol:idle:var0', 's-ping back gut baked'),
    's_ping:left:gut:var0': ('flight:pistol:idle:var0', 's-ping left gut baked'),
    's_ping:right:gut:var0': ('flight:pistol:idle:var0', 's-ping right gut baked'),
}

def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])
def qrot(q, v):
    u = np.asarray(q[:3]); w = q[3]
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)

def placeholder(kind, size=256):
    """procedural chitin / wing / eye skins until textures.dat is available"""
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:size, 0:size] / size
    noise = sum(np.kron(rng.random((size // s, size // s)), np.ones((s, s))) / (k + 1) for k, s in enumerate((32, 16, 8, 4)))
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    base, var = {'exoskeleton': ((58, 66, 34), (60, 52, 18)), 'wings': ((150, 136, 70), (60, 60, 20)),
                 'antennae': ((52, 50, 30), (40, 36, 16)), 'eye': ((170, 40, 20), (60, 30, 10)),
                 'spikes': ((96, 86, 50), (50, 40, 20))}.get(kind, ((90, 90, 90), (30, 30, 30)))
    seg = 0.75 + 0.25 * np.abs(np.sin(yy * np.pi * 9)) if kind == 'exoskeleton' else 1.0
    if kind == 'wings': seg = 0.8 + 0.2 * (np.abs(np.sin(xx * np.pi * 14)) > 0.93)
    rgb = np.stack([(base[c] + var[c] * (noise - 0.5)) * seg for c in range(3)], -1)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB')

DRONE_WEAPONS = ['plasma_pistol', 'needler', 'plasma_rifle', 'spiker']   # out/weapons/<id>/<id>.pkl (CE weapon space)


# Halo 2's Drone shader: a grey-green diffuse (its alpha a specular mask), a normal map, and a glossy olive-gold
# sheen under the mask. Doom draws the diffuse alone, which reads flat and grey, so the rest is baked in: the normal
# map's relief lit from above, the exoskeleton's greys tinted the Yanme'e olive green, and the specular sheen added
# where the mask marks the hard shell.
DRONE_OLIVE = np.array([0.60, 0.66, 0.40], np.float32)
DRONE_SHEEN = np.array([0.85, 0.95, 0.55], np.float32)

def bake_bugger(im, bump):
    from PIL import Image as _I
    a = np.asarray(im.convert('RGBA')).astype(np.float32) / 255
    rgb, spec = a[..., :3], a[..., 3:4]
    nb = np.asarray(bump.convert('RGB').resize(im.size, _I.BILINEAR)).astype(np.float32) / 255 if bump is not None else None
    lum = rgb.mean(2, keepdims=True)
    sat = (rgb.max(2, keepdims=True) - rgb.min(2, keepdims=True)) / np.maximum(rgb.max(2, keepdims=True), 1e-3)
    grey = np.clip((0.22 - sat) / 0.12, 0, 1)                               # the untinted shell (not the painted greens, browns, eye)
    out = rgb * (1 - grey) + np.clip(lum * DRONE_OLIVE * 1.55, 0, 1) * grey
    if nb is not None:
        n = nb * 2 - 1; n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-3)
        L = np.array([-0.35, 0.55, 0.76], np.float32); L /= np.linalg.norm(L)
        Hh = L + np.array([0, 0, 1.0], np.float32); Hh /= np.linalg.norm(Hh)
        diff = np.clip(n @ L, 0, 1)[..., None]
        out = out * (0.55 + 0.6 * diff)
        out = out + spec * (np.clip(n @ Hh, 0, 1)[..., None] ** 14 * 0.55 + 0.08) * DRONE_SHEEN
    return _I.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), 'RGB')

def drone_texture(m, kind):
    """the Drone shader's colour map from MCC's textures.dat (HCE_H2_TEXTURES), baked (bake_bugger); None without it"""
    if not (TEXTURES and os.path.exists(TEXTURES)): return None
    from h2map import mcc_bitmap
    # which bitmap each Drone shader samples (its postprocess bitmap list); the wings keep their alpha cutout
    src = {'wings': 'bugger_wings'}.get(kind, 'bugger')
    im = mcc_bitmap(m, r'objects\characters\bugger\bitmaps' + '\\' + src, TEXTURES)
    if src == 'bugger':                  # alpha is a specular mask there: bake the shader's look into the colour
        im = bake_bugger(im, mcc_bitmap(m, r'objects\characters\bugger\bitmaps\bugger_bump', TEXTURES))
    return im

def drone_textures(pid='Drone'):
    """rewrite only the Drone's textures (the model, its gore and blood kits untouched)"""
    meta = json.load(open(f'{OUT}/models/{pid}/{pid}.json'))
    done = set()
    for n, mat in zip(meta['mesh_names'], meta['meshes']):
        kind = n.rsplit('_', 1)[0]
        if not mat.startswith(pid + '_') or mat in done or kind.startswith(('weapon', 'gore')): continue
        im = drone_texture(m, kind)
        if im is not None: im.save(f'{OUT}/models/{pid}/{mat}'); done.add(mat); print(kind, '->', mat, im.mode, im.size)

def extract_drone(pid='Drone'):
    m = H2Map(MAP, os.environ.get('HCE_H2_CACHE') or None)
    M = render_model(m, DRONE)
    nodes = M['nodes']; NJ = len(nodes)
    od = f'{OUT}/models/{pid}'; os.makedirs(od, exist_ok=True)
    # highest detail section of the base permutation
    perm = M['regions'][0]['perms'][0]
    sec = M['sections'][max(i for i in perm['lods'] if i >= 0)]
    meshes = []; mats = {}
    for shi, tris in sec['parts']:
        sh = M['shaders'][shi] or 'unknown'
        kind = sh.split('bugger_')[-1]
        if kind not in mats:
            mn = f'{pid}_{len(mats)}'
            (drone_texture(m, kind) or placeholder(kind)).save(f'{od}/{mn}.png'); mats[kind] = mn
        n = sec['vc']
        bidx = np.clip(sec['bi'], 0, NJ - 1).astype(np.uint8)
        bw = np.clip(np.round(sec['bw'] * 255), 0, 255).astype(np.uint8)
        meshes.append(dict(name=f'{kind}_{shi}', material=f'{mats[kind]}.png', pos=sec['pos'], nrm=sec['nrm'],
                           uv=sec['uv'], bidx=bidx, bw=bw, tris=tris[:, [0, 2, 1]]))
    # wings (and antennae) are thin double-sided sheets in Halo 2: add the back faces
    for mm in meshes:
        if mm['name'].startswith(('wings', 'antennae')):
            mm['tris'] = np.concatenate([mm['tris'], mm['tris'][:, [0, 2, 1]]])
    # drop unused vertices per mesh (each mesh got the whole vertex buffer)
    for mm in meshes:
        used = np.unique(mm['tris']); remap = -np.ones(len(mm['pos']), np.int64); remap[used] = np.arange(len(used))
        for k in ('pos', 'nrm', 'uv', 'bidx', 'bw'): mm[k] = mm[k][used]
        mm['tris'] = remap[mm['tris']]
    # world bind
    W = []
    for n in nodes:
        t = np.array(n['t']); q = np.array(n['q'])
        if n['parent'] < 0: W.append((t, q))
        else:
            pt, pq = W[n['parent']]; W.append((pt + qrot(pq, t), qmul(pq, q)))
    # guns in the right hand (marker right_hand)
    a = m.tag('mode', DRONE)['addr']
    markers = {}
    for g in m.block(a + 0x58, 0xC):
        nm = m.sid(m.u('I', g)[0])
        for mk in m.block(g + 4, 0x24):
            markers.setdefault(nm.replace('_', ' '), []).append(dict(node=m.b[m.o(mk) + 2], t=list(m.u('3f', mk + 4)), q=list(m.u('4f', mk + 0x10))))
    mesh_weapon = [None] * len(meshes)
    mk = markers['right hand'][0]
    wt, wq = W[mk['node']]; mt = np.array(mk['t']); mq = np.array(mk['q'])
    tq = qmul(wq, mq); tq /= np.linalg.norm(tq)
    import shutil
    # one-handed Covenant guns, one shown per class: the plasma pistol (Halo 2's default), the needler, the CE
    # plasma rifle and the Spiker
    for wid, wm, k in [(w, x, k) for w in DRONE_WEAPONS
                       for k, x in enumerate(pickle.load(open(f'{OUT}/weapons/{w}/{w}.pkl', 'rb'))['meshes'])]:
        pos = np.array([wt + qrot(wq, mt + qrot(mq, v)) for v in wm['pos']])
        nrm = np.array([qrot(tq, v) for v in wm['nrm']])
        bidx = np.zeros((len(pos), 4), np.uint8); bw = np.zeros((len(pos), 4), np.uint8)
        bidx[:, 0] = mk['node']; bw[:, 0] = 255
        shutil.copy(f'{OUT}/weapons/{wid}/{wm["material"]}', f'{od}/{wm["material"]}')
        meshes.append(dict(name=f'weapon_{wid}_{k}', material=wm['material'], pos=pos, nrm=nrm, uv=wm['uv'],
                           bidx=bidx, bw=bw, tris=wm['tris']))
        mesh_weapon.append(wid)
    # animations
    skel, an = h2anim.graph(m, DRONE)
    assert skel == [n['name'] for n in nodes]
    defaults = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
    byname = {x['name']: x for x in an}
    dec = {}
    def get(nm):
        if nm not in dec: dec[nm] = h2anim.decode(byname[nm]['data'], byname[nm]['sizes'], byname[nm]['frames'], byname[nm]['nodes'], defaults)
        return dec[nm]
    alist = []; info = {}
    def add(name, frames, mv, loop):
        dx = mv[:, [0, 1, 2, 3]]
        speed = float(np.hypot(dx[:, 0], dx[:, 1]).sum() / max(1, len(frames)))
        info[name] = dict(frames=len(frames), speed=speed, yaw=float(np.degrees(dx[:, 3].sum())), loop=loop, key=-1, next=-1,
                          dx=[float(dx[:, 0].sum()), float(dx[:, 1].sum())])
        alist.append(dict(name=name, fps=30.0, loop=True, frames=frames))
    for src, dst in RENAME.items():
        fr, mv = get(src); add(dst, fr, mv, byname[src]['loop'])
    for src, (basen, dst) in OVERLAYS.items():
        o = byname[src]
        ofr, _ = h2anim.decode(o['data'], o['sizes'], o['frames'], o['nodes'], [(np.zeros(3), np.array([0, 0, 0, 1.0]))] * NJ)
        bfr, _ = get(basen)
        b0 = bfr[0]
        frames = []
        for f in ofr:
            row = []
            for j in range(NJ):
                bt, bq, bs = b0[j]; ot, oq, os_ = f[j]
                q = qmul(np.array(bq), np.array(oq)); q /= np.linalg.norm(q)
                row.append((tuple(np.array(bt) + np.array(ot)), tuple(q), bs))
            frames.append(row)
        add(dst, frames, np.zeros((len(frames), 4)), 0)
    joints = [(n['name'], n['parent'], tuple(n['t']), tuple(n['q']), (1, 1, 1)) for n in nodes]
    from extract_chars import merge_meshes
    meshes, mesh_weapon = merge_meshes(meshes, mesh_weapon)
    path = f'{od}/{pid}.iqm'
    size = write_iqm(path, joints, meshes, alist)
    allp = sec['pos']
    meta = dict(id=pid, tag=DRONE, maps=['01b_spacestation'], joints=[j[0] for j in joints],
                bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info, materials=sorted(mats.values()),
                iqm_bytes=size, meshes=[x['material'] for x in meshes], has_multi={v: False for v in mats.values()},
                collision_height=0.4, collision_radius=0.25, markers=markers, mesh_weapon=mesh_weapon)
    json.dump(meta, open(f'{od}/{pid}.json', 'w'), indent=1)
    return meta, M, m

SOUNDS_DIR = os.environ.get('HCE_H2_SOUNDS', '')   # MCC halo2\h2_maps_win64_dx11 (sounds_en.dat, sounds_neutral.dat)

def extract_drone_sounds(pid='Drone'):
    """Drone dialogue (sounds_en.dat) and, if present, effects (sounds_neutral.dat: chunk flag 0x2000) -> Ogg Opus"""
    import h2opus
    from h2map import sound_chunks
    m = H2Map(MAP, os.environ.get('HCE_H2_CACHE') or None)
    files = {}
    for k, fn in (('en', 'sounds_en.dat'), ('neutral', 'sounds_neutral.dat')):
        p = os.path.join(SOUNDS_DIR, fn)
        if os.path.exists(p): files[k] = open(p, 'rb')
    od = f'{OUT}/sounds/{pid}'; os.makedirs(od, exist_ok=True)
    idx = {}; missing = set()
    for n in [t['name'] for t in m.tags if t['cls'] == 'snd!' and 'bugger' in t['name'] and t['name'].startswith('sound\\')]:
        base = n.split('\\')[-1]
        for pi, (pn, codec, locs) in enumerate(sound_chunks(m, n)):
            ch = [l for l in locs if l[0] == 0][0][1]
            src = 'neutral' if any(fl & 0x2000 for _, _, fl, _, _ in ch) else 'en'
            if src not in files: missing.add(base); continue
            f = files[src]; pk = []
            for o, cs, fl, us, ri in ch:                 # every chunk is its own length-prefixed packet chain
                f.seek(o); pk += h2opus.packets(f.read(cs & 0xFFFF), strict=True)
            fn = f'{base}_{pi:02d}.ogg'
            open(f'{od}/{fn}', 'wb').write(h2opus.to_ogg(pk, channels=2 if codec[1] == 1 else 1))
            idx.setdefault(base, []).append(fn)
    json.dump(idx, open(f'{od}/index.json', 'w'), indent=1)
    return idx, sorted(missing)

if __name__ == '__main__':
    if sys.argv[1:2] == ['textures']:
        drone_textures(); sys.exit()
    meta, M, m = extract_drone()
    if SOUNDS_DIR:
        idx, missing = extract_drone_sounds()
        print('Drone sounds', sum(map(len, idx.values())), 'clips;', 'missing (need sounds_neutral.dat):' if missing else '', ' '.join(missing))
    print('Drone anims', len(meta['anims']), 'joints', len(meta['joints']), 'iqm', meta['iqm_bytes'] // 1024, 'KB',
          'bounds', np.round(meta['bounds'], 2).tolist())
