"""MCC Halo 2 classic audio: sounds_*.dat chunks are int16-length-prefixed raw Opus packets (the last length is
negative). Wrap them in an Ogg Opus stream so ffmpeg / any player can decode them."""
import struct, zlib

def packets(chunk, strict=False):
    out, p = [], 0
    while p + 2 <= len(chunk):
        L = struct.unpack_from('<h', chunk, p)[0]
        if L == 0 or p + 2 + abs(L) > len(chunk):
            if strict: raise ValueError('bad packet chain at %d' % p)
            break
        n = abs(L); out.append(chunk[p + 2:p + 2 + n]); p += 2 + n
        if L < 0: break
    if strict and p != len(chunk): raise ValueError('chain ends at %d of %d' % (p, len(chunk)))
    return out

_FS = {0: 480, 1: 960, 2: 1920, 3: 2880}
def toc_samples(pkt):
    c = pkt[0] >> 3
    if c < 12: fs = [480, 960, 1920, 2880][c % 4]          # SILK 10/20/40/60 ms
    elif c < 16: fs = [480, 960][c % 2]                     # hybrid 10/20 ms
    else: fs = [120, 240, 480, 960][c % 4]                  # CELT 2.5/5/10/20 ms
    code = pkt[0] & 3
    n = 1 if code == 0 else 2 if code in (1, 2) else (pkt[1] & 0x3F if len(pkt) > 1 else 1)
    return fs * n

def _crc(data):
    crc = 0
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc

def _page(serial, seq, granule, flags, segs_data):
    lacing = b''; body = b''
    for pkt in segs_data:
        n = len(pkt)
        while n >= 255: lacing += b'\xff'; n -= 255
        lacing += bytes([n]); body += pkt
    hdr = struct.pack('<4sBBqIIIB', b'OggS', 0, flags, granule, serial, seq, 0, len(lacing)) + lacing
    crc = _crc(hdr + body)
    return hdr[:22] + struct.pack('<I', crc) + hdr[26:] + body

def to_ogg(pkts, channels=1, rate=48000, preskip=0):
    serial = 0x48324F50; out = []; seq = 0
    head = b'OpusHead' + struct.pack('<BBHIhB', 1, channels, preskip, rate, 0, 0)
    out.append(_page(serial, seq, 0, 2, [head])); seq += 1
    tags = b'OpusTags' + struct.pack('<I', 6) + b'HCE-H2' + struct.pack('<I', 0)
    out.append(_page(serial, seq, 0, 0, [tags])); seq += 1
    gran = 0; group = []
    for i, pk in enumerate(pkts):
        gran += toc_samples(pk); group.append(pk)
        last = i == len(pkts) - 1
        if len(group) >= 40 or last:
            out.append(_page(serial, seq, gran, 4 if last else 0, group)); seq += 1; group = []
    return b''.join(out)
