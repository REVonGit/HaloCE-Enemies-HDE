"""Read loose (source) Halo CE tag files with the same decomp layouts used for cache maps.

Tag files are big-endian: 64-byte header, then the main struct, then each field's child data in field
order (tag reference paths, data blobs, block elements).  Only the main struct is mapped here; tag
reference names are recovered by walking the trailing strings in order.  Blocks are left unresolved
(count only), which is enough for the actor/variant/biped/collision stats the pack uses.

    lm = LooseMap(); t = lm.load('grunt.actor_variant', 'grunt')
    T = tags.tag(lm, t, 'actor_variant_definition'); T['ranged_combat.maximum_firing_range']

Several tag files can be loaded into one LooseMap; each gets its own address range (a 0x100 gap apart) and a tag id
0x80000 + n, with the tags it references given fake ids 0x10000 + k so T['some_tag_reference'] returns a dict with
cls and name like it does on a cache map (data=None: the referenced file is not loaded)."""
import struct, re
from tags import LAYOUT, FMT, VEC

# tag file group code (bytes 0x24..0x28 of the header) -> decomp struct of its main body. Add a pair to load
# another tag class; the struct must exist in the decomp headers.
GROUPS = {'actv': 'actor_variant_definition', 'actr': 'actor_definition', 'bipd': 'biped_definition',
          'coll': 'collision_model', 'weap': 'weapon_definition'}

class LooseMap:
    """A fake map for tags.Tag: d (the loaded files concatenated with padding), tags, byid; u() reads big-endian
    where HMap reads little-endian, so the same decomp layouts apply."""
    def __init__(s):
        """start empty; load() adds tags"""
        s.d = b''; s.tags = []; s.byid = {}
    def u(s, fmt, a):
        """big-endian struct.unpack of fmt at file offset a (addresses here are plain offsets into s.d)."""
        return struct.unpack_from('>' + fmt, s.d, a)
    # all loaded tags of a group code
    def find(s, cls): return [t for t in s.tags if t['cls'] == cls]

    def _tagrefs(s, st, base, out):
        """Append the offsets of every tag_reference field in struct st at base (recursing into embedded structs)."""
        L = LAYOUT.layout(st)
        for fn, (o, t, n) in sorted(L['fields'].items(), key=lambda x: x[1][0]):
            t = re.sub(r'^(struct|union)\s+', '', t.strip())
            if t == 'tag_reference':
                out.append(base + o)
            elif t in LAYOUT.structs and t not in ('tag_block', 'tag_data') and n == 1:
                s._tagrefs(t, base + o, out)

    def load(s, path, name):
        """append the loose tag file at path (a GROUPS class) to s.d at a 0x100-aligned base and register it as tag
        `name`; every tag_reference in its struct gets a synthetic id whose byid entry carries the path string found
        after the struct. Returns the tag dict (cls, id, name, data = the struct's offset)"""
        raw = open(path, 'rb').read()
        grp = raw[0x24:0x28].decode('latin1')
        st = GROUPS[grp]
        base = len(s.d) + 0x100
        s.d += b'\0' * (base - len(s.d)) + raw
        d = bytearray(s.d)
        size = LAYOUT.layout(st)['size']
        refs = []
        s._tagrefs(st, base + 64, refs)
        cur = base + 64 + size
        for a in refs:
            cls = d[a:a + 4].decode('latin1', 'replace')
            ln = struct.unpack_from('>i', d, a + 8)[0]
            tid = 0xFFFFFFFF
            if 0 < ln < 256:
                # next NUL-terminated printable string of exactly this length
                m = re.compile(rb'[\x20-\x7e]{%d}\x00' % ln).search(bytes(d), cur)
                if m:
                    nm = m.group(0)[:-1].decode('latin1')
                    cur = m.end()
                    tid = 0x10000 + len(s.byid)
                    s.byid[tid] = dict(cls=cls, id=tid, name=nm, data=None)
            struct.pack_into('>I', d, a + 12, tid)
        s.d = bytes(d)
        t = dict(cls=grp, id=0x80000 + len(s.tags), name=name, data=base + 64)
        s.tags.append(t)
        return t
