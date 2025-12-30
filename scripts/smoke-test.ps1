# scripts/smoke-test.ps1
# Simple smoke tests for the prototype_3 stack.
# Usage: from project root run: .\scripts\smoke-test.ps1

param(
    [string]$FrontendUrl = 'http://localhost/',
    [string]$BackendUrl = 'http://localhost:8000/'
)

Write-Host "Running smoke tests against: Frontend=$FrontendUrl, Backend=$BackendUrl" -ForegroundColor Cyan

$errors = @()

function Check-Url {
    param($url, $name)
    try {
        $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 10
        Write-Host "[OK] $name returned HTTP 200" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[FAIL] $name at $url did not respond: $_" -ForegroundColor Red
        $global:errors += "$name: $url -> $_"
        return $false
    }
}

# Frontend (root)
Check-Url -url $FrontendUrl -name 'Frontend (root)'

# Backend (root) - depends on your backend, root should respond; else set /health if present
Check-Url -url $BackendUrl -name 'Backend (root)'

# API example: try a known endpoint if exists (adjust as necessary)
$apiTest = "$($BackendUrl.TrimEnd('/'))/api/docs"
Check-Url -url $apiTest -name 'Backend API docs (swagger)'

if ($errors.Count -eq 0) {
    Write-Host "\nAll smoke tests passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "\nSmoke tests found failures:" -ForegroundColor Yellow
    $errors | ForEach-Object { Write-Host $_ }
    exit 2
}
