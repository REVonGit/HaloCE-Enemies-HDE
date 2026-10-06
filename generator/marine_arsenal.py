"""Marine arsenal: HaloDoom Evolved's human weapons as Halo models (the user's picks), as weapon pkls in Halo weapon
space (+x forward, +z up, origin on the grip), for the Marines' weapon overlays.

    python3 marine_arsenal.py            # -> out/weapons/<id>/<id>.pkl + textures

Sources: Halo CE (out/weapons from extract_weapons.py), Halo 2 (01b_spacestation / 08a_deltacliffs) and the Digsite
prototypes (github.com/digsite/h1, JMS + TIFF). The Bulldog is HaloDoom Evolved's own model (Bulldog_HDE.blend: Halo
Infinite's) reinterpreted as a Halo CE gun by bulldog_ce.py, and the grenade launcher HDE's own (GL_HDE.blend1) by gl_ce.py."""
import os, sys, pickle, json
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from jms import JMS

from hce_paths import OUT, DIGSITE
DIG = DIGSITE + '/data/digsite'
H2_01B = os.environ.get('HCE_H2_MAP', '01b_spacestation.map')       # MCC halo2\\h2_maps_win64_dx11
H2_01B_CACHE = os.environ.get('HCE_H2_CACHE') or None
H2_08A = os.environ.get('HCE_H2_MAP08', '08a_deltacliffs.map')
H2_08A_CACHE = os.environ.get('HCE_H2_CACHE08') or None

SH = 'weapons/_shared/'
# HDE weapon -> source. ce: an extract_weapons.py id; dig: (JMS, texture); h2: (map, tag)
ARSENAL = {
    'magnum':           ('ce', 'pistol'),
    'ma5b':             ('ce', 'assault_rifle'),
    'pump_shotgun':     ('ce', 'shotgun'),
    'sniper':           ('ce', 'sniper_rifle'),
    'flamethrower':     ('ce', 'flamethrower'),
    'battle_rifle':     ('h2', ('01b', r'objects\weapons\rifle\battle_rifle\battle_rifle')),
    'smg':              ('h2', ('01b', r'objects\weapons\rifle\smg\smg')),
    'gpmg':             ('h2', ('01b', r'objects\weapons\fixed\h_turret_mp\weapon\weapon')),   # the gun off its tripod
    'rocket_launcher':  ('h2', ('08a', r'objects\weapons\support_high\rocket_launcher\rocket_launcher')),
    'double_barrel':    ('dig', ('weapons/assault_rifle/98_lens/models/base superhigh.JMS', 'weapons/assault_rifle/98_lens/bitmaps/h assault rifle')),
    'commando':         ('dig', ('weapons/assault_rifle/99_mac/models/base superhigh.JMS', SH + '99_mac/bitmaps/h small arms ARGL HG')),
    'dmr':              ('dig', ('weapons/assault_rifle/99_e3/models/h assault rifle.JMS', SH + '99_e3/bitmaps/h small arms AR HG')),
    'ma37':             ('dig', ('weapons/assault_rifle/00_e3/models/h assault rifle.JMS', SH + '00_e3/bitmaps/h small arms ARGL SG')),
    'sidekick':         ('dig', ('weapons/pistol/00_mac/models/h_pistol.JMS', SH + '00_mac/bitmaps/h small arms ARGL HG')),
    'bulldog':          ('ce_bulldog', None),     # HDE's own Bulldog, reinterpreted as a Halo CE gun (bulldog_ce.py)
    'grenade_launcher': ('ce_gl', None),         # HDE's own grenade launcher, reinterpreted as a Halo CE gun (gl_ce.py)
    'stanchion':        ('dig', ('weapons/sniper_rifle/99_mac/models/base superhigh.JMS', SH + '99_mac/bitmaps/h small arms SR SG')),
    'hydra':            ('dig', ('weapons/missile_launcher/99_mac/models/base superhigh.JMS', SH + '99_mac/bitmaps/h support RL ML')),
    'sticky_detonator': ('dig', ('weapons/speargun/99_mac/models/h_speargun.JMS', SH + '99_mac/bitmaps/h small arms SPG SMG')),
}

def load_tex(base):
    for ext in ('.tif', '.tiff', '.TIF', '.png'):
        if os.path.exists(f'{DIG}/{base}{ext}'): return Image.open(f'{DIG}/{base}{ext}')
    raise FileNotFoundError(base)

