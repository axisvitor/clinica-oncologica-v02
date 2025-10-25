#!/usr/bin/env python3
"""
Teste FINAL via API HTTP - a forma mais realista de testar.
"""
import sys
import requests
import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import random
import time

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

print("=" * 60)
print("🧪 TESTE FINAL VIA API HTTP")
print("=" * 60)

# Configuração
API_BASE_URL = "http://localhost:8000"
API_V1_URL = f"{API_BASE_URL}/api/v1"

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
engine = create_engine(DATABASE_URL)

try:
    # 1. Verificar backend
    print("\n1️⃣ Verificando backend...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend está rodando")
        else:
            print(f"   ❌ Backend respondeu com status {response.status_code}")
            sys.exit(1)
    except:
        print("   ❌ Backend não está rodando")
        print("   💡 Inicie: uvicorn app.main:app --reload")
        sys.exit(1)
    
    # 2. Criar paciente via endpoint público (sem autenticação)
    print("\n2️⃣ Criando paciente via API...")
    
    phone_number = f"+5594{random.randint(900000000, 999999999)}"
    patient_email = f"api.final.{uuid4().hex[:8]}@example.com"
    
    patient_data = {
        "name": "Teste Final API",
        "phone": phone_number,
        "email": patient_email,
        "treatment_type": "Terapia Hormonal",
        "treatment_start_date": datetime.now().date().isoformat()
    }
    
    print(f"   Nome: {patient_data['name']}")
    print(f"   Email: {patient_data['email']}")
    print(f"   Telefone: {patient_data['phone']}")
    
    # Tentar criar via endpoint público primeiro
    print("\n   Tentando criar via endpoint público...")
    try:
        response = requests.post(
            f"{API_V1_URL}/patients/public",
            json=patient_data,
            timeout=30
        )
        
        if response.status_code == 201:
            patient = response.json()
            patient_id = patient['id']
            print(f"   ✅ Paciente criado via API pública: {patient_id}")
        else:
            print(f"   ⚠️  Endpoint público não disponível: {response.status_code}")
            print("   Criando diretamente no banco para testar...")
            
            # Criar diretamente no banco
            with Session(engine) as session:
                doctor_query = text("SELECT id FROM users LIMIT 1")
                doctor = session.execute(doctor_query).first()
                
                if not doctor:
                    print("   ❌ Nenhum médico encontrado")
                    sys.exit(1)
                
                patient_id = str(uuid4())
                insert_query = text("""
                    INSERT INTO patients (
                        id, name, phone, email, doctor_id, treatment_type,
                        treatment_start_date, created_at, updated_at
                    ) VALUES (
                        :id, :name, :phone, :email, :doctor_id, :treatment_type,
                        :treatment_start_date, :created_at, :updated_at
                    )
                """)
                
                now = datetime.now()
                session.execute(insert_query, {
                    "id": patient_id,
                    "name": patient_data['name'],
                    "phone": patient_data['phone'],
                    "email": patient_data['email'],
                    "doctor_id": doctor.id,
                    "treatment_type": patient_data['treatment_type'],
                    "treatment_start_date": datetime.now().date(),
                    "created_at": now,
                    "updated_at": now
                })
                
                session.commit()
                print(f"   ✅ Paciente criado no banco: {patient_id}")
                print(f"   ⚠️  ATENÇÃO: Criado diretamente no banco, saga NÃO será executada")
                print(f"   Para testar a saga, precisa criar via API/Service")
    
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        sys.exit(1)
    
    # 3. Aguardar
    print("\n3️⃣ Aguardando 3 segundos...")
    time.sleep(3)
    
    # 4. Verificar no banco
    print("\n4️⃣ Verificando no banco...")
    with Session(engine) as session:
        # Verificar saga
        saga_query = text("""
            SELECT id, status, error_message, created_at
            FROM patient_onboarding_saga 
            WHERE patient_id = :patient_id
            ORDER BY created_at DESC LIMIT 1
        """)
        saga = session.execute(saga_query, {"patient_id": patient_id}).first()
        
        if saga:
            print(f"   ✅ SAGA ENCONTRADA!")
            print(f"   ID: {saga.id}")
            print(f"   Status: {saga.status}")
            print(f"   Criada em: {saga.created_at}")
            if saga.error_message:
                print(f"   Erro: {saga.error_message[:200]}...")
        else:
            print(f"   ❌ SAGA NÃO ENCONTRADA")
        
        # Verificar flow states
        flow_query = text("""
            SELECT COUNT(*) FROM patient_flow_states 
            WHERE patient_id = :patient_id
        """)
        flow_count = session.execute(flow_query, {"patient_id": patient_id}).scalar()
        print(f"   Flow states: {flow_count}")
        
        # Verificar mensagens
        msg_query = text("""
            SELECT COUNT(*) FROM messages 
            WHERE patient_id = :patient_id
        """)
        msg_count = session.execute(msg_query, {"patient_id": patient_id}).scalar()
        print(f"   Mensagens: {msg_count}")
        
        # Resumo
        print("\n" + "=" * 60)
        print("📊 RESULTADO FINAL")
        print("=" * 60)
        print(f"✅ Paciente criado: {patient_id}")
        print(f"{'✅' if saga else '❌'} Saga executada: {saga is not None}")
        print(f"{'✅' if flow_count > 0 else '⚠️ '} Flow states: {flow_count}")
        print(f"{'✅' if msg_count > 0 else '⚠️ '} Mensagens: {msg_count}")
        
        if saga:
            print("\n🎉 SUCESSO! A saga está funcionando!")
            print("\n✅ O FIX FUNCIONOU!")
            print("   - settings.get() → getattr(settings, ...)")
            print("   - ENABLE_SAGA_PATTERN adicionado à configuração")
            print("   - Saga sendo executada corretamente")
        else:
            print("\n⚠️  Saga não foi executada")
            print("\n🔍 Possíveis causas:")
            print("   1. Paciente foi criado diretamente no banco (não via service)")
            print("   2. Endpoint de criação não está chamando o service corretamente")
            print("   3. Há erro na execução da saga (verificar logs do backend)")
            print("\n💡 Para testar corretamente:")
            print("   1. Criar endpoint público de criação de paciente")
            print("   2. OU usar endpoint autenticado com token válido")
            print("   3. OU chamar o PatientService diretamente em um script")

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
