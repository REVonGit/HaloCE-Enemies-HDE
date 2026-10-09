"""covertest.wad: a UDMF arena for the AI load test (tests/run_test.sh).

    The main room, 2048 x 2560, ceiling 320: solid 64x64 pillars and 32-high low walls through the middle; along the
    north wall a platform at 80 (the player starts on it, facing south) with a lift up to it in the middle of its
    front edge (Plat_DownWaitUpStay, worked by using it), and two 30-high steps before it. East, through a door in
    the east wall (Door_Raise, worked by using it from either side), an annex the test harness teleports the player
    into, so the Marines have to follow through and the Covenant have to open the door to chase.
"""
import struct, sys
V, L, S, SEC = [], [], [], []
VI = {}
def v(x, y):
    if (x, y) not in VI: V.append((x, y)); VI[(x, y)] = len(V) - 1
    return VI[(x, y)]
def sector(fl, ce=320, ft='FLOOR0_1'):
    SEC.append((fl, ce, ft)); return len(SEC) - 1
def side(sec, mid='-', lo='-', up='-'):
    S.append((sec, mid, lo, up)); return len(S) - 1
def wall(a, b, front, tex='STARTAN2'):
    """one-sided: the front (right of a->b) faces sector `front`"""
    L.append((v(*a), v(*b), side(front, mid=tex), None, ''))
def step(a, b, front, back, special='', tex='STARTAN2'):
    """two-sided: front (right of a->b) and back sectors"""
    L.append((v(*a), v(*b), side(front, lo=tex, up=tex), side(back, lo=tex, up=tex), special))
def loop(pts, front, back=None):
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if back is None: wall(a, b, front)
        else: step(a, b, front, back)

DOOR = 'special=12;arg0=0;arg1=16;arg2=150;playeruse=true;monsteruse=true;repeatspecial=true;'
LIFT = 'special=62;arg0=0;arg1=32;arg2=105;playeruse=true;monsteruse=true;repeatspecial=true;'
room = sector(0, ft='FLAT1')
plat = sector(80, ft='FLOOR4_8')
lift = sector(80, ft='PLAT1')
door = sector(0, 0, ft='FLAT20')
annex = sector(0, 256, ft='GRASS1')
# the main room (clockwise: inside is the front), the door gap at x 2048, y 1222-1350
for a, b in [((0, 0), (0, 2560)), ((0, 2560), (2048, 2560)), ((2048, 2560), (2048, 1350)), ((2048, 1222), (2048, 0)), ((2048, 0), (0, 0))]:
    wall(a, b, room)
# the door and its jambs
step((2048, 1350), (2048, 1222), room, door, DOOR, 'BIGDOOR2')
step((2080, 1222), (2080, 1350), annex, door, DOOR, 'BIGDOOR2')
wall((2048, 1350), (2080, 1350), door, 'DOORTRAK'); wall((2080, 1222), (2048, 1222), door, 'DOORTRAK')
# the annex
for a, b in [((2080, 900), (2080, 1222)), ((2080, 1350), (2080, 1700)), ((2080, 1700), (2600, 1700)), ((2600, 1700), (2600, 900)), ((2600, 900), (2080, 900))]:
    wall(a, b, annex)
# the platform at 80, its front edge split round the lift
step((16, 2240), (960, 2240), room, plat); step((960, 2240), (1088, 2240), lift, plat); step((1088, 2240), (2032, 2240), room, plat)
step((2032, 2240), (2032, 2544), room, plat); step((2032, 2544), (16, 2544), room, plat); step((16, 2544), (16, 2240), room, plat)
# the lift (up at 80; using any of its three open sides lowers it)
step((960, 2112), (1088, 2112), room, lift, LIFT); step((1088, 2112), (1088, 2240), room, lift, LIFT); step((960, 2240), (960, 2112), room, lift, LIFT)
for x, y in [(300, 1980), (1600, 1980)]:                                   # steps at 30: Marine-sized hoists
    loop([(x, y), (x + 160, y), (x + 160, y + 160), (x, y + 160)], room, sector(30, ft='FLOOR5_1'))
for x, y in [(400, 700), (800, 1100), (1240, 900), (1640, 1300), (600, 1500), (1100, 1650), (1500, 600), (300, 1900), (1750, 1850)]:
    loop([(x, y), (x + 64, y), (x + 64, y + 64), (x, y + 64)], room)        # counter-clockwise: a solid pillar
for x, y in [(200, 1000), (1000, 1300), (1400, 1100), (700, 800), (1600, 1650), (900, 1950)]:
    loop([(x, y), (x + 160, y), (x + 160, y + 24), (x, y + 24)], room, sector(32, ft='FLOOR0_1'))

txt = ['namespace="zdoom";']
txt += [f'vertex{{x={x:.1f};y={y:.1f};}}' for x, y in V]
for a, b, f, bk, sp in L:
    txt.append(f'linedef{{v1={a};v2={b};sidefront={f};' + (f'sideback={bk};twosided=true;' if bk is not None else 'blocking=true;') + sp + '}')
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
