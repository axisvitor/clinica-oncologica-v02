"""
Configuração de fixtures pytest para testes Redis.

Este módulo fornece fixtures compartilhadas para todos os testes Redis.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator


@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para toda a sessão de testes."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_redis_client():
    """Fornece cliente Redis async para testes."""
    from app.core.redis_unified import get_async_redis

    try:
        client = await get_async_redis()
        yield client
    except Exception as e:
        pytest.skip(f"Redis não disponível: {e}")


@pytest.fixture(scope="function")
def sync_redis_client():
    """Fornece cliente Redis sync para testes."""
    from app.core.redis_unified import get_sync_redis

    try:
        client = get_sync_redis()
        yield client
    except Exception as e:
        pytest.skip(f"Redis não disponível: {e}")


@pytest.fixture(scope="function")
async def redis_cleanup():
    """Fixture para cleanup de chaves Redis após testes."""
    keys_to_cleanup = []

    def register_key(key: str):
        """Registra chave para cleanup."""
        keys_to_cleanup.append(key)

    yield register_key

    # Cleanup após o teste
    if keys_to_cleanup:
        try:
            from app.core.redis_unified import get_async_redis
            redis = await get_async_redis()
            if redis:
                await redis.delete(*keys_to_cleanup)
        except Exception:
            pass  # Ignora erros no cleanup


@pytest.fixture(scope="function")
async def cache_manager():
    """Fornece instância do CacheManager para testes."""
    try:
        from app.utils.cache.cache_manager import CacheManager
        manager = CacheManager()
        yield manager
    except Exception as e:
        pytest.skip(f"CacheManager não disponível: {e}")


@pytest.fixture(scope="function")
async def ai_cache():
    """Fornece instância do AICache para testes."""
    try:
        from app.services.cache.ai_cache import AICache
        cache = AICache()
        yield cache
    except Exception as e:
        pytest.skip(f"AICache não disponível: {e}")


@pytest.fixture(scope="function")
async def conversation_memory():
    """Fornece instância do ConversationMemory para testes."""
    try:
        from app.features.memory.conversation_memory import ConversationMemory
        memory = ConversationMemory()
        yield memory
    except Exception as e:
        pytest.skip(f"ConversationMemory não disponível: {e}")


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Configura ambiente de testes."""
    import os

    # Define variáveis de ambiente para testes se necessário
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("REDIS_DECODE_RESPONSES", "true")

    yield

    # Cleanup após todos os testes
    pass


@pytest.fixture(scope="function")
def redis_test_data():
    """Fornece dados de teste padronizados."""
    return {
        "test_key": "test:pytest:key",
        "test_value": "test_value",
        "test_hash": "test:pytest:hash",
        "test_list": "test:pytest:list",
        "test_set": "test:pytest:set",
        "test_user_id": "test_user_123",
        "test_data": {
            "id": 1,
            "name": "Test",
            "email": "test@example.com"
        }
    }
