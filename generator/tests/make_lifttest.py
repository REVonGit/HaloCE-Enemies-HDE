"""lifttest.wad: three small UDMF maps for the Marines' lift use (devtools/lift_test.py).

    Each: a 1536 x 1536 room at 0, a ledge along the north wall at 128 (the player starts on it), and a lift up to it
    (128 x 128, up at 128) jutting into the room. The lift is worked only by the player's kind of activation, as in
    Doom's own maps (no monster use, no monster crossing), three ways:
      LIFTSW    a switch on a pillar out in the room, tagged to the lift (Plat_DownWaitUpStay)
      LIFTFACE  the lift's own faces (tag 0: the lift behind them), used
      LIFTWALK  a walk-over line across the room in front of the lift, tagged to it
"""
import struct, sys

LIFT = 'special=62;arg0={tag};arg1=32;arg2=105;playeruse=true;repeatspecial=true;'
WALK = 'special=62;arg0=1;arg1=32;arg2=105;playercross=true;repeatspecial=true;'


def build(name, kind):
    V, L, S, SEC = [], [], [], []
    VI = {}
    def v(x, y):
        if (x, y) not in VI: V.append((x, y)); VI[(x, y)] = len(V) - 1
        return VI[(x, y)]
    def sector(fl, ce=320, ft='FLOOR0_1', tag=0):
        SEC.append((fl, ce, ft, tag)); return len(SEC) - 1
    def side(sec, mid='-', lo='-', up='-'):
        S.append((sec, mid, lo, up)); return len(S) - 1
    def wall(a, b, front, tex='STARTAN2', sp=''):
        L.append((v(*a), v(*b), side(front, mid=tex), None, sp))
    def step(a, b, front, back, sp='', tex='STARTAN2'):
        L.append((v(*a), v(*b), side(front, lo=tex, up=tex), side(back, lo=tex, up=tex), sp))
    room = sector(0, ft='FLAT1')
    ledge = sector(128, ft='FLOOR4_8')
    lift = sector(128, ft='PLAT1', tag=1)
    # the outer walls (clockwise: inside is the front); the ledge from y 1100 up, its front split round the lift (x 704-832)
    for a, b in [((0, 0), (0, 1100)), ((1536, 1100), (1536, 0)), ((1536, 0), (0, 0))]: wall(a, b, room)
    for a, b in [((0, 1100), (0, 1536)), ((0, 1536), (1536, 1536)), ((1536, 1536), (1536, 1100))]: wall(a, b, ledge)
    step((0, 1100), (704, 1100), room, ledge); step((704, 1100), (832, 1100), lift, ledge); step((832, 1100), (1536, 1100), room, ledge)
    face = LIFT.format(tag=0) if kind == 'face' else ''
    step((704, 972), (832, 972), room, lift, face); step((832, 972), (832, 1100), room, lift, face); step((704, 1100), (704, 972), room, lift, face)
    if kind == 'switch':
        # a pillar out in the room, its south face the switch (counter-clockwise: solid)
        x, y = 300, 500
        pts = [(x, y), (x, y + 64), (x + 64, y + 64), (x + 64, y)]
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            wall(b, a, room, 'SW1STARG' if (a, b) == ((x + 64, y), (x, y)) else 'STARTAN2',
                 LIFT.format(tag=1) if (a, b) == ((x + 64, y), (x, y)) else '')
    if kind == 'walk':
        # a walk-over line across the room in front of the lift: two-sided, room on both sides
        step((200, 760), (1336, 760), room, room, WALK)
    txt = ['namespace="zdoom";']
    txt += [f'vertex{{x={x:.1f};y={y:.1f};}}' for x, y in V]
    for a, b, f, bk, sp in L:
        txt.append(f'linedef{{v1={a};v2={b};sidefront={f};' + (f'sideback={bk};twosided=true;' if bk is not None else 'blocking=true;') + sp + '}')
    for sec, mid, lo, up in S:
        txt.append(f'sidedef{{sector={sec};texturemiddle="{mid}";texturebottom="{lo}";texturetop="{up}";}}')
    for fl, ce, ft, tag in SEC:
        txt.append(f'sector{{heightfloor={fl};heightceiling={ce};texturefloor="{ft}";textureceiling="CEIL1_1";lightlevel=200;'
                   + (f'id={tag};' if tag else '') + '}')
    txt.append('thing{x=768.0;y=1300.0;angle=270;type=1;skill1=true;skill2=true;skill3=true;skill4=true;skill5=true;single=true;}')
    return [(name.encode(), b''), (b'TEXTMAP', ('\n'.join(txt) + '\n').encode()), (b'ENDMAP', b'')]


lumps = build('LIFTSW', 'switch') + build('LIFTFACE', 'face') + build('LIFTWALK', 'walk')
data = b''.join(d for _, d in lumps); off = 12 + len(data)
d = struct.pack('<4sII', b'PWAD', len(lumps), off) + data
pos = 12
for n, l in lumps:
    d += struct.pack('<II8s', pos, len(l), n.ljust(8, b'\0')[:8]); pos += len(l)
open(sys.argv[1] if len(sys.argv) > 1 else 'lifttest.wad', 'wb').write(d)
print('lifttest.wad: LIFTSW, LIFTFACE, LIFTWALK')
