#!/bin/bash
# Package the enemy API addon, the core and the faction packs, and the private Digsite/SPV3 add-on.
set -e
E=/home/claude/enemy; A=$E/addons; G=/home/claude/game
# the enemy API's one source: the repo's addons/localdev copy (the Master add-on carries the same file)
cp $A/localdev/ZScript/BaseAI/*.zsc $A/master/ZScript/BaseAI/
cd $A/localdev && rm -f $G/HCE_EnemyAPI_LocalDEV.pk3 && zip -qr9 $G/HCE_EnemyAPI_LocalDEV.pk3 .
cd $A/master && rm -f $G/HCE_EnemyAPI_Master.pk3 && zip -qr9 $G/HCE_EnemyAPI_Master.pk3 .
python3 $E/split_factions.py
rm -f $G/HaloCE_Enemies.pk3
cd $E/factions/core && rm -f $G/HaloCE_Core.pk3 && zip -qr9 $G/HaloCE_Core.pk3 .
for f in covenant flood sentinels marines; do
  N=$(python3 -c "print({'covenant':'Covenant','flood':'Flood','sentinels':'Sentinels','marines':'Marines'}['$f'])")
  cd $E/factions/$f && rm -f $G/HaloCE_$N.pk3 && zip -qr9 $G/HaloCE_$N.pk3 .
done
# dialogue louder (EBU R128 levelling, idempotent), then the voice pack
cd $E && python3 $E/build_voices.py
cd $E && python3 $E/louden_voices.py $E/voices $A/digsite
cd $E/voices && rm -f $G/HaloCE_Enemies_Voices.pk3 && zip -qr9 $G/HaloCE_Enemies_Voices.pk3 . -x '.loudened.json' '.sources.json'
cd $A/digsite && rm -f $G/HaloCE_Enemies_Digsite.pk3 && zip -qr9 $G/HaloCE_Enemies_Digsite.pk3 . -x '.loudened.json'
python3 $E/build_standalone.py
