"""Where the left hand holds each gun an enemy carries, and how it is turned to a fore-grip that hangs under its gun
(the enemy API's HCE_GripTick, enemies_base.zsc: the left arm's IK). The packs' ZScript/HaloCE/hce_grips_<pack>.zsc.

    python3 grip_ik.py [sheet.png]          (from generator/; reads and writes ../packs)

A body holds every long gun it is given in the few stances it has: Halo CE's rifle stance (made for the CE assault
rifle), the Brute's carbine stance (made for its plasma carbine), the special Elites' rifle stance (the needle
rifle). Its left hand is where that stance's own gun has its fore-end; on another gun (a Marine's Commando, shotgun
or sniper rifle, a gun picked up, a Brute's human guns) it held the air, or the gun's inside. The gun-specific
stances baked for the Marines (marine_grip.py: 'h2smg', 'h2br', 'h2bulldog', 'h2plasma') put the hand on those four;
this does the rest at run time, with no stance of its own for every gun.

Each gun rides the right hand (its overlay model, <Body>_w_<gun>.iqm), so its fore-end is a fixed place off that
bone. For every body (RIGS), every stance of its that cups the left hand under a gun (REFS: the stance, and the gun it
was made for) and every gun it can hold in that stance (its classes' own, from MODELDEF, and its loadouts', from the
ZScript):

* the gun is measured in its own frame (ahead along its barrel, up, left; from the right hand): at a station along it
  (STATION: how far ahead of its back end its fore-end is held; the stance's own otherwise), its underside and its
  middle;
* the hand goes as far under the one and off the other as the stance has it on the gun it was made for;
* a fore-grip that hangs under the gun (LIFT: the SMG's, the Bulldog's) is held about its middle, the hand turned
  upright beside it, its palm to it and its thumb up, the grip in the curl of its fingers (HOLD, CURL): where the
  hand's bone's x and z then face.

Written per pack as a table class (HCE_GripTable_<Pack>): the body an actor is, the gun it holds (its class's, or a
loadout's), and for a body, a stance and a gun, where the stance has the left wrist (HCE_GripTick moves the hand only
while it is there: a reload, a throw or a death that takes the hand off the gun leaves it be), how far it is moved,
and how it is turned. All in the body's bind space, carried by the right hand. With a path, draws every gun from its
side and from above with the stance's hand and the new one, to look over."""
import os, re, sys, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'lib')]
PACKS = os.path.join(HERE, '..', 'packs')

BIPED = ('bip01 l upperarm', 'bip01 l forearm', 'bip01 l hand', 'bip01 r hand')
H2 = ('l_upperarm', 'l_forearm', 'l_hand', 'r_hand')
# a body: its pack and folder, its model and its overlays' prefix, the class its kind derives from, its arm's bones,
# the stance its guns' frame is taken in and the long gun whose length is the barrel's line
RIGS = [
    dict(pack='HaloCE_Marines', dir='models/hce/Marine', body='Marine', pre='Marine', base='HCE_MarineBase', bones=BIPED, primary='stand rifle idle', long='sniper'),
    dict(pack='HaloCE_Marines', dir='models/hce/MarineArmored', body='MarineArmored', pre='MarineArmored', base='HCE_MarineArmoredBase', bones=BIPED, primary='stand rifle idle', long='sniper'),
    dict(pack='HaloCE_Marines', dir='models/hce/MarineODST', body='MarineODST', pre='Marine', base='HCE_MarineODSTBase', bones=BIPED, primary='stand rifle idle', long='sniper'),
    dict(pack='HaloCE_Covenant', dir='models/hce/EliteSpecial', body='EliteSpecial', pre='EliteSpecial', base='HCE_EliteSpecialBase', bones=BIPED, primary='stand rifle idle', long='needle_rifle'),
    dict(pack='HaloCE_Covenant', dir='models/hce_dig/Brute', body='Brute', pre='Brute', base='HCE_BruteBase', bones=H2, primary='stand carbine idle', long='beam_rifle'),
]
# the stances that cup the left hand under a gun's fore-end, and the gun each was made for (by the stance's name in
# its clips: 'stand <stance> idle')
REFS = {'Marine': {'rifle': 'ma5b', 'h2ar': 'ma5b', 'h2shotgun': 'pump_shotgun', 'h2br': 'battle_rifle', 'h2smg': 'smg', 'h2bulldog': 'bulldog', 'h2plasma': 'plasma_rifle'},
        'EliteSpecial': {'rifle': 'needle_rifle'},
        'Brute': {'carbine': 'plasma_carbine'}}
