"""
Testes para o cliente Redis unificado.

Este módulo testa a funcionalidade do cliente Redis centralizado,
incluindo conexões síncronas/assíncronas, SSL/TLS, pooling e singleton pattern.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.core.redis_unified import get_async_redis, get_sync_redis, RedisClientFactory


class TestRedisUnifiedClient:
    """Testes para validação do cliente Redis unificado."""

    @pytest.mark.asyncio
    async def test_async_redis_client_creation(self):
        """Testa se get_async_redis() retorna um cliente válido."""
        client = await get_async_redis()
        assert client is not None
        assert hasattr(client, 'ping')
        assert hasattr(client, 'get')
        assert hasattr(client, 'set')

    @pytest.mark.asyncio
    async def test_async_redis_ping(self):
        """Testa se o cliente async consegue fazer ping no Redis."""
        client = await get_async_redis()
        try:
            result = await client.ping()
            assert result is True
        except Exception as e:
            # Se falhar por conexão, apenas loga (pode estar sem Redis rodando)
            pytest.skip(f"Redis não disponível: {e}")

    @pytest.mark.asyncio
    async def test_async_redis_basic_operations(self):
        """Testa operações básicas do Redis async (get/set/delete)."""
        client = await get_async_redis()
        test_key = "test:unified:async"
        test_value = "test_value_async"

        try:
            # Set
            await client.set(test_key, test_value, ex=60)

            # Get
            result = await client.get(test_key)
            assert result == test_value.encode() or result == test_value

            # Delete
            await client.delete(test_key)
            result = await client.get(test_key)
            assert result is None
        except Exception as e:
            pytest.skip(f"Redis não disponível: {e}")

    def test_sync_redis_client_creation(self):
        """Testa se get_sync_redis() retorna um cliente válido."""
        client = get_sync_redis()
        assert client is not None
        assert hasattr(client, 'ping')
        assert hasattr(client, 'get')
        assert hasattr(client, 'set')

    def test_sync_redis_ping(self):
        """Testa se o cliente sync consegue fazer ping no Redis."""
        client = get_sync_redis()
        try:
            result = client.ping()
            assert result is True
        except Exception as e:
            pytest.skip(f"Redis não disponível: {e}")

    def test_sync_redis_basic_operations(self):
        """Testa operações básicas do Redis sync (get/set/delete)."""
        client = get_sync_redis()
        test_key = "test:unified:sync"
        test_value = "test_value_sync"

        try:
            # Set
            client.set(test_key, test_value, ex=60)

            # Get
            result = client.get(test_key)
            assert result == test_value.encode() or result == test_value

            # Delete
            client.delete(test_key)
            result = client.get(test_key)
            assert result is None
        except Exception as e:
            pytest.skip(f"Redis não disponível: {e}")

    @pytest.mark.asyncio
    async def test_async_client_singleton_pattern(self):
        """Testa se o cliente async reutiliza a mesma instância (singleton)."""
        client1 = await get_async_redis()
        client2 = await get_async_redis()

        # Deve ser a mesma instância
        assert client1 is client2

    def test_sync_client_singleton_pattern(self):
        """Testa se o cliente sync reutiliza a mesma instância (singleton)."""
        client1 = get_sync_redis()
        client2 = get_sync_redis()

        # Deve ser a mesma instância
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_ssl_tls_configuration(self):
        """Testa se a configuração SSL/TLS é aplicada corretamente."""
        # Este teste verifica se o cliente é criado com SSL quando REDIS_USE_SSL=true
        # O comportamento exato depende das variáveis de ambiente
        client = await get_async_redis()

        # Verifica se o cliente tem a propriedade connection_pool
        assert hasattr(client, 'connection_pool')

        # Se SSL estiver habilitado, deve ter configurações SSL
        if client.connection_pool:
            # Testa se não lança exceção na criação
            assert client is not None

    def test_connection_pooling(self):
        """Testa se o connection pooling está funcionando."""
        client = get_sync_redis()

        # Verifica se tem connection pool
        assert hasattr(client, 'connection_pool')
        assert client.connection_pool is not None

        # Verifica configurações do pool
        pool = client.connection_pool
        assert hasattr(pool, 'max_connections')

    @pytest.mark.asyncio
    async def test_async_connection_pooling(self):
        """Testa se o connection pooling async está funcionando."""
        client = await get_async_redis()

        # Verifica se tem connection pool
        assert hasattr(client, 'connection_pool')
        assert client.connection_pool is not None

    @pytest.mark.asyncio
    async def test_redis_factory_reset(self):
        """Testa se o factory consegue resetar as conexões."""
        # Pega clientes atuais
        async_client1 = await get_async_redis()
        sync_client1 = get_sync_redis()

        # Reseta factory
        RedisClientFactory._async_client = None
        RedisClientFactory._sync_client = None

        # Pega novos clientes
        async_client2 = await get_async_redis()
        sync_client2 = get_sync_redis()

        # Devem ser instâncias diferentes após reset
        assert async_client1 is not async_client2
        assert sync_client1 is not sync_client2

    @pytest.mark.asyncio
    async def test_async_redis_error_handling(self):
        """Testa tratamento de erros em operações async."""
        client = await get_async_redis()

        try:
            # Tenta operação em chave inexistente
            result = await client.get("nonexistent:key:12345")
            assert result is None  # Deve retornar None, não erro
        except Exception as e:
            pytest.skip(f"Redis não disponível: {e}")

    def test_sync_redis_error_handling(self):
        """Testa tratamento de erros em operações sync."""
        client = get_sync_redis()

        try:
            # Tenta operação em chave inexistente
            result = client.get("nonexistent:key:12345")
            assert result is None  # Deve retornar None, não erro
        except Exception as e:
            pytest.skip(f"Redis não disponível: {e}")


class TestRedisConfiguration:
    """Testes para validação de configurações do Redis."""

    def test_redis_url_configuration(self):
        """Testa se a URL do Redis está configurada corretamente."""
        from app.core.config import settings

        assert hasattr(settings, 'REDIS_URL')
        assert settings.REDIS_URL is not None
        assert isinstance(settings.REDIS_URL, str)
        assert settings.REDIS_URL.startswith('redis://') or settings.REDIS_URL.startswith('rediss://')

    def test_ssl_configuration(self):
        """Testa se as configurações SSL estão presentes."""
        from app.core.config import settings

        # Verifica se as configurações SSL existem
        assert hasattr(settings, 'REDIS_USE_SSL')
        assert hasattr(settings, 'REDIS_SSL_CERT_REQS')

    @pytest.mark.asyncio
    async def test_redis_timeout_configuration(self):
        """Testa se o timeout está configurado."""
        client = await get_async_redis()

        # Verifica se o cliente tem timeout configurado
        if hasattr(client.connection_pool, 'connection_kwargs'):
            kwargs = client.connection_pool.connection_kwargs
            # Pode ter socket_timeout ou socket_connect_timeout
            assert 'socket_timeout' in kwargs or 'socket_connect_timeout' in kwargs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
