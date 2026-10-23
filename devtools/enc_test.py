#!/usr/bin/env python3
"""enc_test.py: watch the Marine encounters (HCE_Encounters) on a real map.

    python3 enc_test.py MAP02 [--goto 700] [--until 1400] [--shot 760]

Starts the map with hce_encounters 4 at chance 1 (god mode, notarget), and every 70 tics prints each encounter: its
site, the distance to the player, and the health of its Marines and foes (HCEENC lines). --goto T moves the player
480 units from the first encounter's Marines at tic T, facing them; --shot T takes a screenshot (shots/enc_<map>.png).
"""
import argparse, os, re, subprocess, tempfile, time
G = '/home/claude/game'; U = '/home/claude/build/uzb/uzdoom'; D = os.path.dirname(os.path.abspath(__file__))
PACKS = ['HCE_EnemyAPI_LocalDEV.pk3', 'HaloCE_Core.pk3', 'HaloCE_Covenant.pk3', 'HaloCE_Flood.pk3', 'HaloCE_Sentinels.pk3', 'HaloCE_Marines.pk3']
ZS = r'''version "4.15.1"
class HCE_EncTest : EventHandler
{
	override void WorldTick()
	{
		let pl = players[0].mo; if(!pl) return;
		int t = level.maptime;
		if(t == 3) players[0].cheats |= CF_NOTARGET | CF_GODMODE;
		let h = HCE_Encounters(EventHandler.Find("HCE_Encounters"));
		if(!h) return;
		if(t == GOTO && h.enc.Size())
		{
			let en = h.enc[0]; Actor m = null;
			for(int k = 0; k < en.marines.Size() && !m; k++) if(en.marines[k] && en.marines[k].health > 0) m = en.marines[k];
			if(m)
			{
				vector2 dir = (m.pos.xy - en.site.xy).Unit();
				vector2 xy = m.pos.xy + dir * 480;
				pl.SetOrigin((xy, m.pos.z), false); pl.angle = pl.AngleTo(m);
				Console.Printf("HCEENC goto t%d", t);
			}
		}
		if(t == SHOT) Console.Printf("HCEENC shot");
		if(ANIMLOG && t > 30) for(int i = 0; i < h.enc.Size(); i++) for(int k = 0; k < h.enc[i].marines.Size(); k++)
		{
			let m = h.enc[i].marines[k];
			if(m && m.health > 0) Console.Printf("HCEANIM t%d %d.%d %.1f %.1f %s", t, i, k, m.pos.x, m.pos.y, m.hce_curAnim);
		}
		if(t % 70) return;
		for(int i = 0; i < h.enc.Size(); i++)
		{
			let en = h.enc[i];
			String ms = "", fs = "";
			for(int k = 0; k < en.marines.Size(); k++) ms = ms .. (en.marines[k] ? String.Format("%d>%s ", en.marines[k].health, en.marines[k].target ? en.marines[k].target.GetClassName() : 'none') : "x ");
			for(int k = 0; k < en.foes.Size(); k++) fs = fs .. (en.foes[k] ? String.Format("%s:%d>%s ", en.foes[k].GetClassName(), en.foes[k].health, en.foes[k].target ? en.foes[k].target.GetClassName() : 'none') : "x ");
			Console.Printf("HCEENC t%d #%d at %.0f,%.0f dist %.0f joined %d marines [%s] foes [%s]", t, i, en.site.x, en.site.y, (pl.pos - en.site).Length(), en.joined, ms, fs);
		}
	}
}
'''
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('map'); ap.add_argument('--goto', type=int, default=-1)
    ap.add_argument('--until', type=int, default=1400); ap.add_argument('--anims', action='store_true'); ap.add_argument('--shot', type=int, default=-1)
    a = ap.parse_args()
    w = tempfile.mkdtemp(prefix='enc_')
    os.makedirs(f'{w}/p')
    open(f'{w}/p/zscript.txt', 'w').write(ZS.replace('ANIMLOG', 'true' if a.anims else 'false').replace('GOTO', str(a.goto)).replace('SHOT', str(a.shot)))
    open(f'{w}/p/mapinfo.txt', 'w').write('GameInfo { AddEventHandlers = "HCE_EncTest" }\n')
    subprocess.run(['zip', '-qr', f'{w}/t.pk3', '.'], cwd=f'{w}/p', check=True)
    disp = ':79'
    xv = subprocess.Popen(['Xvfb', disp, '-screen', '0', '960x600x24'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(2)
    env = dict(os.environ, DISPLAY=disp)
    log = f'{w}/log.txt'
    g = subprocess.Popen(['stdbuf', '-oL', '-eL', U, '-iwad', f'{G}/doom2.wad', '-nosound', '-skill', '3', '-file', f'{G}/HDE_dev_lite.pk3'] +
                         [f'{G}/{p}' for p in PACKS] + [f'{w}/t.pk3', '-width', '960', '-height', '600', '+vid_fullscreen', '0',
                         '+hce_encounters', '4', '+hce_encounterchance', '1', '+map', a.map], stdout=open(log, 'w'), stderr=subprocess.STDOUT, env=env)
    t0 = time.time(); seen = set(); shot_done = False
    try:
        while time.time() - t0 < 60 + a.until / 35 * 3:
            time.sleep(0.2)
            txt = open(log, errors='replace').read()
            for l in txt.splitlines():
                if ('HCEENC' in l or 'HCEANIM' in l or 'Script error' in l or 'VM abort' in l) and l not in seen:
                    seen.add(l); print(l)
                    if 'HCEENC shot' in l and not shot_done:
                        subprocess.run(['import', '-window', 'root', f'{D}/shots/enc_{a.map}.png'], env=env); shot_done = True
            m = re.findall(r'HCEENC t(\d+)', txt)
            if m and int(m[-1]) >= a.until: break
            if g.poll() is not None: break
    finally:
        g.kill(); xv.kill()
        if not seen or not any('HCEENC t' in l for l in seen): print(open(log, errors='replace').read()[-2500:])
main()
