"""Forerunner guns of the pack's own: original models and textures made here (no game's model), Forerunner in spirit:
angular dark-alloy cores, pale shell plates floating off them, orange hard light in their seams. For HDE's Forerunner
weapons, which had borrowed the nearest human or Covenant model.

    python3 forerunner_guns.py [name ...]      # -> out/weapons/m_<name>/{m_<name>.pkl, w_m_<name>_0.png}

Each gun is a few flat-sided parts, every part a side profile (x forward, z up, in hundredths of a world unit) pushed out
across y between two widths (`extrude`): a gun reads from the side, as Halo CE's do. They sit in Halo's weapon space as
every pkl does (+x the muzzle, +z up, +y the gun's left, the origin on the grip where the hand closes, world units).

One texture per gun, TEX square (`texture`), Halo CE's way: its light painted in. The upper part holds the side panels
(each material's side faces projected straight onto it, by their x and z: one picture of the gun's side, seams and
wear placed along it); below them the rim strips (the faces round each part's edge), lit by which way they face: a
bright strip for those facing up, a mid one for front, back and sides, a dark one for those facing down. Last a swatch
of hard light (orange, white-hot at its middle) for the glowing parts.
"""
import os, sys, pickle
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from hce_paths import OUT

TEX = 512
U = 0.01                          # profile units -> world units
# the materials: their side colour (top and bottom of the panel's gradient) and their rim strips' rows
ALLOY = dict(top=(78, 84, 96), bottom=(40, 43, 52))         # the core: dark blue-grey alloy
SHELL = dict(top=(176, 180, 186), bottom=(118, 122, 130))   # the shells: pale silver plate
GLOW = (255, 150, 40)
# texture layout (pixels): the side panels, the rim strips, the glow swatch
ALLOY_PANEL = (0, 0, 512, 200)
SHELL_PANEL = (0, 200, 512, 400)
STRIPS = {('alloy', 'up'): 404, ('alloy', 'mid'): 420, ('alloy', 'down'): 436,
          ('shell', 'up'): 452, ('shell', 'mid'): 468, ('shell', 'down'): 484}
STRIP_H = 12
GLOW_SWATCH = (448, 500, 504, 510)


def ear_clip(P):
    """triangles (index triples) filling the simple polygon P (counter-clockwise or not)"""
    P = np.asarray(P, float); n = len(P)
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
    idx = list(range(n)) if area > 0 else list(range(n))[::-1]
    out = []
    def inside(p, a, b, c):
        d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
        d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
        d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = P[i0], P[i1], P[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 1e-9: continue
            if any(inside(P[j], a, b, c) for j in idx if j not in (i0, i1, i2)): continue
            out.append((i0, i1, i2)); idx.pop(k); break
        else: break
    if len(idx) == 3: out.append(tuple(idx))
    return out


class Gun:
    """the faces of a gun as they are added: corner positions, normals, uvs, one triangle per three corners"""
    def __init__(s, box):
        s.pos, s.nrm, s.uv = [], [], []
        s.box = box          # (x0, z0, x1, z1) profile units: the gun's side, mapped onto each side panel whole
    def tri(s, p, n, uv):
        s.pos.extend(p); s.nrm.extend([n] * 3); s.uv.extend(uv)
    def side_uv(s, mat, x, z):
        x0, z0, x1, z1 = s.box
        if mat == 'glow': return glow_uv(x, z)
        L, T, R, B = ALLOY_PANEL if mat == 'alloy' else SHELL_PANEL
        return ((L + (x - x0) / (x1 - x0) * (R - L)) / TEX, (T + (z1 - z) / (z1 - z0) * (B - T)) / TEX)
    def rim_uv(s, mat, facing, along, across):
        if mat == 'glow': return glow_uv(along, across)
        y = STRIPS[(mat, facing)]
        x0, _, x1, _ = s.box
        return ((4 + (along - x0) / (x1 - x0) * (TEX - 8)) / TEX, (y + 2 + across * (STRIP_H - 4)) / TEX)
    def extrude(s, prof, y0, y1, mat):
        """the profile pushed across y from y0 to y1 (y0 < y1): both sides and the rim"""
        P = np.asarray(prof, float)
        tris = ear_clip(P)
        for y, n, flip in ((y1, (0, 1, 0), False), (y0, (0, -1, 0), True)):
            for t in tris:
                t = t if not flip else t[::-1]
                # (looking from +y the profile's x runs one way, z up: counter-clockwise in (x, z) faces -y; so +y flips)
                t = t[::-1]
                if flip: t = t[::-1][::-1]
                pts = [(P[i, 0] * U, y * U, P[i, 1] * U) for i in t]
                s.tri(pts, n, [s.side_uv(mat, P[i, 0], P[i, 1]) for i in t])
        n = len(P)
        area = 0.5 * sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            e = b - a; ln = np.hypot(*e)
            if ln < 1e-9: continue
            out = np.array([e[1], -e[0]]) / ln * (1 if area > 0 else -1)      # (the outward normal in x, z)
            nn = (out[0], 0.0, out[1])
            facing = 'up' if out[1] > 0.5 else 'down' if out[1] < -0.5 else 'mid'
            q = [(a[0] * U, y0 * U, a[1] * U), (b[0] * U, y0 * U, b[1] * U), (b[0] * U, y1 * U, b[1] * U), (a[0] * U, y1 * U, a[1] * U)]
            uv = [s.rim_uv(mat, facing, a[0], 0), s.rim_uv(mat, facing, b[0], 0), s.rim_uv(mat, facing, b[0], 1), s.rim_uv(mat, facing, a[0], 1)]
            for tri in ((0, 1, 2), (0, 2, 3)):
                if np.dot(np.cross(np.subtract(q[tri[1]], q[tri[0]]), np.subtract(q[tri[2]], q[tri[0]])), nn) < 0: tri = tri[::-1]
                s.tri([q[k] for k in tri], nn, [uv[k] for k in tri])
    def mirror(s, prof, y0, y1, mat):
        """a pair: the profile at y0..y1 and at -y1..-y0 (a part on both sides of the core)"""
        s.extrude(prof, y0, y1, mat); s.extrude(prof, -y1, -y0, mat)


def glow_uv(a, b):
    L, T, R, B = GLOW_SWATCH
    return (((L + R) / 2) / TEX, ((T + B) / 2) / TEX)


def side_tris_fix(g):
    """the side faces' windings made to agree with their normals (the profile may be drawn either way round)"""
    P = np.asarray(g.pos).reshape(-1, 3, 3); N = np.asarray(g.nrm).reshape(-1, 3, 3)[:, 0]; UV = np.asarray(g.uv).reshape(-1, 3, 2)
    cr = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); bad = (cr * N).sum(1) < 0
    P[bad] = P[bad][:, ::-1]; UV[bad] = UV[bad][:, ::-1]
    g.pos, g.uv = list(P.reshape(-1, 3)), list(UV.reshape(-1, 2))


