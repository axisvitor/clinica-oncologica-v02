#!/usr/bin/env python3
"""
Script simplificado para testar a saga de onboarding diretamente.
Evita importações circulares usando imports tardios.
"""
import sys
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

print("=" * 60)
print("🧪 TESTE SIMPLIFICADO DA SAGA DE ONBOARDING")
print("=" * 60)

# Imports básicos primeiro
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Importar config
print("\n1️⃣ Carregando configurações...")
from app.config import settings
print(f"   ✅ Database: {settings.DATABASE_URL[:50]}...")

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
engine = create_engine(DATABASE_URL)

print("\n2️⃣ Conectando ao banco de dados...")
try:
    with Session(engine) as session:
        # Testar conexão
        result = session.execute(text("SELECT 1")).scalar()
        print(f"   ✅ Conexão estabelecida")
        
        # Obter médico existente
        print("\n3️⃣ Buscando médico...")
        doctor_query = text("SELECT id, full_name, email FROM users LIMIT 1")
        doctor = session.execute(doctor_query).first()
        
        if not doctor:
            print("   ❌ Nenhum médico encontrado")
            sys.exit(1)
        
        doctor_id = doctor.id
        doctor_name = doctor.full_name or doctor.email
        print(f"   ✅ Médico encontrado: {doctor_name} ({doctor_id})")
        
        # Criar dados do paciente
        print("\n4️⃣ Preparando dados do paciente...")
        patient_email = f"teste.saga.{uuid4().hex[:8]}@example.com"
        patient_data = {
            "name": "Teste Saga Direto",
            "phone": "+5511999888777",
            "email": patient_email,
            "treatment_type": "Terapia Hormonal",
            "treatment_start_date": datetime.now().date()
        }
        print(f"   Nome: {patient_data['name']}")
        print(f"   Email: {patient_data['email']}")
        print(f"   Telefone: {patient_data['phone']}")
        
        # Agora vamos tentar importar e executar a saga
        print("\n5️⃣ Importando componentes da saga...")
        
        try:
            # Import tardio para evitar circular imports
            import asyncio
            
            # Importar apenas o necessário
            print("   📦 Importando SagaOrchestrator...")
            from app.coordination.saga_orchestrator import SagaOrchestrator
            print("   ✅ SagaOrchestrator importado")
            
            print("   📦 Importando Redis client...")
            from app.core.redis_client import get_redis_client
            print("   ✅ Redis client importado")
            
            print("   📦 Importando PatientCreate schema...")
            from app.schemas.patient import PatientCreate
            print("   ✅ PatientCreate importado")
            
            # Criar schema do paciente
            print("\n6️⃣ Criando schema do paciente...")
            patient_create = PatientCreate(**patient_data)
            print("   ✅ Schema criado")
            
            # Inicializar saga orchestrator
            print("\n7️⃣ Inicializando Saga Orchestrator...")
            redis_client = get_redis_client()
            saga = SagaOrchestrator(db=session, redis_client=redis_client)
            print("   ✅ Saga Orchestrator inicializado")
            
            # Executar saga
            print("\n8️⃣ Executando saga de onboarding...")
            print("   ⏳ Aguarde...")
            
            async def run_saga():
                return await saga.execute_patient_onboarding_saga(
                    patient_data=patient_create,
                    doctor_id=doctor_id,
                    current_user=None
                )
            
            # Executar de forma síncrona
            patient = asyncio.run(run_saga())
            
            if patient:
                print(f"\n✅ SUCESSO! Paciente criado via saga:")
                print(f"   ID: {patient.id}")
                print(f"   Nome: {patient.name}")
                print(f"   Email: {patient.email}")
                
                # Verificar flow state
                print("\n9️⃣ Verificando resultados no banco...")
                
                flow_query = text("""
                    SELECT COUNT(*) as count FROM patient_flow_states 
                    WHERE patient_id = :patient_id
                """)
                flow_count = session.execute(
                    flow_query, 
                    {"patient_id": str(patient.id)}
                ).scalar()
                
                print(f"   📊 Flow states criados: {flow_count}")
                
                # Verificar mensagens
                msg_query = text("""
                    SELECT COUNT(*) as count FROM messages 
                    WHERE patient_id = :patient_id
                """)
                msg_count = session.execute(
                    msg_query,
                    {"patient_id": str(patient.id)}
                ).scalar()
                
                print(f"   📊 Mensagens criadas: {msg_count}")
                
                # Verificar saga log
                saga_query = text("""
                    SELECT status, error_message, execution_log FROM patient_onboarding_saga 
                    WHERE patient_id = :patient_id
                    ORDER BY created_at DESC LIMIT 1
                """)
                saga_log = session.execute(
                    saga_query,
                    {"patient_id": str(patient.id)}
                ).first()
                
                if saga_log:
                    print(f"\n   📋 Saga log:")
                    print(f"      Status: {saga_log.status}")
                    if saga_log.error_message:
                        print(f"      Erro: {saga_log.error_message}")
                    if saga_log.execution_log:
                        print(f"      Log: {saga_log.execution_log}")
                else:
                    print("\n   ⚠️  Nenhum log de saga encontrado")
                
                # Resumo final
                print("\n" + "=" * 60)
                print("📊 RESUMO DOS RESULTADOS")
                print("=" * 60)
                print(f"✅ Paciente criado: {patient.id}")
                print(f"{'✅' if flow_count > 0 else '❌'} Flow states: {flow_count}")
                print(f"{'✅' if msg_count > 0 else '❌'} Mensagens: {msg_count}")
                print(f"{'✅' if saga_log else '❌'} Saga log: {'Sim' if saga_log else 'Não'}")
                
                if flow_count == 0:
                    print("\n⚠️  ATENÇÃO:")
                    print("   Flow states não foram criados.")
                    print("   Isso pode indicar que:")
                    print("   1. A saga não está criando flows automaticamente")
                    print("   2. Há erro na lógica da saga")
                    print("   3. Celery Beat precisa processar os flows")
                
                if msg_count == 0:
                    print("\n⚠️  ATENÇÃO:")
                    print("   Mensagens não foram criadas.")
                    print("   Isso pode indicar que:")
                    print("   1. A saga não está enviando mensagens automaticamente")
                    print("   2. Celery Beat precisa processar as mensagens")
                    print("   3. Integração com WhatsApp não está configurada")
                
            else:
                print("\n❌ FALHA! Saga retornou None")
                print("   Verificar logs da saga para mais detalhes")
                
        except ImportError as e:
            print(f"\n❌ ERRO DE IMPORTAÇÃO: {e}")
            print("\n💡 Isso indica problema de dependências circulares")
            print("   Solução: Refatorar imports ou usar imports tardios")
            import traceback
            traceback.print_exc()
            
        except Exception as e:
            print(f"\n❌ ERRO NA EXECUÇÃO: {e}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"\n❌ ERRO DE CONEXÃO: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("🏁 TESTE FINALIZADO")
print("=" * 60)
