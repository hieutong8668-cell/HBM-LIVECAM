@echo off
setlocal
cd /d "%~dp0"
title HBM-LIVECAM

set "APP_ROOT=%LOCALAPPDATA%\Programs\HBM-LIVECAM"
set "APP_PYTHON=%APP_ROOT%\python\python.exe"
set "PATH=%APP_ROOT%\bin;%PATH%"

if not exist "%APP_PYTHON%" (
  echo [HBM-LIVECAM] Lan dau khoi dong - dang tu dong cai dat...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-HBM-LIVECAM.ps1"
  if errorlevel 1 (
    echo.
    echo [HBM-LIVECAM] Cai dat that bai. Xem file install.log.
    pause
    exit /b 1
  )
)

echo [HBM-LIVECAM] Dang quet thiet bi...
pushd "%APP_ROOT%"
"%APP_PYTHON%" -m modules.post_install_scan
popd

echo [HBM-LIVECAM] Dang mo ung dung...
cd /d "%APP_ROOT%"
"%APP_PYTHON%" run.py --execution-provider cuda
if errorlevel 1 (
  echo.
  echo [HBM-LIVECAM] Ung dung da dung voi loi %errorlevel%.
  pause
  exit /b %errorlevel%
)

