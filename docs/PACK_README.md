# Halo CE Enemy Pack for UZDoom / HaloDoom Evolved

> **In this repository** Covenant, the Digsite add-on and the voices are one pack, `HaloCE_HDE_Bundle.pk3`, which also carries the enemy API and the Core code it uses. Load it on its own after HDE; for Flood, Sentinels and Marines use the core + faction packs, or the merged pack (`python build.py --merged`). The repository README has the exact load orders. The rest of this manual describes the packs as they were shipped separately; the enemies and settings are the same.

Halo: Combat Evolved's campaign enemies (plus Marines) are extracted from the ten Xbox campaign `.map` files. Each one is an **IQM model with its full Halo animation set**, and its AI is translated from the Halo CE decomp into **ZScript** on top of an extended `enemies_base.zsc`.

| | |
|---|---|
| Characters | 14: Grunt, Grunt Spec-Ops, Jackal, Jackal Major, Elite, Elite Special (Spec-Ops/Stealth/Commander), Hunter, Flood Infection, Flood Carrier, Flood Combat Elite, Flood Combat Human, Sentinel, Marine, Armored Marine |
| Spawnable classes | 82: 68 actor variants (65 from Halo CE plus the new Ultra Jackal and White/Red Hunters) plus 14 `HCE_Random<Character>` spawners |
| Animations | 40–200+ per character, played by name (`SetAnimation`). Fire, flinch and reload overlays are baked into standalone clips |
| Weapons | Each enemy holds its Halo CE weapon (11 third-person models: plasma pistol, plasma rifle, needler, fuel rod, energy sword, assault rifle, pistol, shotgun, sniper rifle, rocket launcher, flamethrower), bound to Halo's hand marker |
| Skins | Halo base maps, with each variant's colours (Minor/Major/Spec-Ops etc.) pre-baked from the multipurpose map's change-colour mask. Flood forms use their untinted base maps; on Xbox the change colour covers almost the whole body and turned them green |
| Stats | Health, shields, weapon, burst timing, accuracy, ranges and grenade counts all come straight from each variant's `actv`/`actr`/`coll` tags |

## Requirements and load order

