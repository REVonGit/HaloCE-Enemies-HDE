"""Dismemberment for the Covenant: severable heads and arms, gore stumps and flying gibs.

    python3 gore_kit.py [Char ...]      # post-processes out/models/<Char>/<Char>.iqm (+ .json) in place

Run after the extract_* scripts (they write the IQMs) and before build_pack.py / build_digsite.py.

Per character (GORE below), each limb is a bone subtree (head, left arm, right arm). The model's surfaces are split
so every limb's triangles sit on surfaces of their own: a surface wholly inside a limb is just tagged; one that
straddles the cut keeps the rest and gets a new copy (same name and material, appended after the existing surfaces,
so no surface index the packs already use moves). Then:

* stumps - one hidden surface per limb ("gore.<limb>") closing the body where the limb was. Elites, Grunts and
  Jackals use SPV3's own caps (b40_1.map's elite_new / grunt_new / jackal_new torsos carry them under a gore shader;
  their skeletons and bind poses are identical to Halo CE's, so they drop straight in, re-boned by name). Everyone
  else gets kitbashed caps: the limb's cut edge, found from the boundary of its triangles, closed with a domed fan
  (a closed limb mesh with no open edge gets a disc across the limb at the joint).
* texture - gore_<Char>.png: SPV3's own gore (wet, ropy flesh with a bone end), read from SPV3's bitmaps.map
  (HCE_SPV3_BITMAPS: the file, or the stem of its split pieces bitmaps.map.001, .002 ...; the level map holds only
  the header). The Kig-Yar's purple for Elites and Jackals, the Unggoy's teal for Grunts, and recoloured to the race's
  blood for the rest (Brute navy, Mgalekgolo / Slug Man orange, Yanme'e pale ichor). SPV3's stumps keep SPV3's UVs;
  the kitbashed caps put the bone end in the middle of the cut, or a patch of flesh for the boneless races (Hunters,
  Slug Men, Drones). Without bitmaps.map a stand-in texture is drawn instead.
* gibs - <Char>_gib_<limb>.iqm: the severed limb, static and centred on itself, with a cap on its cut end. Its
  surface list mirrors the body's (empty where unused) so a gib drawn with the dead enemy's own MODELDEF wears that
  enemy's skins (rank colours, hidden armour and all); the cap sits on the limb's stump surface index.
* json 'gore': per limb the surfaces to hide (limb parts, plus a gun or shield held by that limb), the stump surface,
  the gib model and the limb's centre (Halo units, model space); 'tex' the gore texture. build_pack.py turns it into
  HCE_SeverLimb (the API's HCE_Dismember picks the limbs on a hard kill).
Surfaces: UZDoom draws at most 32 per model. A stray triangle or two of a limb stays on the body; a surface left empty
gives its slot to the limb; the Brute (29 surfaces) loses only its head, and its guns' 2-triangle slivers are pruned.
A pristine copy (<Char>_nogore.iqm / .json) is kept, so re-running starts from the extractor's output.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, shutil
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from hce_paths import OUT
SPV3_B40 = os.environ.get('HCE_SPV3_B40', 'b40_1.map')      # SPV3's b40_1.map (PC/MCC cache): the Elite/Grunt/Jackal stump caps
SPV3_BITMAPS = os.environ.get('HCE_SPV3_BITMAPS', 'bitmaps.map')   # SPV3's bitmaps.map (or the stem of its .001, .002 ... pieces)


# char -> blood colour and texture style, spv3 model (or none: kitbashed caps), limbs {name: root bone (subtree)}
GORE = {
    'Elite':        dict(blood='3A1E8C', style='bone', spv3='elite_new', limbs={'head': 'bip01 neck', 'larm': 'bip01 l upperarm', 'rarm': 'bip01 r upperarm'}),
    'EliteSpecial': dict(blood='3A1E8C', style='bone', spv3='elite_new', limbs={'head': 'bip01 neck', 'larm': 'bip01 l upperarm', 'rarm': 'bip01 r upperarm'}),
    'EliteRifle':   dict(blood='3A1E8C', style='bone', spv3='elite_new', limbs={'head': 'bip01 neck', 'larm': 'bip01 l upperarm', 'rarm': 'bip01 r upperarm'}),
    'Grunt':        dict(blood='40C8D0', style='bone', spv3='grunt_new', limbs={'head': 'bip01 head', 'larm': 'bip01 l upperarm', 'rarm': 'bip01 r upperarm'},
                         regions={'back': ('backpack', 'bip01 spine1')}),
    'GruntSpecOps': dict(blood='40C8D0', style='bone', spv3='grunt_new', limbs={'head': 'bip01 head', 'larm': 'bip01 l upperarm', 'rarm': 'bip01 r upperarm'},
                         regions={'back': ('backpack', 'bip01 spine1')}),
    'Jackal':       dict(blood='4A2A9A', style='bone', spv3='jackal_new', limbs={'head': 'bip01 head', 'larm': 'bip01 l clavicle', 'rarm': 'bip01 r clavicle'}),
    'JackalMajor':  dict(blood='4A2A9A', style='bone', spv3='jackal_new', limbs={'head': 'bip01 head', 'larm': 'bip01 l clavicle', 'rarm': 'bip01 r clavicle'}),
    # kitbashed
    'H2Jackal':     dict(style='bone', blood='4A2A9A', limbs={'head': 'head', 'larm': 'l_upperarm', 'rarm': 'r_upperarm'}),
    'Brute':        dict(style='bone', blood='161C40', prune=True, limbs={'head': 'head'}),   # 32-surface limit: head only
    'Hunter':       dict(style='worm', blood='FF8C1A', limbs={'head': 'frame head', 'larm': 'bip01 l upperarm', 'rarm': 'bip01 r upperarm'}),  # the cannon arm, the shield arm
    'Drone':        dict(style='insect', blood='DDF0D2', limbs={'head': 'head', 'larm': 'l_upperarm', 'rarm': 'r_upperarm'}),
    'SlugMan':      dict(style='worm', blood='FF8C1A', limbs={'head': 'Bip01 Head', 'larm': 'Bip01 L UpperArm', 'rarm': 'Bip01 R UpperArm'}),
}
# SPV3's gore textures (in its bitmaps.map, not the level maps): the Kig-Yar's (purple, also on SPV3's Elites) and the
# Unggoy's (teal). Each is wet, ropy flesh with a bone end in one corner (BONE: centre and radius in UV).
SPV3_GORE_BMP = {'jackal gore': r'characters\jackal_new\bitmaps\jackal gore', 'grunt_gore': r'characters\grunt_new\bitmaps\grunt_gore'}
BONE = ((0.231, 0.199), 0.124)
FLESH = (0.66, 0.68)                  # a stretch of flesh well clear of the bone, for the boneless races' caps
# char -> (SPV3 gore texture, recolour to the race's blood?, cap centred on the bone?)
GORE_TEX = {'Elite': ('jackal gore', False, True), 'EliteSpecial': ('jackal gore', False, True), 'EliteRifle': ('jackal gore', False, True),
            'Grunt': ('grunt_gore', False, True), 'GruntSpecOps': ('grunt_gore', False, True),
            'Jackal': ('jackal gore', False, True), 'JackalMajor': ('jackal gore', False, True), 'H2Jackal': ('jackal gore', False, True),
            'Brute': ('jackal gore', True, True), 'Hunter': ('grunt_gore', True, False), 'SlugMan': ('grunt_gore', True, False),
            'Drone': ('grunt_gore', True, False)}
SPV3_MODEL = {'elite_new': r'characters\elite_new\elite_new', 'grunt_new': r'characters\grunt_new\grunt_new',
              'jackal_new': r'characters\jackal_new\jackal_new'}

_spv3 = None
def spv3():
    global _spv3
    if _spv3 is None:
        from pcmap import PCMap, gbx_geometry
        import halomodel as hm
        m = PCMap(SPV3_B40)
        hm.Model.geometry = lambda s, gi: gbx_geometry(s.m, s.geoms[gi].addr)
        _spv3 = (m, hm)
    return _spv3


def _noise(rng, n, scale, aniso=1.0):
    """tileable smooth noise in [0,1]: white noise low-passed in the frequency domain (aniso > 1 stretches it along x)"""
    w = rng.standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None]; fx = np.fft.fftfreq(n)[None, :]
    f = np.sqrt((fx / aniso) ** 2 + fy ** 2) * n / scale
    a = np.real(np.fft.ifft2(np.fft.fft2(w) * np.exp(-f * f)))
    return (a - a.min()) / max(a.max() - a.min(), 1e-9)


def _bitmaps_read(off, n):
    """bytes from SPV3's bitmaps.map, whole or split into numbered 100 MB pieces (bitmaps.map.001, .002 ...)"""
    if os.path.exists(SPV3_BITMAPS):
        with open(SPV3_BITMAPS, 'rb') as f: f.seek(off); return f.read(n)
    CH = 104857600; out = b''
    while n > 0:
        k, o = divmod(off, CH)
        with open(f'{SPV3_BITMAPS}.{k + 1:03d}', 'rb') as f: f.seek(o); b = f.read(min(n, CH - o))
        if not b: raise EOFError(off)
        out += b; off += len(b); n -= len(b)
    return out


