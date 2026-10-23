		if(t == 5)
		{
			let md = Actor.Spawn("HCE_MarineMedicAssaultRifle", (1036, 980, 0)); HaloDoom_EnemyBase(md).hce_dummy = false; nds.Push(md);
			let p = Actor.Spawn("HCE_MarineAssaultRifle", (1100, 980, 0)); HaloDoom_EnemyBase(p).hce_dummy = false; nds.Push(p);
		}
		if(t > 5 && nds.Size() == 2)
		{
			let md = HaloDoom_EnemyBase(nds[0]), p = HaloDoom_EnemyBase(nds[1]);
			if(t % 70 == 20 && t < 700) { p.A_SetHealth(5); md.HCE_MedicOrder(p); }
			if(t == 760) { Actor.Spawn("HealthBonus", (1036, 1150, 0)); Actor.Spawn("HealthBonus", (900, 1100, 0)); }
			if(t % 70 == 60 || t > 760 && t % 35 == 0) Console.Printf("HCEPREV t%d charges %d patient %d medicFor %d scav %s", t, md.HCE_MedicCharges(), p.health, md.hce_medicFor != null, md.hce_scavItem ? md.hce_scavItem.GetClassName() : 'none');
		}
