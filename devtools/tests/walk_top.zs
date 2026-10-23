class HCE_WalkTest : EventHandler
{
	Array<Actor> nds; double wpX, wpY; Array<double> lastX, lastY; Array<int> stuckN;
	override void WorldTick()
	{
		let pl = players[0].mo; if(!pl) return;
		int t = level.maptime;
		if(t == 5) { for(int k = 0; k < 4; k++) { lastX.Push(0); lastY.Push(0); stuckN.Push(0); } }
		// Chief wanders: every 2 s a new point in sight within 500, walked to under his own physics; 4 Marines follow
		if(t == 5)
		{
			for(int k = 0; k < 4; k++)
			{
				vector2 p = pl.pos.xy + Actor.AngleToVector(pl.angle + 150 + k * 20, 64 + 24 * k);
				let m = Actor.Spawn("HCE_MarineAssaultRifle", (p, pl.pos.z));
				if(m) { HaloDoom_EnemyBase(m).hce_dummy = false; nds.Push(m); if(!m.TestMobjLocation()) m.SetOrigin(pl.pos, false); }
			}
			wpX = pl.pos.x; wpY = pl.pos.y;
		}
		if(t >= 5)
		{
			if(t % 70 == 0 || (pl.pos.xy - (wpX, wpY)).Length() < 48)
			{
				for(int k = 0; k < 12; k++)
				{
					double a = frandom(0, 360);
					FLineTraceData d;
					pl.LineTrace(a, 540, 0, TRF_THRUACTORS, 24, data: d);
					double dist = d.HitType == TRACE_HitNone ? 540 : d.Distance - 40;
					if(dist < 96) continue;
					vector2 q = pl.pos.xy + Actor.AngleToVector(a, dist);
					Sector s = level.PointInSector(q);
					if(!s || s.damageamount > 0 || abs(s.floorplane.ZatPoint(q) - pl.pos.z) > 24 || s.ceilingplane.ZatPoint(q) - s.floorplane.ZatPoint(q) < 64) continue;
					wpX = q.x; wpY = q.y; break;
				}
			}
			vector2 dv = (wpX, wpY) - pl.pos.xy;
			if(dv.Length() > 8) { pl.vel.xy = dv.Unit() * 9; pl.angle = atan2(dv.y, dv.x); }
			if(t % 70 == 35)
			{
				for(int i = 0; i < nds.Size(); i++)
				{
					let e = HaloDoom_EnemyBase(nds[i]); if(!e) continue;
					double moved = (e.pos.xy - (lastX[i], lastY[i])).Length();
					double dp = e.Distance2D(pl);
					bool wanted = dp > 160 || e.hce_moveSpeed > 0;
					if(wanted && moved < 12)
					{
						stuckN[i]++;
						Line bl = e.BlockingLine;
						Console.Printf("HCEPREV STUCK t%d m%d pos %.0f %.0f z %.0f dplayer %.0f act %d ord %d ms %.1f ang %.0f wait %d unstick %d path %d see%d bm %s bl %d fl %d f1 %.0f f2 %.0f ch %.0f sec %d fz %.0f dropoff %.0f lk %d", t, i, e.pos.x, e.pos.y, e.pos.z, dp, e.hce_action, e.hce_squadOrder, e.hce_moveSpeed, e.hce_moveAngle, e.hce_waitTics, e.hce_unstickTics, e.hce_pathX.Size(), e.InStateSequence(e.CurState, e.FindState("See")),
							e.BlockingMobj ? e.BlockingMobj.GetClassName() : '-', bl ? bl.Index() : -1, bl ? bl.flags : 0,
							bl ? bl.frontsector.floorplane.ZatPoint(e.pos.xy) : 0, bl && bl.backsector ? bl.backsector.floorplane.ZatPoint(e.pos.xy) : 0, bl && bl.backsector ? bl.backsector.ceilingplane.ZatPoint(e.pos.xy) - bl.backsector.floorplane.ZatPoint(e.pos.xy) : 0,
							e.CurSector.Index(), e.floorz, e.dropoffz, e.hce_animLock);
					}
					lastX[i] = e.pos.x; lastY[i] = e.pos.y;
				}
			}
		}
		if(t == WALKDUR - 5)
		{
			String st = "";
			for(int i = 0; i < nds.Size(); i++) { let e = HaloDoom_EnemyBase(nds[i]); st.AppendFormat(" m%d stuck %d dist %.0f", i, stuckN[i], e ? e.Distance2D(pl) : -1); }
			Console.Printf("HCEPREV SUMMARY%s", st);
		}
	}
}
