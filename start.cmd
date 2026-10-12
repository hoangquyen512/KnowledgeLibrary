@echo off
REM Unified entrypoint: start local dev (API + Web hidden).
cd /d "%~dp0"
title Knowledge Library
echo Starting local dev (API/Web will run hidden)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-demo.ps1"
if errorlevel 1 pause
