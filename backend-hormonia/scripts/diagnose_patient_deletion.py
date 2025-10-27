#!/usr/bin/env python3
"""
Script para diagnosticar e corrigir problemas de deleção de pacientes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.database import get_db
from app.models.patient import Patient
from app.services.patient import PatientService
from app.dependencies import get_patient_service


async def diagnose_patient_relationships(patient_id: str):
    """Diagnostica relacionamentos que podem impedir a deleção"""
    
    print(f"🔍 DIAGNÓSTICO DE RELACIONAMENTOS - Paciente: {patient_id}")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # Verificar se o paciente existe
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            print(f"❌ Paciente {patient_id} não encontrado")
            return
        
        print(f"✅ Paciente encontrado: {patient.name}")
        print(f"   📧 Email: {patient.email}")
        print(f"   📱 Telefone: {patient.phone}")
        print()
        
        # Verificar relacionamentos que podem impedir deleção
        relationships_to_check = [
            ("messages", "SELECT COUNT(*) FROM messages WHERE patient_id = :patient_id"),
            ("quiz_responses", "SELECT COUNT(*) FROM quiz_responses WHERE patient_id = :patient_id"),
            ("quiz_sessions", "SELECT COUNT(*) FROM quiz_sessions WHERE patient_id = :patient_id"),
            ("flow_states", "SELECT COUNT(*) FROM patient_flow_states WHERE patient_id = :patient_id"),
            ("medical_reports", "SELECT COUNT(*) FROM medical_reports WHERE patient_id = :patient_id"),
            ("alerts", "SELECT COUNT(*) FROM alerts WHERE patient_id = :patient_id"),
            ("onboarding_sagas", "SELECT COUNT(*) FROM patient_onboarding_saga WHERE patient_id = :patient_id"),
            ("treatments", "SELECT COUNT(*) FROM treatments WHERE patient_id = :patient_id"),
            ("appointments", "SELECT COUNT(*) FROM appointments WHERE patient_id = :patient_id"),
            ("medications", "SELECT COUNT(*) FROM medications WHERE patient_id = :patient_id"),
            ("notifications", "SELECT COUNT(*) FROM notifications WHERE related_patient_id = :patient_id"),
            ("consents", "SELECT COUNT(*) FROM consents WHERE patient_id = :patient_id"),
            ("analytics", "SELECT COUNT(*) FROM flow_analytics WHERE patient_id = :patient_id"),
            ("whatsapp_messages", "SELECT COUNT(*) FROM whatsapp_messages WHERE patient_id = :patient_id"),
            ("whatsapp_contacts", "SELECT COUNT(*) FROM whatsapp_contacts WHERE patient_id = :patient_id"),
            ("audit_logs", "SELECT COUNT(*) FROM audit_logs WHERE user_id = :patient_id"),
        ]
        
        blocking_relationships = []
        
        for rel_name, query in relationships_to_check:
            try:
                result = db.execute(text(query), {"patient_id": patient_id}).scalar()
                if result > 0:
                    print(f"⚠️  {rel_name}: {result} registros")
                    blocking_relationships.append((rel_name, result))
                else:
                    print(f"✅ {rel_name}: 0 registros")
            except Exception as e:
                print(f"❓ {rel_name}: Erro ao verificar - {e}")
        
        print()
        
        if blocking_relationships:
            print("🚨 RELACIONAMENTOS QUE PODEM IMPEDIR DELEÇÃO:")
            print("-" * 50)
            for rel_name, count in blocking_relationships:
                print(f"   • {rel_name}: {count} registros")
            print()
            print("💡 SOLUÇÕES POSSÍVEIS:")
            print("1. Implementar deleção em cascata nos relacionamentos")
            print("2. Implementar soft delete (marcar como inativo)")
            print("3. Limpar relacionamentos antes da deleção")
        else:
            print("✅ Nenhum relacionamento bloqueante encontrado")
        
        return blocking_relationships
        
    except Exception as e:
        print(f"❌ Erro durante diagnóstico: {e}")
        return None
    finally:
        db.close()


async def test_patient_deletion(patient_id: str, force: bool = False):
    """Testa a deleção de um paciente"""
    
    print(f"\n🧪 TESTE DE DELEÇÃO - Paciente: {patient_id}")
    print("=" * 60)
    
    if not force:
        print("⚠️  MODO SEGURO: Apenas simulação (use --force para deleção real)")
    
    try:
        # Usar o serviço de pacientes
        patient_service = PatientService()
        
        # Verificar se o paciente existe
        patient = patient_service.get_patient(UUID(patient_id))
        if not patient:
            print(f"❌ Paciente {patient_id} não encontrado")
            return False
        
        print(f"✅ Paciente encontrado: {patient.name}")
        
        if not force:
            print("🔍 Simulando deleção...")
            print("   (Para executar realmente, use --force)")
            return True
        
        # Tentar deletar
        print("🗑️  Executando deleção...")
        result = patient_service.delete_patient(UUID(patient_id))
        
        if result:
            print("✅ Paciente deletado com sucesso!")
            return True
        else:
            print("❌ Falha na deleção do paciente")
            return False
            
    except IntegrityError as e:
        print(f"❌ Erro de integridade referencial: {e}")
        print("💡 Há relacionamentos que impedem a deleção")
        return False
    except Exception as e:
        print(f"❌ Erro durante deleção: {e}")
        return False


async def fix_patient_deletion_constraints():
    """Corrige constraints que impedem deleção de pacientes"""
    
    print("🔧 CORREÇÃO DE CONSTRAINTS DE DELEÇÃO")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # Verificar foreign keys que não têm ON DELETE CASCADE
        foreign_keys_query = """
        SELECT 
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON tc.constraint_name = rc.constraint_name
        WHERE 
            tc.constraint_type = 'FOREIGN KEY' 
            AND ccu.table_name = 'patients'
            AND rc.delete_rule != 'CASCADE'
        ORDER BY tc.table_name;
        """
        
        result = db.execute(text(foreign_keys_query))
        problematic_fks = result.fetchall()
        
        if problematic_fks:
            print("🚨 FOREIGN KEYS SEM CASCADE DELETE:")
            print("-" * 50)
            for fk in problematic_fks:
                print(f"   • {fk.table_name}.{fk.column_name} -> {fk.foreign_table_name}.{fk.foreign_column_name}")
                print(f"     Delete Rule: {fk.delete_rule}")
            
            print("\n💡 RECOMENDAÇÕES:")
            print("1. Adicionar CASCADE DELETE nas foreign keys apropriadas")
            print("2. Ou implementar soft delete para evitar deleção física")
            
        else:
            print("✅ Todas as foreign keys têm regras de deleção apropriadas")
        
        return problematic_fks
        
    except Exception as e:
        print(f"❌ Erro ao verificar constraints: {e}")
        return None
    finally:
        db.close()


async def implement_soft_delete():
    """Implementa soft delete para pacientes"""
    
    print("\n🔄 IMPLEMENTAÇÃO DE SOFT DELETE")
    print("=" * 60)
    
    print("📝 Soft Delete permite 'deletar' sem remover fisicamente do banco")
    print("   Adiciona campo 'deleted_at' e filtra registros ativos")
    print()
    
    # Verificar se já existe coluna deleted_at
    db = next(get_db())
    
    try:
        check_column_query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'patients' 
        AND column_name = 'deleted_at'
        """
        
        result = db.execute(text(check_column_query))
        has_deleted_at = result.fetchone() is not None
        
        if has_deleted_at:
            print("✅ Coluna 'deleted_at' já existe na tabela patients")
        else:
            print("⚠️  Coluna 'deleted_at' não existe")
            print("💡 Para implementar soft delete, execute:")
            print("   ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;")
        
        # Verificar quantos pacientes estão "deletados"
        if has_deleted_at:
            count_query = "SELECT COUNT(*) FROM patients WHERE deleted_at IS NOT NULL"
            deleted_count = db.execute(text(count_query)).scalar()
            
            active_query = "SELECT COUNT(*) FROM patients WHERE deleted_at IS NULL"
            active_count = db.execute(text(active_query)).scalar()
            
            print(f"📊 Pacientes ativos: {active_count}")
            print(f"📊 Pacientes deletados (soft): {deleted_count}")
        
        return has_deleted_at
        
    except Exception as e:
        print(f"❌ Erro ao verificar soft delete: {e}")
        return False
    finally:
        db.close()


