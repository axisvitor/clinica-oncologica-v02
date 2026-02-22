# Coding Conventions

**Analysis Date:** 2026-02-22

## Naming Patterns

**Files:**
- snake_case for all Python modules: `flow_service.py`, `audit_repository.py`, `csrf_tokens.py`
- Packages use snake_case directories with `__init__.py`
- Test files prefixed with `test_`: `test_auth_dependencies.py`, `test_patients.py`
- Shim/compatibility wrappers: thin `*.py` at old location re-exports from new canonical location

**Classes:**
- PascalCase: `FlowManager`, `AlertManager`, `SagaOrchestrator`, `BaseRepository`
- Test classes prefixed `Test`: `TestPatientsV2`, `TestPatientOnboardingSaga`
- Pydantic schemas suffixed with purpose: `FlowTemplateV2Base`, `FlowStateV2Response`, `AuditEventContext`
- Enums: PascalCase class, UPPER_SNAKE_VALUE: `class FlowState(enum.Enum): ONBOARDING = "onboarding"`

**Functions and Methods:**
- snake_case for all: `get_flow_service_dependency`, `validate_patient_access`, `now_sao_paulo`
- Private helpers prefixed with `_`: `_coerce_uuid`, `_normalize_template_metadata`, `_serialize_session`
- Async functions declared `async def` throughout; sync helpers are plain `def`
- Factory/getter functions: `get_<service>()` pattern for dependency injection (e.g., `get_flow_dashboard_service`)

**Variables:**
- snake_case: `patient_id`, `firebase_uid`, `flow_state`
- Module-level constants: UPPER_SNAKE_CASE: `FLOW_SERVICE_TIMEOUT_SECONDS = 15.0`, `SAFE_METHODS = frozenset(...)`
- Type aliases: PascalCase: `ModelType = TypeVar("ModelType", bound=BaseModel)`

**Types:**
- TypeVar bound to base class: `ModelType = TypeVar("ModelType", bound=BaseModel)`
- `Optional[X]` used throughout (not `X | None` style)
- `from typing import ...` explicit imports; `from __future__ import annotations` used in 221+ files for deferred evaluation

## Code Style

**Formatting:**
- Tool: Black
- Line length: 120 characters
- Target: Python 3.13 (`target-version = ['py313']`)
- Trailing commas enforced in multi-line structures

**Linting:**
- Tool: Ruff (pyflakes rules only - `select = ["F"]`)
- `isort` profile `"black"` for import sorting: multi-line output 3, trailing commas, parentheses
- Bandit for security scanning (skips B101 assert, B601 shell injection)
- `**/__init__.py` files are exempt from F401 (unused import) - intentional re-export pattern

## Import Organization

**Order (enforced by isort with black profile):**
1. Standard library (`import os`, `import logging`, `from datetime import datetime`)
2. Third-party packages (`from fastapi import ...`, `from sqlalchemy import ...`, `from pydantic import ...`)
3. Local application (`from app.models...`, `from app.services...`)

**Explicit grouping comment style (used in complex modules):**
```python
# Standard library imports
import logging
from typing import Any, Dict, Optional

# Local application imports
from app.repositories.flow import FlowStateRepository
from app.utils.timezone import now_sao_paulo
```

**Path Aliases:**
- None configured. All imports use full `app.*` paths.
- Relative imports used within packages (e.g., `from .core.manager import FlowManager`)
- `from __future__ import annotations` placed first before all other imports

**Avoiding Circular Imports:**
- `if TYPE_CHECKING:` guard used for type-only imports
- Comment pattern: `# Avoid circular import: X not imported at module level`
- Deferred imports inside functions (especially in conftest.py)

## Error Handling

**Application Exception Hierarchy:**
```python
HormoniaException (root, in app.core.exceptions)
  APIException (HTTP-aware, has status_code)
    NotFoundError
    ValidationError
    AuthenticationError
    AuthorizationError
    ConflictError
```

