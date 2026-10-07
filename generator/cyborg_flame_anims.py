"""The Master Chief's flamethrower stance on the Marines -> out/models/{Marine,MarineArmored}/<char>.iqm and .json

    python3 cyborg_flame_anims.py

Halo CE's flamethrower is a 'support' weapon, carried low at the hip with the left hand on the fore-grip. Only the
cyborg (the Master Chief) has animations for it -- the PC version's multiplayer set, which SPV3's campaign maps carry
(a30_1.map: characters\\cyborg\\cyborg, 'stand support ...', 'crouch support ...', the 'ft' melee and reload). The
cyborg and the Marine are the same 3ds Max biped ('bip01 ...' bones), so the cyborg's local bone rotations play on
the Marine as they are; the Marine keeps his own bone lengths, and the pelvis moves as the cyborg's does, scaled to
the Marine's height. Bones only the Marine has (the jaw, the ponytail) hold their rest pose.

Base animations (idle, moves, turns, airborne, landings, grenade throw, flinch, crouch) come over as they are; the
melee and reload are Halo's replacement animations (only the arms and torso), laid over the stance idle. The
flamethrower has no firing overlay: 'stand support fire-1 baked' is the idle. Names are the generator's
(build_pack.anim_table): 'stand support idle', 'stand support melee', 'stand support reload-1'...

Run after extract_chars.py and the gore / blood / arsenal steps (and reload_anims.py); re-running replaces only these.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
import halomodel as hm
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
MAP = os.environ.get('HCE_SPV3_A30', 'a30_1.map')
CYBORG = 'characters\\cyborg\\cyborg'
# Halo name -> pack name
NAMES = {
    'stand support idle': 'stand support idle', 'stand support move-front': 'stand support move-front',
    'stand support move-back': 'stand support move-back', 'stand support move-left': 'stand support move-left',
    'stand support move-right': 'stand support move-right', 'stand support turn-left': 'stand support turn-left',
    'stand support turn-right': 'stand support turn-right', 'stand support airborne': 'stand support airborne',
    'stand support land-soft': 'stand support land-soft', 'stand support land-hard': 'stand support land-hard',
    'stand support throw-grenade': 'stand support throw-grenade', 'stand support stunned-front': 'stand support surprise-front',
    'crouch support idle': 'crouch support idle', 'crouch support move-front': 'crouch support move-front',
    'stand support ft melee': 'stand support melee', 'stand support ft reload-1': 'stand support reload-1',
}
CHARS = ('Marine', 'MarineArmored')


def cyborg_anims():
    from pcmap import PCMap, gbx_geometry
    from tags import tag
    m = PCMap(MAP)
    _geo = hm.Model.geometry
    hm.Model.geometry = lambda s, gi: gbx_geometry(s.m, s.geoms[gi].addr)
    try:
        bt = next(t for t in m.find('bipd') if t['name'] == CYBORG)
        B = tag(m, bt, 'biped_definition')
        M = hm.Model(m, B['model'])
        nodes = [n['name'] for n in M.nodes]
        rest = [(np.array(n['t']), np.array(n['q'])) for n in M.nodes]
        an = {a.name: a for a in hm.read_animations(m, B['animation_graph'], len(nodes))}
    finally:
        hm.Model.geometry = _geo
    return nodes, rest, an


def retarget(joints, nodes, crest, frames):
    """cyborg frames (local t, q per node) -> the Marine's joints"""
    ci = {n: i for i, n in enumerate(nodes)}
    src = [ci.get(j[0]) for j in joints]
    root = next(i for i, j in enumerate(joints) if j[1] < 0)
    k0 = ci.get(joints[root][0])
    scale = (abs(joints[root][2][2]) / max(1e-6, abs(crest[k0][0][2]))) if k0 is not None else 1.0
    out = []
    for fr in frames:
        row = []
        for j, k in enumerate(src):
            t, q = tuple(joints[j][2]), tuple(joints[j][3])
            if k is not None:
                q = tuple(fr[k][1])
                if j == root: t = tuple(np.array(fr[k][0]) * scale)
            row.append((t, q, (1.0, 1.0, 1.0)))
        out.append(row)
    return out


def main():
    nodes, crest, an = cyborg_anims()
    idle = an['stand support idle'].frames[0]
    cy = {}
    for hn, pn in NAMES.items():
        a = an.get(hn)
        if not a: print('  no', hn); continue
        if a.type == 1: continue
        frames = a.frames
        if a.type == 2:          # replacement: the bones it leaves alone hold the idle
            frames = [[(f[n][0] if f[n][0] is not None else idle[n][0], f[n][1] if f[n][1] is not None else idle[n][1], 1.0)
                       for n in range(len(nodes))] for f in frames]
        cy[pn] = (frames, a.dx if a.type == 0 else np.zeros((len(frames), 4)))
    cy['stand support fire-1 baked'] = ([idle] * 6, np.zeros((6, 4)))
    for char in CHARS:
        pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
        if not os.path.exists(pi): continue
        joints, meshes, anims = read_iqm(pi)
        meta = json.load(open(pj))
        for k in [k for k in anims if ' support ' in k]: anims.pop(k)
        for k in [k for k in meta['anims'] if ' support ' in k]: meta['anims'].pop(k)
        jn = [j[0] for j in joints].index('bip01 ponytail1') if 'bip01 ponytail1' in [j[0] for j in joints] else -1
        for pn, (frames, dx) in cy.items():
            fr = retarget(joints, nodes, crest, frames)
            if jn >= 0:                          # the jaw stays shut (extract_chars.py)
                for f in fr: f[jn] = (tuple(joints[jn][2]), tuple(joints[jn][3]), tuple(joints[jn][4]))
            anims[pn] = fr
            root = next(i for i, j in enumerate(joints) if j[1] < 0)
            k0 = nodes.index(joints[root][0]) if joints[root][0] in nodes else None
            sc = abs(joints[root][2][2]) / max(1e-6, abs(crest[k0][0][2])) if k0 is not None else 1.0
            dx = dx * np.array([sc, sc, sc, 1.0])                 # strides scaled to the Marine
            speed = float(np.hypot(dx[:, 0], dx[:, 1]).sum() / max(1, len(fr)))
            meta['anims'][pn] = dict(frames=len(fr), speed=speed, yaw=float(dx[:, 3].sum()), loop=True, key=-1, next=-1,
                                     dx=[float(dx[:, 0].sum()), float(dx[:, 1].sum())])
        alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in f] for f in anims[n]])
                 for n in sorted(anims)]
        meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
        json.dump(meta, open(pj, 'w'), indent=1)
        print(char, sorted(cy))


if __name__ == '__main__':
    main()
