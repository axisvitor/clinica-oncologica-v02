"""
Tests for transaction management utilities.

Tests both async and sync transaction context managers,
as well as the decorator pattern.

Author: Code Implementation Agent
Date: 2025-01-22
"""

import pytest
from unittest.mock import Mock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.utils.transaction_manager import (
    async_transaction,
    sync_transaction,
    with_transaction,
)


# ============================================================================
# Async Transaction Tests
# ============================================================================


@pytest.mark.asyncio
async def test_async_transaction_commits_on_success():
    """Test async transaction commits when no exception occurs."""
    mock_session = AsyncMock(spec=AsyncSession)

    async with async_transaction(mock_session) as session:
        # Perform some operations
        assert session is mock_session

    # Verify commit was called
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_async_transaction_rolls_back_on_error():
    """Test async transaction rolls back when exception occurs."""
    mock_session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError):
        async with async_transaction(mock_session) as session:
            raise ValueError("Test error")

    # Verify rollback was called
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_async_transaction_no_auto_commit():
    """Test async transaction with auto_commit=False."""
    mock_session = AsyncMock(spec=AsyncSession)

    async with async_transaction(mock_session, auto_commit=False) as session:
        assert session is mock_session

    # Verify commit was NOT called
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_async_transaction_no_auto_rollback():
    """Test async transaction with rollback_on_error=False."""
    mock_session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError):
        async with async_transaction(mock_session, rollback_on_error=False) as session:
            raise ValueError("Test error")

    # Verify rollback was NOT called
    mock_session.rollback.assert_not_called()
    mock_session.commit.assert_not_called()


# ============================================================================
# Sync Transaction Tests
# ============================================================================


def test_sync_transaction_commits_on_success():
    """Test sync transaction commits when no exception occurs."""
    mock_session = Mock(spec=Session)

    with sync_transaction(mock_session) as session:
        assert session is mock_session

    # Verify commit was called
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


def test_sync_transaction_rolls_back_on_error():
    """Test sync transaction rolls back when exception occurs."""
    mock_session = Mock(spec=Session)

    with pytest.raises(ValueError):
        with sync_transaction(mock_session) as session:
            raise ValueError("Test error")

    # Verify rollback was called
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


def test_sync_transaction_no_auto_commit():
    """Test sync transaction with auto_commit=False."""
    mock_session = Mock(spec=Session)

    with sync_transaction(mock_session, auto_commit=False) as session:
        assert session is mock_session

    # Verify commit was NOT called
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()


def test_sync_transaction_no_auto_rollback():
    """Test sync transaction with rollback_on_error=False."""
    mock_session = Mock(spec=Session)

    with pytest.raises(ValueError):
        with sync_transaction(mock_session, rollback_on_error=False) as session:
            raise ValueError("Test error")

    # Verify rollback was NOT called
    mock_session.rollback.assert_not_called()
    mock_session.commit.assert_not_called()


# ============================================================================
# Decorator Tests
# ============================================================================


@pytest.mark.asyncio
async def test_with_transaction_decorator_async():
    """Test with_transaction decorator on async function."""
    mock_session = AsyncMock(spec=AsyncSession)

    @with_transaction()
    async def test_func(db: AsyncSession, data: dict):
        db.add(data)
        return "success"

    result = await test_func(mock_session, {"key": "value"})

    assert result == "success"
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_with_transaction_decorator_async_error():
    """Test with_transaction decorator rolls back on error."""
    mock_session = AsyncMock(spec=AsyncSession)

    @with_transaction()
    async def test_func(db: AsyncSession):
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        await test_func(mock_session)

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_with_transaction_decorator_kwargs():
    """Test with_transaction decorator with session in kwargs."""
    mock_session = AsyncMock(spec=AsyncSession)

    @with_transaction()
    async def test_func(data: dict, db: AsyncSession):
        return data

    result = await test_func({"key": "value"}, db=mock_session)

    assert result == {"key": "value"}
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_with_transaction_decorator_service_pattern():
    """Test with_transaction decorator with service instance pattern."""
    mock_session = AsyncMock(spec=AsyncSession)

    class MockService:
        def __init__(self, db):
            self.db = db

    service = MockService(mock_session)

    @with_transaction()
    async def test_func(self, data: dict):
        return data

    result = await test_func(service, {"key": "value"})

    assert result == {"key": "value"}
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_with_transaction_decorator_no_session():
    """Test with_transaction decorator raises error when no session found."""

    @with_transaction()
    async def test_func(data: dict):
        return data

    with pytest.raises(ValueError, match="No database session found"):
        await test_func({"key": "value"})


