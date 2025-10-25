#!/usr/bin/env python3
"""
Script para testar se a saga agora funciona após o fix.
"""
import sys
import requests
import json
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

print("=" * 60)
print("🧪 TESTE DA SAGA APÓS FIX")
print("=" * 60)

# Configuração
API_BASE_URL = "http://localhost:8000"
API_V1_URL = f"{API_BASE_URL}/api/v1"
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin123"

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
engine = create_engine(DATABASE_URL)

try:
    # 1. Login
    print("\n1️⃣ Fazendo login...")
    response = requests.post(
        f"{API_V1_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"   ❌ Falha no login: {response.status_code}")
        print(f"   Resposta: {response.text}")
        print("\n💡 Tentando criar paciente diretamente no banco...")
        
        # Criar paciente diretamente no banco
        with Session(engine) as session:
            doctor_query = text("SELECT id FROM users LIMIT 1")
            doctor = session.execute(doctor_query).first()
            
            if not doctor:
                print("   ❌ Nenhum médico encontrado")
                sys.exit(1)
            
            patient_id = str(uuid4())
            patient_email = f"teste.fix.{uuid4().hex[:8]}@example.com"
            
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
            # Usar telefone válido fornecido
            phone_number = "+5594991307744"
            
            session.execute(insert_query, {
                "id": patient_id,
                "name": "Teste Saga Fix",
                "phone": phone_number,
                "email": patient_email,
                "doctor_id": doctor.id,
                "treatment_type": "Terapia Hormonal",
                "treatment_start_date": now.date(),
                "created_at": now,
                "updated_at": now
            })
            
            session.commit()
            print(f"   ✅ Paciente criado diretamente: {patient_id}")
    else:
        token = response.json().get("access_token")
        print("   ✅ Login realizado")
        
        # 2. Criar paciente via API
        print("\n2️⃣ Criando paciente via API...")
        phone_number = "+5594991307744"
        
        patient_data = {
            "name": "Teste Saga Fix API",
            "phone": phone_number,
            "email": f"teste.fix.api.{uuid4().hex[:8]}@example.com",
            "treatment_type": "Terapia Hormonal",
            "treatment_start_date": datetime.now().date().isoformat()
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{API_V1_URL}/patients",
            json=patient_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 201:
            patient = response.json()
            patient_id = patient['id']
            print(f"   ✅ Paciente criado via API: {patient_id}")
        else:
            print(f"   ❌ Falha: {response.status_code}")
            print(f"   Resposta: {response.text}")
            sys.exit(1)
    
    # 3. Aguardar e verificar saga
    print("\n3️⃣ Aguardando 3 segundos...")
    import time
    time.sleep(3)
    
    print("\n4️⃣ Verificando saga no banco...")
    with Session(engine) as session:
        saga_query = text("""
            SELECT status, error_message, execution_log 
            FROM patient_onboarding_saga 
            WHERE patient_id = :patient_id
            ORDER BY created_at DESC LIMIT 1
        """)
        saga = session.execute(saga_query, {"patient_id": patient_id}).first()
        
        if saga:
            print(f"   ✅ SAGA ENCONTRADA!")
            print(f"   Status: {saga.status}")
            if saga.error_message:
                print(f"   Erro: {saga.error_message}")
            if saga.execution_log:
                print(f"   Log: {saga.execution_log[:200]}...")
        else:
            print(f"   ❌ SAGA NÃO ENCONTRADA")
            print(f"   Isso significa que o fix não funcionou")
        
        # Verificar flow states
        flow_query = text("""
            SELECT COUNT(*) as count FROM patient_flow_states 
            WHERE patient_id = :patient_id
        """)
        flow_count = session.execute(flow_query, {"patient_id": patient_id}).scalar()
        print(f"   Flow states: {flow_count}")
        
        # Verificar mensagens
        msg_query = text("""
            SELECT COUNT(*) as count FROM messages 
            WHERE patient_id = :patient_id
        """)
        msg_count = session.execute(msg_query, {"patient_id": patient_id}).scalar()
        print(f"   Mensagens: {msg_count}")
        
        print("\n" + "=" * 60)
        print("📊 RESULTADO DO FIX")
        print("=" * 60)
        print(f"{'✅' if saga else '❌'} Saga executada: {saga is not None}")
        print(f"{'✅' if flow_count > 0 else '⚠️ '} Flow states: {flow_count}")
        print(f"{'✅' if msg_count > 0 else '⚠️ '} Mensagens: {msg_count}")
        
        if saga:
            print("\n🎉 FIX FUNCIONOU! A saga agora está sendo executada!")
        else:
            print("\n⚠️  Saga ainda não está sendo executada.")
            print("   Verificar logs do backend para mais detalhes.")

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
