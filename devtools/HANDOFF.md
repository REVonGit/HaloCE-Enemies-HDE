# Handoff: how the Halo CE enemy packs are built, tested and shipped

For whoever picks this up next (a person, or a fresh session with no memory of this one). `README.md` beside this file
lists the commands; this says how the pieces fit and what will bite you.

## The two repositories and one generator

* **HaloCE-Enemies-HDE** (`/home/claude/repos/HaloCE-Enemies-HDE`): the packs for HaloDoom Evolved, the generator
  (`generator/`), the docs and this `devtools/`. `packs/` holds the shipped pk3 contents unpacked (so GitHub diffs
  show what changed); `build.py` at the root zips them into `dist/`.
* **HaloCE-Enemies-Standalone** (`/home/claude/repos/HaloCE-Enemies-Standalone`): the same enemies with no HDE
  dependency. It has no generator of its own: `generator/build_standalone.py` in the HDE repo writes its packs by
  converting the HDE output (class names, HDE pickups and sounds mapped to its own `hces_*` library).
* **The generator** (`generator/`, also at `/home/claude/enemy`) is the only working copy of the code. Hand-written
  code is `addons/localdev/ZScript/BaseAI/enemies_base.zsc` + `hce_squad.zsc` (the enemy API: every enemy's AI,
  mixed into one class) and `pack/ZScript/HaloCE/*.zsc` (the handler with the squad orders and the order wheel,
  projectiles, gore, HDE glue). Everything else under `generator/` is Python that extracts models, animations,
  textures and dialogue from Halo's map files and writes the pk3 trees (`factions/`, `addons/`, `standalone/out/`),
  which are gitignored working data.
* **Shared copies:** `repo.json`'s `sync` lists files that exist both in `generator/` and under `packs/`; the root
  `build.py` copies the newest over the others at every build. Edit either. `hce_squad.zsc` is in that list.

## The loop

1. Edit (`enemies_base.zsc`, `hce_squad.zsc`, `hce_handler.zsc`, a Python extractor, docs).
2. For AI changes, test without a build: copy the API to the master addon and re-zip the LocalDEV pk3:
   `cp addons/localdev/ZScript/BaseAI/*.zsc addons/master/ZScript/BaseAI/ && (cd addons/localdev && rm -f
   /home/claude/game/HCE_EnemyAPI_LocalDEV.pk3 && zip -qr9 /home/claude/game/HCE_EnemyAPI_LocalDEV.pk3 .)`
   then a `scene.py` run. Handler, keys, Chief lines and anything generated need `bash build.sh quick` (~8 min).
3. `bash build.sh full` (~15 min: the packs, Digsite, the Standalone packs) before shipping. Run it detached:
   `(setsid nohup ./build.sh full > /tmp/bf.log 2>&1 &)` and poll the log; a foreground command here is killed at
   2 minutes.
4. `bash ship.sh "subject" body.txt` (~20 min): refreshes both repos' `packs/` from the built pk3s, builds and
   load-tests both dists, checks (sizes, sounds, working data), commits both repos with the trailers in `trailers`
   and pushes. `--allow-sounds` when a sound was meant to change (Chief lines, a new voice); `--dry` to see the
   change list without committing. Write the body file first: what changed and why, for someone reading `git log`.

## Testing in the engine

`scene.py` runs the engine headless (Xvfb) on `covertest.wad` or any wad/map, with a ZScript event handler compiled
in: `--zs` adds per-tic lines (`t` the tic, `pl` the player, `row` the spawned actors, `nds` for actors the test
spawns itself), `--zs-top` adds whole classes (a second `EventHandler` is registered automatically), `--nopin`
frees the player from the camera spot so a `--zs-top` handler can walk him, `--log-damage` logs hits on the player,
`row[]` and `nds[]`, `--voices` logs every line spoken. Output is every `HCEPREV` console line; screenshots land in
`shots/`. Tests that have earned their keep are in `tests/`: a random walk through a real map with four followers
logging every Marine who wanted to move and didn't (`walk_top.zs`, with `--nopin --zs-top`, `WALKDUR` = the
duration), frag-and-clear on a chosen door (`frag.zs`, the door nearest a point), a reload-order check, an arena
fight and a hold-under-fire check that log positions and posts (`fight.zs`, `hold.zs`; `tools/plotpos.py` draws
them over the map). Real maps used: Doom 2 MAP01/MAP02, Extermination Day's Hangar and Map 14 (`edaymaps.wad` in
the game folder is EDAY's maps alone: its pk3 won't load beside HDE).

