#!/usr/bin/env python3
"""sweep.py: every enemy class in the engine, six at a time, on contact sheets -- and the ones that look wrong.

    python3 sweep.py                    # the HDE set with the Digsite add-on (--packs sa: the Standalone set)
    python3 sweep.py --only Sentinel    # classes whose name contains this

One game run: batches of six spawn in a row as display dummies, each held two seconds for its screenshot, then cleared.
Out of each shot, against an empty shot of the arena, every spawn's own column of the picture is measured; a class is
flagged when it failed to spawn, raised an engine error, or changed almost nothing in its column (no model drawn, a
fully hidden skin), or when most of what it drew is one flat colour (a missing texture). Sheets, each batch's full-size shot
(batch_NN.png) and the report land in shots/sweep/ (index.txt lists the flags).
"""
import argparse, math, os, re, shutil, sys, zipfile
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene

PER = 6; SPACING = 76; DEPTH = 470; HOLD = 70
OUT = os.path.join(scene.OUTDIR, 'sweep')


def classes(packs):
    cls = set()
    for p in scene.PACKS[packs]:
        with zipfile.ZipFile(f'{scene.G}/{p}') as z:
            for n in z.namelist():
                if os.path.basename(n).lower().startswith('mapinfo'):
                    for blk in re.findall(r'DoomEdNums\s*\{(.*?)\}', z.read(n).decode('utf8', 'replace'), re.S | re.I):
                        cls |= set(re.findall(r'=\s*"?(\w+)', blk))
    return sorted(c for c in cls if c.startswith('HCE_') and not c.startswith(('HCE_Random', 'HCE_Variant')))   # (HCE_Variant<n>: empty HCEVARS slots)


def zs_for(batches, base):
    arr = ', '.join(f'"{",".join(b)}"' for b in batches)
    return f'''		static const String B[] = {{ {arr} }};
		if(t > 20 && t % 5 == 0)                                    // only the row: the map's own (replaced) things go
		{{
			ThinkerIterator ei = ThinkerIterator.Create("{base}"); Actor x;
			while(x = Actor(ei.Next()))
			{{
				bool mine = false;
				for(int j = 0; j < row.Size(); j++) if(row[j] == x) mine = true;
				if(!mine && x.GetAge() > 5) {{ x.Destroy(); }}
			}}
		}}
		int k = (t - 120) / {HOLD};
		if(t >= 120 && (t - 120) % {HOLD} == 0)
		{{
			for(int i = 0; i < row.Size(); i++) if(row[i]) row[i].Destroy();
			row.Clear();
			ThinkerIterator it = ThinkerIterator.Create("Actor"); Actor a;
			while(a = Actor(it.Next())) if(a.bMISSILE || (a is "Inventory" && !Inventory(a).owner && a.bDROPPED) || a.GetClassName() == 'WeaponPickupProxy') a.Destroy();
			if(k >= 1 && k <= B.Size())
			{{
				Array<String> cs; B[k - 1].Split(cs, ",");
				// each its own width apart (a wide Sentinel crowding the next keeps it from hovering)
				Array<double> xs; double w = 0;
				for(int i = 0; i < cs.Size(); i++)
				{{
					Name nm = cs[i]; class<Actor> c = nm;
					double r = c ? max(16, GetDefaultByType(c).radius) : 16;
					xs.Push(w + r + 6); w += r * 2 + 12;
				}}
				for(int i = 0; i < cs.Size(); i++)
				{{
					Name nm = cs[i]; class<Actor> c = nm;
					double px = 1036 - w / 2 + xs[i];
					Console.Printf("HCEPREV at %d %s %.0f", k, cs[i], px - 1036);
					let s = c ? Actor.Spawn(c, (px, 590 + {DEPTH}, 0)) : null;
					if(!s) {{ Console.Printf("HCEPREV FAILED %s", cs[i]); row.Push(null); continue; }}
					s.angle = 270; row.Push(s); Console.Printf("HCEPREV spawned %s", cs[i]);
					let e = {base}(s); if(e) e.hce_dummy = true;
				}}
			}}
		}}
		if(t >= 120 && (t - 120) % {HOLD} == {HOLD - 20} && k <= B.Size()) Console.Printf("HCEPREV shot %d", k + 1);
		if(t == 120 + {HOLD} * (B.Size() + 1)) Console.Printf("HCEPREV done");
'''


