"""Galap's Sentinels (galap_sentinels: Halo CE custom tags) -> $HCE_OUT/models/<pid>/ and $HCE_OUT/galap_ai.json

    HCE_GALAP=/path/to/galap_sentinels python3 extract_galap_sentinels.py      # after extract_chars.py / extract_h2_sentinels.py

Galap's pack is a set of Halo CE Sentinels made as source tags (characters\\custom\\sentinel_*): the Soldier, Dragoon,
Gold, Onyx, Warden, Protector, Lancer, Interceptor, Marauder, Crawler and the Beam Gunner (and an Enforcer and a
Constructor, left out: the pack has Halo 2's). Read straight from the tags (lib/loosewalk.py, lib/looseantr.py,
lib/loosebitmap.py, lib/looset.py):

* models: each .gbxmodel's base permutations at their best level of detail, skinned to its nodes (the PC parts' local
  node tables mapped back); one surface per shader. Most are rigged to Halo CE's Sentinel skeleton (29 nodes); the
  Crawler, the Marauder and the Beam Gunner have their own.
* skins: Halo CE's 'sentinel_metal' (the Halo CE Sentinel's texture and multipurpose map, from extract_chars.py's
  Sentinel_CE) for most; the Gold's own 'sentinel_metal_gold' bitmap; the shield shaders become a 'shield.' surface
  (build_pack.py draws Halo 2's hard-light lattice on it while the shield holds); invisible shaders are dropped.
* animations: each biped's graph: Galap's 'sentinel_generic' (the Halo CE Sentinel's set), the Gold's Halo CE
  Sentinel graph (taken from Sentinel_CE), the Crawler's walking set, the Marauder's and the Beam Gunner's idles.
  Overlays (flinches, the hover motion) are baked onto the idle as extract_chars.py does.
* AI: every actor variant with its actor, biped and weapon names -> galap_ai.json (build_pack.py adds the classes).
  The ally variants (Soldier, Dragoon, Beam Gunner) fight on the player's side. The invisible Beam Gunner (a turret
  with no model in Galap's maps) wears the small Beam Gunner's.

Credit: Galap (models, textures, animations, AI tags).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import glob, json, os, shutil, sys, copy
import numpy as np
from PIL import Image
import halomodel as hm
import loosewalk as lw
from looseantr import Antr
from iqm import write_iqm, read_iqm
from hce_paths import OUT

SRC = os.environ.get('HCE_GALAP', 'galap_sentinels')
C = 'characters\\custom\\'
# pid -> (model, animation graph); 'ce' = Halo CE's Sentinel graph (from Sentinel_CE)
CHARS = {
    'SentinelSoldier': ('sentinel_soldier\\sentinel_soldier', 'sentinel_soldier\\sentinel_generic'),
    'SentinelDragoon': ('sentinel_dragoon\\sentinel_dragoon', 'sentinel_soldier\\sentinel_generic'),
    'SentinelGold': ('sentinel_gold\\sentinel_gold', 'ce'),
    'SentinelOnyx': ('sentinel_onyx\\sentinel_onyx', 'sentinel_soldier\\sentinel_generic'),
    'SentinelWarden': ('sentinel_warden\\sentinel_warden', 'sentinel_soldier\\sentinel_generic'),
    'SentinelProtector': ('sentinel_protector\\sentinel_protector', 'sentinel_soldier\\sentinel_generic'),
    'SentinelLancer': ('sentinel_lancer\\sentinel_lancer', 'sentinel_soldier\\sentinel_generic'),
    'SentinelInterceptor': ('sentinel_interceptor\\sentinel_interceptor', 'sentinel_soldier\\sentinel_generic'),
    'SentinelMarauder': ('sentinel_marauder\\sentinel_marauder', 'sentinel_marauder\\sentinel_marauder'),
    'SentinelCrawler': ('sentinel_crawler\\sentinel_crawler', 'sentinel_crawler\\sentinel_crawler'),
    'SentinelBeamGunner': ('sentinel_beam_gunner\\sentinel_beam_gunner_small\\sentinel_beam_gunner_small', 'sentinel_beam_gunner\\sentinel_beam_gunner'),
}
# the unit each biped is drawn as (the invisible Beam Gunner wears the small one's model)
UNIT_CHAR = {C + 'sentinel_beam_gunner\\sentinel_beam_gunner_invisible\\sentinel_beam_gunner': 'SentinelBeamGunner',
             C + 'sentinel_beam_gunner\\sentinel_beam_gunner_invisible\\sentinel_beam_gunner_ally': 'SentinelBeamGunner',
             C + 'sentinel_beam_gunner\\sentinel_beam_gunner_small\\sentinel_beam_gunner_small': 'SentinelBeamGunner',
             C + 'sentinel_soldier\\sentinel_soldier': 'SentinelSoldier', C + 'sentinel_soldier\\sentinel_soldier_ally': 'SentinelSoldier',
             C + 'sentinel_dragoon\\sentinel_dragoon': 'SentinelDragoon', C + 'sentinel_dragoon\\sentinel_dragoon_ally': 'SentinelDragoon',
             C + 'sentinel_gold\\sentinel_gold': 'SentinelGold', C + 'sentinel_onyx\\sentinel_onyx': 'SentinelOnyx',
             C + 'sentinel_warden\\sentinel_warden': 'SentinelWarden', C + 'sentinel_protector\\sentinel_protector': 'SentinelProtector',
             C + 'sentinel_lancer\\sentinel_lancer': 'SentinelLancer', C + 'sentinel_interceptor\\sentinel_interceptor': 'SentinelInterceptor',
             C + 'sentinel_marauder\\sentinel_marauder': 'SentinelMarauder', C + 'sentinel_crawler\\sentinel_crawler': 'SentinelCrawler'}
SKIP_VARIANTS = ('sentinel_constructor', 'sentinel_enforcer')       # the pack has Halo 2's
# the beam gunner's own graph names -> the pack's
RENAME = {'gunseat fixed idle': 'stand fixed idle%0', 'crouch fixed idle': 'crouch fixed idle%0'}

CH = {('model', 'markers'): 'model_marker', ('model_marker', 'instances'): 'model_marker_instance', ('model', 'nodes'): 'model_node',
      ('model', 'regions'): 'model_region', ('model_region', 'permutations'): 'model_region_permutation',
      ('model_region_permutation', 'markers'): 'model_perm_marker', ('model', 'geometries'): 'model_geometry',
      ('model_geometry', 'parts'): 'model_geometry_part', ('model_geometry_part', 'uncompressed_vertices'): 'model_vertex_uncompressed',
      ('model_geometry_part', 'compressed_vertices'): 'model_vertex_compressed', ('model_geometry_part', 'triangles'): 'model_triangle',
      ('model', 'shaders'): 'model_shader_reference'}


def path(tag, ext):
    return os.path.join(SRC, tag.replace('\\', '/') + '.' + ext)


def load_model(tag):
    """nodes [dict(name, parent, t, q)], parts [dict(shader name, pos, nrm, uv, bi, bw, tris)] of the base permutations"""
    import cmt_weapon as cw
    lw.fields = cw._fields_gbx
    try:
        t = lw.LooseTag(path(tag, 'gbxmodel'), 'model', CH)
    finally:
        lw.fields = cw._fields_gbx.__defaults__[0]
    r = t.root[1]
    nodes = []
    for o, _ in r['nodes']:
        nodes.append(dict(name=t.cstr(o), parent=t.get('model_node', o, 'parent_node_index'),
                          t=np.array(t.get('model_node', o, 'default_translation')),
                          q=hm.hq(np.array(t.get('model_node', o, 'default_rotation')))))
    shaders = [x[1].get('shader') or '' for x in r.get('shaders', [])]
    bms = [x or 1.0 for x in t.u('2f', 64 + 48)]
    geoms = set()
    for ro, rch in r['regions']:
        perms = rch.get('permutations', [])
        if not perms: continue
        po = next((o for o, _ in perms if t.cstr(o) == 'base'), perms[0][0])
        gi = [g for g in t.u('5h', po + 64) if g >= 0]
        if gi: geoms.add(gi[-1])                    # super high
    parts = []
    for gi in sorted(geoms):
        for po, pch in r['geometries'][gi][1]['parts']:
            sh = t.get('model_geometry_part', po, 'shader_index')
            lnc = t.d[po + 0x6B]; local = list(t.d[po + 0x6C:po + 0x6C + 22])
            vs = pch['uncompressed_vertices']
            if not vs: continue
            pos = np.array([t.u('3f', o) for o, _ in vs]); nrm = np.array([t.u('3f', o + 12) for o, _ in vs])
            uv = np.array([t.u('2f', o + 48) for o, _ in vs]) * np.array(bms)
            nd = np.array([t.u('2h', o + 56) for o, _ in vs]); w = np.array([t.u('2f', o + 60) for o, _ in vs])
            if lnc: nd = np.where(nd >= 0, np.array(local + [0] * 32)[np.clip(nd, 0, 53)], nd)
            nd = np.where(nd < 0, 0, nd)
            w = np.where(w < 0, 0, w); w[:, 0] = np.where(w.sum(1) <= 0, 1.0, w[:, 0])
            w = w / w.sum(1, keepdims=True)
            bi = np.zeros((len(vs), 4), int); bw = np.zeros((len(vs), 4))
            bi[:, :2] = nd; bw[:, :2] = w
            idx = [v for o, _ in pch['triangles'] for v in t.u('3h', o)]
            tris = cw.strip_to_tris(idx)
            tris = tris[(tris < len(vs)).all(1)] if len(tris) else tris
            if len(tris):
                a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
                if np.mean((np.cross(b - a, c - a) * nrm[tris].sum(1)).sum(1) > 0) < 0.5: tris = tris[:, [0, 2, 1]]
            parts.append(dict(shader=shaders[sh] if 0 <= sh < len(shaders) else '', pos=pos, nrm=nrm, uv=uv, bi=bi, bw=bw, tris=tris))
    return nodes, parts


def bitmap(tag):
    from loosebitmap import load
    return load(path(tag, 'bitmap'))


def skins(pid, parts, od):
    """surfaces: body (by shader), shield; returns [(surface name, material file, parts)]"""
    ce = f'{OUT}/models/Sentinel_CE'
    out = {}
    for p in parts:
        s = p['shader'].lower()
        if 'invisible' in s or not len(p['tris']): continue
        if 'shield' in s: key = ('shield.' + s.split('\\')[-1], f'{pid}_shield.png')
        elif 'gold' in s: key = ('body.sentinel_metal_gold', f'{pid}_gold.png')
        else: key = ('body.sentinel_metal', f'{pid}_metal.png')
        out.setdefault(key, []).append(p)
    for (name, mat), _ in out.items():
        dst = f'{od}/{mat}'
        if mat.endswith('_metal.png'):
            shutil.copy(f'{ce}/Sentinel_0.png', dst)
            if os.path.exists(f'{ce}/Sentinel_0_multi.png'): shutil.copy(f'{ce}/Sentinel_0_multi.png', dst[:-4] + '_multi.png')
        elif mat.endswith('_gold.png'):
            im = bitmap(C + 'sentinel_gold\\bitmaps\\sentinel_metal_gold').convert('RGB'); im.save(dst)
            a = np.asarray(im).astype(np.float32) / 255
            multi = np.dstack([np.full(a.shape[:2], 0.8), np.zeros(a.shape[:2]), np.zeros(a.shape[:2]), np.ones(a.shape[:2])])
            Image.fromarray((multi * 255).astype(np.uint8), 'RGBA').save(dst[:-4] + '_multi.png')
        else:
            Image.new('RGB', (64, 64), (110, 170, 255)).save(dst)
    return [(n, m, ps) for (n, m), ps in out.items()]


def surface(name, material, parts):
    pos, nrm, uv, bi, bw, tris, n0 = [], [], [], [], [], [], 0
    for x in parts:
        pos.append(x['pos']); nrm.append(x['nrm']); uv.append(x['uv'])
        bi.append(np.clip(x['bi'], 0, 255).astype(np.uint8)); bw.append(np.clip(np.round(x['bw'] * 255), 0, 255).astype(np.uint8))
        tris.append(x['tris'][:, [0, 2, 1]] + n0); n0 += len(x['pos'])
    bw = np.concatenate(bw); bw[:, 0] += (255 - bw.sum(1).astype(int)).astype(np.uint8)
    return dict(name=name, material=material, pos=np.concatenate(pos), nrm=np.concatenate(nrm), uv=np.concatenate(uv),
                bidx=np.concatenate(bi), bw=bw, tris=np.concatenate(tris))


def anims(graph, nodes):
    """{name: (frames, movement, loop)}: the graph's base animations, its overlays baked on the idle"""
    names = [n['name'] for n in nodes]
    if graph == 'ce':
        j, _, an = read_iqm(f'{OUT}/models/Sentinel_CE/Sentinel.iqm')
        assert [x[0] for x in j] == names, 'the Gold is not on the Halo CE Sentinel skeleton'
        info = json.load(open(f'{OUT}/models/Sentinel_CE/Sentinel.json'))['anims']
        return {k: (fr, np.zeros((len(fr), 4)), 1) for k, fr in an.items() if k in info}
    A = Antr(path(C + graph, 'model_animations'))
    assert A.nodes() == names, f'{graph}: skeleton differs'
    out, ovs = {}, {}
    for a in A.animations():
        if a['node_count'] != len(names): continue
        fr, dx = A.decode(a, len(names))
        n = RENAME.get(a['name'], a['name'])
        if a['type'] == 0: out[n] = ([[(t, q, s if s is not None else 1.0) for t, q, s in f] for f in fr], dx, 1)
        elif a['type'] == 1: ovs[n] = fr
    idle = next((k for k in sorted(out) if k.startswith('stand') and 'idle' in k), next(iter(out), None))
    for n, fr in ovs.items():
        if idle is None or not (n.startswith('s-ping') or 'overlay' in n or 'fire-' in n): continue
        base = [(np.array(t), np.array(q), s) for t, q, s in out[idle][0][0]]
        out[n + ' baked'] = (hm.bake_overlay(base, fr), np.zeros((len(fr), 4)), 1)
    return out


