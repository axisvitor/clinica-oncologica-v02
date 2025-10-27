#!/usr/bin/env python3
"""
Script para testar a conexão com Redis e diagnosticar problemas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from datetime import datetime

async def test_redis_connection():
    """Testa a conexão com Redis"""
    
    print("🔍 Testando conexão com Redis...")
    print("=" * 50)
    
    try:
        # Teste 1: Importar redis_unified
        print("1. Testando importação do redis_unified...")
        from app.core.redis_unified import get_async_redis, get_sync_redis
        print("   ✅ Importação bem-sucedida")
        
        # Teste 2: Obter cliente async
        print("\n2. Testando cliente Redis async...")
        redis_async = await get_async_redis()
        if redis_async is None:
            print("   ❌ Cliente async é None")
            return False
        print("   ✅ Cliente async obtido")
        
        # Teste 3: Ping async
        print("\n3. Testando ping async...")
        pong = await redis_async.ping()
        print(f"   ✅ Ping async: {pong}")
        
        # Teste 4: Set/Get async
        print("\n4. Testando set/get async...")
        test_key = "test:analytics:connection"
        test_value = {"timestamp": datetime.now().isoformat(), "test": True}
        
        await redis_async.setex(test_key, 60, json.dumps(test_value))
        print("   ✅ Set realizado")
        
        cached = await redis_async.get(test_key)
        if cached:
            parsed = json.loads(cached)
            print(f"   ✅ Get realizado: {parsed}")
        else:
            print("   ❌ Get falhou - valor não encontrado")
            return False
        
        # Teste 5: Delete
        await redis_async.delete(test_key)
        print("   ✅ Delete realizado")
        
        # Teste 6: Cliente sync
        print("\n5. Testando cliente Redis sync...")
        redis_sync = get_sync_redis()
        if redis_sync is None:
            print("   ❌ Cliente sync é None")
            return False
        print("   ✅ Cliente sync obtido")
        
        # Teste 7: Ping sync
        print("\n6. Testando ping sync...")
        pong_sync = redis_sync.ping()
        print(f"   ✅ Ping sync: {pong_sync}")
        
        print("\n" + "=" * 50)
        print("✅ TODOS OS TESTES PASSARAM!")
        print("   Redis está funcionando corretamente")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_analytics_cache():
    """Testa especificamente o cache do analytics"""
    
    print("\n🧪 Testando cache do analytics...")
    print("=" * 50)
    
    try:
        # Importar as funções de cache do analytics
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'api', 'v2'))
        
        # Simular as funções de cache
        from app.core.redis_unified import get_async_redis
        import json
        import hashlib
        
        redis_client = await get_async_redis()
        if redis_client is None:
            print("❌ Redis não disponível para cache")
            return False
        
        # Testar cache key generation
        def _get_cache_key(endpoint: str, **params) -> str:
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()
            return f"analytics:v2:{endpoint}:{param_hash}"
        
        cache_key = _get_cache_key(
            "treatment-distribution",
            period="30d",
            role="doctor",
            user="test-user"
        )
        
        print(f"1. Cache key gerada: {cache_key}")
        
        # Testar set cache
        test_data = {
            "period": "30d",
            "total_patients": 10,
            "distribution": [
                {"treatment_type": "Quimioterapia", "count": 5, "percentage": 50.0, "color": "#2563eb"},
                {"treatment_type": "Radioterapia", "count": 3, "percentage": 30.0, "color": "#10b981"},
                {"treatment_type": "Não informado", "count": 2, "percentage": 20.0, "color": "#f59e0b"}
            ],
            "trend_data": [],
            "last_updated": datetime.now().isoformat()
        }
        
        await redis_client.setex(cache_key, 900, json.dumps(test_data, default=str))
        print("2. ✅ Cache set realizado")
        
        # Testar get cache
        cached = await redis_client.get(cache_key)
        if cached:
            parsed = json.loads(cached)
            print("3. ✅ Cache get realizado")
            print(f"   Total patients: {parsed['total_patients']}")
            print(f"   Distribution items: {len(parsed['distribution'])}")
        else:
            print("3. ❌ Cache get falhou")
            return False
        
        # Limpar cache de teste
        await redis_client.delete(cache_key)
        print("4. ✅ Cache limpo")
        
        print("\n✅ Cache do analytics funcionando!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO no cache: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Função principal"""
    
    print("🔧 Diagnóstico Redis - Analytics API v2")
    print("=" * 60)
    
    # Testar conexão básica
    redis_ok = await test_redis_connection()
    
    if redis_ok:
        # Testar cache específico do analytics
        cache_ok = await test_analytics_cache()
        
        if cache_ok:
            print("\n🎉 DIAGNÓSTICO COMPLETO!")
            print("   Redis e cache do analytics estão funcionando")
            print("   O erro 500 deve ter outra causa")
        else:
            print("\n⚠️  Redis funciona, mas cache do analytics tem problemas")
    else:
        print("\n❌ Redis não está funcionando")
        print("   Verifique a configuração e conectividade")

if __name__ == "__main__":
    asyncio.run(main())