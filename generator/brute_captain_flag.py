"""The Brute Captains' hologram flag from Halo 2 -> out/models/Brute/Brute_captain_flag.iqm + captain_flag.png

    python3 brute_captain_flag.py

Halo 2's captains fly a holographic pennant from the pole on their back: a cloth object
(effects\\objects\\characters\\brute\\captain_flag, 08b_deltacontrol.map) hung from the Brute's 'flag attach' marker,
a 4 x 4 grid 0.18 world units square, drawn with the 'plasma_mask_offset' shader: the captain_flag_mask and
captain_flag_offset bitmaps (the claw-marked pennant) lit in the shader's red. Halo simulates the cloth; here it is
the grid as Halo lays it out (hanging back from the pole top), bound to the Brute's spine bone so it moves with the
body, as its own model attachment on the Brute's skeleton (no animations: it plays the Brute's). The pack draws it
additively and bright on a companion actor (build_digsite.py), its shimmer and flicker in a shader."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from iqm import read_iqm, write_iqm

CLOTH = r'effects\objects\characters\brute\captain_flag'
SHADER = r'objects\characters\brute\shaders\captain_flag'
TINT = (235, 12, 16)              # a bright blood red (Halo 2's shader colour is a pale ff 9b 9d)
MARKER = 'flag attach'


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])


def qrot(q, v):
    u = np.array(q[:3]); s = q[3]
    return 2 * np.dot(u, v) * u + (s * s - np.dot(u, u)) * np.asarray(v) + 2 * s * np.cross(u, v)


def main():
    import extract_h2_brute as eb
    from h2map import H2Map
    from extract_h2_brute import OUT
    m = H2Map(eb.MAP, eb.CACHE)
    t = m.tag('clwd', CLOTH)
    a = t['addr']
    gx, gy = m.u('hh', a + 0x10)
    c, p = m.u('II', a + 0x4c)
    V = np.array([m.u('5f', p + i * 20) for i in range(c)])          # position (marker space), uv
    c, p = m.u('II', a + 0x54)
    idx = np.array(m.u(f'{c}H', p)).reshape(-1, 3)
    d = f'{OUT}/models/Brute'
    J, _, _ = read_iqm(f'{d}/Brute.iqm')
    meta = json.load(open(f'{d}/Brute.json'))
    W = []
    for n, par, tt, q, s in J:
        tt = np.array(tt); q = np.array(q)
        if par < 0: W.append((tt, q))
        else: pt, pq = W[par]; W.append((pt + qrot(pq, tt), qmul(pq, q)))
    # the marker instance at the pole's top (Halo pins the cloth's first vertex there)
    inst = max(meta['markers'][MARKER], key=lambda mk: (W[mk['node']][0] + qrot(W[mk['node']][1], np.array(mk['t'])))[2])
    wt, wq = W[inst['node']]; mt = np.array(inst['t']); mq = np.array(inst['q'])
    P = np.array([wt + qrot(wq, mt + qrot(mq, v[:3])) for v in V])
    nrm = qrot(qmul(wq, mq), np.array([0, 1.0, 0]))
    tris = np.concatenate([idx[:, [0, 2, 1]], idx])                 # two-sided
    n = len(P)
    bidx = np.zeros((n, 4), np.uint8); bidx[:, 0] = inst['node']
    bw = np.zeros((n, 4), np.uint8); bw[:, 0] = 255
    mesh = dict(name='captain_flag', material='captain_flag.png', pos=P, nrm=np.tile(nrm, (n, 1)),
                uv=np.stack([V[:, 3], 1 - V[:, 4]], 1), bidx=bidx, bw=bw, tris=tris)
    write_iqm(f'{d}/Brute_captain_flag.iqm', [(nm, par, tuple(tt), tuple(q), tuple(s)) for nm, par, tt, q, s in J], [mesh], [])
    # the hologram's look: the pennant (the mask's shape, the offset map's claw marks and border) in the shader's
    # red, on black (drawn additively, so black is clear)
    mask = np.asarray(eb.bitmap(m, eb.find_bitmap(m, 'captain_flag_mask')).convert('RGBA')).astype(np.float32) / 255
    off = np.asarray(eb.bitmap(m, eb.find_bitmap(m, 'captain_flag_offset')).convert('RGBA')).astype(np.float32) / 255
    shape = mask[..., :3].max(2)
    marks = off[..., :3].max(2)
    lum = np.clip(0.6 * shape + 1.0 * marks, 0, 1)
    edge = np.clip(1 - mask[..., 3], 0, 1)                           # the alpha is the field, dark at the border
    lum = np.clip(lum * (0.7 + 0.3 * (1 - edge)) * 1.35, 0, 1)
    rgb = np.array(TINT, np.float32) / 255 * lum[..., None]
    rgb += np.clip(marks - 0.6, 0, 1)[..., None] * np.array([0.5, 0.12, 0.1], np.float32)   # the claw marks burn hotter red
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(f'{d}/captain_flag.png')
    print('captain flag', gx, 'x', gy, 'grid,', len(tris) // 2, 'triangles, marker', inst['node'], np.round(P[0], 3))


if __name__ == '__main__':
    main()
