# Redis Failure Handling

Test added:
- `tests/core/test_distributed_lock.py::TestRedisFailureHandling::test_try_acquire_raises_on_redis_failure`

Behavior:
- Fail-fast. Redis exceptions propagate from `DistributedLock.try_acquire`.

Note:
- No fallback or retry on Redis outage in `DistributedLock`.
