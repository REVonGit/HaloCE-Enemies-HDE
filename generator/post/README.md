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
