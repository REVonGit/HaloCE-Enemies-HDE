	// HCE_JawShut(): degrees about the jaw hinge from its bind pose to shut (negative: closing), per face; build_pack.jaw_shut writes it beside this
	int hce_lipPhase;
	double hce_lipOpen;
	// Lip sync: every third tic (offset by hce_lipPhase) opens the jaw while the actor is talking on CHAN_VOICE, from
	// two out-of-step sine waves plus jitter, and holds it shut (HCE_JawShut) otherwise. Rotates the 'bip01 ponytail1'
	// bone, which is the jaw on these heads. To change how wide it opens, edit the 14.0 degrees.
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
		// set every third tic, not only on a change: a model change (the kit, a picked-up gun) can drop the override
		hce_lipOpen = want;
		// the heads' bind pose leaves the jaw some 10 degrees open (the mouth hanging): at rest it is held shut
		// (HCE_JawShut), and speech opens it from there
		double a = HCE_JawShut() + want * 14.0;
		SetNamedBoneRotation('bip01 ponytail1', Quat(0, 0, sin(a / 2), cos(a / 2)), SB_ADD, 3);
	}
