@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: Issue-License.cmd ^<device_id^>
  echo.
  echo Current device id:
  python issue_license.py
  pause
  exit /b 1
)

python issue_license.py %~1
pause
