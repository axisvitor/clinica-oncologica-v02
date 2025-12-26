# Transaction Management Examples

## Overview

This document provides practical examples of adding transaction management to AI and template services.

## Example 1: PatientSummaryService Updates

### Current Implementation (Missing Transactions)

**File**: `app/services/ai/patient_summary_service.py`

```python
# ❌ BEFORE: No transaction management
async def _save_summary(self, response: PatientSummaryResponse) -> None:
    """Save summary to database."""
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
    await self.db.commit()  # ❌ No rollback on failure

    logger.info(f"Saved summary {response.summary_id} to database")
```

### Updated Implementation (With Transactions)

```python
# ✅ AFTER: With transaction management
from app.utils.transaction_manager import async_transaction

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
        # Transaction auto-commits on success, auto-rolls back on error

    logger.info(f"Saved summary {response.summary_id} to database")
```

### PDF Export Update

```python
# ❌ BEFORE: No transaction for PDF save
async def export_to_pdf(self, summary_id: UUID) -> bytes:
    """Export summary to PDF."""
    result = await self.db.execute(
        select(PatientSummary).where(PatientSummary.id == summary_id)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        raise ValueError(f"Summary {summary_id} not found")

    if summary.pdf_data:
        return summary.pdf_data

    pdf_bytes = await self._generate_pdf(summary)

    summary.pdf_data = pdf_bytes
    await self.db.commit()  # ❌ No rollback on failure

    return pdf_bytes
```

```python
# ✅ AFTER: With transaction for PDF save
from app.utils.transaction_manager import async_transaction

async def export_to_pdf(self, summary_id: UUID) -> bytes:
    """Export summary to PDF with transaction."""
    # Read operation - no transaction needed
    result = await self.db.execute(
        select(PatientSummary).where(PatientSummary.id == summary_id)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        raise ValueError(f"Summary {summary_id} not found")

    # Return cached PDF if exists
    if summary.pdf_data:
        return summary.pdf_data

    # Generate PDF (I/O operation outside transaction)
    pdf_bytes = await self._generate_pdf(summary)

    # Save PDF with transaction
    async with async_transaction(self.db):
        summary.pdf_data = pdf_bytes
        # Transaction auto-commits on success

    return pdf_bytes
```

## Example 2: TemplateLoader Updates

### Create Template Version (Multi-Step Operation)

```python
# ❌ BEFORE: No transaction - operations can fail partially
def create_template_version(
    self,
    flow_type: str,
    version: str,
    template_data: FlowTemplateData,
    description: str = None,
    created_by: str = None,
) -> bool:
    """Create a new template version."""
    try:
        # Step 1: Get or create flow kind
        kind = self.flow_kind_repo.get_by_flow_type(flow_type)
        if not kind:
            kind = self.flow_kind_repo.create_kind(
                flow_type=flow_type,
                name=template_data.name,
                description=description or template_data.description,
            )  # ❌ Could commit here

        # Step 2: Create template version
        self.template_version_repo.create_version(
            kind_id=kind.id,
            version=version,
            template_data=template_data.to_dict(),
            duration_days=len(template_data.messages),
            description=description,
            created_by=created_by,
        )  # ❌ If this fails, we have orphaned kind

        # Cache invalidation
        self._invalidate_cache_for_flow_type(flow_type)

        logger.info(f"Created new template version: {flow_type} v{version}")
        return True

    except Exception as e:
        logger.error(f"Error creating template version: {e}")
        return False
```

```python
# ✅ AFTER: With transaction - all-or-nothing guarantee
from app.utils.transaction_manager import sync_transaction

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
        # Get database session (assuming repositories share session)
        db_session = self.flow_kind_repo.db

        with sync_transaction(db_session):
            # Step 1: Get or create flow kind
            kind = self.flow_kind_repo.get_by_flow_type(flow_type)
            if not kind:
                kind = self.flow_kind_repo.create_kind(
                    flow_type=flow_type,
                    name=template_data.name,
                    description=description or template_data.description,
                )

            # Step 2: Create template version
            self.template_version_repo.create_version(
                kind_id=kind.id,
                version=version,
                template_data=template_data.to_dict(),
                duration_days=len(template_data.messages),
                description=description,
                created_by=created_by,
            )

            # Transaction auto-commits here (all-or-nothing)

        # Cache invalidation after successful transaction
        self._invalidate_cache_for_flow_type(flow_type)

        logger.info(f"Created new template version: {flow_type} v{version}")
        return True

    except Exception as e:
        logger.error(f"Error creating template version: {e}")
        return False
```

### Publish Template Version (Atomic State Change)