The in-game checks that found real bugs this month, worth repeating after any movement change: Marines spawned on
one spot, Marines fenced by monster-blocking lines, a follower down a drop, a breach that picked a detail sector as
the door, a locked door the Chief had the key for, a burst counter left over from a lost target.

## Conventions that must hold

* **DoomEdNums never change once shipped.** New classes are pinned in `generator/ednum_pins.json`; the next free
  number is noted in the PACK_README table's last rows. Add every new number to the table in both repos.
* **Credits:** every ripped asset is credited in PACK_README's Credits and `generator/digsite_src/CREDITS.txt`.
* **Editor icons:** a new class needs one: `cd generator && HCE_UZDOOM=/home/claude/build/uzb/uzdoom
  HCE_GAME=/home/claude/game python3 udb_icons.py --missing`, then build again. To redo one, delete it from
  `out/udb_icons` first.
* **Sounds:** `keep_voices.py` keeps the committed bytes of a sound whose audio didn't change (the loudness pass
  isn't byte-stable), so a re-levelled line only ships when its level moved half a dB or more (the Chief's lines) or
  `--allow-sounds` is given and the line is new.
* **Bestiary lore stays in universe.** Docs describe behaviour as a player sees it, with the tunable named.
* **The HDE half of `enemies_base.zsc` keeps HDE's names and signatures**: HDE's own enemies and the Standalone
  conversion both depend on it.

## ZScript and engine gotchas met here

* The JIT can't pass a **local vector as an `out` argument** ("REGT_ADDROF not implemented for vectors" and the
  engine hangs): pass fields, as `HCE_Formation.spotTmp` / `aPos` do.
* **Static const arrays inside a mixin** can't be resolved; use a `switch` or arithmetic (`hce_squad.zsc`).
* `out`, `state`, `in` are keywords; no local `const`; `String(x)` is not a cast; a class literal in
  `(class<Actor>)("name")` resolves at compile time (look names up at run time).
* `BlockLinesIterator.CreateFromPos(pos, checkh, radius)`; `Line.locknumber` is the UDMF lock, `Door_LockedRaise`
  keeps its lock in `Args[3]` (`HCE_LineLock`).
* Friendly monsters are blocked by `ML_BLOCKMONSTERS` unless `bNOBLOCKMONST`; the squad sets it.
* A monster can't open a locked door; `HCE_PressLine` activates a locked line as the squad's player.

## Machine gotchas

* `sleep` returns at once in the shell here; wait with `python3 -c "import time; time.sleep(N)"` (N <= 115).
* Never `pkill -f` / `pgrep -f` (they match this session's own commands); kill by PID or process group.
* Disk is tight (2-3 GB free): `/tmp/cov_*.pk3`, `logs/`, `shots/` and old `dist/` trees are safe to delete;
  `/home/claude/ref/sabo/*.map` and `bitmaps.map` are kept on purpose (Sabopool's assets).
* `hce_env` holds every input path this machine has (Halo CE and Halo 2 maps, MCC split files, Sketchfab and
  Workshop rips). Many are under `/mnt/user-data/uploads/`, which is this session's staging area from the PC: stage
  the file again (device bridge) if it is gone. The MCC `Split` folder's 100 MiB pieces are read in place by
  `lib/splitfile.py`; stage only the pieces a job asks for (`MissingPart` names them).

## Where things stand

Shipped and working: the Covenant, Flood, Sentinels and Marines with their AI; squad orders (follow, hold, regroup,
fire orders, medic, weapon, button, reload, take position, stack up, frag and clear) on a two-page wheel; corpsman
biofoam charges; encounters with a room-size check; posts (the squad fights from chosen spots). Deferred, in rough
order of value: vehicles; Sentinel dialogue; non-combat characters; the Sabopool SMG animations (first-person only;
format question open); a column formation for stairs.
