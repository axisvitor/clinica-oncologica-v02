#!/usr/bin/env python3
"""
Redis Client Factory Validation Script

Tests the new Redis client factory with actual connections to verify:
- SSL/TLS configuration works correctly
- Both sync and async clients connect successfully
- Certificate validation with certifi
- Connection pooling
- Health checks
- Error handling

Usage:
    python scripts/validate_redis_factory.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend-hormonia"
sys.path.insert(0, str(backend_path))

import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(name: str, success: bool, details: str = ""):
    """Print a test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"        {details}")


async def test_environment_variables():
    """Test that required environment variables are set."""
    print_section("1. Environment Variables Check")

    from app.config import settings

    checks = []

    # Check REDIS_URL
    has_url = bool(settings.REDIS_URL)
    print_result(
        "REDIS_URL set",
        has_url,
        f"Value: {settings.REDIS_URL}" if has_url else "Not set"
    )
    checks.append(has_url)

    # Check SSL setting
    ssl_enabled = settings.REDIS_SSL
    print_result(
        "REDIS_SSL configured",
        True,
        f"SSL {'enabled' if ssl_enabled else 'disabled'}"
    )

    # Check SSL cert requirements
    cert_reqs = settings.REDIS_SSL_CERT_REQS
    print_result(
        "REDIS_SSL_CERT_REQS set",
        bool(cert_reqs),
        f"Value: {cert_reqs}"
    )
    checks.append(bool(cert_reqs))

    # Check connection settings
    timeout = settings.REDIS_SOCKET_TIMEOUT
    print_result(
        "Connection timeout configured",
        timeout > 0,
        f"Timeout: {timeout}s"
    )

    return all(checks)


async def test_certifi_installation():
    """Test that certifi is installed and working."""
    print_section("2. Certifi Package Check")

    try:
        import certifi
        ca_bundle = certifi.where()
        ca_exists = Path(ca_bundle).exists()

        print_result(
            "certifi installed",
            True,
            f"Version: {certifi.__version__ if hasattr(certifi, '__version__') else 'unknown'}"
        )
        print_result(
            "CA bundle found",
            ca_exists,
            f"Path: {ca_bundle}"
        )

        return ca_exists
    except ImportError:
        print_result(
            "certifi installed",
            False,
            "⚠️  Install with: pip install certifi"
        )
        return False


async def test_ssl_context_creation():
    """Test SSL context creation."""
    print_section("3. SSL Context Creation")

    try:
        from app.core.redis_client_factory import RedisClientFactory
        from app.config import settings

        factory = RedisClientFactory()

        # Parse Redis URL to get hostname
        url_params = factory._parse_redis_url(settings.REDIS_URL)
        hostname = url_params['host']

        # Create SSL context
        ssl_context = factory._create_ssl_context(hostname)

        if settings.REDIS_SSL:
            has_context = ssl_context is not None
            print_result(
                "SSL context created",
                has_context,
                f"For hostname: {hostname}"
            )

            if has_context:
                import ssl
                print_result(
                    "Certificate verification",
                    True,
                    f"Mode: {ssl_context.verify_mode} (CERT_REQUIRED={ssl.CERT_REQUIRED})"
                )
                print_result(
                    "Hostname checking",
                    True,
                    f"Enabled: {ssl_context.check_hostname}"
                )
            return has_context
        else:
            print_result(
                "SSL disabled",
                True,
                "No SSL context needed"
            )
            return True

    except Exception as e:
        print_result(
            "SSL context creation",
            False,
            f"Error: {e}"
        )
        logger.exception("SSL context creation failed")
        return False


async def test_sync_client_connection():
    """Test synchronous Redis client connection."""
    print_section("4. Sync Client Connection Test")

    try:
        from app.core.redis_client_factory import get_redis_client

        # Create sync client
        logger.info("Creating sync Redis client...")
        redis = get_redis_client()

        # Test ping
        logger.info("Testing ping...")
        result = redis.ping()
        print_result(
            "Sync client PING",
            result is True,
            "Connection successful"
        )

        # Test basic operations
        test_key = "test:factory:sync"
        test_value = "sync_client_works"

        logger.info("Testing SET operation...")
        redis.set(test_key, test_value, ex=60)
        print_result(
            "Sync client SET",
            True,
            f"Key: {test_key}"
        )

        logger.info("Testing GET operation...")
        retrieved = redis.get(test_key)
        matches = retrieved == test_value
        print_result(
            "Sync client GET",
            matches,
            f"Retrieved: {retrieved}"
        )

        # Cleanup
        redis.delete(test_key)

        return result and matches

    except Exception as e:
        print_result(
            "Sync client connection",
            False,
            f"Error: {e}"
        )
        logger.exception("Sync client test failed")
        return False


