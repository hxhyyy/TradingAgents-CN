# Fix hypervisor boot settings for Docker Desktop (run as Administrator)
$log = "C:\hhx\rk3576\rk3576\TradingAgents\logs\fix-hypervisor-boot.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $log -Value $line -Encoding UTF8
}

Log "=== Before ==="
Log (bcdedit /enum "{current}" 2>&1 | Out-String)

$set = bcdedit /set hypervisorlaunchtype auto 2>&1 | Out-String
Log "bcdedit /set hypervisorlaunchtype auto => $set"

Log "=== After ==="
Log (bcdedit /enum "{current}" 2>&1 | Out-String)

Log "HyperVisorPresent=$( (Get-ComputerInfo).HyperVisorPresent )"
Log "Done. Reboot required."
