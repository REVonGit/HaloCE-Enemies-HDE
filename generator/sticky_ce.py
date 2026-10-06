"""The Marines' sticky detonator: the Sidekick (the Macworld 2000 pistol, marine_arsenal.fix_sidekick) repainted green,
with HaloDoom Evolved's sticky bomb (Stickybomb.blend, HCE_STICKYBOMB_BLEND: Halo Infinite's charge) reinterpreted
as a Halo CE model (hde_ce.py) seated in its muzzle. Two guns: m_sticky_detonator (loaded: the bomb in the muzzle)
and m_sticky_detonator_fired (the bomb gone); build_pack.py swaps between them as the Marine fires and reloads."""
import os, sys, pickle, shutil
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import hde_ce

BLEND = os.environ.get('HCE_STICKYBOMB_BLEND', os.path.join(HERE, 'Stickybomb.blend'))
BOMB_SCALE = 0.8                 # the charge a little smaller, so it sits in the pistol's muzzle
GREEN = np.array([0.36, 0.58, 0.24])

def green(im):
    """the Sidekick's bare metal (the greys) painted green, its shading kept; the black grip and dark parts stay"""
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
    lum = a.mean(2, keepdims=True)
    sat = (a.max(2, keepdims=True) - a.min(2, keepdims=True)) / np.maximum(a.max(2, keepdims=True), 1e-3)
    w = np.clip((0.25 - sat) / 0.1, 0, 1) * np.clip((lum - 0.18) / 0.12, 0, 1)
    out = a * (1 - w) + np.clip(lum * GREEN * 1.25, 0, 1) * w
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))

def build():
    from marine_arsenal import OUT, save_pkl
    # the charge, CE-style
    src = hde_ce.Source(BLEND)
    P = src.R['default:default.001']['pos']
    origin = np.array([P[:, 0].min(), (P[:, 1].min() + P[:, 1].max()) / 2, (P[:, 2].min() + P[:, 2].max()) / 2])   # its rear, centred
    hde_ce.build(src, {'default:default.001': ('bomb', 320)}, hde_ce.default_paint(src, skip=('hud',)), origin, 'm_sticky_bomb',
                 'hde:Stickybomb.blend (Halo CE reinterpretation)')
    bomb = pickle.load(open(f'{OUT}/weapons/m_sticky_bomb/m_sticky_bomb.pkl', 'rb'))['meshes']
    # the green Sidekick
    sk = pickle.load(open(f'{OUT}/weapons/m_sidekick/m_sidekick.pkl', 'rb'))['meshes']
    Ps = np.concatenate([m['pos'] for m in sk])
    front = Ps[Ps[:, 0] > Ps[:, 0].max() - 0.008]
    muzzle = np.array([Ps[:, 0].max() - 0.004, 0.0, (front[:, 2].min() + front[:, 2].max()) / 2])
    for wid, loaded in (('m_sticky_detonator', True), ('m_sticky_detonator_fired', False)):
        d = f'{OUT}/weapons/{wid}'
        if os.path.isdir(d): shutil.rmtree(d)
        os.makedirs(d)
        meshes = []
        for k, m in enumerate(sk):
            mat = f'w_m_sticky_detonator_{k}.png'
            if not os.path.exists(f'{d}/{mat}'): green(Image.open(f'{OUT}/weapons/m_sidekick/{m["material"]}')).save(f'{d}/{mat}')
            meshes.append(dict(m, material=mat))
        if loaded:
            for m in bomb:
                shutil.copy(f'{OUT}/weapons/m_sticky_bomb/{m["material"]}', f'{d}/{m["material"]}')
                meshes.append(dict(m, pos=m['pos'] * BOMB_SCALE + muzzle))
        save_pkl(wid, meshes, 'hde:sticky detonator (green Sidekick + Stickybomb.blend)')
        P = np.concatenate([m['pos'] for m in meshes]); print(wid, len(meshes), 'meshes', P.min(0).round(3), P.max(0).round(3))

if __name__ == '__main__':
    build()
