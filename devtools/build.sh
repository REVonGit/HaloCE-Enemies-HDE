#!/bin/bash
# build.sh [full|quick|digsite]: the game pk3s in /home/claude/game from the repo's generator.
#   full    build_pack, build_digsite, then build_addons (API, faction packs, voices, Digsite with its loudness pass, Standalone)
#   quick   build_pack and the faction packs only (the HDE packs to test with)
#   digsite build_digsite, the loudness pass, its pk3 and the Standalone packs
set -e
D=/home/claude/devtools; E=/home/claude/enemy; G=/home/claude/game; L=$D/logs; mkdir -p $L
cd $E
case "${1:-full}" in
full)
  python3 build_pack.py > $L/build_pack.log 2>&1 || { tail -5 $L/build_pack.log; exit 1; }
  python3 build_digsite.py > $L/build_digsite.log 2>&1 || { tail -5 $L/build_digsite.log; exit 1; }
  bash $D/build_addons.sh > $L/addons.log 2>&1 || { tail -5 $L/addons.log; exit 1; } ;;
quick)
  python3 build_pack.py > $L/build_pack.log 2>&1 || { tail -5 $L/build_pack.log; exit 1; }
  cp addons/localdev/ZScript/BaseAI/*.zsc addons/master/ZScript/BaseAI/
  (cd addons/localdev && rm -f $G/HCE_EnemyAPI_LocalDEV.pk3 && zip -qr9 $G/HCE_EnemyAPI_LocalDEV.pk3 .)
  python3 split_factions.py > $L/split.log 2>&1 || { tail -5 $L/split.log; exit 1; }
  python3 $D/warm_lumps.py factions dir >> $L/split.log 2>&1
  (cd factions/core && rm -f $G/HaloCE_Core.pk3 && zip -qr9 $G/HaloCE_Core.pk3 .)
  for f in covenant:Covenant flood:Flood sentinels:Sentinels marines:Marines; do
    (cd factions/${f%%:*} && rm -f $G/HaloCE_${f##*:}.pk3 && zip -qr9 $G/HaloCE_${f##*:}.pk3 .)
  done ;;
digsite)
  python3 build_digsite.py > $L/build_digsite.log 2>&1 || { tail -5 $L/build_digsite.log; exit 1; }
  python3 $D/warm_lumps.py addons dir >> $L/build_digsite.log 2>&1
  python3 louden_voices.py voices addons/digsite > $L/louden.log 2>&1
  (cd addons/digsite && rm -f $G/HaloCE_Enemies_Digsite.pk3 && zip -qr9 $G/HaloCE_Enemies_Digsite.pk3 . -x '.loudened.json')
  python3 build_standalone.py > $L/standalone.log 2>&1 || { tail -5 $L/standalone.log; exit 1; } ;;
*) echo "build.sh full|quick|digsite"; exit 2 ;;
esac
echo "build $1 done"
