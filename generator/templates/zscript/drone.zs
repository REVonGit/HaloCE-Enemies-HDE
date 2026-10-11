
	// ---- Halo 2 Drone behaviour ----------------------------------------------------------------------
	// darting flight above the target, sideways dodges when hit (char tag: 50% chance, 4 s apart), wall
	// perching (back to the wall, firing from it), swarm scatter when a drone nearby dies, falling deaths.
	int hce_dartTics, hce_dartNext, hce_zigTics, hce_scatterTics, hce_buzzTics, hce_lastAir;
	double hce_dartAngle, hce_zigOff, hce_altWant;
	int hce_perch, hce_perchTics, hce_perchNext, hce_perchSide, hce_perchEnter;   // perch: 0 no, 1 flying to wall, 2 clinging
	vector3 hce_perchPos; double hce_perchAngle;

	override void PostBeginPlay()
	{
		super.PostBeginPlay();
		hce_altWant = frandom(40, 110);
		hce_perchNext = level.maptime + 35 * random(4, 10);
		hce_perchSide = random(0, 1);
	}

	// flying: stay above whatever we fight, at a height that keeps changing
	void HCE_DroneAltitude()
	{
		if(health <= 0) return;
		if(random(0, 70) == 0) hce_altWant = frandom(30, 130);
		double base = target ? target.pos.z + target.height : floorz + 40;
		double want = clamp(base + hce_altWant, floorz + 24, ceilingz - height - 6);
		vel.z = clamp((want - pos.z) * 0.07, -4, 4) + sin(level.maptime * 9 + tid * 31) * 0.35;
	}

	override void HCE_Fight()
	{
		if(hce_perch) return;
		if(hce_scatterTics > 0 && target)
		{
			hce_scatterTics--;
			HCE_Move(HCE_PickHeading(AngleTo(target) + 180 + hce_zigOff, AngleTo(target)), hce_runSpeed * 1.2);
			A_SetAngle(hce_moveAngle, SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		double d = Distance2D(target);
		HCE_FaceTarget(2.5);
		if(!hce_canSee && level.maptime - hce_lastSeen > 25) { HCE_Pursue(); return; }
		// swarm darting: a new heading offset every half second or so
		if(--hce_zigTics <= 0)
		{
			hce_zigTics = random(10, 28); hce_zigOff = frandom(-110, 110);
			if(random(0, 3) == 0) A_StartSound("HCE/Drone/Whoosh", CHAN_6, CHANF_OVERLAP, 0.5);
		}
		double toT = AngleTo(target), moveA, spd;
		if(d > hce_rangeMax) { moveA = toT + hce_zigOff * 0.4; spd = hce_runSpeed; }
		else if(d < hce_rangeMin) { moveA = toT + 180 + hce_zigOff * 0.5; spd = hce_runSpeed * 0.8; }
		else { moveA = toT + (hce_zigOff >= 0 ? 90 : -90) + hce_zigOff * 0.2; spd = hce_runSpeed * 0.7; }
		HCE_Move(HCE_PickHeading(moveA, toT), spd);
		HCE_UpdateFiring(d);
		HCE_PickMoveAnim();
		if(level.maptime >= hce_perchNext && hce_canSee && random(0, 90) == 0) HCE_TryPerch();
	}

	// dodge sideways when hit
	override int HCE_ModifyIncoming(Actor inflictor, Actor source, int dmg, Name mod, int flags, double dangle)
	{
		dmg = super.HCE_ModifyIncoming(inflictor, source, dmg, mod, flags, dangle);
		if(dmg > 0 && dmg < health && level.maptime >= hce_dartNext && frandom(0, 1) < 0.5)
		{
			hce_dartNext = level.maptime + 35 * 4;
			hce_dartTics = 12;
			hce_dartAngle = angle + (random(0, 1) ? 90 : -90);
			A_StartSound("HCE/Drone/Whoosh", CHAN_6, CHANF_OVERLAP, 0.8);
			if(hce_perch) HCE_LeavePerch();
		}
		return dmg;
	}

	// ---- perching
	void HCE_TryPerch()
	{
		hce_perchNext = level.maptime + 35 * (target ? random(15, 25) : random(10, 18));
		double best = 1e9; FLineTraceData lt;
		Line bestLine = null; int bestSide = 0; vector3 bestHit;
		for(int a = 0; a < 360; a += 30)
		{
			if(!LineTrace(angle + a, 360, 0, TRF_THRUACTORS | TRF_THRUHITSCAN, height * 0.5, data: lt)) continue;
			if(lt.HitType != TRACE_HitWall || !lt.HitLine) continue;
			if(lt.Distance < best) { best = lt.Distance; bestLine = lt.HitLine; bestSide = lt.LineSide; bestHit = lt.HitLocation; }
		}
		if(!bestLine) return;
		vector2 nrm = (bestLine.delta.y, -bestLine.delta.x).Unit();
		if(bestSide == Line.back) nrm = -nrm;
		hce_perchAngle = atan2(nrm.y, nrm.x);
		hce_perchPos = (bestHit.xy + nrm * (radius + 3), bestHit.z - height * 0.5);
		hce_perch = 1; hce_perchTics = 35 * 4;
	}

	void HCE_LeavePerch()
	{
		if(hce_perch == 2) HCE_ApplyAnim(hce_perchSide ? 'perch right exit' : 'perch left exit', 3, false);
		hce_curAnimKind = -1;
		hce_perch = 0; hce_animLock = 0;
		hce_perchNext = level.maptime + 35 * random(8, 15);
		bNOGRAVITY = true;
		vel.xy = AngleToVector(hce_perchAngle, 4);
	}

	void HCE_PerchTick()
	{
		if(hce_perch == 1)
		{
			if(--hce_perchTics <= 0) { hce_perch = 0; return; }
			vector3 dv = level.Vec3Diff(pos, hce_perchPos);
			if(dv.Length() < 10)
			{
				SetOrigin(hce_perchPos, true);
				vel = (0, 0, 0);
				A_SetAngle(hce_perchAngle);
				hce_perch = 2; hce_perchTics = target ? 35 * random(3, 6) : 35 * random(8, 20);
				hce_curAnim = hce_perchSide ? 'perch right enter' : 'perch left enter';
				HCE_ApplyAnim(hce_curAnim, 3, false);
				hce_perchEnter = 20;
				A_StopSound(CHAN_7);
				A_StartSound("HCE/Drone/Stick", CHAN_6, CHANF_OVERLAP, 0.9);
				hce_curAnimKind = -1;
				return;
			}
			HCE_Move(atan2(dv.y, dv.x), hce_runSpeed);
			vel.z = clamp(dv.z * 0.15, -5, 5);
			A_SetAngle(hce_moveAngle, SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		// clinging: hold still with our back to the wall, shoot what we see from here
		vel = (0, 0, 0);
		if(pos != hce_perchPos) SetOrigin(hce_perchPos, true);
		A_SetAngle(hce_perchAngle);
		hce_animLock = 2;                                   // keeps the base AI from walking us off the wall
		if(hce_perchEnter > 0) { hce_perchEnter--; return; }
		if(hce_curAnimKind != -2) { hce_curAnim = hce_perchSide ? 'perch right idle' : 'perch left idle'; HCE_ApplyAnim(hce_curAnim, 4, true); hce_curAnimKind = -2; }
		if(--hce_perchTics <= 0 || (target && Distance2D(target) < 96)) { HCE_LeavePerch(); return; }
		if(target && hce_canSee && abs(DeltaAngle(hce_perchAngle, AngleTo(target))) < 80) HCE_UpdateFiring(Distance2D(target));
	}

	override void Tick()
	{
		if(health > 0 && !isFrozen() && hce_perch) bNOGRAVITY = true;
		super.Tick();
		if(hce_lastAir == 1 && hce_airPhase == 2) A_StartSound("HCE/Drone/BodyFall", CHAN_BODY, CHANF_OVERLAP, 0.8);
		hce_lastAir = hce_airPhase;
		if(health <= 0 || isFrozen() || bDORMANT) return;
		// wing buzz while airborne (one 1.1 s clip after another)
		if(!hce_perch && --hce_buzzTics <= 0) { hce_buzzTics = 37; A_StartSound("HCE/Drone/Fly", CHAN_7, 0, 0.55, ATTN_NORM); }
		if(hce_perch) { HCE_PerchTick(); return; }
		HCE_DroneAltitude();
		if(hce_dartTics > 0)
		{
			hce_dartTics--;
			HCE_Move(hce_dartAngle, hce_runSpeed * 1.8);
			HCE_Play(DeltaAngle(angle, hce_dartAngle) > 0 ? HCE_A_MOVE_L : HCE_A_MOVE_R);
		}
		// idle drones go and rest on a wall now and then
		if(!target && level.maptime >= hce_perchNext && random(0, 60) == 0) HCE_TryPerch();
	}

	// a dead drone scatters the swarm around it
	override void HCE_Die()
	{
		if(hce_perch) { hce_perch = 0; bNOGRAVITY = false; }
		super.HCE_Die();
		let it = BlockThingsIterator.Create(self, 400);
		while(it.Next())
		{
			let d = HCE_DroneBase(it.thing);
			if(!d || d == self || d.health <= 0) continue;
			if(d.hce_perch) d.HCE_LeavePerch();
			d.hce_scatterTics = random(30, 80);
			d.hce_zigOff = frandom(-60, 60);
			d.HCE_Say('Panic', 0.6, 35 * 2);
		}
	}
