# Resource Management Issues - Implementation Checklist

## Critical Issues (P0) - Fix Before Next Deploy

### [ ] Issue #1: Evolution API httpx.AsyncClient Not Properly Closed
- **File**: `app/integrations/evolution/client.py`
- **Lines**: 111-118, 151-162
- **Task**: Add try/except for initialization and ensure close() is always called
- **Estimated Time**: 30 minutes
- **Test**: Create/destroy client 100 times, verify no connection leaks
- **Instructions**:
  1. Wrap `__init__` code in try/except
  2. Call `self.client.aclose()` in except block
  3. Add `__del__` method for garbage collection cleanup
  4. Test with: `pytest tests/integrations/test_evolution_cleanup.py`

---

### [ ] Issue #2: Database Session Not Properly Closed in Follow-Up System
- **File**: `app/core/lifespan.py`
- **Lines**: 484-497
- **Task**: Ensure db.close() is called even if FollowUpSystemService init fails
- **Estimated Time**: 20 minutes
- **Test**: Simulate FollowUpSystemService init failure, verify db is closed
- **Instructions**:
  1. Add nested try/except in _initialize_follow_up_system
  2. Verify db.close() in finally block catches all exceptions
  3. Add logging for cleanup success
  4. Test with: `pytest tests/core/test_lifespan_cleanup.py`

---

### [ ] Issue #3: Redis Connection Pool Not Properly Managed in BaseRepository
- **File**: `app/repositories/base.py`
- **Lines**: 37-58
- **Task**: Replace direct pool creation with shared RedisManager
- **Estimated Time**: 45 minutes
- **Test**: Create 50 repositories, verify only 1 connection pool exists
- **Instructions**:
  1. Remove `_redis_pool` property
  2. Use `get_redis_manager()` instead
  3. Add `__del__` method to BaseRepository
  4. Update all derived repository classes
  5. Test with: `pytest tests/repositories/test_redis_cleanup.py`

---

## High Priority Issues (P1) - Fix in Next Sprint

### [ ] Issue #4: WebSocket Connections Not Properly Garbage Collected
- **File**: `app/services/websocket_service.py`
- **Lines**: 64-76, 126-150
- **Task**: Ensure all dictionaries are cleaned even if errors occur
- **Estimated Time**: 1 hour
- **Test**: Connect/disconnect 1000 clients, verify dicts are empty
- **Implementation**:
  - [ ] Rewrite disconnect() with safe cleanup for all dicts
  - [ ] Use pop() instead of del for safety
  - [ ] Add finally blocks to ensure cleanup
  - [ ] Add metrics for cleanup verification

---

### [ ] Issue #5: ThreadPoolExecutor Not Properly Shutdown
- **File**: `app/core/async_context_manager.py`
- **Lines**: 92-94
- **Task**: Add cleanup() method and call from lifespan shutdown
- **Estimated Time**: 30 minutes
- **Test**: Monitor ThreadPoolExecutor threads, verify they terminate
- **Implementation**:
  - [ ] Add cleanup() method to EventLoopContext
  - [ ] Add __del__ method for backup cleanup
  - [ ] Call cleanup in lifespan _cleanup_other_resources
  - [ ] Add metrics logging for thread shutdown

---

### [ ] Issue #6: Redis AsyncClient Not Initialized with Connection Limits
- **File**: `app/core/redis_manager/manager.py`
- **Lines**: 88-90
- **Task**: Add connection health check and pool reuse validation
- **Estimated Time**: 1 hour
- **Test**: Create 100 concurrent connections, verify pool handles limit
- **Implementation**:
  - [ ] Add health check in get_async_client()
  - [ ] Implement connection recycling on unhealthy check
  - [ ] Add metrics for connection pool status
  - [ ] Add timeout for health check

---

