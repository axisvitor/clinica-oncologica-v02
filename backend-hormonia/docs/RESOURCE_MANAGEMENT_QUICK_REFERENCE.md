# Resource Management Issues - Quick Reference Guide

## Critical Issues Summary (Must Fix Immediately)

### 1. EvolutionClient httpx.AsyncClient Leak
```
File: app/integrations/evolution/client.py:111-118
Issue: HTTP client not closed on init error
Fix: Add try/except in __init__, implement __del__
Time: 30 min | Severity: CRITICAL
```

### 2. Follow-Up Database Session Leak
```
File: app/core/lifespan.py:484-497
Issue: db.close() not called if FollowUpSystemService init fails
Fix: Add nested try/except, ensure finally calls close()
Time: 20 min | Severity: CRITICAL
```

### 3. BaseRepository Redis Pool Leak
```
File: app/repositories/base.py:37-58
Issue: Redis ConnectionPool created per repository, never closed
Fix: Use shared RedisManager, add __del__
Time: 45 min | Severity: CRITICAL
```

---

## High Priority Issues (Next Sprint)

| # | File | Issue | Time | Type |
|---|------|-------|------|------|
| 4 | `app/services/websocket_service.py:64-76` | Memory not freed on disconnect | 1h | Memory leak |
| 5 | `app/core/async_context_manager.py:92-94` | ThreadPoolExecutor never shutdown | 30m | Thread leak |
| 6 | `app/core/redis_manager/manager.py:88-90` | No connection health checks | 1h | Pool exhaustion |
| 7 | `app/celery_app.py:1-50` | No task cleanup on shutdown | 1h | Zombie tasks |
| 8 | `app/agents/base.py:420,475,479` | Orphaned asyncio tasks | 1h | Task leak |
| 9 | `app/integrations/evolution/client.py:151-162` | Context manager not used | 1h | Connection leak |

---

## Code Patterns to Fix

### Pattern 1: Unsafe Resource Creation
```python
# BAD - Resource leaks on exception
def __init__(self):
    self.client = httpx.AsyncClient()
    self.handler = RequestHandler(self.client)  # If this fails, client never closed

# GOOD - Resource cleanup on exception
def __init__(self):
    self.client = None
    try:
        self.client = httpx.AsyncClient()
        self.handler = RequestHandler(self.client)
    except Exception:
        if self.client:
            await self.client.aclose()
        raise
```

### Pattern 2: Untracked Background Tasks
```python
# BAD - Task created but never tracked
async def start(self):
    asyncio.create_task(self._background_work())

# GOOD - Task tracked for cleanup
async def start(self):
    task = asyncio.create_task(self._background_work())
    self._tasks.add(task)
    task.add_done_callback(self._tasks.discard)

async def stop(self):
    for task in self._tasks:
        task.cancel()
    await asyncio.gather(*self._tasks, return_exceptions=True)
```

### Pattern 3: Growing Collections
```python
# BAD - Dictionary grows unbounded
self.cache: dict = {}

# GOOD - Dictionary with TTL cleanup
from collections import OrderedDict
from datetime import datetime, timedelta

class TTLDict:
    def __init__(self, ttl_seconds=3600):
        self._data = OrderedDict()
        self._timestamps = {}
        self.ttl_seconds = ttl_seconds

    def set(self, key, value):
        self._cleanup()
        self._data[key] = value
        self._timestamps[key] = datetime.now()

    def _cleanup(self):
        now = datetime.now()
        expired = [
            k for k, ts in self._timestamps.items()
            if (now - ts).total_seconds() > self.ttl_seconds
        ]
        for k in expired:
            del self._data[k]
            del self._timestamps[k]
```

### Pattern 4: Unsafe Dictionary Cleanup
```python
# BAD - Exception in cleanup can leave dict in bad state
async def disconnect(self, connection_id):
    del self.active_connections[connection_id]
    del self.user_connections[user_id][connection_id]  # May fail
    del self.metadata[connection_id]  # Never executed

# GOOD - Safe cleanup with pop()
async def disconnect(self, connection_id):
    ws = self.active_connections.pop(connection_id, None)
    if ws:
        await ws.close()

    metadata = self.metadata.pop(connection_id, {})
    user_id = metadata.get('user_id')
    if user_id:
        user_conns = self.user_connections.get(user_id, set())
        user_conns.discard(connection_id)
        if not user_conns:
            self.user_connections.pop(user_id, None)
```

---

## Verification Checklist

### Before Deploying Each Fix
- [ ] Added proper exception handling
- [ ] Added cleanup in finally/except blocks
- [ ] Added background task tracking
- [ ] Added shutdown hooks
- [ ] Verified context managers used
- [ ] No circular references
- [ ] Memory profiler shows no growth
- [ ] Stress test passes (1000+ iterations)

### After Deploying
- [ ] Monitor connection pool metrics
- [ ] Monitor memory growth
- [ ] Monitor active task count
- [ ] Check application logs for errors
- [ ] Run load test and verify cleanup

---

## Quick Fix Templates

### Template 1: Safe Resource Initialization
```python
async def initialize_resource(self):
    """Initialize resource with proper cleanup on error."""
    resource = None
    try:
        resource = await create_resource()
        self.resource = resource
        return resource
    except Exception as e:
        if resource:
            await cleanup_resource(resource)
        logger.error(f"Failed to initialize resource: {e}")
        raise
```

