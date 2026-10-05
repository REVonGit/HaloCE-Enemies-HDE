"""Halo CE loose .sound tags -> WAV (permutations of the first pitch range)."""
import struct, wave, io
import numpy as np

def parse(path):
    d = open(path, 'rb').read()
    B = 64
    u = lambda f, o: struct.unpack_from('>' + f, d, o)
    flags, = u('I', B); sr_i, = u('h', B + 6); enc, comp = u('hh', B + 108)
    plen, = u('i', B + 112 + 8)
    npr, = u('i', B + 152)
    cur = B + 164
    if plen > 0: cur += plen + 1
    prs = []
    pr_base = cur; cur += npr * 72
    out = []
    for i in range(npr):
        p = pr_base + i * 72
        name = d[p:p + 32].split(b'\0')[0].decode('latin1')
        nperm, = u('i', p + 60)
        perm_base = cur; cur += nperm * 124
        perms = []
        for k in range(nperm):
            q = perm_base + k * 124
            pname = d[q:q + 32].split(b'\0')[0].decode('latin1')
            pcomp, = u('h', q + 40)
            sizes = [u('i', q + off)[0] for off in (64, 84, 104)]
            blobs = []
            for sz in sizes:
                blobs.append(d[cur:cur + sz]); cur += sz
            perms.append(dict(name=pname, compression=pcomp, samples=blobs[0]))
        out.append(dict(name=name, perms=perms))
    return dict(rate=44100 if sr_i == 1 else 22050, channels=2 if enc == 1 else 1, compression=comp, pitch_ranges=out, end=cur, size=len(d))

# ---- Xbox ADPCM (36-byte blocks per channel: 4-byte header + 32 bytes = 64 samples + 1)
STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97,
        107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
        876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871,
        5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623,
        27086, 29794, 32767]
IDX = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]

def xbox_adpcm(data, ch):
    blk = 36 * ch
    out = [[] for _ in range(ch)]
    for b in range(len(data) // blk):
        base = b * blk
        st = []
        for c in range(ch):
            pred, idx = struct.unpack_from('<hB', data, base + 4 * c)
            st.append([pred, min(88, idx)]); out[c].append(pred)
        p = base + 4 * ch
        for chunk in range(8):
            for c in range(ch):
                word = data[p:p + 4]; p += 4
                for byte in word:
                    for nib in (byte & 15, byte >> 4):
                        pred, idx = st[c]
                        step = STEP[idx]
                        diff = step >> 3
                        if nib & 1: diff += step >> 2
                        if nib & 2: diff += step >> 1
                        if nib & 4: diff += step
                        if nib & 8: diff = -diff
                        pred = max(-32768, min(32767, pred + diff))
                        idx = max(0, min(88, idx + IDX[nib]))
                        st[c] = [pred, idx]; out[c].append(pred)
    return np.array(out, dtype=np.int16).T

def to_wav(samples, rate, ch, path):
    w = wave.open(path, 'wb'); w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(samples.astype('<i2').tobytes()); w.close()

def decode(perm, rate, ch):
    c = perm['compression']; s = perm['samples']
    if c == 0:
        a = np.frombuffer(s[:len(s) // 2 * 2], '>i2').reshape(-1, ch)
        return a
    if c == 1: return xbox_adpcm(s, ch)
    if c == 3: return None   # ogg: copy as-is
    raise ValueError(f'compression {c}')
