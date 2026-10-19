@echo off
rem Double-click launcher for setup_windows.ps1 (bypasses the PowerShell script policy for this run only).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
pause