REFS['MarineArmored'] = REFS['MarineODST'] = REFS['Marine']
# how far ahead of its own back end a gun is held, world units, where that is not where the stance has the hand: the
# SMG's and the Bulldog's fore-grips, the Commando's hand guard, the shotgun's pump, the plasma rifle's lower jaw, and
# the long ones a little further out
# (the Commando, HDE's Tactical Rifle: on the rear of its hand guard, just ahead of its magazine; 0.278, mid-guard, was
# too far forward, the user's "the grip on the tactical rifle is too far forward, especially for marines")
STATION = {'smg': 0.172, 'commando': 0.235, 'pump_shotgun': 0.263, 'bulldog': 0.269, 'sniper': 0.310, 'beam_rifle': 0.264,
           'binary_rifle': 0.301, 'plasma_rifle': 0.155, 'light_rifle': 0.281}
# a fore-grip that hangs under the gun is held about its middle (how far up from its foot that is), the hand turned
# upright to it: its fingers' line and its palm's face then, in the gun's frame (ahead, up, left)
LIFT = {'smg': 0.014, 'bulldog': 0.02}
# guns carried by their handles, not cupped under a fore-end, whatever stance they are held in: left as they are
SKIP = ('gpmg', 'flamethrower', 'fuel_rod', 'rocket_launcher')
# guns a pack's bodies hold in one hand, whatever the stance's other hand does (the user's "covenant should still one
# hand the smg": a Brute's SMG is left as its carbine stance has it, the left hand off the gun)
ONE = {'HaloCE_Covenant': ('smg',)}
HOLD = dict(x=(0.85, 0.25, -0.45), palm=(0.0, 0.0, -1.0))
CURL = (0.58, 0.17)                     # where the grip sits in the hand's curl: along its fingers and off to its palm, of the hand's length
PALM = 0.58                             # the palm's middle along the hand, of its length (Halo's left_hand marker)
SLAB = 0.015                            # (half the length of gun measured at a station)
BAND = 0.03                             # (how far up from its underside its middle is taken)
LEAST = 0.008                           # a move shorter than this is left to the stance


def samples(meshes, n=40000, seed=7):
    """points all over a model's faces, evenly by area"""
    rng = np.random.default_rng(seed); P = []; A = []
    for m in meshes:
        t = m['pos'][m['tris']]; P.append(t); A.append(np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) / 2)
    t = np.concatenate(P); a = np.concatenate(A); pick = rng.choice(len(t), n, p=a / a.sum())
    u, v = rng.random(n), rng.random(n); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    return t[pick, 0] + (t[pick, 1] - t[pick, 0]) * u[:, None] + (t[pick, 2] - t[pick, 0]) * v[:, None]


def held(q, s):
    """a gun's underside and its middle at a station (its points in its own frame: ahead, up, left)"""
    at = q[np.abs(q[:, 0] - s) < SLAB]
    if len(at) < 20: return None
    under = np.percentile(at[:, 1], 3); low = at[(at[:, 1] >= under) & (at[:, 1] <= under + BAND), 2]
    return under, (np.percentile(low, 3) + np.percentile(low, 97)) / 2


