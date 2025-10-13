#!/usr/bin/env python3
"""
Aplicar índices críticos de performance
"""
import os
import sys
sys.path.append('.')

from app.database import get_scoped_session
from sqlalchemy import text

def apply_critical_indexes():
    """Aplicar índices críticos para resolver problemas de performance"""
    
    # Índices críticos
    indexes = [
        # 1. MESSAGES: Índices para queries por direction e patient_id (já existem)
        """CREATE INDEX IF NOT EXISTS idx_messages_direction_created_new 
           ON messages (direction, created_at DESC)""",
        
        """CREATE INDEX IF NOT EXISTS idx_messages_patient_id_created_new 
           ON messages (patient_id, created_at DESC)""",
        
        # 2. ALERTS: Índice para queries por status
        """CREATE INDEX IF NOT EXISTS idx_alerts_status_created_new 
           ON alerts (status, created_at DESC)""",
        
        # 3. PATIENTS: Índice para verificação rápida de existência (já existe)
        """CREATE INDEX IF NOT EXISTS idx_patients_id_active_new 
           ON patients (id) WHERE is_active = true""",
        
        # 4. USERS: Índice para Firebase UID lookup (já existe)
        """CREATE INDEX IF NOT EXISTS idx_users_firebase_uid_active_new 
           ON users (firebase_uid) WHERE is_active = true""",
        
        # 5. QUIZ RESPONSES: Índice para monthly quiz stats (já existe)
        """CREATE INDEX IF NOT EXISTS idx_quiz_responses_patient_created_new 
           ON quiz_responses (patient_id, created_at DESC)""",
        
        # 6. REPORTS: Índice para paginação
        """CREATE INDEX IF NOT EXISTS idx_reports_created_new 
           ON reports (created_at DESC)"""
    ]
    
    print("🚀 Aplicando índices críticos de performance...")
    
    with get_scoped_session() as db:
        success_count = 0
        
        for i, index_sql in enumerate(indexes, 1):
            try:
                print(f"[{i}/{len(indexes)}] Criando índice...")
                db.execute(text(index_sql))
                db.commit()
                success_count += 1
                print(f"✅ Índice {i} criado com sucesso")
                
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower():
                    print(f"ℹ️  Índice {i} já existe")
                    success_count += 1
                else:
                    print(f"❌ Erro no índice {i}: {error_msg[:100]}...")
                db.rollback()
    
    print(f"\n🎉 Processo concluído: {success_count}/{len(indexes)} índices aplicados")
    
    # Verificar índices criados
    print("\n📊 Verificando índices criados...")
    with get_scoped_session() as db:
        result = db.execute(text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE indexname LIKE 'idx_%'
            ORDER BY tablename, indexname
        """))
        
        indexes_found = result.fetchall()
        print(f"Total de índices encontrados: {len(indexes_found)}")
        
        for idx in indexes_found:
            print(f"  - {idx.tablename}.{idx.indexname}")

if __name__ == "__main__":
    apply_critical_indexes()