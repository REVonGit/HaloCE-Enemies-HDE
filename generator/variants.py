"""The variants' looks and ranks: the tables build_pack.py builds the pack's variants from, gathered here so they can be
tuned without reading the build code. Colours are (r, g, b) in 0..1; strengths are 0..1 unless noted. build_pack.py
reads them all (from variants import *); build_digsite.py adds its own entries to some (bp.SHINE['EliteZealot'], ...).

    GRUNT_RANKS, HEAVY_GREEN, HEAVY_HUE        new Grunt and Elite ranks and their armour colours
    HONOR_RED, RANGER_STEEL, ELITE_H2_ARMOUR   the Honor Guard and Ranger Elites in Halo 2's armour
    SHIELD_TINT, SHELL_TINT                    Jackal shields and the shield flare by rank / character
    GRUNT_SHIELDS                              the shielded Grunt ranks
    HUNTER_COLOURS, HUNTER_TONE                the red and white Hunters
    SHINE, SHINE_CUBE, RANK_SHINE, KIT_SHINE   the cube-map reflection baked into armour (and how strong)
    VIVID, VIVID_SHINE, UNDERSUIT, MINOR_BLUE, HUE_LOCK   rank recolours
    GLOW_*, KIT_GLOW_STRENGTH, KIT_OWN_VISORS  lights (self-illumination brightmaps) and visors
"""

# More Grunt ranks (new): Halo 2's Ultra (grunt_ultra: white armour, the toughest of the regular Grunts) with the
# needler or the plasma pistol, and the Heavy (Halo 2's grunt_heavy, in Halo 3's green) with the fuel rod on the Spec
# Ops body (the one with the fuel rod model). Ultras fight like Majors with a third more health; Heavies like the
# Spec Ops fuel-rod Grunts.
# rank -> (armour colour lower bound, upper bound): Halo's change-colour range, so a rank can vary a little from
# Grunt to Grunt (same colour twice = one fixed colour). To recolour a rank, change its pair; to add a rank, add a key
# here and teach build_pack.add_grunt_ranks which variant it copies. Health lives there too (the 1.33 on the Ultra).
GRUNT_RANKS = {'ultra': ((0.86, 0.88, 0.92), (0.70, 0.72, 0.78)), 'heavy': ((0.30, 0.52, 0.14), (0.20, 0.38, 0.08))}

# Elite Heavy (new): a green rank between the Major and the Commander, carrying heavier guns: the fuel rod (in Halo 2's
# fuel-rod stance), the plasma rifle and the needler. 125 body and a 200-point shield (the Spec Ops Elite's), the
# Major's combat data
# its armour change colour (build_pack.add_elite_heavy); its painted skin is the blue Minor's plates turned to the hue
# HEAVY_HUE below (build_pack.heavy_green), so change both to move the rank's green
HEAVY_GREEN = (0.16, 0.36, 0.10)

# Halo 2's Honor Guard and Ranger Elites (build_pack.add_elite_h2_armour): their armour colours, and per rank the
# Halo CE variants they copy, their Halo 2 pieces (extract_h2_elite_kit.py) and extra flags
HONOR_RED = (0.60, 0.13, 0.05)
RANGER_STEEL = (0.72, 0.78, 0.86)

# To give a Halo 2 rank another gun, add 'gun': 'CE variant path' to its first entry (the CE variant supplies the
# combat data and stance); to dress it in another kit piece, name the piece's model (EliteKit/<piece>.iqm) in the
# third; the flags are class flags ZScript gets on top of the CE variant's (HCE_Jetpack: the Ranger's jump pack).
ELITE_H2_ARMOUR = {   # new rank -> (Halo CE variant it copies per gun, colour, kit pieces at models 1.., extra flags)
    'honor guard': ({'plasma rifle': 'characters\\elite\\elite commander\\elite commander plasma rifle',
                     'energy sword': 'characters\\elite\\elite commander\\elite commander energy sword'},
                    HONOR_RED, ('honor_body',), ()),
    'ranger': ({'plasma rifle': 'characters\\elite\\elite minor\\elite minor plasma rifle',
                'needler': 'characters\\elite\\elite minor\\elite minor needler'},
               RANGER_STEEL, ('ranger_body', 'elite_jetpack'), ('HCE_Jetpack',)),
}

