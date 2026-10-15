
	// the Stanchion: 24 tics of aiming (the glint and the targeting laser, the charge-up sound), then one rail
	// shot drawn with HDE's laser beam; it tears what it kills apart (HCE_StanchionRail, HCE_WeaponKind)
	const HCE_RAIL_AIM = 24;
	bool hce_cqc;
	// One rail shot over HCE_RAIL_AIM calls: the first 24 draw the glint and aiming laser toward HCE_AimPoint (and start
	// the charge sound), the 25th flashes the beam, sparks at the hit and deals 150 x hce_damageMod x HCE_DamageScale
	// 'Railgun' damage to the shootable actor hit. hce_burstShot counts the calls. To change the damage, edit the 150.
	void HCE_FireRail()
	{
		if(!target) return;
		vector3 ap = HCE_AimPoint();
		double gz = height * 0.5 + hce_gunOffset.z;
		vector3 from = Vec3Angle(hce_gunOffset.x, angle, gz);
		vector3 diff = level.Vec3Diff(from, ap);
		double ang = atan2(diff.y, diff.x);
		double pit = -atan2(diff.z, diff.xy.Length());
		FLineTraceData lt;
		LineTrace(ang, hce_maxRange, pit, TRF_THRUSPECIES, gz, hce_gunOffset.x, 0, lt);
		vector3 to = lt.HitType != TRACE_HitNone ? lt.HitLocation : from + (cos(ang) * cos(pit), sin(ang) * cos(pit), -sin(pit)) * hce_maxRange;
		if(hce_burstShot < HCE_RAIL_AIM)
		{
			if(hce_burstShot == 0 && hce_chargeSound.Length() > 0) A_StartSound(hce_chargeSound, CHAN_WEAPON, CHANF_OVERLAP, 0.9);
			HCE_SniperGlint(level.Vec3Diff(pos, from), hce_burstShot);
			if(level.Vec3Diff(from, to).Length() >= 1) HCE_AimLaser(from, to);
			hce_burstShot++;
			return;
		}
		HCE_EnemyLaser.Flash(from, to, Color(255, 255, 70, 20), 3.0, 0.08);
		HCE_EnemyLaser.Flash(from, to, Color(255, 255, 200, 120), 1.2, 0.12);
		for(int i = 0; i < 12; i++)
			A_SpawnParticle("FF9020", SPF_FULLBRIGHT, 14, 5, 0, to.x - pos.x, to.y - pos.y, to.z - pos.z, frandom(-2, 2), frandom(-2, 2), frandom(0, 3), 0, 0, -0.1, 1.0, -0.06);
		Actor hit = lt.HitActor;
		if(hit && hit != self && hit.bSHOOTABLE)
			hit.DamageMobj(self, self, max(1, int(round(150 * hce_damageMod * HCE_DamageScale()))), 'Railgun');
		HCE_PlayFireSound(false);
		if(hce_moveSpeed <= 0.1 && HCE_HasAnim(HCE_A_FIRE)) HCE_Play(HCE_A_FIRE, false, true, 2);
		hce_burstShot++;
	}
	// Fires the rail unless the Marine is in close-quarters mode (hce_cqc) or carries a loadout gun, when the base
	// projectile fire is used instead.
	override void HCE_FireShot(bool special)
	{
		if(hce_cqc || hce_hasLoadout) { super.HCE_FireShot(special); return; }
		HCE_FireRail();
	}