### [ ] Issue #7: Celery Tasks Not Properly Cancelled on Shutdown
- **File**: `app/celery_app.py`
- **Lines**: 1-50
- **Task**: Add worker shutdown hook and task cleanup
- **Estimated Time**: 1 hour
- **Test**: Start celery worker, send shutdown signal, verify tasks cancel
- **Implementation**:
  - [ ] Add @worker_shutdown.connect signal handler
  - [ ] Implement task revocation with terminate=True
  - [ ] Add task lifecycle hooks (@task_prerun, @task_postrun)
  - [ ] Set result_expires for backend cleanup

---

### [ ] Issue #8: Untracked asyncio.create_task() Calls
- **File**: `app/agents/base.py`
- **Lines**: 420, 475, 479
- **Task**: Replace direct create_task with tracked version
- **Estimated Time**: 1 hour
- **Test**: Create 50 agents, verify all background tasks cancel on shutdown
- **Implementation**:
  - [ ] Add _background_tasks set to Agent class
  - [ ] Create _create_tracked_task() method
  - [ ] Replace all asyncio.create_task() calls
  - [ ] Add shutdown() method for cleanup

---

### [ ] Issue #9: EvolutionClient HTTP Session Not Explicitly Closed
- **File**: `app/integrations/evolution/client.py`
- **Lines**: 151-162
- **Task**: Audit all usages and wrap with context manager
- **Estimated Time**: 1 hour
- **Test**: Grep for EvolutionClient usage, verify all use 'async with'
- **Implementation**:
  - [ ] Add tracking of all EvolutionClient instantiations
  - [ ] Create wrapper context manager for unsafe usage
  - [ ] Add deprecation warning for direct instantiation
  - [ ] Update all callsites to use context manager

---

## Medium Priority Issues (P2) - Plan for Maintenance Sprint

### [ ] Issue #10: Database Pool Pre-Ping Not Configured for Async Sessions
- **File**: `app/core/database.py`
- **Lines**: 74-99
- **Task**: Ensure pool_pre_ping and pool_reset_on_return are properly configured
- **Estimated Time**: 30 minutes
- **Test**: Simulate database disconnect, verify pool detects and reconnects

---

### [ ] Issue #11: FollowUpSystemService Maintains Growing In-Memory Dictionaries
- **File**: `app/services/follow_up_system/service.py`
- **Lines**: 92-95
- **Task**: Implement TTL-based cleanup for dictionaries
- **Estimated Time**: 1.5 hours
- **Test**: Run for 24 hours, verify memory doesn't grow indefinitely

---

### [ ] Issue #12: No Timeout for Database Queries
- **File**: `app/repositories/base.py`
- **Task**: Add statement_timeout configuration and per-query timeout support
- **Estimated Time**: 1 hour
- **Test**: Run slow queries, verify they timeout correctly

---

### [ ] Issue #13: WebSocket Heartbeat Task Not Properly Stopped
- **File**: `app/core/lifespan.py:201-229`
- **Task**: Add explicit task cancellation to WebSocket manager
- **Estimated Time**: 45 minutes
- **Test**: Start/stop WebSocket manager, verify heartbeat task stops

---

### [ ] Issue #14: Redis Pub/Sub Listener Task Not Properly Cancelled
- **File**: `app/core/lifespan.py:387-437`
- **Task**: Add explicit task cancellation to RedisPubSubManager
- **Estimated Time**: 45 minutes
- **Test**: Start/stop Pub/Sub manager, verify listener task stops

---

## Low Priority Issues (P3) - Monitoring/Optional

### [ ] Issue #16: Logging Handlers Not Closed
- **File**: `app/utils/logging.py`
- **Task**: Add handler cleanup in setup_logging()
- **Estimated Time**: 15 minutes
- **Type**: Enhancement

---

### [ ] Issue #17: Connection Pool Monitoring Not Integrated
- **File**: `app/utils/database_optimization.py`
- **Task**: Add pool event listeners and metrics collection
- **Estimated Time**: 1 hour
- **Type**: Monitoring enhancement

---

### [ ] Issue #18: Missing Service Container Cleanup
- **File**: `app/services/container.py`
- **Task**: Add cleanup() method for service cleanup
- **Estimated Time**: 30 minutes
- **Type**: Enhancement

