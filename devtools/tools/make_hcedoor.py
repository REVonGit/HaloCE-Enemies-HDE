import struct
V=[]; L=[]; S=[]; SEC=[]
def v(x,y):
    if (x,y) not in V: V.append((x,y))
    return V.index((x,y))
def side(sec, mid='-', up='-', low='-'):
    S.append(dict(sector=sec, texturemiddle=mid, textureupper=up, texturelower=low)); return len(S)-1
def line(a,b,front,back=None,**kw):
    d=dict(v1=v(*a), v2=v(*b), sidefront=side(front, 'STARTAN2' if back is None else '-', 'BIGDOOR2' if back is not None else '-', 'STEP1' if back is not None else '-'))
    if back is None: d['blocking']=True
    else: d['sideback']=side(back,'-','BIGDOOR2','STEP1'); d['twosided']=True
    d.update(kw); L.append(d)
A,D,B,LF=0,1,2,3
SEC+= [dict(heightfloor=0,heightceiling=256,texturefloor='FLOOR4_8',textureceiling='CEIL3_5',lightlevel=200),
       dict(heightfloor=0,heightceiling=0,texturefloor='FLOOR4_8',textureceiling='CEIL3_5',lightlevel=200),
       dict(heightfloor=0,heightceiling=256,texturefloor='FLOOR4_8',textureceiling='CEIL3_5',lightlevel=200),
       dict(heightfloor=0,heightceiling=256,texturefloor='FLAT20',textureceiling='CEIL3_5',lightlevel=255)]
door=dict(special=12,arg0=0,arg1=16,arg2=150,playeruse=True,monsteruse=True,repeatspecial=True)
# room A, clockwise
line((0,0),(0,1024),A); line((0,1024),(1024,1024),A)
line((1024,1024),(1024,576),A); line((1024,576),(1024,448),A,D,**door); line((1024,448),(1024,0),A); line((1024,0),(0,0),A)
# door sector walls
line((1024,576),(1040,576),D); line((1040,448),(1024,448),D)
# room B
line((1040,0),(1040,448),B); line((1040,448),(1040,576),B,D,**door); line((1040,576),(1040,1024),B)
line((1040,1024),(2064,1024),B); line((2064,1024),(2064,0),B); line((2064,0),(1040,0),B)
# the lift in room A (front: the room)
lift=dict(special=64,arg0=0,arg1=32,arg2=105,arg3=64,playeruse=True,repeatspecial=True)
line((200,700),(328,700),A,LF,**lift); line((328,700),(328,828),A,LF); line((328,828),(200,828),A,LF); line((200,828),(200,700),A,LF)
def blk(name,d):
    s=name+'\n{\n'
    for k,val in d.items():
        if isinstance(val,bool): val='true' if val else 'false'
        elif isinstance(val,str): val='"%s"'%val
        s+=f'{k} = {val};\n'
    return s+'}\n'
t='namespace = "zdoom";\n'
t+=blk('thing',dict(x=300.0,y=512.0,angle=0,type=1,skill1=True,skill2=True,skill3=True,skill4=True,skill5=True,single=True))
for x,y in V: t+=blk('vertex',dict(x=float(x),y=float(y)))
for l in L: t+=blk('linedef',l)
for s in S: t+=blk('sidedef',s)
for s in SEC: t+=blk('sector',s)
lumps=[('MAP33',b''),('TEXTMAP',t.encode()),('ENDMAP',b'')]
data=b''; dirs=b''; off=12
for n,b in lumps:
    dirs+=struct.pack('<ii8s',off,len(b),n.encode()); data+=b; off+=len(b)
open('/home/claude/game/hcedoor.wad','wb').write(b'PWAD'+struct.pack('<ii',len(lumps),12+len(data))+data+dirs)
print(len(V),len(L),len(S))
