# Halo CE enemy tools

These scripts regenerate `HaloCE_Enemies.pk3` from your own Halo CE **Xbox** campaign maps (a10, a30, a50, b30, b40, c10, c20, c40, d20, d40).

Requirements: Python 3.10+, numpy, Pillow, and a checkout of https://github.com/cybersecurity/halo-ce-universal. Its decomp headers provide every tag struct layout.

```
export HCE_HALO_SRC=/path/to/halo-ce-universal/source
export HCE_MAPS=/path/to/maps        # folder holding a10.map ... d40.map
export HCE_OUT=./out HCE_PACK=./pack # pack/ already holds the hand-written ZScript/CVARINFO/SNDINFO
python3 extract_ai.py      # actv/actr/bipd/coll/weap tags                          -> $HCE_OUT/ai_data.json
python3 extract_weapons.py # third-person weapon models + textures                 -> $HCE_OUT/weapons
python3 extract_chars.py   # IQM models + animations + skins + held weapons         -> $HCE_OUT/models
python3 build_pack.py      # ZScript classes, MODELDEF, baked variant skins, MAPINFO -> $HCE_PACK
python3 split_factions.py  # pack/ -> factions/{core,covenant,flood,sentinels,marines}
for f in core covenant flood sentinels marines; do (cd factions/$f && zip -r9 ../../HaloCE_$f.pk3 .); done   # rename to HaloCE_Core/Covenant/Flood/Sentinels/Marines.pk3
```

| File | Role |
|---|---|
| `halomap.py` | Xbox cache-file reader (zlib, tag index) |
| `clayout.py` | i386 struct layout calculator over the decomp headers |
| `tags.py` | Typed tag access (`Tag['path.to.field']`, blocks) |
| `halomodel.py` | `mode` geometry (compressed verts, strips) and `antr` animations (raw + compressed, overlays, root motion) |
| `iqm.py` | IQM v2 writer |
| `bitmaps.py`, `render.py` | Xbox bitmap decoding (DXT/swizzled) and shader lookup |
| `extract_weapons.py` | Weapon `mod2` geometry; sword blade and needles get solid glow textures |
| `extract_chars.py` | Character list, LOD/permutation pick, overlay baking, weapons bound to the hand marker, surfaces merged per material (UZDoom max 32) |
| `extract_ai.py` | AI and stat dump |
| `build_pack.py` | Pack generator: weapon table, animation mapping, per-type AI flags |
| `build_standalone.py` | Builds the `HaloCE_Standalone_*.pk3` set from the built faction packs and add-on. It needs HDE Local_DEV (`HCE_HDE_PK3`: its pk3 or an unpacked folder) to copy sounds, sprites and models from. `standalone/hces_lib.zsc` holds the HDE-derived projectiles, grenades, effects and shields. |
| `merge_hce_packs.py` | Merges any set of the built pk3s (core, factions, add-on) into one, reconciling zscript/mapinfo/cvarinfo |
| `h2map.py`, `h2anim.py`, `h2opus.py` | Halo 2 MCC readers: chunk-compressed cache, tag index, render models, animation codecs (ported from TagTool), sound gestalt and the Opus audio in `sounds_*.dat` |
| `extract_h2.py` | Halo 2 Drone -> IQM + JSON. Set `HCE_H2_MAP` to `01b_spacestation.map`, `HCE_H2_TEXTURES` to MCC's `textures.dat` (real skins) and `HCE_H2_SOUNDS` to the `h2_maps_win64_dx11` folder (`sounds_en.dat` dialogue, `sounds_neutral.dat` effects) |
| `extract_h2_brute.py` | Halo 2 Brutes from `08b_deltacontrol.map` (`HCE_H2_MAP08B` / `HCE_H2_CACHE08B`): model with every rank's armour plus Tartarus's pieces, the regular and gravity-hammer animations, the CE plasma rifle / assault rifle / shotgun, the Spiker and the H2 gravity hammer in the hand, helmet debris; voices and effects come from `08a_deltacliffs.map` (`HCE_H2_MAP08`) (same `HCE_H2_TEXTURES` / `HCE_H2_SOUNDS` settings). Run `python3 cmt_weapon.py spiker <Spiker folder>` first to convert the Spiker |
| `split_factions.py` | Splits the generated tree into the shared core (no Halo assets) and one pack per faction |
| `pack/ZScript/BaseAI/enemies_base.zsc` | Extended HaloDoom_EnemyBase (hand-written) |

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

It maps each source category (e.g. `Grenade Thrw 3.ogg`) to an event (`GrenadeThrow`) and writes `$random HCE/<Voice>/<Event>` entries. Missing events alias to a related one, e.g. a Jackal's `KillPlayer` uses its `Taunt` lines.

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
python3 build_digsite.py       # classes/MODELDEF/skins via build_pack.build(), boss, Slug dialogue (needs ffmpeg)
cd addons/digsite && zip -r9 ../../HaloCE_Enemies_Digsite.pk3 .
```

| File | Role |
|---|---|
| `jms.py` | JMS 8200 model and JMA/JMM/JMT/JMO/JMR/JMZ animation readers |
| `loosewalk.py` | Generic loose (source) tag walker: block children, data blobs, tag paths |
| `looset.py` | Loose actor / variant / biped stats |
| `looseantr.py` | Loose `model_animations` reader (uncompressed frames) |
| `loosebitmap.py` | Loose `.bitmap` decoding (DXT, 32-bit) |
| `pcmap.py` | Halo CE PC/MCC cache reader (tag index at 0x50000000, gbxmodel vertex/strip data) |
| `extract_spv3.py` | SPV3 characters (Blind Wolf, Thorn Beast, Engineer) through `extract_chars.extract()`, plus their in-map sounds (ogg / PCM / Xbox ADPCM) |
| `cmt_weapon.py` | Loose `.gbxmodel` weapon geometry (triangle strips, LOD 0) |
| `halosound.py` | Loose `.sound` reader + Xbox ADPCM decoder |
| `preview.py` | Software renderer for checking skinned poses |
| `digsite_src/` | Hand-written add-on files: spawn handler, Drinol boss, ZSCRIPT, CVARINFO, credits |
