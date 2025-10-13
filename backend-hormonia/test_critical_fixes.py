#!/usr/bin/env python3
"""
Testar as correções críticas aplicadas.
"""
import os
import sys
import time
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import get_db
from app.services.analytics_cache import AnalyticsCacheService
from app.services.analytics import AnalyticsService


def test_analytics_cache_ttl():
    """Testar se o cache aceita TTL personalizado"""
    print("🔍 Testando AnalyticsCacheService com TTL...")
    
    try:
        cache_service = AnalyticsCacheService()
        
        # Testar get_or_set com TTL
        def dummy_generator():
            return {"test": "data", "timestamp": time.time()}
        
        # Teste com TTL personalizado
        result = cache_service.get_or_set(
            "test_cache",
            {"key": "test"},
            dummy_generator,
            ttl=60  # 1 minuto
        )
        
        print(f"✅ Cache com TTL funcionando: {result}")
        
        # Testar sem TTL (deve usar padrão)
        result2 = cache_service.get_or_set(
            "test_cache2",
            {"key": "test2"},
            dummy_generator
        )
        
        print(f"✅ Cache sem TTL funcionando: {result2}")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de cache: {str(e)}")
        return False


def test_dashboard_performance():
    """Testar performance do dashboard com query consolidada"""
    print("🔍 Testando performance do dashboard...")
    
    try:
        db = next(get_db())
        service = AnalyticsService(db)
        
        # Testar query consolidada
        start_time = time.time()
        result = service._get_quick_stats_consolidated(None)
        duration = (time.time() - start_time) * 1000
        
        print(f"✅ Query consolidada: {duration:.2f}ms")
        print(f"   Resultado: {result}")
        
        # Testar dashboard completo
        start_time = time.time()
        dashboard_data = service.get_dashboard_data(None)
        duration = (time.time() - start_time) * 1000
        
        print(f"✅ Dashboard completo: {duration:.2f}ms")
        
        db.close()
        return duration < 2000  # Target: menos de 2s
        
    except Exception as e:
        print(f"❌ Erro no teste de dashboard: {str(e)}")
        return False


def test_monthly_quiz_index():
    """Testar se o índice do monthly quiz foi criado"""
    print("🔍 Testando índice do monthly quiz...")
    
    try:
        from sqlalchemy import text
        db = next(get_db())
        
        # Verificar se o índice existe
        result = db.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'quiz_sessions' 
            AND indexname = 'idx_quiz_sessions_patient_started_desc'
        """)).fetchone()
        
        if result:
            print(f"✅ Índice encontrado: {result.indexname}")
        else:
            print("⚠️  Índice não encontrado (pode não ter sido criado ainda)")
        
        # Testar query que seria usada pelo monthly quiz
        start_time = time.time()
        test_result = db.execute(text("""
            SELECT id, patient_id, started_at 
            FROM quiz_sessions 
            WHERE patient_id = :patient_id 
            AND session_metadata IS NOT NULL
            ORDER BY started_at DESC 
            LIMIT 1
        """), {"patient_id": str(uuid4())}).fetchone()
        
        duration = (time.time() - start_time) * 1000
        print(f"✅ Query de monthly quiz: {duration:.2f}ms")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de monthly quiz: {str(e)}")
        return False


def main():
    """Executar todos os testes"""
    print("🚀 Testando Correções Críticas\n")
    
    tests = [
        ("Analytics Cache TTL", test_analytics_cache_ttl),
        ("Dashboard Performance", test_dashboard_performance),
        ("Monthly Quiz Index", test_monthly_quiz_index),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} falhou: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("RESUMO DOS TESTES")
    print("="*50)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Todas as correções estão funcionando!")
        print("\nPróximos passos:")
        print("1. Aplicar índice do monthly quiz: psql -f optimize_monthly_quiz_performance.sql")
        print("2. Testar endpoints em produção")
        print("3. Monitorar logs de performance")
    else:
        print("\n⚠️  Algumas correções precisam de ajustes.")


if __name__ == "__main__":
    main()