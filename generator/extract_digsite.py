"""Digsite (github.com/digsite/h1) characters -> IQM + PNG skins + JSON, same layout as extract_chars.py.

Source assets are JMS models and JMA-family animations (not compiled tags), so root motion,
overlays and rename.txt aliases are processed here the way Halo's tool.exe would."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, re, glob
import numpy as np
from PIL import Image
from jms import JMS, JMA, world
from halomodel import qmul, qrot, qconj, qnorm
from iqm import write_iqm

from hce_paths import DIGSITE, OUT
DIG = DIGSITE + '/data/digsite'

CHARS = {
    'Drinol': dict(jms='characters/drinol/00_mac/models/base superhigh.JMS',
                   anims='characters/drinol/00_mac/animations',
                   tex={'torso-shell': 'characters/drinol/00_mac/bitmaps/drinol chest',
                        'head': 'characters/drinol/00_mac/bitmaps/drinol chest',
                        'arms': 'characters/drinol/00_mac/bitmaps/drinol arms',
                        'legs': 'characters/drinol/00_mac/bitmaps/drinol legs'}),
    'SlugMan': dict(jms='characters/slug_man/models/base superhigh.JMS',
                    anims='characters/slug_man/animations',
                    tex={'body': 'characters/slug_man/bitmaps/slugman'},
                    multi={'body': 'characters/slug_man/bitmaps/slugman_multi'},
                    # Slug Men are left-handed: the gun goes on the left hand marker, which follows Halo's usual
                    # weapon axes (barrel +x, top +z), so it needs no remapping (checked against the posed marker in
                    # every aim, move and fire animation; the right hand is the free one reaching forward)
                    weapons=('left hand elite', ['particle_beam_dig', 'plasma_pistol', 'needler', 'plasma_rifle', 'cmt_carbine'])),
}

def load_tex(base):
    for ext in ('.tif', '.tiff', '.TIF', '.png'):
        p = f'{DIG}/{base}{ext}'
        if os.path.exists(p):
            return Image.open(p)
    raise FileNotFoundError(base)

def yaw_q(a):
    return np.array([0, 0, np.sin(a / 2), np.cos(a / 2)])

def yaw_of(q):
    """heading of the quaternion's forward (+x) axis"""
    f = qrot(q, np.array([1.0, 0, 0]))
    return np.arctan2(f[1], f[0])

def process_anim(a, bind_local):
    """returns (frames, dx[F,4]) with root motion removed like tool.exe does per file type"""
    F = a.nframes
    fr = [list(f) for f in a.frames]
    dx = np.zeros((F, 4))
    if a.kind in ('JMA', 'JMT', 'JMZ') and F > 1:
        r0 = fr[0][0][0].copy(); y0 = yaw_of(fr[0][0][1])
        for f in range(F):
            t, q, s = fr[f][0]
            if f + 1 < F:
                d = fr[f + 1][0][0] - t
                dx[f, 0:2] = d[0:2]
                if a.kind == 'JMZ': dx[f, 2] = d[2]
                if a.kind == 'JMT': dx[f, 3] = yaw_of(fr[f + 1][0][1]) - yaw_of(q)
            nt = t.copy(); nt[0:2] = r0[0:2]
            if a.kind == 'JMZ': nt[2] = r0[2]
            nq = q
            if a.kind == 'JMT':
                dy = yaw_of(q) - y0
                nq = qnorm(qmul(yaw_q(-dy), q))
            fr[f][0] = (nt, nq, s)
        dx[:, 3] = (dx[:, 3] + np.pi) % (2 * np.pi) - np.pi
    return fr, dx

def bake_overlay(base_frame, ov):
    """JMO: every frame relative to the overlay's first frame, applied on top of base_frame"""
    out = []
    o0 = ov.frames[0]
    for f in ov.frames:
        cur = []
        for (bt, bq, bs), (t0, q0, s0), (t, q, s) in zip(base_frame, o0, f):
            dq = qnorm(qmul(qconj(q0), q))
            cur.append((bt + (t - t0), qnorm(qmul(bq, dq)), bs))
        out.append(cur)
    return out

