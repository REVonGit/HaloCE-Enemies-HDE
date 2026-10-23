#!/usr/bin/env python3
"""lift_test.py: does a Marine get up a lift to reach the player? (generator/tests/make_lifttest.py -> game/lifttest.wad)

    python3 lift_test.py                  # all three maps: LIFTSW (a switch elsewhere), LIFTFACE (the lift's own face), LIFTWALK (a walk-over line)
    python3 lift_test.py LIFTSW --order   # the squad's "press that button" order on the switch instead (LIFTSW only)

The player stands on a ledge at 128; a Marine (an ally, following him) starts on the floor below. Every second the
Marine's position and floor are logged; the run passes when he stands on the ledge's height within 200 units of the
player, and fails after --time seconds.
"""
import argparse, os, re, subprocess, sys, tempfile, time, zipfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene

ZS = '''version "4.15.1"
class HCE_LiftTest : EventHandler
{
	Actor m;
	override void WorldTick()
	{
		let pl = players[0].mo; if(!pl) return;
		int t = level.maptime;
		if(t == 5)
		{
			players[0].cheats |= CF_NOTARGET | CF_GODMODE;
			m = Actor.Spawn("HCE_MarineAssaultRifle", (768, 300, 0));
			if(m) { m.angle = 90; Console.Printf("HCELIFT spawned"); }
		}
		if(t == 70 && ORDER)
		{
			// from the ledge the player looks at the switch's pillar (its south face at x 300-364, y 500) and orders it pressed
			vector3 d = level.Vec3Diff((pl.pos.xy, pl.pos.z + pl.player.viewheight), (332, 532, 40));
			pl.angle = atan2(d.y, d.x); pl.pitch = -atan2(d.z, d.xy.Length());
		}
		if(t == 72 && ORDER) EventHandler.SendNetworkEvent("hce_squad", 9);
		if(t > 5 && (t % 35 == 0 || (t > 70 && t < 260 && t % 10 == 0)) && m)
		{
			let e = HaloDoom_EnemyBase(m);
			Console.Printf("HCELIFT liftz %.0f t%d x %.0f y %.0f z %.0f dist %.0f%s", level.Sectors[2].floorplane.ZatPoint((768, 1036)), t, m.pos.x, m.pos.y, m.pos.z, m.Distance2D(pl),
				e ? String.Format(" walking %d spot %.0f,%.0f stuck %d button %d act %d lift %d moving %d spd %.1f wait %d", e.hce_fmWalking, e.hce_formSpot.x, e.hce_formSpot.y, e.hce_fmStuck, e.hce_button != null, e.hce_action, e.hce_liftSec != null, e.HCE_OnMovingLift(), e.hce_moveSpeed, e.hce_waitTics) : "");
		}
		if(m && t > 40 && m.pos.z >= 120 && m.Distance2D(pl) < 200 && true) { Console.Printf("HCELIFT PASS t%d", t); Console.Printf("HCELIFT done"); }
		if(t == LIMIT) Console.Printf("HCELIFT FAIL"), Console.Printf("HCELIFT done");
	}
}
'''


def run(mp, order, secs):
    zs = ZS.replace('ORDER', 'true' if order else 'false').replace('LIMIT', str(secs * 35))
    zs = zs.replace('Console.Printf("HCELIFT FAIL"), Console.Printf("HCELIFT done");', '{ Console.Printf("HCELIFT FAIL"); Console.Printf("HCELIFT done"); }')
    work = tempfile.mkdtemp(prefix='lift_')
    pk3 = f'{work}/lift.pk3'
    with zipfile.ZipFile(pk3, 'w') as z:
        z.writestr('zscript.txt', zs)
        z.writestr('mapinfo.txt', 'GameInfo { AddEventHandlers = "HCE_LiftTest" }\n')
    disp = ':' + str(70 + os.getpid() % 9)
    xv = subprocess.Popen(['Xvfb', disp, '-screen', '0', '640x400x24'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    files = [f'{scene.G}/{p}' for p in scene.PACKS['hde']] + [f'{scene.G}/lifttest.wad', pk3]
    log = f'{work}/run.log'
    cmd = ['stdbuf', '-oL', '-eL', scene.U, '-iwad', f'{scene.G}/doom2.wad', '-nosound', '-skill', '3', '-file'] + files + \
          ['-width', '640', '-height', '400', '+vid_fullscreen', '0', '+sv_cheats', '1', '+map', mp]
    g = subprocess.Popen(cmd, stdout=open(log, 'w'), stderr=subprocess.STDOUT, env=dict(os.environ, DISPLAY=disp))
    t0 = time.time()
    while time.time() - t0 < secs * 2 + 90:
        time.sleep(0.5)
        txt = open(log, errors='replace').read()
        if 'HCELIFT done' in txt or g.poll() is not None or 'VM execution aborted' in txt: break
    g.kill(); xv.kill(); g.wait(); xv.wait()
    txt = open(log, errors='replace').read()
    shutil.rmtree(work, ignore_errors=True)
    errs = [l for l in txt.splitlines() if re.search(r'VM abort|Script error|ZScript error', l)]
    return [l for l in txt.splitlines() if l.startswith('HCELIFT')], errs


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('maps', nargs='*', default=['LIFTSW', 'LIFTFACE', 'LIFTWALK'])
    ap.add_argument('--order', action='store_true'); ap.add_argument('--time', type=int, default=60)
    a = ap.parse_args()
    for mp in a.maps:
        lines, errs = run(mp, a.order, a.time)
        print(f'== {mp}' + (' (order)' if a.order else ''))
        for l in errs: print('  ERROR', l)
        for l in lines: print(' ', l)
