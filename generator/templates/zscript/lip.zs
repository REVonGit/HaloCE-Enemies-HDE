
	int hce_lipPhase;
	double hce_lipOpen;
	override void Tick()
	{
		super.Tick();
		if((level.maptime + hce_lipPhase) % 3) return;
		double want = 0;
		if(health > 0 && IsActorPlayingSound(CHAN_VOICE))
		{
			// syllables: two out-of-step waves, so the mouth opens irregularly, never wide for long
			double t = (level.maptime + hce_lipPhase) * 9.0;
			want = clamp(0.25 + 0.55 * abs(sin(t)) * (0.6 + 0.4 * abs(sin(t * 0.37 + 40))) + frandom[HCELip](-0.1, 0.15), 0, 1);
		}
		if(want == 0 && hce_lipOpen == 0) return;
		hce_lipOpen = want;
		double a = want * 10.0;
		SetNamedBoneRotation('bip01 ponytail1', Quat(0, 0, sin(a / 2), cos(a / 2)), SB_ADD, 3);
	}
