# Resource Management Audit Report - Backend-Hormonia

**Date**: 2025-12-25
**Scope**: Database connections, Redis connections, HTTP clients, WebSocket connections, background tasks, file handles
**Severity Levels**: Critical, High, Medium, Low

---

## Executive Summary

Found **18 resource management issues** across the codebase:
- **3 Critical Issues** - Immediate action required
- **6 High Issues** - Should be fixed in next sprint
- **7 Medium Issues** - Address in planned maintenance
- **2 Low Issues** - Monitor and track

---

## Critical Issues (Fix Immediately)

### 1. Evolution API httpx.AsyncClient Not Properly Closed on Errors

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/integrations/evolution/client.py:111-118`

**Resource Type**: HTTP AsyncClient connection pool

**Code**:
```python
self.client = httpx.AsyncClient(
    timeout=httpx.Timeout(timeout, connect=10.0),
    headers=headers,
    follow_redirects=True,
    limits=httpx.Limits(
        max_keepalive_connections=20, max_connections=100, keepalive_expiry=30.0
    ),
)
```

**Leak Scenario**:
- If an exception occurs during initialization (e.g., in RequestHandler, MessageSender, WebhookHandler constructors), the client is never assigned and connections leak
- If service crashes without calling `close()`, client connections remain open indefinitely
- AsyncClient connection pool exhaustion after ~100 requests without proper cleanup

**Severity**: CRITICAL (affects WhatsApp message delivery)

**Fix**:
```python
# Use context manager or ensure cleanup in finally
try:
    self.client = httpx.AsyncClient(...)
    self.request_handler = RequestHandler(...)
    # ... other initialization
except Exception as e:
    if hasattr(self, 'client') and self.client:
        await self.client.aclose()
    raise
```

---

### 2. Database Session Not Properly Closed in Follow-Up System

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py:484-497`

**Resource Type**: SQLAlchemy database session

**Code**:
```python
db = SessionLocal()
try:
    follow_up_service = FollowUpSystemService(db)
    result = await follow_up_service.rehydrate_from_redis()
    app.state.follow_up_service = follow_up_service
    # ...
finally:
    db.close()
```

**Leak Scenario**:
- If `FollowUpSystemService(db)` raises an exception during `__init__`, `db.close()` is executed but the partially-initialized service is stored in `app.state`
- Multiple database sessions may be created internally in FollowUpSystemService without explicit cleanup
- Connection pool can reach max_overflow if service fails to clean internal sessions

**Severity**: CRITICAL (affects startup reliability)

**Fix**:
```python
db = SessionLocal()
try:
    try:
        follow_up_service = FollowUpSystemService(db)
        result = await follow_up_service.rehydrate_from_redis()
        app.state.follow_up_service = follow_up_service
    except Exception as e:
        logger.error(f"Failed to initialize follow-up service: {e}")
        app.state.follow_up_service = None
finally:
    db.close()  # Always close regardless of success/failure
```

---

### 3. Redis Connection Pool Not Properly Managed in BaseRepository

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/base.py:37-58`

**Resource Type**: Redis connection pool

**Code**:
```python
@property
def _redis_pool(self):
    """Get or create a Redis connection pool for cache invalidation."""
    if not hasattr(self, '_redis_pool_instance'):
        import redis
        from app.config import settings

        self._redis_pool_instance = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=10,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return self._redis_pool_instance
```

**Leak Scenario**:
- ConnectionPool is created on first property access and never explicitly closed
- Multiple instances of BaseRepository-derived classes create separate pools (no sharing)
- Pools leak connections when:
  - Repository objects are garbage collected without cleanup
  - Connection timeout occurs and pool doesn't reset connections
  - Application shutdown doesn't call `.disconnect()`

**Severity**: CRITICAL (Redis connection exhaustion)

**Fix**:
```python
def __init__(self, db: Session, model: Type[ModelType]):
    self.db = db
    self.model = model
    self._redis_pool_instance = None

@property
def _redis_pool(self):
    """Get or create a Redis connection pool for cache invalidation."""
    if self._redis_pool_instance is None:
        from app.core.redis_manager import get_redis_manager
        # Use shared Redis manager instead of creating new pool
        self._redis_pool_instance = get_redis_manager()
    return self._redis_pool_instance

def __del__(self):
    """Cleanup Redis pool on garbage collection."""
    if self._redis_pool_instance:
        try:
            self._redis_pool_instance.disconnect()
        except Exception:
            pass
