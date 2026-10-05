import struct
BASE=0x803a6000
class HMap:
    def __init__(s,path):
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
    def v2o(s,a): return a-BASE+s.off
    def cstr(s,a):
        o=s.v2o(a);return s.d[o:s.d.index(b'\0',o)].decode('latin1')
    def u(s,fmt,a): return struct.unpack_from('<'+fmt,s.d,s.v2o(a))
    def reflexive(s,a):  # count, ptr, unused
        return struct.unpack_from('<III',s.d,s.v2o(a))[:2]
    def find(s,cls): return [t for t in s.tags if t['cls']==cls]

class BSP:
    def __init__(s,m,ref_addr):
        s.m=m;d=m.d
        s.fo,s.fs,s.ba,_=m.u('IIII',ref_addr)
        s.tid=m.u('I',ref_addr+28)[0]
        s.name=m.byid[s.tid]['name'].split('\\')[-1]
        s.root=struct.unpack_from('<I',d,s.fo)[0]
    def o(s,a): return s.fo+(a-s.ba)
    def u(s,fmt,a): return struct.unpack_from('<'+fmt,s.m.d,s.o(a))
    def blk(s,a): return s.u('II',a)
    def arr(s,fmt,a,size):
        c,p=s.blk(a)
        return [struct.unpack_from('<'+fmt,s.m.d,s.o(p)+i*size) for i in range(c)]
    def collision(s):
        c,p=s.blk(s.root+0xB0)
        assert c>=1
        cb=p
        planes=s.arr('4f',cb+0x0C,16)
        surfs=s.arr('iiBBh',cb+0x3C,12)
        edges=s.arr('6i',cb+0x48,24)
        verts=s.arr('3fi',cb+0x54,16)
        return planes,surfs,edges,verts
    def coll_polys(s):
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
    def __init__(s,b):
        c,p=b.blk(b.root+0xB0); cb=p
        s.nodes=b.arr('3i',cb+0x00,12)
        s.planes=b.arr('4f',cb+0x0C,16)
        s.leaves=b.arr('hhi',cb+0x18,8)
        s.surfs=b.arr('iiBBh',cb+0x3C,12)
        s.edges=b.arr('6i',cb+0x48,24)
        s.verts=b.arr('3fi',cb+0x54,16)
    def classify(s,x,y,z):
        n=0 if s.nodes else -1
        while n>=0:
            pl,back,front=s.nodes[n]
            a,b_,c,d=s.planes[pl&0x7fffffff]
            n=front if a*x+b_*y+c*z-d>=0 else back
        return n  # negative: leaf (n&0x7fffffff) or -1

def tagrefs(m, addr, size, cls=b'mtib'):
    """scan struct bytes for tag references of a class -> list of (offset, tag id)"""
    o = m.v2o(addr); d = m.d; out = []
    for k in range(0, size - 15, 4):
        if d[o+k:o+k+4] == cls:
            tid = struct.unpack_from('<I', d, o+k+12)[0]
            if tid in m.byid: out.append((k, tid))
    return out
