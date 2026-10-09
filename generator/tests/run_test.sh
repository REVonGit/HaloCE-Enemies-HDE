#!/bin/bash
# run_test.sh [seconds] [skill 1-5] [extra +commands...]: loads HDE Local_DEV and every HDE-version pack in UZDoom with no
# window (Xvfb), plays covertest.wad (make_covertest.py) for that many seconds with every enemy spawned, and reports from
# the console log only: script errors, and the cover / climbing counts the test harness prints. No screenshots.
#   HCE_GAME     folder with doom2.wad, HDE_dev_lite.pk3 (HDE Local_DEV), the built pk3s and covertest.wad
#   HCE_UZDOOM   the uzdoom executable
T=$(cd "$(dirname "$0")" && pwd)
G=${HCE_GAME:?set HCE_GAME to the folder with doom2.wad, HDE_dev_lite.pk3 and the built pk3s}; U=${HCE_UZDOOM:?set HCE_UZDOOM to the uzdoom executable}
[ -f $G/covertest.wad ] || python3 $T/make_covertest.py $G/covertest.wad
SECS=${1:-60}; SK=${2:-4}; shift 2 2>/dev/null
rm -f /tmp/hcetest.pk3 && (cd $T/harness && zip -qr /tmp/hcetest.pk3 .)
LOG=/tmp/hcetest.out
timeout $((SECS + 300)) stdbuf -oL -eL xvfb-run -a -s "-screen 0 640x480x24" $U -iwad $G/doom2.wad -nosound -skill $SK \
  -file $G/HDE_dev_lite.pk3 $G/HCE_EnemyAPI_LocalDEV.pk3 $G/HaloCE_Core.pk3 $G/HaloCE_Covenant.pk3 $G/HaloCE_Flood.pk3 \
        $G/HaloCE_Sentinels.pk3 $G/HaloCE_Marines.pk3 $G/HaloCE_Enemies_Digsite.pk3 $G/covertest.wad /tmp/hcetest.pk3 \
  -width 320 -height 200 +vid_fullscreen 0 +gl_lights 0 +sv_cheats 1 +map COVERTST +god "$@" > $LOG 2>&1 &
PID=$!
for i in $(seq 1 $((SECS + 240))); do
  sleep 1; grep -q "HCETEST t=$SECS " $LOG 2>/dev/null && break; kill -0 $PID 2>/dev/null || break
  grep -qE "Execution could not continue|Script error, \"(HaloCE|HCE)|^.*hce[a-z_]*\.zsc.*(error|Unknown|redefine)" $LOG && break
done
kill $PID 2>/dev/null; sleep 2
for p in $(pgrep -f "^$U -iwad") $(pgrep -f "^Xvfb :"); do kill -9 $p 2>/dev/null; done
grep -iE "script error|VM abort|exception|error|redefine|unknown|tried to|unexpected" $LOG | grep -v "^.*HCETEST" | sort | uniq -c | sort -rn | head -30
grep HCETEST $LOG | tail -n 12
