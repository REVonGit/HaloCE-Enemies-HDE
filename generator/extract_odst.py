"""The ODSTs (SPV3's Halo CE ODST, `characters\\marine_odst\\odst_marine`) and Fire Team Raven -> out/models/MarineODST/

    python3 extract_odst.py

* The body: SPV3's a50_1.map (HCE_SPV3_A50): the ODST model (legs, torso, arms, helmet, visor). It is rigged to the
  Halo CE Marine's 20 bones and plays the Marine's own animation graph, so it goes on the Marine's skeleton with every
  animation the Marine has now (Halo 2's stances, reloads, low ready, the flamethrower and plasma-rifle sets...),
  copied from out/models/Marine/Marine.iqm: run after the Marine steps (reload_anims.py, cyborg_flame_anims.py,
  marine_stances.py, low_ready_anims.py, marine_plasma_grip.py, marine_arsenal.py overlays).
* Fire Team Raven (Connor Dawn's models): SPV3's a10 (HCE_SPV3_A10): four ODSTs in their own colours (green, orange, blue, purple), the same
  model with their own textures -> MarineODST_<k>_raven_<colour>.png beside the base skins.
* The visor: Halo CE's visor shader reflects a cube map (the base ODST: the cyborg's 'reflection armor' cube, Fire
  Team Raven: 'cubemap dark gray') tinted by its perpendicular / parallel colours. The visor texture is written as
  that tint, and build_pack.py gives the visor a shader that looks the cube map up per pixel at run time (the six faces
  in a strip, MarineODST_cube_<name>.png), with Halo's tints and its fresnel blend.
The Marine's arsenal overlays (the guns as model attachments) and hand frame are shared, so any gun a Marine can
carry the ODST can too."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, shutil, sys, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm

A50 = os.environ.get('HCE_SPV3_A50', 'a50_1.map')                  # SPV3's a50
A10 = os.environ.get('HCE_SPV3_A10', 'a10_1.map')                  # SPV3's a10 (Fire Team Raven)
PID = 'MarineODST'
BODY = 'characters\\marine_odst\\odst'
RAVEN = {'green': 'characters\\marine_odst\\raven_green\\odst green',
         'orange': 'characters\\marine_odst\\raven_orange_you_glad\\odst orange',
         'blue': 'characters\\marine_odst\\raven_meth\\odst blue',
         'purple': 'characters\\marine_odst\\raven_purple\\odst purple'}


def extract_spv3(path, biped):
    """one SPV3 biped through extract_chars.extract into a scratch folder -> (folder, meta)"""
    import halomodel as hm
    import extract_chars as ec
    from pcmap import PCMap, gbx_geometry
    m = PCMap(path)
    tmp = tempfile.mkdtemp(); os.makedirs(f'{tmp}/models')
    old = ec.OUT, ec.char_weapons, hm.Model.geometry
    _geo = hm.Model.geometry
    ec.OUT = tmp; ec.char_weapons = lambda name: []
    hm.Model.geometry = lambda s_, gi: gbx_geometry(s_.m, s_.geoms[gi].addr) if isinstance(s_.m, PCMap) else _geo(s_, gi)
    try:
        meta = ec.extract(biped, PID, ['spv3'], {'spv3': m})
    finally:
        ec.OUT, ec.char_weapons, hm.Model.geometry = old
    return f'{tmp}/models/{PID}', meta


VISOR_CUBES = {r'characters\cyborg\bitmaps\cyborg reflection armor': 'cyborg',
               r'characters\elite\bitmaps\cubemap dark gray': 'dark_gray'}


def visor_params(path, colour=None):
    """the visor shader_model's reflection: (cube key, perpendicular brightness and tint, parallel brightness and tint)"""
    from pcmap import PCMap
    m = PCMap(path)
    want = 'h1_odst_visor' if colour is None else f'{colour} visor'
    t = next(t for t in m.find('soso') if t['name'].startswith('characters\\marine_odst\\') and t['name'].endswith(want))
    cube = m.byid.get(m.u('I', t['data'] + 0x164 + 12)[0], {}).get('name')
    pb, pr, pg, pbl, qb, qr, qg, qbl = m.u('8f', t['data'] + 0x144)
    return dict(cube=VISOR_CUBES.get(cube, 'dark_gray'), perp=[pb, [pr, pg, pbl]], par=[qb, [qr, qg, qbl]])


