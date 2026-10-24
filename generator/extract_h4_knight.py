"""Halo 4's Promethean Knight death sounds, for the Sentinel Knights (MCC's Halo 4, Wwise 2013 packages).

    python3 extract_h4_knight.py            # -> knight_h4/{Derez,Death,Death Major,Death Fall} N.ogg

* the dissolve: the event play_fx_knight_derez in halo4\\sound\\pc\\sfxbank.pck (HCE_H4_SFXBANK), its sounds' media
  from the banks' own DATA;
* the death cries: the Knight's combat dialogue (combat\\storm_knight01\\default\\09_involuntary\\dth, dth_mjr,
  dth_fall), one of the external files in halo4\\sound\\pc\\english(us)\\soundstream.pck (HCE_H4_VOSTREAM, whole or
  as 7-Zip's numbered pieces: lib/splitfile). Their 64-bit ids are the game's own (no name hash found), but the
  package stores them in the alphabetical order of their paths, and a Halo 4 map (HCE_H4_MAP: any with Knights; its
  string table lists every combat line's .wav path) gives those paths: the n-th path in sorted order is the n-th file
  by offset. Checked on ff151_mezzanine: the voice boundaries this predicts (masterchief / _fem / crawler / elites ...
  jackal | knight) fall where the audio changes, and the Knight's line lengths fit its categories (dodges and dives
  ~1 s, idles and searches 3-6 s). Some takes share a length (dth 05-08 and dth_fall 05-08, dth_fall 01-04 and
  dth_mjr 01-04) but are different recordings; an exact repeat would be kept once.
Wwise keeps no names, only 32-bit FNV-1 hashes of them (lowercased), so events are looked up by hashing their names.
The media are Wwise Vorbis: vgmstream-cli (HCE_VGMSTREAM) decodes them, ffmpeg writes the Vorbis files, downmixed to
mono. split_factions.knight_voice ships knight_h4/ in the Sentinels pack (KNIGHT_H4_LINES: the events they play for).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))
import splitfile
import os, re, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'knight_h4')
UP = '/mnt/user-data/uploads/Halo The Master Chief Collection'
SFXBANK = os.environ.get('HCE_H4_SFXBANK', f'{UP}/halo4/sound/pc/sfxbank.pck')
VOBANK = os.environ.get('HCE_H4_VOBANK', f'{UP}/halo4/sound/pc/english(us)/soundbank.pck')
VOSTREAM = os.environ.get('HCE_H4_VOSTREAM', f'{UP}/Split/soundstream.pck')
H4_MAP = os.environ.get('HCE_H4_MAP', f'{UP}/halo4/maps/ff151_mezzanine.map')
KNIGHT_VOICE = 'combat\\storm_knight01\\default\\09_involuntary\\'
# knight_h4 file stem -> the dialogue folder its takes come from
DEATHS = {'Death': 'dth', 'Death Major': 'dth_mjr', 'Death Fall': 'dth_fall'}
VGMSTREAM = os.environ.get('HCE_VGMSTREAM', 'vgmstream-cli')
DEREZ_EVENT = 'play_fx_knight_derez'


def fnv(s):
    """Wwise's id for a name: 32-bit FNV-1 of its lowercase bytes"""
    h = 2166136261
    for c in s.lower().encode(): h = (h * 16777619) & 0xffffffff; h ^= c
    return h


def read_pck(f):
    """an AKPK package's tables: {'banks': [...], 'sounds': [...], 'ext': [...]}, each entry {id, size, off}"""
    f.seek(0); d = f.read(32)
    assert d[:4] == b'AKPK', 'not a Wwise package'
    hsize, ver, lang_sz, banks_sz, sounds_sz, ext_sz = struct.unpack('<6I', d[4:28])
    f.seek(8); hdr = f.read(hsize)
    fields = 4 if lang_sz + banks_sz + sounds_sz + 16 == hsize else 5
    off = 4 * fields + lang_sz
    def table(sz, wide):
        nonlocal off
        t = hdr[off:off + sz]; off += sz
        n, es, out = struct.unpack('<I', t[:4])[0], (24 if wide else 20), []
        for i in range(n):
            e = t[4 + i * es: 4 + (i + 1) * es]
            id_, blk, size, start, _lang = struct.unpack('<QIIII' if wide else '<IIIII', e)
            out.append(dict(id=id_, size=size, off=start * blk))
        return out
    return dict(banks=table(banks_sz, False), sounds=table(sounds_sz, False), ext=table(ext_sz, True) if fields == 5 else [])


