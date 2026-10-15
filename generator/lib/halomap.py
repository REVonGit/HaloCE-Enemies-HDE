"""Halo CE Xbox cache file (.map) reader: the tag index, tag-address translation, and the BSP collision tree.

An Xbox map is loaded whole into memory at BASE, so every pointer stored in it is a virtual address; v2o() turns
one into a file offset (addr - BASE + tag-data file offset). The tag index gives each tag's class (4 chars, stored
reversed), id, path name and the virtual address of its main struct; tags.py layers decomp struct layouts over that.
Not a script: imported by tags.py, halomodel.py, bitmaps.py, render.py and the extractors. For PC / MCC caches use
pcmap.PCMap, which has the same interface with a different BASE and index header."""
import struct
BASE=0x803a6000   # virtual address the Xbox cache's tag data is mapped at (the PC base is 0x50000000, see pcmap.py)
class HMap:
    """An opened Xbox cache file: d (bytes), off (file offset of the tag index header), name (scenario name),
    scen_id, count, tags (list of dict(cls, id, name, data=virtual address, ext)) and byid (tag id -> that dict)."""
    def __init__(s,path):
        """Read the whole file and build the tag index from the 32-byte entries at the header's tag-array pointer."""
        s.d=d=open(path,'rb').read()
        s.off,_=struct.unpack_from('<II',d,0x10)
        s.name=d[0x20:0x40].split(b'\0')[0].decode()
        ptr,s.scen_id,_,s.count=struct.unpack_from('<4I',d,s.off)
        s.tags=[];s.byid={}
        p=s.v2o(ptr)
        for i in range(s.count):
            c0,c1,c2,tid,nptr,dptr,ext,_=struct.unpack_from('<4sIIIIIII',d,p+i*32)[:8] if False else struct.unpack_from('<4s3s',b'',0) if False else (None,)*8
            c0=d[p+i*32:p+i*32+4][::-1].decode('latin1')
            tid,nptr,dptr,ext=struct.unpack_from('<IIII',d,p+i*32+12)
            t=dict(cls=c0,id=tid,name=s.cstr(nptr),data=dptr,ext=ext)
            s.tags.append(t);s.byid[tid]=t
    # virtual address -> file offset
    def v2o(s,a): return a-BASE+s.off
    def cstr(s,a):
        """NUL-terminated string at virtual address a."""
        o=s.v2o(a);return s.d[o:s.d.index(b'\0',o)].decode('latin1')
    # little-endian struct.unpack of fmt at virtual address a (returns the tuple)
    def u(s,fmt,a): return struct.unpack_from('<'+fmt,s.d,s.v2o(a))
    def reflexive(s,a):  # count, ptr, unused
        """A tag_block at virtual address a -> (element count, virtual address of the first element)."""
        return struct.unpack_from('<III',s.d,s.v2o(a))[:2]
    # all tags of a 4-char class, e.g. find('bipd')
    def find(s,cls): return [t for t in s.tags if t['cls']==cls]

