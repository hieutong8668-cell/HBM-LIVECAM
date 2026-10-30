[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$appRoot = Join-Path $env:LOCALAPPDATA 'Programs\HBM-LIVECAM'
$runtimeRoot = Join-Path $appRoot 'python'
$python = Join-Path $runtimeRoot 'python.exe'
$logPath = Join-Path $PSScriptRoot 'install.log'
$pythonVersion = '3.10.11'

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
    Add-Content -LiteralPath $logPath -Value "[$(Get-Date -Format o)] $Message" -Encoding UTF8
}

function Invoke-Download([string[]]$Urls, [string]$Destination) {
    foreach ($url in $Urls) {
        try {
            Write-Step "Dang tai $url"
            Invoke-WebRequest -Uri $url -OutFile $Destination -UseBasicParsing
            if ((Test-Path -LiteralPath $Destination) -and (Get-Item -LiteralPath $Destination).Length -gt 0) {
                return
            }
        } catch {
            Add-Content -LiteralPath $logPath -Value "Tai that bai: $url - $($_.Exception.Message)" -Encoding UTF8
        }
    }
    throw "Khong tai duoc tep phu tro: $([IO.Path]::GetFileName($Destination))"
}

function Test-Python310([string]$Executable) {
    if (-not (Test-Path -LiteralPath $Executable)) { return $false }
    $version = @(& $Executable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null) -join ''
    $pythonHeader = Join-Path (Split-Path -Parent $Executable) 'Include\Python.h'
    return ($LASTEXITCODE -eq 0 -and $version.Trim() -eq '3.10' -and (Test-Path -LiteralPath $pythonHeader))
}

function Find-SystemPython310 {
    $candidates = @()
    $cmd = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($cmd) {
        $v = @(& $cmd.Source '-3.10' -c "import sys; print(sys.executable)" 2>$null) -join ''
        if ($LASTEXITCODE -eq 0 -and $v.Trim()) { $candidates += $v.Trim() }
    }
    $cmd = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $candidates += @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310-64\python.exe'),
        'C:\Program Files\Python310\python.exe',
        'C:\Python310\python.exe'
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Python310 $candidate)) { return $candidate }
    }
    return $null
}

