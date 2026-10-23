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
			vector2 P = c + nn * 256;
			Sector ps = level.PointInSector(P);
			for(int k = 0; k < 4; k++)
			{
				let m = Actor.Spawn("HCE_MarineAssaultRifle", ((P + nn * 60 + (nn.y, -nn.x) * (k - 1.5) * 40), ps.floorplane.ZatPoint(P)));
				if(m) { let e = HaloDoom_EnemyBase(m); if(e) e.hce_dummy = false; nds.Push(m); }
			}
			Console.Printf("HCEPREV door width %.0f normal %.2f %.2f", dl.delta.Length(), nn.x, nn.y);
		}
		if(t >= 5 && nds.Size() > 0 && nds[0])
		{
			vector2 c = nds[0].pos.xy, nn = Actor.AngleToVector(nds[0].angle, 1);
			vector2 P = c + nn * 256;
			Sector ps = level.PointInSector(P);
			if(t < 330) { pl.SetOrigin((P, ps.floorplane.ZatPoint(P)), false); pl.angle = nds[0].angle + 180; pl.pitch = 4; }
			else { vector2 Q = c - nn * 64; pl.SetOrigin((Q, level.PointInSector(Q).floorplane.ZatPoint(Q)), false); pl.angle = nds[0].angle; pl.pitch = 4; }
			if(t == 70) EventHandler.SendNetworkEvent("hce_squad", 11);
			if(t == 280) { let it2 = ThinkerIterator.Create("HCE_Breach"); HCE_Breach b2 = HCE_Breach(it2.Next()); if(b2) b2.door.Activate(pl, b2.side, SPAC_Use); }
			if(t == 200) { let e = HaloDoom_EnemyBase(nds[2]); Console.Printf("HCEPREV r %.0f pr %.0f wd %d hold %d dw %d", e.radius, pl.radius, e.hce_waitedTics, e.hce_squadOrder, e.hce_detourTics); for(int a = 0; a < 360; a += 45) { vector2 np = e.pos.xy + Actor.AngleToVector(a, 6.5); bool ok = e.CheckPosition(np); Console.Printf("HCEPREV a%d ok%d bm %s bl %d haz %d dang %d", a, ok, e.BlockingMobj ? e.BlockingMobj.GetClassName() : '-', e.BlockingLine ? e.BlockingLine.Index() : -1, e.HCE_HazardAt(np), e.HCE_DangerStep(np)); } }
			if(t % 35 == 0)
			{
				let it = ThinkerIterator.Create("HCE_Breach"); HCE_Breach b = HCE_Breach(it.Next());
				String st = "";
				for(int i = 1; i < nds.Size(); i++)
				{
					let e = HaloDoom_EnemyBase(nds[i]); if(!e) continue;
					vector2 h = e.hce_holdPos.xy - c;
					st.AppendFormat(" [%.0f,%.0f->%.0f,%.0f d%.0f o%d ms%.1f w%d wd%d pa%d us%d ma%.0f bm%s bl%d]", e.pos.x - c.x, e.pos.y - c.y, h.x, h.y, (e.pos.xy - e.hce_holdPos.xy).Length(), e.hce_squadOrder, e.hce_moveSpeed, e.hce_waitTics, e.hce_waitedTics, e.hce_pathX.Size(), e.hce_unstickTics, e.hce_moveAngle, e.BlockingMobj ? e.BlockingMobj.GetClassName() : '-', e.BlockingLine ? e.BlockingLine.Index() : -1);
				}
				Console.Printf("HCEPREV t%d %s ph%d open%d%s", t, b ? "B" : "-", b ? b.phase : -1, b ? b.IsOpen() : -1, st);
			}
		}
