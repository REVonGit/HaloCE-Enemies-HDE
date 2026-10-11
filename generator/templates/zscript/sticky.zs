
	// the sticky detonator's muzzle: the charge seated in it when loaded, the empty muzzle once fired, until it
	// reloads (setting the charges off is the API's: HCE_StickyTick, for any Marine carrying one)
	int hce_stickyReload;
	override void HCE_OnShot(Actor shot)
	{
		super.HCE_OnShot(shot);
		if(hce_hasLoadout) return;             // traded / picked up something else: not this gun any more
		HCE_StickyFired();
		hce_stickyReload = level.maptime + 45;
	}
	void HCE_StickyLoaded()
	{
%STICKY_LOADED%	}
	void HCE_StickyFired()
	{
%STICKY_FIRED%	}
	override void Tick()
	{
		super.Tick();
		if(hce_stickyReload > 0 && level.maptime >= hce_stickyReload && health > 0) { hce_stickyReload = 0; if(!hce_hasLoadout) HCE_StickyLoaded(); }
	}