def read_anims(adir, names):
    files = sorted(glob.glob(f'{adir}/*.JM?'))
    raw = {}
    for p in files:
        nm = os.path.basename(p).rsplit('.', 1)[0]
        a = JMA(p)
        if len(a.names) != len(names):
            print('  skip (node count)', nm); continue
        if [n.lower() for n in a.names] != [n.lower() for n in names]:
            # reorder by name
            idx = [[n.lower() for n in a.names].index(n.lower()) for n in names]
            a.frames = [[f[i] for i in idx] for f in a.frames]
        raw[nm] = a
    ren = f'{adir}/rename.txt'
    aliases = {}
    if os.path.exists(ren):
        for l in open(ren, encoding='latin1'):
            if '=' in l:
                k, v = [x.strip() for x in l.split('=', 1)]
                aliases[k] = v
    return raw, aliases

def build_mesh(j, pid, tex, multi=None, flip_v=True):
    os.makedirs(f'{OUT}/models/{pid}', exist_ok=True)
    meshes = []; mats = {}
    w0 = 1.0 - np.clip(j.w1, 0, 1)
    for mi, (mname, _) in enumerate(j.materials):
        sel = np.where(j.tri_mat == mi)[0]
        if not len(sel): continue
        src = tex[mname]
        if src not in mats:
            mn = f'{pid}_{len(mats)}'
            load_tex(src).convert('RGB').save(f'{OUT}/models/{pid}/{mn}.png')
            if multi and mname in multi:
                load_tex(multi[mname]).convert('RGBA').save(f'{OUT}/models/{pid}/{mn}_multi.png')
            mats[src] = mn
        tris = j.tris[sel]
        vid = np.unique(tris)
        remap = -np.ones(len(j.pos), int); remap[vid] = np.arange(len(vid))
        bidx = np.zeros((len(vid), 4), np.uint8); bw = np.zeros((len(vid), 4), np.uint8)
        n0 = j.node0[vid]; n1 = j.node1[vid]; ww = w0[vid]
        single = (n1 < 0) | (n1 == n0)
        wb0 = np.where(single, 255, np.round(ww * 255)).astype(int)
        bidx[:, 0] = n0; bw[:, 0] = wb0
        bidx[:, 1] = np.where(single, 0, n1); bw[:, 1] = np.where(single, 0, 255 - wb0)
        uv = j.uv[vid].copy()
        if flip_v: uv[:, 1] = 1.0 - uv[:, 1]
        meshes.append(dict(name=f'{mname}_{mi}', material=f'{mats[src]}.png', pos=j.pos[vid], nrm=j.nrm[vid], uv=uv,
                           bidx=bidx, bw=bw, tris=remap[tris]))
    return meshes, mats

def digsite_weapon(wid, jms, tex):
    """a Digsite JMS weapon -> weapon pkl (already Halo weapon space: +x forward, origin on the grip)"""
    import pickle
    w = JMS(f'{DIG}/{jms}')
    d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
    mat = f'w_{wid}_0.png'
    load_tex(tex).convert('RGB').save(f'{d}/{mat}')
    uv = w.uv.copy(); uv[:, 1] = 1.0 - uv[:, 1]
    pickle.dump(dict(id=wid, tag='digsite:' + jms, meshes=[dict(material=mat, pos=w.pos, nrm=w.nrm, uv=uv, tris=w.tris)]),
                open(f'{d}/{wid}.pkl', 'wb'))

def attach(j, pid, meshes, marker, wids, fix=lambda v: v):
    """weapons rigidly on the hand node at the hand marker (weapon origin = marker), like extract_chars"""
    import pickle, shutil
    mk = next(m for m in j.markers if m['name'] == marker)
    W = j.world_bind()
    wt, wq = W[mk['node']]
    tq = qnorm(qmul(wq, mk['q']))
    added = []
    for wid in wids:
        wd = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
        for k, wm in enumerate(wd['meshes']):
            pos = np.array([wt + qrot(wq, mk['t'] + qrot(mk['q'], fix(v))) for v in wm['pos']])
            nrm = np.array([qrot(tq, fix(n)) for n in wm['nrm']])
            n = len(pos)
            bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8)
            bidx[:, 0] = mk['node']; bw[:, 0] = 255
            shutil.copy(f'{OUT}/weapons/{wid}/{wm["material"]}', f'{OUT}/models/{pid}/{wm["material"]}')
            meshes.append(dict(name=f'weapon_{wid}_{k}', material=wm['material'], pos=pos, nrm=nrm,
                               uv=wm['uv'], bidx=bidx, bw=bw, tris=wm['tris']))
            added.append(wid)
    return added

