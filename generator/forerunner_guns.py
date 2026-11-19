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
bright strip for those facing up, a mid one for front, back and sides, a dark one for those facing down. The glowing
parts are a second mesh on a texture of one colour, each gun's own (its first-person HDE gun's hard light).
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
ALLOY = dict(top=(82, 83, 86), bottom=(40, 41, 44))         # the core and frame: dark gunmetal
SHELL = dict(top=(172, 174, 176), bottom=(112, 114, 118))   # the shells: grey plate (HDE's first-person guns' greys)
# hard light, per gun, as HDE's first-person gun glows (sampled from its sprites): blue for the Light Rifle and the Boltshot, violet for
# the Scattershot, teal for the Binary Rifle. The glowing faces are a mesh of their own on a texture of
# their own (w_m_<gun>_1.png), so the multiplayer pack can light them in this colour by a shader whatever Doom's palette
# and the player's colour do to the texture (HDE-Maps' tools/ce_guns.py)
LIGHT_RIFLE_LIGHT = (70, 160, 225)
SCATTERSHOT_LIGHT = (200, 80, 230)
BINARY_LIGHT = (85, 240, 215)
BOLTSHOT_LIGHT = (90, 130, 220)
# texture layout (pixels): the side panels, the rim strips, the glow swatch
ALLOY_PANEL = (0, 0, 512, 200)
SHELL_PANEL = (0, 200, 512, 400)
STRIPS = {('alloy', 'up'): 404, ('alloy', 'mid'): 420, ('alloy', 'down'): 436,
          ('shell', 'up'): 452, ('shell', 'mid'): 468, ('shell', 'down'): 484}
STRIP_H = 12


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
        s.pos, s.nrm, s.uv, s.mat = [], [], [], []
        s.box = box          # (x0, z0, x1, z1) profile units: the gun's side, mapped onto each side panel whole
    def tri(s, p, n, uv, mat=''):
        s.pos.extend(p); s.nrm.extend([n] * 3); s.uv.extend(uv); s.mat.append(mat)
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
                s.tri(pts, n, [s.side_uv(mat, P[i, 0], P[i, 1]) for i in t], mat)
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
                s.tri([q[k] for k in tri], nn, [uv[k] for k in tri], mat)
    def mirror(s, prof, y0, y1, mat):
        """a pair: the profile at y0..y1 and at -y1..-y0 (a part on both sides of the core)"""
        s.extrude(prof, y0, y1, mat); s.extrude(prof, -y1, -y0, mat)


def glow_uv(a, b):
    return (0.5, 0.5)       # (the glow texture is one colour)


def side_tris_fix(g):
    """the side faces' windings made to agree with their normals (the profile may be drawn either way round)"""
    P = np.asarray(g.pos).reshape(-1, 3, 3); N = np.asarray(g.nrm).reshape(-1, 3, 3)[:, 0]; UV = np.asarray(g.uv).reshape(-1, 3, 2)
    cr = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); bad = (cr * N).sum(1) < 0
    P[bad] = P[bad][:, ::-1]; UV[bad] = UV[bad][:, ::-1]
    g.pos, g.uv = list(P.reshape(-1, 3)), list(UV.reshape(-1, 2))


