# Test Utilities

This directory contains utility classes and helpers for testing.

## SyncExecutor

**File:** `sync_executor.py`

A synchronous executor that provides a drop-in replacement for `ThreadPoolExecutor` specifically designed for testing scenarios.

### Purpose

SQLite databases have strict thread-safety requirements - database objects created in one thread cannot be used in another thread. When using `ThreadPoolExecutor` in tests with SQLite, you'll encounter errors like:

```
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread
```

`SyncExecutor` solves this by executing all tasks synchronously in the current thread, avoiding thread-related issues while maintaining the same API as `ThreadPoolExecutor`.

### Usage

#### As a pytest fixture

```python
def test_my_service(sync_executor, db_session):
    """Test service with database access."""
    service = MyService(executor=sync_executor)

    # This will execute synchronously in the current thread
    future = service.process_task(db_session, data)
    result = future.result()

    assert result is not None
```

#### Direct instantiation

```python
from tests.utils.sync_executor import SyncExecutor

def test_direct_usage():
    executor = SyncExecutor()

    future = executor.submit(lambda x: x * 2, 21)
    assert future.result() == 42

    executor.shutdown()
```

#### As context manager

```python
from tests.utils.sync_executor import SyncExecutor

def test_context_manager():
    with SyncExecutor() as executor:
        future = executor.submit(my_function, arg1, arg2)
        result = future.result()
```

### API Compatibility

`SyncExecutor` implements the following `ThreadPoolExecutor` methods:

- `submit(fn, *args, **kwargs) -> Future`: Execute function and return Future
- `shutdown(wait=True) -> None`: No-op for compatibility
- `__enter__()` / `__exit__()`: Context manager support

### Key Differences from ThreadPoolExecutor

1. **Synchronous execution**: Tasks execute immediately in the current thread
2. **No thread pool**: No actual threads are created
3. **Immediate results**: `Future.result()` is available immediately after `submit()`
4. **Shutdown is no-op**: Unlike `ThreadPoolExecutor`, executor continues working after `shutdown()`

### Testing the Fixture

Run the comprehensive test suite:

```bash
pytest tests/test_sync_executor_fixture.py -v
```

Tests cover:
- Fixture availability
- Basic submit functionality
- Keyword arguments
- Exception handling
- Context manager usage
- Shutdown behavior
- Multiple tasks
- Database integration

### When to Use

✅ **Use SyncExecutor when:**
- Testing services that use executors with SQLite databases
- Running unit tests that need executor interface
- Avoiding thread-related test flakiness
- Need deterministic, synchronous test execution

❌ **Don't use SyncExecutor when:**
- Testing actual threading behavior
- Production code (use real ThreadPoolExecutor)
- Testing async/await code (use asyncio instead)
- Need actual parallel execution

### Performance Notes

Since `SyncExecutor` runs tasks synchronously:
- Tests are deterministic and reproducible
- No race conditions or timing issues
- Slightly slower than parallel execution for CPU-bound tasks
- Much faster test development due to easier debugging

### Example: Service Testing

```python
# app/services/my_service.py
from concurrent.futures import ThreadPoolExecutor

class MyService:
    def __init__(self, executor=None):
        self.executor = executor or ThreadPoolExecutor(max_workers=4)

    def process_data(self, db_session, data):
        """Process data using executor."""
        return self.executor.submit(self._process, db_session, data)

    def _process(self, db_session, data):
        # Database operations here
        result = db_session.query(Model).filter_by(id=data.id).first()
        return result


# tests/services/test_my_service.py
def test_my_service(sync_executor, db_session):
    """Test service with sync executor to avoid SQLite threading issues."""
    service = MyService(executor=sync_executor)

    data = {"id": 1, "value": "test"}
    future = service.process_data(db_session, data)

    # Result is immediately available
    result = future.result()
    assert result is not None
```

### Integration with conftest.py

The `sync_executor` fixture is automatically available to all tests via `conftest.py`:

```python
# conftest.py
from tests.utils.sync_executor import SyncExecutor

@pytest.fixture
def sync_executor():
    """Synchronous executor for testing (avoids SQLite threading issues)."""
    return SyncExecutor()
```

No additional imports or configuration needed in test files!
