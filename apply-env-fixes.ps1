# ============================================================================
# SCRIPT DE APLICAÇÃO DE CORREÇÕES .ENV
# ============================================================================
# Aplica todas as correções identificadas nos logs do Railway
# Versão: 1.0
# Data: 2025-10-06
# ============================================================================

Write-Host "`n" -NoNewline
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  APLICAÇÃO DE CORREÇÕES .ENV - CLÍNICA ONCOLÓGICA V02" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "`n"

# Verificar se estamos no diretório correto
$currentDir = Get-Location
if (-not (Test-Path "backend-hormonia") -or -not (Test-Path "frontend-hormonia")) {
    Write-Host "❌ ERRO: Execute este script na raiz do projeto!" -ForegroundColor Red
    Write-Host "   Diretório atual: $currentDir" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Diretório correto detectado: $currentDir" -ForegroundColor Green
Write-Host "`n"

# ----------------------------------------------------------------------------
# FUNÇÃO: Criar Backup
# ----------------------------------------------------------------------------
function Create-Backup {
    param (
        [string]$FilePath
    )

    if (Test-Path $FilePath) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupPath = "$FilePath.backup_$timestamp"
        Copy-Item $FilePath $backupPath -Force
        Write-Host "   📦 Backup criado: $backupPath" -ForegroundColor Gray
        return $true
    }
    return $false
}

# ----------------------------------------------------------------------------
# PASSO 1: BACKEND .ENV
# ----------------------------------------------------------------------------
Write-Host "🔧 PASSO 1/2: Aplicando correções no BACKEND" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────" -ForegroundColor Yellow

$backendEnv = "backend-hormonia\.env"
$backendEnvFinal = "backend-hormonia\.env.FINAL"

if (-not (Test-Path $backendEnvFinal)) {
    Write-Host "   ❌ Arquivo $backendEnvFinal não encontrado!" -ForegroundColor Red
    exit 1
}

Write-Host "   🔍 Verificando arquivo backend .env..." -ForegroundColor White

# Criar backup
Create-Backup -FilePath $backendEnv

# Aplicar correções
Write-Host "   📝 Aplicando correções do .env.FINAL..." -ForegroundColor White
Copy-Item $backendEnvFinal $backendEnv -Force

Write-Host "   ✅ Backend .env atualizado com sucesso!" -ForegroundColor Green
Write-Host "   📋 Correções aplicadas:" -ForegroundColor White
Write-Host "      • FIREBASE_ADMIN_PRIVATE_KEY atualizada" -ForegroundColor Cyan
Write-Host "      • ALLOWED_ORIGINS corrigido (https://...)" -ForegroundColor Cyan
Write-Host "      • FIREBASE_BLOCK_PUBLIC_DOMAINS=false" -ForegroundColor Cyan
Write-Host "      • AUTO_PROVISION_SUPABASE_USERS removida" -ForegroundColor Cyan
Write-Host "`n"

# ----------------------------------------------------------------------------
# PASSO 2: FRONTEND .ENV
# ----------------------------------------------------------------------------
Write-Host "🎨 PASSO 2/2: Aplicando correções no FRONTEND" -ForegroundColor Yellow
Write-Host "──────────────────────────────────────────────" -ForegroundColor Yellow

$frontendEnv = "frontend-hormonia\.env"
$frontendEnvFinal = "frontend-hormonia\.env.FINAL"

if (-not (Test-Path $frontendEnvFinal)) {
    Write-Host "   ❌ Arquivo $frontendEnvFinal não encontrado!" -ForegroundColor Red
    exit 1
}

Write-Host "   🔍 Verificando arquivo frontend .env..." -ForegroundColor White

# Criar backup
Create-Backup -FilePath $frontendEnv

# Aplicar correções
Write-Host "   📝 Aplicando correções do .env.FINAL..." -ForegroundColor White
Copy-Item $frontendEnvFinal $frontendEnv -Force

Write-Host "   ✅ Frontend .env atualizado com sucesso!" -ForegroundColor Green
Write-Host "   📋 Correções aplicadas:" -ForegroundColor White
Write-Host "      • VITE_SUPABASE_AUTH_ENABLED=false" -ForegroundColor Cyan
Write-Host "      • VITE_SUPABASE_REALTIME_ENABLED=false" -ForegroundColor Cyan
Write-Host "      • VITE_FIREBASE_ENABLED=true" -ForegroundColor Cyan
Write-Host "`n"

