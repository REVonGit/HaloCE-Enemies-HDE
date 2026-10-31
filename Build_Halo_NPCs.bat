@echo off
setlocal
rem Build Halo NPCs.pk3: every pack (Covenant, Flood, Sentinels, Marines) combined into one file, in dist\.
rem Load it right after HDE, instead of the separate packs, never with them.
title Halo NPCs builder
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 is not installed, or not on PATH. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer.
  goto end
)
%PY% build.py --combined
if errorlevel 1 (echo. & echo The build did not finish. The message above says why.) else (echo. & echo Done: "Halo NPCs.pk3" is in the dist folder.)
:end
echo.
pause
