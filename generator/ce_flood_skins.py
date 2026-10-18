"""Halo CE's own Flood combat form skins back on FloodHuman and FloodElite (undoing the XAM reskin)

    python3 ce_flood_skins.py

Re-extracts only the two bodies' images, the base and damaged materials (<Char>_0, <Char>_1), from the Halo CE maps
through extract_chars.extract() into a scratch folder, and copies them over out/models/<Char>/ (and the damaged one
over gore_<Char>.png, gore_kit.py's gib caps); the model, its animations and every later step are left as they are.
xam_flood.py, which painted them red and purple, is retired."""
import os, sys, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import extract_chars as ec
from tags import HMap
from hce_paths import MAPS_DIR
CHARS = ('FloodHuman', 'FloodElite')

if __name__ == '__main__':
    real = ec.OUT
    names = {pid: n for n, pid in ec.CHARS.items() if pid in CHARS}
    maps = {n: HMap(f'{MAPS_DIR}/{n}.map') for n in ec.MAPS}
    with tempfile.TemporaryDirectory() as tmp:
        ec.OUT = tmp
        for pid in CHARS:
            srcs = [n for n in ec.MAPS if any(t['name'] == names[pid] for t in maps[n].find('bipd'))]
            ec.extract(names[pid], pid, srcs, maps)
            for k in (0, 1):
                shutil.copy(f'{tmp}/models/{pid}/{pid}_{k}.png', f'{real}/models/{pid}/{pid}_{k}.png')
            shutil.copy(f'{tmp}/models/{pid}/{pid}_1.png', f'{real}/models/{pid}/gore_{pid}.png')
            print(pid, 'Halo CE skins restored')
