#Requires -Version 7.0
<#
.SYNOPSIS
    Local development: Meilisearch in Docker, the API and Vite on the host with hot reload.

.DESCRIPTION
    Starts the Meilisearch container if it is not already up, then runs uvicorn with reload and
    the Vite dev server as background jobs. Ctrl-C stops both; the container is left running.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv is required.' -ForegroundColor Red
    exit 1
}

if (Test-Path '.env') {
    foreach ($line in Get-Content '.env') {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            Set-Item -Path "env:$($Matches[1])" -Value $Matches[2].Trim('"')
        }
    }
}
$meiliPort = if ($env:MEILI_PORT) { $env:MEILI_PORT } else { '7700' }
$apiPort = if ($env:API_PORT) { $env:API_PORT } else { '8000' }
$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { '5173' }
$env:FOOD_API_MEILI_URL = "http://localhost:$meiliPort"
$env:FOOD_API_MEILI_MASTER_KEY = if ($env:MEILI_MASTER_KEY) { $env:MEILI_MASTER_KEY } else { 'devMasterKeyChangeMe' }

Write-Host '==> Ensuring Meilisearch is running' -ForegroundColor Cyan
docker compose up -d meilisearch

$jobs = @()
try {
    Write-Host "==> API on http://localhost:$apiPort (reload)" -ForegroundColor Cyan
    $jobs += Start-Job -Name 'api' -ScriptBlock {
        param($root, $port)
        Set-Location $root
        uv run --project backend uvicorn food_api.main:app --reload --reload-dir backend/src --host 127.0.0.1 --port $port
    } -ArgumentList $PWD.Path, $apiPort

    if ((Get-Command bun -ErrorAction SilentlyContinue) -and (Test-Path 'frontend/node_modules')) {
        Write-Host "==> Frontend on http://localhost:$frontendPort (hot reload)" -ForegroundColor Cyan
        $jobs += Start-Job -Name 'frontend' -ScriptBlock {
            param($root)
            Set-Location $root
            bun --cwd frontend run dev
        } -ArgumentList $PWD.Path
    } else {
        Write-Host '==> Frontend skipped. Run: bun install --cwd frontend' -ForegroundColor Yellow
    }

    while ($true) {
        $jobs | Receive-Job
        Start-Sleep -Milliseconds 500
    }
} finally {
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
}
