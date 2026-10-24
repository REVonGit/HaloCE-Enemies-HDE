#!/usr/bin/env python3
"""scene.py: look at enemies in the engine, in one command.

    python3 scene.py --spawn HCE_SentinelEnforcer,HCE_Sentinel --shots 50,120 --fight 60 --log-damage
    python3 scene.py --packs sa --spawn HCE_JackalSniperBeamRifle --close 1 --shots 40

Spawns the classes in a row on COVERTST (a flat arena in covertest.wad) facing a camera at a spot known to render,
takes screenshots at the given tics, and prints the HCEPREV log lines. Screenshots come back black now and then (the
first frames under Xvfb): such a run is repeated, up to --retries times.

  --packs hde|sa|bundle   HaloDoom Evolved + the HDE packs (default), the Standalone packs, or HDE + the HDE packs + Digsite
  --spawn A,B,...         classes, left to right (row at y=1010, centred on x=1036, --spacing apart, --z above the floor)
  --dummy                 keep them still (display dummies) for the whole run; otherwise they stand still until --fight
  --free                  left to their own AI from the start (allies fight what you spawn with --zs)
  --fight T               at tic T they wake and fight the player (god mode stays on unless --mortal)
  --mortal                at --fight the player loses god mode and gets 5000 health, so their hits register
  --close K               the camera moves in on spawn K (1-based) for every shot after the first
  --camera x,y,z          camera spot (default 1036,880,0), looking along +y; --pitch P (positive: down)
  --shots T,T,...         screenshot tics (each capture takes a moment: shots a few tics apart land late; for a quick
                          effect run one shot per run); --duration T ends the run (default: 30 after the last shot)
  --log-damage            log every hit on the player and on the spawns (amount, source, damage type)
  --log-every T           every T tics log each spawn's health, distance to the player and target
  --res WxH               render size (default 960x600)
  --voices                print every line spoken (HCEVOICE t<tic> <class> <event>)
  --zs-top FILE           extra top-level ZScript (classes to --spawn: a subclass that forces a look, say)
  --zs FILE               extra ZScript lines inside the handler's WorldTick (t is the tic, pl the player, row the spawns)
  --nopin                 the player is not held at the camera spot (a --zs-top handler may walk him)
Images land in /home/claude/devtools/shots/<name>_<n>.png (--name, default 'scene').
"""
import argparse, os, re, shutil, subprocess, sys, tempfile, time, zipfile
import numpy as np
from PIL import Image

G = '/home/claude/game'
U = os.environ.get('HCE_UZDOOM', '/home/claude/build/uzb/uzdoom')
OUTDIR = '/home/claude/devtools/shots'
PACKS = {'hde': ['HDE_dev_lite.pk3', 'HCE_EnemyAPI_LocalDEV.pk3', 'HaloCE_Core.pk3', 'HaloCE_Covenant.pk3', 'HaloCE_Flood.pk3',
                 'HaloCE_Sentinels.pk3', 'HaloCE_Marines.pk3'],
         'bundle': ['HDE_dev_lite.pk3', 'HCE_EnemyAPI_LocalDEV.pk3', 'HaloCE_Core.pk3', 'HaloCE_Covenant.pk3',
                    'HaloCE_Enemies_Digsite.pk3', 'HaloCE_Flood.pk3', 'HaloCE_Sentinels.pk3', 'HaloCE_Marines.pk3'],
         'sa': ['HaloCE_Standalone_Core.pk3', 'HaloCE_Standalone_Covenant.pk3', 'HaloCE_Standalone_Digsite.pk3',
                'HaloCE_Standalone_Flood.pk3', 'HaloCE_Standalone_Sentinels.pk3', 'HaloCE_Standalone_Marines.pk3']}