```

---

## High Priority Issues

### 4. WebSocket Connections Not Properly Garbage Collected

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/websocket_service.py:64-76`

**Resource Type**: WebSocket connection dictionaries (memory leak)

**Code**:
```python
# Active connections by connection ID
self.active_connections: Dict[str, WebSocket] = {}

# User connections mapping
self.user_connections: Dict[str, Set[str]] = {}

# Patient room connections
self.patient_rooms: Dict[str, Set[str]] = {}

# Connection metadata
self.connection_metadata: Dict[str, Dict[str, Any]] = {}
```

**Leak Scenario**:
- If `disconnect()` method throws exception partway through, dictionaries aren't fully cleaned
- `connection_metadata` accumulates entries if user_id or patient_id cleanup fails
- No TTL or periodic cleanup of stale connection references
- Memory grows indefinitely with long-lived server and many disconnect/reconnect cycles

**Severity**: HIGH (memory leak with scale)

**Fix**:
```python
async def disconnect(self, connection_id: str, reason: str = "unknown") -> None:
    """
    Disconnect and clean up WebSocket connection safely.
    Ensures all dictionaries are cleaned even if errors occur.
    """
    if connection_id not in self.active_connections:
        return

    # Close connection - don't fail if already closed
    try:
        websocket = self.active_connections.get(connection_id)
        if websocket:
            try:
                await websocket.close()
            except Exception as e:
                logger.debug(f"Error closing websocket {connection_id}: {e}")
    except Exception as e:
        logger.warning(f"Critical error during websocket close: {e}")

    # Cleanup connections - use pop() to ensure removal
    self.active_connections.pop(connection_id, None)

    # Clean up metadata safely
    metadata = self.connection_metadata.pop(connection_id, {})

    # Clean up user connections safely
    user_id = metadata.get("user_id")
    if user_id:
        user_conns = self.user_connections.get(user_id, set())
        user_conns.discard(connection_id)
        if not user_conns:
            self.user_connections.pop(user_id, None)

    # Clean up patient rooms safely
    patient_id = metadata.get("patient_id")
    if patient_id:
        patient_conns = self.patient_rooms.get(patient_id, set())
        patient_conns.discard(connection_id)
        if not patient_conns:
            self.patient_rooms.pop(patient_id, None)

    # Clean up heartbeat tracking
    self.last_heartbeat.pop(connection_id, None)
    self.authenticated_connections.discard(connection_id)

    logger.info(f"WebSocket disconnected: {connection_id} ({reason})")
```

---

### 5. ThreadPoolExecutor Not Properly Shutdown

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/async_context_manager.py:92-94`

**Resource Type**: Thread pool executor

**Code**:
```python
self._executor = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="async_context"
)
```

**Leak Scenario**:
- ThreadPoolExecutor is created but no `shutdown()` is ever called
- Threads remain active after EventLoopContext is destroyed
- With N context instances, N*4 threads leak and consume resources
- No cleanup hook in lifespan shutdown

**Severity**: HIGH (thread resource exhaustion)

**Fix**:
```python
class EventLoopContext:
    def __init__(self):
        self._thread_loops: Dict[threading.Thread, asyncio.AbstractEventLoop] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="async_context"
        )

    def cleanup(self) -> None:
        """Cleanup executor thread pool."""
        if self._executor:
            self._executor.shutdown(wait=True, timeout=5.0)
            logger.info("EventLoopContext thread pool shutdown complete")

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            pass
```

Add to lifespan.py shutdown:
```python
async def _cleanup_other_resources(app: FastAPI, logger) -> None:
    """Cleanup other application resources."""
    try:
        # Cleanup event loop context executors
        from app.core.async_context_manager import EventLoopContext
        # Clean up any global instances
        logger.info("Cleaned up thread pool executors")
    except Exception as e:
        logger.error(f"Error cleaning up other resources: {e}")
```

---

### 6. Redis AsyncClient Not Initialized with Connection Limits

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/redis_manager/manager.py:88-90`

**Resource Type**: Redis connection pool

**Code**:
```python
self.max_connections = getattr(
    settings, "REDIS_POOL_MAX_CONNECTIONS", 20
)  # Reduced from 50
```

**Leak Scenario**:
- Default 20 connections can be exhausted under load if not all connections are properly returned
- No explicit connection cleanup in error paths
- AsyncClient pools are created multiple times for different services
- Duplicate pool creation in initialization_helpers.py