def combos(pack):
    """what a pack's bodies hold: {class: (folder, prefix, gun, its idle clip)} and {base class: {loadout: (gun, its idle clip)}}"""
    md = ''.join(open(f).read() for f in sorted(glob.glob(os.path.join(PACKS, pack, 'modeldef*'))))
    over = {}
    for m in re.finditer(r'Model (\w+)\n\{(.*?)\n\}', md, re.S):
        cur = None
        for ln in m.group(2).split('\n'):
            p = re.match(r'\s*Path "([^"]+)"', ln)
            if p: cur = p.group(1)
            g = re.match(r'\s*Model \d+ "(\w+?)_w_(\w+)\.iqm"', ln)
            if g: over[m.group(1)] = (cur, g.group(1), g.group(2))
    classes, loads, parent = {}, {}, {}
    for f in sorted(glob.glob(os.path.join(PACKS, pack, 'ZScript', 'HaloCE', '*.zsc'))):
        z = open(f).read()
        for m in re.finditer(r'\nclass (\w+)\s*:\s*(\w+)(.*?)(?=\nclass |\Z)', z, re.S):
            c, body = m.group(1), m.group(3); parent[c] = m.group(2)
            an = body.find('override Name HCE_AnimName')
            st = re.search(r"case HCE_A_IDLE: return '([^']+)'", body[an:]) if an >= 0 else None
            if c in over and st: classes[c] = over[c] + (st.group(1),)
            for lv in re.finditer(r'void HCE_LoadoutVisual(\d+)\(\)\s*\{(.*?)\n\t\}', body, re.S):
                g = re.search(r"A_ChangeModel\('None', \d+, \"([^\"]+)\", '(\w+?)_w_(\w+)\.iqm'\)", lv.group(2))
                la = re.search(r'Name HCE_LoadoutAnim%s\(int kind\)(.*?)\n\t\}' % lv.group(1), body, re.S)
                st = re.search(r"case HCE_A_IDLE: return '([^']+)'", la.group(1)) if la else None
                if g and st: loads.setdefault(c, {})[int(lv.group(1))] = (g.group(3), st.group(1))
    def depth(c):
        n = 0
        while c in parent: c = parent[c]; n += 1
        return n
    return classes, loads, depth


def stance_of(clip):
    """'stand rifle idle' -> 'rifle' (HCE_GripTick takes a clip's second word the same way)"""
    w = clip.split(' ')
    return w[1] if len(w) >= 3 else ''


