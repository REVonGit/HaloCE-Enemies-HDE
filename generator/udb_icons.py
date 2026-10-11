"""Thing icons for Ultimate Doom Builder: a picture of every placeable enemy, taken in the engine -> $HCE_OUT/udb_icons

    python3 udb_icons.py          # after the packs are built (build_addons.sh); needs UZDoom, Xvfb and ImageMagick

Every class with a DoomEdNum (the faction packs' and the Digsite add-on's MAPINFO) is spawned in turn in the test
map's annex (tests/make_covertest.py), three-quarters on to the camera, and photographed from a little above. The
annex is painted one flat magenta at full light for the shoot, which is keyed out, leaving the enemy on a transparent
background. The pictures are cropped, fitted
into ICON pixels and written as <class>.png with an index (icons.json). build_pack.py / split_factions.py ship them as
sprites (HUxxA0) and name them in each class's //$Sprite editor key, so the enemies show in the editor's thing
browser and on the map. Random spawners have no picture of their own (they borrow their first pick's).

Environment: HCE_UZDOOM (the engine), HCE_IWAD (doom2.wad), HCE_HDE_PK3 (HaloDoom Evolved), HCE_GAME (the built packs),
HCE_COVERTEST (covertest.wad).
"""
import os, re, sys, json, time, shutil, subprocess, tempfile
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'lib'))   # readers and writers live in lib/
try:
    from extract_chars import OUT
except Exception:
    OUT = os.path.join(HERE, 'out')
GAME = os.environ.get('HCE_GAME', os.path.join(HERE, 'game'))
UZDOOM = os.environ.get('HCE_UZDOOM', 'uzdoom')
IWAD = os.environ.get('HCE_IWAD', f'{GAME}/doom2.wad')
HDE = os.environ.get('HCE_HDE_PK3', f'{GAME}/HDE_dev_lite.pk3')
COVERTEST = os.environ.get('HCE_COVERTEST', f'{GAME}/covertest.wad')
PACKS = ['HCE_EnemyAPI_LocalDEV.pk3', 'HaloCE_Core.pk3', 'HaloCE_Covenant.pk3', 'HaloCE_Flood.pk3', 'HaloCE_Sentinels.pk3',
         'HaloCE_Marines.pk3', 'HaloCE_Enemies_Digsite.pk3']
ICON = 80              # the icon's longest side (pixels)
HOLD = 44              # tics each enemy stands before the camera (photographed 14 tics in, well before the next)
KEY_RGB = (255, 0, 255)   # the booth's colour: anything near it in a photo is background

HARNESS = r'''version "4.15.1"
class HCE_IconShoot : EventHandler
{
	static const String CLS[] = { %s };
	Actor cur;
	// the annex painted one flat key colour at full light (walls, floor, ceiling): everything else in a photo is the enemy
	void PaintBooth(Sector sec)
	{
		TextureID key = TexMan.CheckForTexture("HCEKEY", TexMan.Type_Any);
		sec.SetTexture(Sector.floor, key); sec.SetTexture(Sector.ceiling, key);
		sec.SetLightLevel(255);
		for(int i = 0; i < level.lines.Size(); i++)
		{
			Line l = level.lines[i];
			for(int s = 0; s < 2; s++)
			{
				Side sd = l.sidedef[s];
				if(!sd || sd.sector != sec) continue;
				sd.SetTexture(Side.top, key); sd.SetTexture(Side.mid, key); sd.SetTexture(Side.bottom, key);
			}
		}
	}
	override void WorldTick()
	{
		let pl = players[0].mo; if(!pl) return;
		int t = level.maptime;
		if(t == 2) { pl.angle = 90; pl.bNOGRAVITY = true; }
		if(t == 4) PaintBooth(pl.CurSector);                    // (moved into the annex on tic 2)
		// the camera level with the enemy's middle, looking a little down at it from far enough to frame it whole
		double camz = cur ? max(0, cur.height * 0.62 - pl.player.viewheight) : 0;
		if(t >= 2) { pl.SetOrigin((2340, 930, camz), false); pl.vel = (0, 0, 0); pl.pitch = 6; }
		int k = (t - 45) / %d, ph = (t - 45) %% %d;
		if(t < 45 || k >= CLS.Size() + 1) return;
		if(ph == 0)
		{
			if(cur) cur.Destroy();
			if(k == CLS.Size()) { Console.PrintfEx(PRINT_NONOTIFY, "HCEICON done"); return; }
			class<Actor> c = CLS[k];
			if(!c) { Console.PrintfEx(PRINT_NONOTIFY, "HCEICON missing %%d", k); return; }
			let d = GetDefaultByType(c);
			double dist = max(150, d.height * 2.1 + d.radius);
			cur = Actor.Spawn(c, (2340, 930 + dist, 0), NO_REPLACE);
			if(cur) { cur.angle = 240; cur.bFRIENDLY = false; }      // (not a squad Marine: no name tag over him)
		}
		if(cur) { cur.vel.xy = (0, 0); cur.angle = 240; cur.SetOrigin((2340, cur.pos.y, cur.floorz), true); cur.A_SetRenderStyle(1, STYLE_Normal); }   // cloaked ones shown uncloaked
		if(ph == %d && cur) Console.PrintfEx(PRINT_NONOTIFY, "HCEICON shot %%d", k);
	}
}
'''


