"""Digsite add-on pack: Drinol, Slug Man (particle beam rifle / plasma pistol) and plasma-carbine Elites in a
rifle stance.  Generated with build_pack.build() so the classes behave exactly like the main pack's.

Needs out/models/{Drinol,SlugMan,EliteRifle} (extract_digsite.py, extract_elite_rifle.py) and the weapon pkls
from extract_sketchfab.py.  Digsite content is licensed for MCC projects only: never part of a public release."""
import os, sys, json, copy, shutil, subprocess, glob
import numpy as np
from PIL import Image
import build_pack as bp
from looset import LooseMap
from extract_ai import dump, flatten_obj
from halosound import parse as parse_sound, decode, to_wav

from hce_paths import DIGSITE, DIG_PACK as PACK, HERE, OUT
T = DIGSITE + '/tags/'
S = bp.S

CARBINE = r'digsite\weapons\plasma carbine'
BEAM = r'digsite\weapons\particle beam'
PULSE = r'digsite\weapons\pulse carbine'
DRONE = r'characters\drone\drone'
BRUTE = r'characters\brute\brute'
CE_PR = r'weapons\plasma rifle\plasma rifle'
CE_AR = r'weapons\assault rifle\assault rifle'
CE_SG = r'weapons\shotgun\shotgun'
SPIKER = r'h3\weapons\spiker'
HAMMER = r'h2\weapons\gravity hammer'
# Halo 2 Brute ranks: body vitality from their char tags (08b: the honor guard inherits brute_major's); hlmt
# variant -> region permutations they wear; fur colours come from the biped's per-variant change colours.
# Loadouts (all rifle stance): CE plasma rifle / assault rifle / shotgun, the Majors carry the Spiker.
# The Chieftain is a custom rank: Tartarus's look, hammer stance and gravity hammer.
BRUTE_RANKS = {
    'minor': dict(body=175, variants=('minor_bth', 'minor_crl'), weapons=(CE_PR, CE_AR),
                  wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'default'), ('sensors', 'default')}),
    'major': dict(body=150, variants=('major_bth', 'major_crl'), weapons=(SPIKER, CE_SG),
                  wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'default'), ('sensors', 'default'),
                        ('sh_armor', 'default')}),
    'captain': dict(body=200, variants=('captain_bth', 'captain_crl'), weapons=(CE_PR, CE_SG),
                    wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'default'), ('sensors', 'default'),
                          ('sh_armor', 'default'), ('flag', 'captain')}),
    'honor guard': dict(body=150, variants=('minor_bth', 'minor_crl'), weapons=(CE_PR, CE_AR),
                        wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'honor_on'), ('sensors', 'honor_on'),
                              ('sh_armor', 'honor_on'), ('hg_arm', 'honor_on'), ('hg_legs', 'honor_on')}),
    'chieftain': dict(body=350, variants=('tartarus',), weapons=(HAMMER,),
                      wear={('body', 'default'), ('head', 'default'), ('helmet', 'honor_off'), ('helmet', 'tartarus'),
                            ('sensors', 'default'), ('sh_armor', 'skull'), ('hg_arm', 'honor_off'), ('hg_legs', 'honor_off')}),
}
ELITE_RIFLE = r'characters\elite\elite rifle'

CHIEFTAIN_BERSERK = {
    'IDLE': ['berserk hammer idle'], 'ALERT': ['berserk hammer idle'], 'MOVE_F': ['berserk hammer move-front'],
    'MOVE_B': ['berserk hammer move-front'], 'MOVE_L': ['berserk hammer move-front'], 'MOVE_R': ['berserk hammer move-front'],
    'FLEE': ['berserk hammer move-front'], 'TURN_L': ['stand melee turn-left'], 'TURN_R': ['stand melee turn-right'],
    'MELEE': ['berserk hammer melee 1', 'berserk hammer melee 2', 'stand melee melee%4', 'stand melee melee%5']}

