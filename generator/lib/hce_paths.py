"""Paths for the Halo CE enemy tools. Override with environment variables."""
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the generator folder (this file is in lib/)
HALO_SRC = os.environ.get('HCE_HALO_SRC', os.path.join(HERE, 'halo-ce-universal', 'source'))  # decomp headers
MAPS_DIR = os.environ.get('HCE_MAPS', os.path.join(HERE, 'maps'))      # a10.map ... d40.map (Xbox)
OUT = os.environ.get('HCE_OUT', os.path.join(HERE, 'out'))             # intermediate IQM/PNG/JSON
PACK = os.environ.get('HCE_PACK', os.path.join(HERE, 'pack'))          # pk3 source tree
# Digsite add-on (private: Digsite content is licensed for MCC projects only)
DIGSITE = os.environ.get('HCE_DIGSITE', os.path.join(HERE, 'h1'))                      # clone of github.com/digsite/h1
SKETCHFAB = os.environ.get('HCE_SKETCHFAB', os.path.join(HERE, 'extra'))               # folder holding elite.model_animations (CE-rig rifle set)
DIG_PACK = os.environ.get('HCE_DIG_PACK', os.path.join(HERE, 'addons', 'digsite'))     # add-on pk3 source tree
CMT_CARBINE = os.environ.get('HCE_CMT_CARBINE', os.path.join(HERE, 'cmt_carbine'))     # carbine.gbxmodel + bitmaps/ (CMT tags)