# Halo 2's Ranger and its jump pack: their colour maps get the armour's cube-map reflection Halo 2 draws on them (its
# shaders reflect a cube map under the colour map's alpha), as the Elites' painted armour does; the silver cube, gentle
# texture -> (strength, which of the Elites' cube maps: 1 red, 3 silver)
KIT_SHINE = {'ek_ranger_arms.png': (0.25, 3), 'ek_ranger_torso.png': (0.25, 3), 'ek_ranger_legs.png': (0.25, 3),
             'ek_ranger_helmet.png': (0.25, 3),
             'ek_elite_jetpack.png': (0.16, 3),      # skin_check: its wide specular mask glares above this
             # the Honor Guard's Halo 2 Elite armour, crimson and gold, in the red rank's cube
             'ek_torso.png': (0.3, 1), 'ek_arms.png': (0.3, 1), 'ek_legs.png': (0.3, 1), 'ek_elite_honor_armor.png': (0.25, 1)}

# Jackal energy shield colour by rank (Halo shows it through a translucent shader we can't use, so it's baked + brightmapped)
# rank (the variant's _rank) -> (r, g, b) of the shield texture; a rank missing here keeps the shield as extracted.
# build_digsite.py adds 'field marshal' (the Ultra Zealot's arm shield).
SHIELD_TINT = {'minor': (0.20, 0.35, 1.00), 'ultra': (1.00, 0.55, 0.10), 'major': (1.00, 0.30, 0.85),   # Ultra orange, Major pink
               'zealot': (1.00, 0.84, 0.30),   # Zealot (the Halo 2 Spiker Jackal): gold, the colour of Covenant zealots
               # Halo 2's Sentinels: the Aggressors' shield bubble (pale blue for the steel minors, amber for the gold
               # captains) and the Enforcer's two shields (cyan)
               'sentinel_minor': (0.45, 0.75, 1.00), 'sentinel_captain': (1.00, 0.72, 0.25), 'enforcer': (0.35, 0.85, 1.00)}

# the red and white Hunters' armour (build_pack.bake_hunter)
HUNTER_COLOURS = {'red': (0.78, 0.13, 0.08), 'white': (0.86, 0.88, 0.93)}

# (base, gain): paint = colour * (base + gain * the skin's brightness); raise the gain for brighter paint, the base to
# lift its shadows. Tuned so skin_check's lift measure stays under its limit
HUNTER_TONE = {'red': (0.14, 1.9), 'white': (0.08, 1.45)}     # base and gain of the paint's light (skin_check: lift)

# Baked armour shine (Elites and Grunts): Halo CE draws their armour with a cube-map reflection under the
# multipurpose map's specular mask (red channel on Xbox): the swirling liquid-metal sheen. Doom's renderer has no cube
# maps, so the reflection is baked into the skin with Halo's own cube maps (extract_cubemaps.py): every armour texel
# gets the model's surface normal there (the triangles rasterised into texture space, bind pose), nudged by the paint's
# own relief, and reflects a view from the front into the cube map; the result is added under the specular mask. The
# Elites' cube map follows their rank colour (blue, magenta, gold, silver); the Grunts wear the same ones (below).
# character -> strength of the baked reflection (0 or missing: none). build_pack.add_shine reads it; the add-ons add
# their own characters (build_digsite.py: EliteZealot, H2Jackal). Lower a value when a skin glares (skin_check).
SHINE = {'Elite': 1.0, 'EliteSpecial': 1.0, 'EliteRifle': 1.0, 'Grunt': 1.0, 'GruntSpecOps': 1.0, 'Hunter': 0.55}

# the Grunts wear the Elites' rank cube maps (gold for the orange Minors, red for the Majors, silver for Spec Ops) so their
# armour reads like the Elites' painted skins; Halo CE gave them its dull 'cubemap dark gray'
# character -> the cube-map set under out/cubemaps/<name> (extract_cubemaps.py); 'elite' is the four rank cubes, the
# one picked by the rank's armour colour (build_pack.cube_index: 0 blue, 1 red/magenta, 2 gold, 3 silver)
SHINE_CUBE = {'Elite': 'elite', 'EliteSpecial': 'elite', 'EliteRifle': 'elite', 'Grunt': 'elite', 'GruntSpecOps': 'elite', 'Hunter': 'elite'}
# the Hunters too (blue in the Minor's blue cube, red in the red, white in the silver), under Halo CE's own specular mask

# the blue Minor Elite's armour colour: the Spec Ops body's own textures (the ones no hand-painted skin covers) are
# baked in it first, then turned purple (build_pack.build, the skin loop), so they carry the Minor's blue cube-map
# sheen the painted skins have
MINOR_BLUE = (0.31, 0.30, 0.53)