def load_ai():
    m = LooseMap()
    variants, actors, bipeds = {}, {}, {}
    for vp in [r'digsite\characters\drinol\00_mac\drinol', r'digsite\characters\slug_man\slug_man particle beam',
               r'digsite\characters\slug_man\slug_man plasma pistol']:
        t = m.load(T + vp.replace('\\', '/') + '.actor_variant', vp)
        v = dump(m, 'actor_variant_definition', t['data'])
        v['change_colors_list'] = []
        ref = v['ranged_combat']['reference'] or ''
        if 'particle_beam' in ref: v['ranged_combat']['reference'] = BEAM
        ar, ur = v['actor_reference'], v['unit_reference']
        if ar not in actors:
            ta = m.load(T + ar.replace('\\', '/') + '.actor', ar)
            actors[ar] = dump(m, 'actor_definition', ta['data'])
        if ur not in bipeds:
            tb = m.load(T + ur.replace('\\', '/') + '.biped', ur)
            b = flatten_obj(dump(m, 'biped_definition', tb['data']))
            b['change_colors_list'] = []
            bipeds[ur] = b
        variants[vp] = v
    # Elites with the plasma carbine: the CE plasma-rifle ranks re-armed (longer reach, same colours)
    A = bp.AI
    for src in [r'characters\elite\elite minor\elite minor plasma rifle', r'characters\elite\elite major\elite major plasma rifle',
                r'characters\elite\elite specops\elite specops plasma rifle', r'characters\elite\elite commander\elite commander plasma rifle']:
        v = copy.deepcopy(A['variants'][src])
        v['unit_reference'] = ELITE_RIFLE
        rc = v['ranged_combat']
        rc['reference'] = CARBINE
        rc['combat_range_lower_bound'] = max(rc['combat_range_lower_bound'], 3.0)
        rc['combat_range_upper_bound'] = max(rc['combat_range_upper_bound'] * 1.4, 12.0)
        rc['maximum_firing_range'] = max(rc['maximum_firing_range'], 25.0)
        variants[src.replace('plasma rifle', 'plasma carbine')] = v
        actors[v['actor_reference']] = A['actors'][v['actor_reference']]
        # blue Pulse Carbine version of the same rank (added after the first add-on release)
        p = copy.deepcopy(v)
        p['ranged_combat']['reference'] = PULSE
        p['_late'] = True
        variants[src.replace('plasma rifle', 'pulse carbine')] = p
    bipeds[ELITE_RIFLE] = copy.deepcopy(A['bipeds'][r'characters\elite\elite'])
    colls = dict(A['collisions'])
    sp = OUT + '/spv3_ai.json'           # extract_spv3.py (Blind Wolf from SPV3's a30)
    if os.path.exists(sp):
        S3 = json.load(open(sp))
        for v in S3['variants'].values(): v['_late'] = True    # keeps the first add-on release's DoomEdNums
        # the Engineer carries no weapon: a harmless floating hazard (class HCE_Engineer)
        eng = S3['variants'].pop(r'characters\engineer\engineer major plasma pistol', None)
        if eng:
            eng = copy.deepcopy(eng)
            eng['ranged_combat']['reference'] = None
            eng['items']['grenades_upper_bound'] = 0; eng['items']['grenades_lower_bound'] = 0
            S3['variants'][r'characters\engineer\engineer'] = eng
        variants.update(S3['variants']); actors.update(S3['actors']); bipeds.update(S3['bipeds']); colls.update(S3['collisions'])
    # Halo 2 Drone (extract_h2.py): its character tag only sets 30 body / no shield and evasion; the rest of its AI
    # comes from ai\generic, so it starts from the CE minor Jackal's plasma-pistol combat data
    if os.path.exists(OUT + '/models/Drone/Drone.json'):
        jv = copy.deepcopy(A['variants'][r'characters\jackal\jackal minor plasma pistol'])
        jv['unit_reference'] = DRONE; jv['actor_reference'] = DRONE
        jv['unit'] = dict(jv['unit'], maximum_body_vitality=30.0, maximum_shield_vitality=0.0)
        jv['items']['grenades_upper_bound'] = 0; jv['items']['grenades_lower_bound'] = 0
        jv['grenade_combat']['throw_grenade_chance'] = 0.0
        rc = jv['ranged_combat']
        rc['combat_range_lower_bound'] = 2.5; rc['combat_range_upper_bound'] = 7.0
        jv['change_colors_list'] = []
        jv['_late'] = True
        variants[DRONE + ' plasma pistol'] = jv
        actors[DRONE] = copy.deepcopy(A['actors'][r'characters\jackal\jackal minor'])
        jb = copy.deepcopy(A['bipeds'][r'characters\jackal\jackal'])
        jb.update(collision_height_standing=0.55, collision_radius=0.27, flying_velocity=2.6)
        jb['change_colors_list'] = []
        bipeds[DRONE] = jb
    # Halo 2 Brutes (extract_h2_brute.py): Elite-major combat data, re-armed and re-statted from the Brute char tags
    if os.path.exists(OUT + '/models/Brute/Brute.json'):
        base_v = A['variants'][r'characters\elite\elite major\elite major plasma rifle']
        ba = copy.deepcopy(A['actors'][base_v['actor_reference']])
        bz = ba['berserk']
        bz.update(damage_berserk_amount=0.25, damage_berserk_threshold=0.45, proximity_berserk_distance=0.0,
                  melee_attack_range=1.5, melee_attack_delay_timer=4.0)
        actors[BRUTE] = ba
        bb = copy.deepcopy(A['bipeds'][r'characters\elite\elite'])
        bb.update(collision_height_standing=0.95, collision_radius=0.32); bb['change_colors_list'] = []
        bipeds[BRUTE] = bb
        for rank, rd in BRUTE_RANKS.items():
            for fur, wref in enumerate(rd['weapons']):
                v = copy.deepcopy(base_v)
                v['unit_reference'] = BRUTE; v['actor_reference'] = BRUTE
                v['unit'] = dict(v['unit'], maximum_body_vitality=float(rd['body']), maximum_shield_vitality=0.0)
                v['ranged_combat']['reference'] = wref
                gc = v['grenade_combat']                       # char tag: plasma grenades, 10%/s, 3-20 WU, 6 s apart
                gc.update(grenade_type=1, throw_grenade_chance=0.1, throw_grenade_delay=6.0,
                          grenade_range_lower_bound=3.0, grenade_range_upper_bound=20.0, grenade_velocity=10.0)
                v['items']['grenades_lower_bound'] = 1; v['items']['grenades_upper_bound'] = 2
                v['change_colors'] = None; v['change_colors_list'] = []
                v['_late'] = True; v['_brute_rank'] = rank; v['_brute_variant'] = rd['variants'][fur]
                if rank == 'chieftain':
                    # brute_tartarus char: 350 body (his 1000-point overshield cut to a breakable 150), no grenades,
                    # leaps 2.5-6 WU at 50%, smashes with the hammer's gravity shockwave (brute_code)
                    gc['throw_grenade_chance'] = 0.0; v['items']['grenades_lower_bound'] = v['items']['grenades_upper_bound'] = 0
                    v['_ov'] = dict(shield=150, melee=(60, 70), melee_only=True, speed=6.0, leap=(150, 400, 0.5, 13.0),
                                    flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Leaps', 'HCE_Leader'],
                                    berserk_anims=CHIEFTAIN_BERSERK)
                variants[f'{BRUTE} {rank} {wref.split(chr(92))[-1]}'] = v
    return dict(variants=variants, actors=actors, bipeds=bipeds, collisions=colls,
                weapons={k: A['weapons'][k] for k in (CE_PR, CE_AR, CE_SG)})     # shotgun pellets per shot etc.

