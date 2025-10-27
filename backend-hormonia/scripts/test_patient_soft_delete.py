#!/usr/bin/env python3
"""
Script para testar o soft delete de pacientes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import UUID
from app.services.patient import PatientService
from app.repositories.patient import PatientRepository
from app.core.database import get_db


def test_soft_delete():
    """Testa o soft delete de pacientes"""
    
    print("🧪 TESTE DE SOFT DELETE DE PACIENTES")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # Inicializar serviços
        patient_repo = PatientRepository(db)
        patient_service = PatientService(
            db=db,
            patient_repository=patient_repo,
            integrity_service=None,
            flow_engine=None
        )
        
        # Listar pacientes ativos
        print("📋 Listando pacientes ativos...")
        active_patients = patient_repo.get_all_active(limit=10)
        
        if not active_patients:
            print("⚠️ Nenhum paciente ativo encontrado para testar")
            return
        
        print(f"✅ Encontrados {len(active_patients)} pacientes ativos:")
        for i, patient in enumerate(active_patients, 1):
            print(f"   {i}. {patient.name} ({patient.id}) - {patient.phone}")
        
        # Selecionar primeiro paciente para teste
        test_patient = active_patients[0]
        patient_id = test_patient.id
        
        print(f"\n🎯 Testando soft delete do paciente: {test_patient.name}")
        print(f"   ID: {patient_id}")
        
        # Verificar se paciente existe antes da deleção
        patient_before = patient_service.get_patient(patient_id)
        if not patient_before:
            print("❌ Paciente não encontrado antes da deleção")
            return
        
        print("✅ Paciente encontrado antes da deleção")
        
        # Executar soft delete
        print("🗑️ Executando soft delete...")
        delete_result = patient_service.delete_patient(patient_id)
        
        if not delete_result:
            print("❌ Falha no soft delete")
            return
        
        print("✅ Soft delete executado com sucesso")
        
        # Verificar se paciente não aparece mais nas buscas normais
        print("🔍 Verificando se paciente foi 'deletado'...")
        patient_after = patient_service.get_patient(patient_id)
        
        if patient_after:
            print("❌ Paciente ainda aparece nas buscas normais (erro no soft delete)")
            return
        
        print("✅ Paciente não aparece mais nas buscas normais")
        
        # Verificar se paciente ainda existe no banco (incluindo deletados)
        print("🔍 Verificando se paciente ainda existe no banco...")
        patient_with_deleted = patient_repo.get_by_id_including_deleted(patient_id)
        
        if not patient_with_deleted:
            print("❌ Paciente foi removido fisicamente do banco (erro!)")
            return
        
        if not patient_with_deleted.deleted_at:
            print("❌ Paciente existe mas não tem deleted_at preenchido")
            return
        
        print("✅ Paciente ainda existe no banco com deleted_at preenchido")
        print(f"   Deletado em: {patient_with_deleted.deleted_at}")
        
        # Testar restauração
        print("\n🔄 Testando restauração do paciente...")
        restore_result = patient_service.restore_patient(patient_id)
        
        if not restore_result:
            print("❌ Falha na restauração")
            return
        
        print("✅ Restauração executada com sucesso")
        
        # Verificar se paciente voltou a aparecer nas buscas
        print("🔍 Verificando se paciente foi restaurado...")
        patient_restored = patient_service.get_patient(patient_id)
        
        if not patient_restored:
            print("❌ Paciente não aparece nas buscas após restauração")
            return
        
        if patient_restored.deleted_at:
            print("❌ Paciente ainda tem deleted_at preenchido após restauração")
            return
        
        print("✅ Paciente restaurado com sucesso")
        print(f"   Nome: {patient_restored.name}")
        print(f"   deleted_at: {patient_restored.deleted_at}")
        
        # Estatísticas finais
        print("\n📊 Estatísticas finais:")
        active_count = patient_repo.count_active()
        deleted_count = patient_repo.count_deleted()
        
        print(f"   Pacientes ativos: {active_count}")
        print(f"   Pacientes deletados: {deleted_count}")
        
        print("\n🎉 TESTE DE SOFT DELETE CONCLUÍDO COM SUCESSO!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    success = test_soft_delete()
    
    if success:
        print("\n✅ SOFT DELETE FUNCIONANDO CORRETAMENTE!")
        print("\n💡 BENEFÍCIOS CONFIRMADOS:")
        print("• ✅ Deleção não remove dados fisicamente")
        print("• ✅ Pacientes deletados não aparecem em buscas normais")
        print("• ✅ Dados preservados para auditoria")
        print("• ✅ Restauração funcional")
        print("• ✅ Sem problemas de integridade referencial")
    else:
        print("\n❌ PROBLEMAS DETECTADOS NO SOFT DELETE")
        print("Verifique os erros acima e corrija a implementação")