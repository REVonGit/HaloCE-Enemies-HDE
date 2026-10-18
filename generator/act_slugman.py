"""The Slug Man's cleaner armour maps from Sgt Stacker's (Nullen's) Assorted Character Tags Pack -> out/models/SlugMan

    HCE_ACT_TAGS=/path/to/assorted_character_tags/tags python3 act_slugman.py

The pack (Nexus Mods, Halo: MCC mod 2664) carries Digsite's Slug Man ('digsite\\characters\\slug_man_c') with a new
multipurpose map, 'slugman multi.bitmap', on the same UV layout as Digsite's own: its blue channel is a clean, smoothly
shaded painting of the armour plates and its alpha a crisp mask of them. Both are written as SlugMan_0_act_multi.png
(RGBA as in the tag); build_digsite.slug_skin paints the plates from them in the rank's colour and bakes the Elites'
armour reflection on top. Without the tags the Slug Man keeps the older bake from Digsite's own maps."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
TAGS = os.environ.get('HCE_ACT_TAGS', 'tags')
SRC = 'digsite/characters/slug_man_c/bitmaps/slugman multi.bitmap'
DST = 'SlugMan_0_act_multi.png'


def main():
    src = os.path.join(TAGS, SRC)
    if not os.path.exists(src) or not os.path.exists(f'{OUT}/models/SlugMan'): print('act_slugman: no', src); return
    from loosebitmap import load
    load(src).convert('RGBA').save(f'{OUT}/models/SlugMan/{DST}')
    print('SlugMan:', DST)


if __name__ == '__main__':
    main()
