"""Halo 2's jump pack sounds -> $HCE_OUT/sounds/H2Jetpack/{in,loop,out}.ogg

    python3 extract_h2_jetpack_sound.py     # needs MCC's halo2 sounds_neutral.dat (HCE_H2_SOUNDS) and 01b

The Elite Rangers' jump pack (sound\\vehicles\\jet_pack\\jet_pack\\in / loop / out in 01b_spacestation.map) is one of
the few MCC Halo 2 sounds that isn't Opus: its codec is Xbox ADPCM, 44.1 kHz mono, in 36-byte blocks (a 4-byte
predictor/step header, then 64 samples in nibbles). Its chunk's size is the chunk entry's low 16 bits plus its flag
word's low byte as the bits above (a chunk past 64 KiB); the 0x2000 flag puts it in sounds_neutral.dat.
split_factions.py ships the three in the Covenant pack as HCE/Jetpack/In, Loop and Out (HCE_TryJet, HCE_JumpTick),
so the Rangers sound right with or without HaloDoom Evolved.
"""
import os, sys, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))   # readers and writers live in lib/
from h2_elite_anims import MAP01B, CACHE01B
from halosound import xbox_adpcm, to_wav
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
SOUNDS_DIR = os.environ.get('HCE_H2_SOUNDS', '')
TAG = 'sound\\vehicles\\jet_pack\\jet_pack\\'
# Halo 2's sample-rate enum -> Hz
RATES = {0: 22050, 1: 44100, 2: 32000}


def main():
    """decodes the three jump-pack sounds (Xbox ADPCM, whole chunks from sounds_neutral.dat) to WAV and encodes
    them with ffmpeg as out/sounds/H2Jetpack/{in,loop,out}.ogg (Vorbis q5)"""
    from h2map import H2Map, sound_chunks
    bank = os.path.join(SOUNDS_DIR, 'sounds_neutral.dat')
    if not os.path.exists(bank): sys.exit(f'no {bank}: set HCE_H2_SOUNDS to MCC\'s halo2\\h2_maps_win64_dx11')
    m = H2Map(MAP01B, CACHE01B)
    od = f'{OUT}/sounds/H2Jetpack'; os.makedirs(od, exist_ok=True)
    f = open(bank, 'rb')
    for leaf in ('in', 'loop', 'out'):
        perms = sound_chunks(m, TAG + leaf)
        pn, (rate, enc, comp), locs = perms[0]
        assert comp == 1, f'{leaf}: codec {comp} is not Xbox ADPCM'
        ch = 2 if enc == 1 else 1
        data = b''
        for o, cs, fl, us, ri in locs[0][1]:
            f.seek(o); data += f.read((cs & 0xFFFF) | ((fl & 0xFF) << 16))
        pcm = xbox_adpcm(data, ch)
        with tempfile.NamedTemporaryFile(suffix='.wav') as w:
            to_wav(pcm, RATES.get(rate, 22050), ch, w.name)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', w.name, '-c:a', 'libvorbis', '-q:a', '5',
                            f'{od}/{leaf}.ogg'], check=True)
        print(f'{leaf}: {len(pcm) / RATES.get(rate, 22050):.2f}s -> {od}/{leaf}.ogg')


if __name__ == '__main__':
    main()
