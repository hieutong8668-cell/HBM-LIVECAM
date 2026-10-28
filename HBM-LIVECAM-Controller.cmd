@echo off
setlocal
cd /d "%~dp0"

echo [HBM-LIVECAM] Scanning host device...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scan-Host.ps1" -OutputPath "%~dp0host_profile.json"
if errorlevel 1 (
  echo Host scan failed.
  pause
  exit /b 1
)

echo [HBM-LIVECAM] Installing support files and runtime...
call "%~dp0Install-HBM-LIVECAM.cmd"
