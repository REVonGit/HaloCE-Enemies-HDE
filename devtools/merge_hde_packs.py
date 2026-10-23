#!/usr/bin/env python3
"""Merge the HDE-dependent Halo CE enemy packs into HaloCE_Merged.pk3.

    python3 merge_hde_packs.py                 # every HDE pack found next to this script
    python3 merge_hde_packs.py --voices        # ... and fold HaloCE_Enemies_Voices.pk3 in too
    python3 merge_hde_packs.py A.pk3 B.pk3     # exactly these (HDE packs only)
    python3 merge_hde_packs.py -o Mine.pk3

Packs looked for: HaloCE_Core (required), HaloCE_Covenant, HaloCE_Flood, HaloCE_Sentinels, HaloCE_Marines,
HaloCE_Enemies_Digsite. Load the result like the separate packs:
    HDE (Local_DEV) -> HCE_EnemyAPI_LocalDEV.pk3 -> HaloCE_Merged.pk3 -> HaloCE_Enemies_Voices.pk3 (optional)
Needs Python 3 and merge_hce_packs.py in the same folder.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_set import run

SET = dict(
    title='HDE',
    kind='hde',
    core='HaloCE_Core.pk3',
    optional=['HaloCE_Covenant.pk3', 'HaloCE_Flood.pk3', 'HaloCE_Sentinels.pk3', 'HaloCE_Marines.pk3',
              'HaloCE_Enemies_Digsite.pk3'],
    output='HaloCE_Merged.pk3',
    load='HDE (Local_DEV) -> HCE_EnemyAPI_LocalDEV.pk3 -> {out} -> HaloCE_Enemies_Voices.pk3 (optional)',
)

if __name__ == '__main__':
    run(SET)
