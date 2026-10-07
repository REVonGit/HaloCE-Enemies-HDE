"""Halo CE's reflections for the Covenant weapons -> out/weapons/<id>/<material>_multi.png, out/cubemaps/w_<id>/,
out/weapons/<id>/shine.json

    python3 extract_weapon_shine.py

Each Covenant weapon's third-person shader (shader_model) reflects its own cube map ('cubemap plasma rifle' ...) under
the multipurpose map's specular mask, perpendicular and parallel brightness in the shader. extract_weapons.py keeps
only the base maps; this adds the rest for build_pack.py, which bakes the reflection into the colourful parts of the
weapon textures (weapon_shine). Material names follow extract_weapons.py's numbering (w_<id>_<n>)."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import halomodel as hm
from tags import tag, HMap
from bitmaps import bitmap_image
import bitmaps as bm
from extract_weapons import WEAPONS, TRANSPARENT, GLOW
from extract_chars import shader_maps, MAPS, OUT
from hce_paths import MAPS_DIR

COVENANT = ('plasma_pistol', 'plasma_rifle', 'needler', 'fuel_rod', 'energy_sword')
REF_CUBE = 0x164                     # shader_model: reflection cube map (tag reference; its id at +12)
REF_BRIGHT = 0x144                   # perpendicular brightness, tint (rgb), parallel brightness, tint (rgb)


def save_cube(m, bid, d):
    """a cube map bitmap -> d/0_<face>.png (+x -x +y -y +z -z); False if it isn't one"""
    t = m.byid[bid]
    c, p = m.reflexive(t['data'] + 0x60)
    if not c: return False
    sig, w, h, dep, typ, fmt, fl, rx, ry, mips, pad, poff, psz, tid, cb, hw, ba = m.u('4s6h2h2hiiiiII', p)
    if typ != 2: return False
    os.makedirs(d, exist_ok=True)
    for f in range(6):
        bm.decode(m.d, poff + f * (psz // 6), w, h, fmt, fl & ~0x8).convert('RGB').save(f'{d}/0_{f}.png')
    return True


def weapon_shine(m, wt, wid):
    W = tag(m, wt, 'weapon_definition')
    M = hm.Model(m, W['model'])
    parts = []
    for r in M.regions:                        # the same parts, in the same order, as extract_weapons.py
        perm = r['perms'][0]
        best = None
        for gi in sorted(set(perm['geoms'])):
            g = M.geometry(gi)
            nt = sum(len(p['tris']) for p in g)
            if best is None or nt > best[0]: best = (nt, g)
        parts += best[1]
    od = f'{OUT}/weapons/{wid}'
    mats, out = {}, {}
    for p in parts:
        sh = M.shaders[p['shader']] if p['shader'] < len(M.shaders) else None
        cls = m.byid[sh['id']]['cls'] if sh and sh['id'] in m.byid else None
        if cls in TRANSPARENT:                 # glows: extract_weapons.py numbers them along with the base maps
            if wid in GLOW and cls in ('schi', 'scex', 'sotr', 'sgla'): mats.setdefault(('glow', GLOW[wid]), None)
            continue
        base, multi, _ = shader_maps(m, sh)
        if (base,) in mats: continue
        mn = f'w_{wid}_{len(mats)}'; mats[(base,)] = mn
        if cls != 'soso' or not multi: continue
        t = m.byid[sh['id']]
        cube = m.u('I', t['data'] + REF_CUBE + 12)[0]
        if cube not in m.byid or not save_cube(m, cube, f'{OUT}/cubemaps/w_{wid}'): continue
        bitmap_image(m, multi).save(f'{od}/{mn}_multi.png')
        pb, pr, pg, pbl, qb, qr, qg, qbl = m.u('8f', t['data'] + REF_BRIGHT)
        out[mn + '.png'] = dict(cube=f'w_{wid}', multi=f'{mn}_multi.png', perpendicular=pb, parallel=qb,
                                tint=[(pr + qr) / 2, (pg + qg) / 2, (pbl + qbl) / 2])
    json.dump(out, open(f'{od}/shine.json', 'w'), indent=1)
    return out


if __name__ == '__main__':
    done = set()
    for n in MAPS:
        m = HMap(f'{MAPS_DIR}/{n}.map')
        for t in m.find('weap'):
            wid = WEAPONS.get(t['name'])
            if wid not in COVENANT or wid in done: continue
            r = weapon_shine(m, t, wid)
            done.add(wid)
            print(wid, {k: (v['cube'], round(v['perpendicular'], 2), round(v['parallel'], 2)) for k, v in r.items()}, flush=True)