# ---------------------------------------------------------------- the Light Rifle
# a long precision rifle in the Forerunner way: stacked plates with open gaps between them (a pale upper shell, a dark
# core, a lower plate), the hard light glowing in the gaps rather than painted on; the shell and the lower plate run past
# the core into a split muzzle of two tines; an open frame for the stock and grip (a loop of bars round empty space); a
# sight shard floating over the shell; a lit node on the core
def light_rifle():
    g = Gun((-14, -4.2, 26.5, 10.2))
    g.extrude([(-9, 6.0), (-7.6, 8.2), (12, 8.2), (17, 7.5), (26.5, 6.9), (24.5, 6.0)], -1.05, 1.05, 'shell')    # upper shell
    g.mirror([(-6, 6.5), (16, 6.5), (16.6, 6.9), (-5.6, 6.9)], 1.05, 1.15, 'alloy')                              # its dark inset line
    g.extrude([(-6, 3.0), (-5, 5.4), (18, 5.4), (21, 4.4), (20, 2.6), (-4, 2.6)], -0.8, 0.8, 'alloy')            # the core
    g.extrude([(-3, 5.55), (16, 5.55), (16, 5.85), (-3, 5.85)], -0.55, 0.55, 'glow')                             # light in the upper gap
    g.extrude([(4, 1.0), (6, 2.0), (21, 2.0), (26, 1.7), (24, 1.0)], -0.95, 0.95, 'shell')                     # lower plate
    g.extrude([(7, 2.15), (18, 2.15), (18, 2.45), (7, 2.45)], -0.5, 0.5, 'glow')                                 # light in the lower gap
    g.mirror([(10, 1.35), (20, 1.35), (20, 1.6), (10, 1.6)], 0.95, 1.02, 'glow')                                  # the lower plate's side line
    g.mirror([(0.2, 3.4), (1.2, 3.4), (1.6, 4.0), (1.2, 4.6), (0.2, 4.6), (-0.2, 4.0)], 0.8, 0.9, 'glow')         # the core's node
    g.mirror([(-0.6, 3.1), (2.0, 3.1), (2.6, 4.0), (2.0, 4.9), (-0.6, 4.9), (-1.2, 4.0)], 0.8, 0.85, 'shell')      # its ring
    g.extrude([(-5.2, 5.3), (-3.2, 5.3), (-3.6, 6.1), (-5.6, 6.1)], -0.6, 0.6, 'alloy')                          # struts: the shell's
    g.extrude([(18.6, 1.9), (20.2, 1.9), (20.4, 2.7), (18.8, 2.7)], -0.6, 0.6, 'alloy')                          # and the lower plate's
    # the open frame: the stock's top bar off the shell, the butt, the bar down to the grip, the grip, its guard
    g.extrude([(-14, 6.2), (-13, 7.2), (-7.6, 7.2), (-8.4, 6.2)], -0.75, 0.75, 'alloy')
    g.extrude([(-14, 6.2), (-12.9, 6.2), (-12.4, 1.2), (-13.6, 0.4)], -0.75, 0.75, 'alloy')
    g.extrude([(-13.6, 0.4), (-12.4, 1.2), (-2.2, -2.4), (-2.8, -3.6)], -0.7, 0.7, 'alloy')
    g.extrude([(-1.4, 2.7), (1.6, 2.7), (0.6, -3.6), (-2.8, -3.6)], -0.75, 0.75, 'alloy')
    g.extrude([(1.0, -1.8), (5.0, 1.0), (5.0, 1.5), (0.6, -1.0)], -0.3, 0.3, 'alloy')
    g.mirror([(-12.9, 4.6), (-12.6, 2.0), (-12.3, 2.0), (-12.6, 4.6)], 0.75, 0.82, 'glow')                      # a line down the butt
    # the sight: a shard floating over the shell, its lens lit
    g.extrude([(2, 8.8), (9, 8.8), (10.2, 9.6), (3.4, 10.2)], -0.5, 0.5, 'shell')
    g.extrude([(9.2, 8.95), (9.8, 8.95), (10.0, 9.5), (9.5, 9.6)], -0.35, 0.35, 'glow')
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
        # grooves as the Forerunners cut them: long runs along the gun, stepping up or down at 45 degrees, dark with a
        # lit edge above
        rng2 = np.random.default_rng(11 if m is ALLOY else 13)
        for k in range(5):
            y = T + 18 + k * (B - T - 36) // 4; x = L + int(rng2.integers(0, 60)); pts = [(x, y)]
            while x < R:
                run = int(rng2.integers(50, 140)); x += run; pts.append((x, y))
                step = int(rng2.choice([-1, 1])) * int(rng2.integers(6, 14)); y = int(np.clip(y + step, T + 8, B - 8)); x += abs(step); pts.append((x, y))
            d.line(pts, fill=tuple(int(c * 0.55) for c in m['bottom']), width=2)
            d.line([(px, py - 2) for px, py in pts], fill=tuple(min(255, int(c * 1.12)) for c in m['top']), width=1)
    for (mat, facing), y in STRIPS.items():
        m = ALLOY if mat == 'alloy' else SHELL
        k = {'up': 1.25, 'mid': 0.85, 'down': 0.5}[facing]
        base = m['top'] if facing == 'up' else m['bottom']
        col = tuple(min(255, int(c * k)) for c in base)
        d.rectangle((0, y, TEX - 1, y + STRIP_H - 1), fill=col)
        d.line([(0, y + 1), (TEX - 1, y + 1)], fill=tuple(min(255, int(c * 1.25)) for c in col))       # (a lit bevel)
    a = np.asarray(im, np.float32)
    grain = rng.normal(0, 4, a.shape[:2])[..., None]
    a[:400] = np.clip(a[:400] + grain[:400], 0, 255)
    return Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.SMOOTH_MORE) if False else Image.fromarray(a.astype(np.uint8))


