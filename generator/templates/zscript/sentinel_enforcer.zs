	// ---- Halo 2's Sentinel Enforcer (extract_h2_sentinels.py)
	// Two energy shields across its front (surfaces {SL} left, {SR} right) take every hit that comes from ahead of it
	// (within 65 degrees either side of where it faces), the left one the hits from its left, the right one the rest,
	// either covering for the other once one is down. Each holds {SHP} damage; worn out, it winks out and comes back
	// after 10 s, and one that was only scratched recovers 4 s after the last hit. Get round its side or behind it.
	// Every 6-10 s, with its target in sight and not too close, it looses a salvo of four homing hard-light rockets
	// that burst on impact. Its needle bolts are its gun (build_pack.WEAPONS 'enforcer needler'), the grapple its melee.
	const HCE_ENF_SHIELD = {SHP};
	int hce_eshHP[2], hce_eshRegen[2];
	bool hce_eshOff[2], hce_eshInit;
	int hce_rocketNext;
	Array<Actor> hce_rockets;

	// Shows or hides one front shield (side 0 left, 1 right) by swapping its model surface skin to hce_hidden.png;
	// does nothing when it is already in that state.
	void HCE_EnfShieldShow(int side, bool show)
	{
		if(hce_eshOff[side] == !show) return;
		hce_eshOff[side] = !show;
		A_ChangeModel('None', 0, "", 'None', side == 0 ? {SL} : {SR}, "models/{MDIR}/weapons", show ? 'None' : 'hce_hidden.png', CMDL_USESURFACESKIN);
	}

	// Spawns six light-blue sparks on the shield's surface facing the attacker (radius * 1.1 out, at a random height).
	void HCE_EnfShieldSpark(Actor from)
	{
		double a = AngleTo(from);
		vector3 p = Vec3Angle(radius * 1.1, a, height * frandom(0.25, 0.8));
		for(int i = 0; i < 6; i++)
			A_SpawnParticle("80D8FF", SPF_FULLBRIGHT, 12, frandom(2, 4), 0, p.x - pos.x, p.y - pos.y, p.z - pos.z,
				frandom(-1.5, 1.5), frandom(-1.5, 1.5), frandom(-0.5, 1.5), 0, 0, 0, 1.0, -0.08);
	}

	// Front shields: a hit from within 65 deg of its facing (not forced, not a telefrag) goes to the shield on the
	// attacker's side, or the other one if that is down. The shield loses the damage, regens 4 s after the last hit,
	// and when exhausted hides itself for 10 s with a pop. Absorbed hits return 0 and never reach the body;
	// anything else goes to the base DamageMobj.
	override int DamageMobj(Actor inflictor, Actor source, int damage, Name mod, int flags, double angle)
	{
		if(health > 0 && damage > 0 && !(flags & DMG_FORCED) && mod != 'Telefrag')
		{
			Actor from = inflictor ? inflictor : source;
			if(from && from != self)
			{
				double rel = DeltaAngle(self.angle, AngleTo(from));
				if(abs(rel) < 65)
				{
					int side = rel > 0 ? 0 : 1;
					if(hce_eshHP[side] <= 0) side = 1 - side;
					if(hce_eshHP[side] > 0)
					{
						hce_eshHP[side] -= damage; hce_eshRegen[side] = 35 * 4;
						HCE_EnfShieldSpark(from);
						if(hce_eshHP[side] <= 0)
						{
							hce_eshHP[side] = 0; hce_eshRegen[side] = 35 * 10;
							HCE_EnfShieldShow(side, false);
							A_StartSound("Shield/Explode", CHAN_6, CHANF_OVERLAP);
						}
						return 0;
					}
				}
			}
		}
		return super.DamageMobj(inflictor, source, damage, mod, flags, angle);
	}

	// Steers every live rocket in hce_rockets at its tracer and bursts one that has stopped flying (A_Explode 28 dmg,
	// 96 radius). Then, with a visible target at least 192 away and the cooldown passed, fires a salvo of four homing
	// HCE_HardlightBlue rockets (20 dmg each) and sets the next salvo 6-10 s out. To change the cadence, edit random(6, 10).
	void HCE_EnfRockets()
	{
		for(int i = hce_rockets.Size() - 1; i >= 0; i--)
		{
			let r = hce_rockets[i];
			if(!r) { hce_rockets.Delete(i); continue; }
			if(!r.bMISSILE) { r.A_Explode(int(28 * HCE_DamageScale()), 96, 0); hce_rockets.Delete(i); continue; }     // it hit: the burst
			if(r.tracer && r.tracer.health > 0) r.A_SeekerMissile(2, 3, SMF_PRECISE);
		}
		if(health <= 0 || !target || hce_dummy || level.maptime < hce_rocketNext) return;
		if(!CheckSight(target) || Distance3D(target) < 192) return;
		hce_rocketNext = level.maptime + 35 * random(6, 10);
		A_StartSound("Halo/Weapons/LightRifle/Fire", CHAN_7, CHANF_OVERLAP, 1.0);
		for(int i = 0; i < 4; i++)
		{
			let r = A_SpawnProjectile('HCE_HardlightBlue', height * 0.7, (i % 2 ? 1 : -1) * radius * 0.5, frandom(-14, 14));
			if(!r) continue;
			r.tracer = target;
			r.A_SetScale(0.02);
			r.vel = r.vel.Unit() * 10;
			r.SetDamage(max(1, int(20 * HCE_DamageScale())));
			hce_rockets.Push(r);
		}
	}

	// Per tic: on the first tic fills both shields to HCE_ENF_SHIELD and sets the first salvo 3-6 s out; runs the
	// rockets; hides both shields on death; otherwise counts down each shield's regen delay and then refills it 4 HP
	// a tic, showing it again as soon as it starts to recover.
	override void Tick()
	{
		super.Tick();
		if(isFrozen()) return;
		if(!hce_eshInit)
		{
			hce_eshInit = true; hce_eshHP[0] = hce_eshHP[1] = HCE_ENF_SHIELD;
			hce_rocketNext = level.maptime + 35 * random(3, 6);
		}
		HCE_EnfRockets();
		if(health <= 0) { HCE_EnfShieldShow(0, false); HCE_EnfShieldShow(1, false); return; }
		for(int s = 0; s < 2; s++)
		{
			if(hce_eshRegen[s] > 0) { hce_eshRegen[s]--; continue; }
			if(hce_eshHP[s] < HCE_ENF_SHIELD) { HCE_EnfShieldShow(s, true); hce_eshHP[s] = min(HCE_ENF_SHIELD, hce_eshHP[s] + 4); }
		}
	}
