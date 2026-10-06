"""The Marines' Hydra: HaloDoom Evolved's own Hydra (Hydra_HDE.blend, Halo Infinite's MLRS-1) reinterpreted as a
Halo CE gun (hde_ce.py): its own colour map with AO, the UNSC caution and stripe decals painted on."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hde_ce

BLEND = os.environ.get('HCE_HYDRA_BLEND', os.path.join(HERE, 'Hydra_HDE.blend'))
WID = 'm_hydra'
PARTS = {'Hydra': ('body', 900),                  # receiver, stock, grip, tube housing (+ the caution decal)
         'Hydra.003': ('tubes', 260),             # the six-tube missile pod
         'Hydra.001': ('cover', 90),              # pod cover
         'Hydra.002': ('trigger', 14),
         'unsc_decals_Stripes.001': ('decal', 0)}

def build():
    src = hde_ce.Source(BLEND)
    P = src.R['Hydra']['pos']                     # +x forward, +z up
    g = P[(P[:, 2] < -0.04) & (P[:, 0] > -0.08) & (P[:, 0] < 0.04)]
    origin = np.array([g[:, 0].mean(), (P[:, 1].min() + P[:, 1].max()) / 2, P[:, 2].min() + 0.075])
    hde_ce.build(src, PARTS, hde_ce.default_paint(src, skip=('ui_screen',)), origin, WID,
                 'hde:Hydra_HDE.blend (Halo CE reinterpretation)')

if __name__ == '__main__':
    build()
