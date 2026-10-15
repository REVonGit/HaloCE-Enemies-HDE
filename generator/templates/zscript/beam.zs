
	// Particle beam rifle: every shot is telegraphed by a second-long aiming laser and the sniper glint, then one hitscan
	// beam, drawn with HaloDoom Evolved's beam rifle laser
	override void HCE_UpdateFiring(double dist)
	{
		super.HCE_UpdateFiring(dist);
		if(hce_chargeTics > 0 && target)
		{
			HCE_BeamTrace(false);
			HCE_SniperGlint(level.Vec3Diff(pos, Vec3Angle(hce_gunOffset.x, angle, height * 0.5 + hce_gunOffset.z)), hce_chargeTics);
		}
	}
	// The shot itself: one hitscan beam (HCE_BeamTrace) with the fire sound and, standing still, the fire animation.
	// Replaces the base projectile fire entirely; this gun never spawns a projectile actor.
	override void HCE_FireShot(bool special)
	{
		if(!target) return;
		HCE_BeamTrace(true);
		HCE_PlayFireSound(true);
		if(hce_moveSpeed <= 0.1 && HCE_HasAnim(HCE_A_FIRE)) HCE_Play(HCE_A_FIRE, false, true, 2);
	}
	// Traces one line from the gun to the target's chest (60% height). fire=false only draws the aiming laser along it;
	// fire=true adds spread (hce_errorAngle, +1.2 deg vs a running target, else +0.3), draws the purple/pink beam, deals
	// 90 damage (x hce_damageMod x HCE_DamageScale) as 'Fire' to what it hit and puffs there. To change damage, edit the 90.
	void HCE_BeamTrace(bool fire)
	{
		double gz = height * 0.5 + hce_gunOffset.z;
		vector3 from = Vec3Angle(hce_gunOffset.x, angle, gz);
		vector3 aim = target.pos + (0, 0, target.height * 0.6);
		vector3 diff = level.Vec3Diff(from, aim);
		double err = fire ? hce_errorAngle + (target.vel.xy.Length() > 6 ? 1.2 : 0.3) : 0;
		double ang = atan2(diff.y, diff.x) + frandom(-err, err);
		double pit = -atan2(diff.z, diff.xy.Length()) + frandom(-err, err);
		FLineTraceData lt;
		LineTrace(ang, hce_maxRange, pit, 0, gz, hce_gunOffset.x, 0, lt);
		vector3 to = lt.HitType != TRACE_HitNone ? lt.HitLocation : from + (cos(ang) * cos(pit), sin(ang) * cos(pit), -sin(pit)) * hce_maxRange;
		vector3 d = level.Vec3Diff(from, to);
		double len = d.Length();
		if(len < 1) return;
		if(!fire) { HCE_AimLaser(from, to); return; }                  // the targeting laser
		// the shot: HaloDoom Evolved's beam rifle laser, a purple beam with a pink core, flashing out and spreading
		let o = HCE_EnemyLaser.Make(from, "Purple", 1.5, 0.25, 1.02);
		if(o) o.Hold(from, to, 3);
		let c = HCE_EnemyLaser.Make(from, "Pink", 0.75, 0.25, 1.02);
		if(c) c.Hold(from, to, 3);
		{ CVar dbg = CVar.FindCVar("hce_digdebug"); if(dbg && dbg.GetInt()) console.printf("BEAM hit %s at %.0f", lt.HitActor ? lt.HitActor.GetClassName() : 'world', lt.Distance); }
		if(lt.HitActor && lt.HitActor != self)
		{
			int dmg = max(1, int(90 * (hce_damageMod > 0 ? hce_damageMod : 1.0) * HCE_DamageScale()));
			lt.HitActor.DamageMobj(self, self, dmg, 'Fire', 0, ang);
		}
		Spawn("HCE_BeamPuff", to);
	}
