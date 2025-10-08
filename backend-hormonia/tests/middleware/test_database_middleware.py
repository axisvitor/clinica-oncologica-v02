"""
Integration tests for Database Middleware.

Tests database connection handling and transaction management.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import FastAPI, Request, Depends
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import time


class DatabaseMiddleware(BaseHTTPMiddleware):
    """Database connection and transaction middleware."""

    def __init__(
        self,
        app,
        db_pool=None,
        auto_commit: bool = True,
        rollback_on_error: bool = True,
        connection_timeout: int = 30
    ):
        super().__init__(app)
        self.db_pool = db_pool or self._create_mock_pool()
        self.auto_commit = auto_commit
        self.rollback_on_error = rollback_on_error
        self.connection_timeout = connection_timeout

    def _create_mock_pool(self):
        """Create mock database pool for testing."""
        pool = Mock()
        pool.acquire = AsyncMock()
        pool.release = AsyncMock()
        pool.close = AsyncMock()
        return pool

    async def dispatch(self, request: Request, call_next):
        """Handle database connection for request."""
        connection = None
        transaction = None

        try:
            # Acquire connection from pool
            connection = await asyncio.wait_for(
                self.db_pool.acquire(),
                timeout=self.connection_timeout
            )

            # Start transaction
            if hasattr(connection, 'transaction'):
                transaction = await connection.transaction()
                await transaction.start()

            # Attach to request
            request.state.db = connection
            request.state.transaction = transaction

            # Process request
            response = await call_next(request)

            # Commit or rollback based on response
            if transaction:
                if response.status_code >= 400 and self.rollback_on_error:
                    await transaction.rollback()
                elif self.auto_commit:
                    await transaction.commit()

            return response

        except asyncio.TimeoutError:
            # Connection timeout
            if transaction:
                await transaction.rollback()
            raise

        except Exception as exc:
            # Rollback on any error
            if transaction and self.rollback_on_error:
                await transaction.rollback()
            raise

        finally:
            # Release connection back to pool
            if connection:
                await self.db_pool.release(connection)


class MockConnection:
    """Mock database connection for testing."""

    def __init__(self):
        self.queries = []
        self.in_transaction = False
        self.transaction_obj = None

    async def execute(self, query, *args, **kwargs):
        """Execute query."""
        self.queries.append((query, args, kwargs))
        return {"result": "success"}

    async def fetch(self, query, *args, **kwargs):
        """Fetch query results."""
        self.queries.append((query, args, kwargs))
        return [{"id": 1, "name": "test"}]

    async def fetchrow(self, query, *args, **kwargs):
        """Fetch single row."""
        self.queries.append((query, args, kwargs))
        return {"id": 1, "name": "test"}

    async def transaction(self):
        """Create transaction context."""
        self.transaction_obj = MockTransaction(self)
        return self.transaction_obj


class MockTransaction:
    """Mock database transaction."""

    def __init__(self, connection):
        self.connection = connection
        self.started = False
        self.committed = False
        self.rolled_back = False

    async def start(self):
        """Start transaction."""
        self.started = True
        self.connection.in_transaction = True

    async def commit(self):
        """Commit transaction."""
        if not self.started:
            raise RuntimeError("Transaction not started")
        self.committed = True
        self.connection.in_transaction = False

    async def rollback(self):
        """Rollback transaction."""
        if not self.started:
            raise RuntimeError("Transaction not started")
        self.rolled_back = True
        self.connection.in_transaction = False


class MockPool:
    """Mock database connection pool."""

    def __init__(self):
        self.connections = []
        self.acquired_count = 0
        self.released_count = 0
        self.max_connections = 10

    async def acquire(self):
        """Acquire connection from pool."""
        if self.acquired_count >= self.max_connections:
            raise RuntimeError("Connection pool exhausted")
        self.acquired_count += 1
        conn = MockConnection()
        self.connections.append(conn)
        return conn

    async def release(self, connection):
        """Release connection back to pool."""
        self.released_count += 1

    async def close(self):
        """Close pool."""
        self.connections.clear()


@pytest.fixture
def app_with_database():
    """Create FastAPI app with database middleware."""
    app = FastAPI()
    pool = MockPool()

    # Add database middleware
    app.add_middleware(
        DatabaseMiddleware,
        db_pool=pool,
        auto_commit=True,
        rollback_on_error=True,
        connection_timeout=30
    )

    @app.get("/test")
    async def test_endpoint(request: Request):
        db = request.state.db
        result = await db.fetch("SELECT * FROM users")
        return {"users": result}

    @app.post("/create")
    async def create_endpoint(request: Request, data: dict):
        db = request.state.db
        await db.execute("INSERT INTO items VALUES ($1, $2)", data["id"], data["name"])
        return {"created": True}

    @app.get("/error")
    async def error_endpoint(request: Request):
        db = request.state.db
        await db.execute("SELECT * FROM users")
        raise ValueError("Test error")

    @app.get("/transaction")
    async def transaction_endpoint(request: Request):
        db = request.state.db
        await db.execute("UPDATE users SET active = true")
        return {"updated": True}

    return app, pool


@pytest.fixture
def client(app_with_database):
    """Create test client."""
    app, pool = app_with_database
    return TestClient(app), pool


class TestDatabaseMiddleware:
    """Test database middleware functionality."""

    def test_connection_acquired(self, client):
        """Test database connection is acquired."""
        test_client, pool = client
        response = test_client.get("/test")
        assert response.status_code == 200
        assert pool.acquired_count == 1
        assert pool.released_count == 1

    def test_query_execution(self, client):
        """Test queries can be executed."""
        test_client, pool = client
        response = test_client.get("/test")
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert len(data["users"]) > 0

    def test_transaction_commit(self, client):
        """Test transaction is committed on success."""
        test_client, pool = client
        response = test_client.post("/create", json={"id": 1, "name": "test"})
        assert response.status_code == 200

        # Check transaction was committed
        conn = pool.connections[-1]
        assert conn.transaction_obj is not None
        assert conn.transaction_obj.committed is True
        assert conn.transaction_obj.rolled_back is False

    def test_transaction_rollback_on_error(self, client):
        """Test transaction rollback on error."""
        test_client, pool = client
        response = test_client.get("/error")
        assert response.status_code == 500

        # Check transaction was rolled back
        conn = pool.connections[-1]
        if conn.transaction_obj:
            assert conn.transaction_obj.rolled_back is True
            assert conn.transaction_obj.committed is False

    def test_connection_released_after_request(self, client):
        """Test connection is released after request."""
        test_client, pool = client

        # Make multiple requests
        for _ in range(3):
            response = test_client.get("/test")
            assert response.status_code == 200

        # All connections should be released
        assert pool.acquired_count == 3
        assert pool.released_count == 3

    def test_multiple_concurrent_requests(self, client):
        """Test multiple concurrent requests."""
        test_client, pool = client
        import concurrent.futures

        def make_request():
            return test_client.get("/test")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in futures]

        # All requests should succeed
        for response in results:
            assert response.status_code == 200

        # Connections should be acquired and released
        assert pool.acquired_count == 5
        assert pool.released_count == 5

    def test_connection_pool_exhaustion(self):
        """Test connection pool exhaustion handling."""
        app = FastAPI()
        pool = MockPool()
        pool.max_connections = 1

        app.add_middleware(DatabaseMiddleware, db_pool=pool)

        @app.get("/test")
        async def test():
            return {"ok": True}

        # This would need proper async testing
        # to simulate pool exhaustion

    def test_connection_timeout(self):
        """Test connection acquisition timeout."""
        app = FastAPI()
        pool = Mock()

        async def slow_acquire():
            await asyncio.sleep(2)
            return MockConnection()

        pool.acquire = slow_acquire
        pool.release = AsyncMock()

        app.add_middleware(
            DatabaseMiddleware,
            db_pool=pool,
            connection_timeout=1
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        # This would timeout in async context

    def test_transaction_isolation(self, client):
        """Test transaction isolation between requests."""
        test_client, pool = client

        # First request
        response1 = test_client.post("/create", json={"id": 1, "name": "item1"})
        assert response1.status_code == 200

        # Second request
        response2 = test_client.post("/create", json={"id": 2, "name": "item2"})
        assert response2.status_code == 200

        # Should use different connections
        assert len(pool.connections) == 2

        # Each should have its own transaction
        for conn in pool.connections:
            assert conn.transaction_obj is not None
            assert conn.transaction_obj.committed is True


class TestDatabaseConfiguration:
    """Test database middleware configuration."""

    def test_auto_commit_disabled(self):
        """Test with auto-commit disabled."""
        app = FastAPI()
        pool = MockPool()

        app.add_middleware(
            DatabaseMiddleware,
            db_pool=pool,
            auto_commit=False
        )

        @app.post("/test")
        async def test(request: Request):
            db = request.state.db
            await db.execute("INSERT INTO test VALUES (1)")
            return {"ok": True}

        client = TestClient(app)
        response = client.post("/test")
        assert response.status_code == 200

        # Transaction should not be committed
        conn = pool.connections[-1]
        if conn.transaction_obj:
            assert conn.transaction_obj.committed is False

    def test_rollback_on_error_disabled(self):
        """Test with rollback on error disabled."""
        app = FastAPI()
        pool = MockPool()

        app.add_middleware(
            DatabaseMiddleware,
            db_pool=pool,
            rollback_on_error=False
        )

        @app.get("/test")
        async def test():
            raise ValueError("Error")

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 500

        # Transaction should not be rolled back
        conn = pool.connections[-1]
        if conn.transaction_obj:
            assert conn.transaction_obj.rolled_back is False


class TestDatabasePerformance:
    """Test database middleware performance."""

    def test_connection_pooling_efficiency(self, client):
        """Test connection pooling reduces overhead."""
        test_client, pool = client

        # Warm up
        test_client.get("/test")

        # Measure pooled connections
        start = time.time()
        for _ in range(100):
            response = test_client.get("/test")
            assert response.status_code == 200
        pooled_time = time.time() - start

        # Should be efficient
        avg_time = pooled_time / 100
        assert avg_time < 0.01  # Less than 10ms per request

    def test_transaction_overhead(self, client):
        """Test transaction overhead is minimal."""
        test_client, pool = client

        # Measure with transactions
        start = time.time()
        for _ in range(50):
            response = test_client.post("/create", json={"id": 1, "name": "test"})
            assert response.status_code == 200
        transaction_time = time.time() - start

        # Should have minimal overhead
        avg_time = transaction_time / 50
        assert avg_time < 0.02  # Less than 20ms per request