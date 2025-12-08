#!/usr/bin/env python3
"""Criar paciente real diretamente via código Python (bypass API)."""

import asyncio
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings
from app.models.patient import Patient
from app.orchestration.saga_orchestrator import SagaOrchestrator, FlowKind
from app.core.redis_client import get_redis_client
from app.integrations.evolution import EvolutionClient
from app.schemas.patient import PatientCreate

print("=" * 70)
print("CRIAÇÃO DE PACIENTE REAL - FLUXO COMPLETO")
print("=" * 70)

# Dados do paciente REAL
patient_data = {
    "name": "Paciente Real Teste",
    "phone": "+5594991307744",
    "email": "paciente.real@neoplasiaslitoral.com",
    "cpf": "12345678901",
    "birth_date": date(1980, 1, 15),
    "gender": "M",
}

print("\nPaciente:")
print(f"  Nome: {patient_data['name']}")
print(f"  Telefone: {patient_data['phone']}")
print(f"  Email: {patient_data['email']}")

# Conectar ao banco
engine = create_engine(settings.DATABASE_URL)

async def create_patient_with_saga():
    """Criar paciente usando Saga Pattern."""
    
    with Session(engine) as db:
        try:
            # 1. Obter ID do doctor (admin user)
            print("\n=== 1. OBTENDO DOCTOR ===")
            doctor_query = text("""
                SELECT id, email FROM users 
                WHERE email = 'admin@neoplasiaslitoral.com'
                LIMIT 1
            """)
            doctor_result = db.execute(doctor_query).fetchone()
            
            if not doctor_result:
                raise Exception("Doctor admin não encontrado no banco")
            
            doctor_id = doctor_result[0]
            print(f"✅ Doctor: {doctor_result[1]}")
            print(f"   ID: {doctor_id}")
            
            # 2. Criar SagaOrchestrator
            print("\n=== 2. INICIALIZANDO SAGA ORCHESTRATOR ===")
            redis_client = get_redis_client()
            evolution_client = EvolutionClient()
            
            saga_orchestrator = SagaOrchestrator(
                db=db,
                redis=redis_client,
                evolution_client=evolution_client
            )
            print("✅ SagaOrchestrator inicializado")
            
            # 3. Executar Saga de onboarding
            print("\n=== 3. EXECUTANDO SAGA DE ONBOARDING ===")
            print(f"   ENABLE_SAGA_PATTERN: {getattr(settings, 'ENABLE_SAGA_PATTERN', False)}")
            print(f"   ENABLE_WHATSAPP_ON_REGISTRATION: {getattr(settings, 'ENABLE_WHATSAPP_ON_REGISTRATION', False)}")
            print(f"   WHATSAPP_WELCOME_MESSAGE_ENABLED: {getattr(settings, 'WHATSAPP_WELCOME_MESSAGE_ENABLED', False)}")
            
            patient = await saga_orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id
            )
            
            if patient:
                print(f"\n✅ PACIENTE CRIADO COM SUCESSO!")
                print(f"   ID: {patient.id}")
                print(f"   Nome: {patient.name}")
                print(f"   Telefone: {patient.phone}")
                print(f"   Email: {patient.email}")
                
                # Salvar ID para validação
                with open("last_patient_id.txt", "w", encoding="utf-8") as f:
                    f.write(str(patient.id))
                
                return patient.id
            else:
                raise Exception("Saga retornou None - falha na criação do paciente")
                
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise

# Executar criação
print("\n" + "=" * 70)
print("INICIANDO CRIAÇÃO DO PACIENTE")
print("=" * 70)

patient_id = asyncio.run(create_patient_with_saga())

# Aguardar processamento
print("\n" + "=" * 70)
print("AGUARDANDO PROCESSAMENTO DA SAGA (5s)...")
print("=" * 70)
import time
time.sleep(5)

# Validar no banco
print("\n" + "=" * 70)
print("VALIDANDO SAGA E FLUXO COMPLETO")
print("=" * 70)

import subprocess
result = subprocess.run(
    [r".\venv\Scripts\python.exe", "check_saga.py"],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print("\n" + "=" * 70)
print("✅ PROCESSO COMPLETO FINALIZADO!")
print("=" * 70)
print("\nPróximos passos:")
print("  1. Verificar se a mensagem WhatsApp foi enviada")
print("  2. Confirmar recebimento no número +5594991307744")
print("  3. Monitorar logs do servidor para detalhes")
