<#
.SYNOPSIS
Runs the SpiderFoot E2E live system tests.

.DESCRIPTION
This script sets up the Python virtual environment (if it exists) and executes the Pytest E2E integration suite against the running Docker Compose stack.
#>

$ErrorActionPreference = "Stop"

# Ensure we are in the root directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootDir = (Resolve-Path "$scriptDir\..").Path
Set-Location $rootDir

Write-Host "Checking if Docker Compose stack is running..."
$apiStatus = docker compose ps -q api
if (-not $apiStatus) {
    Write-Warning "The 'api' container doesn't seem to be running. Please start the stack with 'docker compose up -d' first."
    exit 1
}

Write-Host "Running End-to-End Tests via Pytest..." -ForegroundColor Cyan

# Use virtual environment pytest if available, else fallback to global pytest
$pytestCmd = "pytest"
if (Test-Path ".\.venv\Scripts\pytest.exe") {
    $pytestCmd = ".\.venv\Scripts\pytest.exe"
} elseif (Test-Path ".\venv\Scripts\pytest.exe") {
    $pytestCmd = ".\venv\Scripts\pytest.exe"
}

# Run the test suite
& $pytestCmd test\e2e\test_live_system.py -v -s

if ($LASTEXITCODE -eq 0) {
    Write-Host "E2E Tests Passed Successfully!" -ForegroundColor Green
} else {
    Write-Host "E2E Tests Failed. See output above." -ForegroundColor Red
}

exit $LASTEXITCODE
