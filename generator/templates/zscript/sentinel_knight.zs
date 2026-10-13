	// ---- Sentinel Knight: its core's colour, rolled once from its rank's palette (cold for the grey Knights, warm for
	// the gold commanders), and its phase: it sinks into the ground in a burst of hard light and rises out of it
	// somewhere else, around its target. It phases when its shield is down and it is under fire, or to close in on a
	// target far away; never more often than every 6-10 s
	bool hce_coreSet, hce_debugPhase;
	color hce_coreCol;                     // the core's colour (its embers when it dies)
	int hce_phase, hce_phaseTics, hce_phaseNext, hce_hurtAt, hce_phaseOff;

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
			case 0: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_orange.png', CMDL_USESURFACESKIN); hce_coreCol = "FF8519"; break;
			case 1: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_amber.png', CMDL_USESURFACESKIN); hce_coreCol = "FFC238"; break;
			case 2: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_red.png', CMDL_USESURFACESKIN); hce_coreCol = "FF421F"; break;
			default: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_gold.png', CMDL_USESURFACESKIN); hce_coreCol = "FFE073"; break;
			}
			return;
		}
		switch(random(0, 3))
		{
		case 0: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_cyan.png', CMDL_USESURFACESKIN); hce_coreCol = "33D9FF"; break;
		case 1: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_ice.png', CMDL_USESURFACESKIN); hce_coreCol = "73A6FF"; break;
		case 2: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_violet.png', CMDL_USESURFACESKIN); hce_coreCol = "9461FF"; break;
		default: A_ChangeModel('None', 0, "", 'None', {CORE}, "{SKINS}", 'core_teal.png', CMDL_USESURFACESKIN); hce_coreCol = "1FF2B8"; break;
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

	// ---- its voice (HCE/SentinelKnight/<line>, the Sentinels pack's sndinfo.knight): the generic events HCE_Say gets
	// become the Knight's lines for what it is looking at; the events it has no line for (pain, death...) stay silent
	bool hce_allyGreeted, hce_saidFirstFlood;
	int hce_carrierWarnAt;

	// what a Knight sees or kills, by class: 0 nothing it has a line for, 1 a Flood combat form, 2 an infection form,
	// 3 a carrier (or the Flood Grunt, which bursts the same way), 4 an Elite, 5 a Grunt, 6 a Jackal, 7 a Brute,
	// 8 other Covenant, 9 a Hunter, 10 a human, 11 a player, 12 a Doom monster, 13 a big one, 14 a Drinol (the Digsite's
	// war beasts)
	static int HCE_KnightKind(Actor a)
	{
		if(!a) return 0;
		if(a.player) return 11;
		String c = a.GetClassName(); c = c.MakeLower();
		if(c.IndexOf("drinol") >= 0) return 14;
		if(c.IndexOf("flood") >= 0)
			return c.IndexOf("carrier") >= 0 || c.IndexOf("floodgrunt") >= 0 ? 3 : c.IndexOf("infection") >= 0 ? 2 : 1;
		if(c.IndexOf("hunter") >= 0) return 9;
		if(c.IndexOf("elite") >= 0 || c.IndexOf("zealot") >= 0) return 4;
		if(c.IndexOf("grunt") >= 0) return 5;
		if(c.IndexOf("jackal") >= 0) return 6;
		if(c.IndexOf("brute") >= 0) return 7;
		if(c.IndexOf("drone") >= 0 || c.IndexOf("bugger") >= 0 || c.IndexOf("engineer") >= 0 || c.IndexOf("prophet") >= 0) return 8;
		if(HCE_TeamOf(a) == HCE_TEAM_HUMAN || c.IndexOf("marine") >= 0 || c.IndexOf("odst") >= 0 || c.IndexOf("zombie") >= 0
			|| c == "shotgunguy" || c == "chaingunguy" || c == "wolfensteinss") return 10;
		if(a.bISMONSTER) return a.SpawnHealth() >= 1000 ? 13 : 12;
		return 0;
	}

	// on the level the Flood first appears on (hce_floodlevel), the first Knight to meet it says so
	bool HCE_FirstFloodLine()
	{
		if(HCE_ReplaceHandler.LevelIndex() != HCE_ReplaceHandler.FloodLevel()) return false;
		let it = ThinkerIterator.Create('HCE_SentinelKnightBase');
		HCE_SentinelKnightBase k;
		while(k = HCE_SentinelKnightBase(it.Next())) if(k.hce_saidFirstFlood) return false;
		hce_saidFirstFlood = true;
		return true;
	}

	// the player by the Spartan class he plays (HaloDoom Evolved's HaloSpartan_II, _III and _IV; Doom's marine and
	// anything else: the plain lines)
	static Name HCE_SpartanLine(Actor a)
	{
		for(class<Object> c = a.GetClass(); c; c = c.GetParentClass())
		{
			Name n = c.GetClassName();
			if(n == 'HaloSpartan_II') return 'SpotSpartanII';
			if(n == 'HaloSpartan_III') return 'SpotSpartanIII';
			if(n == 'HaloSpartan_IV') return 'SpotSpartanIV';
		}
		return 'SpotPlayer';
	}

	Name HCE_SpotLine(Actor a)
	{
		switch(HCE_KnightKind(a))
		{
		case 11: return bFRIENDLY ? 'SpotPlayerAlly' : HCE_SpartanLine(a);
		case 1: case 2: return HCE_FirstFloodLine() ? 'FirstFlood' : 'SpotFlood';
		case 3: return Distance3D(a) < 400 ? 'CarrierBlow' : HCE_FirstFloodLine() ? 'FirstFlood' : 'SpotFlood';
		case 4: case 5: case 6: case 7: case 8: return 'SpotCovenant';
		case 9: return 'SpotHunter';
		case 10: return 'SpotHuman';
		case 14: return 'SpotDrinol';
		}
		return 'None';
	}

	Name HCE_KillLine(Actor a)
	{
		switch(HCE_KnightKind(a))
		{
		case 1: return random(0, 2) == 0 ? 'SanitizeFlood' : random(0, 1) ? 'KillCombatForm' : 'KillFlood';
		case 2: case 3: return random(0, 2) == 0 ? 'SanitizeFlood' : 'KillFlood';
		case 4: return 'KillElite';
		case 5: return 'KillGrunt';
		case 6: return 'KillJackal';
		case 7: return 'KillBrute';
		case 9: case 13: case 14: return 'KillHeavy';
		case 10: case 11: return 'KillHuman';
		}
		return 'None';
	}

	override void HCE_Say(Name ev, double chance, int cooldown, bool force)   // (an override takes no defaults: callers here pass all four)
	{
		Name line = 'None';
		switch(ev)
		{
		case 'Alert': case 'FoundFoe': case 'Sword': case 'Sniper': case 'UpThere': case 'DownThere':
			line = HCE_SpotLine(target); break;
		case 'KillPlayer': line = 'KillHuman'; break;
		case 'Taunt':                  // (said when its target falls, and as chatter between bursts: only the kills get a line)
			if(target && target.health <= 0) { line = HCE_KillLine(target); chance = max(chance, 0.6); }
			break;
		case 'EnemyGrenade': line = 'SpotGrenade'; break;
		case 'Stuck': line = 'PlasmaStuck'; break;
		case 'SearchStart': case 'SearchFail': case 'SearchClear': case 'Investigate': case 'HeardGunfire': case 'KeepWatch':
			line = 'Search'; break;
		case 'CarrierBlow': case 'SpotPlayerAlly': line = ev; break;
		}
		if(line == 'None') return;
		if(hce_debugPhase) Console.Printf("HCEVOICE %s %s -> %s (%s)", GetClassName(), ev, line, target ? target.GetClassName() : 'none');
		super.HCE_Say(line, chance, cooldown, force);
	}

	// a carrier form close by, or (a friendly Knight) the player
	void HCE_KnightWatch()
	{
		if(hce_phase != 0 || (level.maptime + hce_phaseOff) % 15) return;
		if(level.maptime >= hce_carrierWarnAt)
		{
			let it = BlockThingsIterator.Create(self, 260);
			while(it.Next())
			{
				Actor a = it.thing;
				if(a == self || a.health <= 0 || !a.bISMONSTER || Distance3D(a) > 260 || HCE_KnightKind(a) != 3 || !CheckSight(a)) continue;
				HCE_Say('CarrierBlow', 1.0, 35 * 3, false);
				hce_carrierWarnAt = level.maptime + 35 * 8;
				break;
			}
		}
		if(bFRIENDLY && !hce_allyGreeted)
			for(int i = 0; i < MAXPLAYERS; i++)
			{
				if(!playeringame[i] || !players[i].mo || Distance3D(players[i].mo) > 400 || !CheckSight(players[i].mo)) continue;
				hce_allyGreeted = true;
				HCE_Say('SpotPlayerAlly', 1.0, 35 * 3, true);
				break;
			}
	}

	// ---- death (Halo 4): the Knight's own death animation (it twitches and comes apart, its pieces jittering loose) as it
	// burns away into hard-light embers in its core's colour rising off it; nothing is
	// left behind but the guns it drops
	const HCE_DISSOLVE_TICS = 105;          // the death animation's length (90 frames at 30 fps)
	int hce_dissolve;
	override void HCE_Die()
	{
		super.HCE_Die();
		hce_airPhase = 0;                                     // no fall-and-land: it dies where it stands
		vel = (0, 0, 0);
		HCE_ApplyAnim('stand landing-dead', 8, false); hce_curAnim = 'stand landing-dead'; hce_curAnimKind = -1;
		hce_animLock = HCE_DISSOLVE_TICS + 10;
		hce_dissolve = 1;
		bSHOOTABLE = false; bSOLID = false;
		A_StartSound("Halo/Weapons/BinaryRifle/Zoom/IN", CHAN_7, CHANF_OVERLAP, 1.0, ATTN_NORM, 0.6);
	}

	void HCE_DissolveTick()
	{
		double f = double(hce_dissolve) / HCE_DISSOLVE_TICS;          // 0 .. 1: how far gone
		color core = hce_coreCol ? hce_coreCol : color(255, 255, 154, 48);
		color hot = color(255, min(255, core.r + 110), min(255, core.g + 110), min(255, core.b + 110));   // its white-hot specks
		// embers: from the parts still there (the top first, burning down), rising and fading
		int n = 1 + int(f * 8);
		for(int i = 0; i < n; i++)
		{
			double z = height * frandom(0, 1 - f * 0.6);
			A_SpawnParticle(random(0, 3) ? core : hot, SPF_FULLBRIGHT, random(18, 32), frandom(1.5, 4), 0,
				frandom(-radius, radius) * 0.8, frandom(-radius, radius) * 0.8, z,
				frandom(-0.4, 0.4), frandom(-0.4, 0.4), frandom(0.6, 1.8), 0, 0, 0.02, 1.0, -0.04);
		}
		// the glitch: it flickers and jolts, more as it goes
		// whole while it falls apart, then fading and flickering out over the second half
		double a = clamp(1.0 - (f - 0.45) / 0.5, 0, 1);
		if(f > 0.45 && random(0, 9) < 1 + int(f * 4)) a *= frandom(0.2, 0.7);
		A_SetRenderStyle(a, a < 1 ? STYLE_Translucent : STYLE_Normal);
		if(++hce_dissolve > HCE_DISSOLVE_TICS)
		{
			for(int i = 0; i < 20; i++)                               // the last of it scatters
				A_SpawnParticle(core, SPF_FULLBRIGHT, 24, frandom(2, 4), 0, frandom(-radius, radius), frandom(-radius, radius),
					frandom(0, height * 0.6), frandom(-1.5, 1.5), frandom(-1.5, 1.5), frandom(0.5, 2.5), 0, 0, 0, 1.0, -0.04);
			if(hce_shellActor) hce_shellActor.Destroy();
			Destroy();
		}
	}

	override void Tick()
	{
		if(hce_dissolve > 0 && !isFrozen()) { HCE_DissolveTick(); if(bDestroyed) return; }
		super.Tick();
		if(isFrozen()) return;
		if(!hce_coreSet && GetAge() >= 1)
		{
			hce_coreSet = true; HCE_KnightCore();
			hce_phaseOff = random(0, 14);
		}
		if(health <= 0) { hce_phase = 0; return; }
		HCE_KnightWatch();
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
