#!/usr/bin/env python3
"""
Script para testar criação de paciente via API HTTP.
Este é o teste mais realista pois simula o uso real do sistema.
"""
import sys
import requests
import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4
import time

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

print("=" * 60)
print("🧪 TESTE DE CRIAÇÃO DE PACIENTE VIA API")
print("=" * 60)

# Configuração
API_BASE_URL = "http://localhost:8000"
API_V1_URL = f"{API_BASE_URL}/api/v1"

# Credenciais de teste (ajustar conforme necessário)
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin123"

def check_backend_health():
    """Verifica se o backend está rodando."""
    print("\n1️⃣ Verificando se backend está rodando...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Backend está rodando")
            return True
        else:
            print(f"   ⚠️  Backend respondeu com status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Backend não está rodando")
        print("   💡 Inicie o backend com: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"   ❌ Erro ao verificar backend: {e}")
        return False


def login():
    """Faz login e retorna o token."""
    print("\n2️⃣ Fazendo login...")
    try:
        response = requests.post(
            f"{API_V1_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"   ✅ Login realizado com sucesso")
            return token
        else:
            print(f"   ❌ Falha no login: {response.status_code}")
            print(f"   Resposta: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Erro no login: {e}")
        return None


def create_patient(token):
    """Cria um paciente via API."""
    print("\n3️⃣ Criando paciente...")
    
    patient_data = {
        "name": "Ana Costa Teste API",
        "phone": "+5511999888777",
        "email": f"ana.api.{uuid4().hex[:8]}@example.com",
        "treatment_type": "Terapia Hormonal",
        "treatment_start_date": datetime.now().date().isoformat()
    }
    
    print(f"   Nome: {patient_data['name']}")
    print(f"   Email: {patient_data['email']}")
    print(f"   Telefone: {patient_data['phone']}")
    
    try:
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
            print(f"   ✅ Paciente criado com sucesso!")
            print(f"   ID: {patient['id']}")
            return patient
        else:
            print(f"   ❌ Falha ao criar paciente: {response.status_code}")
            print(f"   Resposta: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Erro ao criar paciente: {e}")
        return None


def check_patient_data(patient_id, token):
    """Verifica os dados do paciente no banco via API."""
    print("\n4️⃣ Verificando dados do paciente...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Aguardar um pouco para a saga processar
        print("   ⏳ Aguardando 5 segundos para saga processar...")
        time.sleep(5)
        
        response = requests.get(
            f"{API_V1_URL}/patients/{patient_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            patient = response.json()
            print(f"   ✅ Paciente encontrado")
            print(f"   Nome: {patient.get('name')}")
            print(f"   Status: {patient.get('status', 'N/A')}")
            return patient
        else:
            print(f"   ⚠️  Erro ao buscar paciente: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return None


def check_database_direct(patient_id):
    """Verifica diretamente no banco de dados."""
    print("\n5️⃣ Verificando diretamente no banco de dados...")
    
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session
        from app.config import settings
        
        DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            # Verificar flow states
            flow_query = text("""
                SELECT COUNT(*) as count FROM patient_flow_states 
                WHERE patient_id = :patient_id
            """)
            flow_count = session.execute(
                flow_query, 
                {"patient_id": patient_id}
            ).scalar()
            
            print(f"   📊 Flow states: {flow_count}")
            
            # Verificar mensagens
            msg_query = text("""
                SELECT COUNT(*) as count FROM messages 
                WHERE patient_id = :patient_id
            """)
            msg_count = session.execute(
                msg_query,
                {"patient_id": patient_id}
            ).scalar()
            
            print(f"   📊 Mensagens: {msg_count}")
            
            # Verificar saga
            saga_query = text("""
                SELECT status, error_message FROM patient_onboarding_saga 
                WHERE patient_id = :patient_id
                ORDER BY created_at DESC LIMIT 1
            """)
            saga_log = session.execute(
                saga_query,
                {"patient_id": patient_id}
            ).first()
            
            if saga_log:
                print(f"   📋 Saga status: {saga_log.status}")
                if saga_log.error_message:
                    print(f"   ⚠️  Saga error: {saga_log.error_message}")
            else:
                print(f"   ⚠️  Nenhuma saga encontrada")
            
            return {
                "flow_count": flow_count,
                "msg_count": msg_count,
                "saga_exists": saga_log is not None
            }
    except Exception as e:
        print(f"   ❌ Erro ao verificar banco: {e}")
        return None


def main():
    """Função principal."""
    try:
        # 1. Verificar backend
        if not check_backend_health():
            print("\n❌ Backend não está rodando. Inicie-o primeiro.")
            print("\n💡 Comando:")
            print("   cd backend-hormonia")
            print("   uvicorn app.main:app --reload")
            return
        
        # 2. Login
        token = login()
        if not token:
            print("\n❌ Não foi possível fazer login")
            print("\n💡 Verifique as credenciais:")
            print(f"   Email: {TEST_EMAIL}")
            print(f"   Password: {TEST_PASSWORD}")
            return
        
        # 3. Criar paciente
        patient = create_patient(token)
        if not patient:
            print("\n❌ Não foi possível criar paciente")
            return
        
        patient_id = patient['id']
        
        # 4. Verificar dados via API
        check_patient_data(patient_id, token)
        
        # 5. Verificar diretamente no banco
        db_results = check_database_direct(patient_id)
        
        # Resumo final
        print("\n" + "=" * 60)
        print("📊 RESUMO DOS RESULTADOS")
        print("=" * 60)
        print(f"✅ Paciente criado via API: {patient_id}")
        
        if db_results:
            print(f"{'✅' if db_results['saga_exists'] else '❌'} Saga executada: {db_results['saga_exists']}")
            print(f"{'✅' if db_results['flow_count'] > 0 else '❌'} Flow states: {db_results['flow_count']}")
            print(f"{'✅' if db_results['msg_count'] > 0 else '❌'} Mensagens: {db_results['msg_count']}")
            
            if not db_results['saga_exists']:
                print("\n⚠️  PROBLEMA:")
                print("   Saga não foi executada.")
                print("   Verifique se ENABLE_SAGA_PATTERN está habilitado")
            
            if db_results['flow_count'] == 0:
                print("\n⚠️  ATENÇÃO:")
                print("   Flow não foi iniciado.")
                print("   Celery Beat pode não estar rodando")
                print("\n💡 Inicie o Celery Beat:")
                print("   cd backend-hormonia")
                print("   celery -A app.celery_app worker --beat --loglevel=info --pool=solo")
        
        print("\n✅ Teste concluído!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
