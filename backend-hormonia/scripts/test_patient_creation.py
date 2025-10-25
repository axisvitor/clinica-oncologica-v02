#!/usr/bin/env python3
"""
Script para testar a criação de paciente e verificar se o flow é iniciado.

Este script:
1. Cria um paciente teste no banco
2. Verifica se a saga de onboarding é executada
3. Verifica se o flow state é criado
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

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
engine = create_engine(DATABASE_URL)


def create_test_patient(session: Session) -> str:
    """Cria um paciente teste."""
    print("\n👤 Criando paciente teste...")
    
    # Verificar se já existe um médico
    doctor_query = text("SELECT id FROM users LIMIT 1")
    doctor = session.execute(doctor_query).first()
    
    if not doctor:
        print("  ⚠️  Nenhum médico encontrado na tabela users")
        # Criar um médico teste
        doctor_id = str(uuid4())
        insert_doctor = text("""
            INSERT INTO users (id, email, name, is_active, created_at, updated_at)
            VALUES (:id, :email, :name, :is_active, :created_at, :updated_at)
        """)
        
        now = datetime.now()
        session.execute(insert_doctor, {
            "id": doctor_id,
            "email": "medico.teste@clinica.com",
            "name": "Dr. Teste",
            "is_active": True,
            "created_at": now,
            "updated_at": now
        })
        print(f"    ✅ Médico teste criado: {doctor_id}")
    else:
        doctor_id = doctor.id
        print(f"    ℹ️  Usando médico existente: {doctor_id}")
    
    # Criar paciente teste
    patient_id = str(uuid4())
    insert_patient = text("""
        INSERT INTO patients (
            id, name, phone, email, doctor_id, treatment_type, 
            treatment_start_date, created_at, updated_at
        ) VALUES (
            :id, :name, :phone, :email, :doctor_id, :treatment_type,
            :treatment_start_date, :created_at, :updated_at
        )
    """)
    
    now = datetime.now()
    session.execute(insert_patient, {
        "id": patient_id,
        "name": "Maria Silva Teste",
        "phone": "+5511999887766",
        "email": "maria.teste@example.com",
        "doctor_id": doctor_id,
        "treatment_type": "Terapia Hormonal",
        "treatment_start_date": now.date(),
        "created_at": now,
        "updated_at": now
    })
    
    session.commit()
    print(f"    ✅ Paciente criado: {patient_id}")
    return patient_id


def check_flow_state(session: Session, patient_id: str):
    """Verifica se o flow state foi criado para o paciente."""
    print("\n🔄 Verificando flow state...")
    
    flow_query = text("""
        SELECT pfs.*, fk.kind_key, fk.display_name 
        FROM patient_flow_states pfs
        LEFT JOIN flow_kinds fk ON pfs.flow_template_version_id IN (
            SELECT id FROM flow_template_versions WHERE flow_kind_id = fk.id
        )
        WHERE pfs.patient_id = :patient_id
    """)
    
    flows = session.execute(flow_query, {"patient_id": patient_id}).fetchall()
    
    if flows:
        for flow in flows:
            print(f"    ✅ Flow ativo encontrado")
            print(f"       Status: {flow.status}")
            print(f"       Step atual: {flow.current_step}")
            print(f"       Iniciado em: {flow.started_at}")
    else:
        print("    ⚠️  Nenhum flow state encontrado")
        print("    ℹ️  Isso indica que a saga de onboarding não foi executada")
    
    return len(flows) > 0


def check_saga_status(session: Session, patient_id: str):
    """Verifica o status da saga de onboarding."""
    print("\n📋 Verificando saga de onboarding...")
    
    saga_query = text("""
        SELECT * FROM patient_onboarding_saga 
        WHERE patient_id = :patient_id
        ORDER BY created_at DESC
    """)
    
    sagas = session.execute(saga_query, {"patient_id": patient_id}).fetchall()
    
    if sagas:
        for saga in sagas:
            print(f"    📋 Saga encontrada: {saga.id}")
            print(f"       Status: {saga.status}")
            print(f"       Criada em: {saga.created_at}")
            if hasattr(saga, 'error_message') and saga.error_message:
                print(f"       Erro: {saga.error_message}")
    else:
        print("    ⚠️  Nenhuma saga encontrada")
        print("    ℹ️  A saga deveria ser criada automaticamente na criação do paciente")
    
    return len(sagas) > 0


def check_messages(session: Session, patient_id: str):
    """Verifica se mensagens foram enviadas para o paciente."""
    print("\n💬 Verificando mensagens...")
    
    message_query = text("""
        SELECT * FROM messages 
        WHERE patient_id = :patient_id
        ORDER BY created_at DESC
    """)
    
    messages = session.execute(message_query, {"patient_id": patient_id}).fetchall()
    
    if messages:
        for msg in messages:
            print(f"    💬 Mensagem: {msg.id}")
            print(f"       Status: {msg.status}")
            print(f"       Enviada em: {msg.created_at}")
    else:
        print("    ⚠️  Nenhuma mensagem encontrada")
        print("    ℹ️  Mensagens deveriam ser enviadas pela saga de onboarding")
    
    return len(messages) > 0


def check_templates_available(session: Session):
    """Verifica se os templates estão disponíveis."""
    print("\n📄 Verificando templates disponíveis...")
    
    # Flow kinds
    kinds_query = text("SELECT kind_key, display_name FROM flow_kinds WHERE is_active = true")
    kinds = session.execute(kinds_query).fetchall()
    print(f"    📋 Flow kinds: {len(kinds)}")
    for kind in kinds:
        print(f"       - {kind.kind_key}: {kind.display_name}")
    
    # Flow templates
    templates_query = text("""
        SELECT ftv.template_name, ftv.version_number, fk.kind_key
        FROM flow_template_versions ftv
        JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
        WHERE ftv.is_active = true
    """)
    templates = session.execute(templates_query).fetchall()
    print(f"    📄 Flow templates: {len(templates)}")
    for template in templates:
        print(f"       - {template.template_name} v{template.version_number} ({template.kind_key})")
    
    # Quiz templates
    quiz_query = text("SELECT name, version FROM quiz_templates WHERE is_active = true")
    quizzes = session.execute(quiz_query).fetchall()
    print(f"    📝 Quiz templates: {len(quizzes)}")
    for quiz in quizzes:
        print(f"       - {quiz.name} v{quiz.version}")


def main():
    """Função principal."""
    print("=" * 60)
    print("🧪 TESTE DE CRIAÇÃO DE PACIENTE E FLOW")
    print("=" * 60)
    
    try:
        with Session(engine) as session:
            # 1. Verificar templates disponíveis
            check_templates_available(session)
            
            # 2. Criar paciente teste
            patient_id = create_test_patient(session)
            
            # 3. Verificar se saga foi executada
            saga_exists = check_saga_status(session, patient_id)
            
            # 4. Verificar se flow state foi criado
            flow_exists = check_flow_state(session, patient_id)
            
            # 5. Verificar se mensagens foram enviadas
            messages_exist = check_messages(session, patient_id)
            
            print("\n" + "=" * 60)
            print("📊 RESUMO DOS RESULTADOS")
            print("=" * 60)
            print(f"✅ Paciente criado: {patient_id}")
            print(f"{'✅' if saga_exists else '❌'} Saga executada: {saga_exists}")
            print(f"{'✅' if flow_exists else '❌'} Flow state criado: {flow_exists}")
            print(f"{'✅' if messages_exist else '❌'} Mensagens enviadas: {messages_exist}")
            
            if not saga_exists:
                print("\n⚠️  PROBLEMA IDENTIFICADO:")
                print("   A saga de onboarding não foi executada automaticamente.")
                print("   Isso indica que:")
                print("   1. O Celery Beat não está rodando, OU")
                print("   2. A saga não está sendo disparada na criação do paciente, OU")
                print("   3. Há erro na configuração da saga")
                
            if not flow_exists and saga_exists:
                print("\n⚠️  PROBLEMA IDENTIFICADO:")
                print("   A saga foi executada mas o flow state não foi criado.")
                print("   Verificar logs da saga para identificar o erro.")
                
            if not messages_exist and flow_exists:
                print("\n⚠️  PROBLEMA IDENTIFICADO:")
                print("   O flow foi criado mas mensagens não foram enviadas.")
                print("   Verificar integração com WhatsApp/Evolution API.")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
