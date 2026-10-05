"""Extract Halo CE third-person weapon models (weap -> mod2) for attaching to character IQMs."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import os, sys, json, pickle
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import halomodel as hm
from tags import tag, HMap
from bitmaps import bitmap_image
from extract_chars import shader_maps, MAPS, OUT
from hce_paths import MAPS_DIR

WEAPONS = {  # weapon tag -> pack id
    r'weapons\plasma pistol\plasma pistol': 'plasma_pistol',
    r'weapons\plasma rifle\plasma rifle': 'plasma_rifle',
    r'weapons\needler\needler': 'needler',
    r'weapons\fuel rod gun\fuel rod': 'fuel_rod',
    r'weapons\energy sword\energy sword': 'energy_sword',
    r'weapons\assault rifle\assault rifle': 'assault_rifle',
    r'weapons\pistol\pistol': 'pistol',
    r'weapons\shotgun\shotgun': 'shotgun',
    r'weapons\sniper rifle\sniper rifle': 'sniper_rifle',
    r'weapons\rocket launcher\rocket launcher': 'rocket_launcher',
    r'weapons\flamethrower\flamethrower': 'flamethrower',
}
# translucent shader parts we keep as solid glow colours (blade, needles)
GLOW = {'energy_sword': (120, 190, 255), 'needler': (255, 80, 200)}
TRANSPARENT = ('spla', 'sgla', 'schi', 'scex', 'swat', 'smet', 'sotr')

def extract_weapon(m, wt, wid, outdir):
    W = tag(m, wt, 'weapon_definition')
    M = hm.Model(m, W['model'])
    parts = []
    for r in M.regions:
        perm = r['perms'][0]
        best = None
        for gi in sorted(set(perm['geoms'])):
            g = M.geometry(gi)
            nt = sum(len(p['tris']) for p in g)
            if best is None or nt > best[0]: best = (nt, g)
        parts += best[1]
    os.makedirs(outdir, exist_ok=True)
    mats = {}; meshes = []
    bms = M.base_map_scale
    for p in parts:
        sh = M.shaders[p['shader']] if p['shader'] < len(M.shaders) else None
        cls = m.byid[sh['id']]['cls'] if sh and sh['id'] in m.byid else None
        glow = None
        if cls in TRANSPARENT:
            if wid in GLOW and cls in ('schi', 'scex', 'sotr', 'sgla'): glow = GLOW[wid]
            else: continue
        if glow:
            key = ('glow', glow)
            if key not in mats:
                mn = f'w_{wid}_glow'
                Image.new('RGB', (8, 8), glow).save(f'{outdir}/{mn}.png'); mats[key] = mn
            us = vs = 1
        else:
            base, multi, (us, vs) = shader_maps(m, sh)
            key = (base,)
            if key not in mats:
                mn = f'w_{wid}_{len(mats)}'
                im = bitmap_image(m, base) if base else None
                if im is None: im = Image.new('RGB', (16, 16), (90, 90, 100))
                im.convert('RGB').save(f'{outdir}/{mn}.png'); mats[key] = mn
        uv = p['uv'] * np.array([bms[0] * us, bms[1] * vs])
        meshes.append(dict(material=mats[key] + '.png', pos=p['pos'], nrm=p['nrm'], uv=uv,
                           tris=p['tris'][:, [0, 2, 1]], glow=bool(glow)))
    pickle.dump(dict(id=wid, tag=wt['name'], meshes=meshes), open(f'{outdir}/{wid}.pkl', 'wb'))
    return sum(len(x['tris']) for x in meshes), len(meshes)

if __name__ == '__main__':
    done = set()
    for n in MAPS:
        m = HMap(f'{MAPS_DIR}/{n}.map')
        for t in m.find('weap'):
            wid = WEAPONS.get(t['name'])
            if not wid or wid in done: continue
            tris, nm = extract_weapon(m, t, wid, f'{OUT}/weapons/{wid}')
            done.add(wid)
            print(wid, 'from', n, 'tris', tris, 'meshes', nm, flush=True)
    missing = set(WEAPONS.values()) - done
    if missing: print('missing', missing)