def extract(pid, cfg):
    j = JMS(f'{DIG}/{cfg["jms"]}')
    meshes, mats = build_mesh(j, pid, cfg['tex'], cfg.get('multi'))
    mesh_weapon = [None] * len(meshes)
    if cfg.get('weapons'):
        mesh_weapon += attach(j, pid, meshes, *cfg['weapons'])
    bind = [(t, q, 1.0) for t, q in zip(j.t, j.q)]
    raw, aliases = read_anims(f'{DIG}/{cfg["anims"]}', j.names)
    anims = {}; dxs = {}; overlays = {}
    for nm, a in raw.items():
        if a.kind == 'JMO':
            overlays[nm] = a; continue
        fr, dx = process_anim(a, bind)
        anims[nm] = fr; dxs[nm] = dx
    # tool.exe rename.txt: extra graph entries that reuse another animation
    for k, v in aliases.items():
        if k in anims or k in overlays: continue
        src = v if v in anims or v in overlays else next((n for n in list(anims) + list(overlays) if re.fullmatch(re.escape(v) + r'(%\d+)?', n)), None)
        if not src: continue
        if src in anims: anims[k] = anims[src]; dxs[k] = dxs[src]
        else: overlays[k] = overlays[src]
    # bake overlays (fire, flinch, aim) onto the matching idle pose, like extract_chars
    for on, ov in overlays.items():
        if not re.search(r'fire-|s-ping|overlay|reload', on): continue
        words = on.split(' ')
        mode = None if on.startswith('s-ping') else ' '.join(words[:2])
        cands = [k for k in anims if mode and k.startswith(mode + ' idle')] or \
                [k for k in anims if k.startswith('stand') and ' idle' in k] or [k for k in anims if 'idle' in k]
        if not cands: continue
        base = anims[sorted(cands)[0]][0]
        anims[on + ' baked'] = bake_overlay(base, ov)
        dxs[on + ' baked'] = np.zeros((len(anims[on + ' baked']), 4))
    joints = [(n, p, tuple(t), tuple(q), (1, 1, 1)) for n, p, t, q in zip(j.names, j.parent, j.t, j.q)]
    alist = []; info = {}
    for nm in sorted(anims):
        fr = anims[nm]; dx = dxs[nm]; F = len(fr)
        info[nm] = dict(frames=F, speed=float(np.hypot(dx[:, 0], dx[:, 1]).sum() / max(1, F)), yaw=float(dx[:, 3].sum()),
                        loop=0, key=0, next=-1, dx=[float(dx[:, 0].sum()), float(dx[:, 1].sum())])
        alist.append(dict(name=nm, fps=30.0, loop=True, frames=[[(t, q, (s, s, s)) for (t, q, s) in f] for f in fr]))
    path = f'{OUT}/models/{pid}/{pid}.iqm'
    size = write_iqm(path, joints, meshes, alist)
    markers = {}
    for mk in j.markers:
        markers.setdefault(mk['name'], []).append(dict(node=mk['node'], t=mk['t'].tolist(), q=mk['q'].tolist()))
    meta = dict(id=pid, tag='digsite:' + cfg['jms'], joints=list(j.names),
                bounds=[j.pos.min(0).tolist(), j.pos.max(0).tolist()], anims=info, materials=sorted(mats.values()),
                iqm_bytes=size, meshes=[m['material'] for m in meshes],
                has_multi={v: os.path.exists(f'{OUT}/models/{pid}/{v}_multi.png') for v in mats.values()},
                markers=markers, mesh_weapon=mesh_weapon)
    json.dump(meta, open(f'{OUT}/models/{pid}/{pid}.json', 'w'), indent=1)
    return meta, j, joints, meshes, alist

if __name__ == '__main__':
    # the Slug Man's own weapon, as Digsite set it up: the 99_mac Particle Beam Rifle (all three shaders share one map)
    digsite_weapon('particle_beam_dig', 'weapons/particle_beam/99_mac/models/c particle beam rifle.JMS',
                   'weapons/_shared/99_mac/bitmaps/c small arms PBR CG')
    for pid, cfg in CHARS.items():
        if sys.argv[1:] and pid not in sys.argv[1:]: continue
        meta = extract(pid, cfg)[0]
        print(pid, 'anims', len(meta['anims']), 'iqm', meta['iqm_bytes'] // 1024, 'KB', 'bounds', np.round(meta['bounds'], 2).tolist())
