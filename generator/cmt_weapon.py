"""Loose CE .gbxmodel weapon (e.g. CMT's Covenant carbine) -> weapon pkl (+x forward, +z up, origin at the grip)."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import struct, pickle, os, sys
import numpy as np
import loosewalk as lw

CH = {('model', 'markers'): 'model_marker', ('model_marker', 'instances'): 'model_marker_instance', ('model', 'nodes'): 'model_node',
      ('model', 'regions'): 'model_region', ('model_region', 'permutations'): 'model_region_permutation',
      ('model_region_permutation', 'markers'): 'model_perm_marker', ('model', 'geometries'): 'model_geometry',
      ('model_geometry', 'parts'): 'model_geometry_part', ('model_geometry_part', 'uncompressed_vertices'): 'model_vertex_uncompressed',
      ('model_geometry_part', 'compressed_vertices'): 'model_vertex_compressed', ('model_geometry_part', 'triangles'): 'model_triangle',
      ('model', 'shaders'): 'model_shader_reference'}

def _fields_gbx(st, _orig=lw.fields):
    if st == 'model_perm_marker': return 80, []
    sz, fl = _orig(st)
    if st == 'model_geometry_part': sz = 132          # gbxmodel (PC) parts carry the local-node table
    return sz, fl

def load(path):
    lw.fields = _fields_gbx
    try:
        t = lw.LooseTag(path, 'model', CH)
    finally:
        lw.fields = _fields_gbx.__defaults__[0]
    assert t.complete
    return t

def strip_to_tris(idx):
    tris = []
    for i in range(len(idx) - 2):
        a, b, c = idx[i], idx[i + 1], idx[i + 2]
        if a < 0 or b < 0 or c < 0 or a == b or b == c or a == c: continue
        tris.append((a, b, c) if i % 2 == 0 else (a, c, b))
    return np.array(tris, int)

def geometry(t, lod=0, shaders=None):
    """parts of geometry `lod` as dict(shader, pos, nrm, uv, tris)"""
    r = t.root[1]
    bms = [x or 1.0 for x in t.u('2f', 64 + 48)]     # 0 means unscaled
    geo_off, geo = r['geometries'][lod]
    out = []
    for po, pch in geo['parts']:
        sh = t.get('model_geometry_part', po, 'shader_index')
        if shaders is not None and sh not in shaders: continue
        vs = pch['uncompressed_vertices']
        pos = np.array([t.u('3f', o) for o, _ in vs]); nrm = np.array([t.u('3f', o + 12) for o, _ in vs])
        uv = np.array([t.u('2f', o + 48) for o, _ in vs]) * np.array(bms)
        idx = [v for o, _ in pch['triangles'] for v in t.u('3h', o)]
        tris = strip_to_tris(idx)
        # the strips are wound for Halo's renderer; flip to face along the vertex normals
        if len(tris):
            a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
            agree = np.mean((np.cross(b - a, c - a) * nrm[tris].sum(1)).sum(1) > 0)
            if agree < 0.5: tris = tris[:, [0, 2, 1]]
        out.append(dict(shader=sh, pos=pos, nrm=nrm, uv=uv, tris=tris))
    return out

def build_carbine(gbx, bitmaps_dir, out_dir, wid='cmt_carbine'):
    """CMT Covenant carbine: gray + purple body (the purple shader's tint is baked; GZDoom has no cube-map
    reflections), green status lights and ammo read-out kept as alpha-masked glowing surfaces."""
    from PIL import Image
    from loosebitmap import load as bm
    t = load(gbx)
    os.makedirs(out_dir, exist_ok=True)
    diff = bm(f'{bitmaps_dir}/carbine_body_diff.bitmap').convert('RGB')
    multi = bm(f'{bitmaps_dir}/carbine_body_multi.bitmap').convert('RGBA')
    d = np.asarray(diff).astype(np.float32) / 255
    m = np.asarray(multi.resize(diff.size)).astype(np.float32)[..., 2:3] / 255     # blue: change-colour mask
    tex = {}
    tex['gray.png'] = diff
    # purple shader: Covenant carapace sheen (parallel tint 0.64/0.54/0.89) where the colour-change mask is
    purple = np.array([0.62, 0.46, 0.95], np.float32)
    p = d * (1 - m) + np.clip(d * purple * 1.35 + 0.04 * purple, 0, 1) * m
    tex['purple.png'] = Image.fromarray((p * 255).astype(np.uint8))
    def glow(img, gain=1.0):
        a = np.asarray(img.convert('RGB')).astype(np.float32)
        alpha = np.clip(a.max(2) * 2.0 * gain, 0, 255)
        return Image.fromarray(np.dstack([a, alpha]).astype(np.uint8), 'RGBA')
    tex['lights.png'] = glow(bm(f'{bitmaps_dir}/carbine_body_illum_color.bitmap'))
    tex['icon.png'] = glow(bm(f'{bitmaps_dir}/carbine_icon.bitmap'))
    tex['meter.png'] = glow(bm(f'{bitmaps_dir}/carbine_ammo_meter.bitmap'))
    # blue Pulse Carbine variant: same mesh, re-tinted carapace and blue-shifted status lights (swapped per class)
    blue = np.array([0.32, 0.58, 1.0], np.float32)
    pb = d * (1 - m) + np.clip(d * blue * 1.35 + 0.04 * blue, 0, 1) * m
    tex['blue_purple.png'] = Image.fromarray((pb * 255).astype(np.uint8))
    def to_blue(img):
        a = np.asarray(img).astype(np.float32)
        lum = a[..., :3].max(2, keepdims=True) / 255.0
        rgb = np.clip(lum * np.array([0.35, 0.65, 1.0]) * 255 + lum ** 3 * 60, 0, 255)
        return Image.fromarray(np.dstack([rgb, a[..., 3:4]]).astype(np.uint8), 'RGBA')
    for k in ('lights.png', 'icon.png', 'meter.png'): tex['blue_' + k] = to_blue(tex[k])
    mats = {0: 'gray.png', 5: 'purple.png', 1: 'lights.png', 2: 'icon.png', 4: 'meter.png'}
    meshes = []
    for part in geometry(t, 0, set(mats)):
        meshes.append(dict(material=f'w_{wid}_{mats[part["shader"]]}', pos=part['pos'], nrm=part['nrm'], uv=part['uv'], tris=part['tris']))
    # one surface per material
    merged = {}
    for mm in meshes:
        merged.setdefault(mm['material'], []).append(mm)
    out = []
    for mat, ms in merged.items():
        base = 0; tris = []
        for x in ms: tris.append(x['tris'] + base); base += len(x['pos'])
        out.append(dict(material=mat, pos=np.concatenate([x['pos'] for x in ms]), nrm=np.concatenate([x['nrm'] for x in ms]),
                        uv=np.concatenate([x['uv'] for x in ms]), tris=np.concatenate(tris)))
    for k, im in tex.items(): im.save(f'{out_dir}/w_{wid}_{k}')
    pickle.dump(dict(id=wid, tag='cmt\\weapons\\_shared\\carbine\\carbine', meshes=out), open(f'{out_dir}/{wid}.pkl', 'wb'))
    P = np.concatenate([x['pos'] for x in out])
    print(wid, 'tris', sum(len(x['tris']) for x in out), 'bounds', P.min(0).round(3), P.max(0).round(3), [x['material'] for x in out])

def build_spiker(gbx, bitmaps_dir, out_dir, wid='spiker'):
    """Halo 3's Spiker (community CE port): blade/dull/shiny body parts share the body diffuse, the clip has its
    own, and the heated blade insert becomes a glowing orange surface (brightmapped by the pack builder)."""
    from PIL import Image
    from loosebitmap import load as bm
    t = load(gbx)
    os.makedirs(out_dir, exist_ok=True)
    body = bm(f'{bitmaps_dir}/spiker_body_diff.bitmap').convert('RGB')
    clip = bm(f'{bitmaps_dir}/spiker_clip_diff.bitmap').convert('RGB')
    heat = np.asarray(bm(f'{bitmaps_dir}/spiker_body_heat_glow.bitmap').convert('RGB')).astype(np.float32)
    lum = heat.max(2, keepdims=True) / 255
    glow = np.clip(np.array([255, 140, 40]) * (0.35 + lum) + lum ** 2 * 80, 0, 255)
    tex = {'body.png': body, 'clip.png': clip, 'heat.png': Image.fromarray(glow.astype(np.uint8))}
    mats = {0: 'body.png', 1: 'body.png', 3: 'body.png', 4: 'clip.png', 2: 'heat.png'}
    merged = {}
    for part in geometry(t, 0, set(mats)):
        merged.setdefault(f'w_{wid}_{mats[part["shader"]]}', []).append(part)
    out = []
    for mat, ms in merged.items():
        base = 0; tris = []
        for x in ms: tris.append(x['tris'] + base); base += len(x['pos'])
        out.append(dict(material=mat, pos=np.concatenate([x['pos'] for x in ms]), nrm=np.concatenate([x['nrm'] for x in ms]),
                        uv=np.concatenate([x['uv'] for x in ms]), tris=np.concatenate(tris)))
    for k, im in tex.items(): im.save(f'{out_dir}/w_{wid}_{k}')
    pickle.dump(dict(id=wid, tag='h3\\weapons\\spiker\\spiker', meshes=out), open(f'{out_dir}/{wid}.pkl', 'wb'))
    print(wid, 'tris', sum(len(x['tris']) for x in out), [x['material'] for x in out])

if __name__ == '__main__':
    from hce_paths import OUT, CMT_CARBINE
    if len(sys.argv) > 1 and sys.argv[1] == 'spiker':
        src = sys.argv[2] if len(sys.argv) > 2 else 'Spiker'
        build_spiker(f'{src}/spiker.gbxmodel', f'{src}/bitmaps', sys.argv[3] if len(sys.argv) > 3 else OUT + '/weapons/spiker')
        sys.exit()
    src = sys.argv[1] if len(sys.argv) > 1 else CMT_CARBINE
    out = sys.argv[2] if len(sys.argv) > 2 else OUT + '/weapons/cmt_carbine'
    gbx = next(os.path.join(src, f) for f in os.listdir(src) if f.endswith('.gbxmodel') and 'fp' not in f)
    build_carbine(gbx, os.path.join(src, 'bitmaps'), out)
