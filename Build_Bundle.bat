@echo off
setlocal
rem Compile only the bundle: Core + Covenant (Digsite included) + voices + API -> dist\HDE_CE_Covenant.pk3 (skipped if unchanged).
rem Or from a command prompt:  Build_Bundle.bat --force   (rebuild even if unchanged)
title HDE_CE_Covenant.pk3 builder
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 is not installed, or not on PATH. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer.
  goto end
)
%PY% build_bundle.py %*
if errorlevel 1 (echo. & echo The build did not finish. The message above says why.) else (echo. & echo Done: dist\HDE_CE_Covenant.pk3)
:end
echo.
pause
