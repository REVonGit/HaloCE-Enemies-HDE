"""SOI7's Covenant animations from Halo: Brutality Evolved on the Halo CE bodies -> out/models/<Char>/<Char>.iqm, .json

    HCE_BE_A50=/path/to/brutality_evolved/maps/a50.map python3 be_anims.py [Char ...]

Halo: Brutality Evolved (RoxanneGoat; MCC Steam Workshop 3014096841) gives the Hunter, Elite, Grunt and Jackal SOI7's
animation graphs ('old_lords\\characters\\<race>\\<race>') on Halo CE's own bipeds. Each graph is compared with Halo
CE's own (the same race's graph in Halo CE's a50, MAPS_DIR) and what SOI7 added or redid is taken:

* a redone Halo CE animation (other frames, other length) replaces Halo CE's on the body;
* a new animation is added, unless the body already has one by that name (a Halo 2 stance another script put there:
  the Spec Ops Elite's rifle stance, say), which is never overwritten;
* a Halo CE animation SOI7 split into variants ('stand pistol melee' -> 'stand pistol melee%0'..'%3') is dropped, so
  build_pack.anim_table picks the variants;
* new fire and reload overlays are baked onto their stance's idle (' baked'), as extract_chars.py bakes Halo CE's;
  other overlays (aim, look) are left out, as extract_chars.py leaves Halo CE's.

The Brute (Halo 2's, extract_h2_brute.py) takes the mod's Halo 3-style Brute graph ('tftu\\characters\\brute\\h3', on
Halo 2's Brute skeleton, bones 'bip01 <name>'; its Halo 2-style graph is Halo 2's own, which the Brute already has):
its stances replace the Brute's Halo 2 ones of the same use (H3_STANCE: the gravity hammer's for the Brute's 'melee'
stance, the rifle's, the Brute Shot's for 'support'), name for name, Halo 2's variants of a name dropped; the carbine and
unarmed stances, the burning idles, sleep idles and the head-shot kill are added. Halo 2's low ready, cover, hoist, vault
and fire stay. (add_brute)

Bones are matched by name, so any body on the race's biped takes them (CHARS). Run after extract_chars.py (and
extract_ultra_zealot.py), before low_ready_anims.py, reload_anims.py and cover_anims.py, which build on the stances'
idles. Replaces this script's animations on each run and stamps them (lib/steps.py)."""
import os, sys, json, re, copy
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
import halomodel as hm
import steps
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
BE_A50 = os.environ.get('HCE_BE_A50', 'a50.map')
# body -> race (its SOI7 graph 'old_lords\characters\<race>\<race>', Halo CE's 'characters\<race>\<race>')
CHARS = {'Hunter': 'hunter', 'Elite': 'elite', 'EliteSpecial': 'elite', 'EliteRifle': 'elite', 'EliteZealot': 'elite',
         'Grunt': 'grunt', 'GruntSpecOps': 'grunt', 'Jackal': 'jackal', 'JackalMajor': 'jackal', 'Brute': 'brute'}
BRUTE_GRAPH = r'tftu\characters\brute\h3'
# the mod's Halo 3 Brute stance -> the Brute's stance name (build_digsite: the gravity hammer's is 'melee', the
# two-handed support guns' 'support', every other gun's 'rifle')
H3_STANCE = {'hammer': 'melee', 'rifle': 'rifle', 's-low': 'support', 'carbine': 'carbine', 'unarmed': 'unarmed'}
# The mod's Halo 3-style rig bends the fingers from a different rest pose: on Halo 2's Brute they splay open off the
# gun. Halo 2's own animations hold every finger at the model's rest pose (its gripping hand), so these do too
BRUTE_FINGERS = ('index', 'ring', 'thumb')
# the two-handed stance's left hand: on the assault rifle's handguard (Halo weapon space, as marine_h2_grips.H2_GUNS;
# the shotgun's pump is within a hair of it), placed by two-bone IK in every carbine animation but the ones where the
# left hand lets go (BRUTE_FREE_LEFT)
BRUTE_LEFT_PALM = np.array([0.112, 0.000, 0.010])
BRUTE_FREE_LEFT = ('throw-grenade', 'signal-attack', 'taunt', 'warn', 'celebrate')
STEP = 'be_anims'
_graphs = {}


def graph(m, name):
    """{animation name: hm.Animation} of a map's graph, frames on the graph's own nodes, and the node names"""
    from tags import tag
    t = next(t for t in m.tags if t['cls'] == 'antr' and t['name'] == name)
    G = tag(m, t, 'animation_graph')
    nodes = [m.d[m.v2o(n.addr):m.v2o(n.addr) + 32].split(b'\0')[0].decode() for n in G.block('nodes', 'animation_graph_node')]
    return {a.name: a for a in hm.read_animations(m, t, len(nodes))}, nodes


