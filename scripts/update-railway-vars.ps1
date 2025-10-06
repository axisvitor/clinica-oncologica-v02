# ==========================================================================
# RAILWAY VARIABLES UPDATE SCRIPT
# ==========================================================================
# Automates Railway environment variable updates for backend and frontend
# Run this script to apply all .env.FINAL corrections to Railway production
# ==========================================================================

param(
    [string]$Environment = "production",
    [string]$BackendService = "backend-hormonia",
    [string]$FrontendService = "frontend-hormonia",
    [switch]$DryRun
)

Write-Host "`n Railway Variables Update - Wave 2 Deployment" -ForegroundColor Cyan
Write-Host ('=' * 70) -ForegroundColor Gray

function Test-RailwayCLI {
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
        throw "Railway CLI não encontrado. Instale com 'npm i -g @railway/cli' e faça login antes de continuar."
    }
}

function Get-EnvValues {
    param(
        [string]$Path,
        [string[]]$Keys
    )

    if (-not (Test-Path $Path)) {
        throw "Arquivo .env não encontrado em $Path"
    }

    $content = Get-Content -Path $Path -Raw
    $map = @{}

    foreach ($key in $Keys) {
        $pattern = "(?m)^$([Regex]::Escape($key))\s*=\s*(.*)$"
        $match = [Regex]::Match($content, $pattern)
        if ($match.Success) {
            $value = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
            $map[$key] = $value
        } else {
            Write-Warning "Chave '$key' não encontrada em $Path"
        }
    }

    return $map
}

function Set-RailwayVariables {
    param(
        [string]$Service,
        [hashtable]$Variables
    )

    foreach ($key in $Variables.Keys) {
        $value = $Variables[$key]
        $display = if ($value.Length -gt 40) { $value.Substring(0, 37) + '...' } else { $value }
        Write-Host "  → $key = $display"

        if ($DryRun) {
            Write-Host "    [DRY RUN] railway variables set --service=$Service --environment=$Environment $key=<redacted>" -ForegroundColor DarkGray
            continue
        }

        $args = @("variables", "set", "${key}=$value", "--service=$Service", "--environment=$Environment")
        $process = Start-Process -FilePath "railway" -ArgumentList $args -NoNewWindow -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Falha ao definir variável '$key' para o serviço '$Service'"
        }
    }
}

try {
    Test-RailwayCLI

    $backendEnv = Join-Path $PSScriptRoot "..\backend-hormonia\.env.FINAL"
    $frontendEnv = Join-Path $PSScriptRoot "..\frontend-hormonia\.env.FINAL"

    $backendKeys = @("ALLOWED_ORIGINS", "FIREBASE_ADMIN_PRIVATE_KEY")
    $frontendKeys = @("VITE_SUPABASE_AUTH_ENABLED", "VITE_FIREBASE_ENABLED")

    Write-Host "`n Updating Backend Variables..." -ForegroundColor Yellow
    $backendVars = Get-EnvValues -Path $backendEnv -Keys $backendKeys
    if ($backendVars.Count -gt 0) {
        Set-RailwayVariables -Service $BackendService -Variables $backendVars
    } else {
        Write-Host "  Nenhuma variável encontrada para backend." -ForegroundColor DarkGray
    }

    Write-Host "`n Updating Frontend Variables..." -ForegroundColor Yellow
    $frontendVars = Get-EnvValues -Path $frontendEnv -Keys $frontendKeys
    if ($frontendVars.Count -gt 0) {
        Set-RailwayVariables -Service $FrontendService -Variables $frontendVars
    } else {
        Write-Host "  Nenhuma variável encontrada para frontend." -ForegroundColor DarkGray
    }

    Write-Host "`n Atualização concluída." -ForegroundColor Green
    if ($DryRun) {
        Write-Host "(Nada foi alterado porque o modo DryRun está ativo)" -ForegroundColor DarkGray
    }
}
catch {
    Write-Error $_
    exit 1
}