def write(pid, tag, nodes, meshes, A, od):
    joints = [(n['name'], n['parent'], tuple(n['t']), tuple(n['q']), (1, 1, 1)) for n in nodes]
    alist, info = [], {}
    for name, (frames, mv, loop) in sorted(A.items()):
        fr = [[(tuple(np.asarray(t, float)), tuple(np.asarray(q, float)), (s, s, s) if np.isscalar(s) else tuple(s)) for t, q, s in f] for f in frames]
        speed = float(np.hypot(mv[:, 0], mv[:, 1]).sum() / max(1, len(fr)))
        info[name] = dict(frames=len(fr), speed=speed, yaw=float(mv[:, 3].sum()), loop=bool(loop), key=-1, next=-1,
                          dx=[float(mv[:, 0].sum()), float(mv[:, 1].sum())])
        alist.append(dict(name=name, fps=30.0, loop=True, frames=fr))
    size = write_iqm(f'{od}/{pid}.iqm', joints, meshes, alist)
    allp = np.concatenate([x['pos'] for x in meshes])
    shield = [k for k, x in enumerate(meshes) if x['name'].startswith('shield.')]
    meta = dict(id=pid, tag=C + tag, maps=['galap_sentinels'], joints=[j[0] for j in joints],
                bounds=[allp.min(0).tolist(), allp.max(0).tolist()], anims=info,
                materials=sorted({x['material'][:-4] for x in meshes}), iqm_bytes=size, meshes=[x['material'] for x in meshes],
                mesh_names=[x['name'] for x in meshes], has_multi={x['material'][:-4]: os.path.exists(f'{od}/{x["material"][:-4]}_multi.png') for x in meshes},
                mesh_weapon=[None] * len(meshes), markers={}, collision_height=0.0,
                collision_radius=float(max(allp[:, 1].max() - allp[:, 1].min(), allp[:, 0].max() - allp[:, 0].min()) / 2),
                shield_surface=shield[0] if shield else None, source='galap')
    json.dump(meta, open(f'{od}/{pid}.json', 'w'), indent=1)
    return meta


