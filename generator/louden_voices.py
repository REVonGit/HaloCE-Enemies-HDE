#!/usr/bin/env python3
"""Make the enemy dialogue louder: every voice line is brought up to a common loudness.

    python3 louden_voices.py <pack dir> [<pack dir> ...]

Which files: everything an SNDINFO lump in the pack dir maps under HCE/<Voice>/<Event> for a voice set that
some class names in HCE_Voices (the sets HCE_Say() plays), minus movement / body-fall / footstep sounds.

How: per file, the integrated loudness (EBU R128) is measured and the line is raised toward TARGET LUFS (never
lowered, at most MAX_GAIN dB), with a limiter holding the peaks under -0.8 dBFS. A manifest (.loudened.json)
records the processed files' hashes, so running it again on the same files does nothing.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
import hashlib, json, os, re, subprocess, sys

TARGET = -11.0      # LUFS
MAX_GAIN = 18.0     # dB
SKIP = re.compile(r'(move|flying|bodyfall|step|land|thump|footstep)', re.I)


def lufs(path):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', out)
    return float(m[-1]) if m else None


def sha(path):
    return hashlib.sha1(open(path, 'rb').read()).hexdigest()


def voice_sets(roots):
    names = set()
    here = os.path.dirname(os.path.abspath(__file__))
    for base in list(roots) + [os.path.join(here, 'pack'), os.path.join(here, 'addons', 'digsite')]:
        for r, _, fs in os.walk(base):
            for f in fs:
                if f.endswith('.zsc'):
                    for m in re.findall(r'HCE_Voices\s+"([^"]+)"', open(os.path.join(r, f), errors='replace').read()):
                        names.update(x.strip().lower() for x in m.split(',') if x.strip())
    return names


def files_of(root, voices):
    out = set()
    for f in os.listdir(root):
        if not f.lower().startswith('sndinfo'): continue
        for line in open(os.path.join(root, f), errors='replace'):
            m = re.match(r'\s*HCE/([^/\s]+)/(\S+)\s+"([^"]+)"', line)
            if not m or m.group(1).lower() not in voices or SKIP.search(m.group(2)) or SKIP.search(m.group(3)): continue
            p = os.path.join(root, m.group(3))
            if os.path.isfile(p): out.add(p)
    return sorted(out)


def process(root, voices):
    man_path = os.path.join(root, '.loudened.json')
    man = json.load(open(man_path)) if os.path.exists(man_path) else {}
    files = files_of(root, voices)
    done = 0
    for p in files:
        rel = os.path.relpath(p, root)
        if man.get(rel) == sha(p): continue
        i = lufs(p)
        if i is None: continue
        gain = max(0.0, min(MAX_GAIN, TARGET - i))
        if gain < 0.5:
            man[rel] = sha(p); continue
        tmp = p + '.tmp.ogg'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', p, '-af',
                        f'volume={gain:.1f}dB,alimiter=limit=0.91:attack=2:release=50:level=false',
                        '-c:a', 'libvorbis', '-q:a', '6', tmp], check=True)
        os.replace(tmp, p)
        man[rel] = sha(p); done += 1
    json.dump(man, open(man_path, 'w'), indent=0, sort_keys=True)
    print(f'{root}: {done} voice lines raised ({len(files)} voice files, target {TARGET} LUFS)')


if __name__ == '__main__':
    roots = sys.argv[1:]
    if not roots: sys.exit(__doc__)
    v = voice_sets(roots)
    for r in roots: process(r, v)
