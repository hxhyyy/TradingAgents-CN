[CmdletBinding()]
param(
    [switch]$InstallFrontendDeps,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$npmCmd = "npm.cmd"
$frontendLogDir = Join-Path $projectRoot "logs"
$backendOutLog = Join-Path $frontendLogDir "backend_stdout.log"
$backendErrLog = Join-Path $frontendLogDir "backend_stderr.log"
$frontendOutLog = Join-Path $frontendLogDir "frontend_stdout.log"
$frontendErrLog = Join-Path $frontendLogDir "frontend_stderr.log"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Get-PortProcess($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) {
        return $null
    }
    return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
}

function Ensure-PortAvailable($port, $friendlyName) {
    $proc = Get-PortProcess $port
    if (-not $proc) {
        return $null
    }

    # If the port is occupied by our own typical processes, auto-restart by default
    $isOwnProcess = $false
    if ($friendlyName -eq "Backend" -and ($proc.ProcessName -like "python*" -or $proc.ProcessName -like "uvicorn*")) {
        $isOwnProcess = $true
    } elseif ($friendlyName -eq "Frontend" -and $proc.ProcessName -eq "node") {
        $isOwnProcess = $true
    }

    if ($isOwnProcess -or $ForceRestart) {
        Write-Host "Stopping existing $friendlyName process on port ${port}: $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        Start-Sleep -Seconds 2
        return $null
    }

    # Port is occupied by some other app; do not kill automatically
    Write-Host "$friendlyName port $port is in use by $($proc.ProcessName) (PID $($proc.Id)). Use -ForceRestart to kill it, or free the port manually." -ForegroundColor Yellow
    return $proc
}

function Start-ServiceIfNeeded($serviceName, $displayName) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Host "$displayName service not found. Please install/start it manually." -ForegroundColor Yellow
        return
    }
    if ($service.Status -ne "Running") {
        Write-Host "Starting $displayName service..." -ForegroundColor Yellow
        Start-Service -Name $serviceName
        $service.WaitForStatus("Running", (New-TimeSpan -Seconds 20))
    }
    Write-Host "$displayName service is running." -ForegroundColor Green
}

function Wait-ForPort($port, $friendlyName, $timeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Get-PortProcess $port) {
            Write-Host "$friendlyName is listening on port $port." -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$friendlyName did not start listening on port $port within $timeoutSeconds seconds."
}

function Wait-ForBackend($port = 8000, $timeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    $healthUrl = "http://127.0.0.1:$port/api/health"
    Write-Host "Waiting for backend (cold start may take 60-90s due to data sync)..." -ForegroundColor DarkGray
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                Write-Host "Backend is ready at $healthUrl" -ForegroundColor Green
                return
            }
        } catch {
            # still starting
        }
        Start-Sleep -Seconds 2
    }
    throw "Backend did not become healthy within $timeoutSeconds seconds. Check logs\backend_stdout.log and logs\backend_stderr.log"
}

function Start-BackgroundProcess($filePath, $arguments, $workingDirectory, $stdoutLog, $stderrLog, $name) {
    if (Test-Path $stdoutLog) {
        Remove-Item $stdoutLog -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $stderrLog) {
        Remove-Item $stderrLog -Force -ErrorAction SilentlyContinue
    }

    $process = Start-Process `
        -FilePath $filePath `
        -ArgumentList $arguments `
        -WorkingDirectory $workingDirectory `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog

    if (-not $process) {
        throw "Failed to start $name."
    }

    Start-Sleep -Seconds 2
    if ($process.HasExited) {
        $stdout = if (Test-Path $stdoutLog) { Get-Content -Path $stdoutLog -Raw } else { "" }
        $stderr = if (Test-Path $stderrLog) { Get-Content -Path $stderrLog -Raw } else { "" }
        throw "$name exited immediately.`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
    }

    Write-Host "$name started with PID $($process.Id)." -ForegroundColor Green
}

Write-Host "TradingAgents local full-stack starter" -ForegroundColor Green
Write-Host "Project root: $projectRoot" -ForegroundColor DarkGray

if (-not (Test-Path $venvPython)) {
    throw "Python virtualenv not found: $venvPython"
}

if (-not (Test-Path $frontendRoot)) {
    throw "Frontend directory not found: $frontendRoot"
}

if (-not (Get-Command $npmCmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd not found. Please install Node.js first."
}

if (-not (Test-Path $frontendLogDir)) {
    New-Item -ItemType Directory -Path $frontendLogDir -Force | Out-Null
}

Write-Step "Ensuring local databases are running"
Start-ServiceIfNeeded -serviceName "MongoDB" -displayName "MongoDB"
Start-ServiceIfNeeded -serviceName "Redis" -displayName "Redis"

Write-Step "Checking application ports"
$existingBackend = Ensure-PortAvailable -port 8000 -friendlyName "Backend"
$existingFrontend = Ensure-PortAvailable -port 3000 -friendlyName "Frontend"

if ($InstallFrontendDeps -or -not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
    Write-Step "Installing frontend dependencies"
    & $npmCmd install --prefix $frontendRoot
    if ($LASTEXITCODE -ne 0) {
        throw "npm install failed in frontend."
    }
}

Set-Location $projectRoot

if (-not $existingBackend) {
    Write-Step "Starting backend"
    Start-BackgroundProcess `
        -filePath $venvPython `
        -arguments "-m app" `
        -workingDirectory $projectRoot `
        -stdoutLog $backendOutLog `
        -stderrLog $backendErrLog `
        -name "Backend"
} else {
    Write-Step "Backend already running"
}
Wait-ForBackend -port 8000 -timeoutSeconds 90

if (-not $existingFrontend) {
    Write-Step "Starting frontend"
    Start-BackgroundProcess `
        -filePath $npmCmd `
        -arguments "run dev -- --host 0.0.0.0 --port 3000" `
        -workingDirectory $frontendRoot `
        -stdoutLog $frontendOutLog `
        -stderrLog $frontendErrLog `
        -name "Frontend"
} else {
    Write-Step "Frontend already running"
}
Wait-ForPort -port 3000 -friendlyName "Frontend"

Write-Host ""
Write-Host "Startup complete." -ForegroundColor Green
Write-Host "Frontend:   http://localhost:3000" -ForegroundColor Cyan
Write-Host "Backend:    http://localhost:8000" -ForegroundColor Cyan
Write-Host "API docs:   http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "MongoDB:    localhost:27017" -ForegroundColor Cyan
Write-Host "Redis:      localhost:6379" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs:" -ForegroundColor White
Write-Host "  Backend out: $backendOutLog" -ForegroundColor DarkGray
Write-Host "  Backend err: $backendErrLog" -ForegroundColor DarkGray
Write-Host "  Frontend out: $frontendOutLog" -ForegroundColor DarkGray
Write-Host "  Frontend err: $frontendErrLog" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Tips:" -ForegroundColor White
Write-Host "  Re-run with -ForceRestart if ports 8000/3000 are already occupied." -ForegroundColor DarkGray
Write-Host "  Re-run with -InstallFrontendDeps to refresh frontend packages." -ForegroundColor DarkGray