def create_soft_delete_migration():
    """Cria script de migração para soft delete"""
    
    print("\n📄 CRIANDO SCRIPT DE MIGRAÇÃO PARA SOFT DELETE")
    print("=" * 60)
    
    migration_content = '''"""Add soft delete to patients table

Revision ID: add_soft_delete_patients
Revises: 
Create Date: 2025-10-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_soft_delete_patients'
down_revision = None  # Update with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Add deleted_at column for soft delete functionality."""
    
    # Add deleted_at column
    op.add_column('patients', 
        sa.Column('deleted_at', 
                 postgresql.TIMESTAMP(timezone=True), 
                 nullable=True)
    )
    
    # Add index for performance on active patients queries
    op.create_index('idx_patients_active', 'patients', ['deleted_at'])
    
    # Add index for soft deleted patients
    op.create_index('idx_patients_deleted', 'patients', ['deleted_at'], 
                   postgresql_where=sa.text('deleted_at IS NOT NULL'))


def downgrade():
    """Remove soft delete functionality."""
    
    # Drop indexes
    op.drop_index('idx_patients_deleted', table_name='patients')
    op.drop_index('idx_patients_active', table_name='patients')
    
    # Drop column
    op.drop_column('patients', 'deleted_at')
'''
    
    migration_path = "backend-hormonia/alembic/versions/add_soft_delete_patients.py"
    
    try:
        with open(migration_path, 'w', encoding='utf-8') as f:
            f.write(migration_content)
        
        print(f"✅ Migração criada: {migration_path}")
        print("📋 Para aplicar:")
        print("   1. cd backend-hormonia")
        print("   2. alembic upgrade head")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar migração: {e}")
        return False


