import sys, re; sys.path.insert(0,'/tmp/claude-0/x/tools')
from udmf import *
from PIL import Image, ImageDraw
log, picks, out = sys.argv[1], [int(x) for x in sys.argv[2].split(',')], sys.argv[3]
wad = sys.argv[4] if len(sys.argv) > 4 else '/home/claude/game/covertest.wad'
cx, cy, R = (float(x) for x in (sys.argv[5].split(',') if len(sys.argv) > 5 else ('1036','1300','560')))
g=allmaps(wad)[0][1]
V=g['vertex']; Ls=g['linedef']; S=g['sidedef']
pos={}
for l in open(log):
    m=re.match(r'HCEPREV POS t(\d+) (\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\d) (\d) (-?\d+) (-?\d+)', l.strip())
    if m: pos.setdefault(int(m.group(1)),[]).append([int(x) for x in m.groups()[1:]])
W=420; frames=[]
for t in picks:
    if t not in pos: continue
    im=Image.new('RGB',(W,W),'black'); d=ImageDraw.Draw(im)
    P=lambda x,y:((x-cx+R)*W/(2*R), W-(y-cy+R)*W/(2*R))
    for l in Ls:
        a=V[l['v1']]; b=V[l['v2']]
        d.line([P(a['x'],a['y']),P(b['x'],b['y'])],fill=(110,110,110) if 'sideback' in l else (220,220,220))
    for i,x,y,px,py,k,alive,tx,ty in pos[t]:
        q=P(x,y)
        if i==99: d.ellipse([q[0]-5,q[1]-5,q[0]+5,q[1]+5],fill=(80,200,80)); continue
        if i>=4: d.ellipse([q[0]-4,q[1]-4,q[0]+4,q[1]+4],fill=(230,60,60) if alive else (90,30,30)); continue
        d.ellipse([q[0]-4,q[1]-4,q[0]+4,q[1]+4],fill=(80,160,255) if alive else (40,60,90))
        if alive:
            kc={1:(255,255,0),2:(255,160,0),3:(0,255,255)}.get(k,(120,120,120)); pp=P(px,py)
            d.rectangle([pp[0]-3,pp[1]-3,pp[0]+3,pp[1]+3],outline=kc); d.line([q,pp],fill=kc)
    d.text((5,5),f"t{t}",fill='white'); frames.append(im)
o=Image.new('RGB',(W*len(frames),W))
for i,f in enumerate(frames): o.paste(f,(i*W,0))
o.save(out)
