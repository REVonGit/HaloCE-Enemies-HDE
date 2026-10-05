"""Elite rifle stance: Halo CE Elites only have pistol and sword animation sets.

Builds 'EliteRifle' (Elite body + the Plasma Carbine on the right hand) whose rifle animations keep the
Elite's own legs, pelvis and spine from the matching pistol animation and take the arms from the
Marine's rifle animation of the same action (both are 3ds Max bipeds, so arm bones share local axes).
The left hand is then solved onto the carbine's fore-grip with two-bone IK."""
import sys, os, re, copy
import numpy as np
import halomodel as hm
from halomodel import qmul, qrot, qconj, qnorm
import extract_chars as ec
from tags import tag, HMap

MAP = 'a30'          # carries both the Elite and the Marine graphs
ELITE = r'characters\elite\elite'
MARINE = r'characters\marine\marine'
ARM = ['bip01 l clavicle', 'bip01 r clavicle', 'bip01 l upperarm', 'bip01 r upperarm',
       'bip01 l forearm', 'bip01 r forearm', 'bip01 l hand', 'bip01 r hand']
FOREGRIP = np.array([0.087, 0.07, -0.054])  # support-hand wrist in weapon space, as the CE rifle set holds it
# rifle animation <- (Elite pistol animation for the body, Marine rifle animation for the arms or None to keep)
PLAN = {
    'stand rifle idle': ('stand pistol idle%0', 'stand rifle idle'),
    'alert rifle idle': ('alert pistol idle', 'alert rifle idle%0'),
    'alert rifle move-front': ('alert pistol move-front', 'alert rifle move-front%0'),
    'stand rifle move-front': ('stand pistol move-front', 'stand rifle move-front'),
    'stand rifle move-back': ('stand pistol move-back', 'stand rifle move-back'),
    'stand rifle move-left': ('stand pistol move-left', 'stand rifle move-left'),
    'stand rifle move-right': ('stand pistol move-right', 'stand rifle move-right'),
    'crouch rifle idle': ('crouch pistol idle', 'crouch rifle idle'),
    'crouch rifle move-front': ('crouch pistol move-front', 'crouch rifle move-front'),
    'crouch rifle move-back': ('crouch pistol move-back', 'crouch rifle move-back'),
    'crouch rifle move-left': ('crouch pistol move-left', 'crouch rifle move-left'),
    'crouch rifle move-right': ('crouch pistol move-right', 'crouch rifle move-right'),
    'stand rifle dive-front': ('stand pistol dive-front', 'stand rifle dive-front'),
    'stand rifle dive-left': ('stand pistol dive-left', 'stand rifle dive-left'),
    'stand rifle dive-right': ('stand pistol dive-right', 'stand rifle dive-right'),
    'stand rifle evade-left': ('stand pistol evade-left', 'stand rifle evade-left'),
    'stand rifle evade-right': ('stand pistol evade-right', 'stand rifle evade-right'),
    'stand rifle airborne': ('stand pistol airborne', 'stand rifle airborne'),
    'stand rifle land-soft': ('stand pistol land-soft', 'stand rifle land-soft'),
    'stand rifle land-hard': ('stand pistol land-hard', 'stand rifle land-hard'),
    'stand rifle throw-grenade': ('stand pistol throw-grenade', 'stand rifle throw-grenade'),
    'stand rifle warn': ('stand pistol warn', 'stand rifle warn%1'),
    'stand rifle signal-attack': ('stand pistol signal-attack', 'stand rifle signal-attack'),
    'stand rifle berserk': ('stand pistol berserk', 'stand rifle berserk%3'),
    'stand rifle turn-left': ('stand pistol turn-left', 'stand rifle turn-left'),
    'stand rifle turn-right': ('stand pistol turn-right', 'stand rifle turn-right'),
    # no Marine counterpart: the Elite's own one-handed motion, carbine in the right hand
    'stand rifle melee': ('stand pistol melee', None),
    'stand rifle surprise-front': ('stand pistol surprise-front', 'stand rifle idle'),
    'stand rifle surprise-back': ('stand pistol surprise-back', 'stand rifle idle'),
}
# Copying the Marine's arm rotations points the carbine wrong (the Elite's hand marker is oriented differently),
# so the Elite's own aiming right arm is kept and only the support hand is solved onto the fore-grip.
USE_MARINE_ARMS = False
IK_SKIP = {'stand rifle melee', 'stand rifle throw-grenade', 'stand rifle signal-attack', 'stand rifle warn',
           'stand rifle berserk'}

