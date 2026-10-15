
	// The Engineer never fights: nothing is its enemy (not even whoever shoots it), so it never picks a
	// target. It just drifts around; when killed it bursts and sprays charged Plasma Caster grenades.
	override bool HCE_IsEnemy(Actor other) { return false; }

	double hce_driftAngle, hce_driftSpeed;
	int hce_driftNext;

	// Its gift (as in Halo 3): every second it overshields the allies around it that are in a fight and in
	// its sight, with a pink tether to each. Shielded allies are topped up past their maximum (to 1.5x);
	// unshielded ones (Grunts, Jackals' bodies...) get a small shield of their own. Out of its reach for a few
	// seconds, or when it dies, the gift goes away: overshields fall back to their maximum, given shields vanish.
	Array<HaloDoom_EnemyBase> hce_buffed;
	Array<int> hce_buffAt;
	Array<bool> hce_buffGiven;
	HaloDoom_EnemyBase hce_buffNear;

	// True when e is a live, enabled ally on the Engineer's team and side that is in a fight and is not another
	// Engineer or a Stealth (cloaked) class; those are the ones it shields.
	bool HCE_EngAlly(HaloDoom_EnemyBase e)
	{
		return e && e != self && e.hce_enabled && e.health > 0 && e.hce_team == hce_team && e.bFRIENDLY == bFRIENDLY
			&& !(e is GetClass()) && e.HCE_Alerted() && String.Format("%s", e.GetClassName()).IndexOf("Stealth") < 0;   // cloaked Elites stay shieldless
	}

	// The once-a-second gift: for every ally within 420 units in sight, gives a 40-point shield (x HCE_ShieldScale) to
	// one that has none or tops an existing one up by 20% of its max, to 1.5x max; remembers each in hce_buffed with
	// the time, and keeps the nearest in hce_buffNear. Then releases allies dead or unseen for over 4 s.
	// To change the reach, edit the two 420s; the cap, the 1.5s.
	void HCE_EngPulse()
	{
		hce_buffNear = null;
		double best = 1e9;
		let it = BlockThingsIterator.Create(self, 420);
		while(it.Next())
		{
			let e = HaloDoom_EnemyBase(it.thing);
			if(!HCE_EngAlly(e)) continue;
			double d = Distance3D(e);
			if(d > 420 || !CheckSight(e, SF_IGNOREVISIBILITY)) continue;
			if(d < best) { best = d; hce_buffNear = e; }
			int k = hce_buffed.Find(e);
			bool given = false;
			let sh = ShieldProcessor(e.FindInventory("ShieldProcessor", true));
			if(!sh)
			{
				sh = e.A_SetupShield(40 * HCE_ShieldScale(), 35 * 3, 35 * 2, "Shield/Explode", "", "", "HCE_Shield");
				if(!sh) continue;
				given = true;
			}
			else if(sh.shields < sh.maxshields * 1.5)
				sh.shields = min(sh.maxshields * 1.5, max(sh.shields, 0) + sh.maxshields * 0.2);
			if(k >= hce_buffed.Size()) { hce_buffed.Push(e); hce_buffAt.Push(level.maptime); hce_buffGiven.Push(given); }
			else hce_buffAt[k] = level.maptime;
		}
		// lapsed gifts
		for(int i = hce_buffed.Size() - 1; i >= 0; i--)
			if(!hce_buffed[i] || hce_buffed[i].health <= 0 || level.maptime - hce_buffAt[i] > 35 * 4) HCE_EngRelease(i);
	}

	// Takes the gift back from entry i of hce_buffed: a shield the Engineer gave is destroyed (and its loop sound
	// stopped), a topped-up one is clamped back to its max. Drops the entry from the three parallel arrays.
	void HCE_EngRelease(int i)
	{
		let e = hce_buffed[i];
		if(e && e.health > 0)
		{
			let sh = ShieldProcessor(e.FindInventory("ShieldProcessor", true));
			if(sh)
			{
				if(hce_buffGiven[i]) { e.A_StopSound(ShieldProcessor.CHAN_SHIELDLOOP); sh.Destroy(); }
				else sh.shields = min(sh.shields, sh.maxshields);
			}
		}
		hce_buffed.Delete(i); hce_buffAt.Delete(i); hce_buffGiven.Delete(i);
	}

	// Draws the pink/violet particle tethers from the Engineer's middle to each ally it pulsed in the last 40 tics:
	// 2-18 particles per tether, drifting along it with a slight arc. Purely visual.
	void HCE_EngTether()
	{
		vector3 from = pos + (0, 0, height * 0.5);
		for(int i = 0; i < hce_buffed.Size(); i++)
		{
			let e = hce_buffed[i];
			if(!e || e.health <= 0 || level.maptime - hce_buffAt[i] > 40) continue;
			vector3 d = level.Vec3Diff(from, e.pos + (0, 0, e.height * 0.55));
			int n = clamp(int(d.Length() / 24), 2, 18);
			double ph = (level.maptime % 12) / 12.0;
			for(int k = 0; k < n; k++)
			{
				double t = (k + ph) / n;
				vector3 o = d * t + (frandom(-1.5, 1.5), frandom(-1.5, 1.5), sin(t * 180) * 6);
				A_SpawnParticle(k % 2 ? "FF8CE8" : "C69CFF", SPF_FULLBRIGHT, 4, 3, 0, o.x, o.y, o.z + height * 0.5, 0, 0, 0, 0, 0, 0, 0.85, -0.15);
			}
		}
	}

	// Per tic: pulses the shields once a second (maptime % 35 == 7), redraws tethers every 3 tics, then drifts: toward
	// its nearest shielded ally when farther than 300 or away when closer than 200 (new heading every 2 s), otherwise
	// a random heading every 3-7 s at 0.8-1.8 speed (1 in 4 chance of hovering still). A blocked move repicks at once.
	override void Tick()
	{
		super.Tick();
		if(health <= 0 || bDORMANT || isFrozen()) return;
		if(level.maptime % 35 == 7) HCE_EngPulse();
		if(level.maptime % 3 == 0) HCE_EngTether();
		if(hce_animLock > 0) return;
		// it keeps near the fight: drifts toward the allies it's shielding, but no closer than ~200
		if(hce_buffNear && hce_buffNear.health > 0)
		{
			double d = Distance2D(hce_buffNear);
			if(d > 300 || d < 200)
			{
				double a = AngleTo(hce_buffNear) + (d < 200 ? 180 : 0) + frandom(-25, 25);
				if(level.maptime >= hce_driftNext || abs(DeltaAngle(hce_driftAngle, a)) > 60)
				{
					hce_driftAngle = a; hce_driftSpeed = frandom(1.4, 2.2);
					hce_driftNext = level.maptime + 35 * 2;
				}
			}
		}
		if(level.maptime >= hce_driftNext)
		{
			hce_driftNext = level.maptime + 35 * random(3, 7);
			hce_driftAngle = frandom(0, 360);
			hce_driftSpeed = random(0, 3) == 0 ? 0 : frandom(0.8, 1.8);   // sometimes it just hangs there
		}
		if(hce_driftSpeed <= 0) return;
		if(!HCE_Move(hce_driftAngle, hce_driftSpeed)) { hce_driftNext = 0; return; }   // bumped into something: new heading
		A_SetAngle(angle + clamp(DeltaAngle(angle, hce_driftAngle), -2, 2), SPF_INTERPOLATE);
	}

	// Death: takes back every shield it gave, then bursts (explosion sound, quake, 40 particles) and throws 4-6 charged
	// Plasma Caster cluster shots in a ring, scaled by HCE_DamageScale. The body is hidden; nothing lies on the floor.
	// To change the grenade count, edit random(4, 6).
	override void HCE_Die()
	{
		super.HCE_Die();
		for(int i = hce_buffed.Size() - 1; i >= 0; i--) HCE_EngRelease(i);
		A_StartSound("HCE/Engineer/Explode", CHAN_BODY, CHANF_OVERLAP, 1.0);
		A_StartSound("Halo/Weapons/PlasmaCaster/ChargedFire", CHAN_WEAPON, CHANF_OVERLAP, 1.0);
		A_Quake(2, 8, 0, 512, "");
		for(int i = 0; i < 40; i++)
			A_SpawnParticle(i % 3 ? "C69CFF" : "FFE6FF", SPF_FULLBRIGHT, random(18, 34), frandom(4, 9), 0, 0, 0, height * 0.5,
				frandom(-5, 5), frandom(-5, 5), frandom(-3, 5), 0, 0, -0.12, 1.0, -0.035);
		// charged Plasma Caster shots (HDE): they stick, arm for two seconds, burst and throw two mini bolts
		int n = random(4, 6);
		double a0 = frandom(0, 360);
		for(int i = 0; i < n; i++)
		{
			let g = Spawn("HCE_PlasmaCasterClusterScaled", pos + (0, 0, height * 0.5), ALLOW_REPLACE);
			if(!g) continue;
			g.target = self;
			HCE_ScaleProjectile(g, HCE_DamageScale());          // the projectile nerf covers the bursts too
			g.angle = a0 + i * 360.0 / n + frandom(-20, 20);
			g.vel = (AngleToVector(g.angle, frandom(4, 8)), frandom(4, 9));
		}
		bInvisible = true;            // nothing left to lie on the floor
		vel = (0, 0, 0);
	}