### Template 2: Safe Resource Cleanup
```python
async def cleanup_resource(self):
    """Cleanup resource with robust error handling."""
    if not hasattr(self, 'resource') or not self.resource:
        return

    try:
        # Attempt graceful shutdown
        if hasattr(self.resource, 'shutdown'):
            await self.resource.shutdown()
        # Then close connections
        if hasattr(self.resource, 'close'):
            await self.resource.close()
    except Exception as e:
        logger.error(f"Error cleaning up resource: {e}")
    finally:
        self.resource = None
```

### Template 3: Task Lifecycle Management
```python
class ServiceWithBackgroundTasks:
    def __init__(self):
        self._tasks: Set[asyncio.Task] = set()

    async def _create_task(self, coro):
        """Create and track background task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def shutdown(self):
        """Cancel all background tasks."""
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
```

---

## Debugging Commands

### Check Connection Pool Status
```python
# In psql for PostgreSQL
SELECT count(*) as connections
FROM pg_stat_activity
WHERE datname = 'hormonia';

SELECT count(*) as max_connections FROM pg_settings
WHERE name = 'max_connections';
```

### Check Redis Connections
```bash
redis-cli info stats | grep connected_clients
redis-cli info memory
```

### Check Open Files (Linux)
```bash
lsof -p $(pgrep -f "python.*main.py") | grep -E "TCP|PIPE|socket"
```

### Check Active AsyncIO Tasks
```python
import asyncio
print(len(asyncio.all_tasks()))  # Should be 0 on shutdown
```

### Memory Profiling
```bash
pip install memory-profiler
python -m memory_profiler test_script.py
```

---

## Related Issues by Subsystem

### Database Subsystem
- Issue #2: Follow-up database session leak (lifespan.py)
- Issue #10: Database pool pre-ping configuration
- Issue #12: No timeout for queries

### Redis Subsystem
- Issue #3: BaseRepository Redis pool leak
- Issue #6: Redis async client health checks

### WebSocket Subsystem
- Issue #4: WebSocket memory leaks
- Issue #13: WebSocket heartbeat task cleanup
- Issue #14: Redis Pub/Sub listener task cleanup

### Background Tasks
- Issue #7: Celery task cleanup on shutdown
- Issue #8: Asyncio task tracking in Agent

### HTTP Clients
- Issue #1: EvolutionClient httpx cleanup
- Issue #9: EvolutionClient context manager usage

### Service Lifecycle
- Issue #5: ThreadPoolExecutor shutdown
- Issue #11: Growing in-memory dictionaries
- Issue #18: Service container cleanup

---

## Implementation Order (Recommended)

### Day 1 (Critical)
1. Fix EvolutionClient httpx (Issue #1)
2. Fix Follow-up db session (Issue #2)
3. Fix BaseRepository Redis pool (Issue #3)

### Day 2-3 (High Priority)
4. Fix WebSocket memory (Issue #4)
5. Fix ThreadPool executor (Issue #5)
6. Fix Redis health checks (Issue #6)
7. Fix Celery task cleanup (Issue #7)
8. Fix asyncio task tracking (Issue #8)
9. Fix EvolutionClient context (Issue #9)

### Week 2-3 (Medium)
10-14. Implement remaining medium priority fixes

---

## Key Metrics to Monitor

After fixes are deployed, monitor:

```python
# Database connections
metrics.gauge('db.pool.checked_out', db.pool.checkedout())
metrics.gauge('db.pool.size', db.pool.size())

# Redis connections
metrics.gauge('redis.connected_clients', redis_info['connected_clients'])

# Asyncio tasks
metrics.gauge('asyncio.tasks', len(asyncio.all_tasks()))

# WebSocket connections
metrics.gauge('websocket.active_connections', len(ws_manager.active_connections))

# Memory usage
metrics.gauge('process.memory.rss', process.memory_info().rss)
```

---

## Emergency Recovery Procedures

If resource exhaustion occurs in production:

### Database Connection Exhaustion
```sql
-- Kill idle connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '1 hour';

-- Check pool status
SELECT * FROM pg_stat_activity;
```

### Redis Connection Exhaustion
```bash
# Restart Redis
redis-cli SHUTDOWN
# Then restart server

# Or manually close old connections
redis-cli CLIENT LIST
redis-cli CLIENT KILL TYPE normal
```

### AsyncIO Task Leak
```python
# In running application
import asyncio
tasks = asyncio.all_tasks()
for task in tasks:
    print(f"Task: {task.get_name()}, Done: {task.done()}")
    # Cancel if needed
    task.cancel()
```

---

## References

- Full audit report: [RESOURCE_MANAGEMENT_AUDIT_REPORT.md](./RESOURCE_MANAGEMENT_AUDIT_REPORT.md)
- Implementation checklist: [RESOURCE_MANAGEMENT_FIX_CHECKLIST.md](./RESOURCE_MANAGEMENT_FIX_CHECKLIST.md)
- Architecture docs: [database/02_ARCHITECTURE.md](./database/02_ARCHITECTURE.md)
- Performance guide: [database/04_PERFORMANCE.md](./database/04_PERFORMANCE.md)

