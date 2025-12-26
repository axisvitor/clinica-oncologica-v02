# FastAPI Initialization Timeout - Implementation Plan

## Overview

This document provides step-by-step instructions to implement timeout fixes for FastAPI initialization bottlenecks.

**Problem**: App initialization takes 14-56 seconds (target: <5 seconds)

**Root Causes**:
1. Firebase Admin SDK initialization (10-30s)
2. Redis connection timeouts (5-15s)
3. Sequential service initialization (no parallelization)
4. Missing timeout protection on network calls

---

## Quick Wins (Priority 1) - 1-2 hours

### Step 1: Add Firebase Initialization Timeout

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/firebase_auth_service.py`

**Current Code** (Lines 42-73):
```python
def _initialize_firebase(self):
    try:
        formatted_key = self.private_key.replace("\\n", "\n")
        cred_dict = {...}
        cred = credentials.Certificate(cred_dict)

        # ISSUE: No timeout protection
        if not firebase_admin._apps:
            FirebaseAuthService._app = firebase_admin.initialize_app(cred)
```

**Fix**:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

def _initialize_firebase(self):
    """Initialize Firebase with 10s timeout protection."""
    try:
        formatted_key = self.private_key.replace("\\n", "\n")
        cred_dict = {
            "type": "service_account",
            "project_id": self.project_id,
            "private_key": formatted_key,
            "client_email": self.client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        cred = credentials.Certificate(cred_dict)

        if not firebase_admin._apps:
            # Wrap blocking call with timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(firebase_admin.initialize_app, cred)
                try:
                    FirebaseAuthService._app = future.result(timeout=10.0)
                    logger.info(f"Firebase initialized successfully for {self.project_id}")
                except FuturesTimeoutError:
                    logger.error("Firebase initialization timeout after 10s")
                    raise TimeoutError("Firebase initialization timeout")
        else:
            FirebaseAuthService._app = firebase_admin.get_app()

        FirebaseAuthService._initialized = True

    except TimeoutError:
        logger.error("Firebase initialization timeout - continuing in degraded mode")
        FirebaseAuthService._initialized = False
        # Don't raise - allow app to start without Firebase
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise
```

**Expected Impact**: Reduce worst-case from 30s to 10s

---

### Step 2: Reduce Redis Startup Timeouts

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py`

**Current Code** (Line 189):
```python
async def _initialize_redis_websocket_events(app: FastAPI, logger) -> None:
    redis_client = None
    try:
        redis_manager = get_redis_manager()
        redis_client = await redis_manager.get_async_client()
```

**Fix**:
```python
from app.core.initialization_helpers import initialize_with_timeout

async def _initialize_redis_websocket_events(app: FastAPI, logger) -> None:
    """Initialize Redis with 2s timeout for fast startup."""
    try:
        # Create Redis client with timeout
        redis_client = await initialize_with_timeout(
            func=lambda: get_redis_manager().get_async_client(),
            timeout=2.0,  # Fast fail during startup
            service_name="Redis WebSocket Events",
            logger=logger,
            fallback=None,
            critical=False  # Continue without Redis
        )

        if redis_client:
            await _setup_websocket_events(redis_client, logger)
            app.state.redis_client = redis_client
            app.state.redis_manager = get_redis_manager()
            logger.info("✓ Redis WebSocket events initialized")
        else:
            logger.warning("Continuing without Redis WebSocket events")
            app.state.redis_client = None

    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        logger.warning("Continuing without WebSocket events")
        app.state.redis_client = None
```

**Expected Impact**: Reduce worst-case from 15s to 2s

---

### Step 3: Remove Database Connectivity Test from Startup

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py`

**Current Code** (Lines 304-312):
```python
try:
    from app.database import test_connection
    logger.info("Testing database connectivity...")
    db_status = test_connection()  # BLOCKS on database
    logger.info(f"Database connectivity test result: {db_status}")
except Exception as db_error:
    logger.error(f"Database connectivity test failed: {db_error}")
```

**Fix**: Remove or defer to health check endpoint
```python
# Remove the database connectivity test
# Database health will be checked via /health/ready endpoint

try:
    session_manager = initialize_session_manager(redis_client)
    app.state.session_manager = session_manager
    logger.info("✓ Session manager initialized")

    # Log manager info without connectivity test
    logger.info(f"Session manager instance: {type(session_manager).__name__}")

except Exception as e:
    logger.error(f"Failed to initialize session manager: {e}")
    app.state.session_manager = None
```

**Expected Impact**: Reduce initialization by 2-5s

---

