#!/usr/bin/env python3
"""
Script para adicionar coluna deleted_at na tabela patients
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import get_db


def add_soft_delete_column():
    """Adiciona coluna deleted_at na tabela patients"""
    
    print("🔄 Adicionando suporte a Soft Delete na tabela patients...")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # Verificar se coluna já existe
        print("🔍 Verificando se coluna deleted_at já existe...")
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'patients' 
            AND column_name = 'deleted_at'
        """))
        
        if result.fetchone():
            print("✅ Coluna deleted_at já existe na tabela patients")
            return True
        
        print("⚠️ Coluna deleted_at não existe. Adicionando...")
        
        # Adicionar coluna deleted_at
        print("📝 Executando: ALTER TABLE patients ADD COLUMN deleted_at...")
        db.execute(text("ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE"))
        
        # Adicionar índices para performance
        print("📝 Criando índice para pacientes ativos...")
        db.execute(text("CREATE INDEX idx_patients_active ON patients (deleted_at)"))
        
        print("📝 Criando índice para pacientes deletados...")
        db.execute(text("""
            CREATE INDEX idx_patients_deleted 
            ON patients (deleted_at) 
            WHERE deleted_at IS NOT NULL
        """))
        
        # Commit das mudanças
        db.commit()
        
        print("✅ Coluna deleted_at adicionada com sucesso!")
        print("✅ Índices criados para otimização de performance")
        
        # Verificar resultado
        result = db.execute(text("SELECT COUNT(*) FROM patients WHERE deleted_at IS NULL"))
        active_count = result.scalar()
        
        result = db.execute(text("SELECT COUNT(*) FROM patients WHERE deleted_at IS NOT NULL"))
        deleted_count = result.scalar()
        
        print(f"📊 Pacientes ativos: {active_count}")
        print(f"📊 Pacientes deletados: {deleted_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao adicionar coluna deleted_at: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    success = add_soft_delete_column()
    
    if success:
        print("\n🎉 SOFT DELETE IMPLEMENTADO COM SUCESSO!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. ✅ Coluna deleted_at adicionada")
        print("2. ✅ Índices de performance criados")
        print("3. ✅ Modelo Patient atualizado")
        print("4. ✅ Serviço Patient com soft delete")
        print("5. ✅ Repositório Patient com filtros")
        print("\n💡 AGORA VOCÊ PODE:")
        print("• Deletar pacientes sem perder dados")
        print("• Restaurar pacientes deletados")
        print("• Manter histórico completo")
        print("• Evitar problemas de integridade referencial")
    else:
        print("\n❌ FALHA NA IMPLEMENTAÇÃO")
        print("Verifique os erros acima e tente novamente")