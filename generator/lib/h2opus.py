"""MCC Halo 2 classic audio: sounds_*.dat chunks are int16-length-prefixed raw Opus packets (the last length is
negative). Wrap them in an Ogg Opus stream so ffmpeg / any player can decode them.

    ogg = to_ogg(packets(chunk_bytes), channels=1)      # then ffmpeg -i x.ogg x.wav (or feed UZDoom the .ogg)

Halo 2 MCC Opus is 48 kHz internally whatever the tag's sample rate says."""
import struct, zlib

def packets(chunk, strict=False):
    """Split a sounds_*.dat chunk into its Opus packets (list of bytes). Each packet is an int16 length then the
    bytes; a negative length marks the last packet. A broken chain stops the list quietly, or raises ValueError when
    strict is set."""
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

_FS = {0: 480, 1: 960, 2: 1920, 3: 2880}   # SILK frame sizes in 48 kHz samples (unused; toc_samples spells them out)
def toc_samples(pkt):
    """Samples (at 48 kHz) an Opus packet decodes to, from its TOC byte (RFC 6716 section 3.1): frame size by
    configuration, times the frame count from the low two bits (code 3 reads the count byte)."""
    c = pkt[0] >> 3
    if c < 12: fs = [480, 960, 1920, 2880][c % 4]          # SILK 10/20/40/60 ms
    elif c < 16: fs = [480, 960][c % 2]                     # hybrid 10/20 ms
    else: fs = [120, 240, 480, 960][c % 4]                  # CELT 2.5/5/10/20 ms
    code = pkt[0] & 3
    n = 1 if code == 0 else 2 if code in (1, 2) else (pkt[1] & 0x3F if len(pkt) > 1 else 1)
    return fs * n

def _crc(data):
    """Ogg's CRC-32 (polynomial 0x04C11DB7, no reflection, zero init and xorout) of data."""
    crc = 0
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc

def _page(serial, seq, granule, flags, segs_data):
    """One Ogg page (bytes) holding the packets in segs_data: header, lacing values (255-runs per packet), CRC
    patched in at byte 22. flags: 2 = first page of stream, 4 = last page."""
    lacing = b''; body = b''
    for pkt in segs_data:
        n = len(pkt)
        while n >= 255: lacing += b'\xff'; n -= 255
        lacing += bytes([n]); body += pkt
    hdr = struct.pack('<4sBBqIIIB', b'OggS', 0, flags, granule, serial, seq, 0, len(lacing)) + lacing
    crc = _crc(hdr + body)
    return hdr[:22] + struct.pack('<I', crc) + hdr[26:] + body

def to_ogg(pkts, channels=1, rate=48000, preskip=0):
    """Ogg Opus file bytes for a list of raw packets: OpusHead page, OpusTags page ('HCE-H2' vendor), then the
    packets 40 to a page with the granule position (running 48 kHz sample count) on each. rate is only the
    'original sample rate' hint in the header; Opus always plays at 48 kHz."""
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
