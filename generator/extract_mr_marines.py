"""Mercury Rising's medic and female Marine -> $HCE_OUT/models/MarineKit/mr_medic_body.iqm and mr_female_body.iqm

    python3 extract_mr_marines.py          # after extract_spv3.py MarineMedic MarineFemale and extract_marine_kit.py

Both bodies come from aLTis's Mercury Rising (Steam Workshop 3021510694; extract_spv3.py reads them from its maps into
out/models/MarineMedic and out/models/MarineFemale). Their skeletons are the Halo CE Marine's 20 bones, name for name,
so each is written as one Marine kit piece on the CE Marine's own skeleton (like the Halo 2 ODST's whole body,
extract_h2_odst.py): build_pack.py hides the Marine and wears the piece instead, so it plays every Marine animation,
holds every gun of the arsenal and fights with everything the Marines have.
  * the medic's bind pose is the Marine's: its vertices stay where they are
  * the female Marine's skeleton is her own (a little shorter, narrower shoulders, her own clavicle and neck turns):
    each vertex is carried from her bone's bind pose to the CE bone's (h2rig.retarget), blended by its weights, so
    she animates on the Marine's skeleton without tearing
Their armour is painted white with Halo's change-colour mask (the multipurpose map's blue): it takes the Marines'
olive drab here, the way the CE Marines' own textures are coloured. The pieces go into MarineKit.json as whole bodies
(no outfit or slot rolls them).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))
import os, sys, json
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2rig import ce_world, retarget
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
KIT = f'{OUT}/models/MarineKit'
# kit piece id -> extract_spv3.py pack id
BODIES = {'mr_medic_body': 'MarineMedic', 'mr_female_body': 'MarineFemale'}
OLIVE = np.array([0.50, 0.55, 0.38])      # the change colour: the CE Marines' olive drab (their armour's mean colour, lifted)


def stand_in(mm):
    """the CE Marine texture for a mesh whose own bitmap the map doesn't carry (a 16 x 16 placeholder): the medic's
    face is Halo CE's Marcus head under his own cap, so it takes that face's texture (the same mesh, the same UVs)"""
    _, mm_ce, _ = read_iqm(f'{OUT}/models/Marine/Marine.iqm')
    for m in mm_ce:
        if len(m['uv']) == len(mm['uv']) and np.abs(np.sort(m['uv'], 0) - np.sort(mm['uv'], 0)).max() < 1e-3:
            return 'Marine', m['material']
    return None


def texture(pid, src, mat, mm=None):
    """a body texture with the change colour applied, as mk_<piece>_<k>.png beside the kit's own"""
    out = f'mk_{pid}_{mat[len(src) + 1:]}'
    base = Image.open(f'{OUT}/models/{src}/{mat}').convert('RGB')
    if max(base.size) <= 16 and mm is not None and stand_in(mm):
        s, m = stand_in(mm)
        Image.open(f'{OUT}/models/{s}/{m}').convert('RGB').save(f'{KIT}/{out}')
        print(f'   {pid}: {mat} is a placeholder in the map; the CE Marine\'s {m} instead')
        return out
    mp = f'{OUT}/models/{src}/{mat[:-4]}_multi.png'
    b = np.asarray(base, np.float32) / 255.0
    if os.path.exists(mp):
        m = np.asarray(Image.open(mp).convert('RGB').resize(base.size), np.float32)[..., 2:3] / 255.0
        b = b * (1 - m) + b * OLIVE * m
    Image.fromarray(np.clip(b * 255, 0, 255).astype(np.uint8)).save(f'{KIT}/{out}')
    return out


def main():
    """each BODIES entry retargeted onto the kit's skeleton and written as out/models/MarineKit/<piece>.iqm with its
    textures (mk_<piece>_*.png), and added to MarineKit.json as a whole body (slot 'body', whole=True)"""
    MJ, _, MA = read_iqm(f'{KIT}/helmet_closed.iqm')          # the kit's skeleton (the CE Marine's) and its bind animation
    alist = [dict(name=n, fps=30.0, loop=True, frames=fr) for n, fr in MA.items()]
    mw = ce_world(MJ)
    names = [j[0] for j in MJ]
    kj = f'{KIT}/MarineKit.json'
    kit = json.load(open(kj))
    for pid, src in BODIES.items():
        J, M, _ = read_iqm(f'{OUT}/models/{src}/{src}.iqm')
        sw = ce_world(J)
        tomap = [names.index(j[0]) for j in J]
        out = []
        for mm in M:
            bi = np.asarray(mm['bidx'], int); bw = np.asarray(mm['bw'], float) / 255.0
            P, N, cb, w8 = retarget(mm['pos'], mm['nrm'], bi, bw, sw, mw, tomap)
            out.append(dict(name=mm['name'], material=texture(pid, src, mm['material'], mm), pos=P, nrm=N,
                            uv=np.asarray(mm['uv'], float), bidx=cb, bw=w8, tris=np.asarray(mm['tris'])))
            moved = np.abs(P - np.asarray(mm['pos'], float)).max()
            print(f'   {pid} {mm["name"]}: {len(P)} verts, {len(mm["tris"])} tris, moved up to {moved:.3f} wu')
        write_iqm(f'{KIT}/{pid}.iqm', MJ, out, alist)
        kit['pieces'][pid] = dict(slot='body', source=f'mercury rising {src}', file=f'{pid}.iqm', shell=False, enclosed=True,
                                  needs_helmet=False, whole=True, tris=int(sum(len(x['tris']) for x in out)))
    json.dump(kit, open(kj, 'w'), indent=1)
    print('->', ', '.join(f'{KIT}/{p}.iqm' for p in BODIES))


if __name__ == '__main__':
    main()
