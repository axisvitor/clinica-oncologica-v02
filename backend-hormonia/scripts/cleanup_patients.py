"""
Script de limpeza completa de pacientes do banco de dados de produção.

⚠️ ATENÇÃO: Este script remove TODOS os pacientes e dados relacionados!
Use apenas antes de ir para produção.

Uso: python scripts/cleanup_patients.py
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_database_url():
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL not found in environment")
    return url


def cleanup_patients():
    """Remove all patients and related data from database."""
    db_url = get_database_url()
    
    # Show connection info (masked)
    masked_url = db_url.split("@")[1] if "@" in db_url else db_url
    print(f"\n{'='*60}")
    print("🗑️  LIMPEZA DE PACIENTES DO BANCO DE PRODUÇÃO")
    print(f"{'='*60}")
    print(f"📍 Database: {masked_url}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    
    # Tabelas a limpar (ordem de exclusão respeitando foreign keys)
    tables_to_clean = [
        ("quiz_responses", "Respostas de Questionários"),
        ("quiz_sessions", "Sessões de Questionários"),
        ("patient_onboarding_sagas", "Sagas de Onboarding"),
        ("patient_flow_states", "Estados de Fluxo"),
        ("message_status_events", "Eventos de Status de Mensagens"),
        ("messages", "Mensagens"),
        ("medical_reports", "Relatórios Médicos"),
        ("reports", "Relatórios"),
        ("alerts", "Alertas"),
        ("treatments", "Tratamentos"),
        ("appointments", "Agendamentos"),
        ("medications", "Medicações"),
        ("notifications", "Notificações"),
        ("consents", "Consentimentos"),
        ("flow_analytics", "Analytics de Fluxo"),
        ("patient_summaries", "Resumos de Pacientes"),
        ("data_access_requests", "Requisições de Acesso (LGPD)"),
        ("patients", "Pacientes"),
    ]
    
    # Count records using fresh session per query
    print("📊 Contagem atual de registros:")
    counts = {}
    
    for table_name, description in tables_to_clean:
        session = Session()
        try:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            counts[table_name] = count
            if count > 0:
                print(f"  ✓ {description}: {count} registros")
            session.commit()
        except Exception:
            session.rollback()
            counts[table_name] = 0
        finally:
            session.close()
    
    total = sum(counts.values())
    print(f"\n📦 Total de registros a serem removidos: {total}")
    
    if total == 0:
        print("\n✅ Banco já está limpo! Nenhum registro para remover.")
        engine.dispose()
        return
    
    # Confirm
    print(f"\n{'='*60}")
    print("⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!")
    print(f"{'='*60}")
    response = input("\n❓ Deseja continuar? Digite 'SIM' para confirmar: ")
    
    if response.strip().upper() != "SIM":
        print("\n❌ Operação cancelada pelo usuário.")
        engine.dispose()
        return
    
    print("\n🔄 Iniciando limpeza...\n")
    
    # Delete records using fresh session per table
    deleted_counts = {}
    
    for table_name, description in tables_to_clean:
        if counts.get(table_name, 0) > 0:
            session = Session()
            try:
                result = session.execute(text(f"DELETE FROM {table_name}"))
                deleted = result.rowcount
                deleted_counts[table_name] = deleted
                session.commit()
                print(f"  ✓ {description}: {deleted} registros removidos")
            except Exception as e:
                session.rollback()
                print(f"  ❌ {description}: Erro - {e}")
            finally:
                session.close()
    
    total_deleted = sum(deleted_counts.values())
    print(f"\n{'='*60}")
    print(f"✅ LIMPEZA CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"📊 Total de registros removidos: {total_deleted}")
    print(f"⏰ Finalizado em: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    engine.dispose()


if __name__ == "__main__":
    cleanup_patients()