DRONE_CODE = '''
	// ---- Halo 2 Drone behaviour ----------------------------------------------------------------------
	// darting flight above the target, sideways dodges when hit (char tag: 50% chance, 4 s apart), wall
	// perching (back to the wall, firing from it), swarm scatter when a drone nearby dies, falling deaths.
	int hce_dartTics, hce_dartNext, hce_zigTics, hce_scatterTics, hce_buzzTics, hce_lastAir;
	double hce_dartAngle, hce_zigOff, hce_altWant;
	int hce_perch, hce_perchTics, hce_perchNext, hce_perchSide, hce_perchEnter;   // perch: 0 no, 1 flying to wall, 2 clinging
	vector3 hce_perchPos; double hce_perchAngle;

	override void PostBeginPlay()
	{
		super.PostBeginPlay();
		hce_altWant = frandom(40, 110);
		hce_perchNext = level.maptime + 35 * random(4, 10);
		hce_perchSide = random(0, 1);
	}

	// flying: stay above whatever we fight, at a height that keeps changing
	void HCE_DroneAltitude()
	{
		if(health <= 0) return;
		if(random(0, 70) == 0) hce_altWant = frandom(30, 130);
		double base = target ? target.pos.z + target.height : floorz + 40;
		double want = clamp(base + hce_altWant, floorz + 24, ceilingz - height - 6);
		vel.z = clamp((want - pos.z) * 0.07, -4, 4) + sin(level.maptime * 9 + tid * 31) * 0.35;
	}

	override void HCE_Fight()
	{
		if(hce_perch) return;
		if(hce_scatterTics > 0 && target)
		{
			hce_scatterTics--;
			HCE_Move(HCE_PickHeading(AngleTo(target) + 180 + hce_zigOff, AngleTo(target)), hce_runSpeed * 1.2);
			A_SetAngle(hce_moveAngle, SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		double d = Distance2D(target);
		HCE_FaceTarget(2.5);
		if(!hce_canSee && level.maptime - hce_lastSeen > 25) { HCE_Pursue(); return; }
		// swarm darting: a new heading offset every half second or so
		if(--hce_zigTics <= 0)
		{
			hce_zigTics = random(10, 28); hce_zigOff = frandom(-110, 110);
			if(random(0, 3) == 0) A_StartSound("HCE/Drone/Whoosh", CHAN_6, CHANF_OVERLAP, 0.5);
		}
		double toT = AngleTo(target), moveA, spd;
		if(d > hce_rangeMax) { moveA = toT + hce_zigOff * 0.4; spd = hce_runSpeed; }
		else if(d < hce_rangeMin) { moveA = toT + 180 + hce_zigOff * 0.5; spd = hce_runSpeed * 0.8; }
		else { moveA = toT + (hce_zigOff >= 0 ? 90 : -90) + hce_zigOff * 0.2; spd = hce_runSpeed * 0.7; }
		HCE_Move(HCE_PickHeading(moveA, toT), spd);
		HCE_UpdateFiring(d);
		HCE_PickMoveAnim();
		if(level.maptime >= hce_perchNext && hce_canSee && random(0, 90) == 0) HCE_TryPerch();
	}

	// dodge sideways when hit
	override int HCE_ModifyIncoming(Actor inflictor, Actor source, int dmg, Name mod, int flags, double dangle)
	{
		dmg = super.HCE_ModifyIncoming(inflictor, source, dmg, mod, flags, dangle);
		if(dmg > 0 && dmg < health && level.maptime >= hce_dartNext && frandom(0, 1) < 0.5)
		{
			hce_dartNext = level.maptime + 35 * 4;
			hce_dartTics = 12;
			hce_dartAngle = angle + (random(0, 1) ? 90 : -90);
			A_StartSound("HCE/Drone/Whoosh", CHAN_6, CHANF_OVERLAP, 0.8);
			if(hce_perch) HCE_LeavePerch();
		}
		return dmg;
	}

	// ---- perching
	void HCE_TryPerch()
	{
		hce_perchNext = level.maptime + 35 * (target ? random(15, 25) : random(10, 18));
		double best = 1e9; FLineTraceData lt;
		Line bestLine = null; int bestSide = 0; vector3 bestHit;
		for(int a = 0; a < 360; a += 30)
		{
			if(!LineTrace(angle + a, 360, 0, TRF_THRUACTORS | TRF_THRUHITSCAN, height * 0.5, data: lt)) continue;
			if(lt.HitType != TRACE_HitWall || !lt.HitLine) continue;
			if(lt.Distance < best) { best = lt.Distance; bestLine = lt.HitLine; bestSide = lt.LineSide; bestHit = lt.HitLocation; }
		}
		if(!bestLine) return;
		vector2 nrm = (bestLine.delta.y, -bestLine.delta.x).Unit();
		if(bestSide == Line.back) nrm = -nrm;
		hce_perchAngle = atan2(nrm.y, nrm.x);
		hce_perchPos = (bestHit.xy + nrm * (radius + 3), bestHit.z - height * 0.5);
		hce_perch = 1; hce_perchTics = 35 * 4;
	}

	void HCE_LeavePerch()
	{
		if(hce_perch == 2) HCE_ApplyAnim(hce_perchSide ? 'perch right exit' : 'perch left exit', 3, false);
		hce_curAnimKind = -1;
		hce_perch = 0; hce_animLock = 0;
		hce_perchNext = level.maptime + 35 * random(8, 15);
		bNOGRAVITY = true;
		vel.xy = AngleToVector(hce_perchAngle, 4);
	}

	void HCE_PerchTick()
	{
		if(hce_perch == 1)
		{
			if(--hce_perchTics <= 0) { hce_perch = 0; return; }
			vector3 dv = level.Vec3Diff(pos, hce_perchPos);
			if(dv.Length() < 10)
			{
				SetOrigin(hce_perchPos, true);
				vel = (0, 0, 0);
				A_SetAngle(hce_perchAngle);
				hce_perch = 2; hce_perchTics = target ? 35 * random(3, 6) : 35 * random(8, 20);
				hce_curAnim = hce_perchSide ? 'perch right enter' : 'perch left enter';
				HCE_ApplyAnim(hce_curAnim, 3, false);
				hce_perchEnter = 20;
				A_StopSound(CHAN_7);
				A_StartSound("HCE/Drone/Stick", CHAN_6, CHANF_OVERLAP, 0.9);
				hce_curAnimKind = -1;
				return;
			}
			HCE_Move(atan2(dv.y, dv.x), hce_runSpeed);
			vel.z = clamp(dv.z * 0.15, -5, 5);
			A_SetAngle(hce_moveAngle, SPF_INTERPOLATE);
			HCE_Play(HCE_A_MOVE_F);
			return;
		}
		// clinging: hold still with our back to the wall, shoot what we see from here
		vel = (0, 0, 0);
		if(pos != hce_perchPos) SetOrigin(hce_perchPos, true);
		A_SetAngle(hce_perchAngle);
		hce_animLock = 2;                                   // keeps the base AI from walking us off the wall
		if(hce_perchEnter > 0) { hce_perchEnter--; return; }
		if(hce_curAnimKind != -2) { hce_curAnim = hce_perchSide ? 'perch right idle' : 'perch left idle'; HCE_ApplyAnim(hce_curAnim, 4, true); hce_curAnimKind = -2; }
		if(--hce_perchTics <= 0 || (target && Distance2D(target) < 96)) { HCE_LeavePerch(); return; }
		if(target && hce_canSee && abs(DeltaAngle(hce_perchAngle, AngleTo(target))) < 80) HCE_UpdateFiring(Distance2D(target));
	}

	override void Tick()
	{
		if(health > 0 && !isFrozen() && hce_perch) bNOGRAVITY = true;
		super.Tick();
		if(hce_lastAir == 1 && hce_airPhase == 2) A_StartSound("HCE/Drone/BodyFall", CHAN_BODY, CHANF_OVERLAP, 0.8);
		hce_lastAir = hce_airPhase;
		if(health <= 0 || isFrozen() || bDORMANT) return;
		// wing buzz while airborne (one 1.1 s clip after another)
		if(!hce_perch && --hce_buzzTics <= 0) { hce_buzzTics = 37; A_StartSound("HCE/Drone/Fly", CHAN_7, 0, 0.55, ATTN_NORM); }
		if(hce_perch) { HCE_PerchTick(); return; }
		HCE_DroneAltitude();
		if(hce_dartTics > 0)
		{
			hce_dartTics--;
			HCE_Move(hce_dartAngle, hce_runSpeed * 1.8);
			HCE_Play(DeltaAngle(angle, hce_dartAngle) > 0 ? HCE_A_MOVE_L : HCE_A_MOVE_R);
		}
		// idle drones go and rest on a wall now and then
		if(!target && level.maptime >= hce_perchNext && random(0, 60) == 0) HCE_TryPerch();
	}

	// a dead drone scatters the swarm around it
	override void HCE_Die()
	{
		if(hce_perch) { hce_perch = 0; bNOGRAVITY = false; }
		super.HCE_Die();
		let it = BlockThingsIterator.Create(self, 400);
		while(it.Next())
		{
			let d = HCE_DronePlasmaPistol(it.thing);
			if(!d || d == self || d.health <= 0) continue;
			if(d.hce_perch) d.HCE_LeavePerch();
			d.hce_scatterTics = random(30, 80);
			d.hce_zigOff = frandom(-60, 60);
			d.HCE_Say('Panic', 0.6, 35 * 2);
		}
	}
'''

