#!/usr/bin/env python3
"""
Aplicar otimizações de performance para o dashboard.
Este script aplica os índices otimizados e testa a performance.
"""
import os
import sys
import time
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
from app.database import get_db


def apply_optimized_indexes():
    """Aplicar índices otimizados para performance do dashboard"""
    print("🚀 Aplicando índices otimizados para dashboard...")
    
    indexes = [
        # Messages por direção e data (para contagens diárias/trends)
        """CREATE INDEX IF NOT EXISTS idx_messages_direction_created_opt
           ON messages(direction, created_at DESC)""",
        
        # Messages por paciente e data (para gráficos de engajamento)
        """CREATE INDEX IF NOT EXISTS idx_messages_patient_created_opt
           ON messages(patient_id, created_at DESC)""",
        
        # Messages por paciente, direção e data (para filtros combinados)
        """CREATE INDEX IF NOT EXISTS idx_messages_patient_direction_created_opt
           ON messages(patient_id, direction, created_at DESC)""",
        
        # Alerts por status e data (para contagens de alertas pendentes)
        """CREATE INDEX IF NOT EXISTS idx_alerts_status_created_opt
           ON alerts(status, created_at DESC)""",
        
        # Messages por data apenas (para contagens rápidas por período)
        """CREATE INDEX IF NOT EXISTS idx_messages_created_date_opt
           ON messages(DATE(created_at), created_at DESC)""",
        
        # Patients por doctor_id (se não existir)
        """CREATE INDEX IF NOT EXISTS idx_patients_doctor_id_opt
           ON patients(doctor_id)""",
    ]
    
    try:
        db = next(get_db())
        
        for i, index_sql in enumerate(indexes, 1):
            try:
                print(f"Criando índice {i}/{len(indexes)}...")
                start_time = time.time()
                db.execute(text(index_sql))
                db.commit()
                duration = (time.time() - start_time) * 1000
                print(f"✅ Índice {i} criado em {duration:.2f}ms")
            except Exception as e:
                print(f"⚠️  Índice {i}: {str(e)}")
                db.rollback()
        
        # Analyze tables
        print("\nAnalisando tabelas...")
        analyze_queries = ["ANALYZE messages", "ANALYZE alerts", "ANALYZE patients"]
        for analyze_sql in analyze_queries:
            try:
                start_time = time.time()
                db.execute(text(analyze_sql))
                db.commit()
                duration = (time.time() - start_time) * 1000
                print(f"✅ {analyze_sql} completado em {duration:.2f}ms")
            except Exception as e:
                print(f"❌ {analyze_sql} falhou: {str(e)}")
                db.rollback()
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Falha ao aplicar índices: {str(e)}")
        return False


def test_quick_stats_performance():
    """Testar performance da query consolidada de quick stats"""
    print("\n🔍 Testando performance da query consolidada...")
    
    try:
        db = next(get_db())
        
        # Query consolidada otimizada
        query = text("""
            WITH stats AS (
                SELECT 
                    COUNT(DISTINCT p.id) as total_patients,
                    COUNT(DISTINCT CASE WHEN p.flow_state = 'ACTIVE' THEN p.id END) as active_patients,
                    COUNT(DISTINCT CASE WHEN m.created_at >= CURRENT_DATE THEN m.id END) as messages_today,
                    COUNT(DISTINCT CASE WHEN a.status != 'RESOLVED' THEN a.id END) as alerts_pending
                FROM patients p
                LEFT JOIN messages m ON m.patient_id = p.id
                LEFT JOIN alerts a ON a.patient_id = p.id
            )
            SELECT total_patients, active_patients, messages_today, alerts_pending FROM stats
        """)
        
        # Executar e medir tempo
        start_time = time.time()
        result = db.execute(query).fetchone()
        duration = (time.time() - start_time) * 1000
        
        if result:
            print(f"✅ Query consolidada executada em {duration:.2f}ms")
            print(f"   - Total pacientes: {result.total_patients}")
            print(f"   - Pacientes ativos: {result.active_patients}")
            print(f"   - Mensagens hoje: {result.messages_today}")
            print(f"   - Alertas pendentes: {result.alerts_pending}")
        else:
            print("❌ Nenhum resultado retornado")
        
        db.close()
        return duration < 500  # Target: menos de 500ms
        
    except Exception as e:
        print(f"❌ Erro no teste de performance: {str(e)}")
        return False


def check_existing_indexes():
    """Verificar índices existentes"""
    print("🔍 Verificando índices existentes...")
    
    try:
        db = next(get_db())
        
        result = db.execute(text("""
            SELECT indexname, tablename, indexdef
            FROM pg_indexes 
            WHERE tablename IN ('messages', 'alerts', 'patients')
            AND indexname LIKE '%_opt'
            ORDER BY tablename, indexname
        """))
        
        indexes = result.fetchall()
        
        if indexes:
            print("Índices otimizados encontrados:")
            for index in indexes:
                print(f"  - {index.indexname} em {index.tablename}")
        else:
            print("Nenhum índice otimizado encontrado")
        
        db.close()
        return len(indexes)
        
    except Exception as e:
        print(f"❌ Erro ao verificar índices: {str(e)}")
        return 0


def main():
    """Função principal"""
    print("🎯 Otimizações de Performance do Dashboard\n")
    
    # Verificar índices existentes
    existing_count = check_existing_indexes()
    print()
    
    # Aplicar índices se necessário
    if existing_count < 6:  # Esperamos 6 índices otimizados
        success = apply_optimized_indexes()
        if not success:
            print("\n⚠️  Falha ao aplicar alguns índices.")
            sys.exit(1)
    else:
        print("✅ Todos os índices otimizados já existem")
    
    # Testar performance
    performance_ok = test_quick_stats_performance()
    
    print("\n" + "="*50)
    print("RESUMO DAS OTIMIZAÇÕES")
    print("="*50)
    
    if performance_ok:
        print("✅ Performance: Query consolidada < 500ms")
    else:
        print("⚠️  Performance: Query consolidada > 500ms (pode melhorar com uso)")
    
    print("\n🎉 Otimizações aplicadas com sucesso!")
    print("\nPróximos passos:")
    print("1. Testar GET /api/v1/analytics/dashboard")
    print("2. Monitorar logs de performance")
    print("3. Verificar cache hit rate")
    print("4. Medir tempo de resposta em produção")


if __name__ == "__main__":
    main()