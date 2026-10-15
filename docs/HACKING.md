# Forking and editing the Halo CE enemy packs

A map of where things live and what to edit for the changes people usually want. The player-facing manual is
[PACK_README.md](PACK_README.md); the pipeline that builds the packs is described in
[../generator/README.md](../generator/README.md). This page is the bridge between them.

## The two layers

```
packs/HaloCE_<Pack>/       what players load: each folder is exactly one pk3 (python build.py zips them)
generator/                 what made packs/: Python that reads the Halo maps and writes the ZScript, models and skins
```

Everything in `packs/` is the **output** of `generator/`. You can edit either:

* **Edit `packs/` directly** when you want a quick fork, don't have the Halo maps, or only touch ZScript. The
  generated files say so in their first lines; your edit survives until someone re-runs the generator.
* **Edit `generator/`** when the change should last (it is regenerated into every pack) or touches models and
  textures. You need the Halo CE maps and the other sources the extractors read (`generator/README.md` lists the
  environment variables that point at them).

Most gameplay changes need no generator at all, and many need no code: see the first two rows of the table.

## Where to change what

| I want to ... | Go to |
|---|---|
| Tune a behaviour everyone has (hearing range, how many hunt you, encounter odds, grenade pacing, health and spread nerfs) | A CVar: `packs/HaloCE_Covenant/cvarinfo.txt` lists them with a comment each; set it in the console or the options menu (`menudef.hce`). No rebuild. |
| Make a tougher / faster / re-armed version of an enemy, or have it replace a Doom monster some of the time | An `HCEVARS` lump in your own pk3: no code at all. PACK_README.md, "Your own variants". |
| Change which Halo enemies replace which Doom monsters, and how often | `packs/HaloCE_Covenant/ZScript/HaloCE/hce_handler.zsc`, the `RULES` table at the top of `HCE_ReplaceHandler` ("Class*weight" lists per skill tier; the comment above it explains the format). The Digsite enemies have their own table in `dig_handler.zsc`. Boss stand-ins: `BOSSES` in the same file. |
| Change one enemy's stats (health, shield, gun, ranges, speed, melee, flags) | Its class in `packs/HaloCE_<Pack>/ZScript/HaloCE/hce_<pack>.zsc`: every property is explained in the banner at the top of that file. For a lasting change, the same numbers come from `generator/build_pack.py`: `CHAR_OVERRIDES` (per body), the variant's `_ov` dict (per class), the `WEAPONS` / `PATTERNS` / `FIRE_SOUNDS` / `DROP_WEAPON` tables (per gun), `VOICES`, `BLOOD`, `HEAD_CLEAR`. |
| Recolour a rank, change a shield tint, the armour shine, which Halo 2 kit a rank wears | `generator/variants.py`: every table has a comment saying what it drives and which `build_pack.py` function reads it. Rebuild with `python3 build_pack.py`. |
| Change how the AI behaves (cover, searching, squads, grenades, dodging, melee, pursuit, dialogue timing ...) | `packs/HaloCE_Covenant/ZScript/BaseAI/enemies_base.zsc` (`generator/addons/localdev/ZScript/BaseAI/enemies_base.zsc` in the generator): one class, `HaloDoom_EnemyBase`, with a map of its sections and its override points at the top. Every function has a comment; tunables say "to change X, edit ...". |
| Give one enemy special behaviour | Override a `virtual` method of `HaloDoom_EnemyBase` in that enemy's class (or in an HCEVARS variant's `code`). Worked examples: `generator/templates/zscript/*.zs`, which `build_pack.py` pastes into the Knight, Enforcer, Constructor, Drone, Engineer, beam-rifle and stanchion classes (`WEAPON_CODE`, `BASE_CODE`, `TYPE_CODE`). |
| Add a new enemy from a Halo CE / MCC map | `generator/extract_spv3.py` (`MAPS`: which map, which biped, the pack id) extracts the model, animations and stats; then an `add_*` block in `build_pack.py` makes its variants (`add_mercury` is the most recent and the model to copy: body, variants, weapons, overrides, bestiary group, pinned DoomEdNums). Then lore in `generator/pack/bestiary_lore.txt`, an icon (`udb_icons.py --only <Name>`), credits in `generator/digsite_src/CREDITS.txt` and the manual. |
| Add a gun the Marines can carry | `generator/marine_arsenal.py` (`ARSENAL`: the model source) and `build_pack.py`'s `MARINE_ARSENAL` (its stance, ranges, pellets, the HDE weapon it drops). |
| Add or change a voice set | `generator/voice_extra/<Set>/<Category> N.ogg` (the categories are `build_voices.py`'s `CAT`; a set missing one borrows another through `FALLBACK`), then name the set in `build_pack.py`'s `VOICES` for the character. `extract_marine_voices.py` shows how to pull lines out of a map. |
| Change what is in the bestiary, or its lore | `generator/pack/bestiary_lore.txt` (one `[Key]` per entry; a class takes the longest key found in its name, else its character's), `BESTIARY_GROUP` / `BESTIARY_RANK_GROUP` / `bestiary_title` in `build_pack.py` for the grouping and names. Keep the lore in-universe. |
| Change the Marines' squad orders or the Chief's lines | `hce_handler.zsc` (`HCE_SpawnAllHandler.SquadOrder`, `keyconf.txt` for the keys) and `generator/chief_commands/`. |
| Add a map editor icon for a new class | `generator/udb_icons.py --missing` photographs every class without one (needs the engine and the built packs). |

## The build and test loop (generator side)

```
cd generator
python3 build_pack.py          # pack/: the main pack (ZScript, MODELDEF, skins, projectiles, bestiary, DoomEdNums)
python3 build_digsite.py       # addons/digsite: the Digsite / Halo 2 enemies
python3 split_factions.py      # pack/ -> factions/<core|covenant|flood|sentinels|marines>: the faction packs
python3 build_standalone.py    # standalone/: the packs that need no HaloDoom Evolved
```

Then zip each folder (or let `build.py` at the repository root do it from `packs/`). Loading the result once in
UZDoom with HaloDoom Evolved and watching the console is the minimum test: a ZScript error names its file and line.
`generator/README.md` has the full order of the extractors for a from-scratch build.

Rules that keep forks compatible:

* **DoomEdNums never change once shipped.** `generator/ednum_pins.json` pins every released class; new classes take
  the next free numbers. Don't renumber: maps place these.
* **The HDE API half of `enemies_base.zsc` keeps its names and signatures.** HaloDoom Evolved's own enemies compile
  against it, and `build_standalone.py` turns the file into the standalone `hces_api.zsc`.
* **Comment-only changes are safe; check them.** A quick way to be sure an edit changed only comments: strip `//`
  comments from the old and new file and diff what is left.
* **Credit the authors** of anything you bring in, in `generator/digsite_src/CREDITS.txt` (shipped as each pack's
  `CREDITS.txt`) and the manual's Credits section. Digsite content may not leave MCC mod projects.

## Reading the generated ZScript

`hce_<pack>.zsc` is big (one class per rank and gun) but regular. Each enemy is:

```
// HCE_EliteMajorPlasmaRifle: Halo variant "characters\elite\elite major\elite major plasma rifle", plasma rifle, ...
class HCE_EliteMajorPlasmaRifle : HCE_EliteBase
{
    //$Category ...            editor keys for Ultimate Doom Builder
    Default { ... }            the stats, one HaloDoom_EnemyBase property a line (the banner at the top of the file
                               explains each one and its units)
    HCE_AnimName / HCE_AnimTics / HCE_AnimMove   the animation table: the AI asks for a kind (HCE_A_MOVE_F ...)
                               and gets an IQM clip, its length, and the ground it covers
    ... extra code             anything the generator added for this class (a template from templates/zscript/)
}
```

`HCE_<Character>Base` above the variants holds what the body shares: size, blood and gore, the skins it rolls and the
cosmetics (faces, kit). `HCE_Random<Character>` at the end of each pack picks a random variant, and `HCE_Boss*`
classes stand in for Doom's bosses so map triggers still fire.