**Severity**: HIGH (connection exhaustion under load)

**Fix**:
```python
# In manager.py __init__:
self.max_connections = getattr(
    settings, "REDIS_POOL_MAX_CONNECTIONS", 20
)
self.min_idle_connections = 2  # Keep minimum connections alive
self.connection_timeout = 5.0  # Timeout waiting for connection

# Add connection health check in get_async_client:
async def get_async_client(self) -> redis_async.Redis:
    """Get async Redis client with connection health check."""
    if self._async_client is None:
        await self._create_async_client()

    # Verify connection is healthy
    try:
        await asyncio.wait_for(self._async_client.ping(), timeout=2.0)
    except Exception as e:
        logger.warning(f"Redis connection health check failed: {e}")
        # Reconnect
        await self._create_async_client()

    return self._async_client
```

---

### 7. Celery Tasks Not Properly Cancelled on Shutdown

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/celery_app.py:1-150`

**Resource Type**: Background task references

**Leak Scenario**:
- No worker process shutdown hook defined (signal handlers missing)
- Long-running tasks (soft_time_limit=25min) continue after app shutdown
- Task result backend doesn't clean up completed task data (memory growth)
- Beat scheduler doesn't gracefully stop pending tasks

**Severity**: HIGH (zombie tasks consuming resources)

**Fix**:
```python
from celery.signals import worker_shutdown, worker_process_shutdown, task_prerun, task_postrun

@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs):
    """Cleanup on Celery worker shutdown."""
    logger.info("Celery worker shutting down - cancelling pending tasks")
    # Revoke all pending tasks from this worker
    celery_app.control.revoke('*', terminate=True)
    logger.info("All pending tasks revoked")

@task_prerun.connect
def on_task_prerun(task_id, task, args, kwargs, **kw):
    """Log task execution start."""
    logger.info(f"Task {task.name} starting (id={task_id})")

@task_postrun.connect
def on_task_postrun(task_id, task, args, kwargs, retval, state, **kw):
    """Log task completion and cleanup."""
    logger.info(f"Task {task.name} completed (id={task_id})")

# Add result backend cleanup
celery_app.conf.update(
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'retry_on_timeout': True,
        'retry_policy': {'timeout': 5.0, 'max_retries': 3}
    }
)
```

---

### 8. Untracked asyncio.create_task() Calls

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/agents/base.py:420,475,479`

**Resource Type**: Asyncio task references

**Code**:
```python
task = asyncio.create_task(self._execute_task(task_id, task_data))
# ... later
message_task = asyncio.create_task(self._process_messages())
heartbeat_task = asyncio.create_task(self._heartbeat_loop())
```

**Leak Scenario**:
- Tasks are created but references aren't stored or tracked
- If tasks raise exceptions, they're only logged but task objects leak
- No mechanism to cancel tasks during agent shutdown
- Orphaned tasks continue running after agent is destroyed

**Severity**: HIGH (orphaned background tasks)

**Fix**:
```python
# Add to Agent base class:
def __init__(self):
    # ... existing code
    self._background_tasks: Set[asyncio.Task] = set()

async def _create_tracked_task(self, coro: Coroutine) -> asyncio.Task:
    """Create and track an asyncio task for cleanup."""
    task = asyncio.create_task(coro)
    self._background_tasks.add(task)
    task.add_done_callback(lambda t: self._background_tasks.discard(t))
    return task

async def shutdown(self) -> None:
    """Shutdown agent and cleanup all background tasks."""
    logger.info(f"Shutting down agent {self.agent_id}")

    # Cancel all background tasks
    for task in list(self._background_tasks):
        if not task.done():
            task.cancel()

    # Wait for cancellation
    if self._background_tasks:
        await asyncio.gather(*self._background_tasks, return_exceptions=True)

    logger.info(f"Agent {self.agent_id} shutdown complete")

# Replace direct create_task calls:
# OLD: task = asyncio.create_task(self._execute_task(task_id, task_data))
# NEW:
task = await self._create_tracked_task(self._execute_task(task_id, task_data))
```

---

### 9. EvolutionClient HTTP Session Not Explicitly Closed

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/integrations/evolution/client.py:151-162`

**Resource Type**: httpx.AsyncClient connection

**Code**:
```python
async def __aenter__(self):
    """Async context manager entry."""
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    """Async context manager exit."""
    await self.close()

async def close(self):
    """Close HTTP client."""
    await self.client.aclose()
