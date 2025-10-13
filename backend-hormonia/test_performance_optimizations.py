#!/usr/bin/env python3
"""
Testar as otimizações de performance aplicadas
"""
import sys
sys.path.append('.')

import time
import asyncio
from app.services.monthly_quiz_service import MonthlyQuizService
from app.services.analytics_cache import AnalyticsCacheService
from app.database import get_scoped_session

async def test_monthly_quiz_fast_404():
    """Testar verificação rápida de 404 no monthly quiz"""
    
    print("🧪 Testando Monthly Quiz - Fast 404...")
    
    with get_scoped_session() as db:
        service = MonthlyQuizService(db)
        
        # Teste com paciente inexistente
        fake_patient_id = "00000000-0000-0000-0000-000000000001"
        
        # Primeira chamada (cache miss)
        start_time = time.time()
        exists = service._check_patient_exists_fast(fake_patient_id)
        first_call_time = (time.time() - start_time) * 1000
        
        # Segunda chamada (cache hit)
        start_time = time.time()
        exists2 = service._check_patient_exists_fast(fake_patient_id)
        second_call_time = (time.time() - start_time) * 1000
        
        print(f"  📊 Primeira chamada (cache miss): {first_call_time:.1f}ms")
        print(f"  ⚡ Segunda chamada (cache hit): {second_call_time:.1f}ms")
        print(f"  🎯 Speedup: {first_call_time/second_call_time:.1f}x mais rápido")
        
        if second_call_time < 10:  # Menos de 10ms é excelente
            print("  ✅ Cache negativo funcionando perfeitamente!")
        else:
            print("  ⚠️  Cache pode não estar funcionando corretamente")

async def test_analytics_cache():
    """Testar cache de analytics"""
    
    print("\n🧪 Testando Analytics Cache...")
    
    cache_service = AnalyticsCacheService()
    
    # Teste de cache de monthly quiz stats
    test_patient_id = "test-patient-123"
    test_stats = {
        "total_responses": 15,
        "completion_rate": 85.5,
        "avg_score": 7.2,
        "last_response": "2024-01-15T10:30:00Z"
    }
    
    # Cache stats
    start_time = time.time()
    cached = cache_service.cache_monthly_quiz_stats(test_patient_id, test_stats)
    cache_time = (time.time() - start_time) * 1000
    
    # Retrieve stats
    start_time = time.time()
    retrieved = cache_service.get_monthly_quiz_stats(test_patient_id)
    retrieve_time = (time.time() - start_time) * 1000
    
    print(f"  📊 Cache write: {cache_time:.1f}ms")
    print(f"  ⚡ Cache read: {retrieve_time:.1f}ms")
    
    if retrieved == test_stats:
        print("  ✅ Cache funcionando corretamente!")
    else:
        print("  ❌ Problema no cache - dados não coincidem")
    
    # Test invalidation
    invalidated = cache_service.invalidate_monthly_quiz_stats(test_patient_id)
    if invalidated:
        print("  ✅ Invalidação funcionando!")
    
    # Verify invalidation
    retrieved_after = cache_service.get_monthly_quiz_stats(test_patient_id)
    if retrieved_after is None:
        print("  ✅ Cache invalidado com sucesso!")
    else:
        print("  ⚠️  Cache não foi invalidado corretamente")

def test_database_indexes():
    """Testar se os índices foram criados"""
    
    print("\n🧪 Testando Índices de Database...")
    
    with get_scoped_session() as db:
        from sqlalchemy import text
        
        # Verificar índices criados
        result = db.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE indexname LIKE '%_new'
            ORDER BY indexname
        """))
        
        new_indexes = [row[0] for row in result.fetchall()]
        
        expected_indexes = [
            'idx_messages_direction_created_new',
            'idx_messages_patient_id_created_new', 
            'idx_quiz_responses_patient_created_new',
            'idx_users_firebase_uid_active_new'
        ]
        
        print(f"  📊 Índices encontrados: {len(new_indexes)}")
        
        for idx in expected_indexes:
            if idx in new_indexes:
                print(f"  ✅ {idx}")
            else:
                print(f"  ❌ {idx} - NÃO ENCONTRADO")
        
        # Teste de performance de query com índice
        start_time = time.time()
        result = db.execute(text("""
            SELECT COUNT(*) FROM messages 
            WHERE direction = 'outbound'
        """))
        query_time = (time.time() - start_time) * 1000
        
        print(f"  ⚡ Query com índice: {query_time:.1f}ms")
        
        if query_time < 50:  # Menos de 50ms é bom
            print("  ✅ Performance de query excelente!")
        elif query_time < 100:
            print("  ✅ Performance de query boa!")
        else:
            print("  ⚠️  Query pode estar lenta")

def test_pagination_utils():
    """Testar utilitários de paginação"""
    
    print("\n🧪 Testando Utilitários de Paginação...")
    
    try:
        from app.utils.pagination import convert_pagination_params, PaginatedResponse
        from app.schemas.common import PaginationParams
        
        # Teste de conversão
        pagination = PaginationParams(skip=20, limit=10)
        converted = convert_pagination_params(pagination)
        
        expected_page = 3  # skip=20, limit=10 -> page 3
        
        if converted['page'] == expected_page:
            print("  ✅ Conversão de paginação funcionando!")
        else:
            print(f"  ❌ Erro na conversão: esperado page={expected_page}, got {converted['page']}")
        
        # Teste de resposta paginada
        test_items = [1, 2, 3, 4, 5]
        paginated = PaginatedResponse.create(test_items, total=50, pagination=pagination)
        
        if paginated.page == 3 and paginated.has_next and paginated.has_previous:
            print("  ✅ PaginatedResponse funcionando!")
        else:
            print("  ❌ Problema na PaginatedResponse")
            
    except ImportError as e:
        print(f"  ❌ Erro ao importar utilitários: {e}")

async def main():
    """Executar todos os testes de performance"""
    
    print("🚀 TESTANDO OTIMIZAÇÕES DE PERFORMANCE")
    print("=" * 50)
    
    # 1. Testar Monthly Quiz Fast 404
    await test_monthly_quiz_fast_404()
    
    # 2. Testar Analytics Cache
    await test_analytics_cache()
    
    # 3. Testar índices de database
    test_database_indexes()
    
    # 4. Testar utilitários de paginação
    test_pagination_utils()
    
    print("\n" + "=" * 50)
    print("🎉 TESTES DE PERFORMANCE CONCLUÍDOS!")
    print("\n📋 Resumo:")
    print("- Fast 404: Verificação rápida de pacientes")
    print("- Cache: Redis funcionando para stats")
    print("- Índices: Queries otimizadas")
    print("- Paginação: Utilitários padronizados")

if __name__ == "__main__":
    asyncio.run(main())