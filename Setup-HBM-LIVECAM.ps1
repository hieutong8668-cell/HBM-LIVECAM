[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$appRoot = Join-Path $env:LOCALAPPDATA 'Programs\HBM-LIVECAM'
    if (Test-Path -LiteralPath $appRoot) { Remove-Item -LiteralPath $appRoot -Recurse -Force -ErrorAction SilentlyContinue }
$runtimeRoot = Join-Path $appRoot 'python'
$venv = Join-Path $appRoot 'venv'
$installer = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
$pythonUrls = @('https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe','https://mirrors.huaweicloud.com/python/3.12.10/python-3.12.10-amd64.exe')

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

    $probeCode = "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"
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
    Say 'Sao chط·آ£ط¢آ©p ?ng d?ng vط·آ£ط¢آ o th? m?c riط·آ£ط¹آ¾ng'
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
    $probeCode = "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"
    if (Test-Path -LiteralPath $python) {
        $runtimeProbe = @(& $python -c $probeCode 2>$null) -join ''
        if ($LASTEXITCODE -ne 0 -or $runtimeProbe -notmatch '^3\.12') {
            Say 'Runtime riط·آ£ط¹آ¾ng hi?n t?i khط·آ£ط¢آ´ng h?p l?; t?o l?i t? runtime Python ?? x?c minh'
            Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        $sourceRuntime = Find-Python312Runtime
        if ($sourceRuntime) {
            Say 'Sao chط·آ£ط¢آ©p Python 3.12 ?? x?c minh vط·آ£ط¢آ o runtime riط·آ£ط¹آ¾ng c?a HBM AI'
            New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
            Get-ChildItem -LiteralPath $sourceRuntime -Force | Copy-Item -Destination $runtimeRoot -Recurse -Force
        } else {
            New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
            $localInstaller = Join-Path $PSScriptRoot 'python-3.12.10-amd64.exe'
            if (Test-Path -LiteralPath $localInstaller) {
                Say 'Dung bo cai Python 3.12.10 co san trong goi'
                $installer = $localInstaller
            } else {
                Say 'Tai Python 3.12.10 embedded'
                $zipUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
                $zipFile = Join-Path $env:TEMP 'python-3.12.10-embed-amd64.zip'
                $downloaded = $false
                try {
                    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
                    $downloaded = $true
                } catch {
                    $downloaded = $false
                }
                if (-not $downloaded) { Fail 'Khong tai duoc Python 3.12.10 embedded.' }
                if (Test-Path -LiteralPath $runtimeRoot) { Remove-Item -LiteralPath $runtimeRoot -Recurse -Force }
                New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
                Expand-Archive -Path $zipFile -DestinationPath $runtimeRoot -Force
                $getPip = Join-Path $env:TEMP 'get-pip.py'
                $pthFile = Join-Path $runtimeRoot 'python312._pth'
                if (Test-Path -LiteralPath $pthFile) { (Get-Content $pthFile) -replace '#import site','import site' | Set-Content $pthFile }
                Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getPip -UseBasicParsing
                & (Join-Path $runtimeRoot 'python.exe') $getPip
            }
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        $found = Get-ChildItem -LiteralPath $runtimeRoot -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $python = $found.FullName }
    }
    if (-not (Test-Path -LiteralPath $python)) { Fail 'Khong tim thay Python rieng cua ung dung.' }
    $runtimeProbe = @(& $python -c $probeCode 2>$null) -join ''
    if ($LASTEXITCODE -ne 0 -or $runtimeProbe -notmatch '^3\.12') {
        Fail 'Python riط·آ£ط¹آ¾ng ch?a ?? Python 3.12, pip vط·آ£ط¢آ  Tcl/Tk; ch?a ch?y ti?p cط·آ£ط¢آ i th? vi?n.'
    }

    Say 'T?o mط·آ£ط¢آ´i tr??ng riط·آ£ط¹آ¾ng vط·آ£ط¢آ  cط·آ£ط¢آ i b? x? l? CUDA g?n'
    $vp = $python  # embedded python, no venv
    #
    #
    #
    #
    #

    & $vp -m pip install --prefer-binary numpy Cython setuptools wheel
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
        Fail 'Thieu Microsoft C++ Build Tools. Hay cai Build Tools (Desktop development with C++) roi chay lai.'
    }
    $requirementsArgs = @('-m', 'pip', 'install', '--prefer-binary')
    $localWheelhouse = Join-Path $env:LOCALAPPDATA 'HBM-LIVECAM\app\beta\wheels'
    if (Test-Path -LiteralPath $localWheelhouse) {
        Say 'Dط·آ£ط¢آ¹ng wheel t??ng th?ch ?? c? trط·آ£ط¹آ¾n m?y tr??c khi l?y ph?n c?n thi?u'
        $requirementsArgs += @('--find-links', $localWheelhouse)
    }
    $requirementsArgs += @('-r', (Join-Path $appRoot 'requirements.txt'))
    & $vp @requirementsArgs
    if ($LASTEXITCODE -ne 0) { Fail 'Cط·آ£ط¢آ i th? vi?n th?t b?i. N?u l?i ? InsightFace, c?n Microsoft C++ Build Tools; xem log pip ph?a trط·آ£ط¹آ¾n.' }

    Say 'X?c nh?n ONNX Runtime nh?n ???c GPU NVIDIA'
    & $vp -c "import onnxruntime as ort; ort.preload_dlls(); providers=ort.get_available_providers(); print('ORT',ort.__version__,'providers',providers); assert 'CUDAExecutionProvider' in providers"
    if ($LASTEXITCODE -ne 0) { Fail 'ONNX Runtime ch?a nh?n CUDA; khط·آ£ط¢آ´ng t?o l?i t?t ch?y.' }
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'HBM-LIVECAM.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appRoot 'Run-HBM-LIVECAM.cmd'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = 'HBM-LIVECAM CUDA 13'
    $shortcut.Save()
    Write-Host ''; Write-Host "Cط·آ£ط¢آ i xong: $shortcutPath" -ForegroundColor Green
} catch {
    Write-Host ''; Write-Host "Cط·آ£ط¢آ i ??t d?ng: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

