	// ---- Halo 2's Sentinel (extract_h2_sentinels.py): the shielded ranks (HCE_HasBubble) wear Halo 2's shield bubble
	// (surface {SURF}) while their shield holds; the others keep Halo CE's unseen shield
	int hce_bubble;
	virtual bool HCE_HasBubble() { return false; }

	override void Tick()
	{
		super.Tick();
		if(isFrozen()) return;
		int st = (health > 0 && HCE_HasBubble() && hce_shieldMax > 0 && HCE_ShieldUp()) ? 1 : 2;
		if(st == hce_bubble) return;
		hce_bubble = st;
		A_ChangeModel('None', 0, "", 'None', {SURF}, "models/{MDIR}/weapons", st == 1 ? 'None' : 'hce_hidden.png', CMDL_USESURFACESKIN);
	}