def cube_strip(key, out, size=128):
    """the cube map's six faces (+x -x +y -y +z -z, Halo's axes, extract_cubemaps.py) side by side in one image"""
    from extract_chars import OUT
    faces = [Image.open(f'{OUT}/cubemaps/{key}/0_{f}.png').convert('RGB').resize((size, size), Image.BICUBIC) for f in range(6)]
    strip = Image.new('RGB', (size * 6, size))
    for f, im in enumerate(faces): strip.paste(im, (f * size, 0))
    strip.save(out)


def main():
    from extract_chars import OUT
    src = f'{OUT}/models/Marine'
    d = f'{OUT}/models/{PID}'
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(d)
    tdir, _ = extract_spv3(A50, BODY)
    J, M, _ = read_iqm(f'{tdir}/{PID}.iqm')
    meta = json.load(open(f'{tdir}/{PID}.json'))
    MJ, _, MA = read_iqm(f'{src}/{PID.replace("ODST", "")}.iqm')
    mmeta = json.load(open(f'{src}/Marine.json'))
    assert [j[0] for j in J] == [j[0] for j in MJ], 'not the Marine skeleton'
    dt = max(float(np.abs(np.subtract(a[2], b[2])).max()) for a, b in zip(J, MJ))
    print('bind pose offset from the Marine', round(dt, 5))
    for f in os.listdir(tdir):
        if f.endswith('.png'): shutil.copy(f'{tdir}/{f}', f'{d}/{f}')
    alist = [dict(name=n, fps=30.0, loop=True, frames=[[(tuple(t), tuple(q), tuple(s)) for t, q, s in fr] for fr in MA[n]])
             for n in sorted(MA)]
    meta['iqm_bytes'] = write_iqm(f'{d}/{PID}.iqm', [(n, p, tuple(t), tuple(q), tuple(s)) for n, p, t, q, s in MJ], M, alist)
    # the Marine's animations, overlays and hand frame
    for k in ('anims', 'arsenal', 'hand_frame', 'markers', 'collision_height', 'collision_radius'):
        if k in mmeta: meta[k] = mmeta[k]
    meta['mesh_weapon'] = [None] * len(M)
    for a in (mmeta.get('arsenal') or {}).values():
        shutil.copy(f'{src}/{a["model"]}', f'{d}/{a["model"]}')
    # Fire Team Raven: the same model in each one's own textures, matched by surface
    raven = {}
    for colour, biped in RAVEN.items():
        if not os.path.exists(A10): print('no', A10, ': no Fire Team Raven'); break
        rdir, _ = extract_spv3(A10, biped)
        _, RM, _ = read_iqm(f'{rdir}/{PID}.iqm')
        assert len(RM) == len(M) and all(len(a['tris']) == len(b['tris']) for a, b in zip(RM, M)), colour
        raven[colour] = {}
        for a, b in zip(M, RM):
            fn = f'{a["material"][:-4]}_raven_{colour}.png'
            shutil.copy(f'{rdir}/{b["material"]}', f'{d}/{fn}')
            mp = f'{rdir}/{b["material"][:-4]}_multi.png'
            if os.path.exists(mp): shutil.copy(mp, f'{d}/{fn[:-4]}_multi.png')
            raven[colour][a['material']] = fn
        shutil.rmtree(os.path.dirname(rdir))
    meta['raven'] = raven
    # the visor (the shader with Halo CE's 'grey' base map: its texture is a few texels of flat grey)
    sizes = [(Image.open(f'{d}/{m_["material"]}').size, m_['material']) for m_ in M]
    visor = min(sizes, key=lambda x: x[0][0] * x[0][1])
    assert visor[0][0] <= 16, 'no visor surface'
    vis = dict(mat=visor[1], base=visor_params(A50), raven={})
    def tint_png(p, fn):
        c = np.array(p['par'][1]) * p['par'][0] * 0.6 + np.array(p['perp'][1]) * p['perp'][0] * 0.4
        Image.new('RGB', (8, 8), tuple(int(x) for x in np.clip(0.18 + c * 0.82, 0, 1) * 255)).save(f'{d}/{fn}')
    tint_png(vis['base'], visor[1])
    for colour in raven:
        vis['raven'][colour] = visor_params(A10, colour)
        tint_png(vis['raven'][colour], raven[colour][visor[1]])
    for key in {vis['base']['cube']} | {p['cube'] for p in vis['raven'].values()}:
        cube_strip(key, f'{d}/MarineODST_cube_{key}.png')
    meta['visor'] = vis
    json.dump(meta, open(f'{d}/{PID}.json', 'w'), indent=1)
    shutil.rmtree(os.path.dirname(tdir))
    print(PID, len(M), 'surfaces', [m_['material'] for m_ in M], len(MA), 'animations', 'raven', sorted(raven))


if __name__ == '__main__':
    main()