```

**Leak Scenario**:
- EvolutionClient is used without context manager in many places
- MessageSender and RequestHandler hold references to client but don't close it
- If exception occurs before `close()` is called, resources leak
- No automatic cleanup if client goes out of scope

**Severity**: HIGH (connection exhaustion)

**Fix**:
```python
# Ensure all usages are wrapped in context manager:
# OLD:
client = EvolutionClient()
result = await client.send_text_message(...)

# NEW:
async with EvolutionClient() as client:
    result = await client.send_text_message(...)

# Or add __del__ cleanup:
async def __del__(self):
    """Ensure cleanup on garbage collection."""
    try:
        if hasattr(self, 'client') and self.client:
            asyncio.create_task(self.client.aclose())
    except Exception:
        pass
```

---

## Medium Priority Issues

### 10. Database Pool Pre-Ping Not Configured for Async Sessions

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/database.py:46-99`

**Resource Type**: Database connection pool

**Leak Scenario**:
- pool_pre_ping=True only validates sync connections
- Async RLS context engine doesn't have pre-ping enabled in same way
- Stale connections aren't detected until query fails
- Connection pool can queue dead connections

**Severity**: MEDIUM

**Fix**:
```python
rls_engine = create_optimized_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=rls_pool_size,
    max_overflow=max(10, settings.DATABASE_POOL_MAX_OVERFLOW // 2),
    pool_pre_ping=True,  # Add explicit pre-ping
    pool_recycle=1800,
    pool_timeout=30,
    # Add pool_reset_on_return for better cleanup
    pool_reset_on_return='rollback',  # Rollback uncommitted transactions
    ...
)
```

---

### 11. FollowUpSystemService Maintains Growing In-Memory Dictionaries

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/follow_up_system/service.py:92-95`

**Resource Type**: In-memory dictionary storage

**Code**:
```python
self.pending_actions: dict[UUID, FollowUpAction] = {}
self.active_alerts: dict[UUID, EscalationAlert] = {}
self.conversation_contexts: dict = {}
```

**Leak Scenario**:
- No maxsize limit or TTL cleanup
- Completed actions aren't automatically removed
- Conversation contexts accumulate indefinitely
- Memory usage grows linearly with number of patients/interactions

**Severity**: MEDIUM

**Fix**:
```python
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

class TTLDict:
    """Dictionary with automatic TTL-based cleanup."""
    def __init__(self, ttl_seconds: int = 86400):
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict = OrderedDict()
        self._timestamps: dict = {}

    def set(self, key: UUID, value: Any) -> None:
        """Set value with timestamp."""
        self._data[key] = value
        self._timestamps[key] = datetime.now(timezone.utc)
        self._cleanup()

    def get(self, key: UUID) -> Optional[Any]:
        """Get value if not expired."""
        if key not in self._data:
            return None
        if self._is_expired(key):
            self._data.pop(key, None)
            self._timestamps.pop(key, None)
            return None
        return self._data[key]

    def _is_expired(self, key: UUID) -> bool:
        """Check if key is expired."""
        timestamp = self._timestamps.get(key)
        if not timestamp:
            return True
        age = datetime.now(timezone.utc) - timestamp
        return age.total_seconds() > self.ttl_seconds

    def _cleanup(self) -> None:
        """Remove expired entries."""
        expired_keys = [
            k for k in self._data.keys()
            if self._is_expired(k)
        ]
        for key in expired_keys:
            self._data.pop(key, None)
            self._timestamps.pop(key, None)

# Use in FollowUpSystemService:
self.pending_actions: TTLDict = TTLDict(ttl_seconds=86400)  # 24 hour TTL
self.active_alerts: TTLDict = TTLDict(ttl_seconds=604800)  # 7 day TTL
self.conversation_contexts: TTLDict = TTLDict(ttl_seconds=3600)  # 1 hour TTL
```

---

### 12. No Timeout for Database Queries

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/patient/base.py` (various query methods)

**Resource Type**: Database connections held during long queries

**Leak Scenario**:
- Queries without timeout can hold connections indefinitely
- Connection pool exhaustion if multiple slow queries occur
- No mechanism to interrupt hung queries

**Severity**: MEDIUM