ENGINEER_CODE = '''
	// The Engineer never fights: nothing is its enemy (not even whoever shoots it), so it never picks a
	// target. It just drifts around; when killed it bursts and sprays charged Plasma Caster grenades.
	override bool HCE_IsEnemy(Actor other) { return false; }

	double hce_driftAngle, hce_driftSpeed;
	int hce_driftNext;
	override void Tick()
	{
		super.Tick();
		if(health <= 0 || bDORMANT || isFrozen() || hce_animLock > 0) return;
		if(level.maptime >= hce_driftNext)
		{
			hce_driftNext = level.maptime + 35 * random(3, 7);
			hce_driftAngle = frandom(0, 360);
			hce_driftSpeed = random(0, 3) == 0 ? 0 : frandom(0.8, 1.8);   // sometimes it just hangs there
		}
		if(hce_driftSpeed <= 0) return;
		if(!HCE_Move(hce_driftAngle, hce_driftSpeed)) { hce_driftNext = 0; return; }   // bumped into something: new heading
		A_SetAngle(angle + clamp(DeltaAngle(angle, hce_driftAngle), -2, 2), SPF_INTERPOLATE);
	}

	override void HCE_Die()
	{
		super.HCE_Die();
		A_StartSound("HCE/Engineer/Explode", CHAN_BODY, CHANF_OVERLAP, 1.0);
		A_StartSound("Halo/Weapons/PlasmaCaster/ChargedFire", CHAN_WEAPON, CHANF_OVERLAP, 1.0);
		A_Quake(2, 8, 0, 512, "");
		for(int i = 0; i < 40; i++)
			A_SpawnParticle(i % 3 ? "C69CFF" : "FFE6FF", SPF_FULLBRIGHT, random(18, 34), frandom(4, 9), 0, 0, 0, height * 0.5,
				frandom(-5, 5), frandom(-5, 5), frandom(-3, 5), 0, 0, -0.12, 1.0, -0.035);
		// charged Plasma Caster shots (HDE): they stick, arm for two seconds, burst and throw two mini bolts
		int n = random(4, 6);
		double a0 = frandom(0, 360);
		for(int i = 0; i < n; i++)
		{
			let g = Spawn("HCE_PlasmaCasterClusterScaled", pos + (0, 0, height * 0.5), ALLOW_REPLACE);
			if(!g) continue;
			g.target = self;
			HCE_ScaleProjectile(g, HCE_DamageScale());          // the projectile nerf covers the bursts too
			g.angle = a0 + i * 360.0 / n + frandom(-20, 20);
			g.vel = (AngleToVector(g.angle, frandom(4, 8)), frandom(4, 9));
		}
		bInvisible = true;            // nothing left to lie on the floor
		vel = (0, 0, 0);
	}
'''

THORN_CODE = '''
	// heavy footfalls from its own sound set while it walks
	int hce_stepTics;
	override void Tick()
	{
		super.Tick();
		if(health <= 0 || pos.z > floorz + 2 || vel.xy.Length() < 1.5) return;
		if(++hce_stepTics >= 16) { hce_stepTics = 0; A_StartSound("HCE/ThornBeast/Step", CHAN_BODY, CHANF_OVERLAP, 0.8); }
	}
'''

BEAM_CODE = '''
	// Particle beam rifle: every shot is telegraphed by a second-long aiming laser, then one hitscan beam
	override void HCE_UpdateFiring(double dist)
	{
		super.HCE_UpdateFiring(dist);
		if(hce_chargeTics > 0 && target && (hce_chargeTics & 1)) HCE_BeamTrace(false);
	}
	override void HCE_FireShot(bool special)
	{
		if(!target) return;
		HCE_BeamTrace(true);
		HCE_PlayFireSound(true);
		if(hce_moveSpeed <= 0.1 && HCE_HasAnim(HCE_A_FIRE)) HCE_Play(HCE_A_FIRE, false, true, 2);
	}
	void HCE_BeamTrace(bool fire)
	{
		double gz = height * 0.5 + hce_gunOffset.z;
		vector3 from = Vec3Angle(hce_gunOffset.x, angle, gz);
		vector3 aim = target.pos + (0, 0, target.height * 0.6);
		vector3 diff = level.Vec3Diff(from, aim);
		double err = fire ? hce_errorAngle + (target.vel.xy.Length() > 6 ? 1.2 : 0.3) : 0;
		double ang = atan2(diff.y, diff.x) + frandom(-err, err);
		double pit = -atan2(diff.z, diff.xy.Length()) + frandom(-err, err);
		FLineTraceData lt;
		LineTrace(ang, hce_maxRange, pit, 0, gz, hce_gunOffset.x, 0, lt);
		vector3 to = lt.HitType != TRACE_HitNone ? lt.HitLocation : from + (cos(ang) * cos(pit), sin(ang) * cos(pit), -sin(pit)) * hce_maxRange;
		vector3 d = level.Vec3Diff(from, to);
		double len = d.Length();
		if(len < 1) return;
		double step = fire ? 6 : 20;
		int n = min(400, int(len / step));
		vector3 rel = level.Vec3Diff(pos, from);
		for(int i = 0; i < n; i++)
		{
			vector3 p = rel + d * (i / double(n));
			if(fire)
			{
				A_SpawnParticle("FF66FF", SPF_FULLBRIGHT, 12, 5, 0, p.x, p.y, p.z, 0, 0, 0, 0, 0, 0, 1.0, -0.08);
				A_SpawnParticle("FFFFFF", SPF_FULLBRIGHT, 6, 2, 0, p.x, p.y, p.z);
			}
			else A_SpawnParticle("CC44FF", SPF_FULLBRIGHT, 3, 1.5, 0, p.x, p.y, p.z, 0, 0, 0, 0, 0, 0, 0.6);
		}
		if(!fire) return;
		{ CVar dbg = CVar.FindCVar("hce_digdebug"); if(dbg && dbg.GetInt()) console.printf("BEAM hit %s at %.0f", lt.HitActor ? lt.HitActor.GetClassName() : 'world', lt.Distance); }
		if(lt.HitActor && lt.HitActor != self)
		{
			int dmg = max(1, int(90 * (hce_damageMod > 0 ? hce_damageMod : 1.0) * HCE_DamageScale()));
			lt.HitActor.DamageMobj(self, self, dmg, 'Fire', 0, ang);
		}
		Spawn("HCE_BeamPuff", to);
	}
'''

def voices():
    """Slug Man dialogue from Digsite's sound tags (Xbox ADPCM) -> ogg + SNDINFO events"""
    cat = {'sighted': ['Alert'], 'sighted_re': ['Alert'], 'taunting': ['Taunt'], 'pain': ['Pain', 'PainMed', 'PainHeavy'],
           'death_short': ['Death'], 'death_long': ['Death'], 'retreat': ['Flee', 'Panic'], 'communication': ['Regroup'],
           'evade': ['EnemyGrenade'], 'searching': ['Search'], 'idle_combat': ['Taunt']}
    out = f'{PACK}/sounds/hce_dig/slug'
    os.makedirs(out, exist_ok=True)
    import tempfile; tmp = tempfile.mkdtemp(); os.makedirs(tmp, exist_ok=True)
    events = {}
    for name, evs in cat.items():
        s = parse_sound(f'{T}digsite/sound/dialog/slug/{name}.sound')
        for p in s['pitch_ranges'][0]['perms']:
            a = decode(p, s['rate'], s['channels'])
            fn = f'{name}_{p["name"]}.ogg'
            wav = f'{tmp}/{fn[:-4]}.wav'
            to_wav(a, s['rate'], s['channels'], wav)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libvorbis', '-q:a', '3', f'{out}/{fn}'], check=True)
            for ev in evs: events.setdefault(ev, []).append(f'sounds/hce_dig/slug/{fn}')
    lines = ['// Slug Man dialogue (Digsite sound tags). HCE/<voice>/<event> as played by HCE_Say().']
    for ev in sorted(events):
        ids = []
        for i, pth in enumerate(events[ev]):
            sid = f'HCE/Slug/{ev}/{i}'; lines.append(f'{sid} "{pth}"'); ids.append(sid)
        lines.append(f'$random HCE/Slug/{ev} {{ {" ".join(ids)} }}')
    for ev, fb in bp_fallback().items():
        if ev not in events and fb in events: lines.append(f'$alias HCE/Slug/{ev} HCE/Slug/{fb}')
    return lines

