	// ---- Sentinel Knight: its core's colour, rolled once from its rank's palette (cold for the grey Knights, warm for
	// the gold commanders), and its phase: it sinks into the ground in a burst of hard light and rises out of it
	// somewhere else, around its target. It phases when its shield is down and it is under fire, or to close in on a
	// target far away; never more often than every 6-10 s
	bool hce_coreSet, hce_debugPhase;
	int hce_phase, hce_phaseTics, hce_phaseNext, hce_hurtAt;

	override void HCE_OnDamaged(Actor inflictor, Actor source, int dealt, Name mod)
	{
		super.HCE_OnDamaged(inflictor, source, dealt, mod);
		hce_hurtAt = level.maptime;
	}

	virtual int HCE_KnightPalette() { return 0; }

	void HCE_KnightCore()
	{
		if(HCE_KnightPalette() == 1)
		{
			switch(random(0, 3))
			{
			case 0: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_orange.png', CMDL_USESURFACESKIN); break;
			case 1: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_amber.png', CMDL_USESURFACESKIN); break;
			case 2: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_red.png', CMDL_USESURFACESKIN); break;
			default: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_gold.png', CMDL_USESURFACESKIN); break;
			}
			return;
		}
		switch(random(0, 3))
		{
		case 0: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_cyan.png', CMDL_USESURFACESKIN); break;
		case 1: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_ice.png', CMDL_USESURFACESKIN); break;
		case 2: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_violet.png', CMDL_USESURFACESKIN); break;
		default: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_teal.png', CMDL_USESURFACESKIN); break;
		}
	}

	void HCE_PhaseBurst()
	{
		for(int i = 0; i < 24; i++)
			A_SpawnParticle("FFB040", SPF_FULLBRIGHT, 20, frandom(3, 6), 0, frandom(-radius, radius), frandom(-radius, radius), frandom(0, height),
				frandom(-1, 1), frandom(-1, 1), frandom(0.5, 2.5), 0, 0, 0, 1.0, -0.05);
		A_StartSound("Halo/Weapons/BinaryRifle/Zoom/IN", CHAN_7, CHANF_OVERLAP, 0.9);
	}

	// somewhere 160-400 units from the target, on the floor, in sight of it; false when no such place turns up
	bool HCE_PhaseSpot()
	{
		if(!target) return false;
		vector3 old = pos;
		for(int i = 0; i < 12; i++)
		{
			double a = frandom(0, 360), d = frandom(160, 400);
			vector2 p = target.pos.xy + AngleToVector(a, d);
			double fz = GetZAt(p.x, p.y, 0, GZF_ABSOLUTEPOS);
			SetOrigin((p.x, p.y, fz), false);
			if(TestMobjLocation() && CheckSight(target) && pos.z - fz < 1)
			{
				A_SetAngle(AngleTo(target));
				return true;
			}
		}
		SetOrigin(old, false);
		return false;
	}

	override void Tick()
	{
		super.Tick();
		if(isFrozen()) return;
		if(!hce_coreSet && GetAge() >= 1) { hce_coreSet = true; HCE_KnightCore(); }
		if(health <= 0) { hce_phase = 0; return; }
		if(hce_phase == 0)
		{
			if(!target || level.maptime < hce_phaseNext || hce_dummy) return;      // (it phases out of a flinch too)
			double d = Distance2D(target);
			bool exposed = hce_shieldMax > 0 && !HCE_ShieldUp() && level.maptime - hce_hurtAt < 35;
			if(!(exposed && frandom(0, 1) < 0.08) && !(d > 900 && frandom(0, 1) < 0.01)) return;
			// phase out: sink into the ground, untouchable from halfway down
			hce_phase = 1; hce_phaseTics = {OUT_TICS};
			if(hce_debugPhase) Console.Printf("HCEPHASE out %s at %.0f %.0f", GetClassName(), pos.x, pos.y);
			HCE_ApplyAnim('knight phase-out', 3, false); hce_curAnim = 'knight phase-out'; hce_curAnimKind = -1;
			hce_animLock = {OUT_TICS} + {IN_TICS} + 12;
			vel = (0, 0, 0);
			HCE_PhaseBurst();
			return;
		}
		vel.xy = (0, 0);
		if(--hce_phaseTics > 0)
		{
			if(hce_phase == 1 && hce_phaseTics == {OUT_TICS} / 2) { bSHOOTABLE = false; A_SetRenderStyle(0.5, STYLE_Translucent); }
			if(hce_phase == 2 && hce_phaseTics == {IN_TICS} / 2) { bSHOOTABLE = true; A_SetRenderStyle(1.0, STYLE_Normal); }
			return;
		}
		if(hce_phase == 1)
		{
			// gone: a beat under the ground, then up again somewhere else (where it went down, if nowhere fits)
			hce_phase = 3; hce_phaseTics = 12;
			bINVISIBLE = true;
			HCE_PhaseSpot();
			return;
		}
		if(hce_phase == 3)
		{
			bINVISIBLE = false;
			hce_phase = 2; hce_phaseTics = {IN_TICS};
			HCE_ApplyAnim('knight phase-in', 0, false); hce_curAnim = 'knight phase-in'; hce_curAnimKind = -1;
			HCE_PhaseBurst();
			return;
		}
		// risen
		if(hce_debugPhase) Console.Printf("HCEPHASE in %s at %.0f %.0f", GetClassName(), pos.x, pos.y);
		hce_phase = 0; bSHOOTABLE = true; bINVISIBLE = false; A_SetRenderStyle(1.0, STYLE_Normal);
		hce_animLock = 0;
		hce_phaseNext = level.maptime + 35 * random(6, 10);
	}
