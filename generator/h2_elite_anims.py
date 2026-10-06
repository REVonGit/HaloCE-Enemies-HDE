"""Halo 2 Elite animations on the Halo CE Elite skeleton.

The two rigs are the same 3ds Max biped: every CE bone ("bip01 <name>") has a Halo 2 counterpart ("<name>" with
underscores), with the same parent and the same child offset in its parent's frame (checked bone by bone). So a
Halo 2 bone's local rotation is the CE bone's local rotation; we keep CE's bone offsets (lengths) and let the root
move as Halo 2 moves it. Bones only CE has (the four mandible frames) hold their rest pose; Halo 2's extra bones
(fingers, face, physics_control) are dropped.

Used by extract_chars.py: Halo 2's fuel-rod stance ('missile', which Halo CE spells 'missle') on the Elite, and its
rifle stance (the beam rifle) on the Elite Special.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MAP08A = os.environ.get('HCE_H2_MAP08', '08a_deltacliffs.map')
CACHE08A = os.environ.get('HCE_H2_CACHE08') or None
ELITE = r'objects\characters\elite\elite'

# Halo 2 name -> CE-style name
MISSILE = {
    'combat:missile:idle': 'stand missle idle',
    'combat:missile:move_front': 'stand missle move-front', 'combat:missile:move_back': 'stand missle move-back',
    'combat:missile:move_left': 'stand missle move-left', 'combat:missile:move_right': 'stand missle move-right',
    'combat:missile:turn_left': 'stand missle turn-left', 'combat:missile:turn_right': 'stand missle turn-right',
    'combat:missile:dive_front': 'stand missle dive-front', 'combat:missile:dive_left': 'stand missle dive-left',
    'combat:missile:dive_right': 'stand missle dive-right',
    'combat:missile:evade_left': 'stand missle evade-left', 'combat:missile:evade_right': 'stand missle evade-right',
    'combat:missile:throw_grenade': 'stand missle throw-grenade',
    'combat:missile:airborne': 'stand missle airborne', 'combat:missile:land_soft': 'stand missle land-soft',
    'combat:missile:land_hard': 'stand missle land-hard',
    'combat:missile:surprise_front': 'stand missle surprise-front', 'combat:missile:surprise_back': 'stand missle surprise-back',
    'combat:missile:signal_attack': 'stand missle signal-attack',
    'combat:missile:berserk': 'stand missle berserk',
    'combat:missile:smash_left': 'stand missle melee',             # a swing with the cannon
    'crouch:missile:idle': 'crouch missle idle', 'crouch:missile:move_front': 'crouch missle move-front',
}
MISSILE_FIRE = ('combat:missile:fire_1', 'combat:missile:idle', 'stand missle fire-1 fr baked')   # overlay, base, name

# Halo 2's rifle stance (how its Elites carry the beam rifle), for the beam-rifle Spec Ops Elite. Halo 2 has no
# rifle dives or evades: the generator falls back to the pistol ones.
RIFLE = {
    'combat:rifle:idle': 'stand rifle idle',
    'combat:rifle:move_front': 'stand rifle move-front', 'combat:rifle:move_back': 'stand rifle move-back',
    'combat:rifle:move_left': 'stand rifle move-left', 'combat:rifle:move_right': 'stand rifle move-right',
    'combat:rifle:turn_left': 'stand rifle turn-left', 'combat:rifle:turn_right': 'stand rifle turn-right',
    'combat:rifle:throw_grenade': 'stand rifle throw-grenade', 'combat:rifle:melee': 'stand rifle melee',
    'combat:rifle:airborne': 'stand rifle airborne', 'combat:rifle:land_soft': 'stand rifle land-soft',
    'combat:rifle:land_hard': 'stand rifle land-hard', 'combat:rifle:berserk': 'stand rifle berserk',
    'combat:rifle:surprise_front': 'stand rifle surprise-front', 'combat:rifle:surprise_back': 'stand rifle surprise-back',
    'combat:rifle:signal_attack': 'stand rifle signal-attack', 'combat:rifle:warn': 'stand rifle warn',
    'crouch:rifle:idle': 'crouch rifle idle', 'crouch:rifle:move_front': 'crouch rifle move-front',
}
RIFLE_FIRE = ('combat:rifle:fire_1', 'combat:rifle:idle', 'stand rifle fire-1 csr baked')
STANCES = {'missile': (MISSILE, MISSILE_FIRE), 'rifle': (RIFLE, RIFLE_FIRE)}

# Halo 2's Marine pistol stance (01b_spacestation.map) on the Halo CE Marine -- also one 3ds Max biped (same bone
# names and offsets; Halo 2 adds fingers, face and physics bones, CE a ponytail bone that holds its rest pose).
# Named 'h2pistol' so Halo CE's own pistol set (the needler Marines') stays as it was; the Magnum and Sidekick
# Marines use this one. Halo 2 has no pistol grenade throw, surprise or signal: the generator falls back to CE's.
MAP01B = os.environ.get('HCE_H2_MAP', '01b_spacestation.map')   # MCC halo2\\h2_maps_win64_dx11
CACHE01B = os.environ.get('HCE_H2_CACHE') or None
MARINE = r'objects\characters\marine\marine'
H2PISTOL = {
    'combat:pistol:idle': 'stand h2pistol idle', 'combat:pistol:warn': 'stand h2pistol warn',
    'combat:pistol:move_front': 'stand h2pistol move-front', 'combat:pistol:move_back': 'stand h2pistol move-back',
    'combat:pistol:move_left': 'stand h2pistol move-left', 'combat:pistol:move_right': 'stand h2pistol move-right',
    'combat:pistol:turn_left': 'stand h2pistol turn-left', 'combat:pistol:turn_right': 'stand h2pistol turn-right',
    'combat:pistol:dive_front': 'stand h2pistol dive-front', 'combat:pistol:dive_left:var1': 'stand h2pistol dive-left',
    'combat:pistol:dive_right:var1': 'stand h2pistol dive-right',
    'combat:pistol:evade_left': 'stand h2pistol evade-left', 'combat:pistol:evade_right': 'stand h2pistol evade-right',
    'combat:pistol:airborne': 'stand h2pistol airborne', 'combat:pistol:land_soft': 'stand h2pistol land-soft',
    'combat:pistol:land_hard': 'stand h2pistol land-hard', 'combat:pistol:melee': 'stand h2pistol melee',
    'crouch:pistol:idle': 'crouch h2pistol idle', 'crouch:pistol:move_front': 'crouch h2pistol move-front',
}
H2PISTOL_FIRE = ('combat:pistol:fire_1', 'combat:pistol:idle', 'stand h2pistol fire-1 baked')
STANCES['h2pistol'] = (H2PISTOL, H2PISTOL_FIRE)
STANCE_SOURCE = {'missile': (ELITE, MAP08A, CACHE08A), 'rifle': (ELITE, MAP08A, CACHE08A), 'h2pistol': (MARINE, MAP01B, CACHE01B)}


def _qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])


class Anim:
    """the fields extract_chars.py reads from a Halo CE animation"""
    def __init__(s, name, frames, mv, loop):
        s.name, s.frames, s.nframes = name, frames, len(frames)
        s.dx = np.asarray(mv, float).reshape(-1, 4) if len(mv) else np.zeros((len(frames), 4))
        s.loop, s.key, s.next, s.type = loop, -1, -1, 0


def missile_anims(ce_joints, path=MAP08A, cache=CACHE08A):
    return stance_anims(ce_joints, 'missile', path, cache)


def stance_anims(ce_joints, stance, path=None, cache=None):
    """ce_joints: [(name, parent, t, q, s)] of a CE model -> [Anim] of a Halo 2 stance, in CE joint order"""
    plan, fire = STANCES[stance]
    model, dpath, dcache = STANCE_SOURCE[stance]
    path = path or dpath; cache = cache or dcache
    if not os.path.exists(path): return []
    sys.path.insert(0, '/home/claude/spv3')
    from h2map import H2Map, render_model
    import h2anim
    m = H2Map(path, cache)
    nodes = render_model(m, model)['nodes']
    h2i = {n['name']: i for i, n in enumerate(nodes)}
    _, an = h2anim.graph(m, model)
    byname = {x['name']: x for x in an}
    defaults = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
    # CE joint -> Halo 2 node (or None: keep the CE rest pose)
    src = [h2i.get(j[0].replace('bip01 ', '').replace(' ', '_')) for j in ce_joints]
    rest = [(tuple(j[2]), tuple(j[3])) for j in ce_joints]

    def to_ce(fr):
        out = []
        for row in fr:
            r = []
            for j, k in enumerate(src):
                t, q = rest[j]
                if k is not None:
                    q = tuple(row[k][1])
                    if ce_joints[j][1] < 0: t = tuple(row[k][0])       # the root moves as Halo 2 moves it
                r.append((t, q, (1.0, 1.0, 1.0)))
            out.append(r)
        return out

    res = []
    for h2n, cen in plan.items():
        x = byname.get(h2n)
        if not x: continue
        fr, mv = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], defaults)
        res.append(Anim(cen, to_ce(fr), mv, bool(x['loop'])))
    on, bn, name = fire
    if on in byname and bn in byname:
        o = byname[on]; b = byname[bn]
        ident = [(np.zeros(3), np.array([0, 0, 0, 1.0]))] * len(nodes)
        ofr, _ = h2anim.decode(o['data'], o['sizes'], o['frames'], o['nodes'], ident)
        b0 = h2anim.decode(b['data'], b['sizes'], b['frames'], b['nodes'], defaults)[0][0]
        frames = []
        for f in ofr:
            row = []
            for k in range(len(nodes)):
                bt, bq, bs = b0[k]; ot, oq, _ = f[k]
                q = _qmul(np.array(bq), np.array(oq)); q /= np.linalg.norm(q)
                row.append((tuple(np.array(bt) + np.array(ot)), tuple(q), bs))
            frames.append(row)
        res.append(Anim(name, to_ce(frames), np.zeros((len(frames), 4)), False))
    return res
