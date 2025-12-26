# ⚡ QUICK FIX GUIDE - Unblock All Tests (5 minutes)

## 🎯 Problem
**ALL 284 tests are blocked** by circular import error:
```
AttributeError: module 'app.config.settings' has no attribute 'APP_ENABLE_DEBUG'
```

## ✅ Solution (2 lines of code)

### Step 1: Edit File
```bash
# Open the file
nano /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia/app/utils/database_optimization.py
```

### Step 2: Find Lines 182-183
Look for:
```python
    "echo": settings.APP_ENABLE_DEBUG,
    "echo_pool": settings.APP_ENABLE_DEBUG,
```

### Step 3: Replace With
```python
    "echo": os.getenv("APP_ENABLE_DEBUG", "false").lower() in ("true", "1", "yes"),
    "echo_pool": os.getenv("APP_ENABLE_DEBUG", "false").lower() in ("true", "1", "yes"),
```

### Step 4: Add Import (if missing)
At the top of the file, ensure you have:
```python
import os
```

### Step 5: Verify
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia

# Test 1: Settings import
python3 -c "from app.config import settings; print('✅ Settings OK')"

# Test 2: Base import (was failing)
python3 -c "from app.db.base import Base; print('✅ Base OK')"

# Test 3: Collect tests
python3 -m pytest tests/ --collect-only 2>&1 | head -20
```

### Expected Output
```
collected 245 items
✅ Tests unblocked!
```

## 📋 Complete Fix (Copy-Paste Ready)

Replace the entire `default_settings` dictionary (around line 175) with:

```python
    # Read debug setting directly from environment to avoid circular imports
    # (settings.APP_ENABLE_DEBUG causes circular dependency during module initialization)
    debug_mode = os.getenv("APP_ENABLE_DEBUG", "false").lower() in ("true", "1", "yes", "on")

    default_settings = {
        "poolclass": QueuePool,
        "pool_size": 20,
        "max_overflow": 30,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_timeout": 30,
        "echo": debug_mode,
        "echo_pool": debug_mode,
    }
```

## 🚀 After Fix
Run tests:
```bash
# Run all tests
python3 -m pytest tests/ -v

# Or run specific category
python3 -m pytest tests/api/v2/ -v

# Or run one file
python3 -m pytest tests/api/v2/test_health.py -v
```

---

**Time**: 5 minutes
**Risk**: Low
**Impact**: Unblocks 284 test files
