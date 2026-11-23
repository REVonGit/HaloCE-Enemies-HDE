	// the Flood Grunt bursts like a carrier, a smaller one: 2-4 infection forms
	override void HCE_OnDetonate()
	{
		Name n = 'HCE_FloodInfection';
		class<Actor> ic = (class<Actor>)(n);
		if(!ic) return;
		HCE_ReleaseForms(ic, random(2, 4), 5);
	}
	override Sound HCE_PopSound() { return "HCE/FloodCarrier/Pop"; }
	override bool HCE_BurstsOnDeath() { return true; }   // gone in its burst, as a carrier is: no body left
