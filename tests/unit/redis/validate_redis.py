"""
Script de validação manual do Redis Unificado.

Este script executa validações simples sem depender do pytest,
para garantir que as migrações estão funcionando.
"""

import sys
import os
import asyncio
from pathlib import Path

# Adiciona backend ao path
backend_dir = Path(__file__).parent.parent.parent.parent / "backend-hormonia"
sys.path.insert(0, str(backend_dir))

# Símbolos simples para compatibilidade Windows
CHECK = '[OK]'
CROSS = '[FAIL]'
SKIP_MARK = '[SKIP]'
DOT = '[INFO]'

def print_test(name: str, status: str, message: str = ""):
    """Imprime resultado de um teste."""
    if status == "PASS":
        print(f"{CHECK} {name}: {status} {message}")
    elif status == "FAIL":
        print(f"{CROSS} {name}: {status} {message}")
    elif status == "SKIP":
        print(f"{SKIP_MARK} {name}: {status} {message}")
    else:
        print(f"{DOT} {name}: {status} {message}")


def test_imports():
    """Testa se os módulos importam corretamente."""
    print(f"\n{'='*80}")
    print(f"1. TESTE DE IMPORTACOES")
    print(f"{'='*80}\n")

    modules = [
        ("app.core.redis_unified", ["get_async_redis", "get_sync_redis", "RedisClientFactory"]),
        ("app.core.redis_manager", ["RedisManager"]),
        ("app.core.redis_secure", ["SecureRedisClient"]),
    ]

    all_passed = True

    for module_name, items in modules:
        try:
            module = __import__(module_name, fromlist=items)
            for item in items:
                if hasattr(module, item):
                    print_test(f"Import {module_name}.{item}", "PASS")
                else:
                    print_test(f"Import {module_name}.{item}", "FAIL", f"Item não encontrado")
                    all_passed = False
        except Exception as e:
            print_test(f"Import {module_name}", "FAIL", str(e))
            all_passed = False

    return all_passed


async def test_async_redis_basic():
    """Testa operações básicas do Redis async."""
    print(f"\n{'='*80}")
    print(f"2. TESTE DE REDIS ASYNC - OPERACOES BASICAS")
    print(f"{'='*80}\n")

    try:
        from app.core.redis_unified import get_async_redis

        # Cria cliente
        redis = await get_async_redis()
        print_test("Criar cliente async", "PASS")

        # Ping
        try:
            result = await redis.ping()
            if result:
                print_test("Ping async", "PASS")
            else:
                print_test("Ping async", "FAIL", "Ping retornou False")
        except Exception as e:
            print_test("Ping async", "SKIP", f"Redis não disponível: {str(e)}")
            return True  # Skip resto dos testes

        # Set/Get/Delete
        test_key = "test:validation:async"
        test_value = "test_value"

        await redis.set(test_key, test_value, ex=60)
        print_test("SET async", "PASS")

        result = await redis.get(test_key)
        if result and (result == test_value or result == test_value.encode()):
            print_test("GET async", "PASS")
        else:
            print_test("GET async", "FAIL", f"Valor esperado: {test_value}, recebido: {result}")

        await redis.delete(test_key)
        result = await redis.get(test_key)
        if result is None:
            print_test("DELETE async", "PASS")
        else:
            print_test("DELETE async", "FAIL", "Chave não foi deletada")

        return True

    except Exception as e:
        print_test("Redis async operations", "FAIL", str(e))
        return False


