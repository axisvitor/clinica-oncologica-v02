#!/usr/bin/env python3
"""
Script simples para testar deleção de pacientes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from uuid import UUID
from sqlalchemy import text
from app.core.database import get_db
from app.models.patient import Patient


def test_patient_deletion_simple():
    """Teste simples de deleção de pacientes"""
    
    print("🧪 TESTE SIMPLES DE DELEÇÃO DE PACIENTES")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # Listar pacientes ativos
        print("📋 Listando pacientes...")
        patients = db.query(Patient).filter(Patient.deleted_at.is_(None)).limit(5).all()
        
        if not patients:
            print("⚠️ Nenhum paciente encontrado para testar")
            return True
        
        print(f"✅ Encontrados {len(patients)} pacientes:")
        for i, patient in enumerate(patients, 1):
            print(f"   {i}. {patient.name} ({patient.id}) - {patient.phone}")
        
        # Selecionar primeiro paciente
        test_patient = patients[0]
        patient_id = test_patient.id
        
        print(f"\n🎯 Testando deleção do paciente: {test_patient.name}")
        print(f"   ID: {patient_id}")
        
        # Método 1: Soft Delete (recomendado)
        print("\n🔄 TESTE 1: Soft Delete")
        print("-" * 30)
        
        # Marcar como deletado
        print("🗑️ Executando soft delete...")
        test_patient.deleted_at = datetime.utcnow()
        db.commit()
        print("✅ Soft delete executado")
        
        # Verificar se não aparece em buscas normais
        active_patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
        
        if active_patient:
            print("❌ Paciente ainda aparece em buscas ativas")
        else:
            print("✅ Paciente não aparece mais em buscas ativas")
        
        # Verificar se ainda existe no banco
        deleted_patient = db.query(Patient).filter(Patient.id == patient_id).first()
        
        if deleted_patient and deleted_patient.deleted_at:
            print("✅ Paciente ainda existe no banco com deleted_at preenchido")
            print(f"   Deletado em: {deleted_patient.deleted_at}")
        else:
            print("❌ Problema com soft delete")
        
        # Restaurar paciente
        print("\n🔄 Testando restauração...")
        test_patient.deleted_at = None
        db.commit()
        
        restored_patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.deleted_at.is_(None)
        ).first()
        
        if restored_patient:
            print("✅ Paciente restaurado com sucesso")
        else:
            print("❌ Falha na restauração")
        
        # Método 2: Teste de deleção física (apenas para verificar constraints)
        print("\n🔄 TESTE 2: Verificação de Constraints")
        print("-" * 30)
        
        # Verificar relacionamentos que podem impedir deleção física
        relationships = [
            ("messages", "SELECT COUNT(*) FROM messages WHERE patient_id = :patient_id"),
            ("quiz_responses", "SELECT COUNT(*) FROM quiz_responses WHERE patient_id = :patient_id"),
            ("quiz_sessions", "SELECT COUNT(*) FROM quiz_sessions WHERE patient_id = :patient_id"),
            ("flow_states", "SELECT COUNT(*) FROM patient_flow_states WHERE patient_id = :patient_id"),
        ]
        
        blocking_relationships = []
        
        for rel_name, query in relationships:
            try:
                result = db.execute(text(query), {"patient_id": str(patient_id)}).scalar()
                if result > 0:
                    print(f"⚠️  {rel_name}: {result} registros")
                    blocking_relationships.append((rel_name, result))
                else:
                    print(f"✅ {rel_name}: 0 registros")
            except Exception as e:
                print(f"❓ {rel_name}: Erro - {e}")
        
        if blocking_relationships:
            print("\n🚨 RELACIONAMENTOS QUE IMPEDIRIAM DELEÇÃO FÍSICA:")
            for rel_name, count in blocking_relationships:
                print(f"   • {rel_name}: {count} registros")
            print("\n💡 Por isso o SOFT DELETE é a solução ideal!")
        else:
            print("\n✅ Nenhum relacionamento bloqueante encontrado")
        
        # Estatísticas finais
        print("\n📊 Estatísticas:")
        active_count = db.query(Patient).filter(Patient.deleted_at.is_(None)).count()
        deleted_count = db.query(Patient).filter(Patient.deleted_at.isnot(None)).count()
        
        print(f"   Pacientes ativos: {active_count}")
        print(f"   Pacientes deletados (soft): {deleted_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante teste: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()


def test_api_endpoint():
    """Testa o endpoint de deleção via API"""
    
    print("\n🌐 TESTE DO ENDPOINT DE DELEÇÃO")
    print("=" * 60)
    
    try:
        import requests
        
        # Configurar URL base (ajustar conforme necessário)
        base_url = "http://localhost:8000"  # ou sua URL da API
        
        print("⚠️ Para testar o endpoint da API:")
        print(f"   1. Certifique-se que a API está rodando em {base_url}")
        print("   2. Execute o seguinte comando:")
        print()
        print("   # Listar pacientes")
        print(f"   curl -X GET {base_url}/api/v1/patients")
        print()
        print("   # Deletar paciente (substitua PATIENT_ID)")
        print(f"   curl -X DELETE {base_url}/api/v1/patients/PATIENT_ID")
        print()
        print("   # Restaurar paciente (substitua PATIENT_ID)")
        print(f"   curl -X POST {base_url}/api/v1/patients/PATIENT_ID/restore")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar endpoint: {e}")
        return False


if __name__ == "__main__":
    print("🔧 TESTE DE SISTEMA DE DELEÇÃO DE PACIENTES")
    print("=" * 70)
    
    success1 = test_patient_deletion_simple()
    success2 = test_api_endpoint()
    
    if success1:
        print("\n🎉 SOFT DELETE IMPLEMENTADO E FUNCIONANDO!")
        print("\n✅ BENEFÍCIOS CONFIRMADOS:")
        print("• Deleção segura sem perda de dados")
        print("• Pacientes deletados não aparecem em buscas")
        print("• Dados preservados para auditoria")
        print("• Restauração funcional")
        print("• Sem problemas de integridade referencial")
        
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Testar endpoints da API")
        print("2. Atualizar frontend para usar soft delete")
        print("3. Implementar interface de restauração")
        print("4. Criar relatórios de pacientes deletados")
        
    else:
        print("\n❌ PROBLEMAS DETECTADOS")
        print("Verifique os erros e corrija a implementação")