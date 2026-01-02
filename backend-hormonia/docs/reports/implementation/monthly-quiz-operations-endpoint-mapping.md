# Monthly Quiz Operations - Endpoint Mapping

## Module Breakdown

### 📊 crud.py (2 endpoints)

#### 1. GET /monthly/{quiz_id}/responses
- **Function:** `get_monthly_quiz_responses()`
- **Line Count:** ~100 lines
- **Purpose:** Retrieve all responses for a monthly quiz with pagination
- **Auth:** RBAC - Doctor/Admin
- **Features:**
  - Cursor-based pagination
  - Response enrichment (template + session data)
  - Doctor scope filtering
- **Cache:** 5 minutes TTL

#### 2. GET /monthly/{quiz_id}/statistics
- **Function:** `get_monthly_quiz_statistics()`
- **Line Count:** ~90 lines
- **Purpose:** Get comprehensive quiz statistics
- **Auth:** RBAC - Doctor/Admin
- **Features:**
  - Completion rates
  - Average scores
  - Completion time analytics
  - Daily response distribution
- **Cache:** 2 minutes TTL

---

### 📅 scheduling.py (4 endpoints)

#### 1. POST /monthly/{quiz_id}/reminder
- **Function:** `send_monthly_quiz_reminder()`
- **Line Count:** ~95 lines
- **Purpose:** Send reminders to patients who haven't completed
- **Auth:** RBAC - Admin only
- **Features:**
  - Max 3 reminders per quiz
  - Tracks reminder history
  - Identifies non-completers
  - Multiple delivery methods
- **Rate Limit:** 20/minute

#### 2. GET /monthly/schedule
- **Function:** `get_quiz_schedule()`
- **Line Count:** ~60 lines
- **Purpose:** View schedule of upcoming/past monthly quizzes
- **Auth:** RBAC - Doctor/Admin
- **Features:**
  - Date range filtering
  - Scheduled quiz management
  - Status tracking
- **Cache:** 5 minutes TTL

#### 3. POST /monthly/generate
- **Function:** `generate_monthly_quiz()`
- **Line Count:** ~100 lines
- **Purpose:** Auto-generate monthly quiz from template
- **Auth:** RBAC - Admin only
- **Features:**
  - Automatic naming (Template - Month Year)
  - Scheduled date setup (1st of month)
  - Auto-publish option
  - Tag system for metadata
- **Rate Limit:** 10/minute

#### 4. GET /monthly/templates
- **Function:** `list_quiz_templates()`
- **Line Count:** ~65 lines
- **Purpose:** List available quiz templates
- **Auth:** RBAC - Doctor/Admin
- **Features:**
  - Template metadata
  - Question counts
  - Duration estimation
  - Active templates only
- **Cache:** 30 minutes TTL

---

### 🌐 public.py (3 endpoints)

#### 1. GET /monthly/public/current
- **Function:** `get_current_public_quiz()`
- **Line Count:** ~130 lines
- **Purpose:** Get current monthly quiz (PUBLIC - no auth)
- **Auth:** Token-based (base64-encoded JWT-like)
- **Features:**
  - Token validation & expiry
  - IP logging
  - Question sanitization (removes scoring)
  - Session management
  - Access tracking
- **Rate Limit:** 20/minute
- **Security:**
  - Token type validation
  - Quiz status verification
  - Expiry checking

#### 2. POST /monthly/public/{quiz_id}/submit
- **Function:** `submit_public_quiz_response()`
- **Line Count:** ~165 lines
- **Purpose:** Submit quiz response publicly
- **Auth:** Token-based
- **Features:**
  - Token-quiz ID matching
  - Response recording
  - Auto-completion detection
  - Progress tracking
  - Statistics update
- **Rate Limit:** 20/minute

#### 3. GET /monthly/public/{quiz_id}/results
- **Function:** `get_public_quiz_results()`
- **Line Count:** ~130 lines
- **Purpose:** View aggregate quiz results (PUBLIC)
- **Auth:** None required
- **Features:**
  - Privacy-first (aggregate data only)
  - Response distribution analysis
  - Score averaging
  - Completion rate calculation
  - Question-level statistics
- **Rate Limit:** 20/minute
- **Cache:** 15 minutes TTL

---

### 🏥 health.py (1 endpoint)

#### 1. GET /health
- **Function:** `health_check()`
- **Line Count:** ~15 lines
- **Purpose:** Service health monitoring
- **Auth:** None required
- **Features:**
  - Service status
  - Version info
  - Endpoint counts
  - Feature flags

---

## Route Tags (for OpenAPI/Swagger)

```python
# crud.py routes
tags=["Monthly Quiz - CRUD"]

# scheduling.py routes
tags=["Monthly Quiz - Scheduling"]

# public.py routes
tags=["Monthly Quiz - Public Access"]

# health.py routes
tags=["Monthly Quiz - Health"]
```

---

## Authentication Matrix