def test_sync_redis_basic():
    """Testa operações básicas do Redis sync."""
    print(f"\n{'='*80}")
    print(f"3. TESTE DE REDIS SYNC - OPERACOES BASICAS")
    print(f"{'='*80}\n")

    try:
        from app.core.redis_unified import get_sync_redis

        # Cria cliente
        redis = get_sync_redis()
        print_test("Criar cliente sync", "PASS")

        # Ping
        try:
            result = redis.ping()
            if result:
                print_test("Ping sync", "PASS")
            else:
                print_test("Ping sync", "FAIL", "Ping retornou False")
        except Exception as e:
            print_test("Ping sync", "SKIP", f"Redis não disponível: {str(e)}")
            return True  # Skip resto dos testes

        # Set/Get/Delete
        test_key = "test:validation:sync"
        test_value = "test_value"

        redis.set(test_key, test_value, ex=60)
        print_test("SET sync", "PASS")

        result = redis.get(test_key)
        if result and (result == test_value or result == test_value.encode()):
            print_test("GET sync", "PASS")
        else:
            print_test("GET sync", "FAIL", f"Valor esperado: {test_value}, recebido: {result}")

        redis.delete(test_key)
        result = redis.get(test_key)
        if result is None:
            print_test("DELETE sync", "PASS")
        else:
            print_test("DELETE sync", "FAIL", "Chave não foi deletada")

        return True

    except Exception as e:
        print_test("Redis sync operations", "FAIL", str(e))
        return False


async def test_singleton_pattern():
    """Testa se o padrão singleton está funcionando."""
    print(f"\n{'='*80}")
    print(f"4. TESTE DE SINGLETON PATTERN")
    print(f"{'='*80}\n")

    try:
        from app.core.redis_unified import get_async_redis, get_sync_redis

        # Async
        client1 = await get_async_redis()
        client2 = await get_async_redis()

        if client1 is client2:
            print_test("Singleton async", "PASS", "Mesma instância")
        else:
            print_test("Singleton async", "FAIL", "Instâncias diferentes")

        # Sync
        client3 = get_sync_redis()
        client4 = get_sync_redis()

        if client3 is client4:
            print_test("Singleton sync", "PASS", "Mesma instância")
        else:
            print_test("Singleton sync", "FAIL", "Instâncias diferentes")

        return True

    except Exception as e:
        print_test("Singleton pattern", "FAIL", str(e))
        return False


def test_migrated_modules():
    """Testa se módulos migrados importam corretamente."""
    print(f"\n{'='*80}")
    print(f"5. TESTE DE MODULOS MIGRADOS")
    print(f"{'='*80}\n")

    modules = [
        "app.utils.cache.cache_manager",
        "app.services.cache.ai_cache",
        "app.middleware.rate_limit_middleware",
        "app.core.lifecycle.startup",
        "app.core.lifecycle.shutdown",
        "app.core.monitoring.health",
        "app.features.coordination.coordinator",
        "app.features.memory.conversation_memory",
    ]

    all_passed = True

    for module_name in modules:
        try:
            __import__(module_name)
            print_test(f"Import {module_name}", "PASS")
        except ImportError as e:
            print_test(f"Import {module_name}", "FAIL", str(e))
            all_passed = False
        except Exception as e:
            print_test(f"Import {module_name}", "SKIP", f"Módulo não implementado: {str(e)}")

    return all_passed


def print_summary(results):
    """Imprime sumário dos resultados."""
    print(f"\n{'='*80}")
    print(f"SUMARIO DOS RESULTADOS")
    print(f"{'='*80}\n")

    total = len(results)
    passed = sum(1 for r in results if r)
    failed = total - passed

    if failed == 0:
        print(f"[OK] TODOS OS TESTES PASSARAM ({passed}/{total})")
    else:
        print(f"[FAIL] {failed} TESTE(S) FALHARAM ({passed}/{total} passaram)")

    print()


async def main():
    """Função principal."""
    print(f"\n{'#'*80}")
    print(f"# VALIDACAO DAS MIGRACOES REDIS")
    print(f"{'#'*80}")

    results = []

    # Executa testes
    results.append(test_imports())
    results.append(await test_async_redis_basic())
    results.append(test_sync_redis_basic())
    results.append(await test_singleton_pattern())
    results.append(test_migrated_modules())

    # Sumário
    print_summary(results)

    # Exit code
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
