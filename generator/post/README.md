# post: fixes applied to the packs' files after a build (run against packs/, in this order, after build_pack.py)

* `flood_tendril_alpha.py <Flood pack> ...`: the Flood combat forms' tendril cards (the 128 px skins on a flat grey) cut
  out by that grey, and the blood over them cut to match: they drew as grey rectangles.
* `flood_grunt_ranks.py <Flood pack>`: the Flood Grunt's armour in Halo's Grunt rank colours (minor orange, major red,
  spec ops black) as `floodgrunt_<rank>_<n>.png`; `HCE_FloodGruntBase` picks one as it spawns (Ultra white is the skin as made).
* `geist_skin.py`: the Geist in Covenant colours, a purple top and a grey underbelly by the facing of the model's own
  triangles, with the Elites' baked cube-map sheen (purple: the blue and magenta rank cubes mixed; grey: the silver) (reads the Geist IQM and its multipurpose maps; writes its two skins). The Geist's IQM also had its animations' joints out of order
  (the body flew apart): its animations are now its bind pose held, the gun swung down 75 degrees.
* Ruby's armoured Flood Elites (FloodEliteArmored / Commander / Ultra): their flesh skins (`*_0`, `*_1`) are the Halo CE
  Flood Elite's (`FloodElite/skins/floodelite_floodelite_<n>.png`), their armour skins their own.
* The Flood Jackal and Flood Blind Wolf (SPV3's flood_spider and flood_wolf, from `spv3_rockslide_flood.yelo`): their
  tentacle surfaces (Jackal surface 1, Wolf surface 0, SPV3's `infection_tentacles` shader) use the Infection Form's
  cut-out tentacle skin (`FloodInfection/skins/floodinfection_floodinfection_0.png`); their UVs land on its tentacle strip.
* Hand edits in the Flood pack beyond the generated classes (keep them through a regeneration):
  `ZScript/HaloCE/hce_flood_crawl.zsc` (the crawler mixin, the Flood Wolf's spikes, the Flood Jackal's spit), the
  `mixin HCE_FloodCrawler` + `HCE_CrawlThink` See state in `HCE_FloodInfectionBase` and `HCE_FloodJackalBase`,
  `UseRotationCenter` / `Rotation-Center` in their MODELDEF blocks, the Flood Jackal's spit weapon line, and the Flood
  Wolf's spike weapon, range, burst, gun offset, damage modifier 1.0 and its `HCE_Fight` / `HCE_Charge` overrides.
* `flood_arsenal.py` (run from `generator/`): every armed Flood body (human, Marine, armoured, ODST, Elite, armoured
  Elite, Ultra, Grunt, Brute) can carry any gun but the Forerunners': one overlay model per gun per body in
  `packs/HaloCE_Flood/models/hce/FloodArsenal/` (the Marine arsenal's guns on the body's own gun hand), the guns'
  textures the packs lacked, the shared firing data (`HaloCE_Covenant/ZScript/HaloCE/hce_flood_arsenal.zsc`, from the
  Marine body's loadouts) and each base class's loadouts between its FLOOD ARSENAL markers. Re-run after a
  regeneration of the Flood or Marine classes. (The Standalone packs take the code but not the models: their
  enemies drop no guns, so no Flood ever picks one up there.)
