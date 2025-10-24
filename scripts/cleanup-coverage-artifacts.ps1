# Coverage Artifacts Cleanup Script (PowerShell)
# Removes coverage files from git version control (they should be build artifacts only)

$ErrorActionPreference = "Continue"

Write-Host "[INFO] Cleaning up coverage artifacts from version control..." -ForegroundColor Cyan

$repoRoot = Split-Path -Parent $PSScriptRoot

# Ensure we are inside a git repository
Push-Location $repoRoot
try {
    git rev-parse --git-dir 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Not in a git repository" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Not in a git repository" -ForegroundColor Red
    exit 1
}

# Backend coverage artifacts
Write-Host ""
Write-Host "[SECTION] Backend: removing coverage artifacts tracked by git" -ForegroundColor Yellow
Push-Location "$repoRoot\backend-hormonia"

$filesToRemove = @(
    "coverage.json",
    "coverage.lcov",
    "test_results.txt"
)

foreach ($file in $filesToRemove) {
    if (Test-Path $file) {
        git rm --cached $file 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [REMOVED] $file" -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] $file not tracked (ok)" -ForegroundColor Gray
        }
    } else {
        Write-Host "  [MISSING] $file not found (ok)" -ForegroundColor Gray
    }
}

if (Test-Path "htmlcov") {
    git rm --cached -r htmlcov 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [REMOVED] htmlcov/" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] htmlcov/ not tracked (ok)" -ForegroundColor Gray
    }
} else {
    Write-Host "  [MISSING] htmlcov/ not found (ok)" -ForegroundColor Gray
}

Pop-Location

# Frontend coverage artifacts
Write-Host ""
Write-Host "[SECTION] Frontend: checking coverage artifacts" -ForegroundColor Yellow
Push-Location "$repoRoot\frontend-hormonia"

if (Test-Path "coverage") {
    git rm --cached -r coverage 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [REMOVED] coverage/" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] coverage/ already ignored (ok)" -ForegroundColor Gray
    }
} else {
    Write-Host "  [MISSING] coverage/ not found (ok)" -ForegroundColor Gray
}

if (Test-Path "test-results") {
    git rm --cached -r test-results 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [REMOVED] test-results/" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] test-results/ already ignored (ok)" -ForegroundColor Gray
    }
} else {
    Write-Host "  [MISSING] test-results/ not found (ok)" -ForegroundColor Gray
}

Pop-Location

# Quiz coverage artifacts
Write-Host ""
Write-Host "[SECTION] Quiz app: checking coverage artifacts" -ForegroundColor Yellow
Push-Location "$repoRoot\quiz-mensal-interface"

if (Test-Path "coverage") {
    git rm --cached -r coverage 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [REMOVED] coverage/" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] coverage/ already ignored (ok)" -ForegroundColor Gray
    }
} else {
    Write-Host "  [MISSING] coverage/ not found (ok)" -ForegroundColor Gray
}

Pop-Location
Pop-Location

Write-Host ""
Write-Host "[DONE] Coverage artifact cleanup completed." -ForegroundColor Green
Write-Host ""
Write-Host "[NEXT] Review changes with 'git status', then commit if they look correct." -ForegroundColor Cyan
Write-Host "[NOTE] Files remain on disk; only git tracking was removed." -ForegroundColor Gray
