"""keep the committed bytes of every sound (voice lines, the add-on's effects) (the loudness pass isn't byte-stable): for each
packs/*/sounds/hce_voice/** file, use the HEAD copy at the same path (or at the old packs/HaloCE_Enemies_Voices path)
when it is the same line. Files are numbered per voice across its categories, so a new category renumbers the files
after it: the same path can hold a different line. So the HEAD copy is only kept when its decoded audio matches."""
import hashlib, os, subprocess, sys
import numpy as np
repo = sys.argv[1]
os.chdir(repo)
head = set(subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'HEAD', 'packs'], capture_output=True, text=True).stdout.split('\n'))
head |= set(subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'HEAD', 'generator/voice_extra'], capture_output=True, text=True).stdout.split('\n'))


def pcm(data):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 's16le', '-ac', '1', '-ar', '22050', '-'],
                       input=data, capture_output=True)
    return np.frombuffer(r.stdout, '<i2').astype(np.float64) if r.returncode == 0 and r.stdout else None


def same_line(a, b, level=False):
    """the same recording, levelled again: lengths within 2% and the waveforms correlate (a re-encode or a re-run
    loudness pass changes the bytes and the level slightly, not the line)"""
    if a is None or b is None or abs(len(a) - len(b)) > max(441, 0.02 * len(b)): return False
    if not a.any() or not b.any(): return not a.any() and not b.any()
    # best normalised cross-correlation within +-30 ms (encoders shift the start by some samples)
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    x = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    lag = 660
    best = max(x[:lag].max(), x[-lag:].max())
    c = float(best / (np.linalg.norm(a) * np.linalg.norm(b)))
    # level: a level set on purpose (the Chief's lines: split_factions.py's gain, not the loudness pass, whose re-runs
    # drift by more than this) that changed by half a dB or more (RMS) is a new take of the line
    if level and abs(20 * np.log10(np.linalg.norm(a) / np.sqrt(len(a)) / (np.linalg.norm(b) / np.sqrt(len(b))))) >= 0.5: return False
    # the loudness pass's limiter reshapes short screams: the same length to the sample still means the same line
    return c > 0.9 or (len(a) == len(b) and c > 0.75)


n = skipped = 0
roots = [f'packs/{d}/sounds' for d in os.listdir('packs')] + (['generator/voice_extra'] if os.path.isdir('generator/voice_extra') else [])
for root in roots:                      # every sound, not only the voices: the add-on's are loudened too
    if not os.path.isdir(root): continue
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = f'{dp}/{f}'; rel = p.split('/sounds/', 1)[-1]
            if not f.lower().endswith(('.ogg', '.wav', '.flac')): continue
            for cand in (p, f'packs/HaloCE_Enemies_Voices/sounds/{rel}'):
                if cand in head:
                    data = subprocess.run(['git', 'show', f'HEAD:{cand}'], capture_output=True).stdout
                    cur = open(p, 'rb').read()
                    if data and data != cur:
                        if same_line(pcm(data), pcm(cur), '/hce_chief/' in p):
                            open(p, 'wb').write(data); n += 1
                        else: skipped += 1
                    break
print('voice lines kept from HEAD:', n, ' different lines at an old path (left new):', skipped)