def zscript(a, base):
    cls = [c for c in a.spawn.split(',') if c]
    shots = [int(x) for x in a.shots.split(',') if x] if a.shots else []
    dur = a.duration or (max(shots) + 30 if shots else 200)
    cx, cy, cz = (float(v) for v in a.camera.split(','))
    n = len(cls); x0 = 1036 - (n - 1) * a.spacing / 2
    spawn = '\n'.join(
        f'\t\t\t{{ Name nm = "{c}"; class<Actor> c = nm; let s = c ? Actor.Spawn(c, ({x0 + i * a.spacing:.0f}, 1010, {a.z:.0f})) : null;'
        f' if(!s) Console.Printf("HCEPREV FAILED {c}"); else {{ s.angle = 270; row.Push(s); let e = {base}(s); if(e) e.hce_dummy = {"false" if a.free else "true"};'
        f' Console.Printf("HCEPREV spawned %s health %d radius %.0f height %.0f", s.GetClassName(), s.health, s.radius, s.height); }} }}'
        for i, c in enumerate(cls))
    close = ''
    if a.close:
        k = a.close - 1
        close = (f'\t\tif(t > {shots[0] if shots else 0} && {k} < row.Size() && row[{k}]) {{ let s = row[{k}]; '
                 f'pl.SetOrigin((s.pos.x, s.pos.y - max(90, s.radius * 3.5), 0), false); pl.angle = 90; }}\n')
    fight = ''
    if a.fight:
        fight = (f'\t\tif(t == {a.fight}) {{ players[0].cheats &= ~CF_NOTARGET;'
                 + (' players[0].cheats &= ~CF_GODMODE; pl.A_SetHealth(5000);' if a.mortal else '')
                 + f' for(int i = 0; i < row.Size(); i++) if(row[i]) {{ let e = {base}(row[i]); if(e) e.hce_dummy = false; row[i].target = pl; }} }}\n')
    hold = f't < {a.fight}' if a.fight and not a.dummy else ('true' if a.dummy else ('t < 8' if a.free else f't < {dur}'))
    every = ''
    if a.log_every:
        every = (f'\t\tif(t > 5 && t % {a.log_every} == 0) for(int i = 0; i < row.Size(); i++) if(row[i]) '
                 f'Console.Printf("HCEPREV t%d %s health %d dist %.0f target %s", t, row[i].GetClassName(), row[i].health, '
                 f'row[i].Distance3D(pl), row[i].target ? row[i].target.GetClassName() : \'none\');\n')
    extra = open(a.zs).read() if a.zs else ''
    top = open(a.zs_top).read() if a.zs_top else ''
    dmg = ''
    if a.log_damage:
        dmg = ('\toverride void WorldThingDamaged(WorldEvent e)\n\t{\n\t\tif(!e.thing) return;\n'
               '\t\tif(e.thing.player || row.Find(e.thing) < row.Size() || nds.Find(e.thing) < nds.Size())\n'
               '\t\t\tConsole.Printf("HCEPREV t%d %s hit %d by %s (%s) health %d", level.maptime, e.thing.GetClassName(), e.Damage,'
               ' e.DamageSource ? e.DamageSource.GetClassName() : \'none\', e.DamageType, e.thing.health);\n\t}\n')
    shot_lines = ''.join(f'\t\tif(t == {s}) Console.Printf("HCEPREV shot {i + 1}");\n' for i, s in enumerate(shots))
    return f'''version "4.15.1"
class HCE_SceneTest : EventHandler
{{
	Array<Actor> row; Array<Actor> nds;
	override void WorldTick()
	{{
		let pl = players[0].mo; if(!pl) return;
		int t = level.maptime;
		if(t == 5)
		{{
			players[0].cheats |= CF_NOTARGET | CF_GODMODE;
{spawn}
		}}
		if(t >= 5 && {'false' if a.nopin else 'true'}) {{ pl.SetOrigin(({cx:.0f}, {cy:.0f}, {cz:.0f}), false); pl.angle = 90; pl.pitch = {a.pitch}; }}
{close}		for(int i = 0; i < row.Size(); i++) if(row[i] && {hold}) row[i].angle = 270;
{fight}{every}{extra}{shot_lines}		if(t == {dur}) Console.Printf("HCEPREV done");
	}}
{dmg}}}
{top}''', len(shots), dur


