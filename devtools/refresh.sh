#!/bin/bash
# refresh.sh hde|sa : the built game pk3s -> the repository's packs/ (four packs: Covenant carries Core, the API and
# the enemy dialogue; the Marines their dialogue). Uses repo_compose.py.
set -e
G=/home/claude/game; E=/home/claude/enemy; D=/home/claude/devtools
if [ "$1" = hde ]; then R=/home/claude/repos/HaloCE-Enemies-HDE; CORE=HaloCE_Core; COV=HaloCE_Covenant; DIG=HaloCE_Enemies_Digsite; API=HCE_EnemyAPI_LocalDEV
  PK="HaloCE_Core HCE_EnemyAPI_LocalDEV HaloCE_Flood HaloCE_Sentinels HaloCE_Marines"; MODE=hde
else R=/home/claude/repos/HaloCE-Enemies-Standalone; CORE=HaloCE_Standalone_Core; COV=HaloCE_Standalone_Covenant; DIG=HaloCE_Standalone_Digsite; API=
  PK="HaloCE_Standalone_Core HaloCE_Standalone_Flood HaloCE_Standalone_Sentinels HaloCE_Standalone_Marines"; MODE=sa; fi
cd $R
for p in $PK HaloCE_Enemies_Voices; do rm -rf packs/$p; mkdir packs/$p; (cd packs/$p && unzip -q $G/$p.pk3); done
python3 -c "
import sys; sys.path.insert(0,'tools'); import merge_hce_packs as m
m.merge(['$G/$COV.pk3','$G/$DIG.pk3'],'/tmp/cov_$1.pk3',quiet=True)"
rm -rf packs/$COV; mkdir packs/$COV; (cd packs/$COV && unzip -q /tmp/cov_$1.pk3)
python3 $D/repo_compose.py $R $MODE
python3 $D/keep_voices.py $R
find packs -type f -exec touch {} +
# (sounds: keep_voices.py keeps the committed bytes of every sound whose audio is unchanged)
git update-index --really-refresh >/dev/null 2>&1 || true
git status --short | head -40; git status --short | wc -l