def spv3_gore_image(src):
    """SPV3's gore bitmap (its pixels live in bitmaps.map; the level map only holds the header), or None"""
    from bitmaps import decode
    m, _ = spv3()
    t = next(t for t in m.tags if t['cls'] == 'bitm' and t['name'] == SPV3_GORE_BMP[src])
    c, p = m.reflexive(t['data'] + 0x60)
    _, w, h, _, _, fmt, fl, _, _, _, _, poff, psz = m.u('4s6h2h2hiii', p)[:13]
    try: d = _bitmaps_read(poff, psz)
    except (OSError, EOFError): return None
    return decode(d, 0, w, h, fmt, fl).convert('RGB')


def recolour(im, blood):
    """SPV3's gore in another race's blood: the flesh's shading carried onto the new colour, the bone kept"""
    a = np.asarray(im).astype(float) / 255.0
    mx, mn = a.max(2), a.min(2)
    bone = np.clip(((mx - mn) / np.maximum(mx, 1e-3) - 0.45) / -0.2, 0, 1) * np.clip((mx - 0.45) / 0.15, 0, 1)
    lum = a @ np.array([0.3, 0.55, 0.15]); lum = lum / max(np.percentile(lum, 98), 1e-3)
    col = np.array([int(blood[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    col = col * max(1.0, 0.6 / max(col.max(), 1e-3))        # very dark bloods (the Brute's navy) lifted to read as colour
    flesh = col[None, None] * (0.2 + 1.45 * lum[..., None]) + (lum[..., None] ** 4) * 0.3
    out = flesh * (1 - bone[..., None]) + a * bone[..., None]
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def cap_uv_to_spv3(uv, on_bone):
    """kitbashed caps' planar UVs (centre 0.5, rim 0.42) onto SPV3's texture: the bone end in the middle of the cut,
    or (boneless races) a patch of flesh"""
    if on_bone: c, k = np.array(BONE[0]), BONE[1] / 0.35 / 0.42     # the bone fills about a third of the cut
    else: c, k = np.array(FLESH), 0.3 / 0.42
    return c + (uv - 0.5) * k


def gore_texture(blood, style, n=256, seed=7):
    """our own stump texture, drawn for the caps' planar UVs (the cut centred at (0.5, 0.5), the rim at radius ~0.42):
    'bone' - a bone end (with marrow) in wet, fibrous flesh, a ring of the race's blood darkening to the skin edge;
    'worm' - the Mgalekgolo's cut colony: a tangle of orange worms, no bone;
    'insect' - the Yanme'e's chitin rim around pale, glistening ichor and torn tissue.
    SPV3's own stump textures live in its external bitmaps.map, which isn't part of b40_1.map."""
    rng = np.random.default_rng(seed)
    col = np.array([int(blood[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    y, x = np.mgrid[0:n, 0:n] / n
    dx, dy = x - 0.5, y - 0.5
    r = np.sqrt(dx * dx + dy * dy) / 0.42; th = np.arctan2(dy, dx)
    fine = _noise(rng, n, 40); mid = _noise(rng, n, 12); big = _noise(rng, n, 4)
    def ramp(a, b, v): return np.clip((v - a) / (b - a), 0, 1)
    if style == 'worm':
        # ridged noise: thin bright tubes where the field crosses its middle, packed tight
        w1 = 1 - np.abs(_noise(rng, n, 10, 3.0) * 2 - 1); w2 = 1 - np.abs(_noise(rng, n, 9, 0.35) * 2 - 1)
        worms = np.maximum(w1, w2) ** 6
        shade = 0.25 + 0.9 * worms + 0.15 * fine
        out = col[None, None] * shade[..., None] + (worms ** 4)[..., None] * 0.35
        out *= (1 - 0.5 * ramp(0.85, 1.05, r))[..., None]
    elif style == 'insect':
        ichor = col[None, None] * (0.55 + 0.45 * mid[..., None])
        tissue = np.array([0.55, 0.62, 0.35])[None, None] * (0.5 + 0.5 * fine[..., None])
        t = ramp(0.45, 0.75, mid + 0.25 * fine)[..., None]
        out = ichor * (1 - t) + tissue * t
        out += (ramp(0.8, 0.95, fine) ** 2)[..., None] * 0.35          # wet glints
        rim = ramp(0.78, 0.9, r + 0.08 * (big - 0.5))[..., None]
        out = out * (1 - rim) + np.array([0.18, 0.16, 0.08])[None, None] * (0.6 + 0.4 * fine[..., None]) * rim
    else:
        fib = _noise(rng, n, 14, 6.0)
        # fibres run around the cut: sample the stretched noise in polar coordinates
        pi = ((th / (2 * np.pi) + 0.5) * n * 3).astype(int) % n; pr = (np.clip(r, 0, 1.2) * n * 0.6).astype(int) % n
        fibres = fib[pr, pi]
        flesh = np.array([0.55, 0.12, 0.16]) * 0.5 + col * 0.5
        out = flesh[None, None] * (0.45 + 0.55 * fibres[..., None]) * (0.75 + 0.35 * mid[..., None])
        clot = ramp(0.55, 0.75, big * 0.6 + fine * 0.4)[..., None]
        out = out * (1 - clot) + col[None, None] * 0.55 * clot
        bone_r = 0.22 + 0.04 * (mid - 0.5)
        bone = ramp(bone_r + 0.03, bone_r, r)[..., None]
        bonec = np.array([0.86, 0.82, 0.7])[None, None] * (0.8 + 0.25 * fine[..., None])
        marrow = ramp(0.11, 0.08, r)[..., None]
        bonec = bonec * (1 - marrow) + (col * 0.6 + np.array([0.3, 0.1, 0.1]))[None, None] * marrow
        out = out * (1 - bone) + bonec * bone
        rim = ramp(0.8, 0.98, r + 0.1 * (big - 0.5))[..., None]
        out = out * (1 - rim) + col[None, None] * (0.35 + 0.3 * fine[..., None]) * rim
        out += (ramp(0.82, 0.97, fine) ** 2)[..., None] * 0.3 * (1 - bone)   # wet glints
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def planar_uv(pos, center, outward, radius):
    """the caps' UV layout: across the cut, centred at (0.5, 0.5), 'radius' at 0.42"""
    ax = np.cross(outward, [0, 0, 1.0])
    if np.linalg.norm(ax) < 1e-3: ax = np.cross(outward, [0, 1.0, 0])
    ax /= np.linalg.norm(ax); ay = np.cross(outward, ax)
    d = pos - center
    return np.stack([0.5 + 0.42 * (d @ ax) / radius, 0.5 + 0.42 * (d @ ay) / radius], 1)


def world_bind(joints):
    from preview import world
    return world([j[1] for j in joints], [(j[2], j[3]) for j in joints])


def subtree(joints, root):
    names = [j[0].lower() for j in joints]
    r = names.index(root.lower())
    out = {r}
    for _ in range(len(joints)):
        for i, j in enumerate(joints):
            if j[1] in out: out.add(i)
    return out


def dominant(m):
    k = np.argmax(m['bw'], axis=1)
    return m['bidx'][np.arange(len(k)), k]


def sub_mesh(m, tris):
    used = np.unique(tris)
    remap = np.full(len(m['pos']), -1); remap[used] = np.arange(len(used))
    return dict(name=m['name'], material=m['material'], pos=m['pos'][used], nrm=m['nrm'][used], uv=m['uv'][used],
                bidx=m['bidx'][used], bw=m['bw'][used], tris=remap[tris])


def boundary_loops(parts):
    """cut edges of a limb: edges (by rounded position) used by exactly one of its triangles, chained into loops"""
    key = {}
    pts = []
    def vid(p):
        k = tuple(np.round(p * 2000).astype(int))
        if k not in key: key[k] = len(pts); pts.append(p)
        return key[k]
    cnt = {}
    for m in parts:
        ids = [vid(p) for p in m['pos']]
        for t in m['tris']:
            a, b, c = ids[t[0]], ids[t[1]], ids[t[2]]
            for e in ((a, b), (b, c), (c, a)):
                if e[0] == e[1]: continue
                k = (min(e), max(e)); cnt[k] = cnt.get(k, 0) + 1
    edges = [k for k, n in cnt.items() if n == 1]
    adj = {}
    for a, b in edges: adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for s in adj:
        if s in seen: continue
        loop = [s]; seen.add(s); prev = None; cur = s
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; seen.add(cur); loop.append(cur)
        if len(loop) >= 3: loops.append(np.array([pts[i] for i in loop]))
    return loops


def cap_mesh(loops, joint_pos, outward, bone, material, dome=0.25):
    """kitbashed stump: each cut loop near the joint closed with a fan around a domed centre, facing 'outward'"""
    P, N, UV, T = [], [], [], []
    if not loops: return None
    near = min(np.linalg.norm(l.mean(0) - joint_pos) for l in loops)
    for loop in loops:
        c = loop.mean(0)
        # the cut is the loop at the joint (and any as close): open spikes and eye holes further out stay open
        if np.linalg.norm(c - joint_pos) > near * 1.6 + 0.02: continue
        r = np.linalg.norm(loop - c, axis=1).mean()
        if r < 1e-4: continue
        apex = c + outward * r * dome
        # planar UVs across the cap
        u = loop - c; ax = np.cross(outward, [0, 0, 1.0])
        if np.linalg.norm(ax) < 1e-3: ax = np.cross(outward, [0, 1.0, 0])
        ax /= np.linalg.norm(ax); ay = np.cross(outward, ax)
        base = len(P)
        P.append(apex); N.append(outward); UV.append((0.5, 0.5))
        for p in loop:
            d = p - c
            P.append(p); n = outward * 0.6 + d / max(np.linalg.norm(d), 1e-6) * 0.4; N.append(n / np.linalg.norm(n))
            UV.append((0.5 + 0.42 * (d @ ax) / r, 0.5 + 0.42 * (d @ ay) / r))
        n = len(loop)
        for i in range(n):
            a, b = base + 1 + i, base + 1 + (i + 1) % n
            tri = [base, a, b]
            fn = np.cross(P[a] - P[base], P[b] - P[base])
            if fn @ outward < 0: tri = [base, b, a]
            T.append(tri)
    if not T: return None
    P = np.array(P); n = len(P)
    bidx = np.zeros((n, 4), np.uint8); bidx[:, 0] = bone
    bw = np.zeros((n, 4), np.uint8); bw[:, 0] = 255
    T = np.array(T)[:, [0, 2, 1]]                 # the packs' winding (like the extractors')
    return dict(name='', material=material, pos=P, nrm=np.array(N), uv=np.array(UV), bidx=bidx, bw=bw, tris=T)


def spv3_region(spv, region):
    """SPV3's model region (its first permutation) as points: a limb that is no bone subtree (the Grunt's methane pack,
    rigged to the spine like the torso) is the body's triangles lying on it -- SPV3's grunt_new is Halo CE's Grunt
    with its pack split off as a severable region (bind poses identical)"""
    m, hm = spv3()
    t = next(t for t in m.tags if t['cls'] == 'mod2' and t['name'] == SPV3_MODEL[spv])
    M = hm.Model(m, t)
    r = next(r for r in M.regions if r['name'] == region)
    g = M.geometry(r['perms'][0]['geoms'][0])
    return np.concatenate([x['pos'] for x in g])


def spv3_stumps(spv, joints, limb_roots, points=None):
    """SPV3's torso stump caps, split per limb by the nearest limb root, re-boned onto our skeleton"""
    m, hm = spv3()
    t = next(t for t in m.tags if t['cls'] == 'mod2' and t['name'] == SPV3_MODEL[spv])
    M = hm.Model(m, t)
    sn = [n['name'].lower() for n in M.nodes]
    ours = {j[0].lower(): i for i, j in enumerate(joints)}
    W = world_bind(joints)
    roots = {L: np.array(W[ours[r.lower()]][0]) for L, r in limb_roots.items()}
    roots.update(points or {})                      # region limbs: their own centre
    out = {L: [] for L in roots}
    bms = M.base_map_scale
    for r in M.regions:
        perm = r['perms'][0]
        g = M.geometry(perm['geoms'][0])
        for x in g:
            if x['shader'] >= len(M.shaders) or 'gore' not in M.shaders[x['shader']]['name']: continue
            if r['name'] in limb_roots or r['name'].replace(' ', '') in ('leftarm', 'rightarm', 'head', 'backpack'): continue
            for tri in x['tris']:
                c = x['pos'][tri].mean(0)
                L = min(roots, key=lambda k: np.linalg.norm(roots[k] - c))
                out[L].append((x, tri))
    meshes = {}
    for L, items in out.items():
        if not items: continue
        P, N, UV, BI, BW, T = [], [], [], [], [], []
        for x, tri in items:
            for v in tri:
                P.append(x['pos'][v]); N.append(x['nrm'][v]); UV.append(x['uv'][v] * np.array(bms))
                nd, w = x['nodes'][v], x['w'][v]
                b0 = ours.get(sn[nd[0]], 0); b1 = ours.get(sn[nd[1]], 0)
                if nd[0] == nd[1]: BI.append((b0, 0, 0, 0)); BW.append((255, 0, 0, 0))
                else:
                    w0 = int(round(w[0] * 255)); BI.append((b0, b1, 0, 0)); BW.append((w0, 255 - w0, 0, 0))
            k = len(P); T.append((k - 3, k - 1, k - 2))
        meshes[L] = dict(name='', material='', pos=np.array(P), nrm=np.array(N), uv=np.array(UV),
                         bidx=np.array(BI, np.uint8), bw=np.array(BW, np.uint8), tris=np.array(T))
    return meshes


def process(char):
    cfg = GORE[char]
    od = f'{OUT}/models/{char}'
    ip, jp = f'{od}/{char}.iqm', f'{od}/{char}.json'
    pi, pj = f'{od}/{char}_nogore.iqm', f'{od}/{char}_nogore.json'
    if not os.path.exists(ip): print(char, 'missing'); return
    meta = json.load(open(jp))
    if 'gore' not in meta or not os.path.exists(pi):          # fresh extractor output: keep it
        shutil.copy(ip, pi); shutil.copy(jp, pj)
    meta = json.load(open(pj))
    joints, meshes, anims = read_iqm(pi)
    n0 = len(meshes)
    names = list(meta.get('mesh_names') or [m['name'] for m in meshes])
    mesh_weapon = list(meta.get('mesh_weapon') or [None] * n0)
    mesh_weapon += [None] * (n0 - len(mesh_weapon))
    if cfg.get('prune'):                       # a gun's sliver surfaces (a couple of triangles) give their slots up
        keep = [i for i, m in enumerate(meshes) if not (mesh_weapon[i] and len(m['tris']) <= 4)]
        assert meta.get('shield_surface') is None or meta['shield_surface'] == keep.index(meta['shield_surface'])
        meshes = [meshes[i] for i in keep]; names = [names[i] for i in keep]; mesh_weapon = [mesh_weapon[i] for i in keep]
    limbs = {L: subtree(joints, r) for L, r in cfg['limbs'].items()}
    regions = {}                                   # region limbs: points of SPV3's region, KD-searched
    if cfg.get('regions'):
        from scipy.spatial import cKDTree
        for L, (rg, bone) in cfg['regions'].items():
            pts = spv3_region(cfg['spv3'], rg)
            regions[L] = (cKDTree(pts), pts.mean(0), bone)
    W = world_bind(joints)
    jidx = {j[0].lower(): i for i, j in enumerate(joints)}
    gore = {L: dict(surfaces=[], parts=[]) for L in list(limbs) + list(regions)}
    new = []
    for si, m in enumerate(meshes):
        dom = dominant(m)
        lab = np.full(len(m['tris']), '', dtype=object)
        for L, bones in limbs.items():
            inl = np.isin(dom, list(bones))
            lab[inl[m['tris']].sum(1) >= 2] = L
        for L, (kd, _, _) in regions.items():          # every corner of the triangle on the region's surface
            if not len(m['tris']): continue
            d, _ = kd.query(m['pos'][m['tris']].reshape(-1, 3))
            on = (d.reshape(-1, 3) < 0.004).all(1) & (lab == '')
            lab[on] = L
        is_weapon = bool(mesh_weapon[si]) or 'shield' in names[si] or 'shield' in m['material'].lower()
        if is_weapon:
            # guns and shields aren't cut: they go (hidden) with the limb that holds them
            for L in gore:
                if (lab == L).sum() > len(lab) * 0.5: gore[L]['surfaces'].append(si)
            continue
        for L in gore:                             # a stray triangle or two isn't worth a surface: it stays put
            if 0 < (lab == L).sum() < 4: lab[lab == L] = ''
        Ls = [L for L in gore if (lab == L).any()]
        if not Ls: continue
        if all(lab == Ls[0]):                      # wholly inside one limb: tag it
            gore[Ls[0]]['surfaces'].append(si); gore[Ls[0]]['parts'].append(si); continue
        keep = (lab == '').any()
        for k, L in enumerate(Ls):
            nm = sub_mesh(m, m['tris'][lab == L])
            if not keep and k == 0:                # nothing left on the body: the first limb takes the original slot
                meshes[si] = nm; gore[L]['surfaces'].append(si); gore[L]['parts'].append(si)
            else: new.append((L, si, nm))
        if keep: meshes[si] = sub_mesh(m, m['tris'][lab == ''])
    for L, si, nm in new:
        meshes.append(nm); names.append(names[si]); mesh_weapon.append(None)
        gore[L]['surfaces'].append(len(meshes) - 1); gore[L]['parts'].append(len(meshes) - 1)
    # stumps
    tex = f'gore_{char}.png'
    src, recol, on_bone = GORE_TEX[char]
    gim = spv3_gore_image(src)
    if gim is not None:                                   # SPV3's own gore (recoloured for the other races)
        (recolour(gim, cfg['blood']) if recol else gim).resize((512, 512), Image.LANCZOS).save(f'{od}/{tex}')
    else:                                                 # no bitmaps.map: our own drawing
        print(char, 'SPV3 bitmaps.map not found: drawing the gore texture')
        gore_texture(cfg['blood'], cfg['style']).save(f'{od}/{tex}')
    stumps = spv3_stumps(cfg['spv3'], joints, cfg['limbs'], {L: r[1] for L, r in regions.items()}) if cfg.get('spv3') else {}
    gibs_cap = {}
    for L in gore:
        if L in regions:                          # a region limb: from its bone out to the region's centre
            root = jidx[regions[L][2].lower()]; par = root
            bone = np.array(W[root][0]); ctr_ = regions[L][1]
            out_dir = ctr_ - bone
            Pp = np.concatenate([meshes[i]['pos'] for i in gore[L]['parts']]) if gore[L]['parts'] else ctr_[None]
            jp_ = Pp[np.argmin((Pp - bone) @ (out_dir / max(np.linalg.norm(out_dir), 1e-6)))]   # where it meets the body
            pp = bone
        else:
            root = jidx[cfg['limbs'][L].lower()]
            jp_ = np.array(W[root][0]); par = joints[root][1]
            pp = np.array(W[par][0]) if par >= 0 else jp_ - np.array([0, 0, 0.1])
            kids = [i for i, j in enumerate(joints) if j[1] == root]
            if kids:                                  # along the limb: towards its first bone's end
                out_dir = np.mean([np.array(W[k][0]) for k in kids], 0) - jp_
            else:
                out_dir = jp_ - pp                    # from the body into the limb
            if np.linalg.norm(out_dir) < 1e-5: out_dir = jp_ - pp
        out_dir /= max(np.linalg.norm(out_dir), 1e-6)
        parts = [meshes[i] for i in gore[L]['parts']]
        loops = boundary_loops(parts)
        if L in stumps and len(stumps[L]['tris']) >= 6:
            st = stumps[L]; st['material'] = tex
            if gim is None:                               # SPV3's UVs only fit SPV3's texture
                rr = max(0.02, np.linalg.norm(st['pos'] - jp_, axis=1).max() * 0.8)
                st['uv'] = planar_uv(st['pos'], jp_, out_dir, rr)
            st['spv3'] = True
        else:
            st = cap_mesh(loops, jp_, out_dir, par if par >= 0 else root, tex)
        gcap = cap_mesh(loops, jp_, -out_dir, root, tex)
        if st is None:                                            # no clean cut edge: a small disc at the joint
            # a closed limb mesh pushed into the body (no open edge): a disc across the limb at the joint, as wide as it
            P = np.concatenate([m['pos'] for m in parts]) if parts else jp_[None]
            d = P - jp_; along = d @ out_dir
            near_ = np.abs(along) < max(0.02, np.percentile(np.abs(along), 15))
            rad = np.linalg.norm(d[near_] - along[near_, None] * out_dir, axis=1)
            rr = float(np.clip(np.percentile(rad, 60) if len(rad) else 0.03, 0.015, 0.1))
            ax = np.cross(out_dir, [0, 0, 1.0])
            if np.linalg.norm(ax) < 1e-3: ax = np.cross(out_dir, [0, 1.0, 0])
            ax /= np.linalg.norm(ax); ay = np.cross(out_dir, ax)
            ring = np.array([jp_ + rr * (np.cos(a) * ax + np.sin(a) * ay) for a in np.linspace(0, 2 * np.pi, 13)[:-1]])
            st = cap_mesh([ring], jp_, out_dir, par if par >= 0 else root, tex)
            gcap = gcap or cap_mesh([ring], jp_, -out_dir, root, tex)
        if gim is not None:
            if not st.pop('spv3', False): st['uv'] = cap_uv_to_spv3(st['uv'], on_bone)
            if gcap is not None: gcap['uv'] = cap_uv_to_spv3(gcap['uv'], on_bone)
        st.pop('spv3', None)
        st['name'] = f'gore.{L}'
        meshes.append(st); names.append(f'gore.{L}'); mesh_weapon.append(None)
        gore[L]['stub'] = len(meshes) - 1
        gibs_cap[L] = gcap
    # gibs: the body's surface list, only this limb's parts (centred) and its cap on the stump index
    for L in gore:
        P = np.concatenate([meshes[i]['pos'] for i in gore[L]['parts']]) if gore[L]['parts'] else np.zeros((1, 3))
        ctr = P.mean(0)
        gm = []
        for si, m in enumerate(meshes):
            if si in gore[L]['parts']: src = m
            elif si == gore[L]['stub'] and gibs_cap[L] is not None: src = dict(gibs_cap[L], name=f'gore.{L}')
            else:
                gm.append(dict(name=names[si], material=m['material'], pos=np.zeros((0, 3)), nrm=np.zeros((0, 3)), uv=np.zeros((0, 2)),
                               bidx=np.zeros((0, 4), np.uint8), bw=np.zeros((0, 4), np.uint8), tris=np.zeros((0, 3), int)))
                continue
            n = len(src['pos'])
            bidx = np.zeros((n, 4), np.uint8); bw = np.zeros((n, 4), np.uint8); bw[:, 0] = 255
            gm.append(dict(name=names[si], material=src['material'], pos=src['pos'] - ctr, nrm=src['nrm'], uv=src['uv'],
                           bidx=bidx, bw=bw, tris=src['tris']))
        bind = [[(j[2], j[3], (1.0, 1.0, 1.0)) for j in joints]]
        gfile = f'{char}_gib_{L}.iqm'
        write_iqm(f'{od}/{gfile}', joints, gm, [dict(name='bind', fps=30.0, loop=True, frames=bind)])
        gore[L]['gib'] = gfile; gore[L]['center'] = [float(x) for x in ctr]
        del gore[L]['parts']
    assert len(meshes) <= 32, f'{char}: {len(meshes)} surfaces (UZDoom draws at most 32)'
    info = meta.get('anims', {})
    alist = [dict(name=n, fps=30.0, loop=bool(info.get(n, {}).get('loop', True)), frames=[[(t, q, s) for t, q, s in f] for f in fr])
             for n, fr in anims.items()]
    size = write_iqm(ip, joints, meshes, alist)
    meta.update(meshes=[m['material'] for m in meshes], mesh_names=names, mesh_weapon=mesh_weapon, iqm_bytes=size,
                gore=dict(limbs=gore, tex=tex))
    json.dump(meta, open(jp, 'w'), indent=1)
    print(f'{char:13s} surfaces {n0} -> {len(meshes)}  limbs ' +
          ', '.join(f"{L}: hide {len(g['surfaces'])} stub {g['stub']}" for L, g in gore.items()))


if __name__ == '__main__':
    for c in (sys.argv[1:] or GORE):
        if c in GORE: process(c)