def test_with_transaction_sync_decorator():
    """Test with_transaction decorator on sync function."""
    mock_session = Mock(spec=Session)

    @with_transaction()
    def test_func(db: Session, data: dict):
        db.add(data)
        return "success"

    result = test_func(mock_session, {"key": "value"})

    assert result == "success"
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


def test_with_transaction_sync_decorator_error():
    """Test with_transaction decorator rolls back on sync error."""
    mock_session = Mock(spec=Session)

    @with_transaction()
    def test_func(db: Session):
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        test_func(mock_session)

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


# ============================================================================
# Integration-like Tests (mocked database operations)
# ============================================================================


@pytest.mark.asyncio
async def test_async_transaction_with_database_operations():
    """Test async transaction with simulated database operations."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_model = Mock()

    async with async_transaction(mock_session) as session:
        # Simulate database operations
        session.add(mock_model)
        await session.flush()

    # Verify operations were performed and committed
    mock_session.add.assert_called_once_with(mock_model)
    mock_session.flush.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_async_transaction_multiple_operations():
    """Test async transaction with multiple operations and rollback."""
    mock_session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError):
        async with async_transaction(mock_session) as session:
            # First operation succeeds
            session.add(Mock())
            await session.flush()

            # Second operation fails
            raise ValueError("Operation failed")

    # Verify rollback was called despite successful first operation
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


def test_sync_transaction_multiple_operations():
    """Test sync transaction with multiple operations."""
    mock_session = Mock(spec=Session)

    with pytest.raises(ValueError):
        with sync_transaction(mock_session) as session:
            # Simulate operations
            session.add(Mock())
            session.flush()
            raise ValueError("Operation failed")

    # Verify rollback
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_async_transaction_commit_fails():
    """Test async transaction when commit fails."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = Exception("Commit failed")

    with pytest.raises(Exception, match="Commit failed"):
        async with async_transaction(mock_session):
            pass

    # Rollback should be called after commit failure
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_called_once()


def test_sync_transaction_commit_fails():
    """Test sync transaction when commit fails."""
    mock_session = Mock(spec=Session)
    mock_session.commit.side_effect = Exception("Commit failed")

    with pytest.raises(Exception, match="Commit failed"):
        with sync_transaction(mock_session):
            pass

    # Rollback should be called after commit failure
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_async_transaction_nested_operations():
    """Test nested async transaction operations."""
    mock_session = AsyncMock(spec=AsyncSession)

    async with async_transaction(mock_session) as session:
        session.add(Mock())

        # Simulate nested operation (not a nested transaction, just nested logic)
        async with async_transaction(session, auto_commit=False):
            session.add(Mock())

    # Only outer transaction commits
    assert mock_session.commit.call_count == 1


# ============================================================================
# Logging Tests
# ============================================================================


@pytest.mark.asyncio
async def test_async_transaction_logs_commit(caplog):
    """Test async transaction logs successful commit."""
    mock_session = AsyncMock(spec=AsyncSession)

    with caplog.at_level("DEBUG"):
        async with async_transaction(mock_session):
            pass

    assert "Transaction committed successfully" in caplog.text


@pytest.mark.asyncio
async def test_async_transaction_logs_rollback(caplog):
    """Test async transaction logs rollback on error."""
    mock_session = AsyncMock(spec=AsyncSession)

    with caplog.at_level("ERROR"):
        with pytest.raises(ValueError):
            async with async_transaction(mock_session):
                raise ValueError("Test error")

    assert "Transaction rolled back due to error" in caplog.text


def test_sync_transaction_logs_commit(caplog):
    """Test sync transaction logs successful commit."""
    mock_session = Mock(spec=Session)

    with caplog.at_level("DEBUG"):
        with sync_transaction(mock_session):
            pass

    assert "Transaction committed successfully" in caplog.text


def test_sync_transaction_logs_rollback(caplog):
    """Test sync transaction logs rollback on error."""
    mock_session = Mock(spec=Session)

    with caplog.at_level("ERROR"):
        with pytest.raises(ValueError):
            with sync_transaction(mock_session):
                raise ValueError("Test error")

    assert "Transaction rolled back due to error" in caplog.text
