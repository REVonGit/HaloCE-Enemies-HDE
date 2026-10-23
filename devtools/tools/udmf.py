import struct, re, sys
MON = {3004,9,65,3001,3002,58,3005,3003,69,66,67,71,68,64,16,7,84,3006,72,88,89,87}
def lumps(path):
    d=open(path,'rb').read(); n,off=struct.unpack('<ii',d[4:12]); out=[]
    for i in range(n):
        o,s,nm=struct.unpack('<ii8s',d[off+16*i:off+16*i+16]); out.append((nm.rstrip(b'\0').decode(),d[o:o+s]))
    return out
def parse(txt):
    txt=re.sub(r"//[^\n]*","",txt)
    blocks=[]
    for m in re.finditer(r'(\w+)\s*\{([^}]*)\}', txt):
        kv={}
        for k,v in re.findall(r'(\w+)\s*=\s*([^;]+);', m.group(2)):
            v=v.strip()
            if v.startswith('"'): v=v[1:-1]
            elif v in('true','false'): v=v=='true'
            else:
                try: v=float(v) if '.' in v else int(v)
                except: pass
            kv[k]=v
        blocks.append((m.group(1).lower(),kv))
    g={}
    for t,kv in blocks: g.setdefault(t,[]).append(kv)
    return g
def maps(path):
    L=lumps(path); res=[]
    for i,(nm,b) in enumerate(L):
        if nm=='TEXTMAP': res.append((L[i-1][0], parse(b.decode('latin1'))))
    return res

def hexen(L, i):
    """the binary (Hexen-format) map whose marker is lump i -> the same dict shape as parse()"""
    d={n:b for n,b in L[i+1:i+12]}
    V=[dict(x=float(x),y=float(y)) for x,y in struct.iter_unpack('<hh', d['VERTEXES'])]
    hexf='BEHAVIOR' in d
    T=[];Ls=[];S=[];SEC=[]
    if hexf:
        for tid,x,y,z,a,t,fl,sp,*args in struct.iter_unpack('<hhhhhhhB5B', d['THINGS']):
            T.append(dict(x=float(x),y=float(y),type=t,skill3=bool(fl&4),friend=bool(fl&0x2000) if False else False, flags=fl))
        for v1,v2,fl,sp,a0,a1,a2,a3,a4,f,b in struct.iter_unpack('<HHHB5BHH', d['LINEDEFS']):
            l=dict(v1=v1,v2=v2,special=sp,arg0=a0,flags=fl,sidefront=f)
            if b!=0xFFFF: l['sideback']=b
            Ls.append(l)
    else:
        for x,y,a,t,fl in struct.iter_unpack('<hhhhh', d['THINGS']):
            T.append(dict(x=float(x),y=float(y),type=t,skill3=bool(fl&4),flags=fl))
        for v1,v2,fl,sp,tag,f,b in struct.iter_unpack('<HHHHHHH', d['LINEDEFS']):
            l=dict(v1=v1,v2=v2,special=sp,arg0=tag,flags=fl,sidefront=f)
            if b!=0xFFFF: l['sideback']=b
            Ls.append(l)
    for xo,yo,u,lo,m,sec in struct.iter_unpack('<hh8s8s8sH', d['SIDEDEFS']): S.append(dict(sector=sec))
    for fh,ch,ft,ct,light,sp,tag in struct.iter_unpack('<hh8s8shhh', d['SECTORS']): SEC.append(dict(heightfloor=fh,heightceiling=ch,special=sp,id=tag))
    return dict(vertex=V,linedef=Ls,sidedef=S,sector=SEC,thing=T)

def allmaps(path):
    L=lumps(path); res=[]
    for i,(nm,b) in enumerate(L):
        if nm=='TEXTMAP': res.append((L[i-1][0], parse(b.decode('latin1'))))
        elif nm=='THINGS': res.append((L[i-1][0], hexen(L,i-1)))
    return res
