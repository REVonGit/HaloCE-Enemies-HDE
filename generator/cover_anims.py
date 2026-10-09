"""Halo 2's corner-cover, hoist and vault animations on the Halo CE bodies -> out/models/<char>/<char>.iqm and .json

    python3 cover_anims.py [char ...]

Halo CE's AI has no cover animations: its units crouch or stand in the open. Halo 2's have a full corner set, on
the same 3ds Max bipeds as reload_anims.py uses: a unit steps in beside a corner (enter), waits there pressed to
the wall (idle), leans out past the edge to shoot (cover -> open transition, then the open pose held), leans back
(open -> cover) and steps out again (exit), for each side. Marines and Elites have it in the rifle and pistol stances
(01b_spacestation.map, 08a_deltacliffs.map), Brutes in the Brute Shot stance (08b_deltacontrol.map). Halo 2 also
climbs: 'hoist' pulls the body up onto a ledge, 'vault' takes it over a low wall, for Marines, Elites, Grunts,
Jackals and Brutes.

Each is moved onto the CE skeleton bone for bone (reload_anims.h2_anims) and added under a CE-style name that the
generator's animation table (build_pack.anim_table) looks for:

    stand <stance> cover-left-enter / -idle / -peek / -open / -unpeek / -exit   (and cover-right-...)
    stand <stance> hoist, stand <stance> vault

'-open' is the last frame of the lean-out held as a loop (Halo 2 only stores the transitions for most bodies).
The corner animations keep Halo 2's root motion as part of the pose (the step into the corner and the lean out are
what the player sees). The hoist and vault move the whole body up and forward; that travel is measured from the
root and written to the JSON as 'move' (Halo world units: forward, left, up), so the AI can put the actor where the
animation leaves the body once it has played (build_pack.py turns it into HCE_AnimMove).

Run after reload_anims.py; re-running it replaces its own animations and leaves everything else in the IQM as it is.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
from h2_elite_anims import MAP08A, CACHE08A, MAP01B, CACHE01B, ELITE, MARINE
from reload_anims import h2_anims, GRUNT, JACKAL
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
MAP08B = os.environ.get('HCE_H2_MAP08B', '08b_deltacontrol.map')   # MCC halo2\\h2_maps_win64_dx11
CACHE08B = os.environ.get('HCE_H2_CACHE08B') or None
BRUTE = r'objects\characters\brute\brute'


def corner(h2stance, base, ce):
    """the corner set of one Halo 2 stance -> {CE name: (Halo 2 animation, base idle)}"""
    out = {}
    for side in ('left', 'right'):
        c, o = f'corner_cover_{side}:{h2stance}', f'corner_open_{side}:{h2stance}'
        out[f'stand {ce} cover-{side}-enter'] = (f'{c}:enter', base)
        out[f'stand {ce} cover-{side}-idle'] = (f'{c}:idle', base)
        out[f'stand {ce} cover-{side}-peek'] = (f'{c}:idle:2:corner_open_{side}:idle', base)
        out[f'stand {ce} cover-{side}-unpeek'] = (f'{o}:idle:2:corner_cover_{side}:idle', base)
        out[f'stand {ce} cover-{side}-exit'] = (f'{c}:exit', base)
    return out


def climb(h2stance, base, ce, hoist='hoist', vault='vault'):
    return {f'stand {ce} hoist': (f'hoist:{h2stance}:{hoist}', base), f'stand {ce} vault': (f'vault:{h2stance}:{vault}', base)}


MARINE_SET = {**corner('rifle', 'combat:rifle:idle:var0', 'rifle'), **corner('pistol', 'combat:pistol:idle', 'pistol'),
              **climb('rifle', 'combat:rifle:idle:var0', 'rifle', 'enter', 'enter'),
              **climb('pistol', 'combat:pistol:idle', 'pistol', 'enter', 'enter'),
              **climb('missile', 'combat:missile:idle', 'missle', 'enter', 'enter')}
ELITE_SET = {**corner('rifle', 'combat:rifle:idle', 'rifle'), **corner('pistol', 'combat:pistol:idle', 'pistol'),
             **climb('rifle', 'combat:rifle:idle', 'rifle', 'enter', 'enter:var2'),
             **climb('pistol', 'combat:pistol:idle', 'pistol', 'enter', 'enter:var1'),
             **climb('missile', 'combat:missile:idle', 'missle', 'enter', 'enter:var1'),
             **climb('sword', 'combat:sword:idle', 'sword', 'enter', 'enter:var1')}
GRUNT_SET = {**climb('pistol', 'combat:pistol:idle', 'pistol', 'enter', 'enter'),
             **climb('missile', 'combat:missile:idle', 'missle', 'enter', 'enter')}
JACKAL_SET = {'stand rifle hoist': ('hoist:rifle:enter:var0', 'combat:rifle:idle'),
              'stand pistol hoist': ('hoist:rifle:enter:var0', 'combat:rifle:idle')}
BRUTE_SET = {**corner('support', 'combat:support:idle', 'support'),
             **corner('support', 'combat:support:idle', 'rifle'),           # the rifle stance borrows the Brute Shot's
             **climb('rifle', 'combat:rifle:idle', 'rifle', 'enter:var1', 'enter:var1'),
             **climb('support', 'combat:support:idle', 'support', 'enter:var1', 'enter:var1'),
             **climb('melee', 'combat:melee:idle', 'melee', 'enter:var1', 'enter:var1')}
CHARS = {
    'Marine': (MARINE, MAP01B, CACHE01B, MARINE_SET), 'MarineArmored': (MARINE, MAP01B, CACHE01B, MARINE_SET),
    'MarineODST': (MARINE, MAP01B, CACHE01B, MARINE_SET),
    'Elite': (ELITE, MAP08A, CACHE08A, ELITE_SET), 'EliteSpecial': (ELITE, MAP08A, CACHE08A, ELITE_SET),
    'EliteRifle': (ELITE, MAP08A, CACHE08A, ELITE_SET), 'EliteZealot': (ELITE, MAP08A, CACHE08A, ELITE_SET),
    'Grunt': (GRUNT, MAP08A, CACHE08A, GRUNT_SET), 'GruntSpecOps': (GRUNT, MAP08A, CACHE08A, GRUNT_SET),
    'Jackal': (JACKAL, MAP08A, CACHE08A, JACKAL_SET), 'JackalMajor': (JACKAL, MAP08A, CACHE08A, JACKAL_SET),
    'H2Jackal': (JACKAL, MAP08A, CACHE08A, JACKAL_SET),
    'Brute': (BRUTE, MAP08B, CACHE08B, BRUTE_SET),
}
MARK = (' cover-left-', ' cover-right-', ' hoist', ' vault')


def add(char):
    model, path, cache, plan = CHARS[char]
    pi, pj = f'{OUT}/models/{char}/{char}.iqm', f'{OUT}/models/{char}/{char}.json'
    if not os.path.exists(pi) or not os.path.exists(path): print(char, 'skipped'); return
    joints, meshes, anims = read_iqm(pi)
    meta = json.load(open(pj))
    new = h2_anims(model, path, cache, plan, joints)
    root = next(i for i, j in enumerate(joints) if j[1] < 0)
    # the held lean-out: the peek's last frame
    for k in [k for k in new if k.endswith('-peek')]:
        new[k[:-5] + '-open'] = [new[k][-1], new[k][-1]]
    for k in [k for k in anims if k.startswith('stand ') and any(s in k for s in MARK)]: anims.pop(k)
    for k in [k for k in meta['anims'] if k.startswith('stand ') and any(s in k for s in MARK)]: meta['anims'].pop(k)
    anims.update(new)
    if 'ponytail1' in ' '.join(j[0] for j in joints) and char.startswith('Marine'):
        jn = [j[0] for j in joints].index('bip01 ponytail1')               # the Marine's jaw stays shut (extract_chars.py)
        for k in new:
            for fr in anims[k]: fr[jn] = (tuple(joints[jn][2]), tuple(joints[jn][3]), tuple(joints[jn][4]))
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in anims[n]])
             for n in sorted(anims)]
    meta['iqm_bytes'] = write_iqm(pi, [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in joints], meshes, alist)
    for k, fr in new.items():
        e = dict(frames=len(fr), speed=0.0, yaw=0.0, loop=k.endswith(('-idle', '-open')), key=-1, next=-1, dx=[0.0, 0.0])
        if k.endswith((' hoist', ' vault')):
            d = np.array(fr[-1][root][0]) - np.array(fr[0][root][0])
            e['move'] = [round(float(x), 4) for x in d]
        meta['anims'][k] = e
    json.dump(meta, open(pj, 'w'), indent=1)
    print(char, len(new), 'animations;', ', '.join(f"{k.split(' ', 2)[2]}={meta['anims'][k]['move']}" for k in sorted(new) if 'move' in meta['anims'][k]))


if __name__ == '__main__':
    for c in (sys.argv[1:] or CHARS):
        add(c)
