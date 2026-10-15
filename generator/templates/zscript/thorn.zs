
	// heavy footfalls from its own sound set while it walks
	int hce_stepTics;
	// Plays the Thorn Beast's step sound every 16 tics while it is alive, on the floor and moving faster than 1.5
	// units/tic. To change the footfall rate, edit the 16.
	override void Tick()
	{
		super.Tick();
		if(health <= 0 || pos.z > floorz + 2 || vel.xy.Length() < 1.5) return;
		if(++hce_stepTics >= 16) { hce_stepTics = 0; A_StartSound("HCE/ThornBeast/Step", CHAN_BODY, CHANF_OVERLAP, 0.8); }
	}