def same(a, b):
    """two animations with the same frames (to a rounding)"""
    if a.nframes != b.nframes or a.type != b.type: return False
    for fa, fb in zip(a.frames, b.frames):
        for x, y in zip(fa, fb):
            if (x[1] is None) != (y[1] is None): return False
            if x[1] is not None and 1 - abs(float(np.dot(x[1], y[1]))) > 1e-4: return False
    return True


def soi7(race):
    """(SOI7's animations, its node names, the names SOI7 added or redid, Halo CE names it split into variants, Halo
    CE's names)"""
    if race not in _graphs:
        from pcmap import PCMap
        from tags import HMap
        from hce_paths import MAPS_DIR
        B, nodes = graph(PCMap(BE_A50), f'old_lords\\characters\\{race}\\{race}')
        C, _ = graph(HMap(f'{MAPS_DIR}/a50.map'), f'characters\\{race}\\{race}')
        take = [n for n in B if n not in C or not same(B[n], C[n])]
        split = [n for n in C if n not in B and any(re.fullmatch(re.escape(n) + r'%\d+', k) for k in B)]
        _graphs[race] = (B, nodes, take, split, set(C))
    return _graphs[race]


def add_brute(char):
    """the mod's Halo 3-style stances on the Brute (see the module doc)"""
    from pcmap import PCMap
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    B, nodes = graph(PCMap(BE_A50), BRUTE_GRAPH)
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    st = meta.get('steps') or {}
    for k in st.get(STEP, []): anims.pop(k, None); meta['anims'].pop(k, None)
    jn = [j[0] for j in joints]
    src = [nodes.index('bip01 ' + n) if 'bip01 ' + n in nodes else None for n in jn]
    if sum(x is not None for x in src) < len(nodes): print(char, 'skipped: not the Brute skeleton'); return
    others = {n for k, v in st.items() if k != STEP for n in v}      # other scripts' (low ready, cover, hoist ...): kept
    plan = {}
    for n, a in B.items():
        w = n.split(' ')
        if a.type != 0:
            # the carbine stance's fire, baked onto its idle (the rifle and support stances keep Halo 2's per-gun fire)
            if n.startswith('stand carbine') and 'fire-1' in n: plan[n] = 'stand carbine fire-1 baked'
            continue
        if w[0] in ('stand', 'flaming') and len(w) > 2 and w[1] in H3_STANCE:
            plan[n] = ' '.join([w[0], H3_STANCE[w[1]]] + w[2:])
        elif w[0] == 'asleep' or n == 'h-kill front head':
            plan[n] = n
    import marine_grip as mg
    from marine_arsenal import hand_frame
    parents = [j[1] for j in joints]
    fingers = [i for i, n in enumerate(jn) if any(f in n for f in BRUTE_FINGERS)]
    ix = {n: i for i, n in enumerate(jn)}
    L_ids = (ix['l_upperarm'], ix['l_forearm'], ix['l_hand'])
    R, t0, rj, _ = hand_frame(char, 'assault_rifle')                   # Halo weapon space -> bind pose, at the gun hand
    bt, bq = mg.world(parents, [(j[2], j[3]) for j in joints])[rj]
    palm_h = hm.qrot(hm.qconj(bq), R @ BRUTE_LEFT_PALM + t0 - bt)      # the handguard in the gun hand's frame
    # the left palm: the wrist out to the knuckles' middle (index and ring), in the left hand's own frame
    lpalm = 0.6 * (np.asarray(joints[ix['l_index1']][2]) + np.asarray(joints[ix['l_ring1']][2])) / 2

    def grip(frames, nm):
        """fingers at rest; in the two-handed stance the left hand on the gun's handguard"""
        two = nm.startswith('stand carbine') and not any(k in nm for k in BRUTE_FREE_LEFT)
        out = []
        for fr in frames:
            fr = list(fr)
            for i in fingers: fr[i] = (fr[i][0], tuple(joints[i][3]), fr[i][2])
            if two:
                local = [(x[0], x[1]) for x in fr]
                W = mg.world(parents, local)
                ht, hq = W[rj]
                lq = W[L_ids[2]][1]
                mg.solve_arm(W, local, parents, L_ids, ht + hm.qrot(hq, palm_h) - hm.qrot(lq, lpalm), lq)
                fr = [(tuple(local[i][0]), tuple(local[i][1]), fr[i][2]) for i in range(len(fr))]
            out.append(fr)
        return out
    new = []
    for n, nm in sorted(plan.items()):
        base = re.sub(r'%\d+$', '', nm)
        for k in [k for k in anims if k not in others and (k == base or re.fullmatch(re.escape(base) + r'(%\d+| \d+)', k))]:
            anims.pop(k); meta['anims'].pop(k, None)
    for n, nm in sorted(plan.items()):
        a = B[n]
        if a.type != 0:                                     # an overlay: laid over its stance's idle
            base = B['stand carbine idle']
            a = copy.copy(base); a.frames = hm.bake_overlay(base.frames[0], B[n].frames); a.nframes = len(a.frames)
            a.dx = np.zeros((a.nframes, 4))
        frames = []
        for fr in a.frames:
            r = []
            for j, k in enumerate(src):
                t, q, sc = fr[k] if k is not None else (None, None, None)
                r.append((tuple(joints[j][2]) if t is None else tuple(t), tuple(joints[j][3]) if q is None else tuple(q),
                          (1.0, 1.0, 1.0) if sc is None else ((sc, sc, sc) if np.isscalar(sc) else tuple(sc))))
            frames.append(r)
        anims[nm] = grip(frames, nm)
        meta['anims'][nm] = dict(frames=a.nframes, speed=float(np.hypot(a.dx[:, 0], a.dx[:, 1]).sum() / max(1, a.nframes)),
                                 yaw=float(a.dx[:, 3].sum()), loop=a.loop, key=a.key, next=-1,
                                 dx=[float(a.dx[:, 0].sum()), float(a.dx[:, 1].sum())])
        new.append(nm)
    alist = [dict(name=k, fps=30.0, loop=True, frames=anims[k]) for k in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    steps.stamp(meta, STEP, new)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, len(new), 'animations:', ', '.join(new))