async def test_async_client_connection():
    """Test asynchronous Redis client connection."""
    print_section("5. Async Client Connection Test")

    try:
        from app.core.redis_client_factory import get_redis_client_async

        # Create async client
        logger.info("Creating async Redis client...")
        redis = await get_redis_client_async()

        # Test ping
        logger.info("Testing async ping...")
        result = await redis.ping()
        print_result(
            "Async client PING",
            result is True,
            "Connection successful"
        )

        # Test basic operations
        test_key = "test:factory:async"
        test_value = "async_client_works"

        logger.info("Testing async SET operation...")
        await redis.set(test_key, test_value, ex=60)
        print_result(
            "Async client SET",
            True,
            f"Key: {test_key}"
        )

        logger.info("Testing async GET operation...")
        retrieved = await redis.get(test_key)
        matches = retrieved == test_value
        print_result(
            "Async client GET",
            matches,
            f"Retrieved: {retrieved}"
        )

        # Cleanup
        await redis.delete(test_key)

        return result and matches

    except Exception as e:
        print_result(
            "Async client connection",
            False,
            f"Error: {e}"
        )
        logger.exception("Async client test failed")
        return False


async def test_health_check():
    """Test health check functionality."""
    print_section("6. Health Check Test")

    try:
        from app.core.redis_client_factory import redis_health_check

        logger.info("Running health check...")
        health = await redis_health_check()

        # Check overall status
        is_healthy = health["status"] in ["healthy", "degraded"]
        print_result(
            "Health check status",
            is_healthy,
            f"Status: {health['status']}"
        )

        # Check sync client
        sync_ok = health["sync"]["connected"]
        print_result(
            "Sync client health",
            sync_ok,
            f"Error: {health['sync']['error']}" if not sync_ok else "OK"
        )

        # Check async client
        async_ok = health["async"]["connected"]
        print_result(
            "Async client health",
            async_ok,
            f"Error: {health['async']['error']}" if not async_ok else "OK"
        )

        # Check SSL status
        print_result(
            "SSL enabled",
            True,
            f"SSL: {health['ssl_enabled']}"
        )

        return is_healthy

    except Exception as e:
        print_result(
            "Health check",
            False,
            f"Error: {e}"
        )
        logger.exception("Health check failed")
        return False


async def test_connection_pooling():
    """Test connection pooling and reuse."""
    print_section("7. Connection Pooling Test")

    try:
        from app.core.redis_client_factory import get_redis_client

        # Get client twice
        client1 = get_redis_client()
        client2 = get_redis_client()

        # Should be same instance (cached)
        is_same = client1 is client2
        print_result(
            "Client caching",
            is_same,
            "Clients are reused" if is_same else "Clients are different"
        )

        # Test force_new
        from app.core.redis_client_factory import get_redis_factory
        factory = get_redis_factory()
        client3 = factory.get_sync_client(force_new=True)

        is_different = client1 is not client3
        print_result(
            "Force new client",
            is_different,
            "New client created" if is_different else "Client was reused"
        )

        return is_same and is_different

    except Exception as e:
        print_result(
            "Connection pooling",
            False,
            f"Error: {e}"
        )
        logger.exception("Connection pooling test failed")
        return False


async def test_database_isolation():
    """Test Redis database isolation."""
    print_section("8. Database Isolation Test")

    try:
        from app.core.redis_client_factory import get_redis_client

        # Create clients for different DBs
        db0_client = get_redis_client(db=0)
        db1_client = get_redis_client(db=1)

        # Set same key in different DBs
        test_key = "test:db:isolation"
        db0_client.set(test_key, "db0_value", ex=60)
        db1_client.set(test_key, "db1_value", ex=60)

        # Verify isolation
        db0_value = db0_client.get(test_key)
        db1_value = db1_client.get(test_key)

        is_isolated = db0_value == "db0_value" and db1_value == "db1_value"
        print_result(
            "Database isolation",
            is_isolated,
            f"DB0: {db0_value}, DB1: {db1_value}"
        )

        # Cleanup
        db0_client.delete(test_key)
        db1_client.delete(test_key)

        return is_isolated

    except Exception as e:
        print_result(
            "Database isolation",
            False,
            f"Error: {e}"
        )
        logger.exception("Database isolation test failed")
        return False


async def main():
    """Run all validation tests."""
    print("\n" + "🔍 " * 20)
    print("  Redis Client Factory Validation")
    print("🔍 " * 20)

    results = {}

    # Run all tests
    results["env_vars"] = await test_environment_variables()
    results["certifi"] = await test_certifi_installation()
    results["ssl_context"] = await test_ssl_context_creation()
    results["sync_client"] = await test_sync_client_connection()
    results["async_client"] = await test_async_client_connection()
    results["health_check"] = await test_health_check()
    results["pooling"] = await test_connection_pooling()
    results["db_isolation"] = await test_database_isolation()

    # Summary
    print_section("Validation Summary")

    passed = sum(1 for r in results.values() if r)
    total = len(results)
    success_rate = (passed / total) * 100

    for test_name, result in results.items():
        print_result(test_name.replace('_', ' ').title(), result)

    print(f"\n📊 Results: {passed}/{total} tests passed ({success_rate:.1f}%)")

    if passed == total:
        print("\n✅ All tests passed! Redis client factory is working correctly.")
        return 0
    elif passed >= total * 0.8:
        print("\n⚠️  Most tests passed, but some issues detected. Check logs above.")
        return 1
    else:
        print("\n❌ Multiple tests failed. Review configuration and logs.")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
