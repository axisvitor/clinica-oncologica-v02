# Performance Quick Fixes - Priority Actions

**Date**: December 23, 2025
**Status**: Ready for Implementation

---

## Critical Issues (Fix This Week)

### 1. Parallelize Monitoring Initialization (8-30s → 4-12s)

**File**: `/app/monitoring/manager.py`

**Problem**: Monitoring components initialize sequentially, blocking startup for 8-30 seconds.

**Fix**:
```python
async def _initialize_components(self) -> None:
    """Initialize monitoring components in parallel."""

    # Phase 1: Core collectors (independent)
    logger.info("Initializing core monitoring collectors in parallel...")

    results = await asyncio.gather(
        self._init_apm_collector(),
        self._init_db_monitor(),
        self._init_resource_monitor(),
        self._init_business_metrics(),
        return_exceptions=True
    )

    # Check for failures
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Collector {i} failed: {result}")

    # Phase 2: Dependent components (need collectors)
    logger.info("Initializing dependent monitoring components...")

    await asyncio.gather(
        self._init_dashboard(),
        self._init_anomaly_detector(),
        self._init_metrics_exporter(),
        return_exceptions=True
    )

async def _init_apm_collector(self):
    if self.config.apm.enabled:
        self.apm_collector = APMCollector(self.redis_client)
        logger.info("APM collector initialized")

async def _init_db_monitor(self):
    if self.config.database.enabled:
        self.db_monitor = DatabasePerformanceMonitor(self.redis_client)
        logger.info("Database monitor initialized")

# ... similar for other components
```

**Expected Impact**: 50-60% reduction in monitoring initialization time
**Effort**: 2-3 hours
**Risk**: Low (components are independent)

---

### 2. Add Memory Profiling

**File**: Create `/app/monitoring/memory_profiler.py`

**Problem**: No memory leak detection or profiling in place.

**Fix**:
```python
"""Memory profiling and leak detection."""
import tracemalloc
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MemoryProfiler:
    """Track memory usage and detect leaks."""

    def __init__(self):
        self.enabled = False
        self.snapshots = []
        self.baseline = None

    def start(self):
        """Start memory profiling."""
        tracemalloc.start()
        self.enabled = True
        self.baseline = tracemalloc.take_snapshot()
        logger.info("Memory profiling started")

    def stop(self):
        """Stop memory profiling."""
        if self.enabled:
            tracemalloc.stop()
            self.enabled = False
            logger.info("Memory profiling stopped")

    def take_snapshot(self) -> Dict[str, Any]:
        """Take memory snapshot and compare to baseline."""
        if not self.enabled:
            return {"error": "Profiling not enabled"}

        snapshot = tracemalloc.take_snapshot()
        self.snapshots.append({
            "timestamp": datetime.now(),
            "snapshot": snapshot
        })

        # Compare to baseline
        top_stats = snapshot.compare_to(self.baseline, 'lineno')

        # Top 10 memory consumers
        top_10 = []
        for stat in top_stats[:10]:
            top_10.append({
                "file": stat.traceback.format()[0],
                "size_mb": stat.size / 1024 / 1024,
                "size_diff_mb": stat.size_diff / 1024 / 1024,
                "count": stat.count,
                "count_diff": stat.count_diff
            })

        current, peak = tracemalloc.get_traced_memory()

        return {
            "timestamp": datetime.now().isoformat(),
            "current_mb": current / 1024 / 1024,
            "peak_mb": peak / 1024 / 1024,
            "top_10_consumers": top_10,
            "total_snapshots": len(self.snapshots)
        }

    def detect_leaks(self, threshold_mb: float = 10.0) -> List[Dict[str, Any]]:
        """Detect potential memory leaks."""
        if len(self.snapshots) < 2:
            return []

        leaks = []

        # Compare recent snapshots
        for i in range(len(self.snapshots) - 1):
            old = self.snapshots[i]["snapshot"]
            new = self.snapshots[i + 1]["snapshot"]

            diff = new.compare_to(old, 'lineno')

            for stat in diff:
                size_diff_mb = stat.size_diff / 1024 / 1024

                if size_diff_mb > threshold_mb:
                    leaks.append({
                        "file": stat.traceback.format()[0],
                        "size_increase_mb": size_diff_mb,
                        "timestamp_start": self.snapshots[i]["timestamp"],
                        "timestamp_end": self.snapshots[i + 1]["timestamp"]
                    })

        return leaks

# Global instance
_profiler = MemoryProfiler()

def get_memory_profiler() -> MemoryProfiler:
    return _profiler
```

