		if(t == 5)
		{
			for(int k = 0; k < 4; k++) { let m = Actor.Spawn("HCE_MarineAssaultRifle", (1036 + (k - 1.5) * 60, 980, 0)); if(m) { HaloDoom_EnemyBase(m).hce_dummy = false; nds.Push(m); } }
			Name foes[4]; foes[0] = 'HCE_EliteMinorPlasmaRifle'; foes[1] = 'HCE_GruntMinorPlasmaPistol'; foes[2] = 'HCE_GruntMinorNeedler'; foes[3] = 'HCE_JackalMinorPlasmaPistol';
			for(int k = 0; k < 4; k++) { class<Actor> c = foes[k]; let e = c ? Actor.Spawn(c, (1036 + (k - 1.5) * 90, 1700, 0)) : null; if(e) { HaloDoom_EnemyBase(e).hce_dummy = false; e.angle = 270; nds.Push(e); } else Console.Printf("HCEPREV nofoe %s", foes[k]); }
		}
		if(t >= 5 && t % 35 == 0)
		{
			String st = ""; int alive = 0, foesAlive = 0;
			for(int i = 0; i < nds.Size(); i++)
			{
				let e = HaloDoom_EnemyBase(nds[i]); if(!e) continue;
				if(i >= 4) { if(e.health > 0) foesAlive++; continue; }
				if(e.health > 0) alive++;
				st.AppendFormat(" [%s hp%d post%d k%d d%.0f cv%d rush%d tgt%d see%d ms%.1f]", e.health > 0 ? "" : "X", e.health, e.hce_postOn, e.hce_postKind, (e.hce_post - e.pos.xy).Length(), e.hce_cvState, e.hce_postRush, e.target != null, e.hce_canSee, e.hce_moveSpeed);
			}
			let f = nds.Size() ? HCE_Formation.Get(pl) : null;
			for(int i = 0; i < nds.Size(); i++) { let e = HaloDoom_EnemyBase(nds[i]); if(e) Console.Printf("HCEPREV POS t%d %d %.0f %.0f %.0f %.0f %d %d %.0f %.0f", t, i, e.pos.x, e.pos.y, e.hce_post.x, e.hce_post.y, e.hce_postKind, e.health > 0, e.target ? e.target.pos.x : 0, e.target ? e.target.pos.y : 0); }
			Console.Printf("HCEPREV POS t%d 99 %.0f %.0f 0 0 0 1 0 0", t, pl.pos.x, pl.pos.y);
			Console.Printf("HCEPREV t%d marines %d foes %d drill %d bound %d known %d%s", t, alive, foesAlive, f ? f.drill : -1, f ? f.bounding : -1, f ? f.foes.Size() : -1, st);
		}