def thorn_sounds():
    """the Thorn Beast's own sounds, straight out of SPV3's a30 (ogg permutations) -> HCE/ThornBeast/<event>"""
    import extract_spv3
    got = extract_spv3.export_sounds('ThornBeast', f'{PACK}/sounds/hce_dig/thornbeast')
    ev = {'idle': ['Alert', 'Taunt', 'Idle'], 'melee': ['Melee', 'Berserk'], 'pain_minor': ['Pain'],
          'pain_major': ['PainMed', 'PainHeavy'], 'death': ['Death', 'DeathHard'], 'footsteps': ['Step']}
    lines = ['', '// Thorn Beast (SPV3 a30 sound tags)']
    for base, files in sorted(got.items()):
        ids = []
        for i, f in enumerate(files):
            sid = f'HCE/ThornBeast/{base}/{i}'; lines.append(f'{sid} "sounds/hce_dig/thornbeast/{f}"'); ids.append(sid)
        for e in ev.get(base, []):
            lines.append(f'$random HCE/ThornBeast/{e} {{ {" ".join(ids)} }}')
    return lines

def engineer_sounds():
    """Engineer dialogue + death burst from SPV3's b30 (16-bit PCM / Xbox ADPCM -> ogg)"""
    import extract_spv3
    got = extract_spv3.export_sounds('Engineer', f'{PACK}/sounds/hce_dig/engineer')
    ev = {'engineer_noncombat': ['Idle'], 'engineer_combat': ['Taunt', 'Regroup'], 'engineer_surprise': ['Alert', 'Panic', 'Flee'],
          'engineer_pain_minor': ['Pain'], 'engineer_pain_major': ['PainMed', 'PainHeavy', 'Death', 'DeathHard'],
          'engineer_explosion': ['Explode']}
    lines = ['', '// Engineer (SPV3 b30 sound tags)']
    for base, files in sorted(got.items()):
        ids = []
        for i, f in enumerate(files):
            sid = f'HCE/Engineer/{base.replace(" ", "_")}/{i}'; lines.append(f'{sid} "sounds/hce_dig/engineer/{f}"'); ids.append(sid)
        for e in ev.get(base.replace(' ', '_'), []):
            lines.append(f'$random HCE/Engineer/{e} {{ {" ".join(ids)} }}')
    return lines

def drone_sounds():
    """Halo 2 Drone dialogue (extract_h2_sounds / out/sounds/Drone: MCC sounds_en.dat Opus -> Ogg) -> HCE/Drone/<event>"""
    src = OUT + '/sounds/Drone'
    if not os.path.exists(f'{src}/index.json'): return []
    idx = json.load(open(f'{src}/index.json'))
    dst = f'{PACK}/sounds/hce_dig/drone'; os.makedirs(dst, exist_ok=True)
    ev = {'seefoe': ['Alert'], 'foundfoe': ['Alert'], 'hrdfoe': ['Alert'], 'srprs': ['Alert'],
          'tnt': ['Taunt'], 'thrtn': ['Taunt'], 'crs': ['Taunt'], 'chr': ['Taunt', 'Berserk'], 'strk': ['Taunt'],
          'glt': ['KillPlayer'], 'pain': ['Pain'], 'pain_shld': ['Pain'], 'pain_mdm': ['PainMed'], 'pain_mjr': ['PainHeavy'],
          'pain_fall': ['PainHeavy'], 'dth': ['Death'], 'dth_slw': ['Death'], 'dth_fall': ['Death', 'DeathHard'],
          'dth_mjr': ['DeathHard'], 'flee': ['Flee'], 'panic': ['Panic'], 'cower': ['Panic'], 'whn': ['Panic'],
          'pstcmbt': ['Regroup'], 'warn': ['EnemyGrenade'], 'fall': ['Panic'],
          # effects (sounds_neutral.dat)
          'flying': ['Fly'], 'long_move': ['Whoosh'], 'bugger_stick': ['Stick'], 'bugger_melees': ['Claw'],
          'bugger_bodyfalls_havok': ['BodyFall'], 'bugger_bodyfalls_non_havok': ['BodyFall']}
    lines = ['', '// Drone (Halo 2 MCC: dialogue from sounds_en.dat, effects from sounds_neutral.dat)']
    per_ev = {}
    for base, files in sorted(idx.items()):
        ids = []
        for i, f in enumerate(files):
            shutil.copy(f'{src}/{f}', f'{dst}/{f}')
            sid = f'HCE/Drone/{base}/{i}'; lines.append(f'{sid} "sounds/hce_dig/drone/{f}"'); ids.append(sid)
        for e in ev.get(base, []): per_ev.setdefault(e, []).extend(ids)
    for e, ids in sorted(per_ev.items()):
        lines.append(f'$random HCE/Drone/{e} {{ {" ".join(ids)} }}')
    return lines

def brute_skin(cls, v, si, mat, meta, skin_dir):
    """per-rank Brute skins: hide the armour pieces a rank doesn't wear, bake the variant's fur change colours"""
    names = meta.get('mesh_names')
    if not names or 'Brute' not in mat and not mat.startswith('Brute_'): return None
    region, perm, shader = names[si].split('.')
    rank = BRUTE_RANKS[v['_brute_rank']]
    os.makedirs(skin_dir, exist_ok=True)
    if (region, perm) not in rank['wear']:
        hid = f'{skin_dir}/hce_hidden.png'
        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        return 'hce_hidden.png'
    var = v['_brute_variant']
    fn = f'brute_{var}_{shader}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    src = f'{OUT}/models/Brute/Brute_{shader}.png'
    im = Image.open(src); has_a = im.mode == 'RGBA'
    a = np.asarray(im.convert('RGBA')).astype(np.float64) / 255.0
    mp = f'{OUT}/models/Brute/Brute_{shader}_mask.png'
    cols = meta['change_colors'].get(var) or meta['change_colors']['minor_bth']
    if os.path.exists(mp):
        mk = np.asarray(Image.open(mp).convert('RGB').resize(im.size)).astype(np.float64) / 255.0
        rgb = a[..., :3]
        for ch, col in ((0, cols[0]), (1, cols[1])):           # red = primary (fur/skin), green = secondary (hair)
            if col is None: continue
            m_ = mk[..., ch:ch + 1] if shader in ('brute_hair', 'tartarus_mohawk') else mk[..., :1] if ch == 0 else None
            if m_ is None: continue
            rgb = rgb * (1 - m_) + rgb * np.array(col) * 1.5 * m_
        a[..., :3] = rgb
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), 'RGBA')
    (out if has_a else out.convert('RGB')).save(dst)
    return fn