async def main():
    """Função principal"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnosticar problemas de deleção de pacientes")
    parser.add_argument("--patient-id", help="ID do paciente para diagnosticar")
    parser.add_argument("--test-delete", help="ID do paciente para testar deleção")
    parser.add_argument("--force", action="store_true", help="Executar deleção real (não apenas simular)")
    parser.add_argument("--fix-constraints", action="store_true", help="Verificar e sugerir correções de constraints")
    parser.add_argument("--soft-delete", action="store_true", help="Verificar implementação de soft delete")
    parser.add_argument("--create-migration", action="store_true", help="Criar migração para soft delete")
    
    args = parser.parse_args()
    
    print("🔍 DIAGNÓSTICO DE DELEÇÃO DE PACIENTES")
    print("=" * 70)
    print("Este script ajuda a identificar e resolver problemas de deleção")
    print()
    
    if args.patient_id:
        await diagnose_patient_relationships(args.patient_id)
    
    if args.test_delete:
        await test_patient_deletion(args.test_delete, args.force)
    
    if args.fix_constraints:
        await fix_patient_deletion_constraints()
    
    if args.soft_delete:
        await implement_soft_delete()
    
    if args.create_migration:
        create_soft_delete_migration()
    
    if not any([args.patient_id, args.test_delete, args.fix_constraints, args.soft_delete, args.create_migration]):
        print("💡 USO:")
        print("   python scripts/diagnose_patient_deletion.py --patient-id <UUID>")
        print("   python scripts/diagnose_patient_deletion.py --test-delete <UUID>")
        print("   python scripts/diagnose_patient_deletion.py --fix-constraints")
        print("   python scripts/diagnose_patient_deletion.py --soft-delete")
        print("   python scripts/diagnose_patient_deletion.py --create-migration")
        print()
        print("📋 EXEMPLO:")
        print("   # Diagnosticar relacionamentos de um paciente específico")
        print("   python scripts/diagnose_patient_deletion.py --patient-id 123e4567-e89b-12d3-a456-426614174000")
        print()
        print("   # Testar deleção (simulação)")
        print("   python scripts/diagnose_patient_deletion.py --test-delete 123e4567-e89b-12d3-a456-426614174000")
        print()
        print("   # Verificar constraints problemáticas")
        print("   python scripts/diagnose_patient_deletion.py --fix-constraints")


if __name__ == "__main__":
    asyncio.run(main())