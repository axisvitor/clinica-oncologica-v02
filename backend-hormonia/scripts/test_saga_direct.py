#!/usr/bin/env python3
"""
Script para testar a saga de onboarding diretamente.
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings
from app.coordination.saga_orchestrator import SagaOrchestrator
from app.core.redis_client import get_redis_client
from app.schemas.patient import PatientCreate

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
engine = create_engine(DATABASE_URL)


async def test_saga():
    """Testa a saga de onboarding diretamente."""
    print("=" * 60)
    print("🧪 TESTE DIRETO DA SAGA DE ONBOARDING")
    print("=" * 60)
    
    try:
        with Session(engine) as session:
            # Obter médico existente
            doctor_query = text("SELECT id FROM users LIMIT 1")
            doctor = session.execute(doctor_query).first()
            
            if not doctor:
                print("❌ Nenhum médico encontrado")
                return
            
            doctor_id = doctor.id
            print(f"\n✅ Médico encontrado: {doctor_id}")
            
            # Criar dados do paciente
            patient_data = PatientCreate(
                name="Ana Costa Teste Saga",
                phone="+5511888999777",
                email=f"ana.saga.{uuid4().hex[:8]}@example.com",
                treatment_type="Terapia Hormonal",
                treatment_start_date=datetime.now().date()
            )
            
            print(f"\n📋 Dados do paciente:")
            print(f"   Nome: {patient_data.name}")
            print(f"   Email: {patient_data.email}")
            print(f"   Telefone: {patient_data.phone}")
            
            # Inicializar saga orchestrator
            print("\n🔧 Inicializando Saga Orchestrator...")
            redis_client = get_redis_client()
            saga = SagaOrchestrator(db=session, redis_client=redis_client)
            
            # Executar saga
            print("\n🚀 Executando saga de onboarding...")
            patient = await saga.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
                current_user=None
            )
            
            if patient:
                print(f"\n✅ SUCESSO! Paciente criado via saga:")
                print(f"   ID: {patient.id}")
                print(f"   Nome: {patient.name}")
                print(f"   Email: {patient.email}")
                
                # Verificar flow state
                flow_query = text("""
                    SELECT COUNT(*) as count FROM patient_flow_states 
                    WHERE patient_id = :patient_id
                """)
                flow_count = session.execute(
                    flow_query, 
                    {"patient_id": str(patient.id)}
                ).scalar()
                
                print(f"\n📊 Flow states criados: {flow_count}")
                
                # Verificar mensagens
                msg_query = text("""
                    SELECT COUNT(*) as count FROM messages 
                    WHERE patient_id = :patient_id
                """)
                msg_count = session.execute(
                    msg_query,
                    {"patient_id": str(patient.id)}
                ).scalar()
                
                print(f"📊 Mensagens enviadas: {msg_count}")
                
                # Verificar saga log
                saga_query = text("""
                    SELECT status, error_message FROM patient_onboarding_saga 
                    WHERE patient_id = :patient_id
                    ORDER BY created_at DESC LIMIT 1
                """)
                saga_log = session.execute(
                    saga_query,
                    {"patient_id": str(patient.id)}
                ).first()
                
                if saga_log:
                    print(f"\n📋 Saga log:")
                    print(f"   Status: {saga_log.status}")
                    if saga_log.error_message:
                        print(f"   Erro: {saga_log.error_message}")
                else:
                    print("\n⚠️  Nenhum log de saga encontrado")
                
            else:
                print("\n❌ FALHA! Saga retornou None")
                
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_saga())
