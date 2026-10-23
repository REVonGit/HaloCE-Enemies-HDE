#!/bin/bash
# ship.sh [--dry] [--allow-sounds] "subject" [body file]
# Refresh both repositories from the game pk3s (HDE and Standalone side by side), build each one's dist and load-test it,
# check the changes, then commit both with the session trailers ($D/trailers) and push.
# Checks: a refresh, dist or load test failing stops it; so do files over 40 MB, changed sounds (they should only change
# when a sound was meant to: --allow-sounds), and anything under a private or working folder getting tracked.
# --dry: everything but the commit and push (prints what would be committed).
D=/home/claude/devtools; L=$D/logs; mkdir -p $L
DRY=0; SND=0
while [ "${1#--}" != "$1" ]; do case "$1" in --dry) DRY=1;; --allow-sounds) SND=1;; esac; shift; done
SUBJ="$1"; BODY="$2"
[ $DRY = 1 ] || [ -n "$SUBJ" ] || { echo 'ship.sh [--dry] [--allow-sounds] "subject" [body file]'; exit 2; }

one() {   # one repo: refresh, dist, load test
  local m=$1 R=/home/claude/repos/HaloCE-Enemies-$2 disp=$3
  bash $D/refresh.sh $m > $L/refresh_$m.log 2>&1 || { echo "$2: refresh failed (logs/refresh_$m.log)"; return 1; }
  (cd $R && rm -rf dist && python3 build.py > $L/dist_$m.log 2>&1) || { echo "$2: dist build failed (logs/dist_$m.log)"; return 1; }
  bash $D/lt.sh "$(ls $R/dist/*Merged*.pk3)" $disp $L/lt_$m.log > $L/lt_$m.result 2>&1; local rc=$?
  rm -rf $R/dist
  [ $rc = 0 ] || { echo "$2: load test failed:"; cat $L/lt_$m.result; return 1; }
  echo "$2: $(cat $L/lt_$m.result)"
}
one hde HDE 77 & P1=$!; one sa Standalone 78 & P2=$!
wait $P1; R1=$?; wait $P2; R2=$?
[ $R1 = 0 ] && [ $R2 = 0 ] || { echo "stopped: nothing committed"; exit 1; }

FAIL=0
for r in HDE Standalone; do
  cd /home/claude/repos/HaloCE-Enemies-$r
  git add -A
  n=$(git diff --cached --name-only | wc -l)
  echo "== $r: $n files"
  git diff --cached --name-only | awk -F/ '{ d = $1"/"$2; if (NF > 3) d = d"/"$3; print d }' | sort | uniq -c | sort -rn | head -12
  big=$(git diff --cached --name-only -z | xargs -0 -r ls -l 2>/dev/null | awk '$5 > 40*1024*1024 {print $9}')
  [ -n "$big" ] && { echo "  files over 40 MB: $big"; FAIL=1; }
  snd=$(git diff --cached --name-only --diff-filter=M | grep -ci '/sounds/.*\.\(ogg\|wav\|flac\)$')
  [ "$snd" -gt 0 ] && [ $SND = 0 ] && { echo "  $snd sounds changed (a missed loudness pass? --allow-sounds if meant)"; FAIL=1; }
  bad=$(git diff --cached --name-only | grep -E '^generator/(out|addons/digsite|addons/master|factions|voices|sketchfab|standalone/out)/' | head -3)
  [ -n "$bad" ] && { echo "  working data staged: $bad"; FAIL=1; }
done
if [ $FAIL = 1 ] || [ $DRY = 1 ]; then
  for r in HDE Standalone; do (cd /home/claude/repos/HaloCE-Enemies-$r && git reset -q); done
  [ $FAIL = 1 ] && { echo "stopped: nothing committed"; exit 1; }
  echo "dry run: nothing committed"; exit 0
fi
MSG=$(mktemp); { echo "$SUBJ"; echo; [ -n "$BODY" ] && { cat "$BODY"; echo; }; cat $D/trailers; } > $MSG
for r in HDE Standalone; do
  cd /home/claude/repos/HaloCE-Enemies-$r
  if git diff --cached --quiet; then echo "$r: nothing to commit"; continue; fi
  git commit -q -F $MSG && git push -q origin main 2>&1 | tail -2; echo "$r: $(git log --oneline -1)"
done
rm -f $MSG
