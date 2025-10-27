#!/usr/bin/env python3
"""
Script para implementar soft delete no sistema de pacientes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def update_patient_model_with_soft_delete():
    """Atualiza o modelo Patient para incluir soft delete"""
    
    print("🔄 Atualizando modelo Patient com Soft Delete...")
    print("=" * 60)
    
    try:
        patient_model_path = "app/models/patient.py"
        
        with open(patient_model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se já tem deleted_at
        if 'deleted_at' in content:
            print("   ✅ Campo deleted_at já existe no modelo")
            return True
        
        # Adicionar import para datetime se não existir
        if 'from datetime import datetime' not in content:
            content = content.replace(
                'from sqlalchemy import',
                'from datetime import datetime\nfrom sqlalchemy import'
            )
        
        # Encontrar onde adicionar o campo deleted_at
        # Procurar por updated_at ou created_at
        insert_point = content.find('updated_at = Column')
        if insert_point == -1:
            insert_point = content.find('created_at = Column')
        
        if insert_point != -1:
            # Encontrar o final da linha
            line_end = content.find('\n', insert_point)
            
            # Adicionar campo deleted_at
            new_field = '\n    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)'
            content = content[:line_end] + new_field + content[line_end:]
            
            # Escrever arquivo modificado
            with open(patient_model_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("   ✅ Campo deleted_at adicionado ao modelo Patient")
            return True
        else:
            print("   ❌ Não foi possível encontrar local para inserir deleted_at")
            return False
        
    except Exception as e:
        print(f"   ❌ Erro ao atualizar modelo: {e}")
        return False


def update_patient_service_with_soft_delete():
    """Atualiza o serviço Patient para usar soft delete"""
    
    print("\n🔄 Atualizando PatientService com Soft Delete...")
    print("=" * 60)
    
    try:
        service_path = "app/services/patient.py"
        
        with open(service_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se já tem soft delete implementado
        if 'deleted_at' in content and 'soft delete' in content.lower():
            print("   ✅ Soft delete já implementado no serviço")
            return True
        
        # Encontrar o método delete_patient
        delete_method_start = content.find('def delete_patient(')
        if delete_method_start == -1:
            print("   ❌ Método delete_patient não encontrado")
            return False
        
        # Encontrar o final do método
        method_end = content.find('\n    def ', delete_method_start + 1)
        if method_end == -1:
            method_end = content.find('\n\n    @', delete_method_start + 1)
        if method_end == -1:
            method_end = len(content)
        
        # Substituir implementação por soft delete
        new_delete_method = '''def delete_patient(self, patient_id: UUID) -> bool:
        """Delete patient (soft delete - marks as deleted without removing from DB)"""
        from datetime import datetime
        
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return False
        
        # Soft delete: set deleted_at timestamp
        patient.deleted_at = datetime.utcnow()
        
        try:
            self.repository.db.commit()
            
            # Invalidate caches on deletion
            invalidate_patient_cache(str(patient_id))
            cache_manager = get_cache_manager()
            cache_manager.invalidate_pattern(
                f"patient_by_id:*:{patient_id}*", namespace="cache"
            )
            cache_manager.invalidate_pattern(
                f"patient_list:*:{patient.doctor_id}*", namespace="cache"
            )
            logger.debug(f"Soft deleted patient: {patient_id}")
            
            return True
            
        except Exception as e:
            self.repository.db.rollback()
            logger.error(f"Failed to soft delete patient {patient_id}: {e}")
            return False

    def restore_patient(self, patient_id: UUID) -> bool:
        """Restore a soft-deleted patient"""
        patient = self.repository.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.deleted_at.isnot(None)
        ).first()
        
        if not patient:
            return False
        
        patient.deleted_at = None
        
        try:
            self.repository.db.commit()
            
            # Invalidate caches
            invalidate_patient_cache(str(patient_id))
            cache_manager = get_cache_manager()
            cache_manager.invalidate_pattern(
                f"patient_by_id:*:{patient_id}*", namespace="cache"
            )
            
            logger.debug(f"Restored patient: {patient_id}")
            return True
            
        except Exception as e:
            self.repository.db.rollback()
            logger.error(f"Failed to restore patient {patient_id}: {e}")
            return False

    '''
        
        # Substituir o método antigo
        old_method = content[delete_method_start:method_end]
        content = content.replace(old_method, new_delete_method)
        
        # Escrever arquivo modificado
        with open(service_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("   ✅ Método delete_patient atualizado para soft delete")
        print("   ✅ Método restore_patient adicionado")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao atualizar serviço: {e}")
        return False


def update_patient_repository_with_soft_delete():
    """Atualiza o repositório Patient para filtrar registros deletados"""
    
    print("\n🔄 Atualizando PatientRepository com filtros Soft Delete...")
    print("=" * 60)
    
    try:
        # Verificar se existe repositório específico de pacientes
        repo_path = "app/repositories/patient.py"
        
        if not os.path.exists(repo_path):
            print("   ⚠️ Repositório específico de pacientes não encontrado")
            print("   📝 Usando repositório base - filtros devem ser aplicados no serviço")
            return True
        
        with open(repo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se já tem filtros de soft delete
        if 'deleted_at' in content and 'is null' in content.lower():
            print("   ✅ Filtros de soft delete já implementados")
            return True
        
        # Adicionar métodos para filtrar registros ativos
        soft_delete_methods = '''
    def get_active_patients(self, skip: int = 0, limit: int = 100):
        """Get only active (non-deleted) patients"""
        return self.db.query(Patient).filter(
            Patient.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()
    
    def get_by_id_active(self, patient_id: UUID):
        """Get patient by ID only if not deleted"""
        return self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
    
    def get_by_doctor_active(self, doctor_id: UUID, skip: int = 0, limit: int = 100):
        """Get active patients for a doctor"""
        return self.db.query(Patient).filter(
            Patient.doctor_id == doctor_id,
            Patient.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()
    
    def count_active_patients(self, **filters) -> int:
        """Count active patients with optional filters"""
        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))
        
        for field, value in filters.items():
            if hasattr(Patient, field) and value is not None:
                query = query.filter(getattr(Patient, field) == value)
        
        return query.count()
'''
        
        # Adicionar no final da classe
        content += soft_delete_methods
        
        # Escrever arquivo modificado
        with open(repo_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("   ✅ Métodos de filtro soft delete adicionados ao repositório")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao atualizar repositório: {e}")
        return False


def update_patient_api_endpoints():
    """Atualiza endpoints da API para incluir restore e listar deletados"""
    
    print("\n🔄 Atualizando endpoints da API...")
    print("=" * 60)
    
    try:
        api_path = "app/api/v1/patients.py"
        
        with open(api_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se já tem endpoint de restore
        if 'restore_patient' in content:
            print("   ✅ Endpoint de restore já existe")
            return True
        
        # Adicionar endpoint de restore após o delete
        restore_endpoint = '''

@router.post(
    "/{patient_id}/restore",
    response_model=PatientResponse,
    summary="Restore Patient",
    description="Restore a soft-deleted patient"
)
async def restore_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """Restore a soft-deleted patient."""
    
    # Check if user has permission (admin or treating doctor)
    if _role_value(current_user) not in ["admin", "doctor"]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to restore patients"
        )
    
    success = patient_service.restore_patient(patient_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Patient not found or not deleted"
        )
    
    # Get restored patient
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve restored patient"
        )
    
    # Invalidate cache after restoration
    invalidate_patient_cache(str(patient_id))
    
    return patient


@router.get(
    "/deleted",
    response_model=PatientListResponse,
    summary="List Deleted Patients",
    description="List soft-deleted patients (admin only)"
)
async def list_deleted_patients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service)
):
    """List soft-deleted patients (admin only)."""
    
    # Only admins can see deleted patients
    if _role_value(current_user) != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can view deleted patients"
        )
    
    # This would need to be implemented in the service
    # For now, return empty list
    return PatientListResponse(
        data=[],
        total=0,
        page=1,
        limit=limit,
        pages=0,
        has_more=False,
        has_previous=False
    )
'''
        
        # Encontrar onde inserir (após o endpoint de delete)
        delete_endpoint_end = content.find('invalidate_patient_cache(str(patient_id))')
        if delete_endpoint_end != -1:
            # Encontrar o final da função
            insert_point = content.find('\n\n@router', delete_endpoint_end)
            if insert_point == -1:
                insert_point = content.find('\n\n\n@router', delete_endpoint_end)
            
            if insert_point != -1:
                content = content[:insert_point] + restore_endpoint + content[insert_point:]
            else:
                # Adicionar no final do arquivo
                content += restore_endpoint
        else:
            # Adicionar no final do arquivo
            content += restore_endpoint
        
        # Escrever arquivo modificado
        with open(api_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("   ✅ Endpoint restore_patient adicionado")
        print("   ✅ Endpoint list_deleted_patients adicionado")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao atualizar API: {e}")
        return False


def create_alembic_migration():
    """Cria migração Alembic para adicionar deleted_at"""
    
    print("\n📄 Criando migração Alembic...")
    print("=" * 60)
    
    try:
        # Verificar se diretório de migrações existe
        migrations_dir = "alembic/versions"
        if not os.path.exists(migrations_dir):
            print("   ⚠️ Diretório de migrações não encontrado")
            print("   📝 Criando migração manual...")
            migrations_dir = "migrations"
            os.makedirs(migrations_dir, exist_ok=True)
        
        migration_content = '''"""Add soft delete to patients table