# the hue (0..360) the blue Minor skin's plates are turned to for the Elite Heavy (build_pack.heavy_green)
HEAVY_HUE = 104          # the Elite Heavy's green (Halo 3's Heavy green), degrees

# the Grunts' armour keeps its rank colour's hue under the Elites' cube maps (the gold one would turn the orange
# Minors yellow): the hue of the painted parts is pulled back to the rank colour, the reflection's brightness kept
HUE_LOCK = ('Grunt', 'GruntSpecOps')

# a rank's armour reflection scaled (skin_check: the Ultra Grunts' pale armour under the full silver cube glared)
# (character, rank) -> multiplier on SHINE[character]; ranks not listed get 1.0
RANK_SHINE = {('Grunt', 'ultra'): 0.6}

# Elite Commander (the gold Elite): its tag colour is a dark ochre that, multiplied into the dark Elite Special
# armour, came out a muddy olive. Halo draws it with a bright specular sheen we can't, so the armour is re-baked as
# a vibrant gold that keeps the armour's shading (dark creases stay darker, raised edges catch the light).
# a substring of the variant's name -> the colour its armour is re-baked in (build_pack.bake_vivid); add a rank here
# to give it the vivid treatment instead of Halo's plain colour multiply
VIVID = {'elite commander': (1.00, 0.78, 0.22), 'elite ranger': (0.72, 0.78, 0.86)}   # the Ranger: Halo 2's pale EVA steel

# the same keys -> the reflection strength passed to bake_vivid (unlisted: 1.0)
VIVID_SHINE = {'elite ranger': 0.35}     # how strong their armour's reflection is (on the pale steel the full one glared)

# the teal of the regular Elites' bodysuit: bake_vivid tints the suit between the vivid ranks' plates toward it (and
# their gloves, darker), so the Commander matches its lower ranks instead of showing a black undersuit
UNDERSUIT = (0.30, 0.52, 0.52)

# Energy-shield flare (the shell actor drawn additively over a shielded unit when it's hit): tint per character
# character -> (r, g, b) of its shell texture (build_pack.bake_shell); every shielded character needs an entry (the
# add-ons set theirs in code: Sentinels, Drones, the Zealot)
SHELL_TINT = {'Elite': (0.45, 0.70, 1.00), 'EliteSpecial': (0.45, 0.70, 1.00), 'Brute': (1.00, 0.78, 0.30),
              'Grunt': (0.45, 0.70, 1.00), 'GruntSpecOps': (0.45, 0.70, 1.00)}

# Grunts with an energy shield (new): the Ultras and the Spec Ops (build_pack.add_grunt_shields), rank -> shield points
# (raise a value for a tougher shield; add a rank to shield it; remove one and that rank fights unshielded)
GRUNT_SHIELDS = {'ultra': 60.0, 'specops': 60.0}

# Marine kit visor textures that get the visor shader (the cube-map reflection) as they are, without the tint the
# other helmets' visors are given (build_pack.kit_visors); add a kit helmet's visor here to keep its own colour
KIT_OWN_VISORS = ('mk_hellbringer_visor.png', 'mk_h2_pilot_visor.png')   # kit visors in their own colours (the Hellbringer's amber lens, the pilots' smoked visor)

# Self-illumination: Halo CE's multipurpose map keeps it in the green channel (Xbox: red specular, green self-illumination,
# blue colour change). Every Covenant skin baked from a material that has some gets a brightmap of it (the Elites' and
# Hunters' inset lights, the Grunts' and Jackals' glowing panels, the Engineer's and Slug Man's lights), so those
# texels stay fullbright in the dark; the cloaked skins are left out (their camo shader). The Elite kit's maps come with
# their own (extract_h2_elite_kit.py: the Ranger's and the jump pack's lights, the Honor Guard's markings).
# The four below are read by build_pack.glow_maps: lower GLOW_MIN to brightmap fainter lights, raise GLOW_STRENGTH
# for lights that stay brighter in the dark, GLOW_SOFT for a wider halo round each lit texel.
GLOW_MIN = 0.3                # a material glows when its self-illumination reaches this somewhere

GLOW_STRENGTH = 0.55          # how far toward fullbright a glowing texel goes (1 = fullbright)

GLOW_SOFT = 1.0               # its edge feathered over this many texels

KIT_GLOW_STRENGTH = 0.75      # the Halo 2 pieces' lights (the Ranger's, the jump pack's: coloured lamps), a little stronger
