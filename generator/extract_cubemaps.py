"""Halo CE's reflection cube maps for the Elites and Grunts -> out/cubemaps/<name>/<index>_<face>.png

Their armour shaders (shader_model) reflect a cube map under the multipurpose map's specular mask: the Elites'
'cubemaps' bitmap holds four (blue, magenta, gold, silver: one per rank), the Grunts use 'cubemap dark gray'.
build_pack.py bakes that reflection into the skins (add_shine). Xbox cube maps: six DXT faces in a row, each with its
mip chain, padded to 128 bytes; face order +x -x +y -y +z -z."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
from halomap import HMap
import bitmaps as bm
from hce_paths import OUT, MAPS_DIR
MAP = os.environ.get('HCE_CUBE_MAP', os.path.join(MAPS_DIR, 'a50.map'))
CUBES = {'elite': r'characters\elite\bitmaps\cubemaps', 'dark_gray': r'characters\elite\bitmaps\cubemap dark gray'}

def main():
    m = HMap(MAP)
    for key, name in CUBES.items():
        t = [x for x in m.find('bitm') if x['name'] == name][0]
        c, p = m.reflexive(t['data'] + 0x60)
        d = f'{OUT}/cubemaps/{key}'; os.makedirs(d, exist_ok=True)
        for i in range(c):
            sig, w, h, dep, typ, fmt, fl, rx, ry, mips, pad, poff, psz, tid, cb, hw, ba = m.u('4s6h2h2hiiiiII', p + i * 0x30)
            assert typ == 2, f'{name} #{i}: not a cube map'
            for f in range(6):
                bm.decode(m.d, poff + f * (psz // 6), w, h, fmt, fl & ~0x8).convert('RGB').save(f'{d}/{i}_{f}.png')
        print(key, c, 'cube maps')

if __name__ == '__main__':
    main()
