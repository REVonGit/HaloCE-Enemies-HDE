
	// the sticky detonator's muzzle: the charge seated in it when loaded, the empty muzzle once fired, until it
	// reloads (setting the charges off is the API's: HCE_StickyTick, for any Marine carrying one)
	int hce_stickyReload;
	// After a sticky charge is fired, swaps the muzzle model to its empty state and sets the reload 45 tics out;
	// skipped once the Marine has picked up a different gun.
	override void HCE_OnShot(Actor shot)
	{
		super.HCE_OnShot(shot);
		if(hce_hasLoadout) return;             // traded / picked up something else: not this gun any more
		HCE_StickyFired();
		hce_stickyReload = level.maptime + 45;
	}
	// Swaps the muzzle surface to the loaded charge; the body is filled in by build_pack (overlay_swap, 'sticky_detonator').
	void HCE_StickyLoaded()
	{
%STICKY_LOADED%	}
	// Swaps the muzzle surface to the empty muzzle; filled in by build_pack (overlay_swap, 'sticky_detonator_fired').
	void HCE_StickyFired()
	{
%STICKY_FIRED%	}
	// Per tic: when the reload time has passed on a live Marine still carrying this gun, shows the charge again.
	// To change the reload, edit the 45 in HCE_OnShot.
	override void Tick()
	{
		super.Tick();
		if(hce_stickyReload > 0 && level.maptime >= hce_stickyReload && health > 0) { hce_stickyReload = 0; if(!hce_hasLoadout) HCE_StickyLoaded(); }
	}