class Rig:
    def __init__(self, cfg, read_iqm, pv):
        self.cfg, self.read, self.pv = cfg, read_iqm, pv
        self.path = os.path.join(PACKS, cfg['pack'], cfg['dir'])
        J, M, A = read_iqm(os.path.join(self.path, cfg['body'] + '.iqm'))
        self.A = A; names = [j[0] for j in J]; self.par = [j[1] for j in J]
        bind = pv.world(self.par, [(j[2], j[3]) for j in J])
        self.lh, self.rh = names.index(cfg['bones'][2]), names.index(cfg['bones'][3])
        self.Rb, self.tb = pv.qmat(bind[self.rh][1]), np.asarray(bind[self.rh][0], float)
        # the left hand's own shape, in its bone's frame: its fingers' line and its length (its bone and all under it)
        kids = {self.lh}
        for i in range(len(J)):
            p = self.par[i]
            while p >= 0:
                if p == self.lh: kids.add(i); break
                p = self.par[p]
        Rh, th = pv.qmat(bind[self.lh][1]), np.asarray(bind[self.lh][0], float); V = []
        for m in M:
            own = np.zeros(len(m['pos']))
            for k in range(m['bidx'].shape[1]): own += np.where(np.isin(m['bidx'][:, k], list(kids)), m['bw'][:, k].astype(float), 0)
            V.append(m['pos'][own > 127])
        V = (np.concatenate(V) - th) @ Rh
        self.fing = V.mean(0) / np.linalg.norm(V.mean(0)); self.length = float(np.percentile(V @ self.fing, 95))
        self.guns = {}
        # its guns' frame, fixed in the right hand: ahead along the long gun's length, up as the body's in the
        # primary stance, left
        fw, up, lt = self.carried_axes(cfg['primary'])
        P = self.points(cfg['long']); ax = np.linalg.svd(P - P.mean(0), full_matrices=False)[2][0]; ax *= np.sign(ax @ fw)
        up = up - ax * (up @ ax); up /= np.linalg.norm(up)
        self.fw, self.up, self.lt = ax, up, np.cross(up, ax)

    def points(self, gun):
        if gun not in self.guns: self.guns[gun] = samples(self.read(os.path.join(self.path, '%s_w_%s.iqm' % (self.cfg['pre'], gun)))[1])
        return self.guns[gun]

    def has(self, gun): return os.path.exists(os.path.join(self.path, '%s_w_%s.iqm' % (self.cfg['pre'], gun)))

    def pose(self, clip):
        w = self.pv.world(self.par, [(f[0], f[1]) for f in self.A[clip][0]])
        return w, self.pv.qmat(w[self.rh][1]), np.asarray(w[self.rh][0], float)

    def carried_axes(self, clip):
        """the body's ahead, up and left in a stance, as the right hand carries them, in bind space"""
        w, R, t = self.pose(clip)
        return [self.Rb @ (R.T @ np.array(v, float)) for v in ((1, 0, 0), (0, 0, 1), (0, 1, 0))]

    def L(self, p): p = np.asarray(p) - self.tb; return np.stack([p @ self.fw, p @ self.up, p @ self.lt], -1)   # bind space -> the gun's frame
    def D(self, v): v = np.asarray(v); return np.array([v @ self.fw, v @ self.up, v @ self.lt])
    def B(self, v): return self.fw * v[0] + self.up * v[1] + self.lt * v[2]                                        # and a direction back

    def hand(self, clip):
        """the left hand in a stance, in the gun's frame: its wrist, its bone's axes (x, z), its fingers' line"""
        w, R, t = self.pose(clip); C = lambda v: self.Rb @ (R.T @ v)
        Rh = self.pv.qmat(w[self.lh][1]); wr = np.asarray(w[self.lh][0], float)
        wrist_b = C(wr - t) + self.tb
        return dict(wrist=self.L(wrist_b), wrist_b=wrist_b, x=self.D(C(Rh[:, 0])), z=self.D(C(Rh[:, 2])), f=self.D(C(Rh @ self.fing)))


def cross3(a, b):
    """a cross b for (ahead, up, left) triples (a left-handed order: crossed as ahead, left, up)"""
    c = np.cross([a[0], a[2], a[1]], [b[0], b[2], b[1]]); return np.array([c[0], c[2], c[1]])


def frame(f, n):
    """a hand's frame from its fingers' line and its palm's face: fingers, palm (made square to them), thumb"""
    f = np.asarray(f, float) / np.linalg.norm(f); n = np.asarray(n, float); n = n - f * (f @ n); n /= np.linalg.norm(n)
    return np.stack([f, n, cross3(n, f)], 1)