# ---------------------------------------------------------------- the Scattershot
# a short heavy gun for close quarters: a thick pale shell over a dark core with hard light in the gap between, a tall
# pale emitter block at the front (two slanted slits of light down each side, a lit face), a handguard under it, three
# lit cells in the core's side, and the open frame shorter than the rifle's
def scattershot():
    g = Gun((-11, -4.4, 20, 9.6))
    g.extrude([(-7, 6.0), (-5, 8.6), (8, 9.2), (15, 8.4), (17.5, 6.8), (16, 5.8), (4, 5.8)], -1.35, 1.35, 'shell')   # the shell
    g.extrude([(-6, 2.4), (-6, 5.4), (14, 5.4), (17, 4.6), (17, 2.0), (2, 2.0)], -1.05, 1.05, 'alloy')              # the core
    g.extrude([(-2, 5.45), (13, 5.45), (13, 5.75), (-2, 5.75)], -0.8, 0.8, 'glow')                                   # light in the gap
    g.extrude([(-4.6, 5.3), (-3.0, 5.3), (-3.3, 6.1), (-4.9, 6.1)], -0.7, 0.7, 'alloy')                              # a strut
    g.extrude([(15.4, 1.2), (19.0, 1.6), (19.6, 8.0), (16.4, 8.8), (15.8, 7.0)], -1.6, 1.6, 'shell')               # the emitter
    for x in (16.4, 17.6):
        g.mirror([(x, 2.4), (x + 0.6, 2.4), (x + 1.1, 7.4), (x + 0.5, 7.4)], 1.6, 1.68, 'glow')                   # its slits
    g.extrude([(19.1, 2.2), (19.4, 2.2), (19.9, 7.4), (19.6, 7.4)], -1.2, 1.2, 'glow')                               # its face
    g.extrude([(5, 0.6), (7, 1.9), (15, 1.9), (15.5, 0.4), (8, -0.6)], -1.2, 1.2, 'shell')                          # the handguard
    for x in (3.0, 5.0, 7.0):
        g.mirror([(x, 3.2), (x + 1.2, 3.2), (x + 1.2, 4.3), (x, 4.3)], 1.05, 1.13, 'glow')                          # the cells
    g.extrude([(-11, 6.0), (-10, 7.0), (-5, 7.0), (-5.4, 6.0)], -0.75, 0.75, 'alloy')                              # the frame
    g.extrude([(-11, 6.0), (-10, 6.0), (-9.6, 1.6), (-10.8, 1.0)], -0.75, 0.75, 'alloy')
    g.extrude([(-10.8, 1.0), (-9.6, 1.6), (-2.2, -2.6), (-2.8, -3.8)], -0.7, 0.7, 'alloy')
    g.extrude([(-1.4, 2.2), (1.6, 2.2), (0.6, -3.8), (-2.8, -3.8)], -0.75, 0.75, 'alloy')                          # the grip
    g.extrude([(1.0, -2.0), (5.0, 0.6), (5.0, 1.1), (0.6, -1.2)], -0.3, 0.3, 'alloy')                              # its guard
    side_tris_fix(g)
    return g


