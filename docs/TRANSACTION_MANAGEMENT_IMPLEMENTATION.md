# Transaction Management Implementation for AI and Template Services

## Executive Summary

After analyzing the codebase, I found that:
1. **Existing Transaction Utilities**: The project has `get_scoped_session()` context manager in `app/database.py`
2. **Missing Transaction Management**: AI and template services lack explicit transaction boundaries
3. **Async Context Manager Needed**: Most services are async and need `AsyncSession` transaction support

## Analysis of Current State

### Existing Transaction Patterns

#### 1. **Synchronous Transaction Context** (`app/database.py:128-153`)
```python
@contextmanager
def get_scoped_session():
    """Context manager for scoped database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()  # ✅ Auto-commit on success
    except Exception:
        session.rollback()  # ✅ Auto-rollback on failure
        raise
    finally:
        session.close()
```

#### 2. **Database Circuit Breaker** (`app/core/database_circuit_breaker.py:121`)
```python
async def execute_transaction(self, transaction_func: Callable, ...):
    """Execute database operation with circuit breaker protection."""
    # Has transaction support but not a reusable utility
```

### Services Missing Transaction Management

#### 1. **PatientSummaryService** (`app/services/ai/patient_summary_service.py`)
**Line 347-363**: Direct database operations without transaction context
```python
async def _save_summary(self, response: PatientSummaryResponse) -> None:
    summary = PatientSummary(...)
    self.db.add(summary)
    await self.db.commit()  # ❌ No rollback on failure
```

**Line 457-458**: Missing transaction for PDF save
```python
summary.pdf_data = pdf_bytes
await self.db.commit()  # ❌ No transaction boundary
```

#### 2. **TemplateLoader** (`app/services/template_loader.py`)
**Line 544-581**: Template creation without explicit transactions
```python
def create_template_version(...):
    # Create kind if needed
    kind = self.flow_kind_repo.create_kind(...)  # ❌ No transaction

    # Create template version
    self.template_version_repo.create_version(...)  # ❌ Separate operation

    # Could fail between operations causing inconsistency
```

**Line 583-616**: Publish operation without transaction
```python
def publish_template_version(...):
    success = self.template_version_repo.publish_version(...)
    if set_as_current:
        self.flow_kind_repo.update_current_version(...)  # ❌ Not atomic
```

#### 3. **AIService** (`app/services/ai/ai_service.py`)
- **Cache operations**: Store/retrieve operations need transaction safety
- **No database writes currently**: Uses Redis cache, but if extended to DB caching needs transactions

## Solution: Async Transaction Context Manager

### Implementation

Create `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/utils/transaction_manager.py`:

```python
"""
Database transaction management utilities.

Provides async and sync context managers for database transactions
with automatic commit/rollback and error handling.
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def async_transaction(
    session: AsyncSession,
    auto_commit: bool = True,
    rollback_on_error: bool = True,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database transactions.

    Provides automatic commit on success and rollback on failure.

    Args:
        session: AsyncSession for database operations
        auto_commit: Automatically commit on success (default: True)
        rollback_on_error: Automatically rollback on error (default: True)

    Yields:
        AsyncSession: The database session

    Example:
        >>> async with async_transaction(db) as session:
        ...     session.add(new_record)
        ...     # Auto-commits on success, auto-rolls back on exception
    """
    try:
        yield session

        if auto_commit:
            await session.commit()
            logger.debug("Transaction committed successfully")

    except Exception as e:
        if rollback_on_error:
            await session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
        raise


@contextmanager
def sync_transaction(
    session: Session,
    auto_commit: bool = True,
    rollback_on_error: bool = True,
) -> Generator[Session, None, None]:
    """
    Sync context manager for database transactions.

    Provides automatic commit on success and rollback on failure.

    Args:
        session: Session for database operations
        auto_commit: Automatically commit on success (default: True)
        rollback_on_error: Automatically rollback on error (default: True)

    Yields:
        Session: The database session

    Example:
        >>> with sync_transaction(db) as session:
        ...     session.add(new_record)
        ...     # Auto-commits on success, auto-rolls back on exception
    """
    try:
        yield session

        if auto_commit:
            session.commit()
            logger.debug("Transaction committed successfully")

    except Exception as e:
        if rollback_on_error:
            session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
        raise


# Decorator for automatic transaction management
def with_transaction(auto_commit: bool = True, rollback_on_error: bool = True):
    """
    Decorator for automatic transaction management on async functions.

    Wraps the function with async_transaction context manager.
    Expects the first argument to be 'db' or 'session'.

    Args:
        auto_commit: Automatically commit on success
        rollback_on_error: Automatically rollback on error

    Example:
        >>> @with_transaction()
        ... async def create_record(db: AsyncSession, data: dict):
        ...     record = Model(**data)
        ...     db.add(record)
        ...     return record
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract session from args or kwargs
            session = kwargs.get('db') or kwargs.get('session')
            if not session and args:
                session = args[0] if isinstance(args[0], (AsyncSession, Session)) else None

            if not session:
                raise ValueError("No database session found in function arguments")

            # Use appropriate transaction context
            if isinstance(session, AsyncSession):
                async with async_transaction(session, auto_commit, rollback_on_error):
                    return await func(*args, **kwargs)
            else:
                with sync_transaction(session, auto_commit, rollback_on_error):
                    return func(*args, **kwargs)

        return wrapper
    return decorator
```

