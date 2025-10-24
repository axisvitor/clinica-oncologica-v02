# Release Validation Script
# Runs all tests, checks coverage, and validates deployment readiness

param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$SkipQuiz,
    [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$reportDir = "$repoRoot\validation-reports\$timestamp"

# Create report directory
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

Write-Host "

          RELEASE VALIDATION - HORMONIA SYSTEM               
         Timestamp: $timestamp                    

" -ForegroundColor Cyan

$validationResults = @{
    Backend = @{ Status = "SKIPPED"; Coverage = 0; Errors = @() }
    Frontend = @{ Status = "SKIPPED"; Coverage = 0; Errors = @() }
    Quiz = @{ Status = "SKIPPED"; Coverage = 0; Errors = @() }
    E2E = @{ Status = "SKIPPED"; Tests = 0; Errors = @() }
}

# ============================================================================
# BACKEND VALIDATION
# ============================================================================
if (-not $SkipBackend) {
    Write-Host "`n" -ForegroundColor Yellow
    Write-Host "   BACKEND VALIDATION (FastAPI + PostgreSQL + Redis)" -ForegroundColor Yellow
    Write-Host "`n" -ForegroundColor Yellow
    
    Push-Location "$repoRoot\backend-hormonia"
    
    try {
        Write-Host " Running pytest with coverage..." -ForegroundColor Cyan

        $output = @()
        $exitCode = 1

        $makeCmd = Get-Command make -ErrorAction SilentlyContinue
        if ($makeCmd) {
            $output = & make test-cov 2>&1
            $exitCode = $LASTEXITCODE
        } else {
            $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
            if (-not $pythonCmd) {
                $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
            }

            if (-not $pythonCmd) {
                throw "Python n�o encontrado no PATH e 'make' indispon�vel. Instale Python ou disponibilize o comando make."
            }

            $pytestArgs = @(
                "-m", "pytest",
                "--cov=app",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-report=json:coverage.json",
                "--cov-report=lcov:coverage.lcov"
            )

            $output = & $pythonCmd.Source $pytestArgs 2>&1
            $exitCode = $LASTEXITCODE
        }
        
        # Save output
        $output | Out-File "$reportDir\backend-test-output.txt"
        
        if ($exitCode -eq 0) {
            Write-Host " Backend tests PASSED" -ForegroundColor Green
            $validationResults.Backend.Status = "PASSED"
            
            # Extract coverage percentage
            $coverageLine = $output | Select-String -Pattern "TOTAL.*?(\d+)%" | Select-Object -First 1
            if ($coverageLine) {
                $coverageMatch = [regex]::Match($coverageLine, "(\d+)%")
                if ($coverageMatch.Success) {
                    $coverage = [int]$coverageMatch.Groups[1].Value
                    $validationResults.Backend.Coverage = $coverage
                    
                    if ($coverage -ge 80) {
                        Write-Host " Coverage: $coverage% (80% threshold MET)" -ForegroundColor Green
                    } else {
                        Write-Host "  Coverage: $coverage% (BELOW 80% threshold)" -ForegroundColor Yellow
                        $validationResults.Backend.Status = "WARNING"
                        $validationResults.Backend.Errors += "Coverage below 80%"
                    }
                }
            }
            
            # Copy HTML report
            if (Test-Path "htmlcov\index.html") {
                Copy-Item -Recurse "htmlcov" "$reportDir\backend-coverage-html"
                Write-Host " Coverage report: $reportDir\backend-coverage-html\index.html" -ForegroundColor Cyan
            }
        } else {
            Write-Host " Backend tests FAILED" -ForegroundColor Red
            $validationResults.Backend.Status = "FAILED"
            $validationResults.Backend.Errors += "Test suite failed with exit code $exitCode"
        }
        
    } catch {
        Write-Host " Error running backend tests: $_" -ForegroundColor Red
        $validationResults.Backend.Status = "ERROR"
        $validationResults.Backend.Errors += $_.Exception.Message
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n  Skipping backend validation (--SkipBackend)" -ForegroundColor Gray
}

# ============================================================================
# FRONTEND VALIDATION
# ============================================================================
if (-not $SkipFrontend) {
    Write-Host "`n" -ForegroundColor Yellow
    Write-Host "    FRONTEND VALIDATION (React 19 + Vite + Vitest)" -ForegroundColor Yellow
    Write-Host "`n" -ForegroundColor Yellow
    
    Push-Location "$repoRoot\frontend-hormonia"
    
    try {
        Write-Host " Running quality checks (lint + typecheck + test)..." -ForegroundColor Cyan
        
        # Run quality script (includes all checks)
        $output = & npm run quality 2>&1
        $exitCode = $LASTEXITCODE
        
        # Save output
        $output | Out-File "$reportDir\frontend-quality-output.txt"
        
        if ($exitCode -eq 0) {
            Write-Host " Frontend quality checks PASSED" -ForegroundColor Green
            $validationResults.Frontend.Status = "PASSED"
            
            # Extract coverage if available
            if (Test-Path "coverage\coverage-summary.json") {
                $coverageData = Get-Content "coverage\coverage-summary.json" | ConvertFrom-Json
                $totalCoverage = [math]::Round($coverageData.total.statements.pct, 2)
                $validationResults.Frontend.Coverage = $totalCoverage
                
                if ($totalCoverage -ge 80) {
                    Write-Host " Coverage: $totalCoverage% (80% threshold MET)" -ForegroundColor Green
                } else {
                    Write-Host "  Coverage: $totalCoverage% (BELOW 80% threshold)" -ForegroundColor Yellow
                    $validationResults.Frontend.Status = "WARNING"
                    $validationResults.Frontend.Errors += "Coverage below 80%"
                }
                
                # Copy coverage report
                Copy-Item -Recurse "coverage" "$reportDir\frontend-coverage-html"
                Write-Host " Coverage report: $reportDir\frontend-coverage-html\index.html" -ForegroundColor Cyan
            }
        } else {
            Write-Host " Frontend quality checks FAILED" -ForegroundColor Red
            $validationResults.Frontend.Status = "FAILED"
            $validationResults.Frontend.Errors += "Quality checks failed with exit code $exitCode"
        }
        
    } catch {
        Write-Host " Error running frontend tests: $_" -ForegroundColor Red
        $validationResults.Frontend.Status = "ERROR"
        $validationResults.Frontend.Errors += $_.Exception.Message
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n  Skipping frontend validation (--SkipFrontend)" -ForegroundColor Gray
}

# ============================================================================
# QUIZ APP VALIDATION
# ============================================================================
if (-not $SkipQuiz) {
    Write-Host "`n" -ForegroundColor Yellow
    Write-Host "   QUIZ APP VALIDATION (Next.js 14 + Jest)" -ForegroundColor Yellow
    Write-Host "`n" -ForegroundColor Yellow
    
    Push-Location "$repoRoot\quiz-mensal-interface"
    
    try {
        Write-Host " Running tests with coverage..." -ForegroundColor Cyan
        
        # Run coverage tests
        $output = & pnpm test:coverage 2>&1
        $exitCode = $LASTEXITCODE
        
        # Save output
        $output | Out-File "$reportDir\quiz-test-output.txt"
        
        if ($exitCode -eq 0) {
            Write-Host " Quiz tests PASSED" -ForegroundColor Green
            $validationResults.Quiz.Status = "PASSED"
            
            # Copy coverage report if exists
            if (Test-Path "coverage") {
                Copy-Item -Recurse "coverage" "$reportDir\quiz-coverage-html"
                Write-Host " Coverage report: $reportDir\quiz-coverage-html\index.html" -ForegroundColor Cyan
            }
        } else {
            Write-Host " Quiz tests FAILED" -ForegroundColor Red
            $validationResults.Quiz.Status = "FAILED"
            $validationResults.Quiz.Errors += "Test suite failed with exit code $exitCode"
        }
        
    } catch {
        Write-Host " Error running quiz tests: $_" -ForegroundColor Red
        $validationResults.Quiz.Status = "ERROR"
        $validationResults.Quiz.Errors += $_.Exception.Message
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n  Skipping quiz validation (--SkipQuiz)" -ForegroundColor Gray
}

# ============================================================================
# E2E SMOKE TESTS
# ============================================================================
if (-not $SkipE2E) {
    Write-Host "`n" -ForegroundColor Yellow
    Write-Host "   E2E SMOKE TESTS (Playwright)" -ForegroundColor Yellow
    Write-Host "`n" -ForegroundColor Yellow
    
    Push-Location "$repoRoot\frontend-hormonia"
    
    try {
        Write-Host " Running Playwright smoke tests..." -ForegroundColor Cyan
        
        # Run smoke tests
        $output = & npm run test:e2e:smoke 2>&1
        $exitCode = $LASTEXITCODE
        
        # Save output
        $output | Out-File "$reportDir\e2e-smoke-output.txt"
        
        if ($exitCode -eq 0) {
            Write-Host " E2E smoke tests PASSED" -ForegroundColor Green
            $validationResults.E2E.Status = "PASSED"
            
            # Count tests
            $testCount = ($output | Select-String -Pattern "(\d+) passed" | Select-Object -First 1)
            if ($testCount) {
                $match = [regex]::Match($testCount, "(\d+) passed")
                if ($match.Success) {
                    $validationResults.E2E.Tests = [int]$match.Groups[1].Value
                    Write-Host " Tests passed: $($validationResults.E2E.Tests)" -ForegroundColor Green
                }
            }
        } else {
            Write-Host " E2E smoke tests FAILED" -ForegroundColor Red
            $validationResults.E2E.Status = "FAILED"
            $validationResults.E2E.Errors += "Smoke tests failed with exit code $exitCode"
        }
        
        # Copy Playwright report if exists
        if (Test-Path "playwright-report") {
            Copy-Item -Recurse "playwright-report" "$reportDir\e2e-report"
            Write-Host " E2E report: $reportDir\e2e-report\index.html" -ForegroundColor Cyan
        }
        
    } catch {
        Write-Host " Error running E2E tests: $_" -ForegroundColor Red
        $validationResults.E2E.Status = "ERROR"
        $validationResults.E2E.Errors += $_.Exception.Message
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n  Skipping E2E validation (--SkipE2E)" -ForegroundColor Gray
}

# ============================================================================
# FINAL REPORT
# ============================================================================
Write-Host "`n

                     VALIDATION SUMMARY                       

" -ForegroundColor Cyan

# Backend
$backendSymbol = switch ($validationResults.Backend.Status) {
    "PASSED" { ""; Break }
    "WARNING" { " "; Break }
    "FAILED" { ""; Break }
    "ERROR" { ""; Break }
    default { " "; Break }
}
Write-Host "Backend Tests:     $backendSymbol $($validationResults.Backend.Status) (Coverage: $($validationResults.Backend.Coverage)%)" -ForegroundColor $(if ($validationResults.Backend.Status -eq "PASSED") { "Green" } elseif ($validationResults.Backend.Status -eq "WARNING") { "Yellow" } else { "Red" })
if ($validationResults.Backend.Errors.Count -gt 0) {
    foreach ($error in $validationResults.Backend.Errors) {
        Write-Host "   $error" -ForegroundColor Red
    }
}

# Frontend
$frontendSymbol = switch ($validationResults.Frontend.Status) {
    "PASSED" { ""; Break }
    "WARNING" { " "; Break }
    "FAILED" { ""; Break }
    "ERROR" { ""; Break }
    default { " "; Break }
}
Write-Host "Frontend Tests:    $frontendSymbol $($validationResults.Frontend.Status) (Coverage: $($validationResults.Frontend.Coverage)%)" -ForegroundColor $(if ($validationResults.Frontend.Status -eq "PASSED") { "Green" } elseif ($validationResults.Frontend.Status -eq "WARNING") { "Yellow" } else { "Red" })
if ($validationResults.Frontend.Errors.Count -gt 0) {
    foreach ($error in $validationResults.Frontend.Errors) {
        Write-Host "   $error" -ForegroundColor Red
    }
}

# Quiz
$quizSymbol = switch ($validationResults.Quiz.Status) {
    "PASSED" { ""; Break }
    "WARNING" { " "; Break }
    "FAILED" { ""; Break }
    "ERROR" { ""; Break }
    default { " "; Break }
}
Write-Host "Quiz Tests:        $quizSymbol $($validationResults.Quiz.Status)" -ForegroundColor $(if ($validationResults.Quiz.Status -eq "PASSED") { "Green" } elseif ($validationResults.Quiz.Status -eq "WARNING") { "Yellow" } else { "Red" })
if ($validationResults.Quiz.Errors.Count -gt 0) {
    foreach ($error in $validationResults.Quiz.Errors) {
        Write-Host "   $error" -ForegroundColor Red
    }
}

# E2E
$e2eSymbol = switch ($validationResults.E2E.Status) {
    "PASSED" { ""; Break }
    "WARNING" { " "; Break }
    "FAILED" { ""; Break }
    "ERROR" { ""; Break }
    default { " "; Break }
}
Write-Host "E2E Smoke Tests:   $e2eSymbol $($validationResults.E2E.Status) ($($validationResults.E2E.Tests) tests)" -ForegroundColor $(if ($validationResults.E2E.Status -eq "PASSED") { "Green" } elseif ($validationResults.E2E.Status -eq "WARNING") { "Yellow" } else { "Red" })
if ($validationResults.E2E.Errors.Count -gt 0) {
    foreach ($error in $validationResults.E2E.Errors) {
        Write-Host "   $error" -ForegroundColor Red
    }
}

Write-Host "`n Reports saved to: $reportDir" -ForegroundColor Cyan

# Save JSON report
$validationResults | ConvertTo-Json -Depth 3 | Out-File "$reportDir\validation-summary.json"

# Overall verdict
$allPassed = ($validationResults.Backend.Status -in @("PASSED", "WARNING", "SKIPPED")) -and
             ($validationResults.Frontend.Status -in @("PASSED", "WARNING", "SKIPPED")) -and
             ($validationResults.Quiz.Status -in @("PASSED", "WARNING", "SKIPPED")) -and
             ($validationResults.E2E.Status -in @("PASSED", "WARNING", "SKIPPED"))

$hasFailures = ($validationResults.Backend.Status -in @("FAILED", "ERROR")) -or
               ($validationResults.Frontend.Status -in @("FAILED", "ERROR")) -or
               ($validationResults.Quiz.Status -in @("FAILED", "ERROR")) -or
               ($validationResults.E2E.Status -in @("FAILED", "ERROR"))

$hasWarnings = ($validationResults.Backend.Status -eq "WARNING") -or
               ($validationResults.Frontend.Status -eq "WARNING")

Write-Host "`n`n" -ForegroundColor Cyan

if ($hasFailures) {
    Write-Host " VALIDATION FAILED - DO NOT DEPLOY TO PRODUCTION" -ForegroundColor Red
    Write-Host "   Fix all errors before proceeding with release.`n" -ForegroundColor Red
    exit 1
} elseif ($hasWarnings) {
    Write-Host "  VALIDATION PASSED WITH WARNINGS" -ForegroundColor Yellow
    Write-Host "   Review warnings before deploying to production.`n" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host " ALL VALIDATIONS PASSED - READY FOR DEPLOYMENT" -ForegroundColor Green
    Write-Host "   Proceed with release checklist.`n" -ForegroundColor Green
    exit 0
}
