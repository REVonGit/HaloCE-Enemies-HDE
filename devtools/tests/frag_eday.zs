		if(t == 5)
		{
			Line dl = null; int dside = 0;
			double bestd = 1e9;
			for(int i = 0; i < level.Lines.Size(); i++)
			{
				Line l = level.Lines[i];
				if(!l.backsector || !HCE_Breach.IsDoorSpecial(l.special)) continue;
				double dd = (l.v1.p + l.delta / 2 - (896, 320)).Length(); if(dd > bestd) continue;
				for(int s = 0; s < 2; s++)
				{
					Sector a = s == 0 ? l.frontsector : l.backsector, b = s == 0 ? l.backsector : l.frontsector;
					if(b.ceilingplane.ZatPoint(l.v1.p) - b.floorplane.ZatPoint(l.v1.p) < 8 && a.ceilingplane.ZatPoint(l.v1.p) - a.floorplane.ZatPoint(l.v1.p) > 60 && l.delta.Length() >= 64) { dl = l; dside = s; bestd = dd; break; }
				}
			}
			if(!dl) { Console.Printf("HCEPREV no door"); return; }
			vector2 c = dl.v1.p + dl.delta / 2, nn = (dl.delta.y, -dl.delta.x).Unit();
			if(dside == 1) nn = -nn;
			if(nn.y > 0) nn = -nn;
			let mk = Actor.Spawn("MapSpot", (c, 0)); mk.angle = atan2(nn.y, nn.x); nds.Push(mk);
			vector2 P = c + nn * 170;
			Sector ps = level.PointInSector(P);
			for(int k = 0; k < 4; k++)
			{
				let m = Actor.Spawn("HCE_MarineAssaultRifle", ((P + (nn.y, -nn.x) * (k - 1.5) * 44), ps.floorplane.ZatPoint(P)));
				if(m) { let e = HaloDoom_EnemyBase(m); if(e) e.hce_dummy = false; nds.Push(m); }
			}
			Console.Printf("HCEPREV door width %.0f normal %.2f %.2f", dl.delta.Length(), nn.x, nn.y);
		}
		if(t >= 5 && nds.Size() > 0 && nds[0])
		{
			vector2 c = nds[0].pos.xy, nn = Actor.AngleToVector(nds[0].angle, 1);
			vector2 P = c + nn * 200;
			Sector ps = level.PointInSector(P);
			if(t < 100000) { pl.SetOrigin((P, ps.floorplane.ZatPoint(P)), false); pl.angle = nds[0].angle + 180; pl.pitch = 4; }
			else { vector2 Q = c - nn * 64; pl.SetOrigin((Q, level.PointInSector(Q).floorplane.ZatPoint(Q)), false); pl.angle = nds[0].angle; pl.pitch = 4; }
			if(t == 70) EventHandler.SendNetworkEvent("hce_squad", 13);
			if(t == 50) pl.GiveInventory("RedCard", 1);
			if(t == 60) { let it0 = ThinkerIterator.Create("HCE_Breach"); Console.Printf("HCEPREV KEY has %d", pl.CountInv("YellowCard")); }
			if(t == 300) { let it0 = ThinkerIterator.Create("HCE_Breach"); HCE_Breach b0 = HCE_Breach(it0.Next()); if(b0) { Line ol = b0.OpenLine(); Console.Printf("HCEPREV OL line %d sp %d a3 %d lock %d side %d men0 at %.0f %.0f press %d", ol.Index(), ol.special, ol.Args[3], HaloDoom_EnemyBase.HCE_LineLock(ol), level.PointOnLineSide(b0.men[0].pos.xy, ol), b0.men[0].pos.x, b0.men[0].pos.y, b0.men[0].HCE_PressLine(ol, level.PointOnLineSide(b0.men[0].pos.xy, ol), SPAC_Use)); } }
			if(t == 72) { let it0 = ThinkerIterator.Create("HCE_Breach"); HCE_Breach b0 = HCE_Breach(it0.Next()); if(b0) { Console.Printf("HCEPREV BR door %d c %.0f %.0f n %.2f %.2f t %.2f %.2f w %.0f side %d dsec %d", b0.door.Index(), b0.c.x, b0.c.y, b0.n.x, b0.n.y, b0.t.x, b0.t.y, b0.w, b0.side, b0.doorSec ? b0.doorSec.Index() : -1); for(int i = 0; i < b0.men.Size(); i++) Console.Printf("HCEPREV BR man %d hold %.0f %.0f fits %d", i, b0.men[i].hce_holdPos.x, b0.men[i].hce_holdPos.y, HaloDoom_EnemyBase.HCE_SpotFits(b0.men[i].hce_holdPos.xy, 14, b0.men[i].hce_holdPos.z)); } Console.Printf("HCEPREV BR player %.0f %.0f %.0f marker %.0f %.0f", pl.pos.x, pl.pos.y, pl.pos.z, c.x, c.y); }
			if(t == 60) { let ki = ThinkerIterator.Create("Actor"); Actor kk; while(kk = Actor(ki.Next())) if(kk.bISMONSTER && !kk.bFRIENDLY && kk.health > 0 && (kk.pos.xy - (896, 648)).Length() < 400) kk.bDORMANT = false; }
			if(t >= 200 && t <= 700 && t % 10 == 0) { let gi = ThinkerIterator.Create("Actor"); Actor g; while(g = Actor(gi.Next())) { String cn = g.GetClassName(); if(cn.IndexOf("renade") >= 0 || cn.IndexOf("Frag") >= 0) Console.Printf("HCEPREV G t%d %s %.0f %.0f %.0f", t, cn, g.pos.x - c.x, g.pos.y - c.y, g.pos.z); } }
			if(t == 200)
			{
				for(int i = 0; i < level.Lines.Size(); i++)
				{
					Line l = level.Lines[i];
					if((HaloDoom_EnemyBase.HCE_LinePoint(l, c) - c).Length() > 500) continue;
					double f1 = l.frontsector.floorplane.ZatPoint(l.v1.p), f2 = l.backsector ? l.backsector.floorplane.ZatPoint(l.v1.p) : 9999;
					double c2 = l.backsector ? l.backsector.ceilingplane.ZatPoint(l.v1.p) - f2 : -1;
					Console.Printf("HCEPREV L %.0f %.0f %.0f %.0f %d %.0f %.0f %.0f %d", l.v1.p.x - c.x, l.v1.p.y - c.y, l.v2.p.x - c.x, l.v2.p.y - c.y, l.backsector != null, f1, f2, c2, l.flags);
				}
				for(int i = 1; i < nds.Size(); i++) if(nds[i]) Console.Printf("HCEPREV M %.0f %.0f %.0f %.0f", nds[i].pos.x - c.x, nds[i].pos.y - c.y, HaloDoom_EnemyBase(nds[i]).hce_holdPos.x - c.x, HaloDoom_EnemyBase(nds[i]).hce_holdPos.y - c.y);
				Console.Printf("HCEPREV P %.0f %.0f", pl.pos.x - c.x, pl.pos.y - c.y);
			}
			if(t == 150 && nds.Size() > 1 && nds[1])
			{
				let e = HaloDoom_EnemyBase(nds[1]);
				Console.Printf("HCEPREV dbg z %.0f floorz %.0f dropoff %.0f sec %d dmg %d", e.pos.z, e.floorz, e.dropoffz, e.CurSector.Index(), e.CurSector.damageamount);
				for(int k = -4; k <= 8; k++) { vector2 q = e.pos.xy + (k * 8, 0); Sector qs = level.PointInSector(q); bool ok = e.CheckPosition(q); Console.Printf("HCEPREV dbg x%+d sec %d floor %.0f try %d mobj %s line %d", k * 8, qs.Index(), qs.floorplane.ZatPoint(q), ok, e.BlockingMobj ? e.BlockingMobj.GetClassName() : 'none', e.BlockingLine ? e.BlockingLine.Index() : -1); }
			}
			if(t % 35 == 0)
			{
				let it = ThinkerIterator.Create("HCE_Breach"); HCE_Breach b = HCE_Breach(it.Next());
				String st = "";
				for(int i = 1; i < nds.Size(); i++)
				{
					let e = HaloDoom_EnemyBase(nds[i]); if(!e) continue;
					vector2 h = e.hce_holdPos.xy - c;
					st.AppendFormat(" [%.0f,%.0f->%.0f,%.0f d%.0f o%d br%d cv%d a%d see%d lk%d, ff%d ms%.1f w%d pa%d us%d]", e.pos.x - c.x, e.pos.y - c.y, h.x, h.y, (e.pos.xy - e.hce_holdPos.xy).Length(), e.hce_squadOrder, e.hce_breach != null, e.hce_cvState, e.hce_action, e.InStateSequence(e.CurState, e.FindState("See")), e.hce_animLock, e.hce_ffStepTics, e.hce_moveSpeed, e.hce_waitTics, e.hce_pathX.Size(), e.hce_unstickTics);
				}
				Console.Printf("HCEPREV t%d %s ph%d open%d%s", t, b ? "B" : "-", b ? b.phase : -1, b ? b.IsOpen() : -1, st);
			}
		}
