@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scan-Host.ps1" -OutputPath "%~dp0host_profile.json"
if errorlevel 1 (echo Host scan failed. & pause & exit /b 1)
call "%~dp0Install-HBM-LIVECAM.cmd"
