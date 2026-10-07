"""Halo 2's reload and overheat animations on the Halo CE bodies -> out/models/<char>/<char>.iqm and .json

    python3 reload_anims.py [char ...]

Halo CE's AI never reloads or overheats on screen, so its bodies have no such animations. Halo 2's do, on the same 3ds
Max bipeds (see h2_elite_anims.py): the Marine's rifle, shotgun, pistol and rocket reloads and its plasma overheats
(01b_spacestation.map), the Elite's needler, fuel-rod and carbine reloads and its plasma-pistol, plasma-rifle and
beam-rifle vents, the Grunt's plasma-pistol vent and the Jackal's (08a_deltacliffs.map).

Halo 2 stores them two ways. An overlay (type 1) adds to whatever the body is doing; it is baked onto the stance's
idle, as extract_chars.py bakes the fire overlays. A replacement (type 2) animates the arms and torso; the bones it
leaves alone take the stance's idle pose. Either way the result is moved onto the CE skeleton bone for bone (Halo 2
local rotations, CE bone offsets) and added to the character's IQM under a CE-style name the generator's
animation table looks for:

    stand <stance> reload-1    a magazine (or the needler's needles, the fuel rod's cell)
    stand <stance> reload-sg   the shotgun's shells
    stand <stance> overheat    a plasma weapon venting

Run after extract_chars.py (which writes the IQM from scratch) and the gore / blood / arsenal steps; re-running it
replaces its own animations and leaves everything else in the IQM as it is.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2_elite_anims import _qmul, MAP08A, CACHE08A, MAP01B, CACHE01B, ELITE, MARINE
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
GRUNT = r'objects\characters\grunt\grunt'
JACKAL = r'objects\characters\jackal\jackal'

# CE name: (Halo 2 animation, the stance idle it plays from)
MARINE_SET = {
    'stand rifle reload-1': ('combat:rifle:reload_1', 'combat:rifle:idle:var0'),
    'stand rifle reload-sg': ('combat:rifle:sg:reload_1', 'combat:rifle:idle:var0'),
    'stand rifle overheat': ('combat:rifle:overheat', 'combat:rifle:idle:var0'),
    'stand pistol reload-1': ('combat:pistol:reload_1', 'combat:pistol:idle'),
    'stand pistol overheat': ('combat:pistol:overheat', 'combat:pistol:idle'),
    'stand missle reload-1': ('combat:missile:reload_1', 'combat:missile:idle'),
}
ELITE_SET = {
    'stand pistol overheat': ('combat:pistol:overheated', 'combat:pistol:idle'),
    'stand pistol reload-ne': ('combat:pistol:ne:reload_1', 'combat:pistol:idle'),
    'stand missle reload-1': ('combat:missile:reload_1', 'combat:missile:idle'),
    'stand rifle reload-1': ('combat:rifle:reload_1', 'combat:rifle:idle'),
    'stand rifle overheat': ('combat:rifle:overheated', 'combat:rifle:idle'),
}
GRUNT_SET = {
    'stand pistol overheat': ('combat:pistol:pp:reload_1', 'combat:pistol:idle'),
    'stand pistol reload-1': ('combat:pistol:pp:reload_1', 'combat:pistol:idle'),    # the needler: the same hand-on-gun beat
}
JACKAL_SET = {
    'stand pistol overheat': ('combat:pistol:overheat', 'combat:pistol:idle'),
    'stand pistol reload-1': ('combat:pistol:pr:reload_1', 'combat:pistol:idle'),
    'stand rifle reload-1': ('combat:rifle:reload_1', 'combat:rifle:idle'),
}
CHARS = {
    'Marine': (MARINE, MAP01B, CACHE01B, MARINE_SET), 'MarineArmored': (MARINE, MAP01B, CACHE01B, MARINE_SET),
    'Elite': (ELITE, MAP08A, CACHE08A, ELITE_SET), 'EliteSpecial': (ELITE, MAP08A, CACHE08A, ELITE_SET),
    'EliteRifle': (ELITE, MAP08A, CACHE08A, ELITE_SET),
    'Grunt': (GRUNT, MAP08A, CACHE08A, GRUNT_SET), 'GruntSpecOps': (GRUNT, MAP08A, CACHE08A, GRUNT_SET),
    'Jackal': (JACKAL, MAP08A, CACHE08A, JACKAL_SET), 'JackalMajor': (JACKAL, MAP08A, CACHE08A, JACKAL_SET),
    'H2Jackal': (JACKAL, MAP08A, CACHE08A, JACKAL_SET),
}
MARK = ' reload-', ' overheat'


def h2_anims(model, path, cache, plan, ce_joints):
    sys.path.insert(0, '/home/claude/spv3')
    from h2map import H2Map, render_model
    import h2anim
    m = H2Map(path, cache)
    nodes = render_model(m, model)['nodes']
    h2i = {n['name']: i for i, n in enumerate(nodes)}
    _, an = h2anim.graph(m, model)
    byname = {x['name']: x for x in an}
    bind = [(np.array(n['t']), np.array(n['q'])) for n in nodes]
    ident = [(np.zeros(3), np.array([0, 0, 0, 1.0]))] * len(nodes)
    src = [h2i.get(j[0].replace('bip01 ', '').replace(' ', '_')) for j in ce_joints]

    def to_ce(fr):
        out = []
        for row in fr:
            r = []
            for j, k in enumerate(src):
                t, q = tuple(ce_joints[j][2]), tuple(ce_joints[j][3])
                if k is not None:
                    q = tuple(row[k][1])
                    if ce_joints[j][1] < 0: t = tuple(row[k][0])       # the root moves as Halo 2 moves it
                r.append((t, q, (1.0, 1.0, 1.0)))
            out.append(r)
        return out

    def base_frame(name):
        x = byname.get(name) or next((byname[k] for k in byname if k.startswith(name)), None)
        if not x: return None
        return h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], bind)[0][0]

    res = {}
    for cen, (h2n, basen) in plan.items():
        x = byname.get(h2n)
        b0 = base_frame(basen)
        if not x or b0 is None:
            print('  no', h2n if not x else basen); continue
        if x['type'] == 1:                    # overlay: idle * overlay
            ofr, _ = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], ident)
            frames = []
            for f in ofr:
                row = []
                for k in range(len(nodes)):
                    bt, bq, bs = b0[k]; ot, oq, _ = f[k]
                    q = _qmul(np.array(bq), np.array(oq)); q /= np.linalg.norm(q)
                    row.append((tuple(np.array(bt) + np.array(ot)), tuple(q), bs))
                frames.append(row)
        else:                                 # replacement: the bones it leaves alone hold the idle
            frames, _ = h2anim.decode(x['data'], x['sizes'], x['frames'], x['nodes'], [(np.array(t), np.array(q)) for t, q, _ in b0])
        res[cen] = to_ce(frames)
    return res


def add(char):
    model, path, cache, plan = CHARS[char]
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(path): print(char, 'skipped'); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    new = h2_anims(model, path, cache, plan, joints)
    for k in [k for k in anims if any(s in k for s in MARK) and k.startswith('stand ')]: anims.pop(k)
    for k in [k for k in meta['anims'] if any(s in k for s in MARK) and k.startswith('stand ')]: meta['anims'].pop(k)
    anims.update(new)
    if 'ponytail1' in ' '.join(j[0] for j in joints) and char.startswith('Marine'):
        jn = [j[0] for j in joints].index('bip01 ponytail1')               # the Marine's jaw stays shut (extract_chars.py)
        for k in new:
            for fr in anims[k]: fr[jn] = (tuple(joints[jn][2]), tuple(joints[jn][3]), tuple(joints[jn][4]))
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    for k, fr in new.items():
        meta['anims'][k] = dict(frames=len(fr), speed=0.0, yaw=0.0, loop=False, key=-1, next=-1, dx=[0.0, 0.0])
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, sorted(new))


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
