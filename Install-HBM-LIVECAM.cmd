@echo off
setlocal
cd /d "%~dp0"
title HBM-LIVECAM - Cai dat tu dong

echo [HBM-LIVECAM] Dang tai va cai cac thanh phan can thiet...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-HBM-LIVECAM.ps1"
if errorlevel 1 (
  echo.
  echo [HBM-LIVECAM] Cai dat that bai. Xem install.log trong thu muc nay.
  pause
  exit /b 1
)

echo.
echo [HBM-LIVECAM] Cai dat da hoan tat.
call "%~dp0HBM-LIVECAM.cmd"