| Endpoint | Auth Required | Role | Rate Limit |
|----------|--------------|------|------------|
| GET /monthly/{quiz_id}/responses | ✅ Yes | Doctor/Admin | 50/min |
| GET /monthly/{quiz_id}/statistics | ✅ Yes | Doctor/Admin | 30/min |
| POST /monthly/{quiz_id}/reminder | ✅ Yes | Admin | 20/min |
| GET /monthly/schedule | ✅ Yes | Doctor/Admin | 50/min |
| POST /monthly/generate | ✅ Yes | Admin | 10/min |
| GET /monthly/templates | ✅ Yes | Doctor/Admin | 50/min |
| GET /monthly/public/current | 🔓 Token | Public | 20/min |
| POST /monthly/public/{quiz_id}/submit | 🔓 Token | Public | 20/min |
| GET /monthly/public/{quiz_id}/results | 🔓 None | Public | 20/min |
| GET /health | 🔓 None | Public | No limit |

---

## Cache Strategy

| Endpoint | TTL | Key Pattern |
|----------|-----|-------------|
| GET responses | 5 min | N/A (cursor-based) |
| GET statistics | 2 min | `monthly_quiz_stats:{quiz_id}` |
| GET schedule | 5 min | N/A (dynamic) |
| GET templates | 30 min | `quiz_templates_list` |
| GET public/current | N/A | Dynamic session |
| GET public/results | 15 min | `public_quiz_results:{quiz_id}` |

---

## Dependencies Tree

```
_shared.py (foundation)
├── Common imports
│   ├── FastAPI (APIRouter, Request, Depends, etc.)
│   ├── SQLAlchemy (models, queries)
│   ├── Pydantic (schemas)
│   └── Python stdlib (datetime, UUID, logging, etc.)
├── Database dependencies
│   ├── get_db()
│   └── Database models
├── Auth dependencies
│   ├── get_current_user_simple()
│   └── get_redis_cache()
├── Utilities
│   ├── Rate limiter
│   ├── Pagination helpers
│   └── Cache TTL constants
└── Constants
    └── PUBLIC_PATIENT_ID

crud.py
├── Imports from _shared
└── 2 route handlers

scheduling.py
├── Imports from _shared
└── 4 route handlers

public.py
├── Imports from _shared
├── Additional: base64, json
└── 3 route handlers

health.py
├── Minimal imports
└── 1 route handler

__init__.py (aggregator)
├── Imports all sub-routers
├── Creates main APIRouter
├── Includes all sub-routers
└── Exports main router
```

---

## Request/Response Flow

### Example: Get Quiz Statistics

```
Client Request
    ↓
FastAPI Router (main app)
    ↓
monthly_quiz_operations package
    ↓
__init__.py (main router)
    ↓
crud.py (crud_router)
    ↓
get_monthly_quiz_statistics()
    ↓
1. Rate limiter check (30/min)
2. Auth check (Doctor/Admin)
3. Redis cache check
4. Database queries
5. Statistics calculation
6. Cache result
7. Return response
    ↓
Client Response
```

---

## File Size Comparison

### Before (Single File)
```
monthly_quiz_operations.py: 1,110 lines
Total: 1,110 lines
```

### After (Package)
```
__init__.py:      61 lines
_shared.py:       50 lines
crud.py:         227 lines
scheduling.py:   364 lines
public.py:       455 lines
health.py:        35 lines
────────────────────────
Total:         1,192 lines
Overhead:        +82 lines (7.4%)
```

**Largest Module:** public.py (455 lines)
**Smallest Module:** health.py (35 lines)
**Average Module Size:** 238 lines

---

## Import Patterns

### Old Way (Single File)
```python
from app.api.v2.routers.monthly_quiz_operations import router
app.include_router(router, prefix="/api/v2/quiz")
```

### New Way (Package) - Same!
```python
from app.api.v2.routers.monthly_quiz_operations import router
app.include_router(router, prefix="/api/v2/quiz")
```

### Alternative (Sub-routers)
```python
# If needed for specific use cases
from app.api.v2.routers.monthly_quiz_operations import (
    crud_router,
    scheduling_router,
    public_router,
    health_router
)

# Include individually with different prefixes if needed
app.include_router(crud_router, prefix="/api/v2/quiz")
app.include_router(public_router, prefix="/api/v2/public-quiz")
```

---

## Testing Strategy

### Unit Tests (by module)
```
tests/routers/monthly_quiz_operations/
├── test_crud.py           # Test crud endpoints
├── test_scheduling.py     # Test scheduling endpoints
├── test_public.py         # Test public endpoints
└── test_health.py         # Test health endpoint
```

### Integration Tests
```
tests/integration/
└── test_monthly_quiz_flow.py  # End-to-end quiz workflow
```

---

## Performance Impact

**Before:**
- Single large file loaded
- All routes in memory
- FastAPI router initialization: ~same

**After:**
- 6 smaller files loaded
- All routes in memory (same)
- FastAPI router initialization: ~same

**Conclusion:** No performance impact. FastAPI loads all routes at startup regardless of file organization.

---

## Maintenance Benefits

1. **Easier Bug Fixes**: Locate issues faster by module
2. **Cleaner Git Diffs**: Changes isolated to specific modules
3. **Better Code Review**: Smaller, focused PRs
4. **Team Collaboration**: Multiple developers can work on different modules
5. **Clear Ownership**: Each module has clear responsibility
6. **Scalability**: Easy to add new endpoints or split further

---

**Last Updated:** 2025-11-24
**Status:** ✅ Refactoring Complete
