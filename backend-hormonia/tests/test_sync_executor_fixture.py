"""
Test suite for SyncExecutor fixture integration.

This module demonstrates the usage of the sync_executor fixture
and validates its functionality for SQLite thread-safety in tests.
"""
import pytest
from concurrent.futures import Future
from uuid import UUID


def test_sync_executor_fixture_available(sync_executor):
    """Test that sync_executor fixture is properly loaded."""
    assert sync_executor is not None
    assert hasattr(sync_executor, 'submit')
    assert hasattr(sync_executor, 'shutdown')


def test_sync_executor_submit_simple(sync_executor):
    """Test basic submit functionality."""
    def simple_task(x, y):
        return x + y

    future = sync_executor.submit(simple_task, 5, 3)
    assert isinstance(future, Future)
    assert future.result() == 8


def test_sync_executor_submit_with_kwargs(sync_executor):
    """Test submit with keyword arguments."""
    def task_with_kwargs(name, age=0):
        return f"{name} is {age} years old"

    future = sync_executor.submit(task_with_kwargs, "Alice", age=30)
    assert future.result() == "Alice is 30 years old"


def test_sync_executor_exception_handling(sync_executor):
    """Test that exceptions are properly captured in futures."""
    def failing_task():
        raise ValueError("Test exception")

    future = sync_executor.submit(failing_task)
    assert future.done()

    with pytest.raises(ValueError, match="Test exception"):
        future.result()


def test_sync_executor_context_manager(sync_executor):
    """Test executor can be used as context manager."""
    with sync_executor as executor:
        future = executor.submit(lambda x: x * 2, 21)
        assert future.result() == 42


def test_sync_executor_shutdown(sync_executor):
    """Test shutdown method (no-op but should not raise)."""
    sync_executor.shutdown(wait=True)
    # Should still work after shutdown (unlike ThreadPoolExecutor)
    future = sync_executor.submit(lambda: "still working")
    assert future.result() == "still working"


def test_sync_executor_multiple_tasks(sync_executor):
    """Test multiple sequential task submissions."""
    results = []
    for i in range(5):
        future = sync_executor.submit(lambda x: x ** 2, i)
        results.append(future.result())

    assert results == [0, 1, 4, 9, 16]


def test_sync_executor_database_simulation(sync_executor, db_session):
    """
    Test that sync_executor works with database sessions.

    This simulates the real use case where we need to avoid
    SQLite threading issues by using synchronous execution.
    """
    from app.models.user import User

    def create_user_task(session, email):
        """Simulate a task that uses database session."""
        # This would normally cause issues with ThreadPoolExecutor
        # but works fine with SyncExecutor
        user = User(
            email=email,
            hashed_password="test_hash",
            full_name="Test User",
            is_active=True
        )
        session.add(user)
        session.flush()
        return user.id

    future = sync_executor.submit(create_user_task, db_session, "test@sync.com")
    user_id = future.result()

    assert user_id is not None
    assert isinstance(user_id, UUID)