def brute_code():
    meta = json.load(open(OUT + '/models/Brute/Brute.json'))
    helm = [i for i, n in enumerate(meta['mesh_names']) if n.startswith('helmet.default.')]
    hide = ''.join(f'\t\tA_ChangeModel(\'\', 0, "", \'\', {i}, "models/hce_dig/Brute/skins", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n' for i in helm)
    return '''
	// ---- Halo 2 Brute behaviour ----------------------------------------------------------------------
	// berserk (badly hurt, or the pack is gone): roar, throw the gun away, charge on all fours with the
	// berserk swings and tackles. Headshots knock a Minor/Major/Captain's helmet off. Losing pack mates
	// can send the survivors berserk; the last Brute standing always goes.
	// The Chieftain (Tartarus's look and hammer) keeps his gravity hammer when berserk: every swing and every
	// landed leap ends in a gravity shockwave that hurts and throws back everything around the impact.
	bool hce_weaponTossed, hce_helmetOff, hce_chief;
	int hce_stepTics, hce_fallTics, hce_smashTics, hce_prevLeap;
	Name hce_lastSwing;
	override void PostBeginPlay()
	{
		super.PostBeginPlay();
		String cn = GetClassName();
		hce_chief = cn.IndexOf("Chieftain") >= 0;
	}
	override bool HCE_TryMelee()
	{
		if(!super.HCE_TryMelee()) return false;
		if(hce_chief) hce_smashTics = max(4, int(hce_animLock * 0.45));
		return true;
	}
	void HCE_HammerSmash(double reach)
	{
		vector3 at = Vec3Angle(radius + reach, angle, 0);
		A_StartSound("Halo/Weapons/GravityHammer/Fire", CHAN_WEAPON, CHANF_OVERLAP, 1.0);
		A_StartSound("Halo/Weapons/GravityHammer/Fire/Bass", CHAN_7, CHANF_OVERLAP, 1.0);
		Spawn("GravityHammerExplosion", at, ALLOW_REPLACE);
		let it = BlockThingsIterator.CreateFromPos(at.x, at.y, at.z, 64, 150, false);
		while(it.Next())
		{
			Actor mo = it.thing;
			if(!mo || mo == self || !mo.bSHOOTABLE || mo.health <= 0) continue;
			if(mo is "HaloDoom_EnemyBase" && !HCE_IsEnemy(mo)) continue;      // spare the pack
			double d = (mo.pos.xy - at.xy).Length();
			if(d > 150 || abs(mo.pos.z - at.z) > 96) continue;
			double f = 1.0 - d / 150.0;
			mo.DamageMobj(self, self, int(10 + 25 * f), 'Crush', DMG_THRUSTLESS);
			double a = atan2(mo.pos.y - at.y, mo.pos.x - at.x);
			if(mo.bSOLID && mo.mass < 2000) mo.vel += (AngleToVector(a, 6 + 10 * f), 4 + 5 * f);
		}
	}
	override void Tick()
	{
		super.Tick();
		if(hce_chief && health > 0 && !isFrozen())
		{
			if(hce_smashTics > 0 && --hce_smashTics == 0) HCE_HammerSmash(36);
			if(hce_prevLeap == 2 && hce_leapState == 0) HCE_HammerSmash(12);     // leap ends: ground pound
			hce_prevLeap = hce_leapState;
		}
		if(hce_fallTics > 0 && --hce_fallTics == 0) A_StartSound("HCE/Brute/BodyFall", CHAN_BODY, CHANF_OVERLAP, 0.9);
		if(health > 0 && !isFrozen())
		{
			// footfalls: heavier, quicker on the berserk run
			double sp = vel.xy.Length() + hce_moveSpeed;
			if(pos.z <= floorz + 1 && sp > 1.5 && ++hce_stepTics >= (hce_berserk ? 9 : 15))
			{
				hce_stepTics = 0;
				A_StartSound(hce_berserk ? "HCE/Brute/Run" : "HCE/Brute/Step", CHAN_BODY, CHANF_OVERLAP, 0.7);
			}
			// swing whoosh on each melee / tackle, chest thump on the berserk roar
			if(hce_curAnim != hce_lastSwing)
			{
				String an = hce_curAnim;
				if(an.IndexOf("melee") >= 0 || an.IndexOf("tackle") >= 0) A_StartSound("HCE/Brute/MeleeMove", CHAN_6, CHANF_OVERLAP, 0.9);
				else if(an.IndexOf("berserk") >= 0 && an.IndexOf("stand") == 0) A_StartSound("HCE/Brute/Thump", CHAN_6, CHANF_OVERLAP, 1.0);
				hce_lastSwing = hce_curAnim;
			}
		}
		if(health > 0 && hce_berserk && !hce_weaponTossed && !hce_chief && hce_animLock <= 0) HCE_TossWeapon();
		// a Brute without its gun only charges
		if(hce_weaponTossed && health > 0 && target && hce_action != HCE_ACT_CHARGE) { hce_berserk = true; hce_action = HCE_ACT_CHARGE; }
	}
	void HCE_TossWeapon()
	{
		hce_weaponTossed = true;
		CVar cv = CVar.FindCVar("hce_dropweapons");
		class<Actor> wc = (class<Actor>)(hce_dropWeapon);
		if(wc && (!cv || cv.GetBool())) HCE_Toss(wc);
		hce_dropWeapon = 'None';
		HCE_HideWeaponSurfaces();
		HCE_StopFireLoop();
		hce_projectile = 'None';
		hce_runSpeed *= 1.35; hce_walkSpeed *= 1.35;
		hce_curAnimKind = -1;
	}
	override void HCE_OnDamaged(Actor inflictor, Actor source, int dealt, Name mod)
	{
		super.HCE_OnDamaged(inflictor, source, dealt, mod);
		if(health <= 0 || hce_helmetOff || dealt <= 0 || HCE_HelmetFixed()) return;
		bool head = mod == 'Headshot' || (inflictor && inflictor != source && inflictor.pos.z > pos.z + height * 0.8);
		if(!head) return;
		hce_helmetOff = true;
''' + hide + '''		let h = Spawn("HCE_BruteHelmetDebris", pos + (0, 0, height * 0.95), ALLOW_REPLACE);
		if(h)
		{
			Actor from = inflictor ? inflictor : source;
			double a = from ? from.AngleTo(self) : angle + 180;
			h.vel = (AngleToVector(a + frandom(-30, 30), frandom(3, 6)), frandom(4, 7));
			h.angle = angle;
		}
		HCE_Say('PainHeavy', 1.0, 0, true);
	}
	bool HCE_HelmetFixed() { String cn = GetClassName(); return hce_chief || cn.IndexOf("HonorGuard") >= 0; }   // honor guard helmets are part of the armour
	override void HCE_Die()
	{
		super.HCE_Die();
		hce_fallTics = 22;
		// pack morale: the last Brute nearby always goes berserk, others sometimes do
		Array<HaloDoom_EnemyBase> pack;
		let it = BlockThingsIterator.Create(self, 640);
		while(it.Next())
		{
			let b = HaloDoom_EnemyBase(it.thing);
			if(b && b != self && b.health > 0 && b.GetClassName() != 'None' && (b is "HCE_BruteBase")) pack.Push(b);
		}
		for(int i = 0; i < pack.Size(); i++)
			if(!pack[i].hce_berserk && (pack.Size() == 1 || frandom(0, 1) < 0.35)) pack[i].HCE_GoBerserk(true);
	}
'''

