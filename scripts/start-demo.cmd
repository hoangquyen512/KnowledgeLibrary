@echo off
REM Start local demo without needing PowerShell ExecutionPolicy changes.
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1"
if errorlevel 1 pause