---

## Testing Strategy

### Unit Tests
```bash
# Create tests for each critical fix
pytest tests/integrations/test_evolution_cleanup.py
pytest tests/core/test_lifespan_cleanup.py
pytest tests/repositories/test_redis_cleanup.py
pytest tests/services/test_websocket_cleanup.py
pytest tests/agents/test_task_cleanup.py
```

### Integration Tests
```bash
# Test resource cleanup under load
pytest tests/integration/test_resource_cleanup_load.py
pytest tests/integration/test_graceful_shutdown.py
```

### Stress Tests
```bash
# Test connection pool exhaustion handling
pytest tests/stress/test_db_connection_exhaustion.py
pytest tests/stress/test_redis_connection_exhaustion.py
pytest tests/stress/test_websocket_many_connections.py
```

### Memory Profiling
```bash
# Monitor memory growth
python -m memory_profiler tests/profiling/test_memory_leaks.py
```

---

## Verification Checklist

After implementing each fix, verify:

### Resource Cleanup Verification
- [ ] No connection leaks after 1000 iterations
- [ ] Memory doesn't grow after repeated operations
- [ ] Task count returns to 0 after shutdown
- [ ] Connection pool checkedout count returns to baseline

### Logging Verification
- [ ] Cleanup messages appear in logs
- [ ] No error messages about unclosed resources
- [ ] Warnings logged for slow operations

### Performance Verification
- [ ] No performance regression from cleanup code
- [ ] Startup time remains <15 seconds
- [ ] Shutdown time remains <5 seconds

---

## Rollout Plan

### Phase 1: Critical Issues (Week 1)
1. Fix EvolutionClient cleanup
2. Fix Follow-up database session cleanup
3. Fix BaseRepository Redis pool leaks
4. Deploy to staging for 24-hour soak test

### Phase 2: High Priority (Week 2)
1. Fix WebSocket memory management
2. Fix ThreadPoolExecutor shutdown
3. Fix Redis health checks
4. Fix Celery task cleanup
5. Fix Agent task tracking
6. Deploy to staging for 48-hour soak test

### Phase 3: Medium Priority (Week 3)
1. Implement medium priority fixes
2. Deploy to staging
3. Monitor for 1 week

### Phase 4: Low Priority (Ongoing)
1. Implement monitoring enhancements
2. Integrate pool monitoring
3. Ongoing optimization

---

## Monitoring & Alerts

### Add metrics for:
- [ ] Database connection pool checkedout/checkouts
- [ ] Redis connection pool size
- [ ] AsyncIO active tasks count
- [ ] WebSocket active connections
- [ ] Celery pending/active/completed tasks

### Add alerts for:
- [ ] Connection pool threshold > 90%
- [ ] Memory growth > 1GB/hour
- [ ] Active tasks > 1000
- [ ] Redis connections > 95% of max

---

## Documentation Updates

### Update docs for:
- [ ] Database connection management best practices
- [ ] Resource cleanup patterns
- [ ] Proper context manager usage
- [ ] Background task lifecycle management

### Code examples to add:
- [ ] Context manager usage for HTTP clients
- [ ] Proper database session management
- [ ] Task cleanup patterns

---

## Team Review Points

1. Code review for all critical fixes
2. Architecture review for medium/high priority changes
3. Performance testing sign-off before production deploy
4. Monitoring setup verification

---

## Success Criteria

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Connection leaks per 1K ops | 0 | TBD | |
| Memory growth over 24h | <100MB | TBD | |
| Orphaned tasks at shutdown | 0 | TBD | |
| Graceful shutdown time | <5s | TBD | |
| Startup time | <15s | TBD | |

---

## Related Documentation

- [Resource Management Audit Report](./RESOURCE_MANAGEMENT_AUDIT_REPORT.md)
- [Architecture Overview](./database/02_ARCHITECTURE.md)
- [Performance Guide](./database/04_PERFORMANCE.md)