**Usage in lifespan.py**:
```python
from app.monitoring.memory_profiler import get_memory_profiler

async def _startup(app: FastAPI):
    # Start memory profiling
    profiler = get_memory_profiler()
    profiler.start()
    app.state.memory_profiler = profiler

    # ... rest of startup

    # Take initial snapshot
    snapshot = profiler.take_snapshot()
    logger.info(f"Initial memory: {snapshot['current_mb']:.2f}MB")
```

**Add periodic leak detection** (background task):
```python
async def periodic_memory_check():
    """Run every hour to detect memory leaks."""
    profiler = get_memory_profiler()

    while True:
        await asyncio.sleep(3600)  # 1 hour

        snapshot = profiler.take_snapshot()
        leaks = profiler.detect_leaks(threshold_mb=10.0)

        logger.info(
            f"Memory check: {snapshot['current_mb']:.2f}MB current, "
            f"{snapshot['peak_mb']:.2f}MB peak"
        )

        if leaks:
            logger.error(f"Potential memory leaks detected: {len(leaks)}")
            for leak in leaks:
                logger.error(f"Leak: {leak}")
```

**Expected Impact**: Early detection of memory leaks
**Effort**: 3-4 hours
**Risk**: Low (monitoring only, no business logic changes)

---

### 3. Connection Pool Utilization Alerts

**File**: `/app/monitoring/database_monitor.py`

**Problem**: No alerts when connection pool is near exhaustion.

**Fix**:
```python
async def check_pool_health(self) -> Dict[str, Any]:
    """Check connection pool health and alert on issues."""
    if not self.engine:
        return {"error": "Engine not available"}

    pool = self.engine.pool

    pool_size = pool.size()
    checked_out = pool.checkedout()
    utilization = (checked_out / pool_size * 100) if pool_size > 0 else 0

    health = {
        "pool_size": pool_size,
        "checked_out": checked_out,
        "checked_in": pool.checkedin(),
        "overflow": pool.overflow(),
        "utilization_percent": round(utilization, 2),
        "status": "healthy"
    }

    # Alert thresholds
    if utilization >= 95:
        health["status"] = "critical"
        logger.error(
            f"CRITICAL: Connection pool near exhaustion: {utilization:.1f}%",
            extra={
                "event_type": "connection_pool_critical",
                "utilization": utilization,
                "checked_out": checked_out,
                "pool_size": pool_size
            }
        )
    elif utilization >= 80:
        health["status"] = "warning"
        logger.warning(
            f"WARNING: High connection pool utilization: {utilization:.1f}%",
            extra={
                "event_type": "connection_pool_warning",
                "utilization": utilization
            }
        )

    return health
```

**Add to health check endpoint**:
```python
# app/routers/health.py
@router.get("/health/database")
async def database_health():
    db_monitor = get_monitoring_manager().db_monitor
    if db_monitor:
        pool_health = await db_monitor.check_pool_health()
        return {"database": pool_health}
    return {"error": "Database monitor not available"}
```

**Expected Impact**: Prevent connection pool exhaustion
**Effort**: 1-2 hours
**Risk**: Low (monitoring only)

---

## High Priority (Next Sprint)

### 4. WebSocket Connection Limits

**File**: `/app/services/websocket_service.py` (or wherever WebSocket manager is)

**Problem**: No maximum connection limit, risk of memory exhaustion.

**Fix**:
```python
class WebSocketManager:
    def __init__(self, max_connections: int = 1000):
        self.connections = {}
        self.max_connections = max_connections

    async def connect(self, connection_id: str, websocket: WebSocket):
        # Check connection limit
        if len(self.connections) >= self.max_connections:
            logger.warning(
                f"WebSocket connection limit reached: {self.max_connections}",
                extra={
                    "event_type": "websocket_limit_reached",
                    "active_connections": len(self.connections)
                }
            )
            await websocket.close(
                code=1008,
                reason=f"Server at capacity ({self.max_connections} connections)"
            )
            return False

        # Accept connection
        await websocket.accept()
        self.connections[connection_id] = {
            "websocket": websocket,
            "connected_at": datetime.now(),
            "messages_sent": 0
        }

        logger.info(
            f"WebSocket connected: {connection_id} "
            f"({len(self.connections)}/{self.max_connections})"
        )
        return True
```

**Expected Impact**: Prevent memory exhaustion from excessive connections
**Effort**: 1-2 hours
**Risk**: Low

---

### 5. Background Task Manager

**File**: Create `/app/utils/background_task_manager.py`

**Problem**: 137 background tasks without centralized tracking or timeout enforcement.

