#!/usr/bin/env python3
"""
Script para testar criação de paciente via PatientService (não via SQL direto).
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import random

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

print("=" * 60)
print("🧪 TESTE VIA PATIENT SERVICE")
print("=" * 60)

async def test_patient_creation():
    """Testa criação de paciente via service."""
    try:
        # Imports tardios para evitar circular imports
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session
        from app.config import settings
        from app.schemas.patient import PatientCreate
        
        # Configuração do banco
        DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            # 1. Buscar médico
            print("\n1️⃣ Buscando médico...")
            doctor_query = text("SELECT id FROM users LIMIT 1")
            doctor = session.execute(doctor_query).first()
            
            if not doctor:
                print("   ❌ Nenhum médico encontrado")
                return
            
            doctor_id = doctor.id
            print(f"   ✅ Médico encontrado: {doctor_id}")
            
            # 2. Preparar dados do paciente
            print("\n2️⃣ Preparando dados do paciente...")
            phone_number = f"+5594{random.randint(900000000, 999999999)}"
            patient_email = f"service.test.{uuid4().hex[:8]}@example.com"
            
            patient_data = PatientCreate(
                name="Teste Via Service",
                phone=phone_number,
                email=patient_email,
                treatment_type="Terapia Hormonal",
                treatment_start_date=datetime.now().date()
            )
            
            print(f"   Nome: {patient_data.name}")
            print(f"   Email: {patient_data.email}")
            print(f"   Telefone: {patient_data.phone}")
            
            # 3. Importar e usar o PatientService
            print("\n3️⃣ Importando PatientService...")
            
            # Tentar importar o service
            try:
                from app.services.patient import PatientService
                from app.repositories.patient import PatientRepository
                from app.services.patient_integrity import PatientIntegrityService
                from app.services.flow_engine import FlowEngine
                from app.coordination.saga_orchestrator import SagaOrchestrator
                from app.core.redis_client import get_redis_client
                
                print("   ✅ Imports realizados")
                
                # Criar instâncias
                print("\n4️⃣ Criando instâncias dos services...")
                repository = PatientRepository(session)
                integrity_service = PatientIntegrityService(session)
                flow_engine = FlowEngine(session)
                redis_client = get_redis_client()
                saga_orchestrator = SagaOrchestrator(db=session, redis_client=redis_client)
                
                patient_service = PatientService(
                    db=session,
                    patient_repository=repository,
                    integrity_service=integrity_service,
                    flow_engine=flow_engine,
                    saga_orchestrator=saga_orchestrator
                )
                
                print("   ✅ PatientService criado")
                
                # 5. Criar paciente via service
                print("\n5️⃣ Criando paciente via service...")
                patient = await patient_service.create_patient(
                    patient_data=patient_data,
                    doctor_id=doctor_id,
                    current_user=None
                )
                
                print(f"   ✅ Paciente criado: {patient.id}")
                print(f"   Nome: {patient.name}")
                
                # 6. Verificar saga
                print("\n6️⃣ Verificando saga...")
                saga_query = text("""
                    SELECT id, status, error_message 
                    FROM patient_onboarding_saga 
                    WHERE patient_id = :patient_id
                    ORDER BY created_at DESC LIMIT 1
                """)
                saga = session.execute(saga_query, {"patient_id": str(patient.id)}).first()
                
                if saga:
                    print(f"   ✅ SAGA ENCONTRADA!")
                    print(f"   ID: {saga.id}")
                    print(f"   Status: {saga.status}")
                    if saga.error_message:
                        print(f"   Erro: {saga.error_message}")
                else:
                    print(f"   ❌ SAGA NÃO ENCONTRADA")
                
                # 7. Verificar flow states
                flow_query = text("""
                    SELECT COUNT(*) FROM patient_flow_states 
                    WHERE patient_id = :patient_id
                """)
                flow_count = session.execute(flow_query, {"patient_id": str(patient.id)}).scalar()
                print(f"   Flow states: {flow_count}")
                
                # 8. Verificar mensagens
                msg_query = text("""
                    SELECT COUNT(*) FROM messages 
                    WHERE patient_id = :patient_id
                """)
                msg_count = session.execute(msg_query, {"patient_id": str(patient.id)}).scalar()
                print(f"   Mensagens: {msg_count}")
                
                # Resumo
                print("\n" + "=" * 60)
                print("📊 RESULTADO")
                print("=" * 60)
                print(f"✅ Paciente criado via service: {patient.id}")
                print(f"{'✅' if saga else '❌'} Saga executada: {saga is not None}")
                print(f"{'✅' if flow_count > 0 else '⚠️ '} Flow states: {flow_count}")
                print(f"{'✅' if msg_count > 0 else '⚠️ '} Mensagens: {msg_count}")
                
                if saga:
                    print("\n🎉 SUCESSO! A saga foi executada!")
                else:
                    print("\n❌ FALHA! A saga não foi executada")
                    print("   Verificar logs do backend para mais detalhes")
                
            except ImportError as e:
                print(f"   ❌ Erro de importação: {e}")
                print("   Problema de dependências circulares")
                return
                
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

# Executar
if __name__ == "__main__":
    asyncio.run(test_patient_creation())
    print("\n" + "=" * 60)