def placeable():
    """[(DoomEdNum, class)] from the built packs' MAPINFO"""
    out = []
    for p in PACKS:
        path = f'{GAME}/{p}'
        if not os.path.exists(path): continue
        r = subprocess.run(['unzip', '-p', path, 'mapinfo.txt'], capture_output=True, text=True)
        out += [(int(n), c) for n, c in re.findall(r'^\s*(\d+)\s*=\s*(\w+)', r.stdout, re.M)]
    return sorted(set(out))


def shoot(classes, tmp):
    """photograph these classes in one game run -> {class: photo path}"""
    if os.path.exists(f'{tmp}/h'): shutil.rmtree(f'{tmp}/h')
    os.makedirs(f'{tmp}/h/textures')
    open(f'{tmp}/h/zscript.txt', 'w').write(HARNESS % (', '.join(f'"{c}"' for c in classes), HOLD, HOLD, 14))
    open(f'{tmp}/h/mapinfo.txt', 'w').write('GameInfo { AddEventHandlers = "HCE_IconShoot" }\n')
    Image.new('RGB', (64, 64), KEY_RGB).save(f'{tmp}/h/textures/HCEKEY.png')
    if os.path.exists(f'{tmp}/h.pk3'): os.remove(f'{tmp}/h.pk3')
    subprocess.run(['zip', '-qr', f'{tmp}/h.pk3', '.'], cwd=f'{tmp}/h', check=True)
    disp = ':71'
    xv = subprocess.Popen(['Xvfb', disp, '-screen', '0', '640x480x24'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    env = dict(os.environ, DISPLAY=disp)
    files = [HDE] + [f'{GAME}/{p}' for p in PACKS if os.path.exists(f'{GAME}/{p}')] + [COVERTEST, f'{tmp}/h.pk3']
    log = open(f'{tmp}/log.txt', 'w')
    game = subprocess.Popen(['stdbuf', '-oL', '-eL', UZDOOM, '-iwad', IWAD, '-nosound', '-skill', '3', '-file'] + files +
                            ['-width', '640', '-height', '400', '+vid_fullscreen', '0', '+sv_cheats', '1', '+map', 'COVERTST',
                             '+god', '+notarget', '+r_drawplayersprites', '0', '+screenblocks', '12', '+crosshair', '0',
                             '+hce_cover', '0', '+hce_patrols', '0', '+hce_hunterpairs', '0', '+hce_simpleshaders', '1'], stdout=log, stderr=subprocess.STDOUT, env=env)
    shots, seen = {}, set()
    t0 = time.time()
    try:
        while time.time() - t0 < 60 + len(classes) * 3:
            time.sleep(0.03)
            if game.poll() is not None: break
            for line in open(f'{tmp}/log.txt', errors='replace'):
                m = re.match(r'HCEICON (shot (\d+)|done)', line)
                if not m or line in seen: continue
                seen.add(line)
                if m.group(1) == 'done': raise StopIteration
                fn = f'{tmp}/{classes[int(m.group(2))]}.png'
                subprocess.run(['import', '-window', 'root', fn], env=env, check=False)
                shots[classes[int(m.group(2))]] = fn
    except StopIteration:
        pass
    finally:
        game.kill(); xv.kill(); game.wait(); xv.wait()
    return shots


def cut_out(fn):
    """a booth photo -> the enemy alone (RGBA, fitted into ICON), or None for a failed photo"""
    A = np.asarray(Image.open(fn).convert('RGB'), np.int32)
    if A.mean() < 8: return None                                # a black frame (the screenshot came too early)
    r, g, b = A[..., 0], A[..., 1], A[..., 2]
    bgk = (r > 150) & (b > 150) & (g < 110) & (np.abs(r - b) < 70)     # the booth, lit or tinted a little by the enemy's lights
    if bgk.mean() < 0.3: return None                             # not the booth
    mask = ~bgk
    mask[:6] = False; mask[-6:] = False                          # the window's edges
    ys, xs = np.nonzero(mask)
    if len(xs) < 50: return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    im = Image.fromarray(np.dstack([A, mask * 255]).astype(np.uint8)[y0:y1, x0:x1], 'RGBA')
    im.thumbnail((ICON, ICON), Image.LANCZOS)
    return im


def main():
    classes = [c for _, c in placeable() if not c.startswith('HCE_Random')]
    od = f'{OUT}/udb_icons'
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    tmp = tempfile.mkdtemp()
    index, todo = {}, list(classes)
    for attempt in range(3):                                     # the photos that failed, again
        if not todo: break
        for c, fn in shoot(todo, tmp).items():
            im = cut_out(fn)
            if im is None: continue
            im.save(f'{od}/{c}.png'); index[c] = f'{c}.png'
        todo = [c for c in classes if c not in index]
        if todo: print(f'  pass {attempt + 1}: {len(todo)} to take again')
    json.dump(dict(sorted(index.items())), open(f'{od}/icons.json', 'w'), indent=1)
    print(len(index), 'of', len(classes), 'icons ->', od, ('(none of ' + ', '.join(todo) + ')') if todo else '')
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