**Fix**:
```python
"""Centralized background task manager with monitoring and timeouts."""
import asyncio
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """Centralized manager for background tasks."""

    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_metrics = defaultdict(lambda: {
            "count": 0,
            "duration_avg_ms": 0,
            "errors": 0,
            "timeouts": 0,
            "last_run": None
        })

    async def create_task(
        self,
        name: str,
        coro: Callable,
        timeout: Optional[float] = 60.0,
        on_error: Optional[Callable] = None
    ) -> str:
        """
        Create and track a background task.

        Args:
            name: Task name for metrics
            coro: Coroutine to run
            timeout: Timeout in seconds (None for no timeout)
            on_error: Optional error handler

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        start = datetime.now()

        async def wrapped_task():
            try:
                if timeout:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                else:
                    result = await coro

                # Update metrics
                duration_ms = (datetime.now() - start).total_seconds() * 1000

                self.task_metrics[name]["count"] += 1
                self.task_metrics[name]["duration_avg_ms"] = (
                    (self.task_metrics[name]["duration_avg_ms"] + duration_ms) / 2
                )
                self.task_metrics[name]["last_run"] = datetime.now()

                logger.debug(
                    f"Background task completed: {name} ({duration_ms:.2f}ms)"
                )

                return result

            except asyncio.TimeoutError:
                logger.error(
                    f"Background task timeout: {name} (>{timeout}s)",
                    extra={
                        "event_type": "background_task_timeout",
                        "task_name": name,
                        "timeout_seconds": timeout
                    }
                )
                self.task_metrics[name]["timeouts"] += 1

                if on_error:
                    await on_error(asyncio.TimeoutError(f"Timeout after {timeout}s"))

            except Exception as e:
                logger.error(
                    f"Background task error: {name}: {e}",
                    extra={
                        "event_type": "background_task_error",
                        "task_name": name,
                        "error": str(e)
                    },
                    exc_info=True
                )
                self.task_metrics[name]["errors"] += 1

                if on_error:
                    await on_error(e)

            finally:
                # Remove from active tasks
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]

        # Create task
        task = asyncio.create_task(wrapped_task())
        self.active_tasks[task_id] = task

        logger.info(
            f"Background task created: {name} (id={task_id}, "
            f"timeout={timeout}s, active={len(self.active_tasks)})"
        )

        return task_id

    def get_metrics(self) -> Dict[str, Any]:
        """Get task metrics."""
        return {
            "active_count": len(self.active_tasks),
            "task_metrics": dict(self.task_metrics),
            "timestamp": datetime.now().isoformat()
        }

    async def cancel_all(self):
        """Cancel all active tasks."""
        logger.info(f"Cancelling {len(self.active_tasks)} background tasks...")

        for task_id, task in self.active_tasks.items():
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)

        self.active_tasks.clear()
        logger.info("All background tasks cancelled")

# Global instance
_task_manager = BackgroundTaskManager()

def get_task_manager() -> BackgroundTaskManager:
    return _task_manager
```

**Usage**:
```python
from app.utils.background_task_manager import get_task_manager

# Instead of:
asyncio.create_task(some_background_work())

# Use:
task_manager = get_task_manager()
await task_manager.create_task(
    name="message_processing",
    coro=process_message(msg),
    timeout=30.0
)
```

**Expected Impact**: Better resource control, timeout enforcement, metrics
**Effort**: 4-6 hours
**Risk**: Medium (requires refactoring existing background tasks)

---

## Testing Checklist

After implementing each fix:

- [ ] Run startup 10 times, measure average time
- [ ] Check logs for any new errors
- [ ] Monitor memory usage for 1 hour
- [ ] Run load test with 100 concurrent users
- [ ] Verify all health check endpoints return 200
- [ ] Check Prometheus/Grafana metrics (if available)

---

## Rollback Plan

If any fix causes issues:

1. **Revert the specific file**:
   ```bash
   git checkout HEAD -- path/to/file.py
   ```

2. **Restart the application**:
   ```bash
   systemctl restart hormonia-backend
   ```

3. **Monitor logs**:
   ```bash
   tail -f /var/log/hormonia/app.log
   ```

4. **Report issue** with:
   - Error logs
   - Metrics before/after
   - Steps to reproduce

---

## Monitoring After Implementation

**Track these metrics**:

1. **Startup time** (target: <15s avg):
   ```bash
   # Add to startup logs
   logger.info(f"Startup completed in {total_time:.2f}s")
   ```

2. **Memory usage** (target: <70%, no leaks):
   ```bash
   # Check every hour
   GET /health/memory
   ```

3. **Connection pool** (target: <80% utilization):
   ```bash
   # Check every 5 minutes
   GET /health/database
   ```

4. **Background tasks** (target: <1% error rate):
   ```bash
   # Check metrics endpoint
   GET /api/v2/system/metrics
   ```

---

**Last Updated**: December 23, 2025
**Next Review**: January 6, 2026 (after implementations)
