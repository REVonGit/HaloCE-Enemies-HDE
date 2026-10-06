"""The Marines' Commando: HaloDoom Evolved's own Commando (Commando_HDE.blend1, Halo Infinite's) reinterpreted as a
Halo CE gun (hde_ce.py), keeping its own colour scheme: the Infinite shader's zone colours HDE set up, evaluated."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hde_ce

BLEND = os.environ.get('HCE_COMMANDO_BLEND', os.path.join(HERE, 'Commando_HDE.blend1'))
WID = 'm_commando'
M = '3A1912CC_-871229126_mesh_%d_3A1912CC_-871229126_mesh_%d'
PARTS = {M % (11, 11): ('lower', 330),       # lower receiver, pistol grip, magwell
         M % (24, 24): ('upper', 260),       # upper receiver
         M % (17, 17): ('mag', 90),
         M % (35, 35): ('sight', 130),
         M % (47, 47): ('stock', 70),
         M % (52, 52): ('barrel', 150),
         M % (57, 57): ('fore_lo', 80),
         M % (63, 63): ('fore', 120),
         M % (68, 68): ('front', 60)}

def build():
    src = hde_ce.Source(BLEND)
    lowr = src.R[M % (11, 11)]['pos']                     # +x forward, +z up already
    g = lowr[(lowr[:, 2] > -0.06) & (lowr[:, 2] < -0.02) & (lowr[:, 0] < 0.07)]
    origin = np.array([g[:, 0].mean(), 0.0, lowr[:, 2].min() + 0.075])
    hde_ce.build(src, PARTS, hde_ce.default_paint(src, skip=('display', 'compass', 'tens', 'ones')), origin, WID,
                 'hde:Commando_HDE.blend1 (Halo CE reinterpretation)')

if __name__ == '__main__':
    build()
