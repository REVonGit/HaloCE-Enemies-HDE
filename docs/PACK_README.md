# Halo CE Enemy Pack for UZDoom / HaloDoom Evolved

Halo: Combat Evolved's campaign enemies (plus Marines) are extracted from the ten Xbox campaign `.map` files. Each one is an **IQM model with its full Halo animation set**, and its AI is translated from the Halo CE decomp into **ZScript** on top of an extended `enemies_base.zsc`. The Digsite / SPV3 / Halo 2 add-on adds Drones, Brutes and their Chieftain, the Engineer, Blind Wolf, Thorn Beast, Slug Men and the Drinol.

| | |
|---|---|
| Characters | Halo CE's 14 (Grunt, Grunt Spec-Ops, Jackal, Jackal Major/Ultra, Elite, Elite Special, Hunter, the Flood's Infection, Carrier, Combat Elite and Combat Human forms, Sentinel, Marine, Armored Marine), the ODSTs (Spiral's and Halo 2's) and Fire Team Raven, Sergeants Johnson and Stacker, and the add-on's creatures |
| Placeable classes | 212 DoomEdNums (the table at the end), plus `HCE_Random<Character>` spawners among them |
| Animations | 40–200+ per character, played by name (`SetAnimation`). Fire, flinch and reload overlays are baked into standalone clips |
| Weapons | Each enemy holds its Halo weapon as a model bound to Halo's hand marker; Marines carry the whole HaloDoom Evolved arsenal |
| Skins | Halo base maps, with each variant's colours (Minor/Major/Spec-Ops etc.) pre-baked from the multipurpose map's change-colour mask |
| Stats | Health, shields, weapon, burst timing, accuracy, ranges and grenade counts come straight from each variant's `actv`/`actr`/`coll` tags |

## Requirements and load order

* **UZDoom**. The enemy pack uses ZScript `version "4.15.1"`.
* **HaloDoom Evolved, Local_DEV branch, unmodified.** HDE supplies the projectiles, grenades, `ShieldProcessor`, weapon sounds and player. The pack's extended enemy API rides in `HaloCE_Covenant.pk3` and overrides HDE's own file (below), so you never edit or rebuild Local_DEV.
* **Nash's Gore Mod** (optional): load it last.

### The packs

