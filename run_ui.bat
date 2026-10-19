@echo off
rem Start the AutoSub web UI and open it in your browser. Close this window to quit.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

set PYTHONUTF8=1
".venv\Scripts\python.exe" -m autosub.web %*
pause
