
	// the carbine's tracer: every round draws HaloDoom Evolved's green carbine laser trail along its path, from the
	// muzzle to where it will land, fading in a few tics
	override void HCE_OnShot(Actor shot)
	{
		if(shot.vel.Length() < 0.1) return;
		HCE_EnemyLaser.Flash(shot.pos, HCE_TraceEnd(shot.pos, shot.vel), "Green", 2.0, 0.5);
	}
