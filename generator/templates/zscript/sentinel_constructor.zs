	// ---- Halo 2's Constructor (extract_h2_sentinels.py), in the Lost Souls' place. It has no gun: every 2-4 s, with its
	// target in sight 96-640 units away, it darts at it for up to a second, homing, and rams it (3-24 damage, as a Lost
	// Soul's bite); in reach it welds it with a short arc of its cutting beam (6-16 damage)
	int hce_dartTics, hce_dartNext;

	// In melee reach it welds the target (HCE_ConWeld) instead of the base melee swing, then waits 30 tics before the
	// next weld. Returns false while on cooldown or without a target.
	override bool HCE_TryMelee()
	{
		if(hce_meleeTics > level.maptime || !target) return false;
		A_SetAngle(AngleTo(target));
		HCE_ConWeld();
		hce_meleeTics = level.maptime + 30;
		return true;
	}

	// The welding arc: a line of yellow sparks from its middle to the target's, the Light Rifle fire sound, and 6-16
	// 'Plasma' damage if the target is within 112 units. The damage is not run through HCE_DamageScale.
	void HCE_ConWeld()
	{
		if(!target) return;
		vector3 a = pos + (0, 0, height * 0.5), b = target.pos + (0, 0, target.height * 0.5);
		vector3 d = level.Vec3Diff(a, b);
		int n = clamp(int(d.Length() / 6), 1, 24);
		for(int i = 0; i <= n; i++)
		{
			vector3 p = d * (double(i) / n);
			A_SpawnParticle("FFD870", SPF_FULLBRIGHT, 6, frandom(2, 4), 0, p.x, p.y, height * 0.5 + p.z,
				frandom(-0.4, 0.4), frandom(-0.4, 0.4), frandom(-0.4, 0.4));
		}
		A_StartSound("Halo/Weapons/LightRifle/Fire", CHAN_WEAPON, CHANF_OVERLAP, 0.5);
		if(Distance3D(target) < 112) target.DamageMobj(self, self, int(random(3, 8) * 2 * HCE_DamageScale()), 'Plasma');
	}

	// The ram: while hce_dartTics runs it flies straight at the target at 14 units/tic, homing every tic; on contact
	// deals 3-24 'Melee' damage, bounces back and stops. Otherwise, with the target in sight 96-640 units away and the
	// cooldown passed, starts a 40-tic dart and sets the next one 2-4 s out. To change the cadence, edit random(2, 4).
	override void Tick()
	{
		super.Tick();
		if(isFrozen() || health <= 0 || hce_dummy) { hce_dartTics = 0; return; }
		if(hce_dartTics > 0)
		{
			hce_dartTics--;
			if(!target) { hce_dartTics = 0; return; }
			vel = level.Vec3Diff(pos, target.pos + (0, 0, target.height * 0.5)).Unit() * 14;
			A_SetAngle(AngleTo(target));
			if(Distance3D(target) < radius + target.radius + 20)
			{
				target.DamageMobj(self, self, int(random(1, 8) * 3 * HCE_DamageScale()), 'Melee', 0, AngleTo(target));
				A_StartSound("HCE/Melee", CHAN_WEAPON, CHANF_OVERLAP);
				vel = -vel * 0.4; hce_dartTics = 0;
			}
			return;
		}
		if(!target || level.maptime < hce_dartNext || !CheckSight(target)) return;
		double dist = Distance3D(target);
		if(dist < 96 || dist > 640) return;
		hce_dartNext = level.maptime + 35 * random(2, 4);
		hce_dartTics = 40;
	}
