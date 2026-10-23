		if(t == 30)
		{
			let h = HCE_Encounters(EventHandler.Find("HCE_Encounters"));
			let it = ThinkerIterator.Create("HaloDoom_EnemyBase"); HaloDoom_EnemyBase m;
			while(m = HaloDoom_EnemyBase(it.Next()))
				if(m.hce_encounter && m.hce_team == HCE_TEAM_HUMAN)
				{
					int r = h && h.roomOf.Size() ? h.roomOf[m.CurSector.Index()] : -1;
					Console.Printf("HCEPREV ENC %s %.0f %.0f room %d area %.0f foes %d", m.GetClassName(), m.pos.x, m.pos.y, r, r >= 0 ? h.roomArea[r] : -1, r >= 0 ? h.roomFoes[r] : -1);
				}
		}
