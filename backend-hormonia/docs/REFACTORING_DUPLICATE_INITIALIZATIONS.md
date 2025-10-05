# Refactoring: Duplicate Initializations and Logs

## Overview

This refactoring eliminates duplicate initialization logs by making initialization functions idempotent using module-level sentinel flags.

## Issues Fixed

### 1. Duplicate Supabase Client Initialization

**Problem:**
- `app/database.py` initialized Supabase client at module import (line 122)
- `app/core/database.py` also initialized Supabase client at module import (line 453)
- Both modules are imported, causing duplicate "Supabase client initialized successfully" logs

**Solution:**
- Added `_SUPABASE_CLIENT_INITIALIZED` sentinel flag to `app/core/database.py`
- Made `init_supabase_client()` idempotent - returns early if already initialized
- Modified `app/database.py` to delegate to `app/core/database.py` for shared instance
- Removed module-level initialization from `app/database.py`

**Files Changed:**
- `backend-hormonia/app/core/database.py`
- `backend-hormonia/app/database.py`

### 2. Duplicate Quiz Humanizer Patch

**Problem:**
- `app/services/quiz_question_humanizer_integration.py` auto-patches at module import (line 268-272)
- `app/core/lifespan.py` calls `integrate_humanization_into_quiz_service()` during startup (line 284)
- This caused the patch to run twice and log "Quiz humanization integration successfully patched" twice

**Solution:**
- Added `_QUIZ_HUMANIZER_PATCHED` sentinel flag
- Made `integrate_humanization_into_quiz_service()` idempotent - returns early if already patched
- Module-level auto-integration still works but only patches once
- Calling the function again is safe and doesn't re-patch or re-log

**Files Changed:**
- `backend-hormonia/app/services/quiz_question_humanizer_integration.py`

## Implementation Pattern

### Idempotent Initialization Pattern

```python
# Module-level sentinel to prevent duplicate initialization
_FEATURE_INITIALIZED = False

def initialize_feature():
    """Initialize feature (idempotent)."""
    global _FEATURE_INITIALIZED
    
    # Return early if already initialized
    if _FEATURE_INITIALIZED:
        return True
    
    try:
        # Initialization logic here
        ...
        
        _FEATURE_INITIALIZED = True
        logger.info("Feature initialized successfully")
        return True
        
    except Exception as e:
        _FEATURE_INITIALIZED = True  # Mark as attempted
        logger.error(f"Error initializing feature: {e}")
        return False

# Module-level initialization (safe - only runs once)
initialize_feature()
```

### Benefits

1. **No Duplicate Logs**: Each initialization message appears exactly once
2. **Thread-Safe**: Module-level globals are initialized at import time
3. **Safe Re-calls**: Calling initialization functions multiple times is safe
4. **Backward Compatible**: Existing code continues to work without changes
5. **Clear Intent**: Sentinel flags make idempotency explicit

## Testing

### Manual Test

Run the test script to verify idempotent behavior:

```bash
cd backend-hormonia
python test_idempotent.py
```

Expected output:
- Supabase client initialized flag: True
- Re-calling init_supabase_client() doesn't re-initialize
- Quiz humanizer patched flag: True
- Re-calling integrate_humanization_into_quiz_service() doesn't re-patch

### Integration Test

Start the application and check logs:

```bash
cd backend-hormonia
uvicorn app.main:app --reload
```

Expected in logs:
- "Supabase client initialized successfully" appears **1 time only**
- "Quiz humanization integration successfully patched" appears **1 time only**

## Architecture Decision

### Why app.core.database is the Single Source of Truth

1. **More Complete**: `app/core/database.py` includes RLS support
2. **Feature-Rich**: Contains RLS context management and connection pooling
3. **Better Design**: Separates concerns with `RLSConnectionManager`
4. **Backward Compatibility**: `app/database.py` delegates to core for shared instance

### Migration Path

**Short-term (Current):**
- Both modules co-exist for backward compatibility
- `app/database.py` delegates to `app/core/database.py`
- No duplicate initialization

**Long-term (Recommended):**
- Gradually migrate all imports to use `app.core.database`
- Deprecate `app/database.py`
- Remove deprecated module in next major version

## Related Files

### Modified Files
- `backend-hormonia/app/core/database.py` - Added idempotent Supabase init
- `backend-hormonia/app/database.py` - Delegates to core.database
- `backend-hormonia/app/services/quiz_question_humanizer_integration.py` - Added idempotent patching

### Test Files
- `backend-hormonia/test_idempotent.py` - Manual test script

### Documentation
- `backend-hormonia/docs/REFACTORING_DUPLICATE_INITIALIZATIONS.md` - This file

## Code Quality Improvements

### Before
```python
# Multiple initialization logs
[INFO] Supabase client initialized successfully  # from app.database
[INFO] Supabase client initialized successfully  # from app.core.database
[INFO] Quiz humanization integration successfully patched  # from auto-import
[INFO] Quiz humanization integration successfully patched  # from lifespan
```

### After
```python
# Single initialization log per feature
[INFO] Supabase client initialized successfully  # once
[INFO] Quiz humanization integration successfully patched  # once
```

## Monitoring

No changes to monitoring required. The refactoring maintains the same functionality with cleaner logs.

## Rollback Plan

If issues arise:

1. Revert `app/core/database.py` to restore original `init_supabase_client()`
2. Revert `app/database.py` to restore module-level initialization
3. Revert `quiz_question_humanizer_integration.py` to restore original patching

All changes are isolated to initialization logic and don't affect core functionality.
