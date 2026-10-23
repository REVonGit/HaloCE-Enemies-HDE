		if(t == 5)
		{
			for(int k = 0; k < 4; k++)
			{
				let m = Actor.Spawn("HCE_MarineAssaultRifle", (180 + k * 40, 420, 0));
				if(m) { let e = HaloDoom_EnemyBase(m); if(e) e.hce_dummy = false; nds.Push(m); }
			}
		}
		if(t >= 5)
		{
			pl.SetOrigin((264, 470, 0), false); pl.angle = 90; pl.pitch = 8;
			if(t == 70) EventHandler.SendNetworkEvent("hce_squad", 12);
			if(t % 35 == 0)
			{
				String st = "";
				for(int i = 0; i < nds.Size(); i++)
				{
					let e = HaloDoom_EnemyBase(nds[i]); if(!e) continue;
					st.AppendFormat(" [%.0f,%.0f->%.0f,%.0f o%d sec%d]", e.pos.x, e.pos.y, e.hce_holdPos.x, e.hce_holdPos.y, e.hce_squadOrder, e.CurSector.Index());
				}
				Console.Printf("HCEPREV t%d%s", t, st);
			}
		}