def work(rig, classes, loads, log):
    """every (stance, gun) of a body: {stance: (the wrist's place, {gun: (move, x, z)})}, the bind space's; and what to draw"""
    name = rig.cfg['body']; refs = REFS[name]; pairs = set(); out = {}; draw = []
    for c, (d, pre, g, clip) in classes.items():
        if d == rig.cfg['dir']: pairs.add((stance_of(clip), clip, g))
    for g, clip in loads.get(rig.cfg['base'], {}).values(): pairs.add((stance_of(clip), clip, g))
    for st, clip, g in sorted(pairs):
        if st not in refs or g in SKIP or g in ONE.get(rig.cfg['pack'], ()) or clip not in rig.A or not rig.has(g) or not rig.has(refs[st]): continue
        h = rig.hand(clip); palm = h['wrist'] + h['f'] * rig.length * PALM
        ref = held(rig.L(rig.points(refs[st])), palm[0])
        if ref is None: log('%-14s %-10s the stance\'s hand is not on its own gun (%s): left' % (name, st, refs[st])); continue
        over, off = palm[1] - ref[0], palm[2] - ref[1]
        q = rig.L(rig.points(g)); back = np.percentile(q[:, 0], 0.5)
        s = back + STATION[g] if g in STATION else float(np.clip(palm[0], back + 0.05, np.percentile(q[:, 0], 99.5) - 0.03))
        at = held(q, s)
        if at is None: log('%-14s %-10s %-18s no gun at its station %.3f: left' % (name, st, g, s)); continue
        u, mid = at; x = z = None
        if g in LIFT:
            # (upright beside the grip: the hand as the stance has it, cupped up, turned to HOLD; the grip's middle in
            # the curl of its fingers, the wrist back along the hand and off to its back from there)
            S = frame(h['f'], (0, 1, 0)); G = frame(HOLD['x'], HOLD['palm']); T = G @ S.T
            wrist = np.array([s, u + LIFT[g], mid]) - G[:, 0] * rig.length * CURL[0] - G[:, 1] * rig.length * CURL[1]
            d = wrist - h['wrist']; x, z = T @ h['x'], T @ h['z']
            new = np.array([s, u + LIFT[g], mid])
            log('%-14s %-10s %-18s station %.3f underside %+.3f middle %+.3f  the hand turned upright, the wrist moved %+.3f %+.3f %+.3f (%.3f)' % (name, st, g, s, u, mid, d[0], d[1], d[2], np.linalg.norm(d)))
        else:
            d = np.array([s - palm[0], u + over - palm[1], mid + off - palm[2]])
            if g == refs[st] or np.linalg.norm(d) < LEAST: d[:] = 0
            new = palm + d
            log('%-14s %-10s %-18s station %.3f underside %+.3f middle %+.3f  move %+.3f %+.3f %+.3f (%.3f)' % (name, st, g, s, u, mid, d[0], d[1], d[2], np.linalg.norm(d)))
        draw.append((name, st, g, q, palm, new))
        if np.linalg.norm(d) > 0: out.setdefault(st, (h['wrist_b'], {}))[1][g] = (rig.B(d), None if x is None else rig.B(x), None if z is None else rig.B(z))
    return out, draw


def vec(v): return '(%.4f, %.4f, %.4f)' % tuple(v)


