# Detailed Usage Point Analysis

## 1. Patient Service (app/services/patient.py)

### Current Implementation (Lines 223-231)

```python
# Patient onboarding flow initialization
flow_engine = FlowEngine(db)

# Determine appropriate flow type based on patient metadata
flow_type = self._determine_patient_flow_type(patient)

# Start the flow
try:
    flow_state = flow_engine.start_flow(
        patient_id=patient.id,
        flow_type=flow_type,
        initial_data={
            "onboarding_source": "patient_service",
            "treatment_type": patient.treatment_type
        }
    )
except Exception as e:
    logger.error(f"Failed to start flow for patient {patient.id}: {e}")
    raise
```

### Migration Target

```python
# Use adapter for backward compatibility
flow_engine = FlowEngineAdapter(db)  # ← Only line that changes!

# Everything else stays the same
flow_type = self._determine_patient_flow_type(patient)

try:
    flow_state = flow_engine.start_flow(
        patient_id=patient.id,
        flow_type=flow_type,
        initial_data={
            "onboarding_source": "patient_service",
            "treatment_type": patient.treatment_type
        }
    )
except Exception as e:
    logger.error(f"Failed to start flow for patient {patient.id}: {e}")
    raise
```

### Test Impact
- Existing tests continue to work (same interface)
- Add new tests for AI personalization
- Verify message scheduling uses MessageScheduler

---

## 2. Webhook Processor (app/services/webhook_processor.py)

### Current Implementation (Lines 256-274)

```python
async def _handle_flow_message(
    self,
    patient: Patient,
    message: Message,
    flow_state: PatientFlowState
) -> None:
    """Process message within active flow context."""
    try:
        # Calculate current day
        current_day = await self.enhanced_flow_engine.calculate_patient_day(patient.id)

        # Process response through enhanced flow engine
        response = await self.enhanced_flow_engine.process_patient_response(
            patient_id=patient.id,
            response_text=message.content,
            current_day=current_day
        )

        if response.get("should_advance"):
            # USES LEGACY FlowEngine!
            advancement = await self.flow_engine.advance_flow(
                patient_id=patient.id,
                additional_context={"patient_response": message.content}
            )
            logger.info(f"Flow advanced for patient {patient.id}: {advancement}")

        # Generate and send response
        if response.get("ai_response"):
            await self._send_response(
                patient_id=patient.id,
                content=response["ai_response"],
                metadata={
                    "context": "flow",
                    "flow_state_id": str(flow_state.id),
                    "current_day": current_day,
                    "response_to": str(message.id)
                }
            )
    except Exception as e:
        logger.error(f"Error handling flow message: {e}", exc_info=True)
```

### Migration Target

```python
async def _handle_flow_message(
    self,
    patient: Patient,
    message: Message,
    flow_state: PatientFlowState
) -> None:
    """Process message within active flow context."""
    try:
        # Calculate current day
        current_day = await self.enhanced_flow_engine.calculate_patient_day(patient.id)

        # Process response through enhanced flow engine
        response = await self.enhanced_flow_engine.process_patient_response(
            patient_id=patient.id,
            response_text=message.content,
            current_day=current_day
        )

        if response.get("should_advance"):
            # USE ENHANCED ENGINE DIRECTLY (already available!)
            advancement = await self.enhanced_flow_engine.advance_patient_flow(
                patient_id=patient.id,
                force_day=None  # Let engine calculate
            )
            logger.info(f"Flow advanced for patient {patient.id}: {advancement}")

        # Generate and send response
        if response.get("ai_response"):
            await self._send_response(
                patient_id=patient.id,
                content=response["ai_response"],
                metadata={
                    "context": "flow",
                    "flow_state_id": str(flow_state.id),
                    "current_day": current_day,
                    "response_to": str(message.id)
                }
            )
    except Exception as e:
        logger.error(f"Error handling flow message: {e}", exc_info=True)
```

### Analysis
- **Already has EnhancedFlowEngine** (line 62)
- **Also has legacy FlowEngine** (line 61) ← REDUNDANT!
- Can directly use `self.enhanced_flow_engine.advance_patient_flow()`
- No need for adapter here, just use existing instance

### Migration Steps
1. Remove `self.flow_engine = FlowEngine(db)` (line 61)
2. Replace `self.flow_engine.advance_flow()` with `self.enhanced_flow_engine.advance_patient_flow()`
3. Update tests to verify new method is used

---

## 3. Celery Tasks (app/tasks/flow_automation.py)

### Current Implementation (Lines 58, 214)

```python
@celery_app.task(name="auto_enroll_patients", bind=True, max_retries=3)
def auto_enroll_patients_task(self):
    """Auto-enroll patients who need flows."""
    try:
        with get_db_context() as db:
            # Get patients without active flows
            patients_without_flow = db.execute(
                text("""
                    SELECT p.id, p.name, p.treatment_type
                    FROM patients p
                    LEFT JOIN patient_flow_states pfs ON p.id = pfs.patient_id
                    WHERE pfs.id IS NULL AND p.flow_state = 'ACTIVE'
                """)
            ).fetchall()

            logger.info(f"Found {len(patients_without_flow)} patients without active flows")

            # LEGACY FlowEngine instantiation
            flow_engine = FlowEngine()  # ← No db session passed!
            patient_service = PatientService(db)

            for patient_row in patients_without_flow:
                try:
                    patient_id = patient_row.id
                    flow_type = _determine_flow_type(patient_row.treatment_type)

                    # Start flow
                    flow_engine.start_flow(patient_id, flow_type)
                    logger.info(f"Auto-enrolled patient {patient_id} in flow {flow_type}")

                except Exception as e:
                    logger.error(f"Failed to enroll patient {patient_row.id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Auto-enrollment task failed: {e}")
        raise self.retry(exc=e, countdown=300)
```

