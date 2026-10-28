param(
    [string]$OutputPath = "host_profile.json"
)

$ErrorActionPreference = "SilentlyContinue"

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$os = Get-CimInstance Win32_OperatingSystem
$gpus = Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion
$ramGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)

$nvidiaSmi = $null
try { $nvidiaSmi = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null } catch {}

$pythonCandidates = @()
foreach ($cmd in @("python","py")) {
    $p = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($p) { $pythonCandidates += $p.Source }
}

$profile = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    computer_name = $env:COMPUTERNAME
    os = [ordered]@{
        caption = $os.Caption
        version = $os.Version
        architecture = $os.OSArchitecture
    }
    cpu = [ordered]@{
        name = $cpu.Name
        cores = $cpu.NumberOfCores
        logical_processors = $cpu.NumberOfLogicalProcessors
    }
    memory = [ordered]@{
        total_gb = $ramGb
    }
    gpus = @($gpus | ForEach-Object {
        [ordered]@{
            name = $_.Name
            adapter_ram_bytes = $_.AdapterRAM
            driver_version = $_.DriverVersion
        }
    })
    nvidia_smi = if ($nvidiaSmi) { ($nvidiaSmi -join "`n") } else { $null }
    python = [ordered]@{
        commands = $pythonCandidates
    }
}

$profile | ConvertTo-Json -Depth 6 | Set-Content -Path $OutputPath -Encoding UTF8
Write-Host "Host profile written to $OutputPath"