def add(char):
    if char == 'Brute': return add_brute(char)
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(BE_A50): print(char, 'skipped'); return
    B, nodes, take, split, ce = soi7(CHARS[char])
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    st = meta.get('steps') or {}
    for k in st.get(STEP, []) + st.pop('hunter_be_anims', []): anims.pop(k, None); meta['anims'].pop(k, None)
    jn = [j[0] for j in joints]
    src = [nodes.index(n) if n in nodes else None for n in jn]          # body joint -> SOI7 node
    if sum(s is not None for s in src) < len(nodes): print(char, 'skipped: not the', CHARS[char], 'biped'); return

    def on_body(a):
        out = []
        for fr in a.frames:
            r = []
            for j, k in enumerate(src):
                t, q, s = (fr[k] if k is not None else (None, None, None))
                t = tuple(joints[j][2]) if t is None else tuple(t)
                q = tuple(joints[j][3]) if q is None else tuple(q)
                s = (1.0, 1.0, 1.0) if s is None else ((s, s, s) if np.isscalar(s) else tuple(s))
                r.append((t, q, s))
            out.append(r)
        return out
    owned = set(anims)
    new = []
    for n in split: anims.pop(n, None); meta['anims'].pop(n, None)
    for n in take:
        a = B[n]
        if a.type == 0:
            if n in owned and n not in ce: continue     # a new name the body already has (a Halo 2 stance): kept
            frames, nm, dx = on_body(a), n, a.dx
        elif re.search(r'fire-|reload', n):
            words = n.split(' ')
            base = next((B[k] for k in sorted(B) if k.startswith(' '.join(words[:2]) + ' idle') and B[k].type == 0), None)
            if base is None: continue
            nm = n + ' baked'
            if nm in owned and n not in ce: continue
            b = copy.copy(base); b.frames = hm.bake_overlay(base.frames[0], a.frames)
            frames, dx = on_body(b), np.zeros((len(b.frames), 4))
        else:
            continue
        anims[nm] = frames
        meta['anims'][nm] = dict(frames=len(frames), speed=float(np.hypot(dx[:, 0], dx[:, 1]).sum() / max(1, len(frames))),
                                 yaw=float(dx[:, 3].sum()), loop=a.loop, key=a.key, next=-1,
                                 dx=[float(dx[:, 0].sum()), float(dx[:, 1].sum())])
        new.append(nm)
    alist = [dict(name=k, fps=30.0, loop=True, frames=anims[k]) for k in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    steps.stamp(meta, STEP, new)
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, len(new), 'animations' + (f', dropped {", ".join(split)}' if split else '') + ':', ', '.join(sorted(new)))


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