def ai():
    """galap_ai.json: the actor variants (with their actors and bipeds), as extract_ai.py dumps them"""
    from looset import LooseMap
    from extract_ai import dump, flatten_obj
    m = LooseMap()
    out = dict(variants={}, actors={}, bipeds={}, unit_char=UNIT_CHAR)
    for p in sorted(glob.glob(os.path.join(SRC, 'characters/custom/**/*.actor_variant'), recursive=True)):
        name = os.path.relpath(p, SRC)[:-len('.actor_variant')].replace('/', '\\')
        if any(s in name for s in SKIP_VARIANTS): continue
        v = dump(m, 'actor_variant_definition', m.load(p, name)['data'])
        ar, ur = v['actor_reference'], v['unit_reference']
        if ur not in UNIT_CHAR: print('  no model for', name); continue
        if ar not in out['actors'] and os.path.exists(path(ar, 'actor')):
            out['actors'][ar] = dump(m, 'actor_definition', m.load(path(ar, 'actor'), ar)['data'])
        if ur not in out['bipeds']:
            out['bipeds'][ur] = flatten_obj(dump(m, 'biped_definition', m.load(path(ur, 'biped'), ur)['data']))
        out['variants'][name] = v
    json.dump(out, open(f'{OUT}/galap_ai.json', 'w'), indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    print(f'  galap_ai.json: {len(out["variants"])} variants, {len(out["actors"])} actors, {len(out["bipeds"])} bipeds')


def main():
    if not os.path.isdir(SRC): sys.exit(f'no Galap pack at {SRC} (HCE_GALAP)')
    for pid, (model, graph) in CHARS.items():
        od = f'{OUT}/models/{pid}'
        if os.path.exists(od): shutil.rmtree(od)
        os.makedirs(od)
        nodes, parts = load_model(C + model)
        meshes = [surface(n, m, ps) for n, m, ps in skins(pid, parts, od)]
        A = anims(graph, nodes)
        meta = write(pid, model, nodes, meshes, A, od)
        print(f'  {pid}: {len(nodes)} nodes, {sum(len(x["tris"]) for x in meshes)} tris, surfaces {meta["mesh_names"]}, {len(A)} anims')
    ai()


if __name__ == '__main__':
    main()