## Implementation Plan

### Phase 1: Update PatientSummaryService

**File**: `app/services/ai/patient_summary_service.py`

```python
from app.utils.transaction_manager import async_transaction

class PatientSummaryService:

    async def _save_summary(self, response: PatientSummaryResponse) -> None:
        """Save summary to database with transaction."""
        async with async_transaction(self.db):
            summary = PatientSummary(
                id=response.summary_id,
                patient_id=response.patient_id,
                generated_by=response.generated_by,
                start_date=response.start_date,
                end_date=response.end_date,
                content=response.content.model_dump(),
                token_usage=response.token_usage,
                model_used=response.model_used,
                generation_time_ms=response.generation_time_ms,
            )

            self.db.add(summary)
            # Transaction auto-commits on success

        logger.info(f"Saved summary {response.summary_id} to database")

    async def export_to_pdf(self, summary_id: UUID) -> bytes:
        """Export summary to PDF with transaction."""
        # Get summary (read-only, no transaction needed)
        result = await self.db.execute(
            select(PatientSummary).where(PatientSummary.id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise ValueError(f"Summary {summary_id} not found")

        # Check if PDF already exists
        if summary.pdf_data:
            return summary.pdf_data

        # Generate PDF (I/O operation, no transaction)
        pdf_bytes = await self._generate_pdf(summary)

        # Save PDF with transaction
        async with async_transaction(self.db):
            summary.pdf_data = pdf_bytes
            # Transaction auto-commits on success

        return pdf_bytes
```

### Phase 2: Update TemplateLoader (Sync)

**File**: `app/services/template_loader.py`

```python
from app.utils.transaction_manager import sync_transaction

class EnhancedTemplateLoader:

    def create_template_version(
        self,
        flow_type: str,
        version: str,
        template_data: FlowTemplateData,
        description: str = None,
        created_by: str = None,
    ) -> bool:
        """Create a new template version with transaction."""
        try:
            # Use database session from repositories
            # Assuming repositories share a session
            db_session = self.flow_kind_repo.db

            with sync_transaction(db_session):
                # Get or create flow kind
                kind = self.flow_kind_repo.get_by_flow_type(flow_type)
                if not kind:
                    kind = self.flow_kind_repo.create_kind(
                        flow_type=flow_type,
                        name=template_data.name,
                        description=description or template_data.description,
                    )

                # Create template version
                self.template_version_repo.create_version(
                    kind_id=kind.id,
                    version=version,
                    template_data=template_data.to_dict(),
                    duration_days=len(template_data.messages),
                    description=description,
                    created_by=created_by,
                )

                # Transaction auto-commits on success

            # Clear cache after successful commit
            self._invalidate_cache_for_flow_type(flow_type)

            logger.info(f"Created new template version: {flow_type} v{version}")
            return True

        except Exception as e:
            logger.error(f"Error creating template version: {e}")
            return False

    def publish_template_version(
        self, flow_type: str, version: str, set_as_current: bool = True
    ) -> bool:
        """Publish a draft template version with transaction."""
        try:
            db_session = self.template_version_repo.db

            with sync_transaction(db_session):
                template_version = self.template_version_repo.get_by_flow_type_and_version(
                    flow_type, version
                )
                if not template_version:
                    logger.error(f"Template version not found: {flow_type} v{version}")
                    return False

                # Publish the version
                success = self.template_version_repo.publish_version(template_version.id)
                if not success:
                    raise Exception("Failed to publish version")

                # Optionally set as current version
                if set_as_current:
                    kind = self.flow_kind_repo.get_by_flow_type(flow_type)
                    if kind:
                        self.flow_kind_repo.update_current_version(
                            kind.id, template_version.id
                        )

                # Transaction auto-commits on success

            # Clear cache after successful commit
            self._invalidate_cache_for_flow_type(flow_type)

            logger.info(f"Published template version: {flow_type} v{version}")
            return True

        except Exception as e:
            logger.error(f"Error publishing template version: {e}")
            return False
```

### Phase 3: Add Transaction Support to FlowTemplateManager

**File**: `app/services/flow/templates/manager.py`

**Note**: This manager doesn't directly interact with database sessions. Repository operations need transaction support in their respective implementations.