class BSP:
    """One structure BSP as the scenario's structure_bsps block entry at ref_addr lists it. BSP data is a separate
    file region mapped at its own base: fo (file offset), fs (size), ba (virtual base); o() translates. root is the
    virtual address of the structure_bsp struct; name is the tag path's last component."""
    def __init__(s,m,ref_addr):
        """m: HMap; ref_addr: virtual address of a 32-byte scenario structure_bsp reference."""
        s.m=m;d=m.d
        s.fo,s.fs,s.ba,_=m.u('IIII',ref_addr)
        s.tid=m.u('I',ref_addr+28)[0]
        s.name=m.byid[s.tid]['name'].split('\\')[-1]
        s.root=struct.unpack_from('<I',d,s.fo)[0]
    # BSP-region virtual address -> file offset
    def o(s,a): return s.fo+(a-s.ba)
    # little-endian struct.unpack of fmt at BSP virtual address a
    def u(s,fmt,a): return struct.unpack_from('<'+fmt,s.m.d,s.o(a))
    # tag_block at a -> (count, first element address)
    def blk(s,a): return s.u('II',a)
    def arr(s,fmt,a,size):
        """Unpack every element of the tag_block at a: fmt per element, size = element stride in bytes."""
        c,p=s.blk(a)
        return [struct.unpack_from('<'+fmt,s.m.d,s.o(p)+i*size) for i in range(c)]
    def collision(s):
        """Raw collision BSP arrays of the first collision_bsp (structure_bsp + 0xB0): planes (a, b, c, d: a*x+b*y+c*z = d),
        surfs (plane index | 0x80000000 when flipped, first edge, flags, breakable surface, material), edges (v0, v1,
        forward edge, reverse edge, left surface, right surface) and verts (x, y, z, first edge), in Halo world units."""
        c,p=s.blk(s.root+0xB0)
        assert c>=1
        cb=p
        planes=s.arr('4f',cb+0x0C,16)
        surfs=s.arr('iiBBh',cb+0x3C,12)
        edges=s.arr('6i',cb+0x48,24)
        verts=s.arr('3fi',cb+0x54,16)
        return planes,surfs,edges,verts
    def coll_polys(s):
        """Collision surfaces as polygons: list of dict(v=[(x, y, z) ...] walked around the surface's edge loop,
        plane=(a, b, c, d), flip=plane faces the other way, flags, mat=material index). The loop walk is capped at 64
        edges so a corrupt surface can't hang it."""
        planes,surfs,edges,verts=s.collision()
        polys=[]
        for si,(pl,fe,fl,br,mat) in enumerate(surfs):
            vi=[];e=fe;guard=0
            while True:
                v0,v1,f,r,ls,rs=edges[e]
                if ls==si: vi.append(v0);e=f
                else: vi.append(v1);e=r
                guard+=1
                if e==fe or guard>64: break
            pi=pl&0x7fffffff; flip=pl<0
            polys.append(dict(v=[verts[i][:3] for i in vi],plane=planes[pi],flip=flip,flags=fl,mat=mat))
        return polys

class Coll:
    """The collision BSP tree of a BSP, for point queries: nodes (plane index, back child, front child), planes,
    leaves (flags, bsp2d reference count, first bsp2d reference), surfs, edges, verts as in BSP.collision()."""
    def __init__(s,b):
        """b: a BSP."""
        c,p=b.blk(b.root+0xB0); cb=p
        s.nodes=b.arr('3i',cb+0x00,12)
        s.planes=b.arr('4f',cb+0x0C,16)
        s.leaves=b.arr('hhi',cb+0x18,8)
        s.surfs=b.arr('iiBBh',cb+0x3C,12)
        s.edges=b.arr('6i',cb+0x48,24)
        s.verts=b.arr('3fi',cb+0x54,16)
    def classify(s,x,y,z):
        """Descend the tree from the root for a world-space point: child indices with the top bit set are leaves.
        Returns the final child value: negative, so the leaf index is n & 0x7fffffff; -1 means outside (solid) or
        an empty tree."""
        n=0 if s.nodes else -1
        while n>=0:
            pl,back,front=s.nodes[n]
            a,b_,c,d=s.planes[pl&0x7fffffff]
            n=front if a*x+b_*y+c*z-d>=0 else back
        return n  # negative: leaf (n&0x7fffffff) or -1

# cls is the class as stored in the file (reversed): b'mtib' = bitmap. Each 16-byte tag_reference is class, name
# pointer, name length, tag id; only ids present in the index count, so random bytes rarely match.
def tagrefs(m, addr, size, cls=b'mtib'):
    """scan struct bytes for tag references of a class -> list of (offset, tag id)"""
    o = m.v2o(addr); d = m.d; out = []
    for k in range(0, size - 15, 4):
        if d[o+k:o+k+4] == cls:
            tid = struct.unpack_from('<I', d, o+k+12)[0]
            if tid in m.byid: out.append((k, tid))
    return out