try {
    Set-Content -LiteralPath $logPath -Value "HBM-LIVECAM install - $(Get-Date -Format o)" -Encoding UTF8
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'HBM-LIVECAM yeu cau Windows 64-bit.' }

    Write-Step 'Cap nhat tep ung dung'
    New-Item -ItemType Directory -Path $appRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $PSScriptRoot -Force | Where-Object {
        $_.Name -notin @('.git', '__pycache__', 'support-cache', 'install.log', 'device-scan.json')
    } | Copy-Item -Destination $appRoot -Recurse -Force

    $systemPython = Find-SystemPython310
    if ($systemPython) {
        Write-Step "Su dung Python 3.10 co san: $systemPython"
        $python = $systemPython
        $runtimeRoot = Split-Path -Parent $python
    } elseif (-not (Test-Python310 $python)) {
        Write-Step 'Cai Python 3.10 day du rieng cho ung dung'
        if (Test-Path -LiteralPath $runtimeRoot) { Remove-Item -LiteralPath $runtimeRoot -Recurse -Force }
        $pythonPackage = Join-Path $env:TEMP "python-$pythonVersion-x64.nupkg"
        Invoke-Download @(
            "https://www.nuget.org/api/v2/package/python/$pythonVersion"
        ) $pythonPackage
        $pythonZip = Join-Path $env:TEMP "python-$pythonVersion-x64.zip"
        Copy-Item -LiteralPath $pythonPackage -Destination $pythonZip -Force
        $pythonExtract = Join-Path $env:TEMP "hbm-python-$pythonVersion"
        if (Test-Path -LiteralPath $pythonExtract) { Remove-Item -LiteralPath $pythonExtract -Recurse -Force }
        Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonExtract -Force
        $pythonTools = Join-Path $pythonExtract 'tools'
        if (-not (Test-Path -LiteralPath (Join-Path $pythonTools 'python.exe'))) {
            throw 'Goi Python 3.10 day du khong hop le.'
        }
        New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
        Get-ChildItem -LiteralPath $pythonTools -Force | Copy-Item -Destination $runtimeRoot -Recurse -Force
        if (-not (Test-Python310 $python)) {
            throw 'Khong tao duoc runtime Python 3.10 day du.'
        }
        & $python -m pip --version 2>$null
        if ($LASTEXITCODE -ne 0) {
            $getPip = Join-Path $env:TEMP 'hbm-get-pip.py'
            Invoke-Download @('https://bootstrap.pypa.io/get-pip.py') $getPip
            & $python $getPip --disable-pip-version-check
            if ($LASTEXITCODE -ne 0) { throw 'Khong cai duoc pip cho Python 3.10.' }
        }
    }

    Write-Step 'Tai va cai cac thu vien phu tro'
    & $python -m pip install --disable-pip-version-check --prefer-binary --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw 'Khong cap nhat duoc pip/setuptools/wheel.' }
    Write-Step 'Cai cong cu dung InsightFace'
    & $python -m pip install --disable-pip-version-check --prefer-binary 'numpy>=2.0,<3' 'Cython>=3' packaging
    if ($LASTEXITCODE -ne 0) { throw 'Khong cai duoc numpy/Cython.' }
    & $python -m pip install --disable-pip-version-check --no-build-isolation 'insightface==0.7.3'
    if ($LASTEXITCODE -ne 0) {
        Write-Step 'InsightFace can C++ Build Tools; dang kiem tra/cai bo bien dich'
        $buildTools = Join-Path $env:TEMP 'vs_BuildTools.exe'
        $vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
        $hasBuildTools = $false
        if (Test-Path -LiteralPath $vswhere) {
            $installations = @(& $vswhere -products Microsoft.VisualStudio.Product.BuildTools -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
            $hasBuildTools = ($LASTEXITCODE -eq 0 -and $installations.Count -gt 0)
        }
        if (-not $hasBuildTools) {
            Invoke-Download @('https://aka.ms/vs/17/release/vs_BuildTools.exe') $buildTools
            $process = Start-Process -FilePath $buildTools -ArgumentList @(
                '--quiet', '--wait', '--norestart',
                '--add', 'Microsoft.VisualStudio.Workload.VCTools', '--includeRecommended'
            ) -Wait -PassThru
            if ($process.ExitCode -notin @(0, 3010)) { throw "C++ Build Tools loi ma $($process.ExitCode)." }
        }
        & $python -m pip install --disable-pip-version-check --no-build-isolation 'insightface==0.7.3'
        if ($LASTEXITCODE -ne 0) { throw 'Khong dung duoc InsightFace sau khi da co numpy, Cython va C++ Build Tools.' }
    }
    & $python -m pip install --disable-pip-version-check --prefer-binary -r (Join-Path $appRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) {
        throw 'Cai cac thu vien Python con lai that bai.'
    }

    $appBin = Join-Path $appRoot 'bin'
    $ffmpeg = Join-Path $appBin 'ffmpeg.exe'
    if (-not (Test-Path -LiteralPath $ffmpeg)) {
        Write-Step 'Tai FFmpeg phu tro xu ly video'
        & $python -m pip install --disable-pip-version-check --prefer-binary imageio-ffmpeg
        if ($LASTEXITCODE -ne 0) { throw 'Khong tai duoc FFmpeg.' }
        $downloadedFfmpeg = @(& $python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())") -join ''
        if (-not (Test-Path -LiteralPath $downloadedFfmpeg.Trim())) { throw 'Khong tim thay FFmpeg sau khi tai.' }
        New-Item -ItemType Directory -Path $appBin -Force | Out-Null
        Copy-Item -LiteralPath $downloadedFfmpeg.Trim() -Destination $ffmpeg -Force
    }
    $env:PATH = "$appBin;$env:PATH"
    & $ffmpeg -version | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) { throw 'FFmpeg khong chay duoc.' }

    Write-Step 'Tu dong quet GPU va camera'
    Push-Location $appRoot
    try {
        & $python -m modules.post_install_scan
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { throw 'Quet thiet bi sau cai dat that bai.' }

    $commandsPath = Join-Path $appRoot 'INSTALL-COMMANDS.txt'
    @(
        'Cai dat lai:',
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\Setup-HBM-LIVECAM.ps1`"",
        '',
        'Khoi dong:',
        "`"$python`" `"$appRoot\run.py`" --execution-provider cuda",
        '',
        'Quet lai thiet bi:',
        "cd /d `"$appRoot`" && `"$python`" -m modules.post_install_scan"
    ) | Set-Content -LiteralPath $commandsPath -Encoding UTF8

    Write-Step 'Tao loi tat tren Desktop'
    $cmdContent = @"
@echo off
setlocal
cd /d "%~dp0"
title HBM-LIVECAM

set "APP_ROOT=%~dp0"
set "APP_PYTHON=$python"
set "PATH=%APP_ROOT%bin;%PATH%"

if not exist "%APP_PYTHON%" (
  echo [HBM-LIVECAM] Khong tim thay Python. Hay cai dat lai.
  pause
  exit /b 1
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
"@
    Set-Content -LiteralPath (Join-Path $appRoot 'HBM-LIVECAM.cmd') -Value $cmdContent -Encoding ASCII
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'HBM-LIVECAM.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appRoot 'HBM-LIVECAM.cmd'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = 'HBM-LIVECAM'
    $shortcut.Save()

    Write-Host "`nCai dat hoan tat: $appRoot" -ForegroundColor Green
    Write-Host "Bao cao thiet bi: $(Join-Path $appRoot 'device-scan.json')" -ForegroundColor Green
    Write-Host "Lenh cai dat/khoi dong: $commandsPath" -ForegroundColor Green
    exit 0
} catch {
    Add-Content -LiteralPath $logPath -Value "FAILED: $($_.Exception.Message)" -Encoding UTF8
    Write-Host "`nCai dat that bai: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