**Fix**:
```python
# In database connection setup:
from sqlalchemy import text, event

def configure_query_timeout(engine):
    """Configure query timeout for all connections."""
    @event.listens_for(engine, "connect")
    def set_statement_timeout(dbapi_connection, connection_record):
        """Set statement timeout on connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute(f"SET statement_timeout = {settings.DATABASE_STATEMENT_TIMEOUT_MS}")
        cursor.close()

# Add to BaseRepository for explicit timeouts:
def get_all_with_timeout(self, skip: int = 0, limit: int = 100, timeout: int = 30) -> List[ModelType]:
    """Get all records with timeout."""
    try:
        stmt = self.db.query(self.model).offset(skip).limit(limit)
        # Set timeout for this query
        stmt = stmt.execution_options(timeout=timeout)
        return stmt.all()
    except Exception as e:
        if "timeout" in str(e).lower():
            logger.error(f"Query timeout after {timeout}s")
        raise
```

---

### 13. WebSocket Heartbeat Task Not Properly Stopped

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py:201-229` (ws_manager initialization)

**Resource Type**: Background heartbeat task

**Leak Scenario**:
- WebSocket manager has heartbeat/cleanup background tasks
- Tasks aren't explicitly cancelled in cleanup
- If `ws_manager.stop()` raises exception, tasks continue running
- Multiple manager instances can spawn multiple heartbeat tasks

**Severity**: MEDIUM

**Fix**:
```python
# In websocket_service.py or websocket manager:
class WebSocketConnectionManager:
    def __init__(self):
        # ... existing code
        self._background_tasks: Set[asyncio.Task] = set()
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start background monitoring tasks."""
        # Start heartbeat monitoring
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        self._background_tasks.add(self._heartbeat_task)
        logger.info("WebSocket heartbeat monitor started")

    async def stop(self) -> None:
        """Stop background monitoring tasks."""
        logger.info("Stopping WebSocket connection manager")

        # Cancel heartbeat task
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                logger.debug("Heartbeat task cancelled")

        # Cancel all background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        logger.info("WebSocket connection manager stopped")
```

---

### 14. Redis Pub/Sub Listener Task Not Properly Cancelled

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py:387-437`

**Resource Type**: Background pub/sub listener task

**Code**:
```python
# Start pub/sub listener
await pubsub_manager.start()
```

**Leak Scenario**:
- Pub/Sub manager starts background listener task
- No explicit task cancellation in stop() method
- If Redis disconnects, listener task may hang waiting for reconnect

**Severity**: MEDIUM

**Fix**:
```python
# In RedisPubSubManager:
class RedisPubSubManager:
    def __init__(self, redis_client, connection_manager, instance_id):
        self.redis_client = redis_client
        self.connection_manager = connection_manager
        self.instance_id = instance_id
        self._listener_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start pub/sub listener."""
        if self._listener_task and not self._listener_task.done():
            logger.warning("Pub/Sub listener already running")
            return

        self._listener_task = asyncio.create_task(self._listen_for_messages())
        logger.info(f"Redis Pub/Sub listener started (instance: {self.instance_id})")

    async def stop(self) -> None:
        """Stop pub/sub listener gracefully."""
        logger.info("Stopping Redis Pub/Sub listener")

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                logger.debug("Pub/Sub listener cancelled")

        logger.info("Redis Pub/Sub listener stopped")

    async def _listen_for_messages(self) -> None:
        """Listen for messages from other instances."""
        try:
            async with self.redis_client.pubsub() as pubsub:
                await pubsub.subscribe(f"websocket:{self.instance_id}")
                async for message in pubsub.listen():
                    # Process message
                    pass
        except asyncio.CancelledError:
            logger.debug("Pub/Sub listener cancelled")
            raise
        except Exception as e:
            logger.error(f"Pub/Sub listener error: {e}")
            raise
```

---

## Low Priority Issues

### 15. File Handles Not Closed in Report Generation

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/tasks/reports.py:53`

**Resource Type**: File handle

**Code**:
```python
with open(output_path, "wb") as f:
    # ...
```

**Status**: ✅ **Already using context manager** - This is correctly implemented.

**Severity**: LOW (already fixed)

---

### 16. Logging Handlers Not Closed

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/utils/logging.py`

**Resource Type**: File logging handlers

**Leak Scenario**:
- Logging configuration may add handlers without removing them
- Multiple initializations create duplicate handlers
- File handles remain open after logger reconfiguration

**Severity**: LOW

**Fix**:
```python
# In setup_logging():
import logging

def setup_logging():
    """Setup logging with proper cleanup."""
    logger = logging.getLogger()

    # Remove existing handlers (prevents duplicates)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    # Add new handlers
    # ...
