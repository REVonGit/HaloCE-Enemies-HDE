# devtools: building, testing and shipping the Halo CE enemy packs

The generator lives in the HDE repository (`/home/claude/repos/HaloCE-Enemies-HDE/generator`, also reachable as
`/home/claude/enemy`). It is the only working copy: edit it in place, there is nothing to port. Its working data
(`out/`, `factions/`, `voices/`, `addons/digsite|master`, `standalone/out/`, `sketchfab/`, `third_party/`, `*.blend`)
is gitignored.

## Machine paths
`hce_env` holds every `HCE_*` path (maps, caches, uploads, engine). `usercustomize.py` in the user site-packages loads it
into every Python process with `setdefault`, so an exported variable still wins. The generator's own defaults are
relative to the generator.

## Commands
| command | what it does |
|---|---|
| `bash build.sh full` | build_pack, build_digsite, then the API, faction, voice and Digsite pk3s into `/home/claude/game` |
| `bash build.sh quick` | build_pack and the faction pk3s only (fast iteration on HDE) |
| `bash build.sh digsite` | build_digsite, loudness pass, Digsite pk3, Standalone packs |
| `bash lt.sh "<pk3s>" [display] [log]` | load test after HDE: MAP01, summon, quit; exit 1 on a script error outside HDE |
| `python3 scene.py --spawn A,B --shots 40,90 ...` | in-game scene on COVERTST: spawn a row, screenshot, fight, log damage (see `--help`). `--res 2400x1500` for close crops from afar; `--zs-top` adds classes (a subclass forcing a look, e.g. `class SceneChieftainKH : HCE_BruteChieftainGravityHammer { override void PostBeginPlay() { hce_lineupLook = 3; super.PostBeginPlay(); } }`; it is drawn with its parent's MODELDEF); `--zs` adds per-tic code; `--nopin` frees the player from the camera spot; `--log-damage` also logs hits on the test's own `nds[]` actors |
| `python3 sweep.py [--only X] [--packs sa]` | every enemy class in the engine, six at a time, each spaced by its own radius: contact sheets, each batch's full-size shot and `index.txt` (classes that didn't spawn, raised an engine error, drew nothing or drew one flat colour) in `shots/sweep/`. Run it after a build to catch what a change broke |
| `python3 enc_test.py MAP05 [--goto 420] [--shot T]` | the Marine encounters on a Doom 2 map (4 at chance 1): each one's Marines and foes, their health and targets every 70 tics; `--goto` puts the player by the first one's Marines |
| `python3 lift_test.py [LIFTSW LIFTFACE LIFTWALK] [--order]` | a Marine following the player up a lift worked only the player's way (a switch elsewhere, the lift's face, a walk-over line), on `lifttest.wad` (`generator/tests/make_lifttest.py`); `--order` gives the press-that-button order on the switch instead. Passes when he reaches the player's ledge |
| `bash ship.sh --dry` | refresh both repos, build and load-test both dists in parallel, run the checks, print the change list |
| `bash ship.sh "subject" [body file]` | the same, then commit both repos (trailers from `trailers`) and push |

Logs go to `logs/`, screenshots to `shots/`.

`tests/` holds the `--zs` / `--zs-top` scripts of the squad tests (a walk through a real map with four followers,
frag-and-clear on a chosen door, the reload order, an arena fight, a hold under fire, the medic's charges, the
encounters' room check); `tools/` the UDMF/binary map reader (`udmf.py`), the position plotter for their logs
(`plotpos.py log tics out.png [wad cx,cy,R]`) and the maker of `hcedoor.wad` (two rooms, a door, a lift).
`HANDOFF.md` is the long version of all this.

`ship.sh` stops on: a failed refresh, dist or load test; any file over 40 MB; changed sounds (pass `--allow-sounds`
when a sound was meant to change); working data getting tracked. Dists are deleted after the load test.

## MCC data from the PC
The MCC `Split` folder on the PC (`E:\SteamLibrary\steamapps\common\Halo The Master Chief Collection\Split`) holds
`textures.dat`, `sounds_neutral.dat`, `bitmaps.map`, `a10.map` as numbered 100 MiB pieces (`.001`, `.002` ...).
`generator/lib/splitfile.py` reads such pieces as one file, so they are never joined, and only the pieces a job reads
need staging. A missing piece raises `MissingPart` naming the file and its byte range: stage that piece with the device
bridge (it lands in `/mnt/user-data/uploads/Halo The Master Chief Collection/Split/`) and run again.