```python
# ❌ BEFORE: Race condition - version published but not set as current
def publish_template_version(
    self, flow_type: str, version: str, set_as_current: bool = True
) -> bool:
    """Publish a draft template version."""
    try:
        template_version = self.template_version_repo.get_by_flow_type_and_version(
            flow_type, version
        )
        if not template_version:
            logger.error(f"Template version not found: {flow_type} v{version}")
            return False

        # Step 1: Publish the version
        success = self.template_version_repo.publish_version(template_version.id)
        if not success:
            return False  # ❌ Version state may be inconsistent

        # Step 2: Set as current version
        if set_as_current:
            kind = self.flow_kind_repo.get_by_flow_type(flow_type)
            if kind:
                self.flow_kind_repo.update_current_version(
                    kind.id, template_version.id
                )  # ❌ If this fails, version is published but not current

        # Clear cache
        self._invalidate_cache_for_flow_type(flow_type)

        logger.info(f"Published template version: {flow_type} v{version}")
        return True

    except Exception as e:
        logger.error(f"Error publishing template version: {e}")
        return False
```

```python
# ✅ AFTER: Atomic publish and set current
from app.utils.transaction_manager import sync_transaction

def publish_template_version(
    self, flow_type: str, version: str, set_as_current: bool = True
) -> bool:
    """Publish a draft template version with atomic transaction."""
    try:
        db_session = self.template_version_repo.db

        with sync_transaction(db_session):
            # Get template version
            template_version = self.template_version_repo.get_by_flow_type_and_version(
                flow_type, version
            )
            if not template_version:
                raise ValueError(f"Template version not found: {flow_type} v{version}")

            # Step 1: Publish the version
            success = self.template_version_repo.publish_version(template_version.id)
            if not success:
                raise Exception("Failed to publish version")

            # Step 2: Set as current version (atomic with publish)
            if set_as_current:
                kind = self.flow_kind_repo.get_by_flow_type(flow_type)
                if kind:
                    self.flow_kind_repo.update_current_version(
                        kind.id, template_version.id
                    )

            # Transaction auto-commits here (both steps succeed or both fail)

        # Clear cache after successful transaction
        self._invalidate_cache_for_flow_type(flow_type)

        logger.info(f"Published template version: {flow_type} v{version}")
        return True

    except Exception as e:
        logger.error(f"Error publishing template version: {e}")
        return False
```

## Example 3: Using the Decorator Pattern

### Decorator for Service Methods

```python
from app.utils.transaction_manager import with_transaction
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class PatientDataService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @with_transaction()
    async def create_patient_record(self, data: dict) -> Patient:
        """
        Create patient record with automatic transaction management.

        The decorator automatically:
        - Extracts self.db
        - Wraps operation in transaction
        - Commits on success
        - Rolls back on error
        """
        patient = Patient(**data)
        self.db.add(patient)
        return patient

    @with_transaction()
    async def update_patient_metadata(self, patient_id: UUID, metadata: dict) -> Patient:
        """Update patient metadata with transaction."""
        result = await self.db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        patient.metadata = metadata
        return patient

    @with_transaction()
    async def batch_update_patients(self, updates: list[dict]) -> list[Patient]:
        """Batch update patients in a single transaction."""
        updated_patients = []

        for update in updates:
            result = await self.db.execute(
                select(Patient).where(Patient.id == update["id"])
            )
            patient = result.scalar_one_or_none()

            if patient:
                for key, value in update.items():
                    if key != "id":
                        setattr(patient, key, value)
                updated_patients.append(patient)

        return updated_patients
```

## Example 4: Nested Operations (Advanced)

### Handling Complex Multi-Step Workflows

```python
from app.utils.transaction_manager import async_transaction
from sqlalchemy.ext.asyncio import AsyncSession

class ComplexWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def complex_workflow(self, data: dict) -> dict:
        """
        Complex workflow with nested operations.

        Strategy:
        1. Use outer transaction for all database operations
        2. Perform non-database operations outside transaction
        3. Keep transaction scope as small as possible
        """
        # Step 1: Validate data (no transaction needed)
        validated_data = self._validate_data(data)

        # Step 2: External API calls (outside transaction)
        external_result = await self._call_external_api(validated_data)

        # Step 3: Database operations (inside transaction)
        async with async_transaction(self.db):
            # Create primary record
            primary = PrimaryModel(**validated_data)
            self.db.add(primary)
            await self.db.flush()  # Get ID without committing

            # Create related records
            for item in validated_data.get("items", []):
                related = RelatedModel(
                    primary_id=primary.id,
                    **item
                )
                self.db.add(related)

            # Update audit log
            audit = AuditLog(
                entity_type="primary",
                entity_id=primary.id,
                action="created",
                details=external_result
            )
            self.db.add(audit)

            # Transaction auto-commits here (all-or-nothing)

        # Step 4: Post-commit operations
        await self._invalidate_cache(primary.id)
        await self._send_notification(primary)

        return {
            "primary_id": primary.id,
            "status": "success",
            "external_result": external_result
        }
```

