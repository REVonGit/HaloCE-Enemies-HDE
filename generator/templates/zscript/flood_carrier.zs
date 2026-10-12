
	// carrier pop: releases infection forms
	override void HCE_OnDetonate()
	{
		Name n = 'HCE_FloodInfection';
		class<Actor> ic = (class<Actor>)(n);
		if(!ic) return;
		int count = random(5, 9);
		for(int i = 0; i < count; i++)
		{
			let f = Spawn(ic, pos + (frandom(-12, 12), frandom(-12, 12), height * 0.5), ALLOW_REPLACE);
			if(f)
			{
				f.vel = (frandom(-5, 5), frandom(-5, 5), frandom(3, 7));
				f.target = target;
				f.SetStateLabel("See");
			}
		}
	}
	override Sound HCE_PopSound() { return "HCE/FloodCarrier/Pop"; }