| Pack | Contents |
|---|---|
| `HaloCE_Covenant.pk3` | **Required, the main pack.** The Core (Doom-monster replacement handler, enemy projectiles and explosives, CVars, console commands, menus), the enemy API, the Covenant (Grunts, Jackals, Elites, Hunters, the Doom boss stand-ins), the Digsite / SPV3 / Halo 2 add-on and the enemy dialogue |
| `HaloCE_Marines.pk3` | Marines (Doom's marines and allied monsters become these), the ODSTs, the Marine arsenal, Sergeants Johnson and Stacker, the Marine dialogue and the Master Chief's squad orders |
| `HaloCE_Flood.pk3` | Infection, carrier and combat forms |
| `HaloCE_Sentinels.pk3` | Sentinels |

Load order: HDE (Local_DEV) → `HaloCE_Covenant.pk3` → `HaloCE_Flood.pk3` / `HaloCE_Sentinels.pk3` / `HaloCE_Marines.pk3` (any order) → `nashgore.pk3` (optional, last).

```
uzdoom -file HDE_LocalDEV.pk3 HaloCE_Covenant.pk3 HaloCE_Flood.pk3 HaloCE_Sentinels.pk3 HaloCE_Marines.pk3
```

The replacement table lives in the Covenant pack's core. Any pick whose faction pack isn't loaded is skipped, and the remaining picks share its weight; a Doom monster whose whole list is missing stays a Doom monster.

* **Everything in one file:** `build.py` also writes `dist/HaloCE_Merged.pk3`; load it right after HDE, instead of the separate packs, never with them.
* **Merging your own set:** `tools/merge_hce_packs.py <packs...> -o <out.pk3>` merges any set of these packs (one `zscript.txt`, one `mapinfo.txt`, joined `cvarinfo.txt` and `CREDITS.txt`; it stops and names any file or DoomEdNum two packs disagree on).
* **Older downloads:** don't load `HaloCE_Core`, `HCE_EnemyAPI_LocalDEV`, `HaloCE_Enemies_Voices` or `HaloCE_Enemies_Digsite` pk3s from earlier releases with these: the Covenant pack carries all of them now, and their classes would be defined twice.

### How the enemy API is loaded

UZDoom resolves every `#include` to the **last-loaded** file with that path.

* **`HaloCE_Covenant.pk3`** carries `ZScript/BaseAI/enemies_base.zsc`. HDE's own `ZSCRIPT.txt` already includes that path, so loading the pack after HDE swaps in the extended API; HDE's files stay untouched and the class is never defined twice.
  * The file keeps every member of Local_DEV's original `HaloDoom_EnemyBase` and `LastDamageInfo`, plus its usage example.
  * It compiles under Local_DEV's `version "4.10.0"`. The one 4.12+ call (`SetAnimation`) sits behind a virtual hook, `HCE_ApplyAnim`, which the enemy pack implements in its own 4.15.1 unit.
* That's why the pack must load **after** HDE.

> **Local_DEV crash note:** if UZDoom crashes during "Texman.Init" (signal 11) with a Local_DEV pk3, check whether the pk3 was zipped with the `Raw_Assets/` folder. That 2.6 GB folder of source art is what crashes texture init. A Local_DEV pk3 without `Raw_Assets/` and `.git/` (~500 MB) runs fine on current UZDoom.

## Using it

* **Place in maps:** use the DoomEdNums in the table at the end, or the `HCE_Random*` spawners for a random variant of a character.
* **Summon:** e.g. `summon HCE_EliteMajorPlasmaRifle`.
* **Spawn everything:** the console command `punkassbitches` spawns one of every enemy class that's loaded (every pack and add-on), side by side in lines in front of you and facing you: 640 units of enemies per line, a line every 128 units. They don't patrol or walk to squad stations while idle, so they hold their place in the line until they see something to fight (flyers still hover). Spots blocked by walls are retried further ahead, then behind you, then anywhere free within 1024 units. Marines come out as allies. A class with several looks stands in the line once per look, so all three Brute Chieftains (Tartarus's look and both kit sets) appear. It's a console alias (`KEYCONF`) for `netevent hce_spawnall`, so it works in multiplayer too.
* **Spawn every ODST:** `helljumpers` does the same with only the ODSTs (the ODST rifle and shotgun troopers and Fire Team Raven), as allies.
* **Spawn every Marine:** `leatherneck` does the same with only the Marines: every Marine and Armored Marine class (each gun, both ranks) and Sergeants Johnson and Stacker, as allies, in the same lines. They don't move at all (no following, no squad orders, no dives): each turns, aims and fights from his spot. It's an alias for `netevent hce_spawnmarines`.
* **Spawn every Marine, free to move:** `leatherneck2` spawns the same Marines in the same lines, but they aren't pinned: they join your squad, follow you, dive and take orders like any other Marine. It's an alias for `netevent hce_spawnmarines2`.
* **Doom monsters are replaced automatically.** See the next section for what replaces what. To keep Doom's monsters, set `hce_keepdoommonsters 1`.

| CVar | Default | Effect |
|---|---|---|
| `hce_keepdoommonsters` | false | Leave Doom's monsters alone (Doom's scripted marines are still replaced) |
| `hce_hunterpairs` | true | A lone Hunter spawns with its bond brother |
| `hce_nerf_projectiles` | 0.4 (standalone: 0.3) | **Enemy projectile nerf.** Covers everything an enemy fires or throws: bullets, plasma, needles, spikes, rockets, fuel rods, grenades, Plasma Caster shots, beams, and their blasts and fuel-rod toxic clouds. Melee is untouched, and Marines' shots are not affected |
| `hce_nerf_health` | 0.6 | Enemy health multiplier (Marines unaffected) |
| `hce_nerf_shields` | 0.5 | Enemy energy shields and Jackal shield-gauntlet strength |
| `hce_enemydamage` | 1.0 | An extra multiplier on enemy projectile damage, on top of `hce_nerf_projectiles` |
| `hce_dropweapons` | true | Enemies drop the weapon they carried (and sometimes grenades), like in Halo |
| `hce_betrayal` | true | Marines turn on a player who keeps shooting them (see [Your squad](#your-squad)) |
| `hce_bodyblood` | false | Blood on the body: splatter overlays that build up as an enemy is hurt (see [Blood on the body](#blood-on-the-body)); also under Options > Halo CE Gore |
| `hce_dismember` | true | Weapon-based dismemberment and gibbing, and gun arms shot off (see [Dismemberment](#dismemberment)) |
| `hce_grenadefreq` | 1.0 | Scales how often enemies throw grenades |
| `hce_grenadedodge` | true | Enemies that notice a live grenade near them dive or run clear |
| `hce_jumping` | true | Enemies jump, climb and vault onto ledges and over low obstacles in their way (see [Climbing and vaulting](#climbing-and-vaulting)) |
| `hce_burstpause` | 1.0 | Scales the pause between enemy bursts (1.5 = 50% longer, easier; 0.75 = more aggressive) |
| `hce_enemyspread` | 1.75 | Enemy aim error multiplier (automatic weapons also bloom over a burst; Marines unaffected) |
| `hce_enemytracking` | 5.0 | How fast enemy aim follows a moving target, in map units a tic (lower = easier to strafe out of) |
| `hce_hearing` | 1024 | How far gunfire wakes idle enemies (deaf/ambush enemies only wake on sight, as in Doom) |
| `hce_maxpursuers` | 4 | At most this many enemies of a team hunt one target they can't see at a time; the rest hold position (0 = no limit) |
| `hce_squads` | true | Grunts and Jackals form squads around the nearest Elite or Brute and follow its lead |
| `hce_difficulty` | -1 | **Halo difficulty** (see [Halo difficulty](#halo-difficulty)): -1 follows the skill level (I'm Too Young To Die and Hey, Not Too Rough are Easy, Hurt Me Plenty Normal, Ultra-Violence Heroic, Nightmare Legendary); 0 Easy, 1 Normal, 2 Heroic, 3 Legendary pin one. Also under Options > Halo CE AI |
| `hce_cover` | true | Enemies and Marines fight from cover: they lean out past corners and shoot over low walls (see [Cover](#cover)) |
| `hce_search` | true | The Covenant search for a target they lost and go back to their post when they give up; enemies investigate explosions they hear and notice a flashlight's beam (see [Searching](#searching)) |
| `hce_corpseshoot` | 0.25 | Chance a Marine or Covenant soldier puts a few more rounds into an enemy it has just killed (guns that don't blow up only; 0 turns it off) |
| `hce_tactics` | true | Squad tactics: Marine fire teams and battle drills, Covenant lances in echelons (see [Squad tactics](#squad-tactics)) |
| `hce_patrols` | true | Idle enemies walk short patrols around where they were placed (or along a map's PatrolPoint route) |
| `hce_sleepinggrunts` | 0.3 | Chance that a Grunt placed in a map starts asleep (Grunts placed as deaf/ambush always do; 0 = never) |

Marines are on the human team and fight Covenant and Flood alongside the player. Their stray shots can still hit you, as in Halo.

## Replacing Doom's monsters

Each Doom monster becomes the Halo CE enemy with the closest role, toughness and threat.

If Doom monsters are left on a map, the console says how many and why at map start. That happens when `hce_keepdoommonsters` is on, or when another mod loaded after this pack replaces them first. Monsters with no loaded faction to become aren't counted. (Older builds used `hce_replacemonsters`, which your ini may still hold as `false`; it's ignored now.) The rank mix shifts with the skill level (easy = skills 1–2, normal = 3, hard = 4–5). Each spawn rolls its own pick.

Each spawn rolls from a weighted mix, so a room of Zombiemen isn't all Grunts. Types are listed most likely first, with the measured share at normal skill (600 rolls each). Easy skills favour the first entries; hard skills shift weight toward the later, stronger ones.

| Doom monster | Halo enemies (most → least likely, normal skill) |
|---|---|
| Zombieman | Minor plasma-pistol Grunt 30%, Major Grunt 18%, Minor needler Grunt 17%, Minor Jackal 16%, Major needler Grunt 11%, Minor Elite 6% |
| Shotgun Guy | Major Grunts (plasma pistol 22%, needler 20%), Minor Jackal 21%, Major (needler) Jackal 13%, Minor Elites 16%, Major Elite 6% |
| Chaingunner | Major (needler) Jackal 36%, Ultra (plasma rifle) Jackal 19%, Spec-Ops needler Grunt 17%, needler Elite 16%, ranged Elite 10% |
| Imp | Major Grunts 55%, Minor Jackal 15%, Minor needler Grunt 14%, Major (needler) Jackal 7%, Minor Elite 7% (Spec-Ops Grunts on hard) |
| Pinky | unarmed Flood Human 41% / Flood Elite 40%, shotgun Flood 18% |
| Spectre | Stealth Elite 44%, stealth Flood Elite 22%, Stealth Major 21%, sword Stealth Major 11% |
| Lost Soul | Flood infection form |
| Cacodemon | Sentinel, Shielded and Defensive Sentinels, Majors on harder skills. With the Digsite add-on (or in a bundle), always Halo 2 Drones |
| Hell Knight | Minor Elites 60%, Ultra (plasma rifle) Jackal 11%, Major Elite 10%, Heavy Elite 10%, Spec-Ops fuel-rod Grunt 9% |
| Baron of Hell | Major Elite (plasma rifle / needler), 1.5× health |
| Arachnotron | Spec-Ops Elite (plasma rifle / needler) |
| Pain Elemental | Flood Carrier (Flood pack); the Digsite add-on makes it the Engineer instead |
| Revenant | Spec-Ops fuel-rod Grunts, Spec-Ops needler Elites (homing needles), Spec-Ops needler Grunts |
| Mancubus | Hunter pair: blue 34%, White 33%, Red 32% |
| Arch-Vile | sword Elite Commander, plasma-rifle Commander, sword Stealth Major |
| Cyberdemon | Hunter pair: Major 42% (2× health), White 37% / Red 20% (3× health) |
| Spider Mastermind | Elite Commander, 4× health |
| Wolfenstein SS | armed Flood Humans (assault rifle, pistol, shotgun, needler; rockets on hard) |

The exact weights per skill tier are the `RULES` table at the top of `ZScript/HaloCE/hce_handler.zsc` (`"Class*weight ..."`), easy to tune.

Commander Keen and the Icon of Sin parts aren't replaced; their map scripts need the originals. The Icon's cubes spawn Doom monsters, which then get replaced as usual.

**Marines are always on your side.** Doom's scripted marines are replaced with Halo Marines matched to their weapon, even with `hce_keepdoommonsters 1`:

| Doom marine | Halo Marine |
|---|---|
| ScriptedMarine, fist, pistol | Marine, assault rifle |
| berserk, chainsaw | Armored Marine, assault rifle |
| shotgun / super shotgun | Marine shotgun / Armored Major shotgun |
| chaingun | Major Marine, assault rifle |
| rocket launcher | Armored Major Marine, assault rifle |
| plasma rifle | Marine, plasma rifle |
| railgun, BFG | Armored Major Marine, plasma rifle |

With replacement on, any other allied (friendly) monster becomes a Marine instead of a Covenant or Flood ally, ranked by its toughness: an allied Imp is a Marine, a stronger ally is an Armored or Armored Major Marine. Its TID, special and ambush flag carry over.

**Boss levels still work.** Barons, Mancubi, Arachnotrons, the Cyberdemon and the Spider Mastermind are replaced by dedicated stand-in classes (`HCE_Boss*`). The pack's `CheckReplacee` maps each one back to its Doom boss, and every Halo enemy calls `A_BossDeath` when it dies. So E1M8's Barons, MAP07's Mancubus and Arachnotron triggers and the Cyberdemon/Spider exits fire as usual. Verified on MAP07: killing the Hunter "Mancubi" lowered the tag-666 walls.

**Drops.** Halo enemies drop the weapon they carried as an HDE pickup (`Halo_PlasmaPistol`, `Halo_Needler`, `Halo_PlasmaRifle`, `Halo_FuelRod`, `Halo_MA5B`, …), so the replaced zombies' clip and shotgun drops still turn into ammo. **The Covenant always drop the weapon they carry**, energy swords included (as HDE's Energy Sword): their gun lands just beside the body, clear of HDE's rule that deletes half of all enemy-dropped guns. Flood and Marines still go through that rule. Grunts and Elites with grenades left may also drop plasma grenades, and Marines frag grenades. Hunters (their fuel-rod cannon is part of the arm) and Sentinels drop nothing. Turn drops off with `hce_dropweapons 0`.

## The Marine arsenal

Every human weapon in HaloDoom Evolved has a Marine who carries it, built from the Halo model you picked for it. Both Marine bodies (Marine and Armored Marine) get each one: `HCE_Marine<Gun>` and `HCE_MarineArmored<Gun>`. `HCE_RandomMarine` and `HCE_RandomMarineArmored` now pick from all of them.

| Gun (class suffix) | Model | Fires | Drops |
|---|---|---|---|
| `Magnum` | Halo CE's pistol | Halo CE pistol rounds (25), pairs and triples | `Halo_Magnum` |
| `Sidekick` | the Macworld 2000 pistol (Digsite) | HDE Sidekick rounds (18) | `Halo_Sidekick` |
| `Ma37` | the E3 2000 assault rifle (Digsite), repainted Reach-style: near-black gunmetal, dark grey furniture, worn steel edges | HDE assault-rifle rounds (9), long bursts | `Halo_AssaultRifle` |
| `AssaultRifle` (unchanged) | Halo CE's assault rifle | MA5B rounds | `Halo_MA5B` |
| `Commando` | HaloDoom Evolved's own Commando (Halo Infinite's), reinterpreted as a Halo CE gun in its own colours: black lower receiver, grey upper and handguard | HDE Commando rounds (14), short bursts | `Halo_Commando` |
| `BattleRifle` | Halo 2's battle rifle | three-round bursts (12 a round) | `Halo_BattleRifle` |
| `Dmr` | the E3 1999 assault rifle (Digsite) | HDE DMR rounds (24), paced single shots | `Halo_DMR` |
| `Smg` | Halo 2's SMG | HDE SMG rounds (6), long bursts | `Halo_SMG` |
| `Shotgun` (unchanged) | Halo CE's shotgun | Halo CE pellets | `Halo_Shotgun` |
| `Bulldog` | HaloDoom Evolved's own Bulldog, reinterpreted as a Halo CE gun: its drum-fed shape cut to a CE polygon budget (1,230 triangles) with one 512x512 CE-style painted texture baked from it (gunmetal receiver, olive-drab stock, drum and fore-end, black rubber grips, painted edge wear) | 8 pellets a shot, two to four shots | `Halo_Bulldog` |
| `DoubleBarrel` | the 1998 Lens Flare demo assault rifle (Digsite) | 14 pellets, one blast at a time; it gibs | `Halo_DBLShotgun` |
| `Sniper` | Halo CE's sniper rifle | Halo CE sniper rounds (101), from far back | `Halo_SniperRifle` |
| `RocketLauncher` | Halo 2's rocket launcher, with its SPNKr lettering decals | Halo CE rockets | `Halo_RocketLauncher` |
| `Hydra` | HaloDoom Evolved's own Hydra (Halo Infinite's) at a Halo CE polygon budget, keeping the .blend's own UV layout and texture (Base Color × AO baked and downscaled to Halo CE's 512×512), its UNSC caution and stripe decals on top; held like a rifle | four-missile salvos of HDE Hydra missiles | `Halo_Hydra` |
| `GrenadeLauncher` | HaloDoom Evolved's own grenade launcher (Halo Reach's launcher on Halo Infinite's Bulldog receiver, with a sniper magazine and a Halo 3 shotgun stock and pump), reinterpreted as a Halo CE gun: 1,298 triangles and one 512x512 CE-style painted texture, every part graded into one olive-drab-over-gunmetal finish | HDE 40 mm grenades, lobbed | `Halo_GrenadeLauncher` |
| `StickyDetonator` | the Sidekick repainted green, with HaloDoom Evolved's sticky charge (Halo Infinite's) seated in its muzzle; once fired the muzzle shows empty until it reloads. Held in Halo 2's pistol stance | HDE sticky charges; the Marine sets each one off 1.5 s after it lands; it gibs | `Halo_StickyDetonator` |
| `Gpmg` | Halo 2's machine-gun turret gun, off its tripod, held by its pistol grip with the stock to the shoulder | HDE GPMG rounds (15, explosive), long bursts; it gibs | `Halo_GPMG` |
| `Flamethrower` | Halo CE's flamethrower, carried the Master Chief's way: Halo CE's flamethrower ('support') stance, moved from the cyborg onto the Marine skeleton (`cyborg_flame_anims.py`, from SPV3's copy of the cyborg's animations): idle, moves, turns, jumps and landings, grenade throw, crouch, the flamethrower melee and reload | Halo CE flames, close in | `Halo_Flamethrower` |

**Sergeant Johnson** (`HCE_SgtJohnson`) carries the **Stanchion** (the Macworld 1999 sniper rifle from Digsite). Each shot takes about 0.7 s of aiming: a glint and a targeting laser show it coming, with the Stanchion's charge sound. Then one rail shot (150) is drawn as a red-orange beam, and it tears apart what it kills. When an enemy gets within about 6 m he switches to his **Magnum** in Halo 2's pistol stance, and goes back to the Stanchion once it's past about 9 m. He is the only Marine with Johnson's face and voice, and he has more health (75) and a harder punch (90). He isn't in the random Marine pool; place him with his DoomEdNum or summon him.

**Sergeant Stacker** (`HCE_SgtStacker`, DoomEdNum 30454) is the white sergeant: Halo CE's sergeant's cap face with the regular Marines' full sleeves (not Johnson's arms and hands), the **double barrel** as his main gun, with an **SMG** as his close-range backup (Halo 2's SMG stance): when both barrels are spent with an enemy within about 11 m he draws the SMG instead of reloading, and goes back to the reloaded double barrel once the enemy is past about 13 m or after 6 seconds, and Halo CE's second sergeant voice (the lines Pete Stacker recorded), which no other Marine uses. He has 60 health and a harder punch (75). Halo CE and Halo 2 have no model of their own for Stacker, so he is built from these parts. Like Johnson, he isn't in the random pool.

**SMG, battle rifle and Bulldog in Halo 2's rifle stance, hands on the grips.** These three Marines use Halo 2's Marine rifle animations (idle, warn, moves, turns, dives, evades, airborne and landings, melee, grenade throw, berserk, signal, celebrate, crouch and fire), re-posed per gun so both hands hold it properly: the right hand on the pistol grip and the left hand on the gun's foregrip (the SMG's vertical grip, the battle rifle's fore-end, the Bulldog's pump grip). The Bulldog has its own version of the set in which the gun is also pulled back so its stock sits in the shoulder. The battle rifle is held lower than Halo 2 has it on these bodies, at the cheek like the assault rifle, not level with the top of the helmet. Grenade throws and hand signals still free the left hand. The other rifles keep Halo CE's rifle stance.

**Pistols in Halo 2's stance.** Both pistols (Magnum, Sidekick) use Halo 2's Marine pistol animations (two-handed aim, moves, turns, dives, evades, melee, crouch, fire), from `01b_spacestation.map`. They are moved onto the Halo CE Marine skeleton, the same biped with the same bones. Halo 2 has no pistol grenade throw, surprise or signal, so those come from Halo CE's pistol set. The Needler Marines keep Halo CE's own pistol set.

**How the guns are attached.** Each gun is its own small model on the body's skeleton, attached as model 6 and weighted to the right hand bone. It sits exactly where Halo puts a held weapon: the placement is the same transform Halo CE's assault rifle has on the hand. The Marines' weapon textures are shared in `models/hce/weapons`, and every arsenal Marine wears its assault-rifle twin's skins.

DoomEdNums 30284–30316 (alphabetical: `HCE_MarineArmoredBattleRifle` … `HCE_MarineStickyDetonator`, then `HCE_SgtJohnson`).

## What the AI does (all verified in-engine)

* **Teams:** Human, Covenant, Flood and Sentinel all fight each other the way they do in Halo, e.g. Flood vs Covenant vs Sentinels on 343 Guilty Spark. Same-team damage is ignored, and same-team explosive splash is halved.
* **Perception:** vision cone and range, hearing, and surprise. Grunts and Jackals react with the "surprise" animation when you appear close by.
* **Waking up and converging:** encounters stay the size the map intended. Before, gunfire woke every enemy Doom's sound reached, map placement flags were ignored, and every awake enemy hunted you down, so two or three encounters' worth piled into one room.
  * **Hearing:** gunfire wakes idle enemies only within `hce_hearing` (1024 units).
  * **Deaf monsters:** monsters a mapper placed as deaf ("ambush") wake only on sight, as in Doom.
  * **Hunting:** at most `hce_maxpursuers` (4) enemies of a team hunt one target they can't see at a time. The rest hold their ground, facing where you were last seen, until you show up.
* **Squad leaders:** Grunts and Jackals pick the nearest Elite or Brute in sight within 768 units as their leader (up to nine per leader).
  * When the leader spots you, the whole squad is alerted and shares the target. Sleeping squadmates wake a moment later.
  * Idle squadmates keep station in a loose ring around the leader and follow it on patrol.
  * In a fight they stay within about 420 units of the leader. With you out of sight, they hold near it instead of hunting you on their own.
  * Kill the leader and the squad is on its own: Grunts usually panic.
  * `hce_squads 0` turns squads off.
* **Patrols:** idle enemies walk short loops around where they were placed: a point 96–288 units away with clear floor, a 3–8 s pause, then the next one.
  * A mapper can lay a route with Doom's **PatrolPoint** things: give the enemy the first point's TID as its goal, and each point's next TID (arg 0) and pause in tics (arg 1).
  * Deaf/ambush enemies stand their post. `hce_patrols 0` turns patrols off.
* **Sleeping Grunts:** some Grunts start asleep, in Halo's sleeping animation (`hce_sleepinggrunts`, 30% by default; Grunts placed deaf/ambush always do). Any of these wakes one, and it wakes startled, with the surprise animation and a yell:
  * you walk within 96 units of it;
  * gunfire within 320 units (not for deaf/ambush Grunts);
  * an ally within 400 units, in its sight, fighting or dying;
  * its squad leader raising the alarm;
  * taking damage.
* **Combat:** pattern burst fire (see Fire patterns), with first-burst delay and projectile error taken from each variant. Units strafe and reposition inside the variant's firing-range band.
* **Aim (accuracy nerf):** enemies don't aim at you; they aim at a point that chases you at a limited speed (`hce_enemytracking`), so strafing drags their fire behind you, and a fresh burst opens off the mark.
  * **Leading:** they lead targets half as much as Halo's tags say.
  * **Spread:** the error cone is widened 1.75× (`hce_enemyspread`). Automatic weapons (plasma rifle, assault rifle, needler, Spiker, carbines) get at least 2.5° and bloom by 12% a round up to double over a burst.
  * **Measured:** against a standing target at about 500 units, hit rates fell from 72% to about 20–40% for a plasma-rifle Elite and from 61% to about 35–45% for a plasma-rifle Jackal. Needles still home, so the needler suffers least.
  * Marines keep their tag accuracy.
* **Movement:**
  * Units steer with wall probes: each heading is scored for room ahead, and they drift away from walls beside them. Backing straight off is a last resort, and they only give ground when you're inside half their minimum range, diagonally and only where there's room behind.
  * If a strafe breaks line of sight it reverses. After 0.7 s without sight they move to find a firing position.
  * A stuck check (barely moved in half a second) sends them toward open space.
  * **No stacking:** an enemy knocked or blasted onto another one's head (Doom lets monsters stand on each other) slides off to the roomier side within a few tics instead of riding it or getting wedged under a low ceiling. Crates and barrels can still be stood on.
  * Shield-down cover is a sidestep toward the roomier side, not a backpedal.
  * After a fight they stay alert for 10 s with 360° awareness, so they notice you even if you're behind them.
* **Dodging fire:** enemies watch the projectiles coming at them and sidestep across a shot's path, toward the roomier side, with their evade animation (or a dive if they have none). Grenades are handled separately (see Grenade awareness).
  * The chance per incoming shot is 45% for Elites, 25% for Jackals and 15% for the rest, plus half the variant's evade chance from its tag. After a dodge they wait 2 s before the next.
  * In testing, a Major Elite sidestepped one of three rockets fired straight at it.
  * Hitscan bullets can't be dodged, same as in Halo.
* **Headshots:** a hit in the top fifth of an enemy's height is a headshot, but only once its energy shield is down (or it has none). Precision weapons kill outright: magnum or pistol, sniper rifle, battle rifle, DMR, carbine, beam rifle, binary rifle and needle rifle, plus Doom's pistol in the standalone version. Anything else does 1.5×.
  * In testing, 6 assault-rifle damage to a Grunt's head took 9 health; a pistol headshot killed it.
  * **No headshots:** Hunters, Flood, Sentinels, Engineers, the Drinol, Blind Wolves and the Thorn Beast. Shots to their heads count as ordinary hits.
  * **Brute helmets:** the first head hit knocks the helmet off, for normal damage; after that the bare head takes headshots. Honor Guard and Chieftain helmets never come off. In testing, 10 to the head did 10 with the helmet on and 15 with it off.
* **Flushing you out of cover:** an enemy carrying grenades that loses sight of you for 1–12 s may lob one at where it last saw you, if that spot is within its throwing range and the arc is clear. It rolls every 6–10 s at 60%, and nearby allies hold their own grenades for a few seconds after.
  * In testing, a Spec Ops Elite landed a plasma grenade within 20 units of the spot.
  * Regular Elites carry no grenades in Halo CE's tags, so it's Grunts, Spec Ops Elites, Brutes and Marines that flush.
* **Pump shotgun:** HaloDoom Evolved's pump shotgun (`Halo_Shotgun`, the enemies' shotguns too) shoves: each pellet pushes a living target back a little, harder up close. A kill sends the body flying a short way, 6–9 units a tic in a short arc, the same for every race (Hunters, with their front armour, and fliers stand their ground).
* **Melee:** reach is measured from body edge to body edge: 36 units for most enemies, 40 for Flood, 56 for Hunters and 64 for the energy sword. A swing only connects within 14 units of slack and a 70° arc in front. (Halo's `melee_range` is a decision radius, not arm length; used directly it let Elites swing from about 150 units away.)
* **Plasma pistol overcharge:** Jackals only. Grunts with plasma pistols never overcharge.
* **Lighter enemy plasma:** the Covenant fire HaloDoom Evolved's plasma bolts, which are made for the player's own gun: each carried a crackle of lightning, threw four lightning arcs every four tics (each a chain of 20–70 small actors), four more on impact, and a smoke puff every tic. When a squad noticed you and opened fire together, that put over two thousand effect actors in the level within seconds, which was the hitch. The enemies' bolts keep the look (glowing cores, colour, particles, smoke) without the attached crackle, with one coarser arc in flight and two on impact (only within 1200 units of a player), and smoke every third tic. In a test with 30 Covenant opening fire at once, the effect actors peaked around 350 instead of about 2,400.
* **Grenades:** ballistic throws; Covenant throw plasma grenades and humans throw frags. They're paced so they stay occasional:
  * At most one decision every 6–10 s, at 45% of Halo's throw chance.
  * A 12–20 s cooldown after a throw.
  * Nothing in the first 3–6 s after spotting you.
  * After anyone throws, nearby allies (within 640 units) hold theirs for 5 s.
  * The `hce_grenadefreq` CVar scales all of it (2 = twice as often, 0.5 = half).
  * The old pacing rolled every 2–3 s at 100% for Grunts.
* **Kamikaze Grunts (Halo 3):** Grunts carrying plasma grenades sometimes make a suicide run:
  * They play the jumping alert animation as the pull-out, with two live plasma grenades in their hands, and scream a kamikaze line.
  * The Crazy Grunt voice screams Halo CE's and Halo 2's grenade death screams on the run (the same voice actor in both games: Halo CE's grenade-at-his-feet screams and Halo 2's panic screams), and the same screams when it's stuck by a plasma grenade.
  * They sprint at you in the panic run. On contact, or after 6 s, both grenades go off; that's lethal at point-blank.
  * Kill one mid-run and it pitches forward out of the sprint (a falling-forward death, the body sliding on), and the two grenades fly out of its hands: they keep the run's momentum, scatter to either side and pop up, stick wherever they land (or to whoever they hit), and go off on their normal 2 s fuse. In testing they landed 120–160 units ahead of where it fell.
  * Chance per second in combat: 0.4% Minor, 0.8% Major, 1.2% Spec-Ops, tripled below half health, and a 30% roll when their Elite leader dies.
  * One run at a time per squad, once per Grunt, and panic or berserk never interrupts it.
* **Low ceilings:** before every throw, the grenade's arc is simulated against the ceiling and ledge heights along its path. If the natural lob would hit, the thrower tries flatter, harder throws; if none clear, it holds the grenade and checks again a second later. The White Hunter's plasma-caster volleys follow the same rule. In a test room with a 96-unit ceiling, 21 of 30 grenades used to stick to the roof; now none do, and enemies still throw flatter grenades there.
* **Friendly fire:** before a burst, and every third shot of one, a shooter checks its line of fire for friends (its own side; for Marines, you and the other Marines). If one is in the way, it holds fire and steps sideways to whichever side is open, then fires once the line is clear. Explosive weapons (rockets, the Hydra, grenade launchers, the sticky detonator, fuel rods, Plasma Casters, charged plasma) also hold while a friend stands within the blast of where the shot would land, or while the target is within 150 units (its own blast would reach it). Grenades aren't thrown, and cover isn't flushed, at a spot with a friend within 200 units of it.
* **Crouching:** a crouching body is a smaller target: its hitbox drops to about 60% of its standing height, and grows back when it stands up, if there is headroom.
* **Grenade awareness:** every enemy that notices a live grenade near it (about 200 units, judged by where a thrown one is about to land) gets clear: a dive or evade animation in the escape direction, or a sprint for the ones without dive animations (Flood, Engineers, Blind Wolves, Thorn Beasts, Sentinels and Drones).
  * **Noticing it** depends on how deep inside its vision cone the grenade is: each look (every 4 tics) the chance runs from about 6% at the edge of the cone to almost 100% dead ahead. Behind it, it won't see one at all, unless the grenade lands right at its feet.
  * Whoever spots it shouts its grenade line, and squadmates within 480 units who hear the shout notice that grenade much sooner.
  * The escape heading turns away from walls. Grunts, Jackals, Elites, Hunters, Brutes, Marines and Slug Men use their dive or evade animations, and a berserk Elite or Brute mostly ignores the grenade.
  * **Distance:** a dive throws the body at 1.75 times its run speed for most of the animation, then it sprints on in the same direction for about 0.4 seconds. Those without dive animations sprint at 1.25 times their run speed for about a second.
  * **Cooldown:** one dodge every 3 seconds; a grenade seen sooner than that after the last dodge isn't dodged (they still shout the warning).
  * `hce_grenadedodge 0` turns it off.
* **Dropping off ledges:** Marines and the Covenant step off a drop too deep to walk down when where they're going is below: their target, the spot they last saw it, or (for Marines) you. The drop must be safe, up to two and a half times their own height, and not into a damaging floor. They fall in the airborne animation and land in the landing one.
* **Jumping:** a ledge or a low obstacle (crate, barrel) in the way that is too tall to step onto is jumped onto or over, in the airborne animation, with the landing animation on touchdown. Jump height is about three quarters of the body (24–56 units: a Grunt manages about 30, an Elite or Brute 50+), Hunters only hop 32, and flyers never jump. A ledge that is jumpable doesn't count as a wall when they pick a heading, so they head for it; enemies hunting you by Doom pathfinding also jump up toward you when you are on higher ground. `hce_jumping 0` turns it off.
* **Sniper perches:** Jackal snipers and marksmen change perches after a few shots, or when hurt: another spot with a view of their target, higher ground preferred, well away from the last, and they move there without firing.
* **Rallying:** when an Elite or Brute leader dies, the nearest other leader takes on its Grunts and Jackals (*join me!*), cutting their panic short.
* **Sword lunge:** sword Elites lunge as in Halo 2: from 120–360 units, a fast dash straight at the target into a swing.
* **Shield impacts:** every shot that strikes an energy shield (Elites and the Chieftain's overshield, and the Jackals' arm shields) flashes where it hit: a burst of light and sparks off the shield's surface, thrown back toward the shooter. They come in the shield's colour (Elite blue, Brute gold, the Jackal shield's rank colour), and turn red when the shield is nearly down.
* **Shield flares:** when an Elite's or Brute's energy shield takes a hit, a bright copy of its body lights up in the shield's colour (blue for Elites, gold for Brutes) and fades in a fraction of a second. It flashes brighter when the shield pops and glows softly while recharging. The flare is a second copy of the model, a touch larger, drawn additively with a noise texture, and it plays the same animation as the body.
* **Active camo shimmer:** stealth Elites' skins run through a GLSL shader (`shaders/hce_camo.fp`) that adds moving bands of refraction-like distortion and a faint sparkle, so a cloaked Elite shimmers instead of being a flat translucent ghost.
* **Elites:** take cover when their shields drop below `shield_fraction_hide` and come back out at `emerge`. When an Elite's shield pops it reels in a **hard ping** for the animation's full length (about a second), a moment to finish it off. They evade and dive, and go **berserk** (roar, charge, melee) on heavy damage below 30% vitality or at close range. Grunts and Jackals **panic** when their Elite leader dies.
* **Jackals:** the energy shield is its own entity (`HCE_JackalShield`) riding the `frame shield` node of the Jackal's arm every tic, so it sits wherever the animation holds the shield. Shots that hit it don't reach the Jackal; shots that get around it do.
  * **Bullets:** shotgun pellets and Spiker spikes spark off it without harm.
  * **Needles and fire:** do a little.
  * **Explosions:** full damage.
  * **Melee:** 2.5×, and the Jackal staggers.
  * **Plasma:** 4×, and an overcharged plasma bolt 10×.
  * **Drained, it breaks for good:** the field bursts into a flash and a spray of shards in its colour, the shield is gone from the model, and the Jackal reels in a hard ping and often (60%) panics. It fights on without it; a broken shield never comes back. When the Jackal dies the shield goes out with it, and a severed shield arm flies off without its field.
  * **Animated:** the field is drawn by a shader (`shaders/hce_shield.fp`, fullbright): it drifts and folds over itself, a hex lattice shows through with its cells flickering, bands of light sweep across it, and it pulses.
  * The shield's colour shows the rank:

  | Rank | Shield | Weapon | Body / shield HP | Class |
  |---|---|---|---|---|
  | Minor | Blue | Plasma pistol (with overcharge) | 60 / 200 | `HCE_JackalMinorPlasmaPistol` (30247) |
  | Major | Pink | Needler | 75 / 250 | `HCE_JackalMajorNeedler` (30279) |
  | Ultra (Halo 2 Jackal) | Orange | Plasma rifle | 100 / 350 | `HCE_JackalUltraPlasmaRifle` (30248) |
  | Zealot (Halo 2 Jackal) | Gold | Spiker | 120 / 450 | `HCE_JackalZealotSpiker` (30433) |
  | Sniper (Halo 2 Jackal) | none | Halo 2 beam rifle | 60 / – | `HCE_JackalSniperBeamRifle` (30434) |
  | Marksman (Halo 2 Jackal) | none | Plasma carbine | 70 / – | `HCE_JackalMarksmanPlasmaCarbine` (30436) |
  | Marksman (Halo 2 Jackal) | none | Pulse carbine | 70 / – | `HCE_JackalMarksmanPulseCarbine` (30437) |

  Halo CE only has Minor and Major plasma-pistol Jackals. The plasma-rifle Jackal (rate of fire and bursts from the Minor plasma-rifle Elite) is the **Ultra**, and the needler Jackal (the Major Grunt's needler timing) the **Major**. Each keeps its weapon, shield colour and DoomEdNum: 30248 is the plasma-rifle Ultra, 30279 the needler Major. The rank's name and stats moved with the swap; older builds had them the other way round, as `HCE_JackalMajorPlasmaRifle` and `HCE_JackalUltraNeedler`. `HCE_RandomJackalMajor` spawns either.
* **Halo 2 Jackals (Digsite add-on):** the Ultra, the Zealot, the Sniper and the Marksmen wear Halo 2's Jackal, ripped from MCC's `08a_deltacliffs.map`: its 40-bone model and textures, its arm shield, and its own animations (one-handed pistol stance for the plasma rifle and Spiker, two-handed rifle stance for the beam rifle, crouches, dives, evades, surprise, flinches and deaths). Halo 2's Jackal holds its shield on the right forearm and its gun in the left hand; the shield entity, the gun-hand hit and the shield's switch-off follow those bones (`HCE_ShieldBone`, `HCE_GunHandBone`, `HCE_ShieldSurface`).
  * **Ultra:** the CE pack's plasma-rifle Ultra moved onto the Halo 2 body; same class, stats and DoomEdNum. Its armour takes Halo 2's Major Jackal colours.
  * **Zealot (new):** a tougher Ultra (120 body, 450 shield) with the **Spiker**, a gold shield and gold armour, the colour Halo gives its zealots.
  * **Sniper (new):** Halo 2's Sniper Jackal: no shield (60 body), keeps its distance (combat range 640–2240), and carries **Halo 2's beam rifle**, which fires like HaloDoom's (see Beam rifle below).
  * **Marksman (new):** Halo 3's carbine Jackal on the Halo 2 body: no shield (70 body), Halo 2's Major armour colours, the rifle stance, and the Elites' **plasma carbine** (`HCE_JackalMarksmanPlasmaCarbine`) or the homing **pulse carbine** (`HCE_JackalMarksmanPulseCarbine`), fired like the carbine Elites'. It hangs back at 480–1760 units, a little closer than the Sniper.
  * `HCE_RandomH2Jackal` (30435) picks one of the five.
* **Jackal shield pop:** every Jackal's shield (CE and Halo 2) now pops with Halo 2's Jackal shield-break sound (three variations from `jackal_shield_death`).
* **Beam rifle (Halo 2):** the Sniper Jackal and the beam-rifle Spec Ops Elite carry Halo 2's beam rifle model and fire it like HaloDoom's beam rifle: a held purple beam whose damage climbs while it stays on a target (from about 1 to 4 a tic, three times as much after half a second on target), in bursts of about a second with a 2.5–3.5 s cool-down. **Every burst is telegraphed:** for about 0.9 s before the beam fires, a purple **sniper glint** flashes at the rifle and a thin, harmless **targeting laser** runs to where it's aiming, so you see the shot coming and can break line of sight. The beam and the targeting laser are drawn with **HDE's own beam rifle laser**: the purple beam with its pink core, which fades and spreads when it stops. The Slug Man's particle beam rifle shows the same glint during its one-second aiming laser, and its shot is the same HDE laser, flashing out. It uses HDE's laser sounds and the same slow-tracking aim as every other enemy weapon, so strafing drags the beam off you. It drops HDE's beam rifle. In testing, a Sniper Jackal held on a standing target for up to about 120 damage in a second of beam.
* **Jackal bodies:** no energy shield of their own; the arm shield is all they have. Shots from a Jackal's side or back that clip the shield's hitbox (held out to the side) go on into the Jackal.
* **Jackal gun hand:** a shot whose path passes the gun hand poking out past the shield gets through: the hit goes into the Jackal and it reels in a hard ping. Tested by shooting a Jackal's hand with a 5-damage bullet: it took the damage and played its h-ping.
* **Hunters:** front armour reduces damage by 92% within 70°, so flank them. Their weak spots are where Halo's are:
  * **Back:** the exposed orange flesh takes **3×** from behind (more than 110° off their facing). In testing, 20 to the back did 60.
  * **Belly:** the gap at the stomach takes 1.5× even from the front, within 30° of dead ahead and at 30–55% of their height.
  * **Neck:** the neck takes 2× from the side, above 72% of their height. They fire the fuel-rod cannon at range and melee up close, and come as bonded pairs.
  * **Bond rage:** each Hunter knows its brother (the one it spawned with, or the nearest unpaired Hunter once they meet). When one dies, the other, wherever it is, roars and rages for the rest of its life: it goes berserk (charges, never takes cover or backs off), moves a third faster, pauses half as long between cannon shots (60%), smashes half as hard again with its shield arm, and goes after whoever killed its brother.
* **Hunter colours:**

  | Hunter | Weapon | Class (DoomEdNum) |
  |---|---|---|
  | Blue (CE) | fuel-rod cannon | `HCE_Hunter` (30245), `HCE_HunterMajor` (30246) |
  | White | lobs plasma caster grenades on a ballistic arc (1–2 per volley); 30% of volleys are a charged 3-grenade cluster after an audible charge-up | `HCE_HunterWhite` (30280) |
  | Red | flamethrower stream from the arm cannon, short range (it closes in) | `HCE_HunterRed` (30281) |

  White and Red are new. They're the regular Hunter with the arm cannon's weapon swapped for HDE's plasma caster (the `PlasmaCasterProj` / `PlasmaCasterClusterProj` grenades) or the flamethrower, and the blue armour recoloured. Both come in bonded pairs, and `HCE_RandomHunter` includes them. The Red Hunter is lethal up close: in testing it burned a player from full to 1 HP in about 4 seconds.
* **Stuck Elites go berserk:** an Elite (or anything else that berserks: Flood combat forms, Hunters) stuck by a plasma grenade roars and charges whoever threw it, trying to take them down in the blast. If the thrower is unknown, it charges the nearest enemy in sight. Grunts and Jackals panic instead.
* **Halo CE armour permutations:** Halo CE's models carry alternate armour that the Xbox campaign rolls at random; here each rank gets one. The **Spec Ops Elites** (and the stealth Elites, which share their model) wear the regular Elite's **curved, crescent-masked helmet** with the blunt armoured arms and double-pointed armoured legs, in dark Spec Ops colours. The **Spec Ops Grunts** carry the **shellback** (shrimp-back) tank. The **Major Jackals** wear the **armoured helmet**, and the Halo 2 Jackals wear it too: the helmet is cut out of Halo CE's armoured head and fitted to Halo 2's head bone, tinted with each rank's armour colour.
* **Energy sword:** the blade has its own shader: plasma streaks flowing up it, a white-hot core along its length, shimmering edges and sparks, and the whole blade breathing, drawn at full brightness (every sword Elite, the Ultra Zealot and the cloaked Stealth Majors' visible blades).
* **Stealth Elites:** active camo flickers when shot or firing. A cloaked sword Elite's **energy sword blade stays visible**, glowing at full strength (a blade-only copy of the model plays the Elite's animations), as in Halo. The camo is their protection: they have **no energy shield** and a fragile body (45% of the tag's vitality, 45 health before `hce_nerf_health`).
* **Grunt backs:** each Grunt (Spec Ops included) wears one of Halo CE's two backs, rolled when it spawns: the regular pointed methane tank or the rounded **shellback**, in its own textures from Halo CE (the second image of each Grunt bitmap, which Halo picks by permutation). Shot off, each back comes away as its own piece with its own stump.
* **Armour shine:** Halo CE draws Elite and Grunt armour with a cube-map reflection under its specular mask: the swirling liquid-metal sheen. Doom has no cube maps, so it is baked into the skins. The blue Minor and red Major Elites wear hand-painted skins with that chrome sheen painted in. The Spec Ops Elites, black in Halo CE, wear the same painted skins turned a vibrant dark purple (sheen and highlights included) so they stand apart from the dark undersuit. Every other Elite gets Halo's own cube maps baked in (blue, magenta, gold and silver by rank), reflected off each armour plate's shape, only where Halo's specular mask marks metal. The Grunts' painted armour wears the Elites' cube maps the same way (gold on the orange Minors, red on the Majors, the armour's hue held to its rank colour), so it reads like the Elites'. Their bare metal, masks and hoses keep Halo CE's own dull grey reflection. The Spec Ops Grunts are repainted in the Spec Ops Elites' violet, with smooth shading and soft highlights.
* **Covenant weapon shine:** the Covenant guns the enemies carry get the same baked reflection on their coloured metal. The plasma pistol, plasma rifle and needler use Halo CE's own cube map and reflection mask for each gun. The fuel rod, sword hilt, Halo 2 and Digsite weapons and the Plasma Caster get a gentler one from the plasma rifle's cube map on their painted parts. Lights, glows and grey metal are left as they are.
* **Elite Commander (gold):** the gold Elites wear the regular Elite body, the one the Minors and Majors wear, instead of the Elite Special's: its colour mask leaves the hands their dark gauntlet colour, where the Elite Special's turned the hands gold too. The armour is baked as a vibrant gold that keeps the plates' shading, with highlights on the raised edges. The Commanders keep their own stats, weapons (the regular Elite model now carries the energy sword) and DoomEdNums.
* **More Grunt ranks (new):**
  * **Ultra** (Halo 2's `grunt_ultra`): white armour, a third more health than a Major (100 with the needler, 80 with the plasma pistol); it fights like a Major. `HCE_GruntUltraNeedler` (30319), `HCE_GruntUltraPlasmaPistol` (30320).
  * **Heavy** (Halo 2's `grunt_heavy`, in Halo 3's green): the fuel rod on the Spec Ops body; it fights like the Spec Ops fuel-rod Grunt. `HCE_GruntHeavyFuelRod` (30318).
  * They get the same baked armour shine as the other Grunts, and are in the `HCE_RandomGrunt` / `HCE_RandomGruntSpecOps` spawners; Doom's monsters aren't replaced by them.
* **Elite Heavy (new, green):** a rank between the Major and the Commander, in a deep green (the blue Minor's painted armour turned green, its shading and shine kept): 125 health and a 200-point shield, the Major's combat behaviour, and the heavier guns: the fuel rod in Halo 2's fuel-rod stance (`HCE_EliteHeavyFuelRod`, 30322), the plasma rifle (`HCE_EliteHeavyPlasmaRifle`, 30324) and the needler (`HCE_EliteHeavyNeedler`, 30323). In the random Elite pool, and among the Hell Knights' replacements on the harder skill levels.
* **Honor Guard Elites (new):** the High Council's guard in Halo 2's honour armour, worn over the Halo CE Elite (`extract_h2_elite_kit.py`: Halo 2's Elite and Halo CE's are the same skeleton, so its pieces are carried bone by bone onto the CE Elite and play every CE animation). The tall twin-crested ceremonial helmet over Halo 2's Elite head, and the honour plates on the shoulders, arms and thighs, blue with their glowing red markings; the CE Elite's own head and helmet are cut away underneath, so nothing clashes. The Commander's build (they guard the Prophets) in a crimson harness, with the **plasma rifle** (`HCE_EliteHonorGuardPlasmaRifle`, 30345), the **energy sword** (`HCE_EliteHonorGuardEnergySword`, 30344, charging and berserk like the sword Elites) or the **plasma carbine** (`HCE_EliteHonorGuardPlasmaCarbine`, 30457, Digsite add-on): the Honor Guards' guns in Halo's fiction. A severed head takes the helmet with it, a severed arm its plates.
* **Ranger Elites (new):** Halo 2's EVA Elites from Regret's towers, with a **jump pack**. Halo 2's sealed Ranger helmet, with its gold eye lenses (reflecting a cube map per pixel like the ODST visors, the glass bowed so the reflection sweeps across it), over the CE Elite with its own head cut away, and Halo 2's jump pack on its back (placed where Halo 2's Ranger carries it), in pale EVA steel; the helmet is baked in the same material as the body (the same steel and the same, gentler, armour reflection). A Minor's build (Halo 2's `elite_ranger` char: 30 body, 70 shield), with the **plasma rifle** (`HCE_EliteRangerPlasmaRifle`, 30347), the **needler** (`HCE_EliteRangerNeedler`, 30346) or the **plasma carbine** (`HCE_EliteRangerPlasmaCarbine`, 30458, Digsite add-on).
  * **The jump pack:** now and then in a fight, with its enemy in sight, a Ranger fires the pack and lifts onto higher ground near by (a ledge, a crate, a balcony with room to stand) or, with none, hops to a fresh spot at fighting range. It climbs on a jet of blue exhaust and drifts down slowly on the pack, firing as it goes; spots are open floor (never a damaging one) with headroom, no wall in the way at the height of the hop and not too close to the enemy. HaloDoom Evolved's jetpack sounds where HDE is loaded.
* **Fuel-rod Elite (new, `HCE_EliteMajorFuelRod`, 30282):** a Major Elite with the fuel rod gun, in **Halo 2's fuel-rod stance**. Halo CE's and Halo 2's Elites are the same 3ds Max biped: every CE bone has a Halo 2 twin with the same parent and the same offset in its parent's frame, so Halo 2's animations play on the CE Elite as they are (`h2_elite_anims.py`). It gets Halo 2's fuel-rod idle, moves, turns, dives, evades, grenade throw, berserk, melee and the firing overlay. Its firing data is the Spec Ops Grunt's fuel rod; it drops HDE's fuel rod.
* **Beam-rifle Spec Ops Elite (new, `HCE_EliteSpecopsBeamRifle`, 30283):** the Spec Ops plasma-rifle Elite with Halo 2's beam rifle, in Halo 2's own Elite rifle stance (the same rig match), fighting from further back (combat range 480–1760).
* **Plasma-Caster Spec Ops Elite (new, `HCE_EliteSpecopsPlasmaCaster`, 30317):** a Spec Ops Elite (in the purple Spec Ops armour) carrying HaloDoom Evolved's Plasma Caster as a Halo CE-style gun (the same model as the Brute Captain's), in the Elite rifle stance. It lobs Plasma Caster shots from mid range (4–14 m), sometimes a charged three-shot cluster, and drops HDE's Plasma Caster.
* **Flood:**
  * Infection forms swarm, leap and nibble, then crawl to dead Marines and Elites. The feed animation raises the corpse as a Flood combat form.
  * Carriers waddle up and burst into 5–9 infection forms. Chain reactions happen.
  * Combat forms leap and fire whatever weapon they carry. Dead combat forms can be revived.
* **Sentinels:** hover at Halo's flying height and fire a hitscan beam.
* **Deaths:** directional (front/back/left/right) soft and hard death animations, airborne deaths, and Halo's flinch ("ping") animations by hit direction.
* **Flinches:** a heavy hit plays a **hard ping** (h-ping) every time: a quarter of its health in one hit, a blast, or a hard melee. It cuts short a soft flinch, a landing or a taunt, though not a swing, throw, dive or an earlier hard ping. Lighter hits have a chance of a soft ping (s-ping).
  * Hits a shield soaks up cause no flinch, as in Halo, but popping an Elite's shield does (see Elites).
  * Hunters, the Drinol, Sentinels and the Thorn Beast have no hard-ping animations, so they use their soft one.
  * An audit hit every class for 30% of its health from behind: every one with a hard ping played it. Marines ignore your shots (friendly fire), and infection forms die first.
* **Thrown by explosions:** a kill from a grenade, rocket, fuel rod or any other explosion (anything dealing damage through `A_Explode`), from a Hunter's punch, or from a melee hit with the `Kick` damage type (HDE's player melee) flings the body away from the blast. Kicks throw at about 40% of a grenade's strength: in testing, a kicked Grunt flew about 30 units up versus 100 for a grenade. It flies in Halo's `airborne-dead` pose, facing the blast so it goes backwards, and plays `landing-dead` when it hits the ground.
  * **Physics:** the flight is real engine physics: gravity, wall collisions and ground friction, with most of the slide scrubbed off on impact.
  * **Strength:** the throw scales with the damage dealt and the body's mass, so lighter enemies fly further. In testing, a frag grenade threw a Grunt about 100 units up and over 150 units back. A Jackal went about 80 up, and an Elite about 60.
  * **Exceptions:** Hunters are too heavy to throw and fall in place. Infection forms and Carriers burst instead, and blasts too weak to throw a body just drop it.
  * **Mid-air deaths:** anything that dies in mid-air (a leaping Flood form, a Sentinel) also plays `landing-dead` when it lands.

## Getting around

* **Teleporters:** when you take a teleporter, the Marines following you who were with you come through after you a moment later, one by one, with the teleport fog, and take up places round where you came out. A Marine left far behind (out of sight and 1800 units or more away for 20 seconds) catches up the same way. Marines told to hold stay put.
* **Round corners:** a Marine that can't walk straight to its place in the formation follows your trail instead: the newest point on the path you walked that it can reach.
* **Doors and lifts:** Marines and the Covenant use doors and lifts in their way, the same way the squad's *press that button* order works. A door or lift worked by using it is used, and they wait for it; on a moving lift they stand still and ride it. A closed door worked from a switch elsewhere sends them to press the switch, then back through. Locked doors stay locked. The Flood and the Sentinels don't use them.

## Searching

When the Covenant lose sight of you for a few seconds, they search (`hce_search`, on by default) instead of walking straight to where they last saw you:

* They go to where they last saw you, then follow the way you went for a few seconds (your trail), then check the spots round there they can't see into, looking about at each. A squad fans out to different spots.
* They call it (*search start*, *cover me while I check it out*), shout when they find you, and after 20–30 seconds give up (*all clear*, *lost them*) and go back to their post.
* Beyond `hce_maxpursuers`, the rest of a team keep watch where they are.
* **Explosions:** an enemy with nothing to fight that hears a grenade, rocket or barrel go off (within 1.25× `hce_hearing`) walks over warily to look, then goes back. A Marine following you just turns to watch that way.
* **Flashlights:** an idle enemy that HaloDoom Evolved's flashlight beam falls on, and that can see you, notices you. (The standalone packs' Doom player has no flashlight.)

## Shooting the dead

Now and then (`hce_corpseshoot`, 0.25 by default; the Covenant a little more often, Marines a little less), a Marine or a Covenant soldier that has just dropped its enemy puts a few more rounds into the body, as Halo's AI does: a beat's pause, then a short burst at the body where it lies, which can be enough to gib it.

* **Guns:** only ones that don't blow up: no rockets, grenades, fuel rods, flame, Plasma Casters or stickies.
* **When:** only with the body in sight and no other enemy about; any new enemy ends it at once. It counts against the magazine like any other shooting.

## Combat callouts

Halo 2's own combat dialogue, for the Marines, Elites, Grunts, Jackals and Brutes (voices without a line borrow the nearest one they have):

| Callout | When |
|---|---|
| Cover me / I'm exposed | taking cover / flanked in it |
| Search start, cover me while I check it out, found you, all clear, lost them, keep watch | searching (above) |
| Join me | an Elite or Brute rallying a fallen leader's squad |
| Charge | a lance's breakthrough, a sword lunge |
| Fall back / advance | the Marines' break-contact drill / a fire team's rush |
| Up there / down there, sword, sniper | sighting an enemy above or below, with an energy sword, or a sniper |
| Behind us | an enemy at the squad's rear or flank |

## Footsteps

Every body that walks has footsteps: Halo 2's Marine (the Chief's, played softer: the MCC archive's Marine set doesn't decode), Elite, Grunt and Brute sets; Jackals step as Grunts (lighter), Hunters as Brutes (heavier), the Flood's combat forms as the body they were. One plays a stride of ground actually covered, walk or run, on the surface the floor's texture suggests: hard floor, metal grating, dirt, grass or shallow water (liquid floors and wading).

## Cover

Under fire, or now and then of their own accord, Marines and the Covenant fight from cover, with Halo 2's own corner-cover animations moved onto the Halo CE bodies (`cover_anims.py`). `hce_cover 0` turns it off; it's also under **Options > Halo CE AI**.

* **Corners:** Marines, Elites and Brutes look for a wall that hides them from their target with a corner beside it. They run there (shooting as they go), step in beside the corner and wait pressed to the wall, then lean out past the edge to shoot for a couple of seconds and lean back in. While they lean out they really stand clear of the corner, so their line of sight and fire clear the wall, not just the animation.
* **Low walls:** anyone with a crouch (Grunts, Jackals, Slug Men...) can use a low wall instead: it crouches behind it and stands up to shoot over it.
* **Leaving:** they leave when the spot stops hiding them (you flanked them), when you come too close, when they've lost sight of you for a few seconds, or after 10–16 seconds, then look for another spot a few seconds later.
* **Shields:** Elites and Jackals whose shields are down (Halo's shield-low cover) now hide behind real cover when there is some near, and stay hidden until their shields are back.
* **Who doesn't:** Hunters, Jackals with their arm shield up (the shield is their cover), sword and hammer wielders, berserkers, flyers, the Flood and the Sentinels.
* **Squads:** a unit tied to a squad (Covenant squads, Marines following you) only takes cover close to where its squad wants it, and not while a battle drill or lance manoeuvre is moving it.
* **Difficulty:** the harder the difficulty, the shorter they hide between peeks (Halo's burst separation).
* **How spots are found:** by sampling round the unit with line traces when it wants cover. There is no precomputed graph, so it works on any map and against a moving target. Two units never take the same spot.

## Climbing and vaulting

Halo 2's hoist and vault animations (`cover_anims.py`) are used where they fit, with jumps as before for everything else:

* **Hoist:** a ledge about as high as the body's hoist climbs is climbed, not jumped. Elites and Brutes hoist about 85–95 units, so they now get onto ledges higher than they can jump. Marines hoist about 35 units, Jackals about 40 and Grunts about 45.
* **Vault:** a low wall or a crate with floor beyond it, up to about 60% of the body's height, is vaulted in one movement.
* The body moves with the animation, and the actor is put where the body ended up when it finishes. It's under `hce_jumping`, like the jumps.

## Picking up weapons

Marines and the Covenant swap their gun for a better one they see lying nearby (HaloDoom Evolved packs only; the standalone packs have no Halo weapons to find).

* **How it looks:** it walks over, crouches down next to the weapon for a moment, stands up with it, and its old gun lies where the new one was.
* **When:** out of a fight, or with the enemy out of sight or more than 640 units off; it gives up after 6 seconds if it can't get there. Never with its gun arm shot off.
* **What it picks up:** whatever the gun the dead dropped, a weapon placed in the map, or one you dropped (Marines take guns you drop for them).
  * The **Covenant only ever use Covenant weapons**, except the Brutes (below), and only ones their body is modelled with: Elites the plasma rifle, needler and fuel rod; Spec Ops Elites the plasma rifle and needler; Grunts the plasma pistol and needler; Spec Ops and Heavy Grunts the needler and fuel rod. They only trade up (fuel rod over needler and plasma rifle, those over the plasma pistol).
  * **Brutes** are the one Covenant race that uses human guns. Besides their own (plasma rifle, assault rifle, shotgun, Spiker) they pick up the human guns a Brute would like: the MA5B and MA37, SMG, double barrel, Bulldog, GPMG, flamethrower, rocket launcher, Hydra and grenade launcher. The GPMG and the flamethrower go in Halo 2's **Brute Shot stance** (`brute_stance.py`, from `08b_deltacontrol.map`: held low across the body in both hands, with its idle, moves, turns, dives, evades, grenade throw, cheer, taunt, jumps, landings and the Brute Shot's melee and firing); the rest go in the Brute's one-handed rifle stance.
  * **Marines** can carry **every human and Covenant gun HaloDoom Evolved has** except the melee weapons (energy sword, gravity hammer) and the BFG-class ones (the Unmaker and the Stanchion; Johnson is the exception, as the Stanchion is his own gun: traded away, he takes it back); Forerunner guns aren't human or Covenant, so not those either. That's 28 guns: the whole [Marine arsenal](#the-marine-arsenal) and Halo CE's guns, plus the plasma pistol, plasma rifle, needler, fuel rod, beam rifle, Plasma Caster, carbine, Spiker, Pulse Carbine and Needle Ballista. Every Marine, Johnson and Stacker included, can pick any of them up or be traded one.
  * **The Covenant guns on a Marine:** each is the model the Covenant carry (the plasma pistol, fuel rod, needler and plasma rifle Halo CE's; the beam rifle, carbine and Spiker Halo 2's; the Plasma Caster this pack's), the Pulse Carbine is the carbine in blue, and the Needle Ballista (a 2D gun in HDE, with no model) is Halo CE's needler drawn out half as long again. Pistol-sized ones (plasma pistol, Spiker) go in Halo 2's pistol stance, the fuel rod on the shoulder, the rest in the rifle stance. The plasma rifle is held like a rifle in Halo 2's Marine rifle stance, the left hand moved under it, cupping its lower prong (`marine_plasma_grip.py`). The beam rifle fires HDE's held beam, the Pulse Carbine's bolts home on the Marine's target, and the sticky detonator's charges go off 1.5 s after they land, whoever carries them.
  * **Launchers on the shoulder:** the rocket launcher and fuel rod use Halo 2's Marine launcher stance (`marine_stances.py`, from `01b_spacestation.map`: idle, moves, turns, evades, jumps and landings, grenade throw, cheer, point, crouch, the launcher's melee and reload).
* **Weapon biases:** every gun has a base worth (power weapons highest, sidearms lowest) and a kind (close quarters, mid range, long range, heavy, sidearm). Each Marine adds his liking for some kinds, and picks up (or welcomes in a trade) whatever scores highest:

  | Marine | Liking |
  |---|---|
  | Marine | one of close quarters, mid range or long range, rolled when he spawns (+15) |
  | Armored Marine | heavy and power weapons (+15), mid range (+5) |
  | Corpsman | sidearms (+15), close quarters (+10) |
  | Sergeant Johnson | long range (+20), heavy weapons (+10) |
  | Sergeant Stacker | mid range (+20), long range (+5) |
  | Brute | heavy and power weapons (+15), close quarters (+10) |

  | Kind | Guns (base worth) |
  |---|---|
  | Heavy | Rocket launcher 45, Hydra 42, Needle Ballista 42, fuel rod 40, GPMG 38, Plasma Caster 36, grenade launcher 34, sticky detonator 30 |
  | Long range | Stanchion 50, sniper rifle 40, beam rifle 40, battle rifle 30, DMR 30, carbine 28 |
  | Mid range | Commando 26, needler 25, plasma rifle 25, Pulse Carbine 24, MA5B 22, MA37 20 |
  | Close quarters | flamethrower 34, shotgun 30, Bulldog 30, double barrel 28, SMG 20, Spiker 18 |
  | Sidearm | Magnum 12, Sidekick 10, plasma pistol 10 |

  The other Covenant have no liking: they trade up by base worth alone.
* **What changes:** the gun on the model, its stance and animations, and its firing, sounds, range, magazine or heat are those of the pack's own class that carries that gun (for the Covenant guns, a Marine profile made for each).
* Not picked up by the Covenant: the energy sword and the Plasma Caster (their classes are built around them), and any human gun except by the Brutes.

## Reloading and overheating

Halo CE's AI never runs dry, but Halo 2's reloads and lets its plasma overheat, and so does everyone here with a gun (the Flood, Hunters and Sentinels excepted). It's worked out from the weapon, so a weapon swap (Johnson's Magnum) gets its own.

* **Magazines:** a gun fires its magazine and then reloads, stopping a burst short if it runs dry. Sizes: assault rifle 60, MA37 32, battle rifle 36, Commando 20, DMR 15, SMG 60, Magnum and Sidekick 12, shotgun 12, Bulldog 6, double barrel 2, sniper rifle and Stanchion 4, rocket launcher 2, Hydra 4, grenade launcher 1, sticky detonator 3, GPMG 100, flamethrower 150 bursts' worth of fuel, needler 20, fuel rod 5, Plasma Caster 5. Out of a fight, a Marine or Covenant with a part-spent magazine tops it up.
* **Heat:** the plasma pistol and plasma rifle heat with each shot (an overcharged bolt four times over) and cool between bursts. At full heat they vent, holding fire for a moment.
* **Animations:** Halo 2's own, moved onto the Halo CE bodies like the Halo 2 stances (`reload_anims.py`): the Marines' rifle, shotgun (shell by shell), pistol and rocket reloads and their plasma vents; the Elites' needler and fuel-rod reloads and plasma vents; the Grunts' and Jackals' plasma-pistol vents and reloads. They stand still for it. Where Halo 2 has no animation (the Spec Ops Grunts' fuel rods) they just hold fire for as long as a reload takes.
* **Sounds:** HaloDoom Evolved's reload and overheat sounds for the weapon (the standalone packs carry copies).

## Fire patterns

Enemies fire in set bursts with real pauses between them; they don't hold the trigger. Halo's per-variant numbers stretch or shorten the pause (and, for automatic weapons, the burst length), but every weapon keeps its shape.

| Weapon | Burst | Spacing | Pause |
|---|---|---|---|
| Needler | **3 rounds, semi-auto cadence** | 12 tics (~3 shots/s) | 1.6–2.9 s; never shortened by rank, because needles home and supercombine |
| Plasma pistol | 2–4 taps | 7 tics | 0.8–2.5 s |
| Plasma pistol overcharge (Jackals only) | 1 charged bolt, after a 0.8 s audible charge-up | – | 1.6× normal |
| Plasma rifle | 4–7 (Commanders and Flood up to 11) | 4 tics | 0.7–2.1 s |
| Fuel rod (Spec-Ops Grunt, Hunter) | 1 | – | 2.1–4.1 s |
| Assault rifle (Marines, Flood) | 4–9 | 3 tics | 0.8–1.8 s |
| Pistol / shotgun / sniper / rocket | 2–3 / 1 / 1 / 1 | 9 tics (pistol) | 0.9–5.4 s |
| Flamethrower, Sentinel beam | 0.6–1 s stream | every tic or two | 1.0–2.3 s |

Other changes:

* **Reaction time:** enemies wait at least 0.4 s (Halo's `first_burst_delay` when longer) after spotting you before the first burst.
* **Overcharge:** the plasma pistol overcharge is rolled once per burst (20%) instead of per shot.
* **Difficulty:** `hce_burstpause` scales every pause.

## Weapon sounds

Enemy fire uses HDE's own SNDINFO sounds, the fire layer and, where HDE has one, its `/Bass` layer (the rocket launcher and needle ballista have none), so enemy guns sound like the player's.

* **Covenant:** plasma pistol, plasma rifle, needler and fuel rod (`Halo/Weapons/<Weapon>/Fire`).
* **Overcharge:** `PlasmaPistol/Charge/Start` during the wind-up, then `PlasmaPistol/Fire/Charged`.
* **Human:** `MA5B`, `Mag_MD6`, `Shotgun`, `Sniper` and `RocketLauncher`.
* **Looping weapons:** the flamethrower and Sentinel beam play start, loop and end sounds.

## Dialogue

The voice lines come from [Lewisk3/HaloDoomEnemies](https://github.com/Lewisk3/HaloDoomEnemies) (through the REVonGit/HaloDoomEnemies-Proto fork): 443 lines in 9 voices, plus 53 Crazy Grunt lines from Halo 2 and a rebuilt Loose Elite set (see below). Each Grunt picks one of three personalities (Crazy, Whiley, Whimpy) and each Elite one of two (Dogmatic, Loose). Jackals and Hunters have one voice each. The Digsite add-on's Drinol and Blind Wolf use the two new creature sets:

* **Drinol:** Grave Injury plays for medium and heavy pain, Death XTR for explosive or hard deaths (`DeathHard`), and Sonic Roar for `Berserk`, including the boss's charge.
* **Blind Wolf:** Howl doubles as alert and taunt, and Bite plays for melee.

The fork's Acid Breath lines aren't used.

**Marines:** they speak with Halo CE's and Halo 2's own combat dialogue (1,005 lines in 11 voices, `extract_marine_voices.py`).
* **Faces and kit:** every Marine rolls Halo CE's own cosmetics when it spawns: one of eleven faces and headgear on unarmoured Marines (bare-headed, boonie hats, bandanas, the cap) and seven on Armored Marines (helmets, the cap); sleeves rolled down on about a third of unarmoured Marines. Armored Marines always wear the intact vest (Halo CE's battle-damaged one is left out).
* **Elefant's Marine kit:** on top of that, each Marine rolls pieces from Elefant's expanded Halo CE Marine (`extract_marine_kit.py`), each drawn as a model attachment that moves with the Marine's skeleton. The pieces use Halo CE's own textures where they share its layouts, and the bitmaps from Elefant's kit for the rest.
  * **Headgear (Armored Marines, about one in three):** helmet shells worn over the Marine's own face in place of Halo CE's helmet (the Hellbringer among them), Elefant's helmets on the Fred and Marcus faces, balaclava helmets on the Marcus, Matt and Shiek faces, and the closed and enclosed visor helmets. The orange visor on the closed, enclosed and ODST helmets reflects a cube map per pixel (the ODSTs' visor shader, tinted by its own orange, over Halo CE's cyborg reflection cube map), brighter at grazing angles. Unarmoured Marines sometimes (about one in eight) wear Charles's balaclava or Paul's cap head instead of a Halo CE face.
  * **ODST (Armored Marines, about one in seven):** the whole ODST outfit from the kit instead of single pieces: the ODST helmet (closed, shock or open; some of the closed and shock helmets carry the pair of gas-mask filters Elefant left loose in the blend on the chin), headset, vest, leg armour, pads, gauntlets and cape.
  * **Face and head (about one in three):** headsets and boom mics, HUD eyepieces, goggles, pilot and sniper goggles, glasses, a cigar, a gas mask, a face wrap, and goggles on a strap over Halo CE's helmet. None go under an enclosed helmet.
  * **Chest (about half):** pouches, grenade pouches, a grenade belt, a chest rig, a scarf. The first-aid kit (the red cross) is the corpsmen's alone.
  * **Back (about two in five):** a radio pack, backpacks, bedrolls, an ammo pack. A rocket launcher Marine always wears the launcher tube, and a flamethrower Marine always wears the flamer tank; nobody else does.
  * **Shoulders (one in four or five):** small, medium or long pads.
  * **Gloves (unarmoured Marines, one in five):** full sleeves with gloves, gauntlets, or both, in place of the arms.
  * Sergeants Johnson and Stacker keep their own look. The Insurrectionist, stealth and damaged pieces in the kit aren't used. The heads keep Halo CE's articulated jaw, held shut in every animation: Halo CE drove it from dialogue, and its animations left it parked anywhere from shut to hanging open, so mouths gaped and snapped open and shut between animations. Instead the jaw now moves with the voice: while a Marine speaks, its mouth opens and closes irregularly in syllable-like beats (at most 10°), and it shuts when the line ends. Halo CE's skin weights hung the nose, upper lip and brow partly on the jaw, so opening it dragged the whole face; the faces are reweighted to a clean hinge (`jaw_weights.py`): the mouth line up stays with the head, and only the lower lip and chin move.
* **Sergeant Johnson:** Johnson's face (the dark-skinned one, with his full-sleeved arms) is his alone. Only `HCE_SgtJohnson` wears it (see [The Marine arsenal](#the-marine-arsenal)), and he always speaks with Johnson's voice, from Halo CE's sergeant and Halo 2's Johnson.
* **Everyone else:** a random one of the other voices. From Halo CE: Aussie, Bisenti, Fitzgerald and Mendoza (the second sergeant is Stacker's alone). From Halo 2: Aussie (merged with CE's), Cross, Perez, Timid, and the cautious and gruff sergeants. Halo 2's female Marine voices (Sassy and Tough, the two its female Marine uses) are left out, as Halo CE's Marines are all men.
* **What they say:** sightings, kill taunts, pain, deaths, burning screams, grenade calls, retreats, regrouping, a fallen comrade, berserk and melee shouts. For the squad features they also have Halo's lines for scolding the player's friendly fire, turning on the player, a Marine the player killed, acknowledging orders, forgiving, and being badly wounded (Halo 2's voices have their own acknowledgements; the Halo CE voices use their nearest lines).

**Loudness:** every voice line is levelled at build time (`louden_voices.py`).
* **Method:** its EBU R128 loudness is measured, and it is raised toward -11 LUFS with a peak limiter. Lines are only ever raised, by at most 18 dB.
* **Crazy Grunt fill-in:** Crazy was short of Whiley and Whimpy in most events and had no kamikaze lines at all, so 53 lines of its own voice were added from Halo 2's `grunt_crazy` dialogue (`08a_deltacliffs.map`), skipping any it already had (matched by waveform): 7 kamikaze (threats), 6 kill-player (gloats), 6 taunts, 8 leader-dead, 6 regroup, 4 deaths, 6 hard deaths (it had none of its own), 2 alerts, 3 grenade throws, 1 enemy-grenade warning, 2 stuck, 1 heavy pain and 1 on-fire. It now has at least as many lines as the other two personalities in every event. Halo CE has only one generic Grunt voice, a different voice from Crazy's, so none of its lines were mixed in.
* **Loose Elite voice:** the Loose set is rebuilt from Halo CE's own Elite dialogue (its taunts, kill gloats, sightings, regroup calls, berserk roars, melee shouts, grenade calls, and all of its pain, death and burning screams) plus Halo 2's Loose Elite lines played backwards. CE's Elites speak recorded English run in reverse, so the reversed Halo 2 lines sound like the same alien tongue. Each reversed line fades out over its last few hundredths of a second so it doesn't stop on a click. 229 lines, against 52 before; the Dogmatic set is unchanged. CE reuses some screams across its pain and death sounds, so the same scream can come up as either, but never twice within one event.
* **Scope:** this covers the 443 lines above and the Digsite voices (Brutes, Drones, Engineer, Slug Men, Thorn Beast) and the Marines.
* **Before:** the sets were uneven. Whimpy Grunts averaged -26 LUFS, Jackals -19.5, Elites about -16, against the Blind Wolf's -5.
* **Range:** voices also carry further, at attenuation 0.6 instead of Doom's normal 1.0.

| Event | When |
|---|---|
| Alert | Spotting an enemy |
| Taunt | Every 6–14 s in combat, and after killing a non-player |
| KillPlayer | Killing the player |
| Pain / PainMed / PainHeavy | Hit for small, medium or heavy damage (Grunt and Jackal "Agonized", Elite "Pain Xtr") |
| OnFire | Hit by fire damage |
| GrenadeThrow / EnemyGrenade | Throwing a grenade; a hostile grenade lands nearby |
| Stuck | Stuck by an HDE plasma grenade (the `Pain.PlasmaStuck` state); Grunts and Jackals also panic |
| Kamikaze | Starting a kamikaze run, and while running (all three Grunt personalities; Crazy's are its Halo 2 threats) |
| Panic, Flee, Regroup | Panic starts, while running, panic ends |
| LeaderDead | A Grunt or Jackal's Elite leader dies nearby |
| ManDown | A comrade (not a leader) dies where one of its own side can see it: the nearest who saw it calls it out (Marines: Halo CE's "friend died" lines and Halo 2's laments; Elites, Brutes: the same in their tongue). A Marine the player killed gets the squad's scolding instead. Voices without lines of their own use their LeaderDead lines |
| HeardGunfire | Gunfire heard before the shooter is seen: the player's (Doom's sound) or an enemy's or Marine's shots within 1024 units, by someone with no target who can't see the shooter. One caller per side, each at most every 8 s, and the listeners turn toward the sound. Halo CE's search calls and Halo 2's "heard foe" lines (Marines, Elites, Grunts, Jackals, Brutes); voices without them use Alert |
| Berserk, Melee | Elites and Hunters going berserk; melee swings |
| Death / DeathHard | Dying; `DeathHard` for blast or hard kills, which falls back to Death for voices without one |

Lines don't pile up:

* One line plays at a time per enemy, with a cooldown.
* When one enemy speaks, same-team allies within 512 units stay quiet for a second.
* Death, panic, berserk, stuck and grenade warnings interrupt whatever that enemy was saying.

Without the voice pk3 the sound names don't exist, so enemies are silent and nothing errors. Voices are addressed as `HCE/<Voice>/<Event>`; add your own by defining those names in any SNDINFO and listing the voice in a class's `HaloDoom_EnemyBase.HCE_Voices` property.

## Halo difficulty

Halo CE's own difficulty table, read from the game globals of its maps (the same in a10, b30 and d40), scales the AI with the skill level. `hce_difficulty` pins one (see the CVar table), and it's under **Options > Halo CE AI**.

| | Easy | Normal | Heroic | Legendary |
|---|---|---|---|---|
| Doom skill | ITYTD, HNTR | HMP | UV | NM |
| Enemy damage (shots and melee) | 0.3 | 1 | 1.4 | 1.8 |
| Enemy health and shields | 0.6 | 1 | 1.2 | 1.4 |
| Enemy shield recharge speed | 0.5 | 1 | 1.5 | 2 |
| Rate of fire | 0.8 | 1 | 1.2 | 1.5 |
| Aim error (first shots / over a burst) | 0.75 / 1.25 | 1 | 0.8 | 0.5 |
| Pause between bursts | 1.2 | 1 | 0.8 | 0.5 |
| Reaction to a new target | 1.4 | 1 | 0.6 | 0.3 |
| Tracking and leading a moving target | — | — | +0.2 | +0.4 |
| Plasma overcharges | 0.2 | 1 | 1.5 | 2 |
| Grenade chance / time between throws | 0.2 / 1.2 | 1 | 1.5 / 0.8 | 2 / 0.5 |
| Melee delay | 2× + 1.5 s | 1 | 0.8 | 0.5 |
| Infection forms' speed | up to 0.6× | 1 | up to 1.5× | up to 2× |
| Marines' health and shields | 0.8 | 1 | 1.2 | 1.4 |

* **Normal is what the pack played like before.** The difficulty multiplies the pack's own nerfs (`hce_nerf_*`), which stay what Normal plays like.
* **Ultra-Violence is now Heroic:** enemies do 1.4× and take 1.2× as much to kill. Set `hce_difficulty 1` to play UV as before.
* **Marines:** as in Halo CE, they only get their own health, shields and recharge from the difficulty; their aim and damage stay at Normal.
* The pack's skill-based rank mix (stronger ranks on harder skills) is unchanged.

## Damage scale

**The nerf (default on).** Enemies are cut to 60% health and 50% shields. Everything they shoot or throw does 40% damage (30% in the standalone packs, where the Doom player has no shield).

**Fixed: the nerf was applied twice.** Most HDE projectiles (plasma bolts, bullets, needles, spikes) have damage falloff, and the nerf was re-applied on impact even inside the falloff range, where the shot had already been scaled when fired. Those hits did 0.16× instead of 0.4×, and the smallest (Spiker spikes) rounded down to nothing: an enemy Spiker hit for 0 almost every time. Now the nerf is applied once. Enemy fire hits harder than in earlier builds (a plasma-rifle Elite's bolts about 5 instead of 2–4, Spiker spikes 3 instead of 0); lower `hce_nerf_projectiles` if you preferred it before.

In a test squad (Elite Major, two Grunts, a Jackal) shooting at a player standing still:
* An HDE Spartan now lasts about 12 seconds instead of 2–3. Plasma bolts hit for 2–4 instead of 18–23.
* A vanilla Doom player lasts about 6 seconds.

How it's applied:
* **Plain projectiles:** the nerf is re-applied when the projectile hits. HDE recomputes projectile damage at impact, which also means the old `hce_enemydamage` never affected HDE projectiles.
* **Blasts:** grenades, rockets, fuel rods, needle supercombines and Plasma Caster shots are subclasses whose explosions are scaled.
* **Fuel-rod toxic cloud:** it pulses less often.
* **Plasma grenades:** an enemy plasma grenade stuck to the player kills outright, shields or not, as in Halo. One that lands nearby does its normal (nerfed) blast damage.

Set the three `hce_nerf_*` CVars to 1 for the original Halo numbers. They are new names, so the defaults apply even if your config already saved `hce_enemydamage`.

Halo weapon damage is used almost 1:1. HDE's own guns already use Halo-like values (Assault Rifle 10 vs HDE 6, plasma rifle 12–14 vs 12, sniper 101 vs 128), and enemy health is Halo's body vitality, with shields given through HDE's `ShieldProcessor`. Halo's Marines really are fragile (12 body + 24 shield), so expect them to die fast, as in the game. Approximations where Halo uses physics or scripted damage: Hunter melee 80, Carrier burst 40, infection-form nibble.

## Digsite add-on

More enemies from the [Digsite](https://github.com/digsite/h1) source assets, plus the Engineer (from Ruby's Rebalance), the Blind Wolf and the Thorn Beast (SOI_7's) from SPV3, Halo 2's Drones and Brutes, and Shigure's Ultra Zealot. It ships inside `HaloCE_Covenant.pk3`.

| Class | What it is |
|---|---|
| `HCE_Drinol` | Map-placeable only (DoomEdNum 30400); it no longer replaces any Doom monster. Digsite's war beast (model, 76 animations and stats from its tags). Melee charger that swats and pounces with its `charging_jump`. In Halo it stands about 160 map units tall, so it is shrunk to 62% (99 tall, radius 34) to fit Doom corridors; health 320. Uses the new Drinol sounds from the voice pack: alert, melee, grave injury, death, extreme death, and sonic roar on the boss's charge. |
| `HCE_BossCyberdemonDrinol` | **Boss: replaces every Cyberdemon** while the add-on is loaded. A bigger Drinol (78% scale, 110 tall, radius 40, health 1800) with three attacks. Its swats (~65) are slower than the small Drinol's. Its **charge** is a 22-speed stampede that steers a few degrees per tic, so you can side-step it; a hit does ~55 and bowls you over, and running into a wall staggers it. When it lands from a pounce it **slams** out a 260-unit shockwave that hurts and knocks back its enemies but spares its allies; jumping avoids it. It maps back to `Cyberdemon` (`CheckReplacee`), so boss-death map specials still fire. |
| `HCE_Brute{Minor,Major,Captain,HonorGuard,Chieftain}…` | **Halo 2's Brutes**, ripped from MCC's `08b_deltacontrol.map` (voices from `08a_deltacliffs.map`): one 48-bone model with every rank's armour, 73 animations (including Tartarus's gravity-hammer stance), real textures, both voices (bloodthirsty and cruel) and their footsteps, thumps and body falls.<br>• **Ranks and loadouts** (looks from Halo 2's model variants, health from the rank tags; all hold their own guns in the rifle stance; a human gun they pick up goes in the rifle stance or, for the GPMG and flamethrower, Halo 2's Brute Shot stance):<br>&nbsp;&nbsp;– **Minor**: 175 health, olive fur, light armour (blue Halo 3 pieces, Halo 2's own helmet and shoulder plates, light King Hit pieces, sometimes bare-headed). Carries the **CE plasma rifle** (`HCE_BruteMinorPlasmaRifle`) or the **CE assault rifle** (`HCE_BruteMinorAssaultRifle`).<br>&nbsp;&nbsp;– **Major**: 150 health, reddish fur, medium armour (red Halo 3 pieces, King Hit crested and enclosed helmets; one in five wears the Halo 3 jump-pack suit). Carries the **Spiker** (`HCE_BruteMajorSpiker`), which fires HDE's own spikes in automatic bursts and drops HDE's Spiker, or the **CE shotgun** (`HCE_BruteMajorShotgun`), 15 pellets a shot.<br>&nbsp;&nbsp;– **Captain**: 200 health, grey fur, the flag pack with Halo 2's **hologram flag** flying from it (`brute_captain_flag.py`: the captain's claw-marked pennant from the cloth tag, in a bright blood red, drawn bright and additive with a shimmer, rolling scan lines and a flicker; it moves with the body and stays on the corpse), and heavy armour (gold Halo 3 pieces, King Hit bighorn, heavy and chain-mail helmets, heavy chest plates and leg armour). Carries the CE plasma rifle, the CE shotgun or the **Plasma Caster** (`HCE_BruteCaptainPlasmaCaster`, 30453): HaloDoom Evolved's own (Halo Infinite's), reinterpreted as a low-poly Halo CE Covenant gun in flat colours (a muted dark purple housing and front pod, a dark gunmetal receiver, grip, stock and drum, a silver cone in the pod, cyan lights and a red Banished glyph), lobbing HDE's Plasma Caster shots with a charged three-shot cluster, and dropping HDE's Plasma Caster.<br>&nbsp;&nbsp;– **Honor Guard**: 150 health (Halo 2's Honor Guard inherits the Major's stats), the red ceremonial armour. Carries the CE plasma rifle or the CE assault rifle.<br>&nbsp;&nbsp;– **Stalker** (new, Halo 3's): a Major in **active camo** with the **Spiker** (`HCE_BruteStalkerSpiker`, 30456), cloaked like the Stealth Elites (it flickers into view when it fires or is hit) and wearing no armour kit, 150 health.<br>&nbsp;&nbsp;Each gun is the real model in the Brute's hand: the CE weapons and the Spiker (a community CE port of Halo 3's). Each drops its HDE pickup.<br>• **Brute Chieftain** (`HCE_BruteChieftainGravityHammer`), a custom rank:<br>&nbsp;&nbsp;– **Look:** half of them wear Tartarus's crested white mohawk and helmet, his grey fur and gold armour, and the elite-skull trophy pauldron. The rest wear one of two kit sets: the Halo 3 Chieftain suit (bronze) or the orange-trimmed King Hit chieftain helmet, leg and bracer set.<br>&nbsp;&nbsp;– **Weapon and animations:** Halo 2's gravity hammer, held two-handed with Tartarus's own hammer animations (idles, moves, three swings, two side smashes, leap, berserk hammer run and swings).<br>&nbsp;&nbsp;– **Stats:** 350 health and a 150-point shield (Tartarus's 1000-point overshield, cut down so it can be broken). It is melee only, with no grenades.<br>&nbsp;&nbsp;– **Attacks:** it leaps at targets 150–400 units away at Tartarus's 50% leap chance. Every hammer swing (about 70) and every leap landing sets off a **gravity shockwave**: HDE's hammer blast effect, 10–35 damage within 150 units, knocking things back and sparing other Covenant. It keeps the hammer when berserk and drops HDE's gravity hammer when killed.<br>• **Combat:** strafing, dives and evades, plasma grenades (10% a second, 3–20 unit range, 6 s apart, carrying 1–2, all from the tag), heavy melee (about 35), cheer, taunt and point animations.<br>• **Berserk:** when badly hurt, or when its pack is wiped out (the last Brute nearby always goes, others 35% of the time), it roars and thumps its chest, **throws its gun away** (the pickup lands nearby), then charges on all fours with five swings and two tackles.<br>• **Armour kit:** every Minor, Major and Captain rolls its own armour when it spawns, one piece (or nothing) per slot: helmet, chest, shoulders, arms, legs and waist. The pieces come from the h2_brute armour set: the King Hit pieces (four material tiers), Halo 3-style pieces tinted per rank, and Halo 2's own helmet, shoulder plates and bandolier. 48 pieces in all, each drawn as a model attachment that moves with the Brute's bones.<br>• **Helmets:** a headshot knocks a Minor's, Major's or Captain's helmet off, whichever helmet it wears, and it bounces away as debris. A Brute that spawned bare-headed can be headshot from the first hit. Honor Guard and Chieftain helmets stay on.<br>Scaled to 115%, so a Brute towers a head and more over an Elite (its rifle idle is 0.90 world units at full size against the Elite's 0.80), and moves a little faster to match its stride; collision 76 tall, radius 30, so they still fit Doom doors. DoomEdNums 30422–30430, `HCE_RandomBrute` 30431, the Plasma Caster Captain 30453. |
| `HCE_DronePlasmaPistol` | **Halo 2's Drone** (Yanme'e), ripped from MCC's `01b_spacestation.map` (Cairo Station): model, 32-bone skeleton, 36 animations (flight idle and four-way flight, wall perching, take-off/landing, fire, flinches, falling deaths) its real textures (from MCC's `textures.dat`, with the Drone shader's look baked in: the bump map's relief, the olive-green shell and its glossy olive-gold sheen, see-through wings) and 219 sounds: 149 dialogue lines from `sounds_en.dat`, plus its wing buzz, wing whooshes, wall-cling, claw and body-fall effects from `sounds_neutral.dat` (Halo 2 MCC stores them as raw Opus; the tools wrap them as Ogg). It holds a one-handed Covenant gun in its claw (see below), has 30 health and no shield (from its Halo 2 character tag), and is 48 tall with radius 22. Behaviour:<br>• **Darting flight:** swarm-style zig-zags above its target at changing heights, firing plasma pistol bursts.<br>• **Dodges:** when hit there's a 50% chance it darts sideways, at most every 4 s (its tag's evasion values).<br>• **Wall perching:** it flies to a nearby wall and clings with its back to it, firing from there (3–6 s in combat, 8–20 s when idle), and leaves early if you get within 96 units.<br>• **Swarm scatter:** when a drone dies, others within 400 units scatter in panic.<br>• **Falling death:** it falls out of the air and lands dead.<br>• **Sounds:** its wings buzz while it flies, it whooshes on dodges and darts, clicks when it grabs a wall, and thuds when it lands dead.<br>**Weapons:** the plasma pistol (`HCE_DronePlasmaPistol`, 30420), the **needler** (`HCE_DroneNeedler`, 30438), the CE **plasma rifle** (`HCE_DronePlasmaRifle`, 30439) and the **Spiker** (`HCE_DroneSpiker`, 30440), each dropping its HDE pickup. Cacodemons and Lost Souls become a mix of all four, mostly pistols and needlers; `HCE_RandomDrone` (30421) picks any. The antennae are cut out of their card by the shader's alpha, as Halo 2 draws them. |
| `HCE_EliteUltraZealotEnergySword` | **Ultra Zealot** (new), Shigure's Zealot Elite on the Halo CE Elite (`extract_ultra_zealot.py`): the crested Zealot helmet and ornament, the Zealot torso and Reach-style arm plates, and a **diamond energy arm shield** on its left forearm, with Halo CE's energy sword in its right hand.<br>• **Colours:** Halo Reach's Field Marshal, pushed richer: a deep crimson-maroon armour over the teal undersuit, dark gauntlets, Reach-blue inset lights (drawn bright), and a blue shield animated like the Jackals' energy shields.<br>• **Stance:** it stands and walks like every sword Elite. Taking cover, and for two seconds after a bullet or bolt hits it, it raises its guard: SPV3's shield Elite's stance (the Elite Vanguard animations by Masterz1337 and Ruby of Blue, from a30), the shield arm held out in front as it stands, walks and crouches. Its melee, dives, evades and grenade throws are the shield Elite's.<br>• **Stats:** the gold sword Elite's build made tougher (130 body, 400 shield), sword charges and berserk as the sword Elites do. Severing its left arm takes the shield with it. Drops HDE's energy sword. DoomEdNum 30455, `HCE_RandomEliteZealot` 30432. |
| `HCE_Engineer` | The Engineer from Halo CE Ruby's Rebalance, extracted from SPV3's b30 map (model, texture, 25 animations, health, dialogue). **Replaces every Pain Elemental** while the add-on is loaded; without it, Pain Elementals become Flood Carriers if the Flood pack is loaded. It carries **no weapon and never fights**: it treats nothing as an enemy, even whoever shoots it, and just drifts around, sometimes pausing in mid-air. It's a support unit rather than a combatant.<br>• **Overshields (Halo 3's Engineer ability):** every second it overshields the allies within 420 units that are fighting and in its sight, with a pink tether to each.<br>&nbsp;&nbsp;– Shielded allies are topped up 20% of their maximum a second, up to 1.5× their maximum.<br>&nbsp;&nbsp;– Unshielded allies (Grunts, Jackals, Hunters) get a small 40-point shield of their own (scaled by `hce_nerf_shields`).<br>&nbsp;&nbsp;– Out of its reach for 4 s, or when it dies, the gift goes away: overshields drop back to their maximum and given shields vanish.<br>&nbsp;&nbsp;– It drifts toward the fight, keeping 200–300 units from the ally it's shielding.<br>&nbsp;&nbsp;– In testing, a Grunt next to it got a 20-point shield and an Elite went to 60 of 50. **Kill the Engineer first.** It's still tough to pop (150 body plus a 200 recharging shield), and **when it dies it bursts and sprays 4–6 charged Plasma Caster shots** (HDE's `PlasmaCasterClusterProj`). Each one sticks to what it hits, arms for two seconds, then explodes and throws two mini-bolts, so don't kill it next to yourself. Its dialogue (idle, surprise, pain) and explosion sound come from the map. 70 tall, radius 26 (1.25× scale). Was `HCE_EngineerMajorPlasmaPistol`; same DoomEdNum, 30418. |
| `HCE_ThornBeast` | The Thorn Beast, created by SOI_7, extracted from SPV3's a30 map: a slow, tough melee brute in the Hell Knight mix. It has health 350 and heavy swipes of about 45, and walks at speed 6 (its animation stride is 4.3). Shrunk to 70% (67 tall, radius 36). It plays its own sounds from the map: idle growls as alert and taunt, melee roars, minor and major pain, death, and footsteps while it walks. |
| `HCE_Elite{Minor,Major,Specops,Commander}PulseCarbine` | The same Elite ranks with a **blue Pulse Carbine** (the CMT carbine re-tinted blue, with blue lights) that fires like HDE's Pulse Carbine: bursts of 3–5 slow, accelerating plasma bolts (8 base damage each) that home on the Elite's target. They never re-target onto allies. They drop HDE's Pulse Carbine. |
| `HCE_BlindWolf` | The Blind Wolf, created by SOI_7, extracted from SPV3's a30 map (model, texture, 18 animations, stats). It's a Pinky-style melee charger, health 90: it runs you down, bites for about 22, and pounces from up to 300 units using its leap-start, leap-airborne and leap-melee animations. It uses the new Blind Wolf sounds (alert, howl, bite, pain, death, idle) from the REVonGit/HaloDoomEnemies-Proto fork. |
| `HCE_SlugManParticleBeam` | Slug Man sniper with Digsite's own Particle Beam Rifle (the 99_mac model and texture the Slug Man's `particle beam` variant was built around; its NPC projectile flies at 350 WU/s, so it is effectively hitscan here too). Every shot is telegraphed by a one-second purple aiming laser and the beam-rifle charge sound, then one hitscan beam drawn with HDE's beam rifle laser (90 × the variant's 0.5 damage modifier = 45). Keeps 400–3200 units away and crouches to fire. |
| `HCE_SlugManPlasmaPistol` | Slug Man with a plasma pistol. |
| `HCE_SlugMan{Minor,Major,Ultra}…` | **Slug Man ranks:** more Slug Men in the pistol stance (plasma pistol, needler, plasma rifle) and the rifle stance (particle beam, Covenant carbine, blue pulse carbine), all held in the left hand.<br>• **Minor** (Digsite's grey-violet, 1× health): needler, plasma rifle, carbine.<br>• **Major** (crimson armour plates, 1.35× health, 10% tighter aim): plasma pistol, needler, plasma rifle, particle beam, carbine, pulse carbine.<br>• **Ultra** (silver-white plates, 1.8× health, 25% tighter aim): plasma rifle, particle beam, carbine.<br>**Armour:** every Slug Man (the two original ones count as Minors) has its armour repainted clean: Digsite's grainy, scuffed plates (where its specular mask marks metal; the flesh is left alone) in the rank's colour over smooth shading, the base map's light and shade with the grain filtered out, blended with the specular map's own shading, and a soft highlight on the raised parts.<br>The carbines draw HDE's green laser trail; the particle beams keep the aiming laser and glint. DoomEdNums 30441–30452 (`HCE_SlugManMajorNeedler` … `HCE_SlugManUltraPlasmaRifle`, alphabetical); `HCE_RandomSlugMan` (30409) now picks from all of them. |
| `HCE_Elite{Minor,Major,Specops,Commander}PlasmaCarbine` | Elites with **CMT's Covenant carbine** (model and textures from the CMT tags: purple carapace, glowing status lights and ammo read-out) in a real two-handed **rifle stance**. Semi-auto pairs and triples of HDE's green carbine rounds (15 base damage), each with **HDE's green carbine laser trail** from the muzzle to where it lands, with longer combat ranges than the plasma-rifle Elites. They drop HDE's Carbine. |

* **Rifle stance.** The animations come from a CE-rig Elite animation graph (`elite.model_animations`): stand/crouch/alert idles, moves and turns, dives, evades, berserk, both rifle melees, surprise, signal and land. Its uncompressed frames decode directly. CMT's carbine sits on the `right hand elite` marker, and the support hand lands where the set already places it. A two-bone IK step keeps the support hand on the fore-grip during strides. The graph has no rifle fire overlay, so firing uses a short synthetic recoil kick. Actions the graph lacks (airborne, hard landing, throw, warn, alert move) use the Elite's pistol body, with the support hand solved onto the carbine. The same graph also has cannon (fuel rod) and flamethrower sets that aren't used yet.
* **Slug Man.** Model, 187 animations (full pistol and rifle sets) and stats come from the Digsite JMS/JMA sources and tags. Slug Men are **left-handed**: their guns sit on the left hand marker, which follows Halo's usual weapon axes, so the plasma pistol points ahead from the outstretched left hand and the particle beam rifle is held across the body in every aim, move and fire animation. The voice lines are its own Digsite dialogue (Xbox ADPCM decoded to ogg): sighted, taunt, pain, death, retreat, evade and communication.
* **Spawns.** Each listed Doom monster has a chance to become a Digsite enemy (easy / normal / hard). Otherwise the main pack's mix applies. `hce_digsite_spawns` scales the chances (0 turns them off), and `hce_keepdoommonsters` is respected.

| Doom monster | Chance | Picks |
|---|---|---|
| ZombieMan | 6 / 8 / 10% | plasma-pistol Slug Man |
| ShotgunGuy, DoomImp | 5–10% | plasma-pistol Slug Man, Minor carbine Elite |
| ChaingunGuy | 15 / 20 / 25% | beam-rifle Slug Man, Minor/Major carbine Elites, Minor pulse-carbine Elite, carbine and pulse-carbine Jackal Marksmen |
| Cacodemon | **always** | Halo 2 Drone |
| LostSoul | 60 / 65 / 70% | Halo 2 Drone |
| HellKnight (after the Thorn Beast roll) | 25 / 30 / 35% | Brute Minors (plasma rifle, assault rifle) and Majors (Spiker, shotgun) |
| Revenant (rolls first) | 20 / 25 / 30% | shotgun and plasma-rifle Captains, Spiker Majors, assault-rifle Honor Guards |
| BaronOfHell | 20 / 25 / 30% | **Brute Chieftain** (still counts as a Baron, so E1M8-style boss exits work) |
| Archvile (rolls first) | 20 / 25 / 30% | Honor Guard Brutes |
| PainElemental | **always** | Engineer |
| Demon | **always** | Blind Wolf (the Pinky's replacement while this add-on is loaded; the Drinol is the Cyberdemon boss only) |
| Spectre | 25 / 30 / 35% | Blind Wolf |
| HellKnight | 10 / 15 / 20% Thorn Beast, then 15 / 20 / 25% | Thorn Beast; then Major/Minor/Spec-Ops carbine and Major pulse-carbine Elites |
| Revenant | 15 / 20 / 25% | Spec-Ops/Major pulse-carbine Elites (homing fits the Revenant), Spec-Ops carbine Elite, beam-rifle Slug Man |
| Archvile | 10 / 12 / 15% | Commander carbine or pulse-carbine Elite |
| **Cyberdemon** | **always** | Drinol boss (`HCE_BossCyberdemonDrinol`), unless `hce_digsite_spawns` is 0, which hands it back to the main pack's Hunter bosses |

DoomEdNums 30400–30417, in release order: `HCE_Drinol`, the four carbine Elites, both Slug Men, `HCE_Random{Drinol,EliteRifle,SlugMan}` (30400–30409); `HCE_BlindWolf` (30410) and `HCE_RandomBlindWolf` (30411); `HCE_ThornBeast` (30412) and `HCE_RandomThornBeast` (30413); the four pulse-carbine Elites (30414–30417). `HCE_RandomEliteRifle` now includes the pulse-carbine Elites. `HCE_Engineer` is 30418 and `HCE_RandomEngineer` is 30419; `HCE_DronePlasmaPistol` is 30420 and `HCE_RandomDrone` 30421; the Brutes are 30422–30430 (the Chieftain is 30430) and `HCE_RandomBrute` 30431; the Halo 2 Jackals are `HCE_JackalUltraPlasmaRifle` (keeps 30248), `HCE_JackalZealotSpiker` 30433, `HCE_JackalSniperBeamRifle` 30434, `HCE_RandomH2Jackal` 30435, and the Marksmen `HCE_JackalMarksmanPlasmaCarbine` 30436 and `HCE_JackalMarksmanPulseCarbine` 30437; the Drones `HCE_DroneNeedler` 30438, `HCE_DronePlasmaRifle` 30439 and `HCE_DroneSpiker` 30440. The Ultra Zealot is `HCE_EliteUltraZealotEnergySword` 30455 and `HCE_RandomEliteZealot` 30432; the Brute Stalker `HCE_BruteStalkerSpiker` 30456, and the carbine Honor Guard and Ranger Elites `HCE_EliteHonorGuardPlasmaCarbine` 30457 and `HCE_EliteRangerPlasmaCarbine` 30458. Every released class keeps its number for good: the generator pins them (`ednum_pins.json`).

**License: keep this add-on private.** Digsite's README says its content is not open source and is licensed only for MCC mod projects. The Elites' carbine is CMT's and private too. Sources are listed in the pk3's `CREDITS.txt`.

## Standalone packs (no HaloDoom Evolved needed)

The same enemies with every HaloDoom Evolved dependency built in (projectiles, grenades, explosions, shields, sounds, a loot director dropping vanilla Doom items) are in the **HaloCE-Enemies-Standalone** repository, made by `generator/build_standalone.py`. They run on plain UZDoom / GZDoom with any IWAD, next to other mods. Never load them together with these packs: they define the same enemies. Their manual covers what differs.

## Gore (Nash's Gore Mod)

The enemies work with [Nash's Gore Mod](https://github.com/poperigby/nashgore) (NashGore). Load `nashgore.pk3` last, after the HDE or standalone packs. Without it, Doom's normal blood is used, in the same colours.

**Blood colours** follow each species' blood from Halopedia's "Blood" article (Halo CE colours where the games differ). They are set as each enemy's `BloodColor`, so Doom's blood, the Flood's NashGore blood and the Halo gore patch all take the race's colour:

| Species | Blood |
|---|---|
| Elites (Sangheili) | dark blue/purple |
| Jackals (Kig-Yar) | dark blue/purple |
| Grunts (Unggoy) | light blue / teal |
| Hunters (Mgalekgolo) and Slug Men (a Mgalekgolo sub-species) | bright orange |
| Brutes (Jiralhanae, Halo 2) | dark navy blue / black |
| Drones (Yanme'e) | white, slight green tint |
| Engineers (Huragok) | reddish pink |
| Flood (all forms) | brownish green |
| Marines | red |
| Sentinels | none (machines) |
| Drinol, Blind Wolf, Thorn Beast | dark reds |

**Gibbing only from the heavy weapons:** only the weapons listed under [Dismemberment](#dismemberment) tear a body apart. Anything else leaves it whole, however hard it hits.
* **Bodies stay whole otherwise:** the classes have no `XDeath` state, and an overkill's health is held at the gib threshold, the two things NashGore gibs on.
* **Overkills and hard kills:** these spray extra blood in the race's colour; NashGore turns it into its sprays, splats, decals and pools.
* **Energy shields keep the blood in:** an enemy with its shield up doesn't bleed (no blood sprays, Halo splats or blood on its body). It starts bleeding once the shield pops, and stops again if the shield recharges.
* **Fire doesn't draw blood:** a fire hit (the flamethrower, burning) never sprays blood, adds blood to the body or makes a corpse bleed, whatever is loaded.

**Cryo Cannon:** the one exception. An enemy frozen solid by HDE's Cryo Cannon and shattered (the ice block's `IceBlock` kill) bursts into a huge splatter of blood and meat, and its body is gone.
* **With NashGore:** its full gib burst, with meat, wall and ceiling splats, plus extra gibs and blood.
* **Without NashGore:** a large blood burst.
* **No revivals:** infection forms can't reanimate it, and feigning Elites stay down.

**Halo CE and Halo 2 gore (Covenant pack patch):** with NashGore loaded, Covenant enemies, Marines and the creatures bleed Halo's blood **instead of NashGore's**: no NashGore sprays, floor splats, wall blood, corpse pools, spurts or NashGore gibs on them (the pack's own dismemberment and gibbing still happen). The Flood keep NashGore's blood. Without NashGore the patch does nothing.
* **Wall splats:** every hit sprays the species' own Halo blood decal onto the wall behind it (a second one for a heavy hit), up to 210 units away, picked at random from Halo CE's and Halo 2's splats and drawn at about twice their own size, the size Halo spreads them over a body:

  | Species | Halo decals |
  |---|---|
  | Elites, Jackals | lavender Elite splats (CE + H2) |
  | Grunts | blue Grunt splats (CE + H2) |
  | Hunters, Slug Men | orange Hunter splats (CE + H2) and CE's glowing splat (drawn bright) |
  | Brutes | Halo 2's navy Brute splat |
  | Drones | Halo 2's khaki "bugger" splats |
  | Engineers | Halo CE's pink Engineer splat |
  | Drinol, Blind Wolf, Thorn Beast | red Halo CE and Halo 2 splats, Halo 2's drippy combat splat |
  | Marines | Halo CE's red human splats (and Halo 2's); dying, Halo CE's blood pool and the drippy splat |

* **Impact bursts:** a Halo blood burst puffs out of the wound in the victim's blood colour, with a few blood streaks flung away from the shot (Halo 2's blood trails). The Covenant's are Halo CE's Covenant impact bursts, the Marines' its human impact bursts (with CE's blood bursts); the beasts use the generic Halo CE and Halo 2 bursts.
* **Floor splats:** Halo draws its blood decals on floors as well as walls (Doom's decals only go on walls), so the same splats are laid flat on the floor: under a wounded enemy at most hits (more often the harder the hit), and under the dead a pool of the large splats and smears (Halo CE's blood pool for the Marines) where the body comes to rest. At most 400 at a time; they fade after two minutes.
* **Kills:** a large burst, four big splats sprayed on the walls behind and around the body (Halo CE's Elite and Grunt smears among them), and two or three floor splats around it.
* **Skid marks:** a body thrown by its death (a rocket, a shotgun blast, a melee blow) leaves Halo CE's blood smears along the floor as it slides, stretched in the direction it went, then its pool where it stops. Grenade kills don't skid: a grenade throws bodies every which way.
* **Gore sounds (NashGore's):** a severed head or arm bounces with NashGore's gib-bounce sound and lands with its small-gib sound, a thrown body hits the floor with its blood splash, and blood streaks patter down with its blood drops (now and then). Without NashGore these sounds don't exist and nothing plays.
* **Blood the body sheds itself** (a severed stump, a corpse being shot, a flying limb): Halo blood-burst puffs in its colour.
* **Toggle:** `hce_halogore 0` turns the Halo gore off and leaves NashGore's own.
* Wall splats fade after about two minutes.
* Fire, freezing, drowning and telefrags don't bleed.
* **Toggled off** (`hce_halogore 0`), NashGore's blood comes back on them as NashGore would draw it (`nashgore_bloodtype`).

**BLUDTYPE:** none is needed, and don't list `HCE_HaloBlood` in one. The enemies' blood is `HCE_HaloBlood`, which is Doom's own blood without NashGore and hands over to the Halo gore patch (or, with it off, to NashGore's blood) when NashGore is loaded. The Flood bleed Doom's standard `Blood`, which NashGore replaces on its own.

## Dismemberment

Covenant enemies can lose their head or arms, or be torn apart, depending on the weapon that kills them. This works with or without NashGore.

**Corpses too:** a body stays shootable once it's down. It isn't solid (you walk over it), isn't auto-aimed, doesn't turn HaloDoom Evolved's reticle red (it no longer counts as a monster), and it sits low once it has fallen. Shooting it makes it bleed and adds to the blood on it. The dismembering weapons can take its head and arms off (60% a hit; the rifles only arms), frag grenades sometimes a limb, and the gibbing weapons, or blasts adding up to three times its health, tear it apart.

**Weapons that dismember:** the Magnum, Battle Rifle, DMR, Sniper Rifle, pump Shotgun, Carbine, Scattershot (normal fire), Spiker (melee only), Energy Sword, Plasma Pistol overcharge, Light Rifle (normal fire), MA5B, Beam Rifle, Boltshot and Commando. The enemies' and Marines' own pistols, rifles, carbines, shotguns and beams dismember each other too.
* **Headshot kills:** always take the head off, except with the rifles: the Battle Rifle, DMR, Carbine, Light Rifle, MA5B and Commando (and the enemies' and Marines' assault rifles, battle rifles, DMRs and carbines) take arms but never the head.
* **Other kills:** a kill landing on an arm, or on a Grunt's methane pack, takes it off nearly every time (85%). Body shots leave the limbs on.
* **Where a hit lands:** the top of the enemy (the headshot zone) is the head; the outer sides at arm height are the arms, the middle of a Grunt's back is its methane pack, the rest is the body. The Elites', Grunts', Jackals' and Marines' hit boxes reach the tops of their heads, so a shot at the head connects.

**Weapons that gib:** the Rocket Launcher, Hydra, Scattershot alt fire, Light Rifle alt fire, Binary Rifle, Unmaker, Stanchion, Gravity Hammer, GPMG (autocannon), Double Barrel, Fuel Rod, Needler supercombine, Needle Javelin, Plasma Caster, Sentinel Beam supercombine and Sticky Detonator. A body killed by one bursts apart: the head and arms fly off as pieces in a spray of blood, the rest is gone, and NashGore (when loaded) adds its meat chunks and splats.

**Grenades:** only frag grenades dismember, and they never gib. A frag kill always takes off the limb nearest the blast (a Grunt's pack among them), and a second one half the time, always within 96 units of it. Plasma and spike grenades and firebombs leave the body whole.

**Flying pieces:** a severed head or arm flies off: a blast throws it 20–25 units a tic at point blank and still about 12 at 100 units (a frag grenade sends pieces well across a room), and one shot off pops a metre or so clear of the body. NashGore's gibs from a body torn apart fly further too.

**Anything else** (plasma rifles, needles that don't supercombine, plasma grenades, ordinary melee, fire) leaves the body whole.

**In the standalone packs**, the Doom weapons count as the nearest Halo ones:
* **Dismember:** pistol, chaingun, shotgun and chainsaw.
* **Gib:** super shotgun, rocket launcher and BFG.
* **Neither:** the plasma rifle.

**Losing the gun arm while alive:** a dismembering weapon's hit on the arm holding the gun, taking a fifth of the enemy's health or more, takes the arm off half the time.
* **Grunts and Jackals survive it:** they take a hard flinch, drop the gun, and run away in terror, bleeding from the stump, until they bleed out 5–9 seconds later.
* **Anything else:** dies on the spot.

**Severed limbs:**
* **The severed piece:** shot off, it pops outward from the body (an arm to its side, a Grunt's pack backwards, the head up and to one side) and comes to rest 2–3 feet out from the body's edge. A blast throws it by the explosion's impulse instead: out from the blast's centre, harder the bigger and closer the blast (a grenade at arm's length throws it well over 10 feet). It tumbles and trails blood, and moves like HaloDoom Evolved's spent casings: it spins, kicks off at a new angle each time it bounces, then eases over and lies flat on the floor. It wears the enemy's own rank colours and armour, with a gore cap on the cut end, and fades after about 30 seconds on the floor.
* **The body:** the cut is closed with a gore stump that keeps bleeding for a few seconds as the body falls.
* **Held items:** the gun leaves the enemy's hand when it dies, or when its gun arm is shot off (it drops as a pickup). This covers guns overlaid on the body too (the Marines', the Plasma Casters). A Flood form that gets back up has its gun again. A shield gauntlet in a severed hand goes with the arm. A **Hunter's cannon arm**, shot off, comes off as HaloDoom's own weapon: the Fuel Rod for the regular and Major Hunters, the Flamethrower for the Red, the Plasma Caster for the White (the Standalone packs, which have none, keep the arm). A stealth Elite that loses its sword arm loses the blade too, and a Brute's armour-kit helmet comes off with the head.

| Race | What comes off | Stump |
|---|---|---|
| Elites, Jackals (Halo CE) | head, either arm | Tropical Thunder 98's stump models |
| Grunts (Halo CE) | head, either arm, the methane pack, regular or shellback (as in SPV3) | Tropical Thunder 98's stump models |
| Halo 2 Jackals, Drones, Hunters, Slug Men | head, either arm (a Hunter's cannon arm or shield arm) | kitbashed caps |
| Brutes | head | kitbashed cap |

The stump texture is the gore Tropical Thunder 98 made for the XAM Campaign Overhaul (as SPV3 ships it), wet ropy flesh with a bone end:
* **Elites, Jackals and Halo 2 Jackals:** the purple Jackal gore.
* **Grunts:** the teal Grunt gore.
* **The others:** recoloured to their blood. Brutes are navy, Hunters and Slug Men orange, and Drones a pale ichor.
* **Kitbashed caps:** these put the bone end in the middle of the cut. Hunters, Slug Men and Drones have no bones, so theirs show flesh only.

Limbs don't come off the Flood, Marines, Engineers or the beasts, but the gibbing weapons still burst their bodies apart. Sentinels (machines) and infection forms (which pop) are never gibbed. Brutes lose only their head, because their model is already at UZDoom's 32-surface limit. Turn it off with `hce_dismember 0`.

## Burning

An enemy on fire (HDE's flamethrower and other fire, or the standalone flames) doesn't drop dead from the burn that kills it. It flails and runs about screaming in flames for 1.5–2.7 seconds, then dies.
* **Elites, Grunts and Jackals:** they use Halo CE's own "flaming" animations, a burning flail, and Jackals also have a burning run.
* **Marines and Slug Men:** they use their own burning run and flail.
* **Everything else:** uses its panic run (or its normal run).

A burn death counts as brutal for the squad (below). Any other kill during the flailing ends it at once.

## Blood on the body

Shot enemies show blood on their bodies, in their race's colour. Once the shield is down, every hit that draws blood adds to it.
* **Off by default:** turn it on under **Options > Halo CE Gore > Blood on bodies** (or `hce_bodyblood 1`). The damage is counted while it's off, so an enemy hurt before you turn it on shows the right amount from its next hit.
* **Stages:** a few splatters at 8% of the enemy's health lost, more at 35%, and soaked at 70%. A corpse always shows at least the first stage.
* **Where it lands:** each splatter was placed on the 3D body and painted across its textures. A spray crosses seams and armour edges like real blood, with a dark wet core and drips running down from it.
* **How it's drawn:** it's an overlay that rides the body's own skeleton. Severed limbs and armour a variant doesn't wear stay clean.
* **Who bleeds:** every enemy that bleeds, Flood and Marines included, but not Sentinels.

## Your squad

Marines following you (every Marine is an ally) take orders and react to how you treat them.

* **Formation:** following you, the squad keeps US Army infantry formations (FM 3-21.8 / FM 7-92) instead of bunching up, with you as the leader. UN peacekeeping contingents use their own armies' versions of the same file and wedge.
  * **Wedge**, in the open: the Marines step back to your left and right in a V, about 3.5 m apart along each arm, four to an arm, and anyone past eight falls in down the middle. Each watches his own sector once halted (the left arm left, the right arm right), and the last man covers the rear. Slots that would be in a wall or on another level move onto your path.
  * **File**, where it's tight (under about 7 m across, back to the wedge over about 9 m): one behind another, about 2.5 m apart, walking the path you took, so they follow you through doors and corridors and round corners.
  * The doctrinal 10 m interval would spread a squad over a whole Doom room, so the intervals are closed up. They walk to their slots and run when they fall behind or you run.

* **Following you:** the Marines keep to their places in the squad's formation without fidgeting: each walks to his place once he's well off it and stops once he's on it, turns to face his sector only when he's well off it, and turns smoothly; while you walk he keeps pace in his place rather than stopping and starting; one blocked by the others settles where he stands until you move on. Out of a fight, everyone checks for room before stepping: with a friend standing in the way they wait a moment instead of shuffling round him (walking on behind one who is moving), never swing wide round a friend, and a detour round something, once chosen, holds for a moment on the same side; with no room at all they stand still rather than walk on the spot. In a fight they still sidestep round friends to reach cover. A big squad (more than 12) stands in arcs round the back of the wedge, facing out, instead of a long file trailing behind you.
* **Orders:** the Master Chief's order wheel has every order on it: bind **Squad: order wheel (hold)** under **Options > Customize Controls > Halo CE Squad** (`+hce_wheel`), hold it, point the mouse at an order and let go (or click; right-click or Escape puts it away, and the 1-0 keys pick an order straight off). It's a small, faint ring in the middle of the view, the order under the pointer lit; the game isn't dimmed behind it. Its labels and the name over a Marine in your crosshair use HaloDoom Evolved's HUD font (HaloFont), or the engine's small font where HDE isn't loaded. While the wheel is up the mouse moves its pointer, not your view, and the fire button gives the order instead of shooting. Only the combat orders also get keys of their own in that section (open fire, hold fire, focus, suppress, medic); the others are on the wheel, and every order stays a console alias you can bind yourself (`bind <key> hce_regroup`). The Master Chief says the order out loud (his own lines, in the Marines pack); nothing is printed on screen. Orders go to every following Marine within 1536 units, and one of them acknowledges.
  * `hce_follow`: follow me (the default).
  * `hce_hold`: hold position. Each Marine keeps to the spot where it stood, fighting from within 192 units of it, and walks back to it when the fight is over.
  * `hce_regroup`: regroup on me. They break off the fight and run back to you, then follow again (they give up after 8 seconds).
  * `hce_holdfire`: hold fire. No shots and no grenades until told otherwise.
  * `hce_openfire`: open fire.
  * `hce_focus`: focus on the enemy in your crosshair. Every Marine targets it until it's dead (and opens fire, if holding).
  * `hce_suppress`: suppress. For 8 seconds they fire twice as long and pause a third as long, at the enemy in your crosshair if there is one.
  * `hce_medic`: medic. Put a Marine in your crosshair: the nearest corpsman (`HCE_MarineMedic`) runs to him, crouches beside him and patches him up (60% of his health back, never past his maximum).
  * `hce_weapon`: get that weapon. Point at a gun on the ground; the nearest Marine that can use it goes and picks it up, crouching beside it as usual and leaving his own, whether or not he'd have wanted it.

  * `hce_button`: press that button. Point at a switch (a wall line you'd use); the nearest Marine goes to it and uses it.

  The aliases are for `netevent hce_squad 0`–`9` (in that order). One Marine answers each order, a random one (or the one given the job), and only once the Chief has finished his line (1.6–2.3 s later). The Chief's lines are OGG files, in `sounds/hce_chief`.
* **Trading guns:** press use on a Marine following you. If he can carry the gun in your hands (any human or Covenant gun but the melee and BFG-class ones), you swap: you get his gun and he takes yours. What he says depends on how he rates the swap (his own liking, see the weapon biases): a clearly better gun gets thanks, a fair swap an "okay", a worse one scorn, and one he can't carry at all a refusal (he keeps his). He also refuses if you already carry his gun (say, as your other weapon): taking it would only top up your ammo while he kept yours, and you'd be a weapon short. Each has its own set of Halo 2 lines, every take Halo 2 has for each voice (about 8 to 24 per voice and reaction). The Halo CE voices have no trade lines, so they tell you off instead. (HaloDoom Evolved packs only.)
* **Names:** every Marine has a rank and a name, rolled when he spawns: Privates, Privates First Class and Lance Corporals among the regulars, Lance Corporals to Sergeants among the Armored Marines, Corporals and Staff Sergeants for the Majors, Hospital Corpsman Third Class (`HM3.`) for the corpsmen. First names, middle initials and surnames are drawn from long lists, e.g. `PVT. George A. Romero`. Sergeant Johnson is always `SGT. Avery J. Johnson` and Stacker `MSG. Marcus P. Stacker`.
* **Name and health over his head:** while a Marine is in your crosshair, his rank and name show over his head with Halo CE's health bar under it (HaloDoom Evolved's CE HUD art: nine segments, yellow then red as he's hurt). It fades a moment after you look away.
* **ODSTs (new):** Spiral's Halo CE ODST (`extract_odst.py`, from the a50 map: its own model, legs, torso, arms, helmet and visor, rigged to the Marine's skeleton), with every animation the Marines have and the Marines' guns, voices, blood and squad orders. They fight as Armored Marines (the same combat data, toughness and collision) and wear their textures as they are. The visor reflects Halo CE's cube map per pixel as you move around it (the visor shader's own cube and tints: the cyborg's reflection cube on the base ODSTs, a darker one tinted in each Raven's colour), brighter toward glancing angles.
  * **a50's loadouts:** the assault rifle (`HCE_MarineOdstAssaultRifle`, 30331, and the Major, `HCE_MarineOdstAssaultRifleMajor`, 30332) and the shotgun (`HCE_MarineOdstShotgun`, 30337).
  * **Fire Team Raven** (Connor Dawn's models, from the a10 map): four ODSTs in their own colours, with their a10 guns: green with the shotgun (`HCE_MarineOdstRavenGreen`, 30334), orange with the battle rifle (`HCE_MarineOdstRavenOrange`, 30335), blue with the assault rifle (`HCE_MarineOdstRavenBlue`, 30333) and purple with the sniper rifle (`HCE_MarineOdstRavenPurple`, 30336).
  * **Halo 2's ODSTs:** their own body, the Halo 2 Marine's ODST armour and helmet (`extract_h2_odst.py`), carried onto the Halo CE Marine's skeleton so they play every Marine animation, its armour weathered like the Halo CE Marines' (Halo 2's bump and detail maps, grime, worn plate edges baked in), Halo 2's dark bluish-purple visor, and Halo 2's own Marine stance set (low-ready idle, moves and aim) for every gun: with the assault rifle (`HCE_MarineOdstHalo2`, 30340), the battle rifle (`HCE_MarineOdstHalo2BattleRifle`, 30341) and the Major's shotgun (`HCE_MarineOdstHalo2Shotgun`, 30342).
  * **Hellbringer:** an ODST flame trooper (`HCE_MarineOdstHellbringer`, 30343) in Halo Wars 2's Hellbringer helmet from Elefant's kit, with a red visor (the helmet's own lens, drawn with the visor shader so it catches the light like the ODSTs' visors; Armored Marines who roll the helmet keep its amber lens), a gas mask below and the fuel tank on his back, carrying the flamethrower in the support stance.
  * **Sealed helmets:** two more ODSTs on Spiral's body with one of the kit's fully closed helmets in place of its own: the closed visor helmet, with a silver visor, and the battle rifle (`HCE_MarineOdstClosedHelmet`, 30338), and the enclosed visor helmet with the Major's shotgun (`HCE_MarineOdstEnclosedHelmet`, 30339).
  * **Rocketeer and Sniper:** two more ODSTs on Spiral's body in the kit's sealed helmets: the Rocketeer, in the enclosed visor helmet with the launcher's spare-rocket tube on his back, with the rocket launcher in Halo 2's launcher stance (`HCE_MarineOdstRocketeer`, 30348), and the Sniper, in the closed visor helmet with a silver visor, with the sniper rifle (`HCE_MarineOdstSniper`, 30349).
  * `HCE_RandomMarineODST` (30330) spawns any of them; `leatherneck` spawns them with the other Marines.
* **Corpsmen (new):** Marines who answer the medic order, each with his own gun: `HCE_MarineMedic` (30321, the Sidekick), `HCE_MarineMedicAssaultRifle` (30325, Halo CE's assault rifle), `HCE_MarineMedicMa37` (30326), `HCE_MarineMedicMagnum` (30327), `HCE_MarineMedicShotgun` (30328, Halo CE's shotgun) and `HCE_MarineMedicSmg` (30329). They're in the random Marine pool. A corpsman always wears the first-aid kit with its red cross; no other Marine does.
* **Pilots (new):** Halo 2's Pelican crews (`extract_h2_pilot.py`): the flight helmet with its smoked visor over one of Halo 2's six Marine faces (Smith, Banks, Dion, Morgan, Perez or Walter, rolled when he spawns), worn in place of the Halo CE head, and none of the field kit. Lightly armed and a little less tough than a rifleman (no armour): the Magnum (`HCE_MarinePilotMagnum`, 30350) or the SMG (`HCE_MarinePilotSmg`, 30351).
* **Radio operator (new):** a Marine with the radio pack on his back and the assault rifle (`HCE_MarineRadioOperator`, 30352). Once a fight is on (an enemy in sight), he calls it in; four to seven seconds later a **fire team of three Marines** comes up from behind him, out of the enemy's sight (riflemen, a battle rifle, a shotgun, an SMG or an Armored Marine), and falls in with the squad like any other Marine. One call per operator.
* **Friendly fire:** a Marine you shoot scolds you, and shield hits count too. After 4 hits within 12 seconds, or 60% of its health, it turns on you, says so and fights you. It forgives you 30 seconds after your last hit on it, or once you die.
  * Killing a Marine: the others who saw it call it out, and each of them counts it as two hits against you.
  * Turn betrayal off with `hce_betrayal 0`; they still scold you.
* **Wounded:** under a third of its health a Marine limps (moves at about half speed) and now and then calls for help.
* **Last man standing:** a Marine with no other Marine within 640 units and you more than 768 units away ducks into cover and panics for a few seconds instead of fighting. It can do this again every 12 seconds.
* **Motion tracker:** Marines show on HaloDoom Evolved's motion tracker as yellow friendly dots at all times, not only while they have a target (the tracker draws a monster only while it has one, so a Marine with none carries a stand-in dot that rides with him). (HaloDoom Evolved packs only.)
* **Lobbed rounds:** with a gun whose rounds drop (the grenade launchers, the sticky detonator, the Plasma Caster), a Marine leads a moving target and aims up into the arc that lands the round on it, the low arc where there is one, or 45 degrees when the target is out of reach.
* **Sergeant Johnson:** Marines within 640 units of him aim about 30% tighter and never cower. He nearly always has a quip when he kills something, and when he falls, the Marines who see it call out their leader's death.

* **Watching each other's backs:** a Marine hit from behind calls it and the nearest squadmate not already on that enemy turns on it; and an enemy coming from the squad's rear or flank (100 degrees or more off the way the fight faces) that nobody is engaging gets the nearest Marine who isn't busy, with a shout.

## Low ready

Out of a fight (no target, and ten seconds after the last one), everyone with a gun stands and walks at low ready, Halo 2's 'patrol' animations (`low_ready_anims.py`): the weapon held low across the body, a relaxed idle and an unhurried walk at that animation's own pace. The Marines take Halo CE's own low ready (its Marine 'alert' animations: the weapon held low, with their idle and walk) where Halo CE has one, and Halo 2's Marine set for the rest (pistol and launcher stances). The Halo CE Jackals have their own too (their 'alert' idle and walk: the shield lowered to the side). The Elites, Grunts and Halo 2 Jackals take Halo 2's own (pistol, rifle, fuel rod and sword stances), and the Brutes theirs. The moment they have a target, they snap back to their combat stances. The Marines' flamethrower stance has no low ready.

## Squad tactics

Both sides fight to real doctrine (`hce_tactics`, on by default; `hce_tactics 0` turns it off).

**The UNSC** fights as US Army and UN infantry do (FM 3-21.8 / FM 7-92 fire-team drills; the UN infantry battalion manual uses the same national drills):
* **Fire teams:** the squad following you splits into two teams, Alpha (the base of fire) and Bravo (the maneuver element).
* **React to contact (battle drill 1):** when anyone makes contact, the whole squad turns on that enemy and goes down returning fire for two seconds.
* **Bounding overwatch:** then the teams take turns. One team rushes for 3 to 5 seconds without shooting ("I'm up, he sees me, I'm down"), while the other holds and lays down suppressive fire (long bursts, short pauses). Alpha moves up by your side; Bravo works round the enemy's flank at its own range, never more than about 20 m from you.
* **Break contact (battle drill 2):** once the squad has lost more than half its strength, the teams bound back past you, one covering the other.
* **All-round defence:** told to hold, the squad spreads into a ring around where it stands, each Marine facing out over his own sector.

**The Covenant** fights on Soviet Deep Battle and Mongol steppe lines. Each Elite or Brute leader runs a battle plan for its lance (up to nine followers, the Mongol arban of ten):
* **Preparatory fire:** the first three seconds of contact are a barrage. Fuel rods and other heavy weapons fire in long bursts while the lance forms its ranks.
* **First echelon:** the Jackals with shields form a shield wall ahead of the leader, shoulder to shoulder, toward the enemy. The Grunts stand in the rank behind them, or in front with no Jackals. Heavy weapons stay behind the leader.
* **Encirclement:** with five or more in the lance, the two outermost Grunts sweep round both flanks to close the ring (the Mongol tulughma).
* **Horse archers:** Jackal marksmen and snipers shoot from long range off the flanks and fall back, still shooting, when pressed. Drones make firing passes along the flank and pull out when you close in.
* **Feigned retreat:** when you push in on a lance, its Grunts sometimes break and run back past their leader, who waits silent in ambush. Follow them within about 10 m of it and the ambush is sprung; otherwise the "rout" turns and fights again after a few seconds.
* **Second echelon and breakthrough:** the leader holds back behind its first echelon. Once that echelon has lost 40%, the ambush is sprung, or the fight has gone on about 16 seconds, the leader passes through its own ranks and charges.
* **Massed fire:** the lance takes its leader's target, concentrating at the point of attack.

Sources: [FM 7-92, squad wedge and file](https://www.globalsecurity.org/military/library/policy/army/fm/7-92_2001/fm792_4.htm), [individual movement techniques and fire and movement](https://en.wikipedia.org/wiki/Individual_movement_techniques), [UN Infantry Battalion Manual](https://pksoi.armywarcollege.edu/wp-content/uploads/2021/05/2020.01-UNIBAM-Infantry-Battalion-Manual_JAN-2020.pdf), [deep operation](https://military-history.fandom.com/wiki/Deep_operation), [Mongol military strategy](https://blogs.iu.edu/firewalls/2025/02/23/the-engine-of-the-khan-empire-why-military-strategy-was-the-key-to-mongol-success).

## Brutality and squad morale

How brutally an Elite or Brute dies decides how long the squad it led takes to pull itself together, if it was the last leader standing nearby. If another Elite or Brute is still alive within reach, the squad falls in with it as before.

| Death | Brutality |
|---|---|
| torn apart (gibbed) | 6 |
| burned alive | 3 |
| beheaded | 3 |
| each arm lost | 1 |
| headshot | 1 |
| hard kill (a big hit, an explosion) | 1 |

* **Regrouping:** the squad's Grunts and Jackals can't regroup under anyone for 3 seconds plus 2.5 seconds per point. A clean body shot gives 3–5 seconds; a rocket gib (torn apart, which also takes the head and both arms) about 30.
* **Panic:** each point also adds 8% to every member's chance to panic, and those that panic stay panicked for up to the same time (at most 12 seconds).

## Not included / known limits

* The Flood and Sentinels have no dialogue (HaloDoomEnemies has no lines for them).
* No vehicles, turrets, dropships or scripted AI (encounters, squads, firing points). Units pick positions with local steering instead of Halo's firing-point graph.
* Only combat characters are included: no Keyes, Cortana, 343 Guilty Spark or crew.

## Legal

The models, textures and animations are extracted from Halo CE (and Halo 2 / SPV3 for some of them), and the voice lines are Halo audio; all of it belongs to Microsoft / Bungie. Use the packs privately: **keep them out of public releases** (including UZHalo Shell / HDE Core releases), and keep this repository private. The extraction pipeline in the HDE repository's `generator/` rebuilds the packs from your own copy of the games instead.

## Files

* `packs/`: the four packs, each folder the root of one pk3; `build.py` (or `Build_PK3s.bat`) compiles them into `dist/`, with the merged pack.
* `tools/merge_hce_packs.py`: merges any set of packs into one pk3.
* `docs/PACK_README.md`: this manual.
* `generator/`: the extraction and generation pipeline (Python 3, numpy, Pillow) that rebuilds the packs from the Halo maps; see `generator/README.md`.

## DoomEdNums

| Num | Class |
|---|---|
| 30200 | `HCE_EliteMajorNeedler` |
| 30201 | `HCE_EliteMajorPlasmaRifle` |
| 30202 | `HCE_EliteMinorNeedler` |
| 30203 | `HCE_EliteMinorPlasmaRifle` |
| 30204 | `HCE_EliteMinorPlasmaRifleRanged` |
| 30205 | `HCE_EliteCommanderEnergySword` |
| 30206 | `HCE_EliteCommanderPlasmaRifle` |
| 30207 | `HCE_EliteSpecopsNeedler` |
| 30208 | `HCE_EliteSpecopsPlasmaRifle` |
| 30209 | `HCE_StealthEliteMajorEnergySword` |
| 30210 | `HCE_StealthEliteMajorPlasmaRifle` |
| 30211 | `HCE_StealthElitePlasmaRifle` |
| 30212 | `HCE_Floodcarrier` |
| 30213 | `HCE_FloodcombatEliteAssaultRifle` |
| 30214 | `HCE_FloodcombatEliteFlameThrower` |
| 30215 | `HCE_FloodcombatEliteNeedler` |
| 30216 | `HCE_FloodcombatElitePistol` |
| 30217 | `HCE_FloodcombatElitePlasmaPistol` |
| 30218 | `HCE_FloodcombatElitePlasmaRifle` |
| 30219 | `HCE_FloodcombatEliteRocketLauncher` |
| 30220 | `HCE_FloodcombatEliteShotgun` |
| 30221 | `HCE_FloodcombatEliteSniperRifle` |
| 30222 | `HCE_FloodcombatEliteStealthUnarmed` |
| 30223 | `HCE_FloodcombatEliteUnarmed` |
| 30224 | `HCE_FloodcombatHumanAssaultRifle` |
| 30225 | `HCE_FloodcombatHumanFlameThrower` |
| 30226 | `HCE_FloodcombatHumanNeedler` |
| 30227 | `HCE_FloodcombatHumanPistol` |
| 30228 | `HCE_FloodcombatHumanPlasmaPistol` |
| 30229 | `HCE_FloodcombatHumanPlasmaRifle` |
| 30230 | `HCE_FloodcombatHumanRocketLauncher` |
| 30231 | `HCE_FloodcombatHumanShotgun` |
| 30232 | `HCE_FloodcombatHumanUnarmed` |
| 30233 | `HCE_FloodInfection` |
| 30234 | `HCE_GruntFleeMajorNeedler` |
| 30235 | `HCE_GruntFleeMajorPlasmaPistol` |
| 30236 | `HCE_GruntFleeMinorNeedler` |
| 30237 | `HCE_GruntFleeMinorPlasmaPistol` |
| 30238 | `HCE_GruntMajorNeedler` |
| 30239 | `HCE_GruntMajorPlasmaPistol` |
| 30240 | `HCE_GruntMinorNeedler` |
| 30241 | `HCE_GruntMinorPlasmaPistol` |
| 30242 | `HCE_GruntSpecopsFuelRod` |
| 30243 | `HCE_GruntSpecopsFuelRodAirdef` |
| 30244 | `HCE_GruntSpecopsNeedler` |
| 30245 | `HCE_Hunter` |
| 30246 | `HCE_HunterMajor` |
| 30247 | `HCE_JackalMinorPlasmaPistol` |
| 30248 | `HCE_JackalUltraPlasmaRifle` |
| 30249 | `HCE_MarineAssaultRifle` |
| 30250 | `HCE_MarineAssaultRifleMajor` |
| 30251 | `HCE_MarineNeedler` |
| 30252 | `HCE_MarinePlasmaRifle` |
| 30253 | `HCE_MarineShotgun` |
| 30254 | `HCE_MarineArmoredAssaultRifle` |
| 30255 | `HCE_MarineArmoredAssaultRifleMajor` |
| 30256 | `HCE_MarineArmoredNeedler` |
| 30257 | `HCE_MarineArmoredPlasmaRifle` |
| 30258 | `HCE_MarineArmoredPlasmaRifleMajor` |
| 30259 | `HCE_MarineArmoredShotgunMajor` |
| 30260 | `HCE_Sentinel` |
| 30261 | `HCE_SentinelMajor` |
| 30262 | `HCE_SentinelDefensive` |
| 30263 | `HCE_SentinelShielded` |
| 30264 | `HCE_SentinelShieldedMajor` |
| 30265 | `HCE_RandomElite` |
| 30266 | `HCE_RandomEliteSpecial` |
| 30267 | `HCE_RandomFloodCarrier` |
| 30268 | `HCE_RandomFloodElite` |
| 30269 | `HCE_RandomFloodHuman` |
| 30270 | `HCE_RandomFloodInfection` |
| 30271 | `HCE_RandomGrunt` |
| 30272 | `HCE_RandomGruntSpecOps` |
| 30273 | `HCE_RandomHunter` |
| 30274 | `HCE_RandomJackal` |
| 30275 | `HCE_RandomJackalMajor` |
| 30276 | `HCE_RandomMarine` |
| 30277 | `HCE_RandomMarineArmored` |
| 30278 | `HCE_RandomSentinel` |
| 30279 | `HCE_JackalMajorNeedler` |
| 30280 | `HCE_HunterWhite` |
| 30281 | `HCE_HunterRed` |
| 30282 | `HCE_EliteMajorFuelRod` |
| 30283 | `HCE_EliteSpecopsBeamRifle` |
| 30284 | `HCE_MarineArmoredBattleRifle` |
| 30285 | `HCE_MarineArmoredBulldog` |
| 30286 | `HCE_MarineArmoredCommando` |
| 30287 | `HCE_MarineArmoredDmr` |
| 30288 | `HCE_MarineArmoredDoubleBarrel` |
| 30289 | `HCE_MarineArmoredFlamethrower` |
| 30290 | `HCE_MarineArmoredGpmg` |
| 30291 | `HCE_MarineArmoredGrenadeLauncher` |
| 30292 | `HCE_MarineArmoredHydra` |
| 30293 | `HCE_MarineArmoredMa37` |
| 30294 | `HCE_MarineArmoredMagnum` |
| 30295 | `HCE_MarineArmoredRocketLauncher` |
| 30296 | `HCE_MarineArmoredSidekick` |
| 30297 | `HCE_MarineArmoredSmg` |
| 30298 | `HCE_MarineArmoredSniper` |
| 30299 | `HCE_MarineArmoredStickyDetonator` |
| 30300 | `HCE_MarineBattleRifle` |
| 30301 | `HCE_MarineBulldog` |
| 30302 | `HCE_MarineCommando` |
| 30303 | `HCE_MarineDmr` |
| 30304 | `HCE_MarineDoubleBarrel` |
| 30305 | `HCE_MarineFlamethrower` |
| 30306 | `HCE_MarineGpmg` |
| 30307 | `HCE_MarineGrenadeLauncher` |
| 30308 | `HCE_MarineHydra` |
| 30309 | `HCE_MarineMa37` |
| 30310 | `HCE_MarineMagnum` |
| 30311 | `HCE_MarineRocketLauncher` |
| 30312 | `HCE_MarineSidekick` |
| 30313 | `HCE_MarineSmg` |
| 30314 | `HCE_MarineSniper` |
| 30315 | `HCE_MarineStickyDetonator` |
| 30316 | `HCE_SgtJohnson` |
| 30317 | `HCE_EliteSpecopsPlasmaCaster` |
| 30318 | `HCE_GruntHeavyFuelRod` |
| 30319 | `HCE_GruntUltraNeedler` |
| 30320 | `HCE_GruntUltraPlasmaPistol` |
| 30321 | `HCE_MarineMedic` |
| 30322 | `HCE_EliteHeavyFuelRod` |
| 30323 | `HCE_EliteHeavyNeedler` |
| 30324 | `HCE_EliteHeavyPlasmaRifle` |
| 30325 | `HCE_MarineMedicAssaultRifle` |
| 30326 | `HCE_MarineMedicMa37` |
| 30327 | `HCE_MarineMedicMagnum` |
| 30328 | `HCE_MarineMedicShotgun` |
| 30329 | `HCE_MarineMedicSmg` |
| 30330 | `HCE_RandomMarineODST` |
| 30331 | `HCE_MarineOdstAssaultRifle` |
| 30332 | `HCE_MarineOdstAssaultRifleMajor` |
| 30333 | `HCE_MarineOdstRavenBlue` |
| 30334 | `HCE_MarineOdstRavenGreen` |
| 30335 | `HCE_MarineOdstRavenOrange` |
| 30336 | `HCE_MarineOdstRavenPurple` |
| 30337 | `HCE_MarineOdstShotgun` |
| 30338 | `HCE_MarineOdstClosedHelmet` |
| 30339 | `HCE_MarineOdstEnclosedHelmet` |
| 30340 | `HCE_MarineOdstHalo2` |
| 30341 | `HCE_MarineOdstHalo2BattleRifle` |
| 30342 | `HCE_MarineOdstHalo2Shotgun` |
| 30343 | `HCE_MarineOdstHellbringer` |
| 30344 | `HCE_EliteHonorGuardEnergySword` |
| 30345 | `HCE_EliteHonorGuardPlasmaRifle` |
| 30346 | `HCE_EliteRangerNeedler` |
| 30347 | `HCE_EliteRangerPlasmaRifle` |
| 30348 | `HCE_MarineOdstRocketeer` |
| 30349 | `HCE_MarineOdstSniper` |
| 30350 | `HCE_MarinePilotMagnum` |
| 30351 | `HCE_MarinePilotSmg` |
| 30352 | `HCE_MarineRadioOperator` |
| 30400 | `HCE_Drinol` |
| 30401 | `HCE_EliteCommanderPlasmaCarbine` |
| 30402 | `HCE_EliteMajorPlasmaCarbine` |
| 30403 | `HCE_EliteMinorPlasmaCarbine` |
| 30404 | `HCE_EliteSpecopsPlasmaCarbine` |
| 30405 | `HCE_SlugManParticleBeam` |
| 30406 | `HCE_SlugManPlasmaPistol` |
| 30407 | `HCE_RandomDrinol` |
| 30408 | `HCE_RandomEliteRifle` |
| 30409 | `HCE_RandomSlugMan` |
| 30410 | `HCE_BlindWolf` |
| 30411 | `HCE_RandomBlindWolf` |
| 30412 | `HCE_ThornBeast` |
| 30413 | `HCE_RandomThornBeast` |
| 30414 | `HCE_EliteMinorPulseCarbine` |
| 30415 | `HCE_EliteMajorPulseCarbine` |
| 30416 | `HCE_EliteSpecopsPulseCarbine` |
| 30417 | `HCE_EliteCommanderPulseCarbine` |
| 30418 | `HCE_Engineer` |
| 30419 | `HCE_RandomEngineer` |
| 30420 | `HCE_DronePlasmaPistol` |
| 30421 | `HCE_RandomDrone` |
| 30422 | `HCE_BruteMinorPlasmaRifle` |
| 30423 | `HCE_BruteMinorAssaultRifle` |
| 30424 | `HCE_BruteMajorSpiker` |
| 30425 | `HCE_BruteMajorShotgun` |
| 30426 | `HCE_BruteCaptainPlasmaRifle` |
| 30427 | `HCE_BruteCaptainShotgun` |
| 30428 | `HCE_BruteHonorGuardPlasmaRifle` |
| 30429 | `HCE_BruteHonorGuardAssaultRifle` |
| 30430 | `HCE_BruteChieftainGravityHammer` |
| 30431 | `HCE_RandomBrute` |
| 30432 | `HCE_RandomEliteZealot` |
| 30433 | `HCE_JackalZealotSpiker` |
| 30434 | `HCE_JackalSniperBeamRifle` |
| 30435 | `HCE_RandomH2Jackal` |
| 30436 | `HCE_JackalMarksmanPlasmaCarbine` |
| 30437 | `HCE_JackalMarksmanPulseCarbine` |
| 30438 | `HCE_DroneNeedler` |
| 30439 | `HCE_DronePlasmaRifle` |
| 30440 | `HCE_DroneSpiker` |
| 30441 | `HCE_SlugManMajorNeedler` |
| 30442 | `HCE_SlugManMajorParticleBeam` |
| 30443 | `HCE_SlugManMajorPlasmaCarbine` |
| 30444 | `HCE_SlugManMajorPlasmaPistol` |
| 30445 | `HCE_SlugManMajorPlasmaRifle` |
| 30446 | `HCE_SlugManMajorPulseCarbine` |
| 30447 | `HCE_SlugManMinorNeedler` |
| 30448 | `HCE_SlugManMinorPlasmaCarbine` |
| 30449 | `HCE_SlugManMinorPlasmaRifle` |
| 30450 | `HCE_SlugManUltraParticleBeam` |
| 30451 | `HCE_SlugManUltraPlasmaCarbine` |
| 30452 | `HCE_SlugManUltraPlasmaRifle` |
| 30453 | `HCE_BruteCaptainPlasmaCaster` |
| 30454 | `HCE_SgtStacker` |
| 30455 | `HCE_EliteUltraZealotEnergySword` |
| 30456 | `HCE_BruteStalkerSpiker` |
| 30457 | `HCE_EliteHonorGuardPlasmaCarbine` |
| 30458 | `HCE_EliteRangerPlasmaCarbine` |

## Credits

* **Gore:** the gore stumps and gore textures are by Tropical Thunder 98, from the XAM Campaign Overhaul.
* **Engineer:** from Halo CE Ruby's Rebalance.
* **Blind Wolf and Thorn Beast:** created by SOI_7.
* **Marine kit:** the extra Marine accessories and permutations are Elefant's.
* **Additional Brute and Elite content:** by Shigure (the Ultra Zealot's armour and arm shield among it).
* **Elite Vanguard animations:** by Masterz1337 and Ruby of Blue (the shield Elite's animations: the Ultra Zealot's guard and sword actions).
* **ODSTs:** the Halo CE ODST model and textures by Spiral.
* **Fire Team Raven:** the Fire Team Raven ODST models by Connor Dawn.
* **Halo assets:** property of Microsoft / 343 Industries / Bungie, used under the Game Content Usage Rules (non-commercial).
* HaloDoom Evolved team (HDE and the enemy API base); Lewisk3/HaloDoomEnemies (voice files); the CMT Covenant carbine and the Halo 3 Spiker port authors; the Digsite source release.
