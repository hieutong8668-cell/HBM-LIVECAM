@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-HBM-AI-Current.ps1"
if errorlevel 1 (
  echo.
  echo Cai dat gap loi. Doc thong bao ben tren.
  pause
)