# ---------------------------------------------------------------- the Binary Rifle
# a long sniper: a dark body, two long pale rails running out past it with an open gap between them and a line of hard
# light along the gap, small brackets near the rails' tips holding a lit node between them, slashes of light down the
# body's side, a long sight shard on one thin mount, and a long skeletal stock (a triangle of bars) with a line of light
def binary_rifle():
    g = Gun((-16, -4.4, 34, 10.2))
    g.extrude([(-8, 2.6), (-7, 6.0), (10, 6.4), (13, 5.2), (13, 2.4), (2, 2.0)], -0.9, 0.9, 'alloy')               # the body
    g.extrude([(6, 6.0), (8, 7.4), (26, 7.0), (34, 6.5), (31, 5.9), (14, 5.9)], -0.85, 0.85, 'shell')              # upper rail
    g.extrude([(8, 2.2), (10, 3.4), (26, 3.2), (33, 2.7), (30, 2.1)], -0.85, 0.85, 'shell')                         # lower rail
    g.extrude([(13, 4.5), (29, 4.5), (29, 4.8), (13, 4.8)], -0.35, 0.35, 'glow')                                   # the line in the gap
    g.extrude([(26.5, 5.4), (28.0, 5.4), (28.0, 6.0), (26.5, 6.0)], -1.05, 1.05, 'alloy')                          # the tip brackets
    g.extrude([(26.5, 3.3), (28.0, 3.3), (28.0, 3.9), (26.5, 3.9)], -1.05, 1.05, 'alloy')
    g.extrude([(26.9, 4.0), (27.6, 4.0), (27.6, 5.3), (26.9, 5.3)], -0.6, 0.6, 'glow')                             # their node
    for x in (-4.0, -2.2):
        g.mirror([(x, 3.4), (x + 0.6, 3.4), (x + 1.6, 5.2), (x + 1.0, 5.2)], 0.9, 0.98, 'glow')                   # the slashes
    g.extrude([(2.0, 6.2), (3.2, 6.2), (3.4, 8.1), (2.2, 8.1)], -0.4, 0.4, 'alloy')                                # the sight's mount
    g.extrude([(-2, 8.0), (10, 8.0), (12, 9.0), (0, 9.6)], -0.6, 0.6, 'shell')                                     # the sight
    g.extrude([(11.2, 8.3), (11.8, 8.3), (12.0, 8.9), (11.5, 9.0)], -0.45, 0.45, 'glow')                           # its lens
    g.extrude([(-16, 5.6), (-15, 6.6), (-7, 6.2), (-7.4, 5.2)], -0.75, 0.75, 'alloy')                              # the stock
    g.extrude([(-16, 5.6), (-15, 5.6), (-14.4, 0.6), (-15.6, 0.0)], -0.75, 0.75, 'alloy')
    g.extrude([(-15.6, 0.0), (-14.4, 0.6), (-2.4, -2.6), (-3.0, -3.8)], -0.7, 0.7, 'alloy')
    g.mirror([(-14, 5.6), (-8, 5.45), (-8, 5.75), (-14, 5.9)], 0.75, 0.82, 'glow')                                  # its line
    g.extrude([(-1.4, 2.4), (1.6, 2.4), (0.6, -3.8), (-2.8, -3.8)], -0.75, 0.75, 'alloy')                          # the grip
    g.extrude([(1.0, -2.0), (5.0, 0.8), (5.0, 1.3), (0.6, -1.2)], -0.3, 0.3, 'alloy')                              # its guard
    side_tris_fix(g)
    return g