**In Services:**
- Raise domain exceptions (`NotFoundError`, `ValidationError`) not `HTTPException`
- `try/except Exception as e:` followed by re-raise or event broadcast:
```python
try:
    context, step_result = await self.engine.execute_step(context, step_definition)
    await self._broadcast_event(FlowEvent(..., event_type=FlowEventType.STEP_COMPLETED, ...))
except Exception as e:
    await self._broadcast_event(FlowEvent(..., event_type=FlowEventType.STEP_FAILED, data={"error": str(e)}))
    raise
```

**In Routers (FastAPI):**
- Raise `HTTPException` directly with `status_code` and `detail`:
```python
raise HTTPException(status_code=404, detail="Template not found")
raise HTTPException(status_code=409, detail="Version already exists")
raise HTTPException(status_code=422, detail=exc.errors()) from exc
```

**Global Exception Handlers:**
- Registered in `app/core/exception_handlers.py`
- `HormoniaException` → 500 via `hormonia_exception_handler`
- `APIException` → specific code via `api_exception_handler`
- `RequestValidationError` → 422 with structured field errors via `validation_exception_handler`

## Logging

**Framework:** Python standard `logging` module.

**Initialization Pattern (module-level):**
```python
logger = logging.getLogger(__name__)
```
Used in every module that logs. Module name becomes the logger hierarchy.

**Patterns:**
- `logger.info(f"...")` for operational events
- `logger.error(f"...")` for caught exceptions (often with the exception variable)
- `logger.warning(f"...")` for degraded-but-handled conditions
- `logger.debug(f"...")` for detailed trace information
- f-strings used universally for message formatting

## Comments

**Module Docstrings:**
Every module has a top-level docstring explaining purpose, architecture notes, and sometimes usage examples:
```python
"""
Flow Manager - Main orchestrator for Flow Services (QW-021).

This module implements the FlowManager class...

Usage:
    >>> manager = FlowManager(db)
    >>> flow_id = await manager.start_flow(...)
"""
```

**Class Docstrings:**
- All public classes have docstrings
- Constructor parameters documented in `Args:` section (Google style)
- Important attributes listed in `Attributes:` section for complex classes

**Inline Comments:**
- Section separators with `# ===...===` or `# ---...---` used to organize large files
- `# PERFORMANCE:`, `# LGPD:`, `# TODO(async-migration):` prefixed comments mark specific concerns
- `# noqa: F401` on intentional re-exports in `__init__.py` files

## Function Design

**Size:**
- Service methods generally 20-80 lines; longer methods exist (router handlers up to ~100 lines)
- Large routers (`flows.py` at 1120 lines) organize via grouping, not splitting

**Parameters:**
- Dependency injection via `Depends(...)` for FastAPI endpoints
- Optional dependencies via `Optional[Type] = None` in `__init__` for testability:
```python
def __init__(
    self,
    db: Any,
    engine: Optional[FlowEngine] = None,
    validator: Optional[FlowValidator] = None,
    ...
):
```
- Private helper functions prefixed `_` for internal use only

**Return Values:**
- `Optional[ModelType]` for repository lookups that may not find a record
- Pydantic response models for router handlers (`FlowStateV2Response`, etc.)
- `None` or specific sentinel for cache misses

## Module Design

**Exports:**
- `__all__` defined in package `__init__.py` files to declare public API
- All public re-exports use explicit imports: `from .orchestrator import SagaOrchestrator`

**Barrel/Package Files (`__init__.py`):**
- Packages expose canonical public API through `__init__.py`
- `# noqa: F401` used on re-export lines in `__init__.py`
- Shim pattern: old module paths kept as thin wrappers:
```python
# Compatibility wrapper. Implementation lives in app.services.flow.core.manager.
from .core.manager import FlowManager
__all__ = ["FlowManager"]
```

**Tombstone Pattern (dead code):**
- Dead files replaced with module docstring + `raise ImportError(...)` to fail fast at import time
- Tombstoned files are never deleted to preserve git history

**Soft-Delete Pattern:**
- Models use `deleted_at` column (nullable DateTime); queries filter `deleted_at.is_(None)`

---

*Convention analysis: 2026-02-22*
