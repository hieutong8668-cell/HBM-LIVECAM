@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo HBM AI Current chua duoc cai dat. Hay chay Install-HBM-AI-Current.cmd.
  pause
  exit /b 1
)
"venv\Scripts\python.exe" run.py --execution-provider cuda
if errorlevel 1 pause
