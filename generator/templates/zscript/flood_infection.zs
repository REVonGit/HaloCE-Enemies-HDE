	// Infection forms hunt bodies and raise them as Flood: a dead Marine, Elite or Grunt comes back as the combat form
	// of its kind (HCE_HostForm), holding the gun it dropped if that still lies by the body; a fallen Flood combat form
	// is reanimated as it was (HCE_Revive). Out of a fight any body within 512 units; in one, only a body nearer than
	// the target and within 384. One infection form to a body (hce_feedBy).
	override bool HCE_SeekCorpse()
	{
		if(++hce_actionTics < 20) return false;
		hce_actionTics = 0;
		let it = BlockThingsIterator.Create(self, 512);
		Actor best = null; double bd = 1e9;
		while(it.Next())
		{
			let c = HaloDoom_EnemyBase(it.thing);
			if(!c || !c.bCORPSE || !c.hce_enabled || c.hce_gibbed) continue;
			if(c.hce_feedBy && c.hce_feedBy != self && c.hce_feedBy.health > 0) continue;
			if(!HCE_CanInfect(c)) continue;
			double d = Distance2D(c);
			if(d < bd) { bd = d; best = c; }
		}
		if(!best) return false;
		if(target && target.health > 0 && (bd > 384 || bd > Distance2D(target))) return false;   // the fight comes first
		hce_feedTarget = best;
		HaloDoom_EnemyBase(best).hce_feedBy = self;
		hce_action = HCE_ACT_FEED;
		return true;
	}
	// a body this infection form can take: a fallen Flood combat form that rises again, or a Marine, Elite or Grunt
	// with a Flood form of its own (not the Draeth or the Brutes)
	bool HCE_CanInfect(HaloDoom_EnemyBase c)
	{
		if(c.hce_team == HCE_TEAM_FLOOD) return c.bHCE_Resurrects && c.hce_reviveTics <= 0;
		if(c.bHCE_Resurrects) return false;
		String cn = c.GetClassName();
		if(cn.IndexOf("Draeth") >= 0 || cn.IndexOf("Brute") >= 0) return false;
		if(c.hce_team == HCE_TEAM_HUMAN) return c.hce_type == 7;
		if(c.hce_team == HCE_TEAM_COVENANT) return (c.hce_type == 0 && cn.IndexOf("Elite") >= 0) || (c.hce_type == 2 && cn.IndexOf("Grunt") >= 0);
		return false;
	}
	// The combat form a host becomes: its kind's Flood form carrying the host's gun if one does (and gun is set to the
	// dropped pickup by the body, taken with it), else its kind's unarmed form. To change who becomes what, edit the
	// lists: first match on the gun wins, the last entry is the unarmed fallback
	Name HCE_HostForm(HaloDoom_EnemyBase c, out Actor gun)
	{
		String ODST = "HCE_FloodcombatOdstAssaultRifle HCE_FloodcombatOdstShotgun HCE_FloodcombatOdstSniperRifle HCE_FloodcombatHumanArmoredPistol HCE_FloodcombatHumanArmoredRocketLauncher HCE_FloodcombatHumanArmoredUnarmed";
		String ARMORED = "HCE_FloodcombatHumanArmoredAssaultRifle HCE_FloodcombatHumanArmoredPistol HCE_FloodcombatHumanArmoredRocketLauncher HCE_FloodcombatHumanArmoredShotgun HCE_FloodcombatHumanArmoredSniperRifle HCE_FloodcombatHumanArmoredUnarmed";
		String MARINE = "HCE_FloodcombatHumanUnarmoredAssaultRifle HCE_FloodcombatHumanUnarmoredPistol HCE_FloodcombatHumanFlameThrower HCE_FloodcombatHumanNeedler HCE_FloodcombatHumanPlasmaPistol HCE_FloodcombatHumanPlasmaRifle HCE_FloodcombatHumanRocketLauncher HCE_FloodcombatHumanShotgun HCE_FloodcombatHumanUnarmoredUnarmed";
		String MINOR = "HCE_FloodcombatEliteMinorNeedler HCE_FloodcombatEliteMinorPlasmaPistol HCE_FloodcombatEliteMinorPlasmaRifle HCE_FloodcombatEliteMinorUnarmed";
		String MAJOR = "HCE_FloodcombatEliteMajorNeedler HCE_FloodcombatEliteMajorPlasmaPistol HCE_FloodcombatEliteMajorPlasmaRifle HCE_FloodcombatEliteMajorUnarmed";
		String ELITE = "HCE_FloodcombatEliteCommanderEnergySword HCE_FloodcombatEliteUltraFuelRod HCE_FloodcombatEliteAssaultRifle HCE_FloodcombatEliteFlameThrower HCE_FloodcombatEliteNeedler HCE_FloodcombatElitePistol HCE_FloodcombatElitePlasmaPistol HCE_FloodcombatElitePlasmaRifle HCE_FloodcombatEliteRocketLauncher HCE_FloodcombatEliteShotgun HCE_FloodcombatEliteSniperRifle HCE_FloodcombatEliteUnarmed";
		gun = null;
		String cn = c.GetClassName();
		if(c.hce_type == 2) return 'HCE_FloodGrunt';
		if(c.hce_type == 0 && cn.IndexOf("Stealth") >= 0) return 'HCE_FloodcombatEliteStealthUnarmed';
		// the host's dropped gun, if it still lies by the body
		Name w = c.hce_dropWeapon;
		if(w != 'None' && w != '')
		{
			let it = BlockThingsIterator.Create(c, 64);       // a plain Weapon, or HaloDoom Evolved's pickup proxy for one
			while(it.Next())
				if(it.thing != c && c.Distance2D(it.thing) < 64 && HCE_GroundWeaponClass(it.thing) == w) { gun = it.thing; break; }
		}
		Name wn = gun ? w : 'None';
		if(c.hce_type == 7) return cn.IndexOf("Odst") >= 0 ? HCE_PickForm(ODST, wn) : cn.IndexOf("Armored") >= 0 ? HCE_PickForm(ARMORED, wn) : HCE_PickForm(MARINE, wn);
		return cn.IndexOf("Minor") >= 0 ? HCE_PickForm(MINOR, wn) : cn.IndexOf("Major") >= 0 ? HCE_PickForm(MAJOR, wn) : HCE_PickForm(ELITE, wn);
	}
	// the first of the forms (space-separated class names) carrying gun w (its default hce_dropWeapon), else the last (the unarmed one)
	static Name HCE_PickForm(String list, Name w)
	{
		Array<String> forms; list.Split(forms, " ");
		for(int i = 0; i < forms.Size() - 1; i++)
		{
			class<Actor> k = forms[i];
			let d = k ? HaloDoom_EnemyBase(GetDefaultByType(k)) : null;
			if(d && w != 'None' && d.hce_dropWeapon == w) return forms[i];
		}
		return forms[forms.Size() - 1];
	}
	// The feed action set up by HCE_SeekCorpse: walks to the chosen body and plays the feed animation for 3 s. Then a
	// fallen Flood form gets up again; anyone else is replaced by its combat form (HCE_HostForm), which takes the
	// host's gun from the floor if it carries it, plays its rise animation and goes to See. The infection form is
	// spent. Aborts to idle if the body is gone or no longer a corpse.
	override void HCE_Feed()
	{
		let c = HaloDoom_EnemyBase(hce_feedTarget);
		if(!c || !c.bCORPSE || c.hce_gibbed) { hce_action = HCE_ACT_IDLE; hce_feedTarget = null; return; }
		if(Distance2D(c) > radius + c.radius + 4)
		{
			HCE_Move(AngleTo(c), hce_runSpeed);
			A_SetAngle(AngleTo(c), SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		if(hce_curAnimKind != HCE_A_FEED) { HCE_Play(HCE_A_FEED, true, true); hce_leapState = 0; hce_reviveTics = 35 * 3; return; }
		if(--hce_reviveTics > 0) return;
		c.hce_feedBy = null;
		if(c.hce_team == HCE_TEAM_FLOOD)
		{
			// it gets up holding its gun again: the one it dropped is taken back off the floor (and drops again when it dies)
			Name w = c.hce_dropWeapon;
			let it = BlockThingsIterator.Create(c, 64);
			while(w != 'None' && it.Next())
				if(it.thing != c && c.Distance2D(it.thing) < 64 && HCE_GroundWeaponClass(it.thing) == w) { it.thing.Destroy(); c.hce_gunDropped = false; break; }
			c.HCE_Revive();
			Destroy();
			return;
		}
		Actor gun;
		Name nc = HCE_HostForm(c, gun);
		class<Actor> cc = nc;
		if(cc)
		{
			let f = Spawn(cc, c.pos, ALLOW_REPLACE);
			if(f)
			{
				f.angle = c.angle;
				let fe = HaloDoom_EnemyBase(f);
				if(fe && gun && fe.hce_dropWeapon == c.hce_dropWeapon) gun.Destroy();     // it took the gun up
				if(fe && fe.HCE_HasAnim(HCE_A_RESURRECT_F)) fe.HCE_PlayLocked(HCE_A_RESURRECT_F);
				f.SetStateLabel("See");
			}
			c.Destroy();
		}
		Destroy();
	}
	override Sound HCE_PopSound() { return "HCE/FloodInfection/Pop"; }
