@echo off
rem Generate subtitles for every video in .\input. Pass --force to reprocess everything.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

set PYTHONUTF8=1
".venv\Scripts\python.exe" -m autosub %*
pause
