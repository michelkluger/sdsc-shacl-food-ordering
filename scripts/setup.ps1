#Requires -Version 7.0
<#
.SYNOPSIS
    One-command setup: check prerequisites, install dependencies, start Meilisearch, seed it.

.DESCRIPTION
    The PowerShell twin of scripts/setup.sh. Both are deliberately thin: everything with real
    logic lives in the `food-api` CLI (backend/src/food_api/cli.py), which is tested, so the two
    scripts cannot drift apart.

.EXAMPLE
    ./scripts/setup.ps1
    Backend and Meilisearch only, ready for ./scripts/dev.ps1

.EXAMPLE
    ./scripts/setup.ps1 -Full
    Also build and run the API and frontend containers.
#>
[CmdletBinding()]
param(
    [switch]$Full,
    [switch]$NoSeed
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$repoRoot = $PWD.Path

function Write-Step { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Message) Write-Host "  ok $Message" -ForegroundColor Green }
function Stop-With  { param([string]$Message) Write-Host "error: $Message" -ForegroundColor Red; exit 1 }

function Test-Requirement {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Stop-With "$Name is required but not on PATH. $Hint"
    }
}

Write-Step 'Checking prerequisites'
Test-Requirement 'docker' 'Install Docker Desktop: https://docs.docker.com/get-docker/'
Test-Requirement 'uv' 'Install uv: https://docs.astral.sh/uv/getting-started/installation/'
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Stop-With 'Docker Compose v2 is required (`docker compose`).' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Stop-With 'Docker is installed but not running. Start it and retry.' }
Write-Ok 'docker and uv found'

if (-not (Test-Path '.env')) {
    Write-Step 'Creating .env from .env.example'
    Copy-Item '.env.example' '.env'
    Write-Ok "wrote $repoRoot\.env"
}

# Load .env into the process so the CLI sees the same configuration as the containers.
foreach ($line in Get-Content '.env') {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
        Set-Item -Path "env:$($Matches[1])" -Value $Matches[2].Trim('"')
    }
}
$meiliPort = if ($env:MEILI_PORT) { $env:MEILI_PORT } else { '7700' }
$env:FOOD_API_MEILI_URL = "http://localhost:$meiliPort"
$env:FOOD_API_MEILI_MASTER_KEY = if ($env:MEILI_MASTER_KEY) { $env:MEILI_MASTER_KEY } else { 'devMasterKeyChangeMe' }

Write-Step 'Installing backend dependencies'
uv sync --project backend --frozen
if ($LASTEXITCODE -ne 0) { Stop-With 'uv sync failed.' }
Write-Ok 'backend environment ready'

Write-Step 'Starting Meilisearch'
docker compose up -d meilisearch
if ($LASTEXITCODE -ne 0) { Stop-With 'Could not start the Meilisearch container.' }
Write-Ok 'meilisearch container up'

Write-Step 'Waiting for Meilisearch and validating the dish corpus'
if ($NoSeed) {
    uv run --project backend food-api check
    if ($LASTEXITCODE -ne 0) { Stop-With 'The dish corpus did not load.' }
    uv run --project backend food-api wait-for-search --timeout 90
} else {
    uv run --project backend food-api bootstrap --timeout 90
}
if ($LASTEXITCODE -ne 0) { Stop-With 'Bootstrap failed.' }

$apiPort = if ($env:API_PORT) { $env:API_PORT } else { '8000' }
$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { '5173' }

if ($Full) {
    Write-Step 'Building and starting the API and frontend containers'
    docker compose up -d --build api frontend
    if ($LASTEXITCODE -ne 0) { Stop-With 'Could not start the stack.' }
    Write-Ok 'stack up'
    Write-Host ""
    Write-Host "  Frontend  http://localhost:$frontendPort"
    Write-Host "  API docs  http://localhost:$apiPort/api/docs"
} else {
    Write-Host ""
    Write-Host 'Setup complete.' -ForegroundColor Green
    Write-Host '  ./scripts/dev.ps1     run the API and the frontend on the host with reload'
    Write-Host '  ./scripts/check.ps1   format, lint, type-check and test'
}
Write-Host "  Meilisearch  http://localhost:$meiliPort"
