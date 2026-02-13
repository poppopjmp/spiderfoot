<# 
.SYNOPSIS
    Run SpiderFoot locally in microservice mode (Windows)

.DESCRIPTION
    Starts SpiderFoot API + WebUI as separate processes.
    WebUI runs in API proxy mode (SF_WEBUI_API_MODE=true).

.EXAMPLE
    .\scripts\run_microservices.ps1
    .\scripts\run_microservices.ps1 -ApiPort 9001
    .\scripts\run_microservices.ps1 -ApiOnly
    .\scripts\run_microservices.ps1 -Debug
#>

param(
    [int]$ApiPort = 8001,
    [int]$WebUiPort = 5001,
    [string]$Host = "127.0.0.1",
    [switch]$ApiOnly,
    [switch]$WebUiOnly,
    [switch]$Debug
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$LogLevel = if ($Debug) { "DEBUG" } else { "INFO" }
$ApiUrl = "http://${Host}:${ApiPort}/api"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       SpiderFoot — Local Microservice Mode               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$Processes = @()

try {
    # ── Start API ──
    if (-not $WebUiOnly) {
        Write-Host "  ▶ Starting API server on ${Host}:${ApiPort}" -ForegroundColor Blue

        $env:SF_SERVICE = "api"
        $env:SF_API_HOST = $Host
        $env:SF_API_PORT = $ApiPort
        $env:SF_API_WORKERS = "1"
        $env:SF_LOG_LEVEL = $LogLevel
        $env:SF_DEPLOYMENT_MODE = "microservice"
        $env:SF_SERVICE_ROLE = "api"

        $ApiProc = Start-Process -FilePath python -ArgumentList @(
            "-m", "spiderfoot.service_runner",
            "--service", "api",
            "--port", $ApiPort,
            "--log-level", $LogLevel
        ) -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow
        $Processes += $ApiProc

        # Wait for API health
        Write-Host "  ⏳ Waiting for API..." -ForegroundColor Yellow -NoNewline
        $Ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            try {
                $null = Invoke-RestMethod -Uri "http://${Host}:${ApiPort}/healthz" -TimeoutSec 2 -ErrorAction Stop
                $Ready = $true
                break
            } catch {
                Start-Sleep -Seconds 1
                Write-Host "." -NoNewline
            }
        }
        if ($Ready) {
            Write-Host " ✓ ready" -ForegroundColor Green
        } else {
            # Try /api/docs as fallback
            try {
                $null = Invoke-WebRequest -Uri "http://${Host}:${ApiPort}/api/docs" -TimeoutSec 3 -ErrorAction Stop
                Write-Host " ✓ ready" -ForegroundColor Green
            } catch {
                Write-Host " ✗ timeout (may still be starting)" -ForegroundColor Yellow
            }
        }
    }

    # ── Start WebUI ──
    if (-not $ApiOnly) {
        Write-Host "  ▶ Starting WebUI on ${Host}:${WebUiPort} (API proxy → $ApiUrl)" -ForegroundColor Blue

        $env:SF_SERVICE = "webui"
        $env:SF_WEB_HOST = $Host
        $env:SF_WEB_PORT = $WebUiPort
        $env:SF_LOG_LEVEL = $LogLevel
        $env:SF_WEBUI_API_MODE = "true"
        $env:SF_WEBUI_API_URL = $ApiUrl
        $env:SF_DEPLOYMENT_MODE = "microservice"
        $env:SF_SERVICE_ROLE = "webui"

        $WebUiProc = Start-Process -FilePath python -ArgumentList @(
            "-m", "spiderfoot.service_runner",
            "--service", "webui",
            "--port", $WebUiPort,
            "--log-level", $LogLevel
        ) -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow
        $Processes += $WebUiProc

        Start-Sleep -Seconds 3
    }

    # ── Summary ──
    Write-Host ""
    Write-Host ("=" * 58) -ForegroundColor Green
    Write-Host "  SpiderFoot Microservice Mode — Running" -ForegroundColor Green
    Write-Host ("=" * 58) -ForegroundColor Green
    if (-not $WebUiOnly) {
        Write-Host "  API Server:   http://${Host}:${ApiPort}" -ForegroundColor Cyan
        Write-Host "  API Docs:     http://${Host}:${ApiPort}/api/docs" -ForegroundColor Cyan
    }
    if (-not $ApiOnly) {
        Write-Host "  Web UI:       http://${Host}:${WebUiPort}" -ForegroundColor Cyan
        Write-Host "  Mode:         API Proxy (WebUI → API → DB)" -ForegroundColor Cyan
    }
    Write-Host "  Log Level:    $LogLevel" -ForegroundColor Cyan
    Write-Host ("=" * 58) -ForegroundColor Green
    Write-Host ""
    Write-Host "  Press Ctrl+C to stop all services." -ForegroundColor White
    Write-Host ""

    # ── Wait ──
    while ($true) {
        foreach ($p in $Processes) {
            if ($p.HasExited) {
                Write-Host "  ✗ Process $($p.Id) exited with code $($p.ExitCode)" -ForegroundColor Red
                throw "Service process died"
            }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host ""
    Write-Host "  ⏹ Shutting down..." -ForegroundColor Yellow
    foreach ($p in $Processes) {
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "  ✓ All services stopped." -ForegroundColor Green

    # Clean up env vars
    Remove-Item Env:\SF_SERVICE -ErrorAction SilentlyContinue
    Remove-Item Env:\SF_WEBUI_API_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:\SF_WEBUI_API_URL -ErrorAction SilentlyContinue
    Remove-Item Env:\SF_DEPLOYMENT_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:\SF_SERVICE_ROLE -ErrorAction SilentlyContinue
}
