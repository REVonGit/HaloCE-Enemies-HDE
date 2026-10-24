"""The textures the ported Halo shaders sample, and the Jackal shield's sounds -> shader_maps/ (tracked, like knight_h4/)

    python3 extract_shader_maps.py      # Halo CE's a10 and b30 (HCE_MAPS); Halo 2's 06b_floodzone (HCE_H2_MAP06B, HCE_H2_TEXTURES)

* jshield_noise.png, jshield_offset.png, jshield_mask.png: Halo CE's Jackal shield (characters\\jackal\\shaders\\jackal
  shield, a shader_transparent_generic: two scrolling noise maps, the rib pattern in the offset map's alpha, the
  shield's shape and rim colour in the mask). shaders/jshield.fp runs its seven combiner stages.
* plasma_noise.png: Halo CE's 3D plasma shield noise (characters\\elite\\bitmaps\\plasma shield noise, 32x32x32), its
  32 slices in 8 columns and 4 rows (256 x 128). shaders/plasma.fp samples it by hand (trilinear, wrapped) for the shield flares
  (characters\\elite\\shaders\\shield plasma) and the Sentinels' bubbles (Halo 2's plasma_shield, the same noise).
* enf_noise.png, enf_offset.png, enf_mask.png: Halo 2's Sentinel Enforcer shields (objects\\characters\\sentinel_enforcer
  \\shaders\\energy_shield, plasma_mask_offset: the Jackal shield's combiner over its own hexagon noise and cracks).
* jshield_sfx/Hit N.ogg, Deplete N.ogg: Halo CE's shield impact (sound\\sfx\\weapons\\shield fx\\hits, what the Jackal
  shield's impact effects play) and the Jackal's shield depletion (characters\\jackal\\effects\\shield depletion:
  sound\\sfx\\weapons\\shield fx\\deplete). split_factions.py ships them in the Covenant pack (sndinfo.jshield).
Xbox bitmaps are swizzled (bitmaps.decode does 2D; the 3D noise is unswizzled here: Morton order over x, y, z).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))
import os, sys, shutil, subprocess, tempfile
import numpy as np
from PIL import Image
from hce_paths import MAPS_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'shader_maps')
H2_MAP06B = os.environ.get('HCE_H2_MAP06B', '06b_floodzone.map')
H2_CACHE06B = os.environ.get('HCE_H2_CACHE06B') or None
H2_TEXTURES = os.environ.get('HCE_H2_TEXTURES', 'textures.dat')
CE_2D = {  # file -> Halo CE bitmap (a10)
    'jshield_noise.png': r'characters\jackal\bitmaps\shield noise',
    'jshield_offset.png': r'characters\jackal\bitmaps\shield offset',
    'jshield_mask.png': r'characters\jackal\bitmaps\shield mask',
}
CE_3D = {'plasma_noise.png': r'characters\elite\bitmaps\plasma shield noise'}
H2_2D = {  # file -> Halo 2 bitmap (06b_floodzone)
    'enf_noise.png': r'objects\characters\sentinel_enforcer\bitmaps\energy_shield_noise',
    'enf_offset.png': r'objects\characters\sentinel_enforcer\bitmaps\energy_shield_offset',
    'enf_mask.png': r'objects\characters\sentinel_enforcer\bitmaps\energy_shield_mask',
}
SOUNDS = {'Hit': r'sound\sfx\weapons\shield fx\hits', 'Deplete': r'sound\sfx\weapons\shield fx\deplete'}   # (b30)


def entry(m, t):
    """a CE bitmap tag's first bitmap_data: (w, h, depth, type, format, flags, pixels offset)"""
    c, p = m.reflexive(t['data'] + 0x60)
    sig, w, h, dep, typ, fmt, fl, rx, ry, mips, pad, poff, *_ = m.u('4s6h2h2hiiiiII', p)
    return w, h, dep, typ, fmt, fl, poff


def ce_maps():
    from halomap import HMap
    from bitmaps import decode
    m = HMap(os.path.join(MAPS_DIR, 'a10.map'))
    by = {t['name']: t for t in m.tags if t['cls'] == 'bitm'}
    for fn, name in CE_2D.items():
        w, h, dep, typ, fmt, fl, poff = entry(m, by[name])
        decode(m.d, poff, w, h, fmt, fl).save(f'{OUT}/{fn}')
    for fn, name in CE_3D.items():
        w, h, dep, typ, fmt, fl, poff = entry(m, by[name])
        assert typ == 1 and w == h == dep, (name, typ, w, h, dep)
        bpp = 2                                            # A8Y8 (Y and A carry the same noise)
        raw = np.frombuffer(m.d, np.uint8, count=w * h * dep * bpp, offset=poff).reshape(-1, bpp)
        z, y, x = np.meshgrid(np.arange(dep), np.arange(h), np.arange(w), indexing='ij')
        idx = np.zeros_like(x)
        for b in range(int(np.log2(w))):                   # Morton order: x, y, z bits interleaved
            idx |= ((x >> b) & 1) << (3 * b) | ((y >> b) & 1) << (3 * b + 1) | ((z >> b) & 1) << (3 * b + 2)
        vol = raw[idx][..., 0] if fl & 0x8 else raw.reshape(dep, h, w, bpp)[..., 0]
        # slice z at ((z % 8) * w, (z // 8) * h): 8 x 4 slices (256 x 128, under the packs' 512-pixel texture cap)
        Image.fromarray(np.concatenate([np.concatenate(list(vol[r * 8:(r + 1) * 8]), 1) for r in range(dep // 8)], 0)).save(f'{OUT}/{fn}')


def h2_maps():
    from h2map import H2Map, mcc_bitmap
    m = H2Map(H2_MAP06B, H2_CACHE06B)
    for fn, name in H2_2D.items():
        mcc_bitmap(m, name, H2_TEXTURES).save(f'{OUT}/{fn}')


def ce_sounds():
    from tags import HMap, tag
    from halosound import xbox_adpcm, to_wav
    od = f'{OUT}/jshield_sfx'
    if os.path.isdir(od): shutil.rmtree(od)
    os.makedirs(od)
    m = HMap(os.path.join(MAPS_DIR, 'b30.map'))
    by = {t['name']: t for t in m.tags if t['cls'] == 'snd!'}
    tmp = tempfile.mkdtemp()
    for ev, name in SOUNDS.items():
        S = tag(m, by[name], 'sound_definition')
        ch = 2 if S['encoding'] == 1 else 1
        rate = 44100 if S['sample_rate'] == 1 else 22050
        n = 0
        for pr in S.block('pitch_ranges', 'sound_pitch_range'):
            for pm in pr.block('permutations', 'sound_permutation'):
                sz, fl, fo = m.u('iii', pm.addr + 64)
                if pm['compression'] != 1 or sz <= 0: continue
                n += 1
                w = f'{tmp}/{ev}_{n}.wav'
                to_wav(xbox_adpcm(m.d[fo:fo + sz], ch), rate, ch, w)
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', w, '-ac', '1', '-c:a', 'libvorbis', '-q:a', '5', f'{od}/{ev} {n}.ogg'], check=True)
        print(ev, n, 'takes')
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    ce_maps()
    try: h2_maps()
    except (OSError, KeyError) as e: print('Halo 2 Enforcer maps skipped:', e)
    ce_sounds()
    print('->', OUT, sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main()