### Step 4: Add Monitoring Initialization Timeout

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py`

**Current Code** (Lines 143-159):
```python
async def _initialize_monitoring(app: FastAPI, logger) -> None:
    try:
        from app.monitoring.manager import initialize_monitoring, start_monitoring

        monitoring_manager = await initialize_monitoring()
        await start_monitoring()
```

**Fix**:
```python
from app.core.initialization_helpers import initialize_with_timeout

async def _initialize_monitoring(app: FastAPI, logger) -> None:
    """Initialize monitoring with timeout protection."""
    try:
        from app.monitoring.manager import initialize_monitoring, start_monitoring

        # Initialize with 5s timeout
        monitoring_manager = await initialize_with_timeout(
            func=initialize_monitoring,
            timeout=5.0,
            service_name="Monitoring System",
            logger=logger,
            fallback=None,
            critical=False
        )

        if monitoring_manager:
            await start_monitoring()
            app.state.monitoring_manager = monitoring_manager
            logger.info("✓ Monitoring system started")
        else:
            logger.warning("Monitoring system unavailable")
            app.state.monitoring_manager = None

    except Exception as e:
        logger.error(f"Monitoring initialization failed: {e}")
        app.state.monitoring_manager = None
```

**Expected Impact**: Reduce worst-case from 10s to 5s

---

## Structural Improvements (Priority 2) - 4-6 hours

### Step 5: Implement Parallel Initialization

**File**: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py`

**Current Code** (Lines 52-102):
```python
async def _startup(app: FastAPI):
    # Sequential initialization
    await _initialize_monitoring(app, logger)
    await _initialize_redis_websocket_events(app, logger)
    await _initialize_websocket_manager(app, logger)
    await _initialize_redis_pubsub(app, logger)
    await _initialize_session_manager(app, logger)
    await _initialize_ai_services(app, logger)
    await _initialize_enum_validation(app, logger)
    await _initialize_follow_up_system(app, logger)
```

**Fix**:
```python
from app.core.initialization_helpers import parallel_initialize, StartupTimer

async def _startup(app: FastAPI):
    """Startup with parallel initialization and timing."""
    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)
    configure_structured_logging(log_level="DEBUG" if settings.APP_ENABLE_DEBUG else "INFO")

    # Create startup timer
    timer = StartupTimer()

    # Record startup time
    app.state.start_time = time.time()
    logger.info("Starting Hormonia Backend System")

    # Phase 1: Core services (must complete first)
    async with timer.track("Monitoring"):
        await _initialize_monitoring(app, logger)

    # Phase 2: Independent services (parallel)
    async with timer.track("Parallel Services"):
        await parallel_initialize([
            ("Redis WebSocket", lambda: _initialize_redis_websocket_events(app, logger), 2.0),
            ("WebSocket Manager", lambda: _initialize_websocket_manager(app, logger), 3.0),
            ("AI Services", lambda: _initialize_ai_services(app, logger), 2.0),
            ("Enum Validation", lambda: _initialize_enum_validation(app, logger), 1.0),
        ], logger)

    # Phase 3: Dependent services (sequential)
    async with timer.track("Redis Pub/Sub"):
        await _initialize_redis_pubsub(app, logger)

    async with timer.track("Session Manager"):
        await _initialize_session_manager(app, logger)

    async with timer.track("Follow-up System"):
        await _initialize_follow_up_system(app, logger)

    # Log startup report
    timer.log_report(logger)
    logger.info("Hormonia Backend System startup completed")

    return logger
```

**Expected Impact**: Reduce initialization from 18-36s to 10-15s (40-60% faster)

---

### Step 6: Add Circuit Breakers for External Services

**File**: Create circuit breaker wrappers for Firebase and Redis

**Implementation**:
```python
# app/services/firebase_auth_service.py
from app.core.circuit_breaker import CircuitBreaker

class FirebaseAuthService:
    _circuit_breaker = None

    def __init__(self, project_id: str, private_key: str, client_email: str):
        self.project_id = project_id
        self.private_key = private_key
        self.client_email = client_email

        # Create circuit breaker
        if not FirebaseAuthService._circuit_breaker:
            FirebaseAuthService._circuit_breaker = CircuitBreaker(
                name="Firebase Auth",
                failure_threshold=3,
                timeout=10.0,
                recovery_timeout=60.0
            )

        if not FirebaseAuthService._initialized:
            self._initialize_firebase()

    def _initialize_firebase(self):
        """Initialize with circuit breaker protection."""
        try:
            # Use circuit breaker
            result = asyncio.run(
                self._circuit_breaker.call(
                    func=lambda: self._do_firebase_init(),
                    fallback=None
                )
            )

            if result:
                FirebaseAuthService._initialized = True
            else:
                logger.warning("Firebase unavailable - circuit breaker open")

        except Exception as e:
            logger.error(f"Firebase initialization failed: {e}")
```