The manager's bulk operations should leverage repository-level transactions:

```python
from app.utils.transaction_manager import sync_transaction

class FlowTemplateManager:

    def create_templates_bulk(
        self,
        templates_data: List[Dict[str, Any]],
        validate: bool = True,
    ) -> List[FlowTemplate]:
        """Create multiple templates in a single transaction."""
        created = []

        try:
            # Get database session from repository
            db_session = self.repository.db if hasattr(self.repository, 'db') else None

            if db_session:
                with sync_transaction(db_session):
                    for template_data in templates_data:
                        template = self.create_template(template_data, validate=validate)
                        created.append(template)
                    # Transaction auto-commits on success
            else:
                # Fallback to individual transactions
                for template_data in templates_data:
                    try:
                        template = self.create_template(template_data, validate=validate)
                        created.append(template)
                    except Exception as e:
                        logger.warning(
                            f"Failed to create template {template_data.get('template_id')}: {e}"
                        )

            logger.info(f"Bulk created {len(created)} templates")
            return created

        except Exception as e:
            logger.error(f"Bulk template creation failed: {e}")
            # All or nothing - return empty list on transaction failure
            return []
```

## Benefits

### 1. **Data Consistency**
- Atomic operations prevent partial updates
- All-or-nothing guarantees for multi-step operations
- Automatic rollback prevents data corruption

### 2. **Error Handling**
- Centralized transaction management
- Consistent error handling across services
- Automatic cleanup on failures

### 3. **Code Clarity**
- Explicit transaction boundaries
- Clear separation of concerns
- Self-documenting code with context managers

### 4. **Maintainability**
- Reusable transaction utilities
- Easy to test transaction behavior
- Reduced code duplication

## Testing Strategy

### Unit Tests

Create `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/tests/utils/test_transaction_manager.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.transaction_manager import async_transaction, sync_transaction

@pytest.mark.asyncio
async def test_async_transaction_commit(async_db_session: AsyncSession):
    """Test async transaction commits on success."""
    async with async_transaction(async_db_session) as session:
        # Add test data
        session.add(TestModel(name="test"))

    # Verify committed
    result = await async_db_session.execute(select(TestModel))
    assert result.scalar_one_or_none() is not None

@pytest.mark.asyncio
async def test_async_transaction_rollback(async_db_session: AsyncSession):
    """Test async transaction rolls back on error."""
    with pytest.raises(ValueError):
        async with async_transaction(async_db_session) as session:
            session.add(TestModel(name="test"))
            raise ValueError("Test error")

    # Verify rolled back
    result = await async_db_session.execute(select(TestModel))
    assert result.scalar_one_or_none() is None

def test_sync_transaction_commit(db_session: Session):
    """Test sync transaction commits on success."""
    with sync_transaction(db_session) as session:
        session.add(TestModel(name="test"))

    # Verify committed
    assert db_session.query(TestModel).first() is not None
```

### Integration Tests

Test service-level transactions:

```python
@pytest.mark.asyncio
async def test_save_summary_transaction(patient_summary_service, async_db):
    """Test summary save with transaction."""
    response = PatientSummaryResponse(...)

    await patient_summary_service._save_summary(response)

    # Verify saved
    result = await async_db.execute(
        select(PatientSummary).where(PatientSummary.id == response.summary_id)
    )
    summary = result.scalar_one_or_none()
    assert summary is not None
    assert summary.patient_id == response.patient_id
```

## Migration Checklist

- [ ] Create `app/utils/transaction_manager.py`
- [ ] Update `PatientSummaryService._save_summary()`
- [ ] Update `PatientSummaryService.export_to_pdf()`
- [ ] Update `TemplateLoader.create_template_version()`
- [ ] Update `TemplateLoader.publish_template_version()`
- [ ] Add transaction support to repository base classes
- [ ] Create unit tests for transaction utilities
- [ ] Create integration tests for services
- [ ] Update documentation
- [ ] Code review and merge

## Performance Considerations

1. **Transaction Scope**: Keep transactions as short as possible
2. **Read Operations**: Don't wrap read-only operations in transactions
3. **External API Calls**: Never include in transaction blocks
4. **Batch Operations**: Use single transaction for batch inserts/updates

## Security Considerations

1. **SQL Injection**: Transaction utilities don't prevent SQL injection - use parameterized queries
2. **Access Control**: Transactions don't enforce permissions - check before transaction
3. **Audit Logging**: Log transaction start/commit/rollback for compliance

## Conclusion

Implementing proper transaction management in AI and template services will:
- **Prevent data inconsistencies** from partial updates
- **Improve error handling** with automatic rollbacks
- **Enhance code quality** with explicit transaction boundaries
- **Increase maintainability** with reusable utilities

The proposed `async_transaction` and `sync_transaction` context managers provide a clean, Pythonic API that integrates seamlessly with existing code.