BRUTE_EVENTS = {
    'Alert': ['seefoe', 'seefoe_srprs', 'foundfoe', 'hrdfoe', 'morefoe', 'srprs'],
    'Taunt': ['tnt', 'thrtn', 'crs', 'cllcoward', 'cllwimp', 'strk'],
    'KillPlayer': ['glt', 'chr_kllfoe'],
    'Pain': ['pain', 'pain_shld'], 'PainMed': ['pain_mdm'], 'PainHeavy': ['pain_mjr', 'pain_fall'],
    'Death': ['dth', 'dth_slw'], 'DeathHard': ['dth_mjr', 'dth_hdsht', 'dth_fall'],
    'Berserk': ['brsrk', 'charge'], 'Melee': ['melee', 'meleeleap'],
    'Panic': ['panic'], 'Regroup': ['pstcmbt', 'newordr_charge'], 'LeaderDead': ['lmnt_deadally', 'lmnt'],
    'EnemyGrenade': ['warn_incmn_grnd', 'warn_incmn'], 'GrenadeThrow': ['strk_grnd'],
}
BRUTE_FX = {'Step': ['step_walk'], 'Run': ['step_run'], 'Thump': ['thump'], 'MeleeMove': ['melee_moves'],
            'BodyFall': ['bodyfall']}

def brute_sounds():
    """Halo 2 Brute voices (bloodthirsty, cruel) + effects (extract_h2_brute.extract_brute_sounds) -> HCE/<voice>/<event>"""
    src = OUT + '/sounds/Brute'
    if not os.path.exists(f'{src}/index.json'): return []
    idx = json.load(open(f'{src}/index.json'))
    lines = ['', '// Brutes (Halo 2 MCC: dialogue from sounds_en.dat, effects from sounds_neutral.dat)']
    def emit(group, prefix, table):
        for ev, leaves in sorted(table.items()):
            ids = []
            for leaf in leaves:
                for i, f in enumerate(idx.get(group, {}).get(leaf, [])):
                    dst = f'{PACK}/sounds/hce_dig/brute/{f}'
                    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(f'{src}/{f}', dst)
                    sid = f'{prefix}/{leaf}/{i}'; lines.append(f'{sid} "sounds/hce_dig/brute/{f}"'); ids.append(sid)
            if ids: lines.append(f'$random {prefix}/{ev} {{ {" ".join(ids)} }}')
    for voice in ('Brute_Bloodthirsty', 'Brute_Cruel'): emit(voice, f'HCE/{voice}', BRUTE_EVENTS)
    emit('fx', 'HCE/Brute', BRUTE_FX)
    return lines

def bp_fallback():
    from build_voices import FALLBACK
    return FALLBACK

