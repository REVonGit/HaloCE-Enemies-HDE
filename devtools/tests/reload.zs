		if(t == 5) for(int k = 0; k < 2; k++) { let m = Actor.Spawn("HCE_MarineAssaultRifle", (1000 + k * 60, 1000, 0)); if(m) { HaloDoom_EnemyBase(m).hce_dummy = false; nds.Push(m); } }
		if(t == 5) { let g = Actor.Spawn("HCE_GruntMinorPlasmaPistol", (1036, 1500, 0)); if(g) { HaloDoom_EnemyBase(g).hce_dummy = false; g.A_SetHealth(100000); nds.Push(g); } }
		if(t >= 10 && t % 10 == 0 && t < 300) for(int i = 0; i < 2; i++) { let e = HaloDoom_EnemyBase(nds[i]); if(e.hce_mag == e.hce_magSize && e.hce_magSize > 0) e.hce_mag = e.hce_magSize / 3; e.hce_combatUntil = level.maptime + 100000; }
		if(t == 300) EventHandler.SendNetworkEvent("hce_squad", 10);
		if(t >= 280 && t % 7 == 0 && t < 460) { String st = ""; for(int i = 0; i < 2; i++) { let e = HaloDoom_EnemyBase(nds[i]); st.AppendFormat(" [mag %d/%d want %d lock %d shots %d tgt %d]", e.hce_mag, e.hce_magSize, e.hce_wantReload, e.hce_animLock, e.hce_shotsLeft, e.target != null); } Console.Printf("HCEPREV t%d%s", t, st); }
