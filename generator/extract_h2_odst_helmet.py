"""Halo 2's ODST helmet as a Marine kit piece -> $HCE_OUT/models/MarineKit/h2_odst_helmet.iqm (+ its texture)

    python3 extract_h2_odst_helmet.py

Halo 2's Marine (01b_spacestation.map: HCE_H2_MAP, textures from HCE_H2_TEXTURES) has an 'odst' permutation of its head
region: the sealed ODST helmet with its visor. Halo 2's Marine is modelled in the same frame and at the same scale as
Halo CE's (their heads both sit 0.53-0.64 world units up), so the helmet is moved by the difference between the two
heads' bind positions and bound wholly to the CE Marine's head bone, like Elefant's kit pieces (extract_marine_kit.py).
Its neck collar is cut off (the bodies it goes on have their own). The visor takes the kit's visor texture, so it gets
the kit visors' cube-map reflection (build_pack.kit_visors). The piece is added to MarineKit.json (an enclosed helmet,
for the ODST variants and the Armored Marines' ODST outfit). Run after extract_marine_kit.py.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm
from h2_elite_anims import MAP01B, CACHE01B, MARINE, _qmul
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
KIT = f'{OUT}/models/MarineKit'
PID = 'h2_odst_helmet'
VISOR = 'mk_innie_visor_diff.png'            # the kit's visor texture: build_pack.kit_visors gives it the cube-map shader
DETAIL_TILE = 4                              # the detail map repeats this many times across the colour map
LIFT = 1.9                                   # brightness lift for Doom's sheen-less lighting
COLLAR_Z = 0.515                            # triangles wholly below this (the neck collar) are left off


def qrot(q, v):
    x, y, z, w = q
    u = np.array([x, y, z]); return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def world(nodes, k):
    t, q = np.array(nodes[k]['t'], float), np.array(nodes[k]['q'], float)
    p = nodes[k].get('parent', -1)
    while p is not None and p >= 0:
        pt, pq = np.array(nodes[p]['t'], float), np.array(nodes[p]['q'], float)
        t = pt + qrot(pq, t); q = _qmul(pq, q); p = nodes[p].get('parent', -1)
    return t


def ce_head(J):
    names = [j[0] for j in J]
    k = names.index('bip01 head')
    t, q = np.array(J[k][2], float), np.array(J[k][3], float)
    p = J[k][1]
    while p >= 0:
        t = np.array(J[p][2], float) + qrot(np.array(J[p][3], float), t); p = J[p][1]
    return k, t


def main():
    from PIL import Image
    from h2map import H2Map, render_model
    import extract_h2_brute as hb
    m = H2Map(MAP01B, CACHE01B)
    R = render_model(m, MARINE)
    nodes = R['nodes']
    hk = [n['name'] for n in nodes].index('head')
    J, M, A = read_iqm(f'{KIT}/helmet_closed.iqm')                 # the kit's skeleton and its bind animation
    bone, ce = ce_head(J)
    shift = ce - world(nodes, hk)
    print('head offset Halo 2 -> CE', shift.round(4))
    meshes = []
    for mm in hb.model_meshes(m, R):
        if mm['region'] != 'head' or mm['perm'] != 'odst': continue
        pos = np.array(mm['pos'], float) + shift
        tris = np.array(mm['tris'])
        keep = pos[tris].max(axis=1)[:, 2] >= COLLAR_Z
        tris = tris[keep]
        used = np.unique(tris)
        remap = -np.ones(len(pos), int); remap[used] = np.arange(len(used))
        visor = 'visor' in mm['shader']
        if visor: mat = VISOR
        else:
            shs = [s for s in R['shaders'] if s and s.endswith('\\' + mm['shader'])]
            bms = []
            if shs:
                sh = m.tag('shad', shs[0])['addr']
                for pp in m.block(sh + 0x20, 0x7C)[:1]:
                    for b in m.block(pp + 4, 0xC):
                        t = m.u('I', b)[0]
                        if t in m.byid: bms.append(m.byid[t]['name'])
            cands = [n for n in bms if not any(x in n for x in ('bump', 'default_', 'detail', 'cube_map', 'multipurpose', 'noise'))]
            print('  ', mm['shader'], 'bitmaps', bms[:6], '->', cands[:1])
            mat = f'mk_{PID}.png'
            im = hb.bitmap(m, cands[0]) if cands else Image.new('RGB', (8, 8), (70, 72, 70))
            im = np.asarray(im.convert('RGB'), float)
            det = [n for n in bms if 'detail' in n]            # Halo 2 lays its detail map over it (colour x detail x 2)
            if det:
                d = np.asarray(hb.bitmap(m, det[0]).convert('L').resize((im.shape[1] // DETAIL_TILE, im.shape[0] // DETAIL_TILE)), float)
                d = np.tile(d, (DETAIL_TILE, DETAIL_TILE))[:im.shape[0], :im.shape[1], None] / 255.0
                im = im * d * 2
            # its specular sheen is what keeps the charcoal shell from reading as flat black in Halo 2; Doom has none
            im = np.clip(im * LIFT, 0, 255).astype(np.uint8)
            Image.fromarray(im).save(f'{KIT}/{mat}')
        n = len(used)
        meshes.append(dict(name=mm['shader'], material=mat, pos=pos[used], nrm=np.array(mm['nrm'], float)[used],
                           uv=np.array(mm['uv'], float)[used], bidx=np.tile(np.array([bone, 0, 0, 0], np.uint8), (n, 1)),
                           bw=np.tile(np.array([255, 0, 0, 0], np.uint8), (n, 1)), tris=remap[tris][:, [0, 2, 1]]))
        print('  ', mm['shader'], n, 'verts', len(tris), 'tris (collar cut:', int((~keep).sum()), ')')
    alist = [dict(name=n, fps=30.0, loop=True, frames=fr) for n, fr in A.items()]
    write_iqm(f'{KIT}/{PID}.iqm', J, meshes, alist)
    kj = f'{KIT}/MarineKit.json'
    kit = json.load(open(kj))
    kit['pieces'][PID] = dict(slot='head', source='halo2 marine head odst', file=f'{PID}.iqm', shell=False, enclosed=True,
                              needs_helmet=False, tris=int(sum(len(x['tris']) for x in meshes)))
    if PID not in kit['enclosed']: kit['enclosed'].append(PID)
    for o in kit.get('outfits', {}).get('MarineArmored', []):           # the Armored Marines' ODST outfit wears it too
        heads = o['slots'].get('head', [])
        if heads and not any(p == PID for p, _ in heads): heads.append([PID, 2])
    json.dump(kit, open(kj, 'w'), indent=1)
    print('->', f'{KIT}/{PID}.iqm')


if __name__ == '__main__':
    main()
