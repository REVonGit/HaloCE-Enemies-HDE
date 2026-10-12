	// the Flood Grunt bursts like a carrier, a smaller one: 2-4 infection forms
	override void HCE_OnDetonate()
	{
		Name n = 'HCE_FloodInfection';
		class<Actor> ic = (class<Actor>)(n);
		if(!ic) return;
		int count = random(2, 4);
		for(int i = 0; i < count; i++)
		{
			let f = Spawn(ic, pos + (frandom(-8, 8), frandom(-8, 8), height * 0.5), ALLOW_REPLACE);
			if(f) { f.vel = (frandom(-4, 4), frandom(-4, 4), frandom(3, 6)); f.target = target; f.SetStateLabel("See"); }
		}
	}
	override Sound HCE_PopSound() { return "HCE/FloodCarrier/Pop"; }
