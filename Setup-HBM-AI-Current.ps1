[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$appRoot = Join-Path $env:LOCALAPPDATA 'Programs\HBM-AI-Current'
$runtimeRoot = Join-Path $appRoot 'python'
$venv = Join-Path $appRoot 'venv'
$installer = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
$pythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'

function Say([string]$Message) { Write-Host ''; Write-Host "==> $Message" -ForegroundColor Cyan }
function Fail([string]$Message) { throw $Message }
function Find-Python312Runtime {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'HBM-Beta\runtime\python312'),
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
    if (-not [Environment]::Is64BitOperatingSystem) { Fail 'Ứng dụng cần Windows 64-bit.' }
    New-Item -ItemType Directory -Path $appRoot -Force | Out-Null
    Say 'Sao chép ứng dụng vào thư mục riêng'
    Get-ChildItem -LiteralPath $PSScriptRoot -Force | Where-Object {
        $_.Name -notin @('Setup-HBM-AI-Current.ps1', 'Install-HBM-AI-Current.cmd', 'models')
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
            Say 'Runtime riêng hiện tại không hợp lệ; tạo lại từ runtime Python đã xác minh'
            Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        $sourceRuntime = Find-Python312Runtime
        if ($sourceRuntime) {
            Say 'Sao chép Python 3.12 đã xác minh vào runtime riêng của HBM AI'
            New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
            Get-ChildItem -LiteralPath $sourceRuntime -Force | Copy-Item -Destination $runtimeRoot -Recurse -Force
        } else {
            Say 'Tải Python 3.12.10 chính thức'
            Invoke-WebRequest -Uri $pythonUrl -OutFile $installer
            $sig = Get-AuthenticodeSignature -FilePath $installer
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
                Fail 'Chữ ký nhà phát hành Python không hợp lệ.'
            }
            $pyInstallArgs = '/quiet InstallAllUsers=0 "TargetDir={0}" PrependPath=0 Include_launcher=0 Include_test=0 Include_pip=1 Include_tcltk=1 Shortcuts=0' -f $runtimeRoot
            $p = Start-Process -FilePath $installer -ArgumentList $pyInstallArgs -Wait -PassThru
            if ($p.ExitCode -ne 0) { Fail "Python installer thoát với mã $($p.ExitCode)." }
        }
    }
    if (-not (Test-Path -LiteralPath $python)) { Fail 'Không tìm thấy Python riêng của ứng dụng.' }
    $runtimeProbe = @(& $python -c $probeCode 2>$null) -join ''
    if ($LASTEXITCODE -ne 0 -or $runtimeProbe -notmatch '^3\.12\|') {
        Fail 'Python riêng chưa đủ Python 3.12, pip và Tcl/Tk; chưa chạy tiếp cài thư viện.'
    }

    Say 'Tạo môi trường riêng và cài bộ xử lý CUDA gọn'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $python -m venv $venv
        if ($LASTEXITCODE -ne 0) { Fail 'Không tạo được môi trường Python riêng.' }
    }
    $vp = Join-Path $venv 'Scripts\python.exe'

    $requirementsArgs = @('-m', 'pip', 'install', '--prefer-binary')
    $localWheelhouse = Join-Path $env:LOCALAPPDATA 'HBM-Beta\app\beta\wheels'
    if (Test-Path -LiteralPath $localWheelhouse) {
        Say 'Dùng wheel tương thích đã có trên máy trước khi lấy phần còn thiếu'
        $requirementsArgs += @('--find-links', $localWheelhouse)
    }
    $requirementsArgs += @('-r', (Join-Path $appRoot 'requirements.txt'))
    & $vp @requirementsArgs
    if ($LASTEXITCODE -ne 0) { Fail 'Cài thư viện thất bại. Nếu lỗi ở InsightFace, cần Microsoft C++ Build Tools; xem log pip phía trên.' }

    Say 'Xác nhận ONNX Runtime nhận được GPU NVIDIA'
    & $vp -c "import onnxruntime as ort; ort.preload_dlls(); providers=ort.get_available_providers(); print('ORT',ort.__version__,'providers',providers); assert 'CUDAExecutionProvider' in providers"
    if ($LASTEXITCODE -ne 0) { Fail 'ONNX Runtime chưa nhận CUDA; không tạo lối tắt chạy.' }
    $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'HBM AI Current.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appRoot 'Run-HBM-AI-Current.cmd'
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = 'HBM AI Current — CUDA 13'
    $shortcut.Save()
    Write-Host ''; Write-Host "Cài xong: $shortcutPath" -ForegroundColor Green
} catch {
    Write-Host ''; Write-Host "Cài đặt dừng: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