def configure():
    W = bp.W
    bp.WEAPONS['plasma carbine'] = ('HCE_CarbineRound', 'HaloCarbine_Bullet', 15, 6.0)   # HDE's green carbine round
    bp.WEAPONS['particle beam'] = ('HCE_BeamRifleShot', 'HCE_BeamPuff', None, 30.0)
    bp.FIRE_CODE.update({'plasma carbine': 'cr', 'particle beam': 'sr', 'pulse carbine': 'cr'})
    # Pulse Carbine: HDE's homing, accelerating plasma bolts in bursts (its own gun fires five-bolt bursts)
    bp.WEAPONS['pulse carbine'] = ('HCE_PulseCarbineBolt', 'HCE_PulseCarbineHoming', 8, 1.2)
    bp.PATTERNS['pulse carbine'] = (3, 5, 3, 1.4, 2.3, 0, False, 1.0, 1.0)
    bp.FIRE_SOUNDS['pulse carbine'] = (W + 'PulseCarbine/Fire', W + 'PulseCarbine/Fire/Bass', '', '', False)
    bp.DROP_WEAPON['pulse carbine'] = 'Halo_PulseCarbine'
    bp.WEAPON_IDS[PULSE] = 'cmt_carbine'
    bp.WEAPON_SKIN['pulse carbine'] = {f'w_cmt_carbine_{k}.png': f'w_cmt_carbine_blue_{k}.png' for k in ('purple', 'lights', 'icon', 'meter')}
    bp.PATTERNS['plasma carbine'] = (2, 3, 9, 1.0, 1.7, 0, False, 1.0, 1.0)      # semi-auto pairs/triples
    # Brute weapons: the CE plasma rifle / assault rifle / shotgun come from the main pack's tables; the Spiker fires
    # HDE's own spikes (Halo 3's Spiker is an automatic: AR-like bursts); the gravity hammer is melee only and drops
    # HDE's hammer
    bp.WEAPONS['spiker'] = ('HCE_SpikerSpike', 'HaloSpiker_Bullet', 10, 2.0)
    bp.PATTERNS['spiker'] = (5, 9, 3, 0.8, 1.4, 0, True, 1.0, 2.0)
    bp.FIRE_SOUNDS['spiker'] = (W + 'Spiker/Fire', W + 'Spiker/Fire/Bass', '', '', False)
    bp.DROP_WEAPON['spiker'] = 'Halo_Spiker'
    bp.DROP_WEAPON['gravity hammer'] = 'Halo_GravityHammer'
    bp.WEAPON_IDS[SPIKER] = 'spiker'
    bp.WEAPON_IDS[HAMMER] = 'gravity_hammer'
    bp.FIRE_CODE['spiker'] = 'sk'
    bp.SKIN_HOOK['Brute'] = brute_skin
    bp.BERSERK_ANIMS['Brute'] = {
        'IDLE': ['berserk idle'], 'ALERT': ['berserk idle'], 'MOVE_F': ['berserk move-front'], 'MOVE_B': ['berserk move-front'],
        'MOVE_L': ['berserk move-front'], 'MOVE_R': ['berserk move-front'], 'FLEE': ['berserk move-front'],
        'TURN_L': ['berserk turn-left'], 'TURN_R': ['berserk turn-right'],
        'MELEE': [f'berserk melee {i}' for i in range(1, 6)] + ['berserk tackle 1', 'berserk tackle 2']}
    bp.TYPE_CODE['Brute'] = brute_code()
    bp.PATTERNS['particle beam'] = (1, 1, 1, 2.2, 3.2, 35, False, 2.5, 0.7)      # 1 s aiming laser, then one beam
    bp.SPECIAL_FIRE['particle beam'] = 1.0
    bp.FIRE_SOUNDS['plasma carbine'] = (W + 'Carbine/Fire', W + 'Carbine/Fire/Bass', '', '', False)
    bp.FIRE_SOUNDS['particle beam'] = ('', '', W + 'BeamRifle/Laser/Fire', W + 'BeamRifle/Laser/Begin', False)
    bp.DROP_WEAPON.update({'plasma carbine': 'Halo_Carbine', 'particle beam': 'Halo_BeamRifle'})
    bp.WEAPON_IDS.update({CARBINE: 'cmt_carbine', BEAM: 'particle_beam_dig'})
    bp.VOICES.update({'SlugMan': 'Slug', 'EliteRifle': 'Elite_Dogmatic,Elite_Loose', 'Drinol': 'Drinol', 'BlindWolf': 'Blind_Wolf',
                      'ThornBeast': 'ThornBeast', 'Engineer': 'Engineer', 'Drone': 'Drone',
                      'Brute': 'Brute_Bloodthirsty,Brute_Cruel'})
    bp.TYPE_CODE['ThornBeast'] = THORN_CODE
    bp.TYPE_CODE['Engineer'] = ENGINEER_CODE
    bp.TYPE_CODE['Drone'] = DRONE_CODE
    bp.WEAPON_CODE['particle beam'] = BEAM_CODE
    bp.CHAR_OVERRIDES.update({
        # a war beast twice a Hunter's height: shrunk to fit Doom maps; charges, swats, pounces
        'Drinol': dict(stance='unarmed', health=320, scale=0.62, radius=34, melee=(44, 60),
                       flags=['HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Leaps'],
                       leap=(140, 420, 0.6, 13.0), anims={'LEAP_START': ['charging_jump']}),
        'SlugMan': dict(stance={'particle beam': 'rifle', 'plasma pistol': 'pistol'}, melee=(24, 20),
                        flags=['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades'],
                        anims_by_weapon={'plasma pistol': {'FIRE': ['stand pistol pp fire-1 baked']}}),
        'EliteRifle': dict(stance='rifle'),
        # SPV3 a30's Blind Wolf: a Pinky-style melee charger that also pounces (its leap-start/airborne/melee set)
        # SPV3 a30's Thorn Beast: slow, tough melee brute (Hell Knight mix), shrunk to fit Doom doorways
        'ThornBeast': dict(stance='unarmed', health=350, scale=0.7, radius=36, melee=(44, 45), speed=6.0,   # stride is 4.3: a little faster for Doom
                           flags=['HCE_Berserks', 'HCE_AlwaysBerserk']),
        # SPV3 b30's Engineer: unarmed, harmless floater with Halo's 150 body / 200 shield; bursts into charged
        # Plasma Caster grenades when killed (an environmental hazard). Takes the Pain Elemental's slot.
        'Engineer': dict(stance='unarmed', flying=True, scale=1.25, radius_fixed=26, height_fixed=56, drops=False,
                         flags=['HCE_Flying']),
        # Halo 2 Drone (Yanme'e): fragile darting flier with a plasma pistol; perches on walls, scatters when the
        # swarm takes losses, falls out of the air when killed
        # Halo 2 Brutes: shrunk to 80% (1.07 WU = 86 units would not fit Doom doors), melee 2.0 WU / 1.5 WU from
        # their char tag, berserk charge that throws the gun away, plasma grenades
        'Brute': dict(stance={'gravity hammer': 'melee', None: 'rifle'}, scale=0.8,
                      height_fixed=68, radius_fixed=26, melee=(120, 35), weapon_toss=True, shield=0, speed=5.5,
                      flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_Leader']),
        'Drone': dict(stance='pistol', flying=True, radius_fixed=22, height_fixed=48, shield=0, speed=9.5, flags=['HCE_Flying']),
        'BlindWolf': dict(stance='unarmed', health=90, melee=(30, 22),
                          flags=['HCE_Berserks', 'HCE_AlwaysBerserk', 'HCE_Leaps'], leap=(48, 300, 0.7, 14.0)),
    })

def build():
    configure()
    ai = load_ai()
    if os.path.exists(PACK): shutil.rmtree(PACK)
    os.makedirs(PACK)
    cou = {r'digsite\characters\drinol\00_mac\drinol': 'Drinol', r'digsite\characters\slug_man\slug_man': 'SlugMan',
           ELITE_RIFLE: 'EliteRifle', r'characters\blind_wolf\blind_wolf': 'BlindWolf',
           r'characters\thorn_beast\thorn_beast': 'ThornBeast', r'characters\engineer\engineer': 'Engineer',
           DRONE: 'Drone', BRUTE: 'Brute'}
    team = {'Drinol': 'COVENANT', 'SlugMan': 'COVENANT', 'EliteRifle': 'COVENANT', 'BlindWolf': 'COVENANT', 'ThornBeast': 'COVENANT', 'Engineer': 'COVENANT', 'Drone': 'COVENANT', 'Brute': 'COVENANT'}
    cfg = dict(char_of_unit=cou, team=team, ai=ai, pack=PACK, mdir='hce_dig', tag='dig', ed0=30400, main=False,
               handler='HCE_DigsiteHandler', nerf_mixin='HCE_DigNerfMixin', late_chars=['BlindWolf', 'ThornBeast', 'Engineer', 'Drone', 'Brute'],
               late_order=['HCE_BlindWolf', 'HCE_RandomBlindWolf', 'HCE_ThornBeast', 'HCE_RandomThornBeast',
                           'HCE_EliteMinorPulseCarbine', 'HCE_EliteMajorPulseCarbine', 'HCE_EliteSpecopsPulseCarbine',
                           'HCE_EliteCommanderPulseCarbine', 'HCE_Engineer', 'HCE_RandomEngineer', 'HCE_DronePlasmaPistol', 'HCE_RandomDrone',
                           'HCE_BruteMinorPlasmaRifle', 'HCE_BruteMinorAssaultRifle', 'HCE_BruteMajorSpiker', 'HCE_BruteMajorShotgun', 'HCE_BruteCaptainPlasmaRifle', 'HCE_BruteCaptainShotgun', 'HCE_BruteHonorGuardPlasmaRifle', 'HCE_BruteHonorGuardAssaultRifle', 'HCE_BruteChieftainGravityHammer', 'HCE_RandomBrute'], index='digsite_index.json', glow=[f'w_cmt_carbine_{b}{k}.png' for b in ('', 'blue_') for k in ('lights', 'icon', 'meter')] + ['w_spiker_heat.png'],
               gl_title='// Digsite add-on: glowing surfaces')
    bp.build(cfg)
    src = HERE + '/digsite_src'
    for f in ('dig_handler.zsc', 'dig_boss.zsc', 'dig_pulse.zsc', 'dig_brute.zsc'):
        shutil.copy(f'{src}/{f}', f'{PACK}/ZScript/HaloCE/{f}')
    for f in ('zscript.txt', 'cvarinfo.txt', 'CREDITS.txt'):
        shutil.copy(f'{src}/{f}', f'{PACK}/{f}')
    open(f'{PACK}/sndinfo.dig', 'w').write('\n'.join(voices() + thorn_sounds() + engineer_sounds() + drone_sounds() + brute_sounds()) + '\n')
    # Cyberdemon stand-in: the Drinol at 78% instead of 62% (dig_boss.zsc)
    import re
    md = open(f'{PACK}/modeldef.dig').read()
    blk = re.search(r'Model HCE_Drinol\n\{.*?\n\}\n', md, re.S).group(0)
    sc = S * 0.78
    boss = re.sub(r'Scale [^\n]*', f'Scale {sc:.0f} {sc:.0f} {sc * 1.2:.0f}', blk).replace('Model HCE_Drinol', 'Model HCE_BossCyberdemonDrinol')
    open(f'{PACK}/modeldef.dig', 'a').write('\n' + boss)
    # Brute helmet debris (pops off on headshots)
    hs = OUT + '/models/BruteHelmet'
    if os.path.exists(f'{hs}/BruteHelmet.iqm'):
        hd = f'{PACK}/models/hce_dig/BruteHelmet'; os.makedirs(hd, exist_ok=True)
        for f in ('BruteHelmet.iqm', 'BruteHelmet_0.png'): shutil.copy(f'{hs}/{f}', f'{hd}/{f}')
        open(f'{PACK}/modeldef.dig', 'a').write('\nModel HCE_BruteHelmetDebris\n{\n\tPath "models/hce_dig/BruteHelmet"\n'
            '\tModel 0 "BruteHelmet.iqm"\n\tSkin 0 "BruteHelmet_0.png"\n\tScale 64 64 77\n\tUseActorPitch\n\tUseActorRoll\n'
            '\tFrameIndex HCEM A 0 0\n}\n')

if __name__ == '__main__':
    build()
