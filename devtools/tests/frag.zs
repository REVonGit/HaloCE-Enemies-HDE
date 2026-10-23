		if(t == 5)
		{
			Line dl = null; int dside = 0;
			for(int i = 0; i < level.Lines.Size() && !dl; i++)
			{
				Line l = level.Lines[i];
				if(!l.backsector || !HCE_Breach.IsDoorSpecial(l.special)) continue;
				for(int s = 0; s < 2; s++)
				{
					Sector a = s == 0 ? l.frontsector : l.backsector, b = s == 0 ? l.backsector : l.frontsector;
					if(b.ceilingplane.ZatPoint(l.v1.p) - b.floorplane.ZatPoint(l.v1.p) < 8 && a.ceilingplane.ZatPoint(l.v1.p) - a.floorplane.ZatPoint(l.v1.p) > 96 && l.delta.Length() >= 64) { dl = l; dside = s; break; }
				}
			}
			if(!dl) { Console.Printf("HCEPREV no door"); return; }
			vector2 c = dl.v1.p + dl.delta / 2, nn = (dl.delta.y, -dl.delta.x).Unit();
			if(dside == 1) nn = -nn;
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
			vector2 P = c + nn * 280;
			Sector ps = level.PointInSector(P);
			if(t < 100000) { pl.SetOrigin((P, ps.floorplane.ZatPoint(P)), false); pl.angle = nds[0].angle + 180; pl.pitch = 4; }
			else { vector2 Q = c - nn * 64; pl.SetOrigin((Q, level.PointInSector(Q).floorplane.ZatPoint(Q)), false); pl.angle = nds[0].angle; pl.pitch = 4; }
			if(t == 70) EventHandler.SendNetworkEvent("hce_squad", 13);
			if(t >= 200 && t <= 400 && t % 4 == 0) { let gi = ThinkerIterator.Create("Actor"); Actor g; while(g = Actor(gi.Next())) { String cn = g.GetClassName(); if(cn.IndexOf("renade") >= 0 || cn.IndexOf("Frag") >= 0) Console.Printf("HCEPREV G t%d %s %.0f %.0f %.0f", t, cn, g.pos.x - c.x, g.pos.y - c.y, g.pos.z); } }
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
					st.AppendFormat(" [%.0f,%.0f->%.0f,%.0f d%.0f o%d a%d see%d lk%d, ff%d ms%.1f w%d pa%d us%d]", e.pos.x - c.x, e.pos.y - c.y, h.x, h.y, (e.pos.xy - e.hce_holdPos.xy).Length(), e.hce_squadOrder, e.hce_action, e.InStateSequence(e.CurState, e.FindState("See")), e.hce_animLock, e.hce_ffStepTics, e.hce_moveSpeed, e.hce_waitTics, e.hce_pathX.Size(), e.hce_unstickTics);
				}
				Console.Printf("HCEPREV t%d %s ph%d open%d%s", t, b ? "B" : "-", b ? b.phase : -1, b ? b.IsOpen() : -1, st);
			}
		}