def columns(offs, w):
    """each spawn's column of the picture (left, right in pixels), from its offset across the row (map units)"""
    hfov = 2 * math.atan(math.tan(math.radians(25)) * (16 / 10) / (4 / 3))
    f = (w / 2) / math.tan(hfov / 2)
    out = []
    for dx in offs:
        cx = w / 2 + dx / DEPTH * f
        half = SPACING / 2 / DEPTH * f
        out.append((int(cx - half), int(cx + half)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--packs', default='bundle', choices=sorted(scene.PACKS)); ap.add_argument('--only', default='')
    a0 = ap.parse_args()
    cl = [c for c in classes(a0.packs) if a0.only.lower() in c.lower()]
    batches = [cl[i:i + PER] for i in range(0, len(cl), PER)]
    print(f'{len(cl)} classes, {len(batches)} batches')
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    base = 'HCES_EnemyBase' if a0.packs == 'sa' else 'HaloDoom_EnemyBase'
    zf = os.path.join(OUT, 'sweep.zs'); open(zf, 'w').write(zs_for(batches, base))
    a = argparse.Namespace(packs=a0.packs, spawn='', spacing=SPACING, z=0, dummy=True, free=False, fight=0, mortal=False, close=0,
                           camera='1036,590,0', pitch=0, shots='', duration=10 ** 6, log_damage=False, log_every=0, zs=zf, zs_top='',
                           name='sweep/s', retries=0, res='1280x800', voices=False, timeout=60 + len(batches) * 4)
    a.res_w, a.res_h = 1280, 800
    for attempt in range(3):                              # the first frames under Xvfb come out black now and then
        lines, errors, shots, black, _ = scene.run(a, 0)
        if shots and np.asarray(Image.open(shots[0]).convert('RGB')).mean() >= 3: break
        print(f'(attempt {attempt + 1}: a black start; again)')
    failed = {l.split()[-1] for l in lines if 'FAILED' in l}
    offs = {}
    for l in lines:
        m = re.match(r'HCEPREV at (\d+) (\w+) (-?\d+)', l)
        if m: offs[m.group(2)] = float(m.group(3))
    if os.environ.get('SWEEP_DEBUG'): print('\n'.join(lines[:40]), errors[:5])
    flags = [f'{c}: did not spawn' for c in sorted(failed)] + [f'engine: {e}' for e in errors[:20]]
    if not shots: print('no shots'); sys.exit(1)
    bg = np.asarray(Image.open(shots[0]).convert('RGB')).astype(np.float32)
    if bg.mean() < 3: print('the empty arena shot came out black: run again'); sys.exit(1)
    H, W = bg.shape[:2]
    tiles = []
    for k, b in enumerate(batches):
        if k + 1 >= len(shots): flags.append(f'batch {k + 1}: no shot'); continue
        im = Image.open(shots[k + 1]).convert('RGB'); a1 = np.asarray(im).astype(np.float32)
        if a1.mean() < 3: flags.append(f'batch {k + 1} ({b[0]}...): black shot, not checked'); tiles.append(im.resize((W // 2, H // 2))); continue
        d = np.abs(a1 - bg).sum(2) > 40
        d[:int(H * 0.25)] = False                         # the console lines and the HUD at the top
        d[int(H * 0.68):, :int(W * 0.2)] = False          # the motion tracker
        for c, (l, r) in zip(b, columns([offs.get(c, 0) for c in b], W)):
            l, r = max(0, l), min(W, r)
            m = d[:, l:r]
            cover = m.mean()
            if c in failed: continue
            if cover < 0.004: flags.append(f'{c}: nothing drawn ({cover:.4f} of its column changed)'); continue
            px = a1[:, l:r][m]
            q = np.round(px / 8)
            _, cnt = np.unique(q, axis=0, return_counts=True)
            if cnt.max() / len(px) > 0.6 and len(px) > 400:
                flags.append(f'{c}: mostly one flat colour ({cnt.max() / len(px):.0%}): a missing texture?')
        dr = ImageDraw.Draw(im)
        for c, (l, r) in zip(b, columns([offs.get(c, 0) for c in b], W)):
            dr.text((max(2, l + 2), int(H * 0.9)), c[4:][:22], fill=(255, 230, 120))
        tiles.append(im.resize((W // 2, H // 2)))
    for s in range(0, len(tiles), 6):
        sheet = Image.new('RGB', (W, H * 3 // 2))
        for i, t in enumerate(tiles[s:s + 6]): sheet.paste(t, ((i % 2) * W // 2, (i // 2) * H // 2))
        sheet.save(os.path.join(OUT, f'sheet_{s // 6 + 1:02d}.png'))
    for k, p in enumerate(shots[1:]): shutil.move(p, os.path.join(OUT, f'batch_{k + 1:02d}.png'))   # full size, for a closer look
    os.remove(shots[0])
    open(os.path.join(OUT, 'index.txt'), 'w').write('\n'.join(flags) + '\n')
    print(f'{len(flags)} flags; sheets in {OUT}')
    for f in flags: print(' ', f)


if __name__ == '__main__':
    main()
