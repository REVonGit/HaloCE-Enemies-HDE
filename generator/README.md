# Halo CE enemy tools

**Layout:** the pipeline scripts you run sit in this folder; the format readers and writers they share (Xbox/MCC map readers, tag layouts, model/animation/bitmap/sound codecs, the IQM writer, `hce_paths.py`) are in `lib/`, which every script puts on its import path. The hand-written ZScript sources are `addons/localdev/` (enemy API), `pack/` (core), `digsite_src/` (Digsite add-on) and `standalone/` (standalone library and loot). Merging pk3s is done by the repository's `build.py` and `tools/merge_hce_packs.py`.

These scripts regenerate `HaloCE_Enemies.pk3` from your own Halo CE **Xbox** campaign maps (a10, a30, a50, b30, b40, c10, c20, c40, d20, d40).

Requirements: Python 3.10+, numpy, Pillow, and a checkout of https://github.com/cybersecurity/halo-ce-universal. Its decomp headers provide every tag struct layout.

```
export HCE_HALO_SRC=/path/to/halo-ce-universal/source
export HCE_MAPS=/path/to/maps        # folder holding a10.map ... d40.map
export HCE_OUT=./out HCE_PACK=./pack # pack/ already holds the hand-written ZScript/CVARINFO/SNDINFO
python3 extract_ai.py      # actv/actr/bipd/coll/weap tags                          -> $HCE_OUT/ai_data.json
python3 extract_weapons.py # third-person weapon models + textures                 -> $HCE_OUT/weapons
python3 extract_chars.py   # IQM models + animations + skins + held weapons         -> $HCE_OUT/models
HCE_SPV3_B40=/path/to/b40_1.map HCE_SPV3_BITMAPS=/path/to/bitmaps.map python3 gore_kit.py   # dismemberment: limb surfaces, stumps, gibs (in place)
python3 blood_kit.py       # blood on the body: per-character blood-splatter overlays (after gore_kit.py)
HCE_DIGSITE=/path/to/h1 python3 marine_arsenal.py && python3 marine_arsenal.py overlays   # the Marines' guns (after blood_kit.py)
python3 build_pack.py      # ZScript classes, MODELDEF, baked variant skins, MAPINFO -> $HCE_PACK
python3 split_factions.py  # pack/ -> factions/{core,covenant,flood,sentinels,marines}
for f in core covenant flood sentinels marines; do (cd factions/$f && zip -r9 ../../HaloCE_$f.pk3 .); done   # rename to HaloCE_Core/Covenant/Flood/Sentinels/Marines.pk3
```

