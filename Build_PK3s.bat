@echo off
setlocal
rem Compile packs\ into dist\*.pk3.  Double-click: every pack + the bundle + the merged pack.
rem Or run from a command prompt:  Build_PK3s.bat Covenant Digsite   (only those packs)
title Halo CE enemy pk3 builder
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 is not installed, or not on PATH. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer.
  goto end
)
if "%~1"=="" (%PY% build.py --all) else (%PY% build.py %*)
if errorlevel 1 (echo. & echo The build did not finish. The message above says why.) else (echo. & echo Done: the pk3s are in the dist folder.)
:end
echo.
pause