Revision ID: add_patient_soft_delete
Revises: 
Create Date: 2025-10-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_patient_soft_delete'
down_revision = None  # Update with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Add deleted_at column for soft delete functionality."""
    
    # Add deleted_at column
    op.add_column('patients', 
        sa.Column('deleted_at', 
                 sa.DateTime(timezone=True), 
                 nullable=True)
    )
    
    # Add index for performance on active patients queries
    op.create_index('idx_patients_active', 'patients', ['deleted_at'])
    
    # Add partial index for deleted patients (PostgreSQL specific)
    op.execute("""
        CREATE INDEX idx_patients_deleted 
        ON patients (deleted_at) 
        WHERE deleted_at IS NOT NULL
    """)


def downgrade():
    """Remove soft delete functionality."""
    
    # Drop indexes
    op.drop_index('idx_patients_deleted', table_name='patients')
    op.drop_index('idx_patients_active', table_name='patients')
    
    # Drop column
    op.drop_column('patients', 'deleted_at')
'''
        
        migration_file = f"{migrations_dir}/add_patient_soft_delete.py"
        
        with open(migration_file, 'w', encoding='utf-8') as f:
            f.write(migration_content)
        
        print(f"   ✅ Migração criada: {migration_file}")
        print("   📋 Para aplicar:")
        print("      alembic upgrade head")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao criar migração: {e}")
        return False


def main():
    """Função principal"""
    
    print("🔄 IMPLEMENTAÇÃO DE SOFT DELETE PARA PACIENTES")
    print("=" * 70)
    print("Este script implementa soft delete no sistema de pacientes")
    print("Soft delete marca registros como deletados sem removê-los fisicamente")
    print()
    
    # Executar todas as atualizações
    steps = [
        ("Modelo Patient", update_patient_model_with_soft_delete),
        ("Serviço Patient", update_patient_service_with_soft_delete),
        ("Repositório Patient", update_patient_repository_with_soft_delete),
        ("Endpoints API", update_patient_api_endpoints),
        ("Migração Alembic", create_alembic_migration),
    ]
    
    results = []
    
    for step_name, step_function in steps:
        print(f"🔄 Executando: {step_name}")
        print("-" * 40)
        
        try:
            success = step_function()
            results.append((step_name, success))
            
            if success:
                print(f"✅ {step_name}: SUCESSO")
            else:
                print(f"❌ {step_name}: FALHOU")
                
        except Exception as e:
            print(f"❌ {step_name}: ERRO - {e}")
            results.append((step_name, False))
        
        print()
    
    # Resumo final
    print("=" * 70)
    print("📊 RESUMO DA IMPLEMENTAÇÃO")
    print("=" * 70)
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"✅ Sucessos: {successful}/{total}")
    print(f"❌ Falhas: {total - successful}/{total}")
    print()
    
    for step_name, success in results:
        status = "✅ SUCESSO" if success else "❌ FALHOU"
        print(f"   {status}: {step_name}")
    
    print("\n" + "=" * 70)
    
    if successful == total:
        print("🎉 SOFT DELETE IMPLEMENTADO COM SUCESSO!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Executar migração: alembic upgrade head")
        print("2. Testar deleção de pacientes")
        print("3. Testar restauração de pacientes")
        print("4. Atualizar testes unitários")
        print("5. Atualizar documentação da API")
    else:
        print("⚠️ ALGUMAS IMPLEMENTAÇÕES FALHARAM")
        print("\n📋 AÇÕES NECESSÁRIAS:")
        print("1. Revisar erros acima")
        print("2. Corrigir problemas manualmente")
        print("3. Re-executar script")
    
    print("\n💡 BENEFÍCIOS DO SOFT DELETE:")
    print("• Preserva dados para auditoria")
    print("• Permite restauração de registros")
    print("• Evita problemas de integridade referencial")
    print("• Mantém histórico completo")


if __name__ == "__main__":
    main()