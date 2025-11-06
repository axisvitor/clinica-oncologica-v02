# Script para criar paciente REAL e validar fluxo completo de onboarding
# Inclui: Cadastro -> Saga -> WhatsApp -> Flow State

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "CADASTRO DE PACIENTE REAL - FLUXO COMPLETO" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Dados do paciente REAL
$patientData = @{
    name = "Paciente Real Teste"
    phone = "+5594991307744"
    email = "paciente.real@neoplasiaslitoral.com"
    cpf = "12345678901"
    birth_date = "1980-01-15"
    gender = "M"
}

Write-Host "`nPaciente:" -ForegroundColor Yellow
Write-Host "  Nome: $($patientData.name)" -ForegroundColor White
Write-Host "  Telefone: $($patientData.phone)" -ForegroundColor White
Write-Host "  Email: $($patientData.email)" -ForegroundColor White

# URLs
$baseUrl = "http://localhost:8000"
$patientsUrl = "$baseUrl/api/v1/patients"

# Admin user ID (doctor)
$adminDoctorId = "d7c3e4f5-6a7b-8c9d-0e1f-2a3b4c5d6e7f"  # ID do usuário admin@neoplasiaslitoral.com

try {
    # 1. Obter token Firebase
    Write-Host "`nObtendo token Firebase..." -ForegroundColor Yellow
    
    # pragma: allowlist secret - token obtido dinamicamente para execução local
    $firebaseToken = & .\get_firebase_token.ps1
    
    if (-not $firebaseToken) {
        throw "Falha ao obter token Firebase"
    }
    
    Write-Host "✅ Token Firebase obtido" -ForegroundColor Green
    
    # 2. Preparar headers da API
    $apiHeaders = @{
        "Authorization" = "Bearer $firebaseToken"  # pragma: allowlist secret - header construído dinamicamente
        "Content-Type" = "application/json"
    }
    
    # 3. Criar paciente (SAGA ATIVA)
    # Nota: doctor_id será extraído automaticamente do token Firebase pelo backend
    Write-Host "`n=========================================" -ForegroundColor Cyan
    Write-Host "CRIANDO PACIENTE REAL (SAGA ATIVA)" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    
    $patientBody = @{
        name = $patientData.name
        phone = $patientData.phone
        email = $patientData.email
        cpf = $patientData.cpf
        birth_date = $patientData.birth_date
        gender = $patientData.gender
        doctor_id = $adminDoctorId
    } | ConvertTo-Json
    
    $patientResponse = Invoke-RestMethod -Uri $patientsUrl -Method Post `
        -Headers $apiHeaders -Body $patientBody
    
    $patientId = $patientResponse.id
    
    Write-Host "`n✅ PACIENTE CRIADO!" -ForegroundColor Green
    Write-Host "   ID: $patientId" -ForegroundColor White
    Write-Host "   Nome: $($patientResponse.name)" -ForegroundColor White
    Write-Host "   Telefone: $($patientResponse.phone)" -ForegroundColor White
    
    # Salvar ID para validação
    $patientId | Out-File -FilePath "last_patient_id.txt" -Encoding UTF8
    
    # 4. Aguardar processamento da Saga
    Write-Host "`nAguardando processamento da Saga (15s)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
    
    # 5. Validar Saga no banco
    Write-Host "`n=========================================" -ForegroundColor Cyan
    Write-Host "VALIDANDO SAGA E FLUXO COMPLETO" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    
    & .\venv\Scripts\python.exe check_saga.py
    
    Write-Host "`n=========================================" -ForegroundColor Cyan
    Write-Host "✅ PROCESSO COMPLETO FINALIZADO!" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "`nPróximos passos:" -ForegroundColor Yellow
    Write-Host "  1. Verificar se a mensagem WhatsApp foi enviada" -ForegroundColor White
    Write-Host "  2. Confirmar recebimento no número +5594991307744" -ForegroundColor White
    Write-Host "  3. Monitorar logs do servidor para detalhes" -ForegroundColor White
    
} catch {
    Write-Host "`n❌ ERRO: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Resposta do servidor: $responseBody" -ForegroundColor Red
    }
    exit 1
}
