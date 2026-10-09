"""covertest.wad: a UDMF arena for the cover / climbing / difficulty load test (tests/run_test.sh).

    2048 x 2560, ceiling 320. Solid 64x64 pillars and 32-high low walls through the middle; along the north wall a
    platform at 80 (where the player starts, facing south), and two 30-high steps before it. Elites and Brutes can
    hoist the 80 ledge from the floor, Marines the 30 steps; the low walls are crouch cover and can be vaulted.
"""
import struct, sys
V, L, S, SEC = [], [], [], []
def v(x, y):
    V.append((x, y)); return len(V) - 1
def sector(fl, ce=320, ft='FLAT1'):
    SEC.append((fl, ce, ft)); return len(SEC) - 1
def side(sec, mid='-', lo='-', up='-'):
    S.append((sec, mid, lo, up)); return len(S) - 1
def poly(pts, front_sec, back_sec=None, tex='STARTAN2'):
    """a closed loop; front (right) side faces front_sec. For a hole or raised block, list the points
    counter-clockwise so the right side faces out."""
    ids = [v(x, y) for x, y in pts]
    for i in range(len(ids)):
        a, b = ids[i], ids[(i + 1) % len(ids)]
        if back_sec is None: L.append((a, b, side(front_sec, mid=tex), None, True))
        else: L.append((a, b, side(front_sec, lo=tex, up=tex), side(back_sec), False))
room = sector(0)
poly([(0, 0), (0, 2560), (2048, 2560), (2048, 0)], room)                 # clockwise: the inside is the front
plat = sector(80, ft='FLOOR4_8'); poly([(16, 2240), (2032, 2240), (2032, 2544), (16, 2544)], room, plat)
for x, y in [(300, 1980), (1600, 1980)]:                                  # steps at 30: Marine-sized hoists
    st = sector(30, ft='FLOOR5_1'); poly([(x, y), (x + 160, y), (x + 160, y + 160), (x, y + 160)], room, st)
for x, y in [(400, 700), (800, 1100), (1240, 900), (1640, 1300), (600, 1500), (1100, 1650), (1500, 600), (300, 1900), (1750, 1850)]:
    poly([(x, y), (x + 64, y), (x + 64, y + 64), (x, y + 64)], room)     # counter-clockwise: a solid pillar
for x, y in [(200, 1000), (1000, 1300), (1400, 1100), (700, 800), (1600, 1650), (900, 1950)]:
    low = sector(32, ft='FLOOR0_1'); poly([(x, y), (x + 160, y), (x + 160, y + 24), (x, y + 24)], room, low)
txt = ['namespace="zdoom";']
txt += [f'vertex{{x={x:.1f};y={y:.1f};}}' for x, y in V]
for a, b, f, bk, blk in L:
    txt.append(f'linedef{{v1={a};v2={b};sidefront={f};' + (f'sideback={bk};twosided=true;' if bk is not None else '') + ('blocking=true;' if blk else '') + '}')
for sec, mid, lo, up in S:
    txt.append(f'sidedef{{sector={sec};texturemiddle="{mid}";texturebottom="{lo}";texturetop="{up}";}}')
for fl, ce, ft in SEC:
    txt.append(f'sector{{heightfloor={fl};heightceiling={ce};texturefloor="{ft}";textureceiling="CEIL1_1";lightlevel=200;}}')
txt.append('thing{x=1024.0;y=2400.0;angle=270;type=1;skill1=true;skill2=true;skill3=true;skill4=true;skill5=true;single=true;}')
tm = ('\n'.join(txt) + '\n').encode()
lumps = [(b'COVERTST', b''), (b'TEXTMAP', tm), (b'ENDMAP', b'')]
data = b''.join(d for _, d in lumps); off = 12 + len(data)
d = struct.pack('<4sII', b'PWAD', len(lumps), off) + data
pos = 12
for n, l in lumps:
    d += struct.pack('<II8s', pos, len(l), n); pos += len(l)
open(sys.argv[1] if len(sys.argv) > 1 else 'covertest.wad', 'wb').write(d)
print('covertest.wad', len(V), 'vertices', len(L), 'lines', len(SEC), 'sectors')
