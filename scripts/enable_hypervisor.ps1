# Enable Windows virtualization features for Docker Desktop
$log = Join-Path (Split-Path $PSScriptRoot -Parent) "logs\enable-hypervisor.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $log -Value $line
    Write-Host $line
}

Log "Starting virtualization feature enablement..."

$features = @(
    "Microsoft-Windows-Subsystem-Linux",
    "VirtualMachinePlatform",
    "HypervisorPlatform"
)

foreach ($name in $features) {
    Log "Enabling $name ..."
    $out = dism.exe /online /enable-feature /featurename:$name /all /norestart 2>&1 | Out-String
    Log $out.Trim()
}

Log "--- Feature status ---"
$status = dism.exe /online /get-features /format:table 2>&1 | Out-String
foreach ($line in ($status -split "`n")) {
    if ($line -match "Hypervisor|VirtualMachine|Subsystem-Linux") {
        Log $line.Trim()
    }
}

Log "Done. A reboot is required for Hypervisor to become active."
