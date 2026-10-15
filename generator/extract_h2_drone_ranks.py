"""Halo 2 Drone ranks (Ruby of Blue's 'H2 Drone Rank Tags') -> the Digsite Drone's rank colours and health.

    HCE_H2_DRONE_RANKS=/path/to/H2_Drone_Rank_Tags.zip python3 extract_h2_drone_ranks.py

Run after extract_h2.py. The mod gives Halo 2's Drone (bugger_cc) a change-colour map and rank variants. From its
H2EK tags (read straight out of the zip):

    bugger_cc.biped           the change-colour permutations, one per variant name (minor, major, ultra, captain,
                              captain_major and three Reach-style ones): the lower and upper colour of each
    bugger_cc.bitmap          the change-colour map: its exoskeleton plates in red (from the bitmap's import source,
                              the artist's 512 px BGRA original the tag keeps); the same UV layout as Halo 2's bugger
                              texture the Drone already wears (Drone_0.png)
    ai/bugger_<rank>.character the rank's body and shield vitality (normal and legendary)

Writes out/models/Drone/Drone_rank_mask.png (the plates, 0..255) and Drone.json 'ranks': {rank: {colour, body, shield}}
with the legendary vitality (the pack's Drone already has Halo 2's legendary Minor's 30 body). build_digsite.py makes
a class per rank and loadout and paints each rank's plates (drone_skin).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import json, os, struct, sys, zipfile
import numpy as np
from PIL import Image
from h2jms import tag_sources
from extract_chars import OUT

SRC = os.environ.get('HCE_H2_DRONE_RANKS', 'H2_Drone_Rank_Tags.zip')   # Ruby of Blue's mod, as downloaded
DRONE = f'{OUT}/models/Drone'
RANKS = ('minor', 'major', 'ultra', 'captain', 'captain_major')     # the Halo 2 ranks (the Reach palettes are left out)


def blocks(d):
    """[(offset of the element data, count, element size)] of every tag block in an H2EK tag file"""
    out, i = [], 0
    while True:
        i = d.find(b'dfbt', i)
        if i < 0: return out
        _, c, s = struct.unpack_from('<iii', d, i + 4)
        out.append((i + 16, c, s)); i += 4


def change_colours(d):
    """{variant name: (lower rgb, upper rgb)} from a biped's change-colour initial permutations (32-byte elements:
    weight, lower rgb, upper rgb, variant string id; the names follow the block, the id's top byte their length)"""
    for o, c, s in blocks(d):
        if s != 32 or c < 2: continue
        rows = [struct.unpack_from('<7fI', d, o + k * 32) for k in range(c)]
        p = o + c * s; names = []
        for r in rows:
            n = r[7] >> 24
            names.append(d[p:p + n].decode('latin1')); p += n
        if all(n.replace('_', '').isalpha() for n in names):
            return {n: (r[1:4], r[4:7]) for n, r in zip(names, rows)}
    return {}


def vitality(d):
    """(normal body, normal shield, legendary body, legendary shield) from a character tag's vitality block"""
    for o, c, s in blocks(d):
        if s == 112 and c == 1:
            return struct.unpack_from('<5f', d, o)[1:5]
    return None


def main():
    """reads the mod's biped (change colours), bitmap (the plates mask, resized to Drone_0.png) and character tags
    (vitality) straight from the zip and writes Drone_rank_mask.png and the 'ranks' block of Drone.json"""
    if not os.path.exists(SRC): print('extract_h2_drone_ranks: no', SRC); return
    if not os.path.exists(f'{DRONE}/Drone.json'): print('extract_h2_drone_ranks: run extract_h2.py first'); return
    z = zipfile.ZipFile(SRC)
    by = {n.lower().split('/')[-1]: n for n in z.namelist()}
    cols = change_colours(z.read(by['bugger_cc.biped']))
    # the change-colour map: red where the plates take the rank colour (its other channels hold the plain skin)
    tmp = f'{DRONE}/_cc.bitmap'
    open(tmp, 'wb').write(z.read(by['bugger_cc.bitmap']))
    src = tag_sources(tmp)[0]; os.remove(tmp)
    n = int(round((len(src) // 4) ** 0.5))
    a = np.frombuffer(src, np.uint8)[:n * n * 4].reshape(n, n, 4)[:, :, [2, 1, 0]].astype(np.float64) / 255.0
    red = np.clip((a[..., 0] - np.maximum(a[..., 1], a[..., 2])) / 0.35, 0, 1)
    size = Image.open(f'{DRONE}/Drone_0.png').size
    Image.fromarray((red * 255).astype(np.uint8)).resize(size, Image.LANCZOS).save(f'{DRONE}/Drone_rank_mask.png')
    meta = json.load(open(f'{DRONE}/Drone.json'))
    ranks = {}
    for r in RANKS:
        v = vitality(z.read(by[f'bugger_{r}.character']))
        lo, hi = cols[r]
        ranks[r] = dict(colour=[round((x + y) / 2, 3) for x, y in zip(lo, hi)], body=v[2], shield=v[3])
        print(f'  {r:14s} colour {ranks[r]["colour"]}  body {v[2]:.0f}  shield {v[3]:.0f}')
    meta['ranks'] = ranks
    json.dump(meta, open(f'{DRONE}/Drone.json', 'w'))
    print(f'-> {DRONE}/Drone_rank_mask.png ({red.mean() * 100:.0f}% of the texture), Drone.json ranks')


if __name__ == '__main__':
    main()
