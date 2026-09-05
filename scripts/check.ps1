#Requires -Version 7.0
<#
.SYNOPSIS
    Everything CI runs, in the same order, so a green local run means a green pipeline.

.EXAMPLE
    ./scripts/check.ps1
    Format check, lint, type check and tests (integration tests excluded).

.EXAMPLE
    ./scripts/check.ps1 -Fix
    Apply formatting and autofixable lint first.

.EXAMPLE
    ./scripts/check.ps1 -All
    Also run the integration tests. Requires Meilisearch to be running.
#>
[CmdletBinding()]
param(
    [switch]$Fix,
    [switch]$All
)

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')

$failed = [System.Collections.Generic.List[string]]::new()

$repoRoot = $PWD.Path

function Invoke-Check {
    param([string]$Name, [string]$Directory, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location (Join-Path $repoRoot $Directory)
    try { & $Body } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $failed.Add($Name) }
}

if ($Fix) {
    Write-Host "==> Formatting and autofixing" -ForegroundColor Cyan
    Push-Location (Join-Path $repoRoot 'backend')
    try {
        uv run ruff format src tests
        uv run ruff check --fix src tests
    } finally { Pop-Location }
}

# Every Python check runs with backend/ as the working directory: pytest resolves `testpaths`
# and the `tests` package relative to the rootdir it discovers, so running it from the repo
# root silently fails to import the test package.
Invoke-Check 'ruff format --check' 'backend' { uv run ruff format --check src tests }
Invoke-Check 'ruff check'          'backend' { uv run ruff check src tests }
Invoke-Check 'ty check'            'backend' { uv run ty check }

$pytestArgs = @('--cov=food_api', '--cov-report=term-missing', '--cov-fail-under=85')
if ($All) {
    Invoke-Check 'pytest (with integration)' 'backend' { uv run pytest @pytestArgs }
} else {
    Invoke-Check 'pytest' 'backend' { uv run pytest @pytestArgs -m "not integration" }
}

if ((Get-Command bun -ErrorAction SilentlyContinue) -and (Test-Path 'frontend/node_modules')) {
    Invoke-Check 'frontend typecheck' 'frontend' { bun run typecheck }
    Invoke-Check 'frontend lint'      'frontend' { bun run lint }
    Invoke-Check 'frontend tests'     'frontend' { bun run test }
} else {
    Write-Host ""
    Write-Host 'Skipping frontend checks (bun or frontend/node_modules missing).' -ForegroundColor Yellow
}

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host 'All checks passed.' -ForegroundColor Green
    exit 0
}
Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
exit 1