def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    c = np.cross(a, b); d = float(np.dot(a, b))
    if d < -0.999999:
        ax = np.cross(a, [1, 0, 0])
        if np.linalg.norm(ax) < 1e-6: ax = np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax)
        return np.array([ax[0], ax[1], ax[2], 0.0])
    return qnorm(np.array([c[0], c[1], c[2], 1.0 + d]))

def world(parent, frame):
    W = []
    for i, (t, q, s) in enumerate(frame):
        if parent[i] < 0: W.append((np.asarray(t, float), qnorm(q)))
        else:
            pt, pq = W[parent[i]]
            W.append((pt + qrot(pq, t), qnorm(qmul(pq, q))))
    return W

def two_bone_ik(frame, parent, iu, if_, ih, target):
    W = world(parent, frame)
    S, qs = W[iu]; E, qe = W[if_]; H, qh = W[ih]
    a = np.linalg.norm(E - S); b = np.linalg.norm(H - E)
    T = np.asarray(target)
    dv = T - S; d = np.linalg.norm(dv)
    d = min(max(d, abs(a - b) + 1e-4), a + b - 1e-4)
    n = dv / np.linalg.norm(dv)
    x = (a * a - b * b + d * d) / (2 * d); h = np.sqrt(max(0.0, a * a - x * x))
    bend = (E - S) - np.dot(E - S, n) * n
    if np.linalg.norm(bend) < 1e-6: bend = np.array([0, 0, -1.0])
    bend /= np.linalg.norm(bend)
    E2 = S + n * x + bend * h
    d1 = rot_between(E - S, E2 - S)
    qs2 = qnorm(qmul(d1, qs)); qe2 = qnorm(qmul(d1, qe))
    H2 = E2 + qrot(d1, H - E)
    d2 = rot_between(H2 - E2, S + n * d - E2)
    qe3 = qnorm(qmul(d2, qe2))
    pu = W[parent[iu]][1]
    out = list(frame)
    out[iu] = (frame[iu][0], qnorm(qmul(qconj(pu), qs2)), frame[iu][2])
    out[if_] = (frame[if_][0], qnorm(qmul(qconj(qs2), qe3)), frame[if_][2])
    return out

def build(maps):
    m = maps[MAP]
    def graph(name):
        bt = [t for t in m.find('bipd') if t['name'] == name][0]
        B = tag(m, bt, 'biped_definition')
        model = hm.Model(m, B['model'])
        return model, {a.name: a for a in hm.read_animations(m, B['animation_graph'], len(model.nodes))}
    em, EA = graph(ELITE)
    mm, MA = graph(MARINE)
    en = [n['name'] for n in em.nodes]; mn = [n['name'] for n in mm.nodes]
    eparent = [n['parent'] for n in em.nodes]
    emap = {b: en.index(b) for b in ARM}
    mmap = {b: mn.index(b) for b in ARM}
    markers = ec.read_markers(m, em)
    mk = markers['right hand elite'][0]
    mnode, mt, mq = mk['node'], np.array(mk['t']), hm.hq(mk['q'])
    il = [en.index(x) for x in ('bip01 l upperarm', 'bip01 l forearm', 'bip01 l hand')]
    made = []
    for rname, (ename, mname) in PLAN.items():
        if ename not in EA: print('  missing elite', ename); continue
        ea = EA[ename]; ma = MA.get(mname) if mname else None
        if mname and not ma: print('  missing marine', mname); continue
        a = copy.copy(ea); a.name = rname
        frames = []
        for f, fr in enumerate(ea.frames):
            fr = list(fr)
            if ma and USE_MARINE_ARMS:
                g = int(round(f / max(1, len(ea.frames) - 1) * (len(ma.frames) - 1))) if ma.nframes > 1 else 0
                src = ma.frames[g]
                for b in ARM:
                    t, q, s = fr[emap[b]]
                    fr[emap[b]] = (t, src[mmap[b]][1], s)
            if rname not in IK_SKIP:
                W = world(eparent, fr)
                ht, hq = W[mnode]
                gp = ht + qrot(hq, mt + qrot(mq, FOREGRIP))
                fr = two_bone_ik(fr, eparent, *il, gp)
            frames.append(fr)
        a.frames = frames
        made.append(a)
    # carbine recoil: the Marine's assault-rifle fire overlay (arm deltas only)
    for on in ('stand rifle ar fire-1',):
        ov = MA.get(on)
        if ov is None: continue
        o = copy.copy(ov); o.name = 'stand rifle cr fire-1'
        o.frames = [[((None, fr[mn.index(b)][1], None) if b in ARM else (None, None, None)) for b in en] for fr in ov.frames]
        made.append(o)
    return made

