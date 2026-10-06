"""Digsite add-on pack: Drinol, Slug Man (particle beam rifle / plasma pistol) and plasma-carbine Elites in a
rifle stance.  Generated with build_pack.build() so the classes behave exactly like the main pack's.

Needs out/models/{Drinol,SlugMan,EliteRifle} (extract_digsite.py, extract_elite_rifle.py) and the weapon pkls
from extract_sketchfab.py.  Digsite content is licensed for MCC projects only: never part of a public release."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'lib'))   # readers and writers live in lib/
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
# Minors, Majors and Captains wear only their body here: their helmets and armour come from the armour kit
# (extract_brute_kit.py, KIT_JSON), rolled per Brute when it spawns (brute_code / kit_code).
# The Chieftain is a custom rank: Tartarus's look, hammer stance and gravity hammer.
BRUTE_RANKS = {
    'minor': dict(body=175, variants=('minor_bth', 'minor_crl'), weapons=(CE_PR, CE_AR),
                  wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default')}),
    'major': dict(body=150, variants=('major_bth', 'major_crl'), weapons=(SPIKER, CE_SG),
                  wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default')}),
    'captain': dict(body=200, variants=('captain_bth', 'captain_crl'), weapons=(CE_PR, CE_SG),
                    wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('sensors', 'default'), ('flag', 'captain')}),
    'honor guard': dict(body=150, variants=('minor_bth', 'minor_crl'), weapons=(CE_PR, CE_AR),
                        wear={('body', 'default'), ('head', 'default'), ('hair', 'default'), ('helmet', 'honor_on'), ('sensors', 'honor_on'),
                              ('sh_armor', 'honor_on'), ('hg_arm', 'honor_on'), ('hg_legs', 'honor_on')}),
    'chieftain': dict(body=350, variants=('tartarus',), weapons=(HAMMER,),
                      wear={('body', 'default'), ('head', 'default'), ('helmet', 'honor_off'), ('helmet', 'tartarus'),
                            ('sensors', 'default'), ('sh_armor', 'skull'), ('hg_arm', 'honor_off'), ('hg_legs', 'honor_off')}),
}
ELITE_RIFLE = r'characters\elite\elite rifle'
KIT_DIR = f'{bp.OUT}/models/BruteKit'
KIT_JSON = f'{KIT_DIR}/BruteKit.json'
KIT_RANKS = ['minor', 'major', 'captain', 'chieftain']
# Halo 2 Jackals (extract_h2_jackal.py): one model, three ranks. Ultra (the CE pack's plasma-rifle Ultra moved onto
# the Halo 2 body, same class and DoomEdNum), Zealot (Spiker, gold shield) and Sniper (Halo 2's beam rifle, no shield)
H2JACKAL = r'objects\characters\jackal\jackal'
H2BEAM = bp.H2BEAM
H2J_JSON = f'{bp.OUT}/models/H2Jackal/H2Jackal.json'
H2J_NO_SHIELD = ('sniper', 'marksman')        # ranks that carry no arm shield (Halo 3's long-range Jackals)
# armour change colours per rank (primary, secondary, tertiary): Ultra and Sniper take the Halo 2 major / minor
# biped colours; the Zealot is a custom gold with pale trim
H2J_COLOURS = {'ultra': 'major', 'sniper': 'minor', 'marksman': 'major',
               'zealot': [[1.0, 0.84, 0.32], [0.95, 0.92, 0.80], [0.85, 0.62, 0.16]]}

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
        # the other one-handed Covenant guns the Drone model carries (extract_h2.DRONE_WEAPONS)
        for wref, key in ((r'weapons\needler\needler', 'needler'), (CE_PR, 'plasma rifle'), (SPIKER, 'spiker')):
            dv = copy.deepcopy(jv)
            dv['ranged_combat']['reference'] = wref
            variants[DRONE + ' ' + key] = dv
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
    # Halo 2 Jackals: the Ultra keeps the CE Ultra's combat data (moved out of the main pack, build_pack.MOVED); the
    # Zealot is a tougher Ultra with the Spiker; the Sniper starts from the CE Minor and keeps its distance
    ultra = bp.MOVED.get(r'characters\jackal\jackal ultra plasma rifle')
    if ultra and os.path.exists(H2J_JSON):
        actors[H2JACKAL] = copy.deepcopy(A['actors'][ultra['actor_reference']])
        jb = copy.deepcopy(A['bipeds'][ultra['unit_reference']]); jb['change_colors_list'] = []
        bipeds[H2JACKAL] = jb
        def h2j(src, rank, body, shield, wref, **kw):
            v = copy.deepcopy(src)
            v['unit_reference'] = H2JACKAL; v['actor_reference'] = H2JACKAL
            v['unit'] = dict(v['unit'], maximum_body_vitality=float(body), maximum_shield_vitality=float(shield))
            v['ranged_combat']['reference'] = wref
            v['change_colors'] = None; v['change_colors_list'] = []
            v['_rank'] = rank; v['_late'] = True
            v.update(kw)
            return v
        variants[H2JACKAL + '\\jackal ultra plasma rifle'] = h2j(ultra, 'ultra', 100, 350, CE_PR)
        variants[H2JACKAL + '\\jackal zealot spiker'] = h2j(ultra, 'zealot', 120, 450, SPIKER)
        sn = h2j(A['variants'][r'characters\jackal\jackal minor plasma pistol'], 'sniper', 60, 0, H2BEAM,
                 _ov=dict(stance='rifle', shield=0, flags=['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades']))
        sn['ranged_combat'].update(combat_range_lower_bound=8.0, combat_range_upper_bound=28.0, maximum_firing_range=48.0)
        sn['items']['grenades_lower_bound'] = 0; sn['items']['grenades_upper_bound'] = 0
        variants[H2JACKAL + '\\jackal sniper beam rifle'] = sn
        # Marksmen (Halo 3's carbine Jackals): the Sniper's build with the plasma carbine or the pulse carbine, a
        # little closer in; no shield, rifle stance
        for wref, key in ((CARBINE, 'plasma carbine'), (PULSE, 'pulse carbine')):
            mk = h2j(A['variants'][r'characters\jackal\jackal minor plasma pistol'], 'marksman', 70, 0, wref,
                     _ov=dict(stance='rifle', shield=0, flags=['HCE_Surprise', 'HCE_Panics', 'HCE_SeeksCover', 'HCE_Evades']))
            mk['ranged_combat'].update(combat_range_lower_bound=6.0, combat_range_upper_bound=22.0, maximum_firing_range=40.0)
            mk['items']['grenades_lower_bound'] = 0; mk['items']['grenades_upper_bound'] = 0
            variants[H2JACKAL + f'\\jackal marksman {key}'] = mk
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
			let d = HCE_DroneBase(it.thing);
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

	// Its gift (as in Halo 3): every second it overshields the allies around it that are in a fight and in
	// its sight, with a pink tether to each. Shielded allies are topped up past their maximum (to 1.5x);
	// unshielded ones (Grunts, Jackals' bodies...) get a small shield of their own. Out of its reach for a few
	// seconds, or when it dies, the gift goes away: overshields fall back to their maximum, given shields vanish.
	Array<HaloDoom_EnemyBase> hce_buffed;
	Array<int> hce_buffAt;
	Array<bool> hce_buffGiven;
	HaloDoom_EnemyBase hce_buffNear;

	bool HCE_EngAlly(HaloDoom_EnemyBase e)
	{
		return e && e != self && e.hce_enabled && e.health > 0 && e.hce_team == hce_team && e.bFRIENDLY == bFRIENDLY
			&& !(e is GetClass()) && e.HCE_Alerted() && String.Format("%s", e.GetClassName()).IndexOf("Stealth") < 0;   // cloaked Elites stay shieldless
	}

	void HCE_EngPulse()
	{
		hce_buffNear = null;
		double best = 1e9;
		let it = BlockThingsIterator.Create(self, 420);
		while(it.Next())
		{
			let e = HaloDoom_EnemyBase(it.thing);
			if(!HCE_EngAlly(e)) continue;
			double d = Distance3D(e);
			if(d > 420 || !CheckSight(e, SF_IGNOREVISIBILITY)) continue;
			if(d < best) { best = d; hce_buffNear = e; }
			int k = hce_buffed.Find(e);
			bool given = false;
			let sh = ShieldProcessor(e.FindInventory("ShieldProcessor", true));
			if(!sh)
			{
				sh = e.A_SetupShield(40 * HCE_ShieldScale(), 35 * 3, 35 * 2, "Shield/Explode", "", "Shield/Regenerate", "HCE_Shield");
				if(!sh) continue;
				given = true;
				e.A_StartSound("Shield/Regenerate", CHAN_AUTO, CHANF_OVERLAP, 0.7);
			}
			else if(sh.shields < sh.maxshields * 1.5)
				sh.shields = min(sh.maxshields * 1.5, max(sh.shields, 0) + sh.maxshields * 0.2);
			if(k >= hce_buffed.Size()) { hce_buffed.Push(e); hce_buffAt.Push(level.maptime); hce_buffGiven.Push(given); }
			else hce_buffAt[k] = level.maptime;
		}
		// lapsed gifts
		for(int i = hce_buffed.Size() - 1; i >= 0; i--)
			if(!hce_buffed[i] || hce_buffed[i].health <= 0 || level.maptime - hce_buffAt[i] > 35 * 4) HCE_EngRelease(i);
	}

	void HCE_EngRelease(int i)
	{
		let e = hce_buffed[i];
		if(e && e.health > 0)
		{
			let sh = ShieldProcessor(e.FindInventory("ShieldProcessor", true));
			if(sh)
			{
				if(hce_buffGiven[i]) { e.A_StopSound(ShieldProcessor.CHAN_SHIELDLOOP); sh.Destroy(); }
				else sh.shields = min(sh.shields, sh.maxshields);
			}
		}
		hce_buffed.Delete(i); hce_buffAt.Delete(i); hce_buffGiven.Delete(i);
	}

	void HCE_EngTether()
	{
		vector3 from = pos + (0, 0, height * 0.5);
		for(int i = 0; i < hce_buffed.Size(); i++)
		{
			let e = hce_buffed[i];
			if(!e || e.health <= 0 || level.maptime - hce_buffAt[i] > 40) continue;
			vector3 d = level.Vec3Diff(from, e.pos + (0, 0, e.height * 0.55));
			int n = clamp(int(d.Length() / 24), 2, 18);
			double ph = (level.maptime % 12) / 12.0;
			for(int k = 0; k < n; k++)
			{
				double t = (k + ph) / n;
				vector3 o = d * t + (frandom(-1.5, 1.5), frandom(-1.5, 1.5), sin(t * 180) * 6);
				A_SpawnParticle(k % 2 ? "FF8CE8" : "C69CFF", SPF_FULLBRIGHT, 4, 3, 0, o.x, o.y, o.z + height * 0.5, 0, 0, 0, 0, 0, 0, 0.85, -0.15);
			}
		}
	}

	override void Tick()
	{
		super.Tick();
		if(health <= 0 || bDORMANT || isFrozen()) return;
		if(level.maptime % 35 == 7) HCE_EngPulse();
		if(level.maptime % 3 == 0) HCE_EngTether();
		if(hce_animLock > 0) return;
		// it keeps near the fight: drifts toward the allies it's shielding, but no closer than ~200
		if(hce_buffNear && hce_buffNear.health > 0)
		{
			double d = Distance2D(hce_buffNear);
			if(d > 300 || d < 200)
			{
				double a = AngleTo(hce_buffNear) + (d < 200 ? 180 : 0) + frandom(-25, 25);
				if(level.maptime >= hce_driftNext || abs(DeltaAngle(hce_driftAngle, a)) > 60)
				{
					hce_driftAngle = a; hce_driftSpeed = frandom(1.4, 2.2);
					hce_driftNext = level.maptime + 35 * 2;
				}
			}
		}
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
		for(int i = hce_buffed.Size() - 1; i >= 0; i--) HCE_EngRelease(i);
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
	// Particle beam rifle: every shot is telegraphed by a second-long aiming laser and the sniper glint, then one hitscan beam
	override void HCE_UpdateFiring(double dist)
	{
		super.HCE_UpdateFiring(dist);
		if(hce_chargeTics > 0 && target)
		{
			if(hce_chargeTics & 1) HCE_BeamTrace(false);
			HCE_SniperGlint(level.Vec3Diff(pos, Vec3Angle(hce_gunOffset.x, angle, height * 0.5 + hce_gunOffset.z)), hce_chargeTics);
		}
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

def h2jackal_skin(cls, v, si, mat, meta, skin_dir):
    """Halo 2 Jackal skins: armour change colours per rank; the Sniper carries no shield (its surfaces hidden)"""
    names = meta.get('mesh_names')
    if not names or not mat.startswith('H2Jackal_'): return None
    nm = names[si]
    os.makedirs(skin_dir, exist_ok=True)
    rank = v.get('_rank')
    if nm.startswith('shield.') and rank in H2J_NO_SHIELD:
        hid = f'{skin_dir}/hce_hidden.png'
        if not os.path.exists(hid): Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(hid)
        return 'hce_hidden.png'
    shader = nm.split('.', 1)[1]
    src = f'{bp.OUT}/models/H2Jackal/H2Jackal_{shader}.png'
    mp = f'{bp.OUT}/models/H2Jackal/H2Jackal_{shader}_mask.png'
    if not os.path.exists(mp):
        fn = f'h2jackal_{shader}.png'
        if not os.path.exists(f'{skin_dir}/{fn}'): shutil.copy(src, f'{skin_dir}/{fn}')
        return fn
    fn = f'h2jackal_{rank}_{shader}.png'
    dst = f'{skin_dir}/{fn}'
    if os.path.exists(dst): return fn
    cols = H2J_COLOURS.get(rank, 'minor')
    if isinstance(cols, str): cols = meta['change_colors'][cols]
    im = Image.open(src).convert('RGB')
    rgb = np.asarray(im).astype(np.float64) / 255.0
    mk = np.asarray(Image.open(mp).convert('RGB').resize(im.size)).astype(np.float64) / 255.0
    for ch, col in enumerate(cols[:3]):                   # red / green / blue mask = primary / secondary / tertiary
        if col is None: continue
        m_ = mk[..., ch:ch + 1]
        rgb = rgb * (1 - m_) + rgb * np.array(col) * 1.5 * m_
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(dst)
    return fn

def h2jackal_code():
    meta = json.load(open(H2J_JSON))
    return f'''
	// ---- Halo 2 Jackal: its arm shield rides the 'shield' node of the right forearm, the gun is in the left hand
	override Name HCE_ShieldBone() {{ return '{meta['shield_bone']}'; }}
	override Name HCE_GunHandBone() {{ return '{meta['hand_bone']}'; }}
	override int HCE_ShieldSurface() {{ return {meta['shield_surface']}; }}
'''

def h2jackal_sounds():
    """Halo 2's Jackal shield popping (jackal_shield_death) -> HCE/Jackal/ShieldPop (played for every Jackal's shield)"""
    if not os.path.exists(H2J_JSON): return []
    meta = json.load(open(H2J_JSON))
    dst = f'{PACK}/sounds/hce_dig/jackal'; os.makedirs(dst, exist_ok=True)
    lines = ['', "// Jackal shield pop (Halo 2's jackal_shield_death)"]; ids = []
    for i, f in enumerate(meta.get('sounds', [])):
        shutil.copy(f'{bp.OUT}/models/H2Jackal/{f}', f'{dst}/{os.path.basename(f)}')
        sid = f'HCE/Jackal/ShieldPop/{i}'; lines.append(f'{sid} "sounds/hce_dig/jackal/{os.path.basename(f)}"'); ids.append(sid)
    if ids: lines.append(f'$random HCE/Jackal/ShieldPop {{ {" ".join(ids)} }}')
    return lines

def kit_code():
    """armour kit dressing: per rank, a weighted pick per slot (model attachments 1-6) or a whole outfit"""
    if not os.path.exists(KIT_JSON): return '\tvoid HCE_DressArmour() {}\n'
    kit = json.load(open(KIT_JSON))
    meta = json.load(open(OUT + '/models/Brute/Brute.json'))
    armour = [i for i, n in enumerate(meta['mesh_names']) if not n.startswith('weapon_') and n.split('.')[0] not in ('body', 'head', 'hair', 'sensors')]
    pools, outfits, keep = [], [], []
    for r in KIT_RANKS:
        rd = kit['ranks'][r]
        for slot in kit['slots']: pools.append('|'.join(f'{f}:{w}' for f, w in rd['slots'][slot]))
        outfits.append('|'.join(f'{c};' + ','.join(o[slot] for slot in kit['slots']) for c, o in rd['outfits']))
        keep.append(rd['keep_base'])
    pool_cases = ''.join(f'\t\t\tcase {i}: return "{p}";\n' for i, p in enumerate(pools))
    out_cases = ''.join(f'\t\t\tcase {i}: return "{o}";\n' for i, o in enumerate(outfits) if o)
    keep_cases = ''.join(f'\t\t\tcase {i}: return {k};\n' for i, k in enumerate(keep) if k)
    hide = ''.join(f'\t\t\tA_ChangeModel(\'None\', 0, "", \'None\', {i}, "models/hce_dig/Brute/skins", \'hce_hidden.png\', CMDL_USESURFACESKIN);\n' for i in armour)
    n = len(kit['slots'])
    return f'''
	// ---- armour kit (extract_brute_kit.py): each Minor / Major / Captain rolls its own helmet, chest, shoulder,
	// arm, leg and waist pieces when it spawns (some ranks may also roll a whole outfit); the Chieftain keeps
	// Tartarus's look or wears one of the kit's chieftain sets. Pieces are model attachments {{1-{n}}} riding the
	// Brute's own bones; their textures are named in the piece models.
	String hce_kitHelmet;
	static String HCE_KitPool(int i)
	{{
		switch(i)
		{{
{pool_cases}		}}
		return "";
	}}
	static String HCE_KitOutfits(int r)
	{{
		switch(r)
		{{
{out_cases}		}}
		return "";
	}}
	static double HCE_KitKeepBase(int r)
	{{
		switch(r)
		{{
{keep_cases}		}}
		return 0;
	}}
	static String HCE_KitRoll(String pool)
	{{
		Array<String> opts; pool.Split(opts, "|");
		double tot = 0;
		for(int i = 0; i < opts.Size(); i++) {{ Array<String> p; opts[i].Split(p, ":"); if(p.Size() > 1) tot += p[1].ToDouble(); }}
		double x = frandom[HCEKit](0, tot);
		for(int i = 0; i < opts.Size(); i++)
		{{
			Array<String> p; opts[i].Split(p, ":");
			if(p.Size() < 2) continue;
			x -= p[1].ToDouble();
			if(x <= 0) return p[0];
		}}
		return "";
	}}
	void HCE_DressArmour()
	{{
		String cn = GetClassName();
		int r = cn.IndexOf("Minor") >= 0 ? 0 : cn.IndexOf("Major") >= 0 ? 1 : cn.IndexOf("Captain") >= 0 ? 2 : cn.IndexOf("Chieftain") >= 0 ? 3 : -1;
		if(r < 0) return;
		double keep = HCE_KitKeepBase(r);
		if(keep > 0 && frandom[HCEKit](0, 1) < keep) return;
		Array<String> pick;
		for(int s = 0; s < {n}; s++) pick.Push("");
		bool outfit = false;
		String outs = HCE_KitOutfits(r);
		if(outs.Length() > 0)
		{{
			Array<String> ol; outs.Split(ol, "|");
			double x = frandom[HCEKit](0, 1);
			for(int i = 0; i < ol.Size() && !outfit; i++)
			{{
				Array<String> p; ol[i].Split(p, ";");
				if(p.Size() < 2) continue;
				double c = p[0].ToDouble();
				if(x < c)
				{{
					Array<String> f; p[1].Split(f, ",");
					for(int s = 0; s < {n} && s < f.Size(); s++) pick[s] = f[s];
					outfit = true;
				}}
				else x -= c;
			}}
		}}
		if(!outfit) for(int s = 0; s < {n}; s++) pick[s] = HCE_KitRoll(HCE_KitPool(r * {n} + s));
		if(r == 3)
		{{
{hide}		}}
		for(int s = 0; s < {n}; s++)
			if(pick[s].Length() > 0) A_ChangeModel('None', s + 1, "models/hce_dig/BruteKit", pick[s], s + 1, "", 'None');
		hce_kitHelmet = pick[0];
		if(hce_kitHelmet.Length() == 0 && r < 3) hce_helmetOff = true;     // bare-headed: nothing to knock off
	}}
'''

def brute_code():
    return kit_code() + '''
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
		HCE_DressArmour();                     // before any animation starts (A_ChangeModel resets the current one)
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
		HCE_KnockHelmet(inflictor ? inflictor : source);
		HCE_Say('PainHeavy', 1.0, 0, true);
	}
	void HCE_KnockHelmet(Actor from)
	{
		hce_helmetOff = true;
		A_ChangeModel('None', 1, "", 'None', 1, "", 'None', CMDL_HIDEMODEL);           // the kit helmet (attachment 1) flies off
		let h = HCE_BruteHelmetDebris(Spawn("HCE_BruteHelmetDebris", pos + (0, 0, height * 0.95), ALLOW_REPLACE));
		if(h)
		{
			h.hce_piece = "debris_" .. hce_kitHelmet;
			double a = from ? from.AngleTo(self) : angle + 180;
			h.vel = (AngleToVector(a + frandom(-30, 30), frandom(3, 6)), frandom(4, 7));
			h.angle = angle;
		}
	}
	// decapitated with the kit helmet still on: it comes off too (the gib is the bare head)
	override void HCE_OnSever(int limb, bool gunArm)
	{
		if(limb == HCE_LIMB_HEAD && !hce_helmetOff && !HCE_HelmetFixed() && hce_kitHelmet.Length() > 0) HCE_KnockHelmet(target);
	}
	override color HCE_ShieldColor() { return Color(255, 255, 200, 90); }       // the Chieftain's gold overshield
	bool HCE_HelmetFixed() { String cn = GetClassName(); return hce_chief || cn.IndexOf("HonorGuard") >= 0; }   // honor guard helmets are part of the armour
	// the helmet takes the first head hit (it flies off instead): only a bare head can be headshot
	override bool HCE_HeadProtected() { return !hce_helmetOff || HCE_HelmetFixed(); }
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
    # Halo 2 Jackals and Halo 2's beam rifle (it behaves like HaloDoom's: a held beam whose damage climbs while it
    # stays on a target, fired in ~1 s bursts with a cool-down between them; HDE's laser sounds)
    if os.path.exists(H2J_JSON):
        bp.SKIN_HOOK['H2Jackal'] = h2jackal_skin
        bp.TYPE_CODE['H2Jackal'] = h2jackal_code()
        bp.SHIELD_MAT['H2Jackal'] = 'H2Jackal_jackal_shield'
        bp.VOICES['H2Jackal'] = 'Jackal'
    # (the beam rifle itself is set up in build_pack.py: the Spec Ops Elite carries it too)
    bp.TYPE_CODE['ThornBeast'] = THORN_CODE
    bp.TYPE_CODE['Engineer'] = ENGINEER_CODE
    bp.BASE_CODE['Drone'] = DRONE_CODE    # every Drone shares it (the swarm finds its mates of any weapon)
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
        # Halo 2 Brutes: scaled to 90% so a Brute stands as tall as an Elite (its rifle idle is 0.90 WU tall against
        # the Elite's 0.80; full size would not fit Doom doors), melee 2.0 WU / 1.5 WU from their char tag, berserk
        # charge that throws the gun away, plasma grenades
        'Brute': dict(stance={'gravity hammer': 'melee', None: 'rifle'}, scale=0.9,
                      height_fixed=68, radius_fixed=26, melee=(120, 35), weapon_toss=True, shield=0, speed=5.5,
                      flags=['HCE_Surprise', 'HCE_Berserks', 'HCE_Evades', 'HCE_ThrowsGrenades', 'HCE_Leader']),
        'H2Jackal': dict(stance='pistol'),
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
           DRONE: 'Drone', BRUTE: 'Brute', H2JACKAL: 'H2Jackal'}
    team = {'Drinol': 'COVENANT', 'SlugMan': 'COVENANT', 'EliteRifle': 'COVENANT', 'BlindWolf': 'COVENANT', 'ThornBeast': 'COVENANT', 'Engineer': 'COVENANT', 'Drone': 'COVENANT', 'Brute': 'COVENANT', 'H2Jackal': 'COVENANT'}
    cfg = dict(char_of_unit=cou, team=team, ai=ai, pack=PACK, mdir='hce_dig', tag='dig', ed0=30400, main=False,
               handler='HCE_DigsiteHandler', nerf_mixin='HCE_DigNerfMixin', late_chars=['BlindWolf', 'ThornBeast', 'Engineer', 'Drone', 'Brute', 'H2Jackal'],
               late_order=['HCE_BlindWolf', 'HCE_RandomBlindWolf', 'HCE_ThornBeast', 'HCE_RandomThornBeast',
                           'HCE_EliteMinorPulseCarbine', 'HCE_EliteMajorPulseCarbine', 'HCE_EliteSpecopsPulseCarbine',
                           'HCE_EliteCommanderPulseCarbine', 'HCE_Engineer', 'HCE_RandomEngineer', 'HCE_DronePlasmaPistol', 'HCE_RandomDrone',
                           'HCE_BruteMinorPlasmaRifle', 'HCE_BruteMinorAssaultRifle', 'HCE_BruteMajorSpiker', 'HCE_BruteMajorShotgun', 'HCE_BruteCaptainPlasmaRifle', 'HCE_BruteCaptainShotgun', 'HCE_BruteHonorGuardPlasmaRifle', 'HCE_BruteHonorGuardAssaultRifle', 'HCE_BruteChieftainGravityHammer', 'HCE_RandomBrute',
                           'HCE_JackalUltraPlasmaRifle', 'HCE_JackalZealotSpiker', 'HCE_JackalSniperBeamRifle', 'HCE_RandomH2Jackal',
                           'HCE_JackalMarksmanPlasmaCarbine', 'HCE_JackalMarksmanPulseCarbine',
                           'HCE_DroneNeedler', 'HCE_DronePlasmaRifle', 'HCE_DroneSpiker'], index='digsite_index.json', glow=[f'w_cmt_carbine_{b}{k}.png' for b in ('', 'blue_') for k in ('lights', 'icon', 'meter')] + ['w_spiker_heat.png'],
               gl_title='// Digsite add-on: glowing surfaces')
    bp.build(cfg)
    src = HERE + '/digsite_src'
    for f in ('dig_handler.zsc', 'dig_boss.zsc', 'dig_pulse.zsc', 'dig_brute.zsc'):
        shutil.copy(f'{src}/{f}', f'{PACK}/ZScript/HaloCE/{f}')
    for f in ('zscript.txt', 'cvarinfo.txt', 'CREDITS.txt'):
        shutil.copy(f'{src}/{f}', f'{PACK}/{f}')
    open(f'{PACK}/sndinfo.dig', 'w').write('\n'.join(voices() + thorn_sounds() + engineer_sounds() + drone_sounds() + brute_sounds() + h2jackal_sounds()) + '\n')
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
        # no Skin line: the model names its own texture, so the kit helmets swapped in keep theirs
        open(f'{PACK}/modeldef.dig', 'a').write('\nModel HCE_BruteHelmetDebris\n{\n\tPath "models/hce_dig/BruteHelmet"\n'
            '\tModel 0 "BruteHelmet.iqm"\n\tScale 72 72 86\n\tUseActorPitch\n\tUseActorRoll\n'
            '\tFrameIndex HCEM A 0 0\n}\n')
    # Brute armour kit pieces (model attachments, swapped in by HCE_DressArmour)
    if os.path.exists(KIT_JSON):
        kd = f'{PACK}/models/hce_dig/BruteKit'; os.makedirs(kd, exist_ok=True)
        for f in os.listdir(KIT_DIR):
            if f.endswith(('.iqm', '.jpg', '.png')): shutil.copy(f'{KIT_DIR}/{f}', f'{kd}/{f}')

if __name__ == '__main__':
    build()
