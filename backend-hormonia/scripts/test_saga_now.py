#!/usr/bin/env python3
"""
Script para testar a saga AGORA com telefone único.
"""
import sys
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

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
engine = create_engine(DATABASE_URL)

print("=" * 60)
print("🧪 TESTE DA SAGA - AGORA")
print("=" * 60)

try:
    with Session(engine) as session:
        # 1. Buscar médico
        print("\n1️⃣ Buscando médico...")
        doctor_query = text("SELECT id, full_name FROM users LIMIT 1")
        doctor = session.execute(doctor_query).first()
        
        if not doctor:
            print("   ❌ Nenhum médico encontrado")
            sys.exit(1)
        
        print(f"   ✅ Médico: {doctor.full_name} ({doctor.id})")
        
        # 2. Criar paciente com telefone único
        print("\n2️⃣ Criando paciente...")
        patient_id = str(uuid4())
        patient_email = f"saga.test.{uuid4().hex[:8]}@example.com"
        # Gerar telefone único: +55 + DDD (94) + 9 dígitos
        phone_number = f"+5594{random.randint(900000000, 999999999)}"
        
        print(f"   Nome: Teste Saga Agora")
        print(f"   Email: {patient_email}")
        print(f"   Telefone: {phone_number}")
        
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
            "name": "Teste Saga Agora",
            "phone": phone_number,
            "email": patient_email,
            "doctor_id": doctor.id,
            "treatment_type": "Terapia Hormonal",
            "treatment_start_date": now.date(),
            "created_at": now,
            "updated_at": now
        })
        
        session.commit()
        print(f"   ✅ Paciente criado: {patient_id}")
        
        # 3. Aguardar um pouco
        print("\n3️⃣ Aguardando 2 segundos...")
        import time
        time.sleep(2)
        
        # 4. Verificar saga
        print("\n4️⃣ Verificando saga...")
        saga_query = text("""
            SELECT id, status, error_message, execution_log, created_at
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
                print(f"   ⚠️  Erro: {saga.error_message}")
            if saga.execution_log:
                print(f"   📋 Log: {saga.execution_log[:300]}...")
        else:
            print(f"   ❌ SAGA NÃO ENCONTRADA")
            print(f"   Isso significa que a saga ainda não está sendo executada")
            print(f"   Possíveis causas:")
            print(f"   1. O código ainda tem o bug do settings.get()")
            print(f"   2. A saga está falhando silenciosamente")
            print(f"   3. O backend não foi reiniciado após o fix")
        
        # 5. Verificar flow states
        print("\n5️⃣ Verificando flow states...")
        flow_query = text("""
            SELECT COUNT(*) as count FROM patient_flow_states 
            WHERE patient_id = :patient_id
        """)
        flow_count = session.execute(flow_query, {"patient_id": patient_id}).scalar()
        print(f"   Flow states: {flow_count}")
        
        # 6. Verificar mensagens
        print("\n6️⃣ Verificando mensagens...")
        msg_query = text("""
            SELECT COUNT(*) as count FROM messages 
            WHERE patient_id = :patient_id
        """)
        msg_count = session.execute(msg_query, {"patient_id": patient_id}).scalar()
        print(f"   Mensagens: {msg_count}")
        
        # Resumo
        print("\n" + "=" * 60)
        print("📊 RESULTADO")
        print("=" * 60)
        print(f"✅ Paciente criado: {patient_id}")
        print(f"{'✅' if saga else '❌'} Saga executada: {saga is not None}")
        print(f"{'✅' if flow_count > 0 else '⚠️ '} Flow states: {flow_count}")
        print(f"{'✅' if msg_count > 0 else '⚠️ '} Mensagens: {msg_count}")
        
        if not saga:
            print("\n⚠️  PROBLEMA: Saga não foi executada")
            print("\n🔍 Próximos passos:")
            print("   1. Verificar se o backend foi reiniciado")
            print("   2. Verificar logs do backend")
            print("   3. Verificar se o fix foi aplicado corretamente")
            
            # Verificar se o fix foi aplicado
            print("\n🔧 Verificando se o fix foi aplicado...")
            print("   Verificar em: backend-hormonia/app/services/patient.py")
            print("   Linha 86 deve ter: getattr(settings, 'ENABLE_SAGA_PATTERN', True)")
            print("   NÃO deve ter: settings.get('ENABLE_SAGA_PATTERN', True)")
        else:
            print("\n🎉 SUCESSO! A saga está funcionando!")
            if flow_count == 0:
                print("\n⚠️  Flow states não criados ainda")
                print("   Isso é normal se o Celery Beat não estiver rodando")
            if msg_count == 0:
                print("\n⚠️  Mensagens não criadas ainda")
                print("   Isso é normal se o Celery Beat não estiver rodando")

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