# ---------------------------------------------------------------- the Light Rifle
# a long precision rifle: a dark alloy core from the stock's fin to a square hard-light frame at the muzzle, two pale
# shell shards floating off each side over its middle (a lower pair under them), a low sight on top with a lit lens,
# the grip slanting back under it with a hard-light guard, hard-light seams along the shells and the core
def light_rifle():
    g = Gun((-14, -4, 27, 10))
    core = [(-14, 3.4), (-12, 6.8), (-4, 7.4), (4, 7.6), (13, 7.0), (21, 5.8), (24.5, 5.4), (24.5, 2.6), (19, 2.2), (9, 2.0),
            (5, 1.2), (0, 1.2), (-6, 2.0), (-10, 1.2), (-14, 1.8)]
    g.extrude(core, -0.95, 0.95, 'alloy')
    g.extrude([(-9, 7.0), (6, 8.2), (15, 7.6), (19, 6.0), (6, 7.2)], -0.55, 0.55, 'alloy')            # the spine's ridge
    g.extrude([(-13.4, 2.6), (-11.8, 6.0), (-7.5, 6.5), (-8.6, 2.8)], -1.2, 1.2, 'shell')            # the stock's pale inset
    g.mirror([(-1, 8.4), (9, 8.8), (18, 7.2), (22.5, 5.6), (14, 4.9), (3, 5.3)], 1.2, 1.7, 'shell')     # the upper shards
    g.mirror([(8, 4.0), (15, 4.2), (20.5, 2.8), (17, 1.6), (10, 1.8)], 1.2, 1.6, 'shell')              # the lower shards
    g.mirror([(1.5, 7.2), (14, 6.8), (14.4, 6.4), (2, 6.8)], 1.7, 1.78, 'glow')                       # the shards' seams
    g.mirror([(10, 2.6), (16, 2.8), (16.3, 2.5), (10.2, 2.3)], 1.6, 1.68, 'glow')
    g.mirror([(-11, 4.4), (-4, 4.8), (-4, 4.4), (-11, 4.0)], 0.95, 1.03, 'glow')                       # the stock's line
    g.extrude([(2, 7.5), (8, 7.5), (9.4, 9.0), (3.6, 9.4)], -0.55, 0.55, 'alloy')                     # the sight
    g.extrude([(8.8, 8.2), (9.4, 8.1), (9.6, 8.9), (9.0, 9.0)], -0.4, 0.4, 'glow')                    # its lens
    g.extrude([(-1.2, 1.4), (2.4, 1.4), (0.2, -3.4), (-3.0, -3.2)], -0.75, 0.75, 'alloy')             # the grip
    g.extrude([(2.2, -2.4), (6.6, 1.2), (6.6, 1.6), (1.6, -1.8)], -0.22, 0.22, 'glow')                # its guard
    # the muzzle's square frame: bars round a lit pane
    for bar in ([(24.5, 5.6), (26.6, 5.6), (26.6, 6.2), (24.5, 6.2)], [(24.5, 2.0), (26.6, 2.0), (26.6, 2.6), (24.5, 2.6)]):
        g.extrude(bar, -1.25, 1.25, 'shell')
    g.mirror([(24.5, 2.0), (26.6, 2.0), (26.6, 6.2), (24.5, 6.2)], 0.95, 1.25, 'shell')
    g.extrude([(25.3, 2.6), (25.7, 2.6), (25.7, 5.6), (25.3, 5.6)], -0.95, 0.95, 'glow')
    side_tris_fix(g)
    return g