## Example 5: Handling Specific Error Types

### Selective Rollback Based on Error Type

```python
from app.utils.transaction_manager import async_transaction
from sqlalchemy.exc import IntegrityError

class SmartTransactionService:
    async def create_with_retry(self, data: dict) -> Model:
        """
        Create with retry on unique constraint violations.

        Uses manual transaction management for fine-grained control.
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                async with async_transaction(self.db):
                    # Generate unique identifier
                    unique_id = self._generate_unique_id(retry_count)

                    model = Model(
                        unique_id=unique_id,
                        **data
                    )
                    self.db.add(model)
                    # Auto-commits on success

                return model

            except IntegrityError as e:
                # Unique constraint violation
                retry_count += 1
                logger.warning(
                    f"Unique constraint violation, retrying ({retry_count}/{max_retries})"
                )

                if retry_count >= max_retries:
                    raise ValueError("Failed to generate unique ID after retries")

                # Continue to next iteration
                continue
```

## Best Practices Summary

### DO ✅

1. **Use transactions for write operations**
   ```python
   async with async_transaction(db):
       db.add(record)
   ```

2. **Keep transaction scope minimal**
   ```python
   # Prepare data outside transaction
   validated_data = validate(data)

   # Only database operations in transaction
   async with async_transaction(db):
       db.add(Model(**validated_data))
   ```

3. **Use decorator for simple service methods**
   ```python
   @with_transaction()
   async def create_record(self, data: dict):
       record = Model(**data)
       self.db.add(record)
       return record
   ```

4. **Batch operations in single transaction**
   ```python
   async with async_transaction(db):
       for item in items:
           db.add(Model(**item))
   ```

### DON'T ❌

1. **Don't include I/O operations in transactions**
   ```python
   # ❌ WRONG
   async with async_transaction(db):
       db.add(record)
       await send_email()  # I/O outside transaction!

   # ✅ CORRECT
   async with async_transaction(db):
       db.add(record)
   await send_email()  # After transaction
   ```

2. **Don't nest transactions unnecessarily**
   ```python
   # ❌ WRONG
   async with async_transaction(db):
       async with async_transaction(db):  # Nested!
           db.add(record)

   # ✅ CORRECT
   async with async_transaction(db):
       db.add(record)
   ```

3. **Don't ignore transaction errors**
   ```python
   # ❌ WRONG
   try:
       async with async_transaction(db):
           db.add(record)
   except Exception:
       pass  # Silently ignoring!

   # ✅ CORRECT
   try:
       async with async_transaction(db):
           db.add(record)
   except Exception as e:
       logger.error(f"Transaction failed: {e}")
       raise
   ```

4. **Don't mix transaction management styles**
   ```python
   # ❌ WRONG
   async with async_transaction(db):
       db.add(record)
       await db.commit()  # Manual commit in auto-commit context!

   # ✅ CORRECT
   async with async_transaction(db, auto_commit=False):
       db.add(record)
       await db.commit()  # Manual commit with auto_commit=False
   ```

## Testing Examples

### Unit Test with Transaction

```python
@pytest.mark.asyncio
async def test_save_summary_with_transaction(mock_db_session):
    """Test summary save uses transaction."""
    service = PatientSummaryService(mock_db_session)
    response = PatientSummaryResponse(...)

    await service._save_summary(response)

    # Verify transaction methods called
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_not_called()

@pytest.mark.asyncio
async def test_save_summary_rolls_back_on_error(mock_db_session):
    """Test summary save rolls back on error."""
    service = PatientSummaryService(mock_db_session)
    response = PatientSummaryResponse(...)

    # Simulate commit failure
    mock_db_session.commit.side_effect = Exception("Commit failed")

    with pytest.raises(Exception):
        await service._save_summary(response)

    # Verify rollback was called
    mock_db_session.rollback.assert_called_once()
```

## Conclusion

Transaction management is critical for:
- **Data consistency**: All-or-nothing guarantees
- **Error handling**: Automatic rollback on failures
- **Code clarity**: Explicit transaction boundaries

Use the provided utilities (`async_transaction`, `sync_transaction`, `with_transaction`) to add robust transaction management to your services.
