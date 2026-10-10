"""Halo 2's pilots -> $HCE_OUT/models/MarineKit/h2_pilot_<face>.iqm (whole heads for the Marine kit)

    python3 extract_h2_pilot.py        # after extract_marine_kit.py

Halo 2's Marine (01b_spacestation.map) has a 'pilot' permutation of its helmet region: the Pelican crews' flight
helmet with its tinted visor. Each piece here is one of Halo 2's Marine faces (Smith, Banks, Dion, Morgan, Perez,
Walter) with its eyes and teeth, under that flight helmet: a whole head, worn in place of the Halo CE Marine's own
(build_pack: the Pilots, HCE_MarinePilot*). As extract_h2_odst.py does for the ODST helmet, Halo 2's head is moved
by the difference between the two Marines' heads' bind positions (they're modelled in the same frame, at the same
scale) and bound wholly to the CE head bone. The visor gets its own dark tint and the kit visors' cube-map shader
(build_pack.KIT_OWN_VISORS). The pieces go into MarineKit.json as enclosed heads that no Marine outfit rolls.
"""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))   # readers and writers live in lib/
from iqm import read_iqm, write_iqm
from h2_elite_anims import MAP01B, CACHE01B, MARINE
import extract_h2_odst as eo
import extract_h2_elite_kit as ek
KIT = eo.KIT
FACES = ('smith', 'banks', 'dion', 'morgan', 'perez', 'walter')
VISOR = 'mk_h2_pilot_visor.png'
VISOR_RGB = ((0.42, 0.30, 0.16), (0.10, 0.07, 0.05))   # smoked amber, lighter at the brow


def main():
    from h2map import H2Map, render_model
    import extract_h2_brute as hb
    from PIL import Image
    m = H2Map(MAP01B, CACHE01B)
    R = render_model(m, MARINE)
    nodes = R['nodes']
    J, _, A = read_iqm(f'{KIT}/helmet_closed.iqm')
    alist = [dict(name=n, fps=30.0, loop=True, frames=fr) for n, fr in A.items()]
    bone, cehead = eo.ce_head(J)
    shift = cehead - eo.world(nodes, [n['name'] for n in nodes].index('head'))
    ek.KIT = KIT                                   # its colour maps go into the Marine kit
    t, b = np.array(VISOR_RGB[0]), np.array(VISOR_RGB[1])
    y = np.linspace(0, 1, 64)[:, None, None]
    Image.fromarray(np.clip((t * (1 - y) + b * y) * 255 * np.ones((64, 64, 3)), 0, 255).astype(np.uint8)).save(f'{KIT}/{VISOR}')
    done = {}
    def tex(shader):
        if shader not in done:
            fn = f'mk_h2_{shader}.png'
            ek.colour_map(m, hb, eo.shader_bitmaps(m, R, shader), fn)
            done[shader] = fn
        return done[shader]
    kj = f'{KIT}/MarineKit.json'
    kit = json.load(open(kj))
    for face in FACES:
        pid = f'h2_pilot_{face}'
        meshes = []
        for mm in hb.model_meshes(m, R, keep={('head', face), ('helmet', 'pilot')}):
            mat = VISOR if 'visor' in mm['shader'] else tex(mm['shader'])
            n = len(mm['pos'])
            meshes.append(dict(name=mm['shader'], material=mat, pos=np.array(mm['pos'], float) + shift, nrm=np.array(mm['nrm'], float),
                               uv=np.array(mm['uv'], float), bidx=np.tile(np.array([bone, 0, 0, 0], np.uint8), (n, 1)),
                               bw=np.tile(np.array([255, 0, 0, 0], np.uint8), (n, 1)), tris=np.array(mm['tris'])[:, [0, 2, 1]]))
        write_iqm(f'{KIT}/{pid}.iqm', J, meshes, alist)
        kit['pieces'][pid] = dict(slot='head', source=f'halo2 marine head {face} + helmet pilot', file=f'{pid}.iqm', shell=False,
                                  enclosed=True, needs_helmet=False, tris=int(sum(len(x['tris']) for x in meshes)))
        if pid not in kit['enclosed']: kit['enclosed'].append(pid)
        print(pid, [x['material'] for x in meshes], kit['pieces'][pid]['tris'], 'tris')
    json.dump(kit, open(kj, 'w'), indent=1)


if __name__ == '__main__':
    main()