def texture(g):
    """the gun's texture (see the module's note): its side panels painted as the gun's side, seams where its parts
    meet, wear on the edges"""
    rng = np.random.default_rng(7)
    im = Image.new('RGB', (TEX, TEX), (30, 30, 34)); d = ImageDraw.Draw(im)
    for (L, T, R, B), m in ((ALLOY_PANEL, ALLOY), (SHELL_PANEL, SHELL)):
        for y in range(T, B):
            k = (y - T) / (B - T - 1)
            d.line([(L, y), (R - 1, y)], fill=tuple(int(m['top'][c] * (1 - k) + m['bottom'][c] * k) for c in range(3)))
        # panel seams: straight, far apart, dark with a lit edge beside (Forerunner plating), one groove along
        for x in range(L + 70, R, 96):
            d.line([(x, T + 4), (x, B - 4)], fill=tuple(int(c * 0.55) for c in m['bottom']), width=2)
            d.line([(x + 2, T + 4), (x + 2, B - 4)], fill=tuple(min(255, int(c * 1.15)) for c in m['top']), width=1)
        y = T + (B - T) * 2 // 5
        d.line([(L, y), (R, y)], fill=tuple(int(c * 0.7) for c in m['bottom']), width=1)
    for (mat, facing), y in STRIPS.items():
        m = ALLOY if mat == 'alloy' else SHELL
        k = {'up': 1.25, 'mid': 0.85, 'down': 0.5}[facing]
        base = m['top'] if facing == 'up' else m['bottom']
        col = tuple(min(255, int(c * k)) for c in base)
        d.rectangle((0, y, TEX - 1, y + STRIP_H - 1), fill=col)
        d.line([(0, y + 1), (TEX - 1, y + 1)], fill=tuple(min(255, int(c * 1.25)) for c in col))       # (a lit bevel)
    L, T, R, B = GLOW_SWATCH
    d.rectangle((L, T, R, B), fill=GLOW)
    d.rectangle((L + 8, T + 2, R - 8, B - 2), fill=(255, 185, 80))       # (hotter at its middle, still orange)
    a = np.asarray(im, np.float32)
    grain = rng.normal(0, 4, a.shape[:2])[..., None]
    a[:400] = np.clip(a[:400] + grain[:400], 0, 255)
    return Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.SMOOTH_MORE) if False else Image.fromarray(a.astype(np.uint8))


GUNS = {'light_rifle': light_rifle}
CREDIT = 'an original Forerunner-style gun made for the pack (forerunner_guns.py)'


def build(names=None):
    for name, fn in GUNS.items():
        if names and name not in names: continue
        g = fn(); wid = 'm_' + name
        d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
        for f in os.listdir(d): os.remove(os.path.join(d, f))
        mat = f'w_{wid}_0.png'; texture(g).save(f'{d}/{mat}')
        pos = np.asarray(g.pos, float); n = len(pos)
        mesh = dict(material=mat, pos=pos, nrm=np.asarray(g.nrm, float), uv=np.asarray(g.uv, float), tris=np.arange(n).reshape(-1, 3))
        pickle.dump(dict(id=wid, tag=CREDIT, meshes=[mesh]), open(f'{d}/{wid}.pkl', 'wb'))
        print(wid, 'tris', n // 3, 'bounds', pos.min(0).round(3), pos.max(0).round(3), '->', d)


if __name__ == '__main__':
    build(sys.argv[1:] or None)