def write(pack, rigs, tables, classes, loads, depth):
    """the pack's table class: HCE_GripTable_<Pack> (the enemy API's HCE_GripTable, enemies_base.zsc, by way of HCE_GripReach, hce_grip.zsc)"""
    short = pack.split('_')[-1]; L = []
    L += ['// ---- where the left hand holds each gun, and how it is turned to a fore-grip that hangs under its gun: the',
          '// enemy API\'s HCE_GripTick (enemies_base.zsc) looks these up. Written by generator/grip_ik.py (why, and how each',
          '// is measured); not for editing by hand: change its STATION, LIFT, HOLD or CURL and run it again.', '',
          'class HCE_GripTable_%s : HCE_GripReach' % short, '{',
          '\t// (the body an actor is: its place in this table)', '\toverride int Rig(Actor a)', '\t{']
    for i, r in enumerate(rigs): L.append('\t\tif(a is "%s") return %d;' % (r.cfg['base'], i))
    L += ['\t\treturn -1;', '\t}', '\t// (the gun it holds: a loadout\'s, or its class\'s own)', '\toverride Name Gun(Actor a, int rig, int lo)', '\t{', '\t\tif(lo >= 0)', '\t\t{', '\t\t\tswitch(rig * 100 + lo)', '\t\t\t{']
    for i, r in enumerate(rigs):
        for lo, (g, clip) in sorted(loads.get(r.cfg['base'], {}).items()): L.append("\t\t\tcase %d: return '%s';" % (i * 100 + lo, g))
    L += ['\t\t\t}', "\t\t\treturn 'None';", '\t\t}']
    for i, r in enumerate(rigs):
        own = [(c, v[2]) for c, v in sorted(classes.items(), key=lambda cv: (-depth(cv[0]), cv[0])) if v[0] == r.cfg['dir']]      # (a class before the one it derives from)
        if not own: continue
        L.append('\t\tif(rig == %d)' % i); L.append('\t\t{')
        for c, g in own: L.append("\t\t\tif(a is \"%s\") return '%s';" % (c, g))
        L.append('\t\t}')
    L += ["\t\treturn 'None';", '\t}',
          '\t// (for a body, a gun and a stance: its arm\'s bones, where the stance has the left wrist, how far the hand is',
          '\t// moved, and where its bone\'s x and z face when it is turned upright)', '\toverride bool Find(int rig, Name gun, Name stance)', '\t{',
          '\t\tgripTurn = false;', '\t\tswitch(rig)', '\t\t{']
    for i, r in enumerate(rigs):
        b = r.cfg['bones']
        L.append("\t\tcase %d: armU = '%s'; armF = '%s'; armH = '%s'; handR = '%s'; break;" % (i, b[0], b[1], b[2], b[3]))
    L += ['\t\tdefault: return false;', '\t\t}']
    for i, r in enumerate(rigs):
        for st, (wrist, guns) in sorted(tables[i].items()):
            L.append("\t\tif(rig == %d && stance == '%s')" % (i, st)); L.append('\t\t{'); L.append('\t\t\tgripRef = %s;' % vec(wrist))
            for g, (d, x, z) in sorted(guns.items()):
                if x is None: L.append("\t\t\tif(gun == '%s') { gripMove = %s; return true; }" % (g, vec(d)))
                else: L.append("\t\t\tif(gun == '%s') { gripMove = %s; gripTurn = true; gripX = %s; gripZ = %s; return true; }" % (g, vec(d), vec(x), vec(z)))
            L.append('\t\t\treturn false;'); L.append('\t\t}')
    L += ['\t\treturn false;', '\t}', '}', '']
    path = os.path.join(PACKS, pack, 'ZScript', 'HaloCE', 'hce_grips_%s.zsc' % short.lower())
    open(path, 'w', newline='\n').write('\n'.join(L))
    zt = os.path.join(PACKS, pack, 'zscript.txt'); inc = '#include "ZScript/HaloCE/hce_grips_%s.zsc"' % short.lower(); src = open(zt).read()
    if inc not in src: open(zt, 'w', newline='\n').write(src.rstrip('\n') + '\n' + inc + '\n')
    return path


if __name__ == '__main__':
    from iqm import read_iqm
    import preview as pv
    drawn = []
    for pack in sorted({r['pack'] for r in RIGS}):
        classes, loads, depth = combos(pack); rigs = [Rig(c, read_iqm, pv) for c in RIGS if c['pack'] == pack]; tables = []
        for r in rigs:
            t, d = work(r, classes, loads, print); tables.append(t); drawn += d
        p = write(pack, rigs, tables, classes, loads, depth)
        print('%s: %d moves written into %s' % (pack, sum(len(g) for t in tables for _, g in t.values()), os.path.relpath(p, os.path.join(HERE, '..'))))
    if sys.argv[1:]:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        cols = 3; n = len(drawn); rows = (n + cols - 1) // cols
        fig, axs = plt.subplots(rows, cols * 2, figsize=(cols * 13, rows * 2.5)); axs = np.atleast_2d(axs)
        for k, (name, st, g, q, palm, new) in enumerate(drawn):
            for v, (x, y) in enumerate(((0, 1), (0, 2))):
                ax = axs[k // cols, (k % cols) * 2 + v]; ax.scatter(q[::6, x], q[::6, y], s=0.6, c='0.55')
                ax.plot(0, 0, 'r+', ms=12, mew=2); ax.plot(palm[x], palm[y], 'g^', ms=7); ax.plot(new[x], new[y], 'o', color='orange', ms=7, mec='k')
                ax.set_xlim(-0.15, 0.5); ax.set_ylim((-0.12, 0.12) if v == 0 else (-0.09, 0.09)); ax.set_aspect('equal')
                ax.set_title('%s %s: %s %s' % (name, st, g, 'side' if v == 0 else 'top'), fontsize=7); ax.grid(True, alpha=.3); ax.tick_params(labelsize=4)
        plt.tight_layout(); plt.savefig(sys.argv[1], dpi=45)