def read_banks(path):
    """every bank in a package: (objects {id: (type, body)}, events {id: [action ids]}, media {id: bytes})"""
    objs, evs, media = {}, {}, {}
    with open(path, 'rb') as f:
        for b in read_pck(f)['banks']:
            f.seek(b['off']); d = f.read(b['size']); p = 0; didx = {}; data = None
            while p + 8 <= len(d):
                tag, sz = d[p:p + 4], struct.unpack('<I', d[p + 4:p + 8])[0]; body = d[p + 8:p + 8 + sz]
                if tag == b'DIDX':
                    for i in range(0, sz, 12):
                        mid, mo, ms = struct.unpack('<III', body[i:i + 12]); didx[mid] = (mo, ms)
                elif tag == b'DATA': data = body
                elif tag == b'HIRC':
                    q = 4
                    for _ in range(struct.unpack('<I', body[:4])[0]):
                        t = body[q]; ln, oid = struct.unpack('<II', body[q + 1:q + 9]); ob = body[q + 9:q + 5 + ln]
                        objs[oid] = (t, ob)
                        if t == 4:                       # an event: its action list
                            n = struct.unpack('<I', ob[:4])[0]; evs.setdefault(oid, []).extend(struct.unpack(f'<{n}I', ob[4:4 + 4 * n]))
                        q += 5 + ln
                p += 8 + sz
            if data is not None:
                for mid, (mo, ms) in didx.items(): media.setdefault(mid, data[mo:mo + ms])
    return objs, evs, media


def children(objs, b):
    """a container's child list: the first count-prefixed run of ids that are all sounds or containers"""
    for i in range(0, len(b) - 8):
        n = struct.unpack('<I', b[i:i + 4])[0]
        if 1 <= n <= 64 and i + 4 + 4 * n <= len(b):
            ids = struct.unpack(f'<{n}I', b[i + 4:i + 4 + 4 * n])
            if all(x in objs and objs[x][0] in (2, 5, 6, 7) for x in ids): return list(ids)
    return []


def event_sources(objs, evs, name):
    """the media ids an event's Play actions reach (sound objects: the source id 8 bytes into the body, Wwise v88)"""
    out, seen = [], set()
    def walk(oid):
        if oid in seen or oid not in objs: return
        seen.add(oid); t, b = objs[oid]
        if t == 2: out.append(struct.unpack('<I', b[8:12])[0]); return
        for ch in children(objs, b): walk(ch)
    for a in evs.get(fnv(name), []):
        if a in objs and objs[a][0] == 3:
            atype, tgt = struct.unpack('<HI', objs[a][1][:6])
            if atype == 0x0403: walk(tgt)                  # Play
    return out


def wem_to_ogg(data, dst):
    """a Wwise media file -> mono Vorbis at dst (vgmstream decodes, ffmpeg encodes)"""
    with tempfile.TemporaryDirectory() as t:
        open(f'{t}/a.wem', 'wb').write(data)
        subprocess.run([VGMSTREAM, '-o', f'{t}/a.wav', f'{t}/a.wem'], check=True, capture_output=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{t}/a.wav', '-ac', '1', '-c:a', 'libvorbis', '-q:a', '6', dst], check=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    objs, evs, media = read_banks(SFXBANK)
    srcs = [s for s in dict.fromkeys(event_sources(objs, evs, DEREZ_EVENT)) if s in media]
    for f in os.listdir(OUT):
        if f.startswith('Derez '): os.remove(os.path.join(OUT, f))
    for i, s in enumerate(sorted(srcs), 1): wem_to_ogg(media[s], f'{OUT}/Derez {i}.ogg')
    print('Derez', len(srcs), 'takes')
    if not (splitfile.exists(VOSTREAM) and os.path.exists(H4_MAP)):
        print('death cries skipped: no', VOSTREAM if not splitfile.exists(VOSTREAM) else H4_MAP); return
    import hashlib
    m = open(H4_MAP, 'rb').read()
    paths = sorted(set(x.group().decode() for x in re.finditer(rb'combat\\[a-z0-9_\\]{3,200}\.wav', m)))
    with splitfile.open(VOSTREAM) as f:
        ext = sorted(read_pck(f)['ext'], key=lambda e: e['off'])
        seen = set()
        for stem, folder in DEATHS.items():
            for g in os.listdir(OUT):
                if re.match(re.escape(stem) + r' \d+\.ogg$', g): os.remove(os.path.join(OUT, g))
            n = 0
            for i, p in enumerate(paths):
                if not p.startswith(KNIGHT_VOICE + folder + '\\'): continue
                e = ext[i]; f.seek(e['off']); data = f.read(e['size'])
                with tempfile.TemporaryDirectory() as t:              # the same take filed twice: kept once
                    open(f'{t}/a.wem', 'wb').write(data)
                    pcm = subprocess.run([VGMSTREAM, '-p', f'{t}/a.wem'], capture_output=True).stdout
                key = hashlib.sha1(pcm[44:]).hexdigest()
                if key in seen: continue
                seen.add(key); n += 1
                wem_to_ogg(data, f'{OUT}/{stem} {n}.ogg')
            print(stem, n, 'takes')


if __name__ == '__main__':
    main()
