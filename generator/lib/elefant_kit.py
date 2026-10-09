"""Elefant's Marine kit: the extra Marine accessories and permutations in marine.blend, read without Blender.

    pieces = load(BLEND, nodes)     # {object name: dict(pos, nrm, uv, bi/bw (N,4) into nodes, tris, tmat, mats)}

marine.blend (Blender 4.0 format) holds Halo CE's Marine rebuilt and expanded by Elefant: more faces, helmets and
head add-ons, sleeves, pads, pouches and packs, rigged to the Halo CE Marine skeleton ('bip01 ...' vertex groups). Its
meshes keep their attributes in the pre-4.3 CustomData layers, which this reads; the rest (object transforms, parents,
mirror modifiers, weights, normals) is brute_kit.Kit's. Coordinates are JMS units: / 100 is the render model's.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brute_kit as bk

BLEND = os.environ.get('HCE_MARINE_KIT', 'marine.blend')
# CustomData layer types (Blender 4.0): 48 float3, 49 float2, 11 int32 attribute
_SPEC = {48: ('<f4', 3), 49: ('<f4', 2), 11: ('<i4', 1)}


class Kit(bk.Kit):
    def __init__(s, path=BLEND):
        super().__init__(path)

    def attrs(s, me):
        B = s.B; out = {}
        sz = B.fields('CustomDataLayer')['__size__']
        counts = {'vdata': 'totvert', 'ldata': 'totloop', 'pdata': 'totpoly'}
        for cd, dom in (('vdata', 0), ('ldata', 3), ('pdata', 2)):
            c = B.get('Mesh', me.off, cd); lb = B.block(B.get('CustomData', c, 'layers'))
            if not lb: continue
            n = B.get('Mesh', me.off, counts[cd])
            for k in range(B.get('CustomData', c, 'totlayer')):
                p = lb.off + k * sz
                t = B.get('CustomDataLayer', p, 'type'); name = B.get('CustomDataLayer', p, 'name')
                if t not in _SPEC: continue
                dt, w = _SPEC[t]
                a = B.array(B.get('CustomDataLayer', p, 'data'), dt)
                if a is None: continue
                a = a[:n * w]
                out[name] = (a.reshape(n, w) if w > 1 else a, dom)
        return out


def marine_nodes(joints):
    """the Marine's joint names in brute_kit.bone_name's spelling ('bip01 l thigh' -> 'l_thigh')"""
    return [j[0][6:].replace(' ', '_') if j[0].startswith('bip01 ') else j[0] for j in joints]


def load(names, nodes, path=BLEND):
    k = Kit(path)
    return {n: k.piece(n, nodes) for n in names}