**Expected Impact**: Fast-fail after 3 failures, prevent repeated timeout waits

---

## Testing Plan

### Test 1: Timeout Protection
```bash
# Test Firebase timeout (should complete in <12s)
python -c "
import time
from app.services.firebase_auth_service import FirebaseAuthService

start = time.time()
try:
    service = FirebaseAuthService('test-project', 'invalid-key', 'test@test.com')
except Exception as e:
    pass
duration = time.time() - start
print(f'Duration: {duration:.2f}s (expected: <12s)')
assert duration < 12, f'Timeout protection failed: {duration}s'
"
```

### Test 2: Parallel Initialization
```bash
# Test parallel initialization performance
pytest tests/test_startup_performance.py::test_parallel_initialization -v
```

### Test 3: Circuit Breaker
```bash
# Test circuit breaker fast-fail
pytest tests/test_circuit_breaker.py::test_firebase_circuit_breaker -v
```

---

## Verification Checklist

After implementing fixes, verify:

- [ ] Firebase initialization completes within 10s (or fails gracefully)
- [ ] Redis connection attempts timeout within 2s
- [ ] Database connectivity test removed from startup
- [ ] Monitoring initialization completes within 5s
- [ ] Independent services initialize in parallel
- [ ] Total startup time < 15s (best case: <8s)
- [ ] App starts successfully even if services unavailable
- [ ] Circuit breakers prevent repeated timeout waits
- [ ] Startup timing metrics logged
- [ ] Tests pass with new timeout configuration

---

## Rollback Plan

If issues occur after implementation:

1. **Revert timeout changes**:
   ```bash
   git checkout HEAD -- app/services/firebase_auth_service.py
   git checkout HEAD -- app/core/lifespan.py
   ```

2. **Disable parallel initialization**:
   - Comment out `parallel_initialize()` calls
   - Restore sequential initialization

3. **Increase timeouts temporarily**:
   ```python
   # Temporarily increase if needed
   REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 10  # Was: 2
   FIREBASE_INIT_TIMEOUT = 30  # Was: 10
   ```

---

## Monitoring After Deployment

### Metrics to Track

1. **Startup Time**:
   - Total initialization duration
   - Per-component timing
   - Slowest component

2. **Timeout Events**:
   - Firebase timeout count
   - Redis timeout count
   - Services unavailable count

3. **Circuit Breaker State**:
   - State transitions (CLOSED → OPEN → HALF_OPEN)
   - Fast-fail count
   - Recovery success rate

### Alerts to Configure

```python
# Alert if startup takes > 20s
if startup_duration > 20:
    alert("Slow startup detected", severity="warning")

# Alert if circuit breaker opens
if circuit_state == "OPEN":
    alert("Service circuit breaker open", severity="critical")

# Alert if services unavailable
if redis_unavailable or firebase_unavailable:
    alert("External service unavailable", severity="warning")
```

---

## Expected Results

### Before Fix
- **Best case**: 14s (all services available)
- **Worst case**: 56s (multiple timeouts)
- **Test reliability**: 60-70%

### After Phase 1 (Quick Wins)
- **Best case**: 8s (43% improvement)
- **Worst case**: 20s (64% improvement)
- **Test reliability**: 85-90%

### After Phase 2 (Structural)
- **Best case**: 5s (64% improvement)
- **Worst case**: 12s (79% improvement)
- **Test reliability**: 95%+

---

## Files Modified

1. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/firebase_auth_service.py` - Firebase timeout
2. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/lifespan.py` - Parallel init, Redis timeout
3. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/initialization_helpers.py` - NEW helper utilities
4. `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/circuit_breaker.py` - NEW circuit breaker

---

## Next Steps

1. **Review this plan** with the team
2. **Implement Phase 1** (Quick Wins) first
3. **Test thoroughly** in development environment
4. **Deploy to staging** and monitor startup metrics
5. **Implement Phase 2** if Phase 1 results are satisfactory
6. **Document learnings** and update runbooks

---

## Support & References

- **Detailed Analysis**: `INITIALIZATION_TIMEOUT_ANALYSIS.md`
- **Circuit Breaker Pattern**: https://martinfowler.com/bliki/CircuitBreaker.html
- **FastAPI Lifespan**: https://fastapi.tiangolo.com/advanced/events/
- **Asyncio Timeouts**: https://docs.python.org/3/library/asyncio-task.html#timeouts