from hce_paths import SKETCHFAB, MAPS_DIR
ANTR = SKETCHFAB + '/elite.model_animations'   # user-supplied CE Elite graph with a rifle set
TAG_IK = True

def from_tag(maps):
    """real Elite rifle animations from the supplied CE-rig animation graph"""
    from looseantr import Antr
    A = Antr(ANTR)
    m = maps[MAP]
    bt = [t for t in m.find('bipd') if t['name'] == ELITE][0]
    B = tag(m, bt, 'biped_definition')
    em = hm.Model(m, B['model'])
    en = [n['name'] for n in em.nodes]
    assert A.nodes() == en, 'node mismatch'
    eparent = [n['parent'] for n in em.nodes]
    mk = ec.read_markers(m, em)['right hand elite'][0]
    mnode, mt, mq = mk['node'], np.array(mk['t']), hm.hq(mk['q'])
    il = [en.index(x) for x in ('bip01 l upperarm', 'bip01 l forearm', 'bip01 l hand')]
    EA = {a.name: a for a in hm.read_animations(m, B['animation_graph'], len(em.nodes))}
    made = []
    for a in A.animations():
        n = a['name']
        if ' rifle ' not in f' {n} ' or not n.startswith(('stand rifle', 'crouch rifle', 'alert rifle')): continue
        if a['type'] != 0 or a['node_count'] != len(en): continue
        frames, dx = A.decode(a, len(en))
        if TAG_IK and n not in IK_SKIP and not n.startswith('stand rifle melee'):
            out = []
            for fr in frames:
                W = world(eparent, fr)
                ht, hq_ = W[mnode]
                gp = ht + qrot(hq_, mt + qrot(mq, FOREGRIP))
                lh = W[il[2]][0]
                out.append(two_bone_ik(fr, eparent, *il, gp) if np.linalg.norm(lh - gp) > 0.02 else fr)
            frames = out
        an = copy.copy(EA['stand pistol idle%0'])
        an.name = n; an.type = 0; an.nframes = len(frames); an.frames = frames; an.dx = dx
        an.loop = 0; an.key = 0; an.next = -1
        made.append(an)
    # recoil (the tag has no rifle fire overlay): the upper body kicks up ~3 degrees and settles
    base = next((x for x in made if x.name == 'stand rifle idle'), None)
    if base is not None:
        isp = en.index('bip01 spine1')
        fr0 = base.frames[0]
        frames = []
        for k in range(8):
            th = np.radians(3.2) * (1 - k / 7.0) ** 2 * (1 if k else 0.6)
            W = world(eparent, fr0)
            pq = W[eparent[isp]][1]; sq = W[isp][1]
            kick = np.array([0, -np.sin(th / 2), 0, np.cos(th / 2)])     # pitch up about the lateral axis
            nq = qnorm(qmul(qconj(pq), qmul(kick, sq)))
            fr = list(fr0); fr[isp] = (fr0[isp][0], nq, fr0[isp][2])
            frames.append(fr)
        o = copy.copy(base); o.name = 'stand rifle cr fire-1 baked'; o.frames = frames; o.nframes = 8
        o.dx = np.zeros((8, 4)); made.append(o)
    names = {a.name for a in made}
    # rifle actions the tag lacks: Elite pistol body + IK support hand (from build())
    for a in build(maps):
        if a.name not in names and not any(n.startswith(a.name + '%') for n in names) and a.type == 0: made.append(a)
    return made

def run():
    maps = {MAP: HMap(f'{MAPS_DIR}/{MAP}.map')}
    made = from_tag(maps) if os.path.exists(ANTR) else build(maps)
    keep = re.compile(r'^(stand|alert|crouch|flee|s-ping|h-ping|s-kill|h-kill|stand airborne-dead|stand landing-dead)')
    orig_read = hm.read_animations
    def patched(mm, graph, nc):
        res = orig_read(mm, graph, nc)
        if nc != 26: return res
        res = [a for a in res if keep.match(a.name) and ' sword ' not in a.name]
        names = {a.name for a in res}
        return res + [a for a in made if a.name not in names]
    hm.read_animations = patched
    ec.char_weapons = lambda name: ['cmt_carbine']
    ec.HAND_MARKER['EliteRifle'] = 'right hand elite'
    meta = ec.extract(ELITE, 'EliteRifle', [MAP], maps)
    hm.read_animations = orig_read
    print('EliteRifle anims', len(meta['anims']), 'iqm', meta['iqm_bytes'] // 1024, 'KB')
    return meta

if __name__ == '__main__':
    run()
