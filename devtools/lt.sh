#!/bin/bash
# lt.sh <pk3s> [display] [log]: load-test pk3s (after HaloDoom Evolved) on MAP01: start, summon an enemy, quit.
# Exit 1 if the engine reports a script error or VM abort outside HDE's own files.
G=/home/claude/game; U=/home/claude/build/uzb/uzdoom; N=${2:-76}; LOG=${3:-/home/claude/devtools/logs/lt.log}
rm -f /tmp/.X$N-lock /tmp/.X11-unix/X$N; Xvfb :$N -screen 0 640x480x24 >/dev/null 2>&1 & XP=$!; sleep 2
DISPLAY=:$N timeout 240 $U -iwad $G/doom2.wad -nosound -skill 3 -file $G/HDE_dev_lite.pk3 $1 -width 320 -height 200 +vid_fullscreen 0 +map MAP01 +"wait 140; summon HCE_RandomDrone; wait 70; quit" > $LOG 2>&1
kill -9 $XP 2>/dev/null; wait $XP 2>/dev/null
BAD=$(grep -E "VM abort|Script error|ZScript error" $LOG | grep -v "HDE_dev_lite" | head -5)
[ -n "$BAD" ] && { echo "$BAD"; exit 1; }
echo "load ok ($(grep -c . $LOG) lines)"