# ---------------------------------------------------------------- the Boltshot
# a pistol: a pale top slab over a dark lower body with hard light in the gap, a lit chamber (an octagon of light) in
# the body's side, a lit emitter at the front, and the grip an open loop of two bars
def boltshot():
    g = Gun((-5.2, -5.4, 11.8, 5.2))
    g.extrude([(-4, 3.3), (-3, 4.8), (9, 4.8), (11.5, 3.9), (10, 3.3)], -0.9, 0.9, 'shell')                       # the top slab
    g.extrude([(-3, 0.6), (-3, 3.0), (10, 3.0), (10.5, 1.6), (8, 0.6)], -0.8, 0.8, 'alloy')                       # the body
    g.extrude([(0, 3.05), (8, 3.05), (8, 3.25), (0, 3.25)], -0.6, 0.6, 'glow')                                    # light in the gap
    g.extrude([(-2.6, 2.9), (-1.4, 2.9), (-1.6, 3.4), (-2.8, 3.4)], -0.6, 0.6, 'alloy')                           # a strut
    oct8 = [(4.3 + 0.85 * np.cos(np.radians(22.5 + 45 * k)), 1.8 + 0.85 * np.sin(np.radians(22.5 + 45 * k))) for k in range(8)]
    g.mirror(oct8, 0.8, 0.88, 'glow')                                                                             # the chamber
    g.extrude([(10.3, 1.0), (10.6, 1.0), (11.3, 3.6), (11.0, 3.6)], -0.6, 0.6, 'glow')                            # the emitter
    g.extrude([(-0.4, 0.8), (1.2, 0.8), (-0.6, -4.6), (-2.0, -4.6)], -0.7, 0.7, 'alloy')                          # the grip's bars
    g.extrude([(-3.0, 0.8), (-1.8, 0.8), (-3.4, -4.0), (-4.6, -4.0)], -0.7, 0.7, 'alloy')
    g.extrude([(-4.6, -4.0), (-0.6, -4.6), (-0.8, -5.2), (-4.8, -4.6)], -0.7, 0.7, 'alloy')
    g.extrude([(1.0, -1.8), (4.0, 0.6), (4.0, 1.0), (0.6, -1.0)], -0.3, 0.3, 'alloy')                             # the guard
    side_tris_fix(g)
    return g


GUNS = {'light_rifle': (light_rifle, LIGHT_RIFLE_LIGHT), 'scattershot': (scattershot, SCATTERSHOT_LIGHT),
        'binary_rifle': (binary_rifle, BINARY_LIGHT), 'boltshot': (boltshot, BOLTSHOT_LIGHT)}
CREDIT = 'an original Forerunner-style gun made for the pack (forerunner_guns.py)'


def build(names=None):
    for name, (fn, glow) in GUNS.items():
        if names and name not in names: continue
        g = fn(); wid = 'm_' + name
        d = f'{OUT}/weapons/{wid}'; os.makedirs(d, exist_ok=True)
        for f in os.listdir(d): os.remove(os.path.join(d, f))
        mat = f'w_{wid}_0.png'; texture(g).save(f'{d}/{mat}')
        lit = f'w_{wid}_1.png'; Image.new('RGB', (16, 16), glow).save(f'{d}/{lit}')
        side_tris = np.asarray(g.mat) == 'glow'
        pos = np.asarray(g.pos, float).reshape(-1, 3, 3); nrm = np.asarray(g.nrm, float).reshape(-1, 3, 3); uv = np.asarray(g.uv, float).reshape(-1, 3, 2)
        meshes = []
        for m, sel in ((mat, ~side_tris), (lit, side_tris)):
            P, N, UV = pos[sel].reshape(-1, 3), nrm[sel].reshape(-1, 3), uv[sel].reshape(-1, 2)
            meshes.append(dict(material=m, pos=P, nrm=N, uv=UV, tris=np.arange(len(P)).reshape(-1, 3)))
        pickle.dump(dict(id=wid, tag=CREDIT, meshes=meshes), open(f'{d}/{wid}.pkl', 'wb'))
        pos = np.vstack([m['pos'] for m in meshes]); n = len(pos)
        print(wid, 'tris', n // 3, 'bounds', pos.min(0).round(3), pos.max(0).round(3), '->', d)


if __name__ == '__main__':
    build(sys.argv[1:] or None)