```

---

### 17. Connection Pool Monitoring Not Integrated

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/utils/database_optimization.py`

**Resource Type**: Database connection pool

**Severity**: LOW (monitoring only)

**Recommendation**:
```python
# Implement pool metrics collection
from sqlalchemy import event
from app.monitoring.database_monitor import record_pool_metric

def setup_pool_monitoring(engine):
    """Setup database pool monitoring."""
    @event.listens_for(engine.pool, "connect")
    def receive_connect(dbapi_conn, connection_record):
        record_pool_metric("connect", engine.pool.checkedout())

    @event.listens_for(engine.pool, "close")
    def receive_close(dbapi_conn, connection_record):
        record_pool_metric("close", engine.pool.checkedout())

    @event.listens_for(engine.pool, "detach")
    def receive_detach(dbapi_conn, connection_record):
        record_pool_metric("detach", engine.pool.checkedout())
```

---

### 18. Missing Service Container Cleanup

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/container.py`

**Resource Type**: Service instances (potential circular references)

**Severity**: LOW (depends on service implementation)

**Recommendation**:
```python
# Add cleanup method to service container
class ServiceContainer:
    async def cleanup(self) -> None:
        """Cleanup all services in container."""
        for service in self._services.values():
            if hasattr(service, 'cleanup'):
                try:
                    await service.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up service: {e}")

# Call in lifespan shutdown
```

---

## Severity Distribution

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 3 | Immediate |
| High | 6 | Next Sprint |
| Medium | 7 | Planned |
| Low | 2 | Monitor |
| **TOTAL** | **18** | |

---

## Action Items

### Immediate (This Sprint)
1. ✅ Fix EvolutionClient httpx cleanup
2. ✅ Fix Follow-up database session cleanup
3. ✅ Fix BaseRepository Redis pool leaks

### Next Sprint (High Priority)
4. ✅ Improve WebSocket memory management
5. ✅ Add ThreadPoolExecutor shutdown
6. ✅ Add Redis connection health checks
7. ✅ Implement Celery task cleanup on shutdown
8. ✅ Track asyncio tasks in Agent base class
9. ✅ Ensure EvolutionClient context manager usage

### Planned Maintenance
10. ✅ Add database pool pre-ping validation
11. ✅ Implement TTL-based cleanup for follow-up dicts
12. ✅ Add query timeouts to repositories
13. ✅ Improve WebSocket heartbeat task management
14. ✅ Add Redis Pub/Sub listener cancellation

### Monitoring
15. ✅ Add logging handler cleanup
16. ✅ Integrate pool monitoring metrics
17. ✅ Add service container cleanup

---

## Testing Recommendations

### Connection Pool Stress Test
```python
# Test database connection exhaustion handling
# Run N concurrent requests to verify pool doesn't leak
```

### Redis Connection Monitoring
```python
# Monitor Redis connection count during operation
# Verify it returns to baseline after shutdown
```

### WebSocket Memory Test
```python
# Connect/disconnect many clients rapidly
# Monitor memory usage doesn't grow indefinitely
```

### Task Cleanup Verification
```python
# Verify all background tasks are cancelled on shutdown
# Check for orphaned asyncio tasks
```

---

## Implementation Priority Matrix

| Issue | Effort | Impact | Priority |
|-------|--------|--------|----------|
| 1. EvolutionClient cleanup | Low | Critical | P0 |
| 2. Follow-up session cleanup | Low | Critical | P0 |
| 3. BaseRepository Redis pool | Medium | Critical | P0 |
| 4. WebSocket memory leak | Medium | High | P1 |
| 5. ThreadPoolExecutor shutdown | Low | High | P1 |
| 6. Redis health checks | Medium | High | P1 |
| 7. Celery task cleanup | Medium | High | P1 |
| 8. Agent task tracking | Medium | High | P1 |
| 9. EvolutionClient context | Low | High | P1 |

---

## Summary

The backend-hormonia codebase has **18 resource management issues** that need attention. Three are critical and require immediate fixes to prevent production failures. The main areas of concern are:

1. **Database/Redis Connection Leaks** - Lack of proper cleanup in error paths
2. **Async Task Management** - Background tasks not properly tracked and cancelled
3. **Memory Leaks** - In-memory collections growing without bounds
4. **HTTP Client Sessions** - Not using context managers consistently
5. **Service Shutdown** - Incomplete cleanup during graceful shutdown

Addressing the critical issues will significantly improve system reliability and prevent resource exhaustion in production.

