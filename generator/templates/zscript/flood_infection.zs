
	// infection forms hunt for dead humans / elites and reanimate them
	override bool HCE_SeekCorpse()
	{
		if(++hce_actionTics < 20) return false;
		hce_actionTics = 0;
		let it = BlockThingsIterator.Create(self, 512);
		Actor best = null; double bd = 1e9;
		while(it.Next())
		{
			let c = HaloDoom_EnemyBase(it.thing);
			if(!c || !c.bCORPSE || !c.hce_enabled || c.bHCE_Resurrects || c.hce_gibbed) continue;
			if(c.hce_team != HCE_TEAM_HUMAN && c.hce_team != HCE_TEAM_COVENANT) continue;
			if(c.hce_type != 0 && c.hce_type != 7) continue;   // elites and marines only
			double d = Distance2D(c);
			if(d < bd) { bd = d; best = c; }
		}
		if(!best) return false;
		hce_feedTarget = best;
		hce_action = HCE_ACT_FEED;
		return true;
	}
	// The feed action set up by HCE_SeekCorpse: walks to the chosen corpse, then plays the feed animation for 3 s and
	// replaces the corpse with a combat form (Elite or human, by hce_type), which plays its rise animation and goes to
	// See. The infection form destroys itself. Aborts to idle if the corpse is gone or no longer a corpse.
	override void HCE_Feed()
	{
		let c = hce_feedTarget;
		if(!c || !c.bCORPSE) { hce_action = HCE_ACT_IDLE; hce_feedTarget = null; return; }
		if(Distance2D(c) > radius + c.radius + 4)
		{
			HCE_Move(AngleTo(c), hce_runSpeed);
			A_SetAngle(AngleTo(c), SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		if(hce_curAnimKind != HCE_A_FEED) { HCE_Play(HCE_A_FEED, true, true); hce_leapState = 0; hce_reviveTics = 35 * 3; return; }
		if(--hce_reviveTics > 0) return;
		Name nc = HaloDoom_EnemyBase(c).hce_type == 0 ? 'HCE_FloodcombatEliteUnarmed' : 'HCE_FloodcombatHumanUnarmed';
		class<Actor> cc = (class<Actor>)(nc);
		if(cc)
		{
			let f = Spawn(cc, c.pos, ALLOW_REPLACE);
			if(f)
			{
				f.angle = c.angle;
				let fe = HaloDoom_EnemyBase(f);
				if(fe && fe.HCE_HasAnim(HCE_A_RESURRECT_F)) fe.HCE_PlayLocked(HCE_A_RESURRECT_F);
				f.SetStateLabel("See");
			}
			c.Destroy();
		}
		Destroy();
	}
	override Sound HCE_PopSound() { return "HCE/FloodInfection/Pop"; }
