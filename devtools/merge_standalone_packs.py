#!/usr/bin/env python3
"""Merge the standalone Halo CE enemy packs (no HaloDoom Evolved needed) into HaloCE_Standalone_Merged.pk3.

    python3 merge_standalone_packs.py              # every standalone pack found next to this script
    python3 merge_standalone_packs.py --voices     # ... and fold HaloCE_Enemies_Voices.pk3 in too
    python3 merge_standalone_packs.py A.pk3 B.pk3  # exactly these (standalone packs only)
    python3 merge_standalone_packs.py -o Mine.pk3

Packs looked for: HaloCE_Standalone_Core (required), _Covenant, _Flood, _Sentinels, _Marines, _Digsite.
Load the result on its own (any IWAD, alongside other mods), optionally followed by HaloCE_Enemies_Voices.pk3.
Needs Python 3 and merge_hce_packs.py in the same folder.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_set import run

SET = dict(
    title='standalone',
    kind='standalone',
    core='HaloCE_Standalone_Core.pk3',
    optional=['HaloCE_Standalone_Covenant.pk3', 'HaloCE_Standalone_Flood.pk3', 'HaloCE_Standalone_Sentinels.pk3',
              'HaloCE_Standalone_Marines.pk3', 'HaloCE_Standalone_Digsite.pk3'],
    output='HaloCE_Standalone_Merged.pk3',
    load='{out} -> HaloCE_Enemies_Voices.pk3 (optional), with any other mods',
)

if __name__ == '__main__':
    run(SET)