def run(a, attempt):
    base = 'HCES_EnemyBase' if a.packs == 'sa' else 'HaloDoom_EnemyBase'
    zs, nshots, dur = zscript(a, base)
    work = tempfile.mkdtemp(prefix='scene_')
    pk3 = f'{work}/scene.pk3'
    # a --zs-top subclass (class X : Parent) is drawn with its parent's MODELDEF block
    md = ''
    subs = re.findall(r'class\s+(\w+)\s*:\s*(\w+)', open(a.zs_top).read()) if a.zs_top else []
    if subs:
        blocks = {}
        for p in PACKS[a.packs]:
            with zipfile.ZipFile(f'{G}/{p}') as zz:
                for n in zz.namelist():
                    if os.path.basename(n).lower().startswith('modeldef'):
                        for m in re.finditer(r'(?ms)^Model\s+(\w+)\s*\n\{.*?^\}', zz.read(n).decode('utf-8', 'replace')):
                            blocks[m.group(1).lower()] = m.group(0)
        for child, parent in subs:
            b = blocks.get(parent.lower())
            if b: md += re.sub(r'^Model\s+\w+', f'Model {child}', b, count=1) + '\n'
    with zipfile.ZipFile(pk3, 'w') as z:
        z.writestr('zscript.txt', zs)
        if md: z.writestr('modeldef.scene', md)
        # a --zs-top EventHandler subclass is registered too
        handlers = ['HCE_SceneTest'] + re.findall(r'class\s+(\w+)\s*:\s*(?:Static)?EventHandler', open(a.zs_top).read() if a.zs_top else '')
        z.writestr('mapinfo.txt', 'GameInfo { AddEventHandlers = "%s" }\n' % '", "'.join(handlers))
    disp = str(90 + os.getpid() % 9)
    for f in (f'/tmp/.X{disp}-lock', f'/tmp/.X11-unix/X{disp}'):
        if os.path.exists(f): os.remove(f)
    xv = subprocess.Popen(['Xvfb', f':{disp}', '-screen', '0', f'{a.res_w}x{a.res_h}x24'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    files = [f'{G}/{p}' for p in PACKS[a.packs]] + [a.wad if os.path.isabs(a.wad) else f'{G}/{a.wad}', pk3]
    log = f'{work}/run.log'
    env = dict(os.environ, DISPLAY=f':{disp}', ALSOFT_DRIVERS='null')
    snd = ['-config', os.environ['HCE_SCENE_SOUND']] if os.environ.get('HCE_SCENE_SOUND') else ['-nosound']    # HCE_SCENE_SOUND=1: sound on (OpenAL's null output: IsActorPlayingSound works)
    cmd = ['stdbuf', '-oL', '-eL', U, '-iwad', f'{G}/doom2.wad'] + snd + ['-skill', os.environ.get('HCE_SCENE_SKILL', '3'), '-file'] + files + \
          ['-width', str(a.res_w), '-height', str(a.res_h), '+fov', '50', '+vid_fullscreen', '0', '+win_x', '0', '+win_y', '0', '+win_w', str(a.res_w), '+win_h', str(a.res_h), '+win_maximized', '0', '+sv_cheats', '1', '+hce_debugvoice', '1', '+map', a.map,
           '+r_drawplayersprites', '0', '+screenblocks', '12', '+crosshair', '0'] + os.environ.get('HCE_SCENE_ARGS', '').split()   # HCE_SCENE_ARGS: extra engine args (+playerclass ...)
    game = subprocess.Popen(cmd, stdout=open(log, 'w'), stderr=subprocess.STDOUT, env=env)
    os.makedirs(OUTDIR, exist_ok=True)
    shots, n, t0 = [], 1, time.time()
    while time.time() - t0 < getattr(a, 'timeout', 150):
        time.sleep(0.2)
        txt = open(log, errors='replace').read()
        while f'HCEPREV shot {n}\n' in txt or f'HCEPREV shot {n}\r' in txt:
            p = f'{OUTDIR}/{a.name}_{n}.png'
            subprocess.run(['import', '-window', 'root', p], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shots.append(p); n += 1
        if 'HCEPREV done' in txt or game.poll() is not None or 'VM execution aborted' in txt: break
    game.kill(); xv.kill(); game.wait(); xv.wait()
    txt = open(log, errors='replace').read()
    tl = txt.splitlines()
    errors = [' | '.join(tl[i:i + 3]) for i, l in enumerate(tl)
              if re.search(r'VM abort|Script error|ZScript error|Unknown class', l) and 'HDE_dev_lite' not in l]
    lines = [l for l in txt.splitlines() if l.startswith(('HCEPREV', 'HCEVOICE' if a.voices else 'HCEPREV'))]
    if not lines and not errors: errors = ['(no output; the log ends:)'] + txt.splitlines()[-12:]
    black = [p for p in shots if os.path.exists(p) and np.asarray(Image.open(p)).mean() < 3]
    if os.environ.get('HCE_SCENE_LOG'): shutil.copy(log, os.environ['HCE_SCENE_LOG'])   # keep the engine's whole log
    shutil.rmtree(work, ignore_errors=True)
    return lines, errors, shots, black, nshots


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--packs', default='hde', choices=sorted(PACKS))
    ap.add_argument('--spawn', default='')
    ap.add_argument('--spacing', type=float, default=40); ap.add_argument('--z', type=float, default=0)
    ap.add_argument('--dummy', action='store_true'); ap.add_argument('--free', action='store_true'); ap.add_argument('--fight', type=int, default=0)
    ap.add_argument('--mortal', action='store_true'); ap.add_argument('--close', type=int, default=0)
    ap.add_argument('--camera', default='1036,880,0'); ap.add_argument('--pitch', type=float, default=0)
    ap.add_argument('--shots', default=''); ap.add_argument('--duration', type=int, default=0)
    ap.add_argument('--log-damage', action='store_true'); ap.add_argument('--log-every', type=int, default=0)
    ap.add_argument('--zs-top', default=''); ap.add_argument('--voices', action='store_true');
    ap.add_argument('--nopin', action='store_true')      # the player isn't held at the camera spot
    ap.add_argument('--zs', default=''); ap.add_argument('--wad', default='covertest.wad'); ap.add_argument('--map', default='COVERTST'); ap.add_argument('--name', default='scene'); ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--res', default='960x600', help='render size WxH (bigger: crop faces from a distant camera)')
    a = ap.parse_args()
    a.res_w, a.res_h = (int(v) for v in a.res.split('x'))
    for attempt in range(a.retries + 1):
        lines, errors, shots, black, nshots = run(a, attempt)
        if errors:
            print('\n'.join(['ENGINE ERRORS:'] + errors[:15])); sys.exit(1)
        if not black and len(shots) == nshots: break
        print(f'(attempt {attempt + 1}: {len(black)} black, {len(shots)}/{nshots} shots; again)')
    print('\n'.join(lines))
    for p in shots: print('shot', p, '(black)' if p in black else '')


if __name__ == '__main__':
    main()