def dig_meshes(jms):
    w = JMS(f'{DIG}/{jms}')
    uv = w.uv.copy(); uv[:, 1] = 1.0 - uv[:, 1]
    return w, uv

def save_pkl(wid, meshes, tag):
    d = f'{OUT}/weapons/{wid}'
    pickle.dump(dict(id=wid, tag=tag, meshes=meshes), open(f'{d}/{wid}.pkl', 'wb'))

def build_dig(wid, jms, tex):
    d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
    w, uv = dig_meshes(jms)
    mat = f'w_{wid}_0.png'
    load_tex(tex).convert('RGB').save(f'{d}/{mat}')
    save_pkl(wid, [dict(material=mat, pos=w.pos.astype(float), nrm=w.nrm.astype(float), uv=uv, tris=w.tris)], 'digsite:' + jms)

_maps = {}
def h2map(key):
    from h2map import H2Map
    if key not in _maps:
        _maps[key] = H2Map(*{'01b': (H2_01B, H2_01B_CACHE), '08a': (H2_08A, H2_08A_CACHE)}[key])
    return _maps[key]

def build_h2(wid, key, tagname):
    from h2map import render_model
    import extract_h2_brute as hb
    m = h2map(key)
    d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
    M = render_model(m, tagname)
    meshes = []
    for k, mm in enumerate(hb.model_meshes(m, M)):
        shs = [s for s in M['shaders'] if s and s.endswith('\\' + mm['shader'])]
        bms = []
        if shs:
            sh = m.tag('shad', shs[0])['addr']
            for pp in m.block(sh + 0x20, 0x7C)[:1]:
                for b in m.block(pp + 4, 0xC):
                    t = m.u('I', b)[0]
                    if t in m.byid: bms.append(m.byid[t]['name'])
        cands = [n for n in bms if not any(x in n for x in ('bump', 'default_', 'linear_corner', 'detail', 'cube_map', 'noise',
                                                              'clouds', 'gunmetal', 'metal_dirty', 'dark_gray', '_illum', 'reticle'))]
        mat = f'w_{wid}_{k}.png'
        im = hb.bitmap(m, cands[0]) if cands else Image.new('RGBA', (8, 8), (90, 90, 90, 255))
        im.convert('RGB').save(f'{d}/{mat}')
        meshes.append(dict(material=mat, pos=mm['pos'], nrm=mm['nrm'], uv=mm['uv'], tris=mm['tris'][:, [0, 2, 1]],
                           region=mm['region'], perm=mm['perm'], shader=mm['shader'], bitmaps=bms))
    save_pkl(wid, meshes, 'h2:' + tagname)

def _rot(meshes, R, shift=(0, 0, 0)):
    R = np.asarray(R, float)
    for m in meshes:
        m['pos'] = m['pos'] @ R.T + np.asarray(shift, float); m['nrm'] = m['nrm'] @ R.T
        if np.linalg.det(R) < 0: m['tris'] = m['tris'][:, [0, 2, 1]]
    return meshes

def fix_sidekick(meshes):
    """the Macworld 2000 pistol's JMS is its left half (the mirror half was made at compile time): mirror it, centre it,
    and put the origin mid-grip like Halo CE's pistol"""
    out = []
    for m in meshes:
        r = dict(m); r['pos'] = m['pos'] * [1, -1, 1] + [0, -0.002, 0]; r['nrm'] = m['nrm'] * [1, -1, 1]; r['tris'] = m['tris'][:, [0, 2, 1]]
        out += [m, r]
    P = np.concatenate([m['pos'] for m in out])
    grip = P[P[:, 2] < 0.02]
    shift = -np.array([grip[:, 0].mean(), -0.001, 0.02])
    for m in out: m['pos'] = m['pos'] + shift
    return out

def fix_gpmg(meshes):
    """Halo 2's machine-gun turret gun without its tripod, turned to point forward (+x) and levelled; the origin stays
    on the spade grips (its right_hand marker)"""
    meshes = [m for m in meshes if 'tripod' not in m.get('shader', '')]
    P = np.concatenate([m['pos'] for m in meshes])
    c = P.mean(0); u, s, vt = np.linalg.svd(P - c); ax = vt[0] * np.sign(-vt[0][0])      # barrel axis, pointing to -x (forward)
    pitch = np.arctan2(ax[2], -ax[0])
    Rz = np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]])                                   # turn around
    cp, sp = np.cos(pitch), np.sin(pitch)
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])                                 # level the barrel
    return _rot(meshes, Ry @ Rz)

