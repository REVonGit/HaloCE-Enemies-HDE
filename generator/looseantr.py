"""Read a loose Halo CE .model_animations (antr) tag file: nodes + animations with frame data.

Tag files store each struct's children after the struct array in field order (block elements, then each
element's own children; tag_data blobs; tag reference paths), all big-endian."""
import struct, re
import numpy as np
from tags import LAYOUT
from halomodel import hq, qnorm

CHILD = {
    ('animation_graph', 'object_overlays'): 'animation_graph_object_overlay',
    ('animation_graph', 'unit_seats'): 'animation_graph_unit_seat',
    ('animation_graph', 'weapon_animations'): 'animation_graph_weapon_animations',
    ('animation_graph', 'device_animations'): 'animation_graph_device_animations',
    ('animation_graph', 'unit_damage_animations'): 'animation_graph_animation_index',
    ('animation_graph', 'first_person_weapon_animations'): 'animation_graph_first_person_weapon_animations',
    ('animation_graph', 'sound_references'): 'animation_graph_sound_reference',
    ('animation_graph', 'nodes'): 'animation_graph_node',
    ('animation_graph', 'animations'): 'animation',
    ('animation_graph_unit_seat', 'animations'): 'animation_graph_animation_index',
    ('animation_graph_unit_seat', 'ik_points'): 'animation_graph_ik_point',
    ('animation_graph_unit_seat', 'weapon_classes'): 'animation_graph_weapon_class',
    ('animation_graph_weapon_class', 'animations'): 'animation_graph_animation_index',
    ('animation_graph_weapon_class', 'ik_points'): 'animation_graph_ik_point',
    ('animation_graph_weapon_class', 'weapon_types'): 'animation_graph_weapon_type',
    ('animation_graph_weapon_type', 'animations'): 'animation_graph_animation_index',
    ('animation_graph_weapon_animations', 'animations'): 'animation_graph_animation_index',
    ('animation_graph_first_person_weapon_animations', 'animations'): 'animation_graph_animation_index',
    ('animation_graph_device_animations', 'animations'): 'animation_graph_animation_index',
}

def _fields(st):
    L = LAYOUT.layout(st)
    out = []
    for fn, (o, t, n) in sorted(L['fields'].items(), key=lambda x: x[1][0]):
        out.append((fn, o, re.sub(r'^(struct|union)\s+', '', t.strip())))
    return L['size'], out

class Antr:
    def __init__(s, path):
        s.d = open(path, 'rb').read()
        assert s.d[0x24:0x28] == b'antr'
        s.blocks = {}      # (struct, field) -> list of (element offset, child dict)
        size, _ = _fields('animation_graph')
        s.root = 64
        s.cur = 64 + size
        s.children = s._children('animation_graph', s.root)
        assert s.cur == len(s.d), (s.cur, len(s.d))

    def u(s, f, o): return struct.unpack_from('>' + f, s.d, o)

    def _children(s, st, off):
        """walk the child data of one struct instance at `off`; returns {field: [(elem_off, children)] or bytes}"""
        _, fields = _fields(st)
        res = {}
        for fn, o, t in fields:
            if t == 'tag_reference':
                ln, = s.u('i', off + o + 8)
                if ln > 0:
                    res[fn] = s.d[s.cur:s.cur + ln].decode('latin1'); s.cur += ln + 1
            elif t == 'tag_data':
                sz, = s.u('i', off + o)
                res[fn] = (s.cur, sz); s.cur += sz
            elif t == 'tag_block':
                cnt, = s.u('i', off + o)
                if cnt <= 0: res[fn] = []; continue
                et = CHILD.get((st, fn))
                if et is None: raise ValueError(f'unknown block element {st}.{fn} ({cnt})')
                esz, _ = _fields(et)
                base = s.cur; s.cur += cnt * esz
                res[fn] = [(base + i * esz, s._children(et, base + i * esz)) for i in range(cnt)]
        return res

    def nodes(s):
        out = []
        for off, ch in s.children['nodes']:
            name = s.d[off:off + 32].split(b'\0')[0].decode('latin1')
            out.append(name)
        return out

    def animations(s):
        """list of dict(name, type, frames, flags, nodes, data offsets...)"""
        L = LAYOUT.layout('animation')['fields']
        def fo(name): return L[name][0]
        res = []
        for off, ch in s.children['animations']:
            a = dict(name=s.d[off:off + 32].split(b'\0')[0].decode('latin1'))
            for k in ('type', 'frame_count', 'frame_size', 'frame_info_type', 'node_count', 'flags',
                      'offset_to_compressed_data', 'compressed_data_offset'):
                if k in L:
                    t = L[k][1]; f = {'short': 'h', 'long': 'i', 'word': 'H', 'unsigned long': 'I', 'long_flags': 'I',
                                      'word_flags': 'H', 'short_enum': 'h'}.get(t.strip(), 'h')
                    a[k] = s.u(f, off + fo(k))[0]
            for k in ('nodes_with_translation_flags', 'nodes_with_rotation_flags', 'nodes_with_scale_flags'):
                a[k] = s.u('I', off + fo(k))[0] | (s.u('I', off + fo(k) + 4)[0] << 32)
            a['frame_info'] = ch.get('frame_info'); a['default_data'] = ch.get('default_data'); a['data'] = ch.get('data')
            res.append(a)
        return res

    def decode(s, a, node_count):
        """uncompressed tag frame data -> frames[F][N] = (t, q, s); dx[F,4]"""
        F = a['frame_count']; overlay = a['type'] != 0
        tf, rf, sf = a['nodes_with_translation_flags'], a['nodes_with_rotation_flags'], a['nodes_with_scale_flags']
        do, dsz = a['default_data']; po0, psz = a['data']
        fsize = a['frame_size']
        frames = []
        for f in range(F):
            po = po0 + f * fsize; dd = do
            cur = []
            for n in range(node_count):
                q = t = sc = None
                if rf >> n & 1: q = np.array(s.u('4h', po), float) / 32767.0; po += 8
                elif not overlay: q = np.array(s.u('4h', dd), float) / 32767.0; dd += 8
                if tf >> n & 1: t = np.array(s.u('3f', po)); po += 12
                elif not overlay: t = np.array(s.u('3f', dd)); dd += 12
                if sf >> n & 1: sc = s.u('f', po)[0]; po += 4
                elif not overlay: sc = s.u('f', dd)[0]; dd += 4
                cur.append((t, hq(q) if q is not None else None, sc))
            frames.append(cur)
        dx = np.zeros((F, 4))
        fo_, fsz = a['frame_info']
        per = {1: 8, 2: 12, 3: 16}.get(a['frame_info_type'])
        if per and fsz:
            for f in range(min(F, fsz // per)):
                v = s.u('%df' % (per // 4), fo_ + f * per)
                if a['frame_info_type'] == 1: dx[f] = (v[0], v[1], 0, 0)
                elif a['frame_info_type'] == 2: dx[f] = (v[0], v[1], 0, v[2])
                else: dx[f] = v
        return frames, dx