# ----------------------------------------------------------------------------
# RESUMO FINAL
# ----------------------------------------------------------------------------
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✅ TODAS AS CORREÇÕES APLICADAS COM SUCESSO!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`n"

Write-Host "📊 PRÓXIMOS PASSOS:" -ForegroundColor Yellow
Write-Host "`n"
Write-Host "1️⃣  COMMIT & PUSH (Local):" -ForegroundColor White
Write-Host "   git add backend-hormonia/app/services/firebase_user_sync_service.py" -ForegroundColor Cyan
Write-Host "   git commit -m " -NoNewline -ForegroundColor Cyan
Write-Host '"perf(auth): Eliminate duplicate Firebase API calls"' -ForegroundColor Cyan
Write-Host "   git push origin docs-refactor-py313" -ForegroundColor Cyan
Write-Host "`n"

Write-Host "2️⃣  ATUALIZAR RAILWAY (Backend):" -ForegroundColor White
Write-Host "   cd backend-hormonia" -ForegroundColor Cyan
Write-Host "   railway variables --set FIREBASE_BLOCK_PUBLIC_DOMAINS=false" -ForegroundColor Cyan
Write-Host "   railway variables --set ALLOWED_ORIGINS='[" -NoNewline -ForegroundColor Cyan
Write-Host '"https://frontend-production-18bb.up.railway.app"' -NoNewline -ForegroundColor Cyan
Write-Host ',"' -NoNewline -ForegroundColor Cyan
Write-Host 'https://quiz-interface-production.up.railway.app' -NoNewline -ForegroundColor Cyan
Write-Host '"]' -NoNewline -ForegroundColor Cyan
Write-Host "'" -ForegroundColor Cyan
Write-Host "   railway variables --delete AUTO_PROVISION_SUPABASE_USERS" -ForegroundColor Cyan
Write-Host "`n"
Write-Host "   ⚠️  FIREBASE_ADMIN_PRIVATE_KEY:" -ForegroundColor Yellow
Write-Host "   Atualize via Railway Dashboard UI (preserva quebras de linha)" -ForegroundColor Gray
Write-Host "   https://railway.app → seu projeto → backend → Variables" -ForegroundColor Gray
Write-Host "`n"

Write-Host "3️⃣  ATUALIZAR RAILWAY (Frontend):" -ForegroundColor White
Write-Host "   cd frontend-hormonia" -ForegroundColor Cyan
Write-Host "   railway variables --set VITE_SUPABASE_AUTH_ENABLED=false" -ForegroundColor Cyan
Write-Host "   railway variables --set VITE_SUPABASE_REALTIME_ENABLED=false" -ForegroundColor Cyan
Write-Host "   railway variables --set VITE_FIREBASE_ENABLED=true" -ForegroundColor Cyan
Write-Host "`n"

Write-Host "4️⃣  VERIFICAR LOGS (Após Deploy):" -ForegroundColor White
Write-Host "   railway logs --service backend | Select-String " -NoNewline -ForegroundColor Cyan
Write-Host '"ALLOWED_ORIGINS"' -ForegroundColor Cyan
Write-Host "   railway logs --service backend | Select-String " -NoNewline -ForegroundColor Cyan
Write-Host '"WebSocket"' -ForegroundColor Cyan
Write-Host "   railway logs --service backend | Select-String " -NoNewline -ForegroundColor Cyan
Write-Host '"auth/me"' -ForegroundColor Cyan
Write-Host "`n"

Write-Host "📚 DOCUMENTAÇÃO:" -ForegroundColor Yellow
Write-Host "   • docs/deployment/ENV_FINAL_CORRECTIONS_SUMMARY.md" -ForegroundColor Gray
Write-Host "   • docs/frontend/WEBSOCKET_AUDIT_REPORT.md" -ForegroundColor Gray
Write-Host "   • docs/deployment/FIREBASE_AUTH_FIX_SUMMARY.md" -ForegroundColor Gray
Write-Host "`n"

Write-Host "🎯 RESULTADOS ESPERADOS:" -ForegroundColor Yellow
Write-Host "   ✅ CORS com URLs completas (https://...)" -ForegroundColor Green
Write-Host "   ✅ WebSocket: 1 conexão limpa por sessão" -ForegroundColor Green
Write-Host "   ✅ Login 2x mais rápido (<500ms na 2ª tentativa)" -ForegroundColor Green
Write-Host "   ✅ Apenas 1 chamada ao Firebase Admin SDK" -ForegroundColor Green
Write-Host "`n"

Write-Host "Pressione qualquer tecla para sair..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