def fix_upright(meshes):
    """Halo CE's flamethrower model stands on end: lay it nozzle-forward"""
    meshes = _rot(meshes, [[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
    P = np.concatenate([m['pos'] for m in meshes])
    tip = P[P[:, 0] > P[:, 0].max() - 0.03].mean(0)          # nozzle end: level it with the grip
    a = np.arctan2(tip[2], tip[0])
    return _rot(meshes, [[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])

# ---------------------------------------------------------------- repaints and the grenade-launcher kitbash
PALETTES = {
    # Halo: Reach's MA37: near-black gunmetal receiver, dark grey furniture, worn steel edges
    'reach': dict(metal=((0.045, 0.048, 0.052), (0.36, 0.37, 0.39)), paint=((0.07, 0.072, 0.07), (0.40, 0.40, 0.37)), wear=(0.62, 0.62, 0.63)),
    # Halo 3's UNSC olive drab over gunmetal
    'unsc': dict(metal=((0.05, 0.053, 0.056), (0.38, 0.39, 0.41)), paint=((0.11, 0.12, 0.075), (0.47, 0.49, 0.34)), wear=(0.60, 0.60, 0.58)),
}

def repaint(img, pal, seed=0):
    """gradient-map a texture into a palette, keeping its detail: coloured (camo, khaki, wood) texels become the paint,
    grey ones the metal; sharp highlights become worn steel"""
    from PIL import ImageFilter
    P = PALETTES[pal]
    a = np.asarray(img.convert('RGB')).astype(np.float32) / 255
    L = a @ np.array([0.3, 0.59, 0.11], np.float32)
    mx, mn = a.max(2), a.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    lo, hi = np.percentile(L, 2), np.percentile(L, 98)
    t = np.clip((L - lo) / max(hi - lo, 1e-3), 0, 1)[..., None] ** 1.1
    def ramp(r): return np.array(r[0], np.float32) * (1 - t) + np.array(r[1], np.float32) * t
    paint = np.clip((sat - 0.10) / 0.12, 0, 1)[..., None]
    out = ramp(P['metal']) * (1 - paint) + ramp(P['paint']) * paint
    blur = np.asarray(Image.fromarray((L * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255
    edge = np.clip((L - blur - 0.06) / 0.10, 0, 1)[..., None] * 0.55
    out = out * (1 - edge) + np.array(P['wear'], np.float32) * edge
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))

def fix_ma37(meshes):
    for m in meshes:
        f = f'{OUT}/weapons/m_ma37/{m["material"]}'
        repaint(Image.open(f), 'reach').save(f)
    return meshes

def _islands(pos, tris):
    key = np.round(pos / 1e-4).astype(np.int64)
    _, weld = np.unique(key, axis=0, return_inverse=True); weld = weld.ravel()
    par = np.arange(weld.max() + 1)
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for t in tris:
        a = f(weld[t[0]])
        for v in t[1:]: par[f(weld[v])] = a
    return np.array([f(weld[t[0]]) for t in tris])

def _part(m, sel_tris):
    used = np.unique(m['tris'][sel_tris]); remap = -np.ones(len(m['pos']), int); remap[used] = np.arange(len(used))
    return dict(material=m['material'], pos=m['pos'][used].copy(), nrm=m['nrm'][used].copy(), uv=m['uv'][used].copy(), tris=remap[m['tris'][sel_tris]])

FIX = {'ma37': fix_ma37, 'sidekick': fix_sidekick, 'gpmg': fix_gpmg, 'flamethrower': fix_upright}

def summary(wid):
    d = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
    P = np.concatenate([m['pos'] for m in d['meshes']])
    return P.min(0).round(3), P.max(0).round(3), sum(len(m['tris']) for m in d['meshes'])

def wid_of(name):
    kind, src = ARSENAL[name]
    return src if kind == 'ce' and name not in FIX else 'm_' + name      # Halo CE's own ids stay; the rest get m_ (no clash with CE's)

MARINES = ['Marine', 'MarineArmored']

def hand_frame(char):
    """(R, t, joint) taking Halo weapon space to the character's bind pose at its gun hand, recovered exactly from the
    Halo CE assault rifle extract_chars.py baked onto it (so every weapon sits where Halo puts a held weapon)"""
    from iqm import read_iqm
    joints, meshes, _ = read_iqm(f'{OUT}/models/{char}/{char}.iqm')
    meta = json.load(open(f'{OUT}/models/{char}/{char}.json'))
    ar = pickle.load(open(f'{OUT}/weapons/assault_rifle/assault_rifle.pkl', 'rb'))
    groups = {}
    for m in ar['meshes']: groups.setdefault(m['material'], []).append(m['pos'])
    A, B, jn = [], [], None
    for si, w in enumerate(meta['mesh_weapon']):
        if w != 'assault_rifle': continue
        src = np.concatenate(groups[meshes[si]['material']]); dst = meshes[si]['pos']
        if len(src) == len(dst): A.append(src); B.append(dst); jn = int(meshes[si]['bidx'][0, 0])
    A = np.concatenate(A); B = np.concatenate(B)
    ca, cb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]); R = Vt.T @ D @ U.T
    t = cb - R @ ca
    assert np.abs(A @ R.T + t - B).max() < 1e-4
    return R, t, jn, joints

def overlays():
    """one overlay model per Marine body per weapon: the weapon on the gun hand's bone, on the body's own skeleton
    (build_pack.py attaches it as model 6, where it moves with the body like the blood overlays)"""
    from iqm import write_iqm
    import shutil
    made = {}
    for char in MARINES:
        R, t, jn, joints = hand_frame(char)
        bind = [[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]]
        od = f'{OUT}/models/{char}'
        for name in ARSENAL:
            wid = wid_of(name)
            d = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
            ms = []
            for k, m in enumerate(d['meshes']):
                n = len(m['pos'])
                bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8); bidx[:, 0] = jn; bw[:, 0] = 255
                ms.append(dict(name=f'{wid}_{k}', material=m['material'], pos=m['pos'] @ R.T + t, nrm=m['nrm'] @ R.T,
                               uv=m['uv'], bidx=bidx, bw=bw, tris=m['tris']))
                shutil.copy(f'{OUT}/weapons/{wid}/{m["material"]}', f'{od}/{m["material"]}')
            fn = f'{char}_w_{name}.iqm'
            write_iqm(f'{od}/{fn}', joints, ms, [dict(name='bind', fps=30.0, loop=True, frames=bind)])
            made.setdefault(char, {})[name] = dict(model=fn, materials=[m['material'] for m in d['meshes']])
        meta = json.load(open(f'{od}/{char}.json'))
        meta['arsenal'] = made[char]
        json.dump(meta, open(f'{od}/{char}.json', 'w'), indent=1)
        print(char, 'weapon overlays', len(made[char]))

def main(only=None):
    for name, (kind, src) in ARSENAL.items():
        wid = wid_of(name)
        if only and name not in only: continue
        if kind == 'dig': build_dig(wid, *src)
        elif kind == 'h2': build_h2(wid, *src)
        elif kind == 'ce_bulldog':
            import bulldog_ce; bulldog_ce.build()
        elif kind == 'ce_gl':
            import gl_ce; gl_ce.build()
        elif name in FIX:                       # a CE weapon needing a fix-up gets its own copy
            import shutil
            wid = 'm_' + name; d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
            sd = pickle.load(open(f'{OUT}/weapons/{src}/{src}.pkl', 'rb'))
            for mm in sd['meshes']:
                new = mm['material'].replace(f'w_{src}_', f'w_{wid}_'); shutil.copy(f'{OUT}/weapons/{src}/{mm["material"]}', f'{d}/{new}'); mm['material'] = new
            save_pkl(wid, sd['meshes'], sd.get('tag', src))
        if name in FIX:
            d = pickle.load(open(f'{OUT}/weapons/{wid}/{wid}.pkl', 'rb'))
            save_pkl(wid, FIX[name](d['meshes']), d.get('tag'))
        print(f'{wid:20s}', *summary(wid))

if __name__ == '__main__':
    if sys.argv[1:2] == ['overlays']: overlays()
    else: main(sys.argv[1:])