| File | Role |
|---|---|
| `lib/halomap.py` | Xbox cache-file reader (zlib, tag index) |
| `lib/clayout.py` | i386 struct layout calculator over the decomp headers |
| `lib/tags.py` | Typed tag access (`Tag['path.to.field']`, blocks) |
| `lib/halomodel.py` | `mode` geometry (compressed verts, strips) and `antr` animations (raw + compressed, overlays, root motion) |
| `lib/iqm.py` | IQM v2 writer |
| `lib/bitmaps.py`, `lib/render.py` | Xbox bitmap decoding (DXT/swizzled) and shader lookup |
| `extract_weapons.py` | Weapon `mod2` geometry; sword blade and needles get solid glow textures |
| `extract_chars.py` | Character list, LOD/permutation pick, overlay baking, weapons bound to the hand marker, surfaces merged per material (UZDoom max 32) |
| `extract_ai.py` | AI and stat dump |
| `build_pack.py` | Pack generator: weapon table, animation mapping, per-type AI flags; bakes the variant skins, with a stylised armour shine on Elites and Grunts (`SHINE`: the model's normals rasterised into texture space, lit by a fixed sky and masked by the multipurpose map's specular channel, standing in for Halo CE's cube-map reflection) |
| `build_standalone.py` | Builds the `HaloCE_Standalone_*.pk3` set from the built faction packs and add-on. It needs HDE Local_DEV (`HCE_HDE_PK3`: its pk3 or an unpacked folder) to copy sounds, sprites and models from. `standalone/hces_lib.zsc` holds the HDE-derived projectiles, grenades, effects and shields. |
| `lib/h2map.py`, `lib/h2anim.py`, `lib/h2opus.py` | Halo 2 MCC readers: chunk-compressed cache, tag index, render models, animation codecs (ported from TagTool), sound gestalt and the Opus audio in `sounds_*.dat` |
| `extract_h2.py` | Halo 2 Drone -> IQM + JSON. Set `HCE_H2_MAP` to `01b_spacestation.map`, `HCE_H2_TEXTURES` to MCC's `textures.dat` (real skins) and `HCE_H2_SOUNDS` to the `h2_maps_win64_dx11` folder (`sounds_en.dat` dialogue, `sounds_neutral.dat` effects) |
| `extract_h2_brute.py` | Halo 2 Brutes from `08b_deltacontrol.map` (`HCE_H2_MAP08B` / `HCE_H2_CACHE08B`): model with every rank's armour plus Tartarus's pieces, the regular and gravity-hammer animations, the CE plasma rifle / assault rifle / shotgun, the Spiker and the H2 gravity hammer in the hand, helmet debris; voices and effects come from `08a_deltacliffs.map` (`HCE_H2_MAP08`) (same `HCE_H2_TEXTURES` / `HCE_H2_SOUNDS` settings). Run `python3 cmt_weapon.py spiker <Spiker folder>` first to convert the Spiker |
| `marine_arsenal.py` | The Marine arsenal: HaloDoom Evolved's human weapons as Halo models, picked per gun from Halo CE (`out/weapons`), Halo 2 (`01b_spacestation.map`: battle rifle, SMG, the machine-gun turret's gun without its tripod; `08a_deltacliffs.map`: rocket launcher; `HCE_H2_MAP` / `HCE_H2_MAP08`, `HCE_H2_TEXTURES`) and the Digsite prototypes (`HCE_DIGSITE`: JMS + TIFF). Fix-ups per gun: the Macworld 2000 pistol's half model mirrored, the turret gun turned forward and levelled, CE's flamethrower laid nozzle-forward, the MA37 repainted Reach-style, and the grenade launcher kitbashed (the Macworld 1999 shotgun, CE's sniper scope and magazine, a lengthened barrel, one UNSC finish for all of it). `overlays` then writes `<Char>_w_<gun>.iqm` for both Marine bodies: the gun on the hand bone of the body's own skeleton, placed with the exact transform Halo CE's assault rifle has there, listed in the body's JSON (`arsenal`). `build_pack.py` (`MARINE_ARSENAL`) makes a class per gun per body, attaches the gun as model 6, and adds Sergeant Johnson (Stanchion, Magnum up close) |
| `split_factions.py` | Splits the generated tree into the shared core (no Halo assets) and one pack per faction |
| `addons/localdev/ZScript/BaseAI/enemies_base.zsc` | Extended HaloDoom_EnemyBase (hand-written): the AI, grenade dodging, jumping, flinches, gore |
| `pack/ZScript/HaloCE/hce_core.zsc` | Hand-written core code that needs ZScript 4.15 bone queries: the Jackal shield entity riding the arm's `frame shield` node |
| `extract_h2_jackal.py` | Halo 2 Jackal from `08a_deltacliffs.map` (`HCE_H2_MAP08` / `HCE_H2_SOUNDS` / `HCE_H2_TEXTURES`): model, skins and change-colour masks, arm shield, pistol and rifle stances with fire overlays, deaths; the CE plasma rifle, the Spiker and Halo 2's beam rifle in the gun hand; the shield-pop sound. `build_digsite.py` builds the Ultra, Zealot and Sniper Jackals from it. Run before `extract_chars.py` (the Elite Special carries its beam rifle) |
| `ce_jackal_helmet.py` | Halo CE's Jackal helmet for the Halo 2 Jackal: cuts the helmet out of the CE model's `armored_head` permutation (what it has that the bare head doesn't), in the CE head bone's frame; `extract_h2_jackal.py` fits it onto the Halo 2 head (`HELMET_SCALE`, `HELMET_OFFSET`) as its own surface, tinted per rank |
| `extract_brute_kit.py` | the Brute armour kit from `h2_brute.zip` (`HCE_BRUTE_KIT`: the zip or its unpacked folder; `brute.blend` + its bitmaps): 48 helmets, chest plates, shoulder pads, bracers, belts and leg pieces on the Halo 2 Brute skeleton, read straight from the .blend (`lib/blendfile.py`, `lib/brute_kit.py`), one IQM per piece (Halo 3-style pieces tinted per rank), plus helmet debris and `BruteKit.json` with the per-rank pools. Run after `extract_h2_brute.py`; `build_digsite.py` writes the dressing code |
| `extract_halo_gore.py` | Halo CE and Halo 2 blood for the Halo gore, which also layers on Nash's Gore Mod when the player loads it (split per faction pack by `split_factions.py`, code in the core): the blood-splat decals (CE sprite sheets cut by their sequence rectangles, Halo 2's 2x2 sheets from `08b_deltacontrol.map` + `textures.dat`), converted from Halo's multiply / add blending to plain RGBA, grouped per species in `decaldef.hcegore`; the blood bursts and blood trails as white sprite masks (`HGBP`, `HGBS`). Output in `out/gore`; `split_factions.py` gives each faction pack its species' decals (Covenant, Flood, Marines) and puts `pack/ZScript/HaloCE/hce_gore.zsc` in the core |
| `gore_kit.py` | Dismemberment, run on `$HCE_OUT/models` after the extractors (again after the Digsite / Halo 2 ones) and before `build_pack.py` / `build_digsite.py`; it keeps the extractor's output as `<Char>_nogore.iqm/.json` and starts from that each time. Per race the head and arms (bone subtrees) get surfaces of their own, a hidden gore stump closing the body where each comes off, and a gib model of the severed piece whose surface list mirrors the body's (so it wears the dead enemy's own skins). Elites, Grunts and Jackals use SPV3's stump caps from `b40_1.map` (`HCE_SPV3_B40`; same skeletons as Halo CE); the Halo 2 Jackals, Brutes (head only: 32-surface limit), Hunters, Drones and Slug Men get kitbashed caps closing the cut edge. The stump texture is SPV3's own gore from its `bitmaps.map` (`HCE_SPV3_BITMAPS`: the file, or the stem of its split `.001`, `.002` ... pieces): the Kig-Yar's purple for Elites and Jackals, the Unggoy's teal for Grunts, recoloured to each other race's blood; the kitbashed caps centre its bone end on the cut (a patch of flesh for the boneless Hunters, Slug Men and Drones). Without `bitmaps.map` a stand-in is drawn. `build_pack.py` turns the json's `gore` block into `HCE_SeverLimb`; the API's `HCE_Dismember` picks limbs on hard kills (`hce_dismember`) |
| `blood_kit.py` | Blood on the body, run after `gore_kit.py` (again after the add-on's extractors): for every character that bleeds, three blood-splatter overlay models (`<Char>_blood1..3.iqm`: the body's own surfaces on the same skeleton, pushed a hair out along the normals; guns, stumps and shields left empty) and their textures (`blood<k>_<material>.png`). Hits are placed on the 3D body surface (area-weighted) and painted into texture space through a rasterised per-texel position map, so splats and their drips cross UV seams; stage 1 has 5 hits, stage 2 adds 7, stage 3 adds 10. `build_pack.py` attaches the overlay as model 7 at run time (`HCE_BloodModel`), hiding severed limbs (`HCE_BloodHideLimb`) and armour a variant doesn't wear (`HCE_BloodHideClass`) |
| `h2_elite_anims.py` | Halo 2 animations on the CE skeletons (the rigs are the same bipeds): the fuel-rod stance for the Elite, the rifle stance for the Elite Special, and Halo 2's Marine pistol stance (`01b_spacestation.map`, as `h2pistol`) for both Marine bodies (the Magnum and Sidekick Marines, Johnson up close). Called by `extract_chars.py` |
| `extract_h2_grunt.py` | Extra Crazy Grunt dialogue from Halo 2's `grunt_crazy` set in `08a_deltacliffs.map` (same `HCE_H2_MAP08` / `HCE_H2_SOUNDS` settings as the Brutes): fills the events the Crazy set is short on, skipping lines it already has (`HCE_VOICE_SRC`). Writes `voice_extra/Grunt_Crazy/`, which `build_voices.py` adds on top of the main source |
| `extract_marine_voices.py` | Marine dialogue: Halo CE's Marine voices (aussie, bisenti, fitzgerald, mendoza, the sergeant Johnson and the second sergeant: `sound\\dialog\\marines\\*`, `sargeant`, `sarge2` in the campaign maps) and Halo 2's from `01b_spacestation.map` + `sounds_en.dat` (`marine_*`, `sgt_*`; the female `marine_sassy` left out), up to six lines per event from each game, into `voice_extra/Marine_<Name>/`; CE's and Halo 2's Aussie and Johnson are merged. `build_pack.py` gives Marines a random face (`extract_chars.MULTI_PERMS`) and a random voice, Johnson's face always Johnson's voice |
| `extract_elite_loose.py` | The Loose Elite dialogue set: Halo CE's Elite dialogue from the campaign maps (`HCE_MAPS`), plus Halo 2's `elite_loose` lines from `08a_deltacliffs.map` (`HCE_H2_MAP08` / `HCE_H2_SOUNDS`) played backwards, the way CE's Elites speak. Writes `voice_extra/Elite_Loose/` with a `REPLACE` marker, so `build_voices.py` uses it instead of the main source's Loose set |
| `louden_voices.py` | Levels the dialogue (EBU R128, raised toward -11 LUFS with a limiter): `python3 louden_voices.py voices <digsite pack dir>` after `build_voices.py` / `build_digsite.py` |

Every Halo world unit becomes 80 map units. In MODELDEF, Z is scaled ×1.2 to cancel Doom's pixel-aspect squash.

## API addon

`addons/localdev/` packages as `HCE_EnemyAPI_LocalDEV.pk3`. It holds only `ZScript/BaseAI/enemies_base.zsc`, which overrides HDE Local_DEV's file of the same path. Zip the folder's contents:

```
cd addons/localdev && zip -r9 ../../HCE_EnemyAPI_LocalDEV.pk3 .
```

The generated `pack/` doesn't contain the API, so it must load after the addon.

## Dialogue pk3

`build_voices.py` builds `HaloCE_Enemies_Voices.pk3` from a checkout of https://github.com/Lewisk3/HaloDoomEnemies:

```
HCE_VOICE_SRC=/path/to/HaloDoomEnemies/Sounds HCE_VOICE_OUT=./voices python3 build_voices.py
cd voices && zip -r9 ../HaloCE_Enemies_Voices.pk3 .
```

Then run `python3 louden_voices.py voices` to level the lines (it only raises quiet ones, and running it twice does nothing). It maps each source category (e.g. `Grenade Thrw 3.ogg`) to an event (`GrenadeThrow`) and writes `$random HCE/<Voice>/<Event>` entries. Missing events alias to a related one, e.g. a Jackal's `KillPlayer` uses its `Taunt` lines.

## Fire patterns and weapon sounds

Both are set in `build_pack.py`. `PATTERNS` gives each weapon its shots per burst, tics between shots, pause range and overcharge wind-up. `FIRE_SOUNDS` gives the HDE SNDINFO names to play.

## Digsite add-on (private)

Builds `HaloCE_Enemies_Digsite.pk3` (Drinol + Drinol boss, Slug Men, carbine and pulse-carbine Elites in a rifle stance, SPV3's Blind Wolf and Thorn Beast). Run it after the main pipeline: it reuses `$HCE_OUT/ai_data.json` and the weapon pkls.

```
export HCE_DIGSITE=/path/to/h1               # clone of github.com/digsite/h1 (MCC-only licence: keep the output private)
export HCE_SKETCHFAB=/path/to/extra          # folder holding elite.model_animations (CE-rig Elite rifle set)
export HCE_CMT_CARBINE=/path/to/cmt_carbine  # CMT carbine: carbine.gbxmodel + bitmaps/ (*.bitmap tags)
export HCE_DIG_PACK=./addons/digsite
HCE_SPV3_A30=/path/to/a30_1.map HCE_SPV3_B30=/path/to/b30_1.map python3 extract_spv3.py   # SPV3 Blind Wolf + Thorn Beast (a30), Engineer (b30) -> IQM + $HCE_OUT/spv3_ai.json
python3 cmt_weapon.py          # loose gbxmodel + bitmap tags -> carbine weapon pkl (purple tint baked, glow surfaces)
python3 extract_digsite.py     # JMS/JMA sources -> Drinol, SlugMan IQMs + the 99_mac Particle Beam Rifle
python3 extract_elite_rifle.py # CE Elite + rifle set from elite.model_animations + carbine -> EliteRifle IQM
python3 gore_kit.py            # dismemberment for the add-on's characters (H2 Jackals, Brutes, Drones, Slug Men, rifle Elites)
python3 blood_kit.py           # blood overlays for them
python3 build_digsite.py       # classes/MODELDEF/skins via build_pack.build(), boss, Slug dialogue (needs ffmpeg)
cd addons/digsite && zip -r9 ../../HaloCE_Enemies_Digsite.pk3 .
```

| File | Role |
|---|---|
| `lib/jms.py` | JMS 8200 model and JMA/JMM/JMT/JMO/JMR/JMZ animation readers |
| `lib/loosewalk.py` | Generic loose (source) tag walker: block children, data blobs, tag paths |
| `lib/looset.py` | Loose actor / variant / biped stats |
| `lib/looseantr.py` | Loose `model_animations` reader (uncompressed frames) |
| `lib/loosebitmap.py` | Loose `.bitmap` decoding (DXT, 32-bit) |
| `lib/pcmap.py` | Halo CE PC/MCC cache reader (tag index at 0x50000000, gbxmodel vertex/strip data) |
| `extract_spv3.py` | SPV3 characters (Blind Wolf, Thorn Beast, Engineer) through `extract_chars.extract()`, plus their in-map sounds (ogg / PCM / Xbox ADPCM) |
| `cmt_weapon.py` | Loose `.gbxmodel` weapon geometry (triangle strips, LOD 0) |
| `lib/halosound.py` | Loose `.sound` reader + Xbox ADPCM decoder |
| `lib/preview.py` | Software renderer for checking skinned poses |
| `digsite_src/` | Hand-written add-on files: spawn handler, Drinol boss, ZSCRIPT, CVARINFO, credits |

`ednum_pins.json` holds every released class's DoomEdNum. `build_pack.py` keeps those numbers whatever order the classes come out in, and gives new classes the next free numbers; add a new class there once it has shipped.
