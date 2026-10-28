[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$appRoot = Join-Path $env:LOCALAPPDATA 'Programs\HBM-LIVECAM'
$runtimeRoot = Join-Path $appRoot 'python'
$venv = Join-Path $appRoot 'venv'
$installer = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
$pythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'

function Say([string]$Message) { Write-Host ''; Write-Host "==> $Message" -ForegroundColor Cyan }
function Fail([string]$Message) { throw $Message }
function Find-Python312Runtime {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'HBM-LIVECAM\runtime\python312'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312')
    )
    $registryLocations = @(
        @{ Hive = [Microsoft.Win32.Registry]::CurrentUser; Path = 'Software\Python\PythonCore\3.12\InstallPath' },
        @{ Hive = [Microsoft.Win32.Registry]::LocalMachine; Path = 'Software\Python\PythonCore\3.12\InstallPath' }
    )
    foreach ($location in $registryLocations) {
        $key = $null
        try {
            $key = $location.Hive.OpenSubKey($location.Path)
            if ($key) {
                $installPath = [string]$key.GetValue('')
                $executablePath = [string]$key.GetValue('ExecutablePath')
                if ($installPath) { $candidates += $installPath }
                if ($executablePath) { $candidates += (Split-Path -Parent $executablePath) }
            }
        } finally {
            if ($key) { $key.Dispose() }
        }
    }

    $probeCode = "import sys, tkinter, pip; t=tkinter.Tcl(); print(str(sys.version_info.major)+'.'+str(sys.version_info.minor)+'|'+t.eval('info patchlevel'))"
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $candidatePython = Join-Path $candidate 'python.exe'
        if (-not (Test-Path -LiteralPath $candidatePython)) { continue }
        $probe = @(& $candidatePython -c $probeCode 2>$null) -join ''
        if ($LASTEXITCODE -eq 0 -and $probe -match '^3\.12\|') { return $candidate }
    }
    return $null
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { Fail '?ng d?ng c?n Windows 64-bit.' }
    New-Item -ItemType Directory -Path $appRoot -Force | Out-Null
    Say 'Sao chép ?ng d?ng vào th? m?c riêng'
    Get-ChildItem -LiteralPath $PSScriptRoot -Force | Where-Object {
        $_.Name -notin @('Setup-HBM-LIVECAM.ps1', 'Install-HBM-LIVECAM.cmd', 'models')
    } | Copy-Item -Destination $appRoot -Recurse -Force
    $sourceModels = Join-Path $PSScriptRoot 'models'
    $installedModels = Join-Path $appRoot 'models'
    New-Item -ItemType Directory -Path $installedModels -Force | Out-Null
    if (Test-Path -LiteralPath $sourceModels) {
        Get-ChildItem -LiteralPath $sourceModels -File -Recurse -Force | ForEach-Object {
            $relative = $_.FullName.Substring($sourceModels.Length).TrimStart('\')
            $destination = Join-Path $installedModels $relative
            if (-not (Test-Path -LiteralPath $destination)) {
                New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                Copy-Item -LiteralPath $_.FullName -Destination $destination
            }
        }
    }

    $python = Join-Path $runtimeRoot 'python.exe'
    $probeCode = "import sys, tkinter, pip; t=tkinter.Tcl(); print(str(sys.version_info.major)+'.'+str(sys.version_info.minor)+'|'+t.eval('info patchlevel'))"
    if (Test-Path -LiteralPath $python) {
        $runtimeProbe = @(& $python -c $probeCode 2>$null) -join ''
        if ($LASTEXITCODE -ne 0 -or $runtimeProbe -notmatch '^3\.12\|') {
            Say 'Runtime riêng hi?n t?i không h?p l?; t?o l?i t? runtime Python ?? x?c minh'
            Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        $sourceRuntime = Find-Python312Runtime
        if ($sourceRuntime) {
            Say 'Sao chép Python 3.12 ?? x?c minh vào runtime riêng c?a HBM AI'
            New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
            Get-ChildItem -LiteralPath $sourceRuntime -Force | Copy-Item -Destination $runtimeRoot -Recurse -Force
        } else {
            $localInstaller = Join-Path $PSScriptRoot 'python-3.12.10-amd64.exe'
            if (Test-Path -LiteralPath $localInstaller) {
                Say 'Dung bo cai Python 3.12.10 co san trong goi'
                $installer = $localInstaller
            } else {
                Say 'Tai Python 3.12.10 chinh thuc'
                $downloaded = $false
                for ($i = 0; $i -lt 3 -and -not $downloaded; $i++) {
                    try {
                        Invoke-WebRequest -Uri $pythonUrl -OutFile $installer -UseBasicParsing
                        $downloaded = $true
                    } catch {
                        Start-Sleep -Seconds 3
                    }
                }
                if (-not $downloaded) { Fail 'Khong tai duoc Python 3.12.10. Hay dat file python-3.12.10-amd64.exe vao thu muc goi va chay lai.' }
            }
            $sig = Get-AuthenticodeSignature -FilePath $installer
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
                Fail 'Ch? k? nhà ph?t hành Python không h?p l?.'
            }
            $pyInstallArgs = @('/quiet','InstallAllUsers=0',"TargetDir=$runtimeRoot",'PrependPath=0','Include_launcher=0','Include_test=0','Include_pip=1','Include_tcltk=1','Shortcuts=0')
            $p = Start-Process -FilePath $installer -ArgumentList $pyInstallArgs -Wait -PassThru
            if ($p.ExitCode -ne 0) { Fail "Python installer tho?t v?i m? $($p.ExitCode)." }
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        $found = Get-ChildItem -LiteralPath $runtimeRoot -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $python = $found.FullName }
    }
    if (-not (Test-Path -LiteralPath $python)) { Fail 'Khong tim thay Python rieng cua ung dung.' }
    $runtimeProbe = @(& $python -c $probeCode 2>$null) -join ''
    if ($LASTEXITCODE -ne 0 -or $runtimeProbe -notmatch '^3\.12\|') {
        Fail 'Python riêng ch?a ?? Python 3.12, pip và Tcl/Tk; ch?a ch?y ti?p cài th? vi?n.'
    }

    Say 'T?o môi tr??ng riêng và cài b? x? l? CUDA g?n'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $python -m venv $venv
        if ($LASTEXITCODE -ne 0) { Fail 'Không t?o ???c môi tr??ng Python riêng.' }
    }
    $vp = Join-Path $venv 'Scripts\python.exe'

    $requirementsArgs = @('-m', 'pip', 'install', '--prefer-binary')
    $localWheelhouse = Join-Path $env:LOCALAPPDATA 'HBM-LIVECAM\app\beta\wheels'
    if (Test-Path -LiteralPath $localWheelhouse) {
        Say 'Dùng wheel t??ng th?ch ?? c? trên m?y tr??c khi l?y ph?n c?n thi?u'
        $requirementsArgs += @('--find-links', $localWheelhouse)
    }
    $requirementsArgs += @('-r', (Join-Path $appRoot 'requirements.txt'))
    & $vp @requirementsArgs
    if ($LASTEXITCODE -ne 0) { Fail 'Cài th? vi?n th?t b?i. N?u l?i ? InsightFace, c?n Microsoft C++ Build Tools; xem log pip ph?a trên.' }

    Say 'X?c nh?n ONNX Runtime nh?n ???c GPU NVIDIA'
    & $vp -c "import onnxruntime as ort; ort.preload_dlls(); providers=ort.get_available_providers(); print('ORT',ort.__version__,'providers',providers); assert 'CUDAExecutionProvider' in providers"
    if ($LASTEXITCODE -ne 0) { Fail 'ONNX Runtime ch?a nh?n CUDA; không t?o l?i t?t ch?y.' }
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'HBM-LIVECAM.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appRoot 'Run-HBM-LIVECAM.cmd'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = 'HBM-LIVECAM — CUDA 13'
    $shortcut.Save()
    try { Start-Process -FilePath (Join-Path $appRoot 'Run-HBM-LIVECAM.cmd') } catch {}
    Write-Host ''; Write-Host "Cài xong: $shortcutPath" -ForegroundColor Green
} catch {
    Write-Host ''; Write-Host "Cài ??t d?ng: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