### Migration Target

```python
@celery_app.task(name="auto_enroll_patients", bind=True, max_retries=3)
def auto_enroll_patients_task(self):
    """Auto-enroll patients who need flows."""
    try:
        with get_db_context() as db:
            # Get patients without active flows
            patients_without_flow = db.execute(
                text("""
                    SELECT p.id, p.name, p.treatment_type
                    FROM patients p
                    LEFT JOIN patient_flow_states pfs ON p.id = pfs.patient_id
                    WHERE pfs.id IS NULL AND p.flow_state = 'ACTIVE'
                """)
            ).fetchall()

            logger.info(f"Found {len(patients_without_flow)} patients without active flows")

            # USE ADAPTER with proper db session
            flow_engine = FlowEngineAdapter(db)
            patient_service = PatientService(db)

            for patient_row in patients_without_flow:
                try:
                    patient_id = patient_row.id
                    flow_type = _determine_flow_type(patient_row.treatment_type)

                    # Start flow (same interface)
                    flow_engine.start_flow(patient_id, flow_type)
                    logger.info(f"Auto-enrolled patient {patient_id} in flow {flow_type}")

                except Exception as e:
                    logger.error(f"Failed to enroll patient {patient_row.id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Auto-enrollment task failed: {e}")
        raise self.retry(exc=e, countdown=300)
```

### Critical Issue Found
**Line 58**: `flow_engine = FlowEngine()` **with NO db session!**

This is a **bug** in current code. FlowEngine requires db session but tasks don't pass it.

**Fix Required**:
1. Update to `FlowEngineAdapter(db)` - passes session correctly
2. Add validation to adapter to ensure db is not None
3. Add test to catch this pattern

---

## 4. Service Provider (app/services.py)

### Current Implementation (Line 209)

```python
class ServiceProvider:
    """Central service provider using dependency injection."""

    def __init__(self, db: Session):
        self.db = db
        self._flow_engine = None
        # ... other services

    @property
    def flow_engine(self) -> FlowEngine:
        if self._flow_engine is None:
            # FlowEngine needs db
            self._flow_engine = FlowEngine(self.db)
        return self._flow_engine
```

### Migration Target

```python
class ServiceProvider:
    """Central service provider using dependency injection."""

    def __init__(self, db: Session):
        self.db = db
        self._flow_engine = None
        # ... other services

    @property
    def flow_engine(self) -> FlowEngineAdapter:
        """Legacy flow engine (via adapter for backward compatibility)."""
        if self._flow_engine is None:
            # Use adapter to route to new service
            self._flow_engine = FlowEngineAdapter(self.db)
        return self._flow_engine

    @property
    def flow_service(self) -> FlowEngineIntegrationService:
        """New flow service (recommended for new code)."""
        # Existing property, no changes needed
        return self._flow_service
```

### Changes
1. Update `flow_engine` property to return `FlowEngineAdapter`
2. Add type hint: `FlowEngineAdapter` instead of `FlowEngine`
3. Keep existing `flow_service` property unchanged (already correct)

---

## 5. Thread-Safe Services (app/thread_safe_services.py)

### Current Implementation (Lines 225-232)

```python
@property
def flow_engine(self) -> FlowEngine:
    """Create FlowEngine with proper session management."""
    try:
        # Try new constructor pattern
        return FlowEngine(db_session_factory=self.db_session_factory)
    except TypeError:
        # Fallback to original constructor
        with self.get_db_session() as session:
            return FlowEngine(db=session)
```

### Migration Target

```python
@property
def flow_engine(self) -> FlowEngineAdapter:
    """Create FlowEngine adapter with proper session management."""
    # Adapter always uses db parameter (no factory pattern)
    with self.get_db_session() as session:
        return FlowEngineAdapter(db=session)
```

### Changes
1. Remove factory pattern fallback (adapter doesn't support it)
2. Always use `db=session` parameter
3. Return `FlowEngineAdapter` type
4. Simplify logic (no try/except needed)

---

## Summary of Changes

| File | Lines | Change Type | Complexity |
|------|-------|-------------|------------|
| `patient.py` | 223-231 | Replace import + instantiation | Low |
| `webhook_processor.py` | 61, 267 | Remove legacy engine, use existing enhanced | Low |
| `flow_automation.py` | 58, 214 | Add db session, use adapter | Medium (bug fix) |
| `services.py` | 209 | Update property type + instantiation | Low |
| `thread_safe_services.py` | 225-232 | Simplify to adapter | Low |

**Total Files**: 5
**Total Lines Modified**: ~15-20
**Estimated Effort**: 4-6 hours including tests