* **UZDoom**. The enemy pack uses ZScript `version "4.15.1"`.
* **HaloDoom Evolved, Local_DEV branch, unmodified.** HDE supplies the projectiles, grenades, `ShieldProcessor`, weapon sounds and player. The pack's changes to HDE's enemy API ship as a small addon pk3 that loads on top of your build, so you never rebuild or edit Local_DEV itself. (HDE master isn't supported.)

### Faction packs

The enemies come as one pack per faction on top of a small shared core. Load the core plus any combination of factions:

| Pack | Contents | Size |
|---|---|---|
| `HaloCE_Core.pk3` | **Required.** Shared projectiles, the Doom-monster replacement handler, CVARs and sound aliases. It contains no Halo assets, so it can be shared publicly. | 6 KB |
| `HaloCE_Covenant.pk3` | Grunts, Jackals, Elites, Hunters, and the Doom boss stand-ins | 14 MB |
| `HaloCE_Flood.pk3` | Infection, carrier and combat forms | 10 MB |
| `HaloCE_Sentinels.pk3` | Sentinels | 1.3 MB |
| `HaloCE_Marines.pk3` | Marines (Doom's marines and allied monsters become these) | 5 MB |

The replacement table lives in the core. Any pick whose faction pack isn't loaded is skipped, and the remaining picks share its weight. A Doom monster whose entire list is missing stays a Doom monster (for example Pinkies without the Flood pack, or Cacodemons without Sentinels). Without the Marines pack, Doom's marines and allied monsters stay as they are. DoomEdNums didn't change; each pack lists its own.

#### Merging packs into one

`merge_hce_packs.py` combines any set of these packs into a single pk3. It needs only Python 3.

```
python3 merge_hce_packs.py                    # Core + Covenant + Digsite in the same folder -> HaloCE_Merged.pk3
python3 merge_hce_packs.py -o MyHalo.pk3 HaloCE_Core.pk3 HaloCE_Covenant.pk3 HaloCE_Flood.pk3 HaloCE_Enemies_Digsite.pk3
```

* It writes one `zscript.txt` with every pack's includes, and one `mapinfo.txt` with all DoomEdNums and both event handlers, kept in their original order.
* `cvarinfo.txt` and `CREDITS.txt` are joined, with one section per pack.
* Everything else is copied. If a file exists in two packs with different contents, or a DoomEdNum is used twice, the merge stops and names it instead of guessing.
* Load the result where the separate packs went: after the API addon, before the voice pack.
* On Windows, keep `Merge_HaloCE_Packs.bat` next to the script. Double-click it to merge Core + Covenant + Digsite from that folder, or drag any pk3s onto it to merge exactly those. It finds Python for you and keeps the window open so you can read the result.

**One-click merges per pack set.** There is a script and a launcher for each set. Put them next to `merge_set.py`, `merge_hce_packs.py` and the pk3s:

| Set | Script | Windows launcher | Packs it picks up | Output |
|---|---|---|---|---|
| HDE (needs HDE Local_DEV + `HCE_EnemyAPI_LocalDEV.pk3`) | `merge_hde_packs.py` | `Merge_HDE_Packs.bat` | `HaloCE_Core` (required), `HaloCE_Covenant`, `HaloCE_Flood`, `HaloCE_Sentinels`, `HaloCE_Marines`, `HaloCE_Enemies_Digsite` | `HaloCE_Merged.pk3` |
| Standalone (no HDE) | `merge_standalone_packs.py` | `Merge_Standalone_Packs.bat` | `HaloCE_Standalone_Core` (required), `_Covenant`, `_Flood`, `_Sentinels`, `_Marines`, `_Digsite` | `HaloCE_Standalone_Merged.pk3` |

* **Which packs:** each script merges every pack of its set that is in the folder, so leave out the factions you don't want.
* **Voices:** `--voices` (or answering Y in the launcher) puts `HaloCE_Enemies_Voices.pk3` inside the merged pack too.
* **Drag and drop:** dragging pk3s onto a launcher merges exactly those.
* **Safety checks:** a pack from the other set is refused with a message naming the right script. `merge_hce_packs.py` itself now also refuses to mix HDE and standalone packs.
* **Load order:** after merging, each script prints the load order for its result.

**All-in-one bundles.** `merge_bundle.py` packs the usual set (Core, Covenant, Digsite, the enemy API and the voices) into a single pk3 for either version. There is a launcher for each:

| Launcher | Needs next to it | Output | Load |
|---|---|---|---|
| `Merge_HDE_Bundle.bat` (`merge_bundle.py hde`) | `HaloCE_Core`, `HaloCE_Covenant`, `HaloCE_Enemies_Digsite`, `HCE_EnemyAPI_LocalDEV`, `HaloCE_Enemies_Voices` | `HaloCE_HDE_Bundle.pk3` | HDE (Local_DEV), then the bundle; nothing else |
| `Merge_Standalone_Bundle.bat` (`merge_bundle.py standalone`) | `HaloCE_Standalone_Core`, `_Covenant`, `_Digsite`, `HaloCE_Enemies_Voices` | `HaloCE_Standalone_Bundle.pk3` | the bundle on its own, with any other mods |

* **Standalone API:** the standalone core already contains the enemy API, so that bundle has no separate API pack.
* **HDE API:** in the HDE bundle, the API's `ZScript/BaseAI/enemies_base.zsc` still overrides HDE's file of the same path, so the bundle must load after HDE.
* **Requirements:** keep `merge_bundle.py` and `merge_hce_packs.py` together. Every listed pack is required, and a missing one is named.

**Updating a merged pack.** When a new Digsite add-on comes out, `update_merged_pack.py` swaps it into your existing `HaloCE_Merged.pk3`, so you don't need Core or Covenant again:

```
python3 update_merged_pack.py                                         # HaloCE_Merged.pk3 + HaloCE_Enemies_Digsite.pk3 in this folder
python3 update_merged_pack.py HaloCE_Merged.pk3 HaloCE_Enemies_Digsite.pk3 -o New_Merged.pk3
```

* The tool removes the old add-on's ZScript, its `.dig` lumps, its own asset folders (`models/hce_dig`, `sounds/hce_dig`), its DoomEdNums and event handler, and its sections of `cvarinfo.txt` / `CREDITS.txt`. Then it merges the new add-on in. Files the new version no longer ships don't linger. The result is identical to merging Core + Covenant + the new Digsite from scratch.
* Without `-o` it updates the merged pk3 in place and keeps the previous one as `HaloCE_Merged.bak.pk3`.
* It needs `merge_hce_packs.py` in the same folder.
* It works for any pack that was merged in. Give the newer copy of that pack instead: it is matched by file name.
* On Windows, double-click `Update_Merged_With_Digsite.bat`, or drag the merged pk3 and then the new Digsite pk3 onto it.

Load order: `HDE (Local_DEV).pk3` → `HCE_EnemyAPI_LocalDEV.pk3` → `HaloCE_Core.pk3` → faction packs (any order) → `HaloCE_Enemies_Digsite.pk3` (optional, private) → `HaloCE_Enemies_Voices.pk3` (optional)

```
uzdoom -file HDE_LocalDEV.pk3 HCE_EnemyAPI_LocalDEV.pk3 HaloCE_Core.pk3 HaloCE_Covenant.pk3 HaloCE_Flood.pk3 HaloCE_Sentinels.pk3 HaloCE_Marines.pk3 HaloCE_Enemies_Voices.pk3
```

### How the addon works

UZDoom resolves every `#include` to the **last-loaded** file with that path.

* **`HCE_EnemyAPI_LocalDEV.pk3`** contains only `ZScript/BaseAI/enemies_base.zsc`. Local_DEV's own `ZSCRIPT.txt` already includes that path, so loading the addon after Local_DEV swaps in the extended API. Local_DEV's files stay untouched, and the addon has no `ZSCRIPT` lump of its own, so the class is never defined twice.
  * The file keeps every member of Local_DEV's original `HaloDoom_EnemyBase` and `LastDamageInfo`, plus its usage example.
  * It compiles under Local_DEV's `version "4.10.0"`. The one 4.12+ call (`SetAnimation`) sits behind a virtual hook, `HCE_ApplyAnim`, which the enemy pack implements in its own 4.15.1 unit.
* **`HaloCE_Core.pk3` and the faction packs** don't contain the API. They add the projectiles, handler, enemy classes and models, so they must load **after** the addon.

> **Local_DEV crash note:** if UZDoom crashes during "Texman.Init" (signal 11) with a Local_DEV pk3, check whether the pk3 was zipped with the `Raw_Assets/` folder. That 2.6 GB folder of source art is what crashes texture init. A Local_DEV pk3 without `Raw_Assets/` and `.git/` (~500 MB) runs fine on current UZDoom and needs no code fixes.

## Using it

* **Place in maps:** use DoomEdNums **30200–30281** (table below), or the `HCE_Random*` spawners for a random variant of a character.
* **Summon:** e.g. `summon HCE_EliteMajorPlasmaRifle`.
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
| `hce_grenadefreq` | 1.0 | Scales how often enemies throw grenades |
| `hce_burstpause` | 1.0 | Scales the pause between enemy bursts (1.5 = 50% longer, easier; 0.75 = more aggressive) |

Marines are on the human team and fight Covenant and Flood alongside the player. Their stray shots can still hit you, as in Halo.

## Replacing Doom's monsters

Each Doom monster becomes the Halo CE enemy with the closest role, toughness and threat.

If Doom monsters are left on a map, the console says how many and why at map start. That happens when `hce_keepdoommonsters` is on, or when another mod loaded after this pack replaces them first. Monsters with no loaded faction to become aren't counted. (Older builds used `hce_replacemonsters`, which your ini may still hold as `false`; it's ignored now.) The rank mix shifts with the skill level (easy = skills 1–2, normal = 3, hard = 4–5). Each spawn rolls its own pick.

Each spawn rolls from a weighted mix, so a room of Zombiemen isn't all Grunts. Types are listed most likely first, with the measured share at normal skill (600 rolls each). Easy skills favour the first entries; hard skills shift weight toward the later, stronger ones.

| Doom monster | Halo enemies (most → least likely, normal skill) |
|---|---|
| Zombieman | Minor plasma-pistol Grunt 30%, Major Grunt 18%, Minor needler Grunt 17%, Minor Jackal 16%, Major needler Grunt 11%, Minor Elite 6% |
| Shotgun Guy | Major Grunts (plasma pistol 22%, needler 20%), Minor Jackal 21%, Major Jackal 13%, Minor Elites 16%, Major Elite 6% |
| Chaingunner | Major Jackal 36%, Ultra Jackal 19%, Spec-Ops needler Grunt 17%, needler Elite 16%, ranged Elite 10% |
| Imp | Major Grunts 55%, Minor Jackal 15%, Minor needler Grunt 14%, Major Jackal 7%, Minor Elite 7% (Spec-Ops Grunts on hard) |
| Pinky | unarmed Flood Human 41% / Flood Elite 40%, shotgun Flood 18% |
| Spectre | Stealth Elite 44%, stealth Flood Elite 22%, Stealth Major 21%, sword Stealth Major 11% |
| Lost Soul | Flood infection form |
| Cacodemon | Sentinel, Shielded and Defensive Sentinels, Majors on harder skills |
| Hell Knight | Minor Elites 71%, Spec-Ops fuel-rod Grunt 9%, Ultra Jackal 9%, Major Elite 8% |
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

**Drops.** Halo enemies drop the weapon they carried as an HDE pickup (`Halo_PlasmaPistol`, `Halo_Needler`, `Halo_PlasmaRifle`, `Halo_FuelRod`, `Halo_MA5B`, …), so the replaced zombies' clip and shotgun drops still turn into ammo. HDE's pickup system applies its normal rules for enemy-dropped guns. Grunts and Elites with grenades left may also drop plasma grenades, and Marines frag grenades. Energy swords vanish as in CE, and Hunters and Sentinels drop nothing. Turn drops off with `hce_dropweapons 0`.

## What the AI does (all verified in-engine)

* **Teams:** Human, Covenant, Flood and Sentinel all fight each other the way they do in Halo, e.g. Flood vs Covenant vs Sentinels on 343 Guilty Spark. Same-team damage is ignored, and same-team explosive splash is halved.
* **Perception:** vision cone and range, hearing, and surprise. Grunts and Jackals react with the "surprise" animation when you appear close by.
* **Combat:** pattern burst fire (see Fire patterns), with first-burst delay, projectile error and target leading taken from each variant. Units strafe and reposition inside the variant's firing-range band.
* **Movement:**
  * Units steer with wall probes: each heading is scored for room ahead, and they drift away from walls beside them. Backing straight off is a last resort, and they only give ground when you're inside half their minimum range, diagonally and only where there's room behind.
  * If a strafe breaks line of sight it reverses. After 0.7 s without sight they move to find a firing position.
  * A stuck check (barely moved in half a second) sends them toward open space.
  * Shield-down cover is a sidestep toward the roomier side, not a backpedal.
  * After a fight they stay alert for 10 s with 360° awareness, so they notice you even if you're behind them.
* **Melee:** reach is measured from body edge to body edge: 36 units for most enemies, 40 for Flood, 56 for Hunters and 64 for the energy sword. A swing only connects within 14 units of slack and a 70° arc in front. (Halo's `melee_range` is a decision radius, not arm length; used directly it let Elites swing from about 150 units away.)
* **Plasma pistol overcharge:** Jackals only. Grunts with plasma pistols never overcharge.
* **Grenades:** ballistic throws; Covenant throw plasma grenades and humans throw frags. They're paced so they stay occasional:
  * At most one decision every 6–10 s, at 45% of Halo's throw chance.
  * A 12–20 s cooldown after a throw.
  * Nothing in the first 3–6 s after spotting you.
  * After anyone throws, nearby allies (within 640 units) hold theirs for 5 s.
  * The `hce_grenadefreq` CVar scales all of it (2 = twice as often, 0.5 = half).
  * The old pacing rolled every 2–3 s at 100% for Grunts.
* **Kamikaze Grunts (Halo 3):** Grunts carrying plasma grenades sometimes make a suicide run:
  * They play the jumping alert animation as the pull-out, with two live plasma grenades in their hands, and scream a kamikaze line.
  * They sprint at you in the panic run. On contact, or after 6 s, both grenades go off; that's lethal at point-blank.
  * Kill one mid-run and the grenades arm on their normal 2 s fuse, so back off.
  * Chance per second in combat: 0.4% Minor, 0.8% Major, 1.2% Spec-Ops, tripled below half health, and a 30% roll when their Elite leader dies.
  * One run at a time per squad, once per Grunt, and panic or berserk never interrupts it.
* **Low ceilings:** before every throw, the grenade's arc is simulated against the ceiling and ledge heights along its path. If the natural lob would hit, the thrower tries flatter, harder throws; if none clear, it holds the grenade and checks again a second later. The White Hunter's plasma-caster volleys follow the same rule. In a test room with a 96-unit ceiling, 21 of 30 grenades used to stick to the roof; now none do, and enemies still throw flatter grenades there.
* **Elites:** take cover when their shields drop below `shield_fraction_hide` and come back out at `emerge`. They evade and dive, and go **berserk** (roar, charge, melee) on heavy damage below 30% vitality or at close range. Grunts and Jackals **panic** when their Elite leader dies.
* **Jackals:** the energy shield blocks frontal fire within 55°, has its own HP and regenerates. Shoot around it, or break it. The shield's colour shows the rank, and it glows (brightmap in `gldefs.hce`):

  | Rank | Shield | Weapon | Body / shield HP | Class |
  |---|---|---|---|---|
  | Minor | Blue | Plasma pistol (with overcharge) | 60 / 200 | `HCE_JackalMinorPlasmaPistol` (30247) |
  | Major | Orange | Plasma rifle | 75 / 250 | `HCE_JackalMajorPlasmaRifle` (30248) |
  | Ultra | Pink | Needler | 100 / 350 | `HCE_JackalUltraNeedler` (30279) |

  Halo CE only has Minor and Major plasma-pistol Jackals. The Major is re-armed with the plasma rifle (rate of fire and bursts from the Minor plasma-rifle Elite). The Ultra is new, built on the Major body with the Major Grunt's needler timing. `HCE_RandomJackalMajor` spawns Majors or Ultras. The old `HCE_JackalMajorPlasmaPistol` class is gone; maps using DoomEdNum 30248 now get the plasma-rifle Major.
* **Hunters:** front armour reduces damage by 92% within 70°, so flank them. They fire the fuel-rod cannon at range and melee up close, and come as bonded pairs. Killing one sends its brother berserk.
* **Hunter colours:**

  | Hunter | Weapon | Class (DoomEdNum) |
  |---|---|---|
  | Blue (CE) | fuel-rod cannon | `HCE_Hunter` (30245), `HCE_HunterMajor` (30246) |
  | White | lobs plasma caster grenades on a ballistic arc (1–2 per volley); 30% of volleys are a charged 3-grenade cluster after an audible charge-up | `HCE_HunterWhite` (30280) |
  | Red | flamethrower stream from the arm cannon, short range (it closes in) | `HCE_HunterRed` (30281) |

  White and Red are new. They're the regular Hunter with the arm cannon's weapon swapped for HDE's plasma caster (the `PlasmaCasterProj` / `PlasmaCasterClusterProj` grenades) or the flamethrower, and the blue armour recoloured. Both come in bonded pairs, and `HCE_RandomHunter` includes them. The Red Hunter is lethal up close: in testing it burned a player from full to 1 HP in about 4 seconds.
* **Stuck Elites go berserk:** an Elite (or anything else that berserks: Flood combat forms, Hunters) stuck by a plasma grenade roars and charges whoever threw it, trying to take them down in the blast. If the thrower is unknown, it charges the nearest enemy in sight. Grunts and Jackals panic instead.
* **Stealth Elites:** active camo flickers when shot or firing.
* **Flood:**
  * Infection forms swarm, leap and nibble, then crawl to dead Marines and Elites. The feed animation raises the corpse as a Flood combat form.
  * Carriers waddle up and burst into 5–9 infection forms. Chain reactions happen.
  * Combat forms leap and fire whatever weapon they carry. Dead combat forms can be revived.
* **Sentinels:** hover at Halo's flying height and fire a hitscan beam.
* **Deaths:** directional (front/back/left/right) soft and hard death animations, airborne deaths, and Halo's flinch ("ping") animations by hit direction.
* **Thrown by explosions:** a kill from a grenade, rocket, fuel rod or any other explosion (anything dealing damage through `A_Explode`), from a Hunter's punch, or from a melee hit with the `Kick` damage type (HDE's player melee) flings the body away from the blast. Kicks throw at about 40% of a grenade's strength: in testing, a kicked Grunt flew about 30 units up versus 100 for a grenade. It flies in Halo's `airborne-dead` pose, facing the blast so it goes backwards, and plays `landing-dead` when it hits the ground.
  * **Physics:** the flight is real engine physics: gravity, wall collisions and ground friction, with most of the slide scrubbed off on impact.
  * **Strength:** the throw scales with the damage dealt and the body's mass, so lighter enemies fly further. In testing, a frag grenade threw a Grunt about 100 units up and over 150 units back. A Jackal went about 80 up, and an Elite about 60.
  * **Exceptions:** Hunters are too heavy to throw and fall in place. Infection forms and Carriers burst instead, and blasts too weak to throw a body just drop it.
  * **Mid-air deaths:** anything that dies in mid-air (a leaping Flood form, a Sentinel) also plays `landing-dead` when it lands.

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

Enemy fire uses HDE's own SNDINFO sounds, both the fire layer and its `/Bass` layer, so enemy guns sound like the player's.

* **Covenant:** plasma pistol, plasma rifle, needler and fuel rod (`Halo/Weapons/<Weapon>/Fire`).
* **Overcharge:** `PlasmaPistol/Charge/Start` during the wind-up, then `PlasmaPistol/Fire/Charged`.
* **Human:** `MA5B`, `Mag_MD6`, `Shotgun`, `Sniper` and `RocketLauncher`.
* **Looping weapons:** the flamethrower and Sentinel beam play start, loop and end sounds.

## Dialogue (optional `HaloCE_Enemies_Voices.pk3`)

The voice lines come from [Lewisk3/HaloDoomEnemies](https://github.com/Lewisk3/HaloDoomEnemies) (your fork REVonGit/HaloDoomEnemies-Proto): 443 lines in 9 voices. Each Grunt picks one of three personalities (Crazy, Whiley, Whimpy) and each Elite one of two (Dogmatic, Loose). Jackals and Hunters have one voice each. The Digsite add-on's Drinol and Blind Wolf use the two new creature sets:

* **Drinol:** Grave Injury plays for medium and heavy pain, Death XTR for explosive or hard deaths (`DeathHard`), and Sonic Roar for `Berserk`, including the boss's charge.
* **Blind Wolf:** Howl doubles as alert and taunt, and Bite plays for melee.

The fork's Acid Breath lines aren't used.

| Event | When |
|---|---|
| Alert | Spotting an enemy |
| Taunt | Every 6–14 s in combat, and after killing a non-player |
| KillPlayer | Killing the player |
| Pain / PainMed / PainHeavy | Hit for small, medium or heavy damage (Grunt and Jackal "Agonized", Elite "Pain Xtr") |
| OnFire | Hit by fire damage |
| GrenadeThrow / EnemyGrenade | Throwing a grenade; a hostile grenade lands nearby |
| Stuck | Stuck by an HDE plasma grenade (the `Pain.PlasmaStuck` state); Grunts and Jackals also panic |
| Kamikaze | Starting a kamikaze run, and while running (Whiley/Whimpy Grunts; Crazy uses its panic lines) |
| Panic, Flee, Regroup | Panic starts, while running, panic ends |
| LeaderDead | A Grunt or Jackal's Elite leader dies nearby |
| Berserk, Melee | Elites and Hunters going berserk; melee swings |
| Death / DeathHard | Dying; `DeathHard` for blast or hard kills, which falls back to Death for voices without one |

Lines don't pile up:

* One line plays at a time per enemy, with a cooldown.
* When one enemy speaks, same-team allies within 512 units stay quiet for a second.
* Death, panic, berserk, stuck and grenade warnings interrupt whatever that enemy was saying.

Without the voice pk3 the sound names don't exist, so enemies are silent and nothing errors. Voices are addressed as `HCE/<Voice>/<Event>`; add your own by defining those names in any SNDINFO and listing the voice in a class's `HaloDoom_EnemyBase.HCE_Voices` property.

## Damage scale

**The nerf (default on).** Enemies are cut to 60% health and 50% shields. Everything they shoot or throw does 40% damage (30% in the standalone packs, where the Doom player has no shield).

In a test squad (Elite Major, two Grunts, a Jackal) shooting at a player standing still:
* An HDE Spartan now lasts about 12 seconds instead of 2–3. Plasma bolts hit for 2–4 instead of 18–23.
* A vanilla Doom player lasts about 6 seconds.

How it's applied:
* **Plain projectiles:** the nerf is re-applied when the projectile hits. HDE recomputes projectile damage at impact, which also means the old `hce_enemydamage` never affected HDE projectiles.
* **Blasts:** grenades, rockets, fuel rods, needle supercombines and Plasma Caster shots are subclasses whose explosions are scaled.
* **Fuel-rod toxic cloud:** it pulses less often.
* **Plasma grenades:** a stuck one is still close to lethal (about 150 at the centre before HDE's Spartan shield).

Set the three `hce_nerf_*` CVars to 1 for the original Halo numbers. They are new names, so the defaults apply even if your config already saved `hce_enemydamage`.

Halo weapon damage is used almost 1:1. HDE's own guns already use Halo-like values (Assault Rifle 10 vs HDE 6, plasma rifle 12–14 vs 12, sniper 101 vs 128), and enemy health is Halo's body vitality, with shields given through HDE's `ShieldProcessor`. Halo's Marines really are fragile (12 body + 24 shield), so expect them to die fast, as in the game. Approximations where Halo uses physics or scripted damage: Hunter melee 80, Carrier burst 40, infection-form nibble.

## Digsite add-on (optional, private): `HaloCE_Enemies_Digsite.pk3`

More enemies from the [Digsite](https://github.com/digsite/h1) source assets, plus SPV3's Engineer, Blind Wolf and Thorn Beast, and Halo 2's Drones and Brutes. It needs only `HaloCE_Core.pk3`, for the API, handler and projectiles, and works with or without any faction pack:

```
uzdoom -file HDE_LocalDEV.pk3 HCE_EnemyAPI_LocalDEV.pk3 HaloCE_Core.pk3 HaloCE_Covenant.pk3 HaloCE_Enemies_Digsite.pk3 HaloCE_Enemies_Voices.pk3
```

| Class | What it is |
|---|---|
| `HCE_Drinol` | Map-placeable only (DoomEdNum 30400); it no longer replaces any Doom monster. Digsite's war beast (model, 76 animations and stats from its tags). Melee charger that swats and pounces with its `charging_jump`. In Halo it stands about 160 map units tall, so it is shrunk to 62% (99 tall, radius 34) to fit Doom corridors; health 320. Uses the new Drinol sounds from the voice pack: alert, melee, grave injury, death, extreme death, and sonic roar on the boss's charge. |
| `HCE_BossCyberdemonDrinol` | **Boss: replaces every Cyberdemon** while the add-on is loaded. A bigger Drinol (78% scale, 110 tall, radius 40, health 1800) with three attacks. Its swats (~65) are slower than the small Drinol's. Its **charge** is a 22-speed stampede that steers a few degrees per tic, so you can side-step it; a hit does ~55 and bowls you over, and running into a wall staggers it. When it lands from a pounce it **slams** out a 260-unit shockwave that hurts and knocks back its enemies but spares its allies; jumping avoids it. It maps back to `Cyberdemon` (`CheckReplacee`), so boss-death map specials still fire. |
| `HCE_Brute{Minor,Major,Captain,HonorGuard,Chieftain}…` | **Halo 2's Brutes**, ripped from MCC's `08b_deltacontrol.map` (voices from `08a_deltacliffs.map`): one 48-bone model with every rank's armour, 73 animations (including Tartarus's gravity-hammer stance), real textures, both voices (bloodthirsty and cruel) and their footsteps, thumps and body falls.<br>• **Ranks and loadouts** (looks from Halo 2's model variants, health from the rank tags; all hold their guns in the rifle stance):<br>&nbsp;&nbsp;– **Minor**: 175 health, bare shoulders, olive fur. Carries the **CE plasma rifle** (`HCE_BruteMinorPlasmaRifle`) or the **CE assault rifle** (`HCE_BruteMinorAssaultRifle`).<br>&nbsp;&nbsp;– **Major**: 150 health, shoulder armour, reddish fur. Carries the **Spiker** (`HCE_BruteMajorSpiker`), which fires HDE's own spikes in automatic bursts and drops HDE's Spiker, or the **CE shotgun** (`HCE_BruteMajorShotgun`), 15 pellets a shot.<br>&nbsp;&nbsp;– **Captain**: 200 health, shoulder armour and the flag pack, grey fur. Carries the CE plasma rifle or the CE shotgun.<br>&nbsp;&nbsp;– **Honor Guard**: 150 health (Halo 2's Honor Guard inherits the Major's stats), the red ceremonial armour. Carries the CE plasma rifle or the CE assault rifle.<br>&nbsp;&nbsp;Each gun is the real model in the Brute's hand: the CE weapons and the Spiker (a community CE port of Halo 3's). Each drops its HDE pickup.<br>• **Brute Chieftain** (`HCE_BruteChieftainGravityHammer`), a custom rank:<br>&nbsp;&nbsp;– **Look:** Tartarus's crested white mohawk and helmet, his grey fur and gold armour, and the elite-skull trophy pauldron.<br>&nbsp;&nbsp;– **Weapon and animations:** Halo 2's gravity hammer, held two-handed with Tartarus's own hammer animations (idles, moves, three swings, two side smashes, leap, berserk hammer run and swings).<br>&nbsp;&nbsp;– **Stats:** 350 health and a 150-point shield (Tartarus's 1000-point overshield, cut down so it can be broken). It is melee only, with no grenades.<br>&nbsp;&nbsp;– **Attacks:** it leaps at targets 150–400 units away at Tartarus's 50% leap chance. Every hammer swing (about 70) and every leap landing sets off a **gravity shockwave**: HDE's hammer blast effect, 10–35 damage within 150 units, knocking things back and sparing other Covenant. It keeps the hammer when berserk and drops HDE's gravity hammer when killed.<br>• **Combat:** strafing, dives and evades, plasma grenades (10% a second, 3–20 unit range, 6 s apart, carrying 1–2, all from the tag), heavy melee (about 35), cheer, taunt and point animations.<br>• **Berserk:** when badly hurt, or when its pack is wiped out (the last Brute nearby always goes, others 35% of the time), it roars and thumps its chest, **throws its gun away** (the pickup lands nearby), then charges on all fours with five swings and two tackles.<br>• **Helmets:** a headshot knocks a Minor's, Major's or Captain's helmet off; it bounces away as debris. Honor Guard and Chieftain helmets stay on.<br>Scaled to 80% (68 tall, radius 26) so they fit Doom doors. DoomEdNums 30422–30430, `HCE_RandomBrute` 30431. |
| `HCE_DronePlasmaPistol` | **Halo 2's Drone** (Yanme'e), ripped from MCC's `01b_spacestation.map` (Cairo Station): model, 32-bone skeleton, 36 animations (flight idle and four-way flight, wall perching, take-off/landing, fire, flinches, falling deaths) its real textures (from MCC's `textures.dat`) and 219 sounds: 149 dialogue lines from `sounds_en.dat`, plus its wing buzz, wing whooshes, wall-cling, claw and body-fall effects from `sounds_neutral.dat` (Halo 2 MCC stores them as raw Opus; the tools wrap them as Ogg). It holds a plasma pistol in its claw, has 30 health and no shield (from its Halo 2 character tag), and is 48 tall with radius 22. Behaviour:<br>• **Darting flight:** swarm-style zig-zags above its target at changing heights, firing plasma pistol bursts.<br>• **Dodges:** when hit there's a 50% chance it darts sideways, at most every 4 s (its tag's evasion values).<br>• **Wall perching:** it flies to a nearby wall and clings with its back to it, firing from there (3–6 s in combat, 8–20 s when idle), and leaves early if you get within 96 units.<br>• **Swarm scatter:** when a drone dies, others within 400 units scatter in panic.<br>• **Falling death:** it falls out of the air and lands dead.<br>• **Sounds:** its wings buzz while it flies, it whooshes on dodges and darts, clicks when it grabs a wall, and thuds when it lands dead.<br>It replaces **Lost Souls** (60/65/70% by difficulty) and drops a plasma pistol.DoomEdNum 30420 (`HCE_RandomDrone` 30421). |
| `HCE_Engineer` | SPV3's Engineer, extracted from its b30 map (model, texture, 25 animations, health, dialogue). **Replaces every Pain Elemental** while the add-on is loaded; without it, Pain Elementals become Flood Carriers if the Flood pack is loaded. It carries **no weapon and never fights**: it treats nothing as an enemy, even whoever shoots it, and just drifts around, sometimes pausing in mid-air. It's an environmental hazard rather than a combatant. It's still tough to pop (150 body plus a 200 recharging shield), and **when it dies it bursts and sprays 4–6 charged Plasma Caster shots** (HDE's `PlasmaCasterClusterProj`). Each one sticks to what it hits, arms for two seconds, then explodes and throws two mini-bolts, so don't kill it next to yourself. Its dialogue (idle, surprise, pain) and explosion sound come from the map. 70 tall, radius 26 (1.25× scale). Was `HCE_EngineerMajorPlasmaPistol`; same DoomEdNum, 30418. |
| `HCE_ThornBeast` | SPV3's Thorn Beast from the same a30 map: a slow, tough melee brute in the Hell Knight mix. It has health 350 and heavy swipes of about 45, and walks at speed 6 (its animation stride is 4.3). Shrunk to 70% (67 tall, radius 36). It plays its own sounds from the map: idle growls as alert and taunt, melee roars, minor and major pain, death, and footsteps while it walks. |
| `HCE_Elite{Minor,Major,Specops,Commander}PulseCarbine` | The same Elite ranks with a **blue Pulse Carbine** (the CMT carbine re-tinted blue, with blue lights) that fires like HDE's Pulse Carbine: bursts of 3–5 slow, accelerating plasma bolts (8 base damage each) that home on the Elite's target. They never re-target onto allies. They drop HDE's Pulse Carbine. |
| `HCE_BlindWolf` | SPV3's Blind Wolf, extracted from its a30 map (model, texture, 18 animations, stats). It's a Pinky-style melee charger, health 90: it runs you down, bites for about 22, and pounces from up to 300 units using its leap-start, leap-airborne and leap-melee animations. It uses the new Blind Wolf sounds (alert, howl, bite, pain, death, idle) from your HaloDoomEnemies fork. |
| `HCE_SlugManParticleBeam` | Slug Man sniper with Digsite's own Particle Beam Rifle (the 99_mac model and texture the Slug Man's `particle beam` variant was built around; its NPC projectile flies at 350 WU/s, so it is effectively hitscan here too). Every shot is telegraphed by a one-second purple aiming laser and the beam-rifle charge sound, then one hitscan beam (90 × the variant's 0.5 damage modifier = 45). Keeps 400–3200 units away and crouches to fire. |
| `HCE_SlugManPlasmaPistol` | Slug Man with a plasma pistol. |
| `HCE_Elite{Minor,Major,Specops,Commander}PlasmaCarbine` | Elites with **CMT's Covenant carbine** (model and textures from the CMT tags: purple carapace, glowing status lights and ammo read-out) in a real two-handed **rifle stance**. Semi-auto pairs and triples of HDE's green carbine rounds (15 base damage), with longer combat ranges than the plasma-rifle Elites. They drop HDE's Carbine. |

* **Rifle stance.** The animations come from the CE-rig Elite graph you supplied (`elite.model_animations`): stand/crouch/alert idles, moves and turns, dives, evades, berserk, both rifle melees, surprise, signal and land. Its uncompressed frames decode directly. CMT's carbine sits on the `right hand elite` marker, and the support hand lands where the set already places it. A two-bone IK step keeps the support hand on the fore-grip during strides. The graph has no rifle fire overlay, so firing uses a short synthetic recoil kick. Actions the graph lacks (airborne, hard landing, throw, warn, alert move) use the Elite's pistol body, with the support hand solved onto the carbine. The same graph also has cannon (fuel rod) and flamethrower sets that aren't used yet.
* **Slug Man.** Model, 187 animations (full pistol and rifle sets) and stats come from the Digsite JMS/JMA sources and tags. Its hand marker points the barrel down z instead of x, so held weapons are rotated to match. The voice lines are its own Digsite dialogue (Xbox ADPCM decoded to ogg): sighted, taunt, pain, death, retreat, evade and communication.
* **Spawns.** Each listed Doom monster has a chance to become a Digsite enemy (easy / normal / hard). Otherwise the main pack's mix applies. `hce_digsite_spawns` scales the chances (0 turns them off), and `hce_keepdoommonsters` is respected.

| Doom monster | Chance | Picks |
|---|---|---|
| ZombieMan | 6 / 8 / 10% | plasma-pistol Slug Man |
| ShotgunGuy, DoomImp | 5–10% | plasma-pistol Slug Man, Minor carbine Elite |
| ChaingunGuy | 15 / 20 / 25% | beam-rifle Slug Man, Minor/Major carbine Elites, Minor pulse-carbine Elite |
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

DoomEdNums 30400–30417, in release order: `HCE_Drinol`, the four carbine Elites, both Slug Men, `HCE_Random{Drinol,EliteRifle,SlugMan}` (30400–30409); `HCE_BlindWolf` (30410) and `HCE_RandomBlindWolf` (30411); `HCE_ThornBeast` (30412) and `HCE_RandomThornBeast` (30413); the four pulse-carbine Elites (30414–30417). `HCE_RandomEliteRifle` now includes the pulse-carbine Elites. `HCE_Engineer` is 30418 and `HCE_RandomEngineer` is 30419; `HCE_DronePlasmaPistol` is 30420 and `HCE_RandomDrone` 30421; the Brutes are 30422–30430 (the Chieftain is 30430) and `HCE_RandomBrute` 30431.

**License: keep this add-on private.** Digsite's README says its content is not open source and is licensed only for MCC mod projects. The Elites' carbine is CMT's and private too. Sources are listed in the pk3's `CREDITS.txt`.

## Standalone packs (no HaloDoom Evolved needed)

`HaloCE_Standalone_*.pk3` are the same enemies with every HaloDoom Evolved dependency built in. They run on plain UZDoom/GZDoom with any IWAD and next to other gameplay, weapon or map mods. You don't need HDE or `HCE_EnemyAPI_LocalDEV.pk3`.

| Pack | Contents | Size |
|---|---|---|
| `HaloCE_Standalone_Core.pk3` | **required**: the enemy AI, the Doom-monster replacement handler, and the projectiles, grenades, explosions, shields, sounds, sprites and models taken from HDE | 14.3 MB |
| `HaloCE_Standalone_Covenant.pk3` | Grunts, Jackals, Elites, Hunters | 14.1 MB |
| `HaloCE_Standalone_Flood.pk3` | infection, carrier and combat forms | 10.3 MB |
| `HaloCE_Standalone_Sentinels.pk3` | Sentinels | 1.3 MB |
| `HaloCE_Standalone_Marines.pk3` | Marines (allies) | 5.3 MB |
| `HaloCE_Standalone_Digsite.pk3` | the Digsite add-on: Slug Men, carbine Elites, SPV3 creatures, Drones, Brutes and the Chieftain | 29.7 MB |

**Load order:**
1. `HaloCE_Standalone_Core.pk3`
2. any of the faction packs and the Digsite pack
3. optionally `HaloCE_Enemies_Voices.pk3` (unchanged; it never needed HDE)
4. other mods before or after these

Don't load these together with the regular HDE packs: they define the same enemies.

**What changed from the HDE versions:**
* **Projectiles:** HDE's projectiles are rebuilt as small self-contained classes (`hces_lib.zsc`). They use HDE's own models and sprites:
  * tracer bullets
  * plasma bolts with their glowing cores
  * overcharged plasma that homes and splashes
  * accelerating, homing Pulse Carbine bolts
  * needles that stick, shatter after a second, and supercombine at 7 for a big pink blast
  * arcing Spiker spikes
  * fuel-rod plasma with a green blast
  * accelerating rockets
  * flamethrower flames
  * bouncing frag grenades and sticky plasma grenades
  * Plasma Caster grenades and clusters
  * the gravity-hammer blast
* **Shields:** Elites and other shielded enemies use HDE's shield logic, ported unchanged: it absorbs damage, breaks with a sound, and regenerates.
* **Damage:**
  * Enemy shots do Halo's damage numbers as plain Doom damage, scaled by `hce_nerf_projectiles` (default 0.3 here) and `hce_enemydamage`.
  * Enemy health and shields follow `hce_nerf_health` and `hce_nerf_shields`.
  * Explosions and flames hurt the player and other factions but not the shooter's own side.
  * Overlapping flames don't stack; a victim burns for at most about 23 a second.
* **Drops: a loot director, not one fixed item per enemy.** Every kill earns loot points: a Grunt about 1, an Elite about 1.7, a Brute about 3, a Hunter or Chieftain about 6. The points are spent on whatever the neediest living player is shortest of right now:
  * **Health** when hurt: health bonuses, stimpacks, and medikits from big kills.
  * **Armor:** armor bonuses as a steady trickle, and sometimes a green armor from a big kill when armor is low.
  * **Ammo** for the weapons the player actually owns, emptiest first, with the gun in hand counted double. The ammo type comes from the weapon itself, so weapon mods get their own ammo.

  Supplies that have dropped but haven't been picked up yet count toward need for a few seconds, so a burst of kills doesn't bury a hurt player in stimpacks.

  **Weapons** drop themed to what the enemy carried:

  | Enemy weapon | Doom weapon |
  |---|---|
  | rifles, pistols, Spikers | chaingun |
  | shotguns | shotgun, then super shotgun |
  | rockets, fuel rods, Plasma Casters | rocket launcher |
  | Covenant energy weapons | shotgun or chaingun first, later the plasma rifle |
  | bosses | BFG |

  * **Order:** shotgun and chaingun come first; the rocket launcher and super shotgun follow; the plasma rifle needs both basics; the BFG needs a big gun already.
  * **Pity counter:** a missing weapon gets steadily more likely, so nobody goes long without one.
  * **Pacing:** at most one weapon every 20 seconds.
  * **Other mods:** all drops are vanilla Doom item classes spawned with replacement, so gameplay and weapon mods drop their own versions. In games without Doom's items (Heretic, Hexen), nothing drops.
  * **Settings:**
    * `hces_loot`: 0 = off, 1 = balanced (default), 2 = generous.
    * `hces_loot_weapons`: true by default; set it false to turn off weapon drops.
* **No name clashes:** everything imported has its own names, so nothing collides with HDE or other mods:
  * `HCES_` classes
  * `HCES/` sounds
  * `HZ**` sprites
  * `models/hces`
  * `HCES_EnemyBase` in place of `HaloDoom_EnemyBase`

  Credits for the imported material are in `CREDITS_STANDALONE.txt` inside the core pack.
* **Merging:** `merge_hce_packs.py` and `update_merged_pack.py` work on these packs too. Run with no arguments, they use the standalone set when that's what is in the folder.

## Gore (Nash's Gore Mod)

The enemies work with [Nash's Gore Mod](https://github.com/poperigby/nashgore) (NashGore). Load `nashgore.pk3` last, after the HDE or standalone packs. Without it, Doom's normal blood is used, in the same colours.

**Blood colours** follow each species' blood from Halopedia's "Blood" article (Halo CE colours where the games differ). They are set as each enemy's `BloodColor`, so NashGore's sprays, floor splats, wall decals, corpse pools, footprints and gibs all take the race's colour:

| Species | Blood |
|---|---|
| Elites (Sangheili) | dark blue/purple |
| Jackals (Kig-Yar) | dark blue/purple |
| Grunts (Unggoy) | light blue / teal |
| Hunters (Mgalekgolo) | bright orange |
| Brutes (Jiralhanae, Halo 2) | dark navy blue / black |
| Drones (Yanme'e) | white, slight green tint |
| Engineers (Huragok) | reddish pink |
| Flood (all forms) | brownish green |
| Marines | red |
| Sentinels | none (machines) |
| Slug Men | yellow-green |
| Drinol, Blind Wolf, Thorn Beast | dark reds |

**Gibbing:**
* **When:** only an overkill gibs, as with Doom's monsters: damage that takes an enemy past its gib health (minus its spawn health) sends it to a separate `XDeath` state. Ordinary kills leave the animated corpse.
* **With NashGore:** its gibs replace the body, and the model is hidden.
* **Without NashGore:** the body stays and sprays the race's blood.
* **No revivals:** Flood infection forms can't reanimate a gibbed body, and feigning Elites stay down.

**BLUDTYPE:** none is needed. The enemies, HDE's projectiles and the standalone projectiles all spawn Doom's standard `Blood`, which NashGore replaces on its own. If another mod gives these enemies a custom blood class, list it in a `BLUDTYPE.txt` as described in [nashgore_bludtype](https://github.com/nashmuhandes/nashgore_bludtype).

## Not included / known limits

* Marines, Flood and Sentinels have no dialogue (HaloDoomEnemies has no lines for them).
* No vehicles, turrets, dropships or scripted AI (encounters, squads, firing points). Units pick positions with local steering instead of Halo's firing-point graph.
* Only the 14 combat characters are included: no Keyes, Cortana, 343 Guilty Spark or crew.

## Legal

The models, textures and animations are extracted from Halo CE, and the voice lines are Halo audio taken from Lewisk3/HaloDoomEnemies; all of it belongs to Microsoft / Bungie. Use the faction packs and `HaloCE_Enemies_Voices.pk3` privately: **keep them out of public releases** (including UZHalo Shell / HDE Core releases). `HCE_EnemyAPI_LocalDEV.pk3` and `HaloCE_Core.pk3` contain no Halo assets (only ZScript, CVARs and sound aliases onto HDE sounds). Ship it with `enemies_base.zsc` and the extraction tools (`halo_ce_enemy_tools.zip`) instead, so users can generate the pk3 from their own copy of the game.

## Files

* `HaloCE_Core.pk3`: shared projectiles, the replacement handler and CVARs (required, no Halo assets).
* `HaloCE_Covenant.pk3`, `HaloCE_Flood.pk3`, `HaloCE_Sentinels.pk3`, `HaloCE_Marines.pk3`: the faction packs (models with held weapons, animations, skins, enemy classes).
* `HaloCE_Enemies_Voices.pk3`: optional dialogue (14 MB), loaded after the enemy pack.
* `HCE_EnemyAPI_LocalDEV.pk3`: the enemy API addon for HDE Local_DEV.
* `enemies_base.zsc`: the extended enemy API source (the file the addon carries).
* `halo_ce_enemy_tools.zip`: the extraction and generation scripts (Python 3, numpy, Pillow), plus the addon source tree. They rebuild the pk3 byte-for-byte from the `.map` files.
* `preview.png`: the lineup in UZDoom.
* `HaloCE_Enemies_Digsite.pk3`: the private Digsite/SPV3 add-on (Drinol and its boss, Slug Men, carbine and pulse-carbine Elites, Engineer, Blind Wolf, Thorn Beast). `digsite_preview.png` shows some of them.

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
| 30248 | `HCE_JackalMajorPlasmaRifle` |
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
| 30279 | `HCE_JackalUltraNeedler` |
| 30280 | `HCE_HunterWhite` |
| 30281 | `HCE_HunterRed` |
