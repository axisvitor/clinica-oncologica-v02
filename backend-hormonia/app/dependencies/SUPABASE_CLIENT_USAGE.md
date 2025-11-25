# Database Client Usage Documentation

**Purpose:** DATA LAYER via SQLAlchemy + Amazon RDS PostgreSQL
**Status:** MIGRATED from Supabase to Amazon RDS (2025-10)
**Last Updated:** 2025-11-25

---

## Architecture Overview

**Current Database Stack:**
- **Database:** Amazon RDS PostgreSQL 14+ (sa-east-1 region)
- **ORM:** SQLAlchemy 2.0+ with async support
- **Migrations:** Alembic (22 migrations: 001-021)
- **Authentication:** Firebase Admin SDK (NOT database auth)
- **Cache:** Redis Cloud (required)

---

## Migration History

### Supabase (DEPRECATED - Pre October 2025)
The project originally used Supabase for:
- PostgreSQL database access
- Real-time subscriptions (if enabled)

### Amazon RDS (CURRENT - October 2025+)
Migrated to Amazon RDS for:
- Better performance and control
- Regional compliance (sa-east-1 - Brazil)
- Custom PostgreSQL configuration
- Direct SQLAlchemy integration

---

## Database Access Pattern

### Current Implementation (SQLAlchemy)

```python
from app.dependencies import get_db
from sqlalchemy.orm import Session

@router.get("/data")
async def get_data(db: Session = Depends(get_db)):
    # Use SQLAlchemy ORM
    result = db.query(Patient).filter(Patient.is_active == True).all()
    return result
```

### Thread-Safe Service Provider (Recommended)

```python
from app.dependencies import get_thread_safe_service_provider
from app.services import ServiceProvider

@router.get("/patients")
async def get_patients(services: ServiceProvider = Depends(get_thread_safe_service_provider)):
    # Services use isolated per-request sessions
    return await services.patient_service.list_all()
```

---

## Authentication Flow (Correct)

```
+----------+      +----------+      +----------+      +------------+
| Frontend |      | Firebase |      | Backend  |      | Amazon RDS |
| (React)  |--1-->|   Auth   |--2-->|   API    |--3-->| PostgreSQL |
+----------+      +----------+      +----------+      +------------+
```

1. **Frontend** authenticates via Firebase
2. **Backend** validates Firebase token (Firebase Admin SDK)
3. **Backend** queries PostgreSQL via SQLAlchemy

---

## Removed Dependencies

### DO NOT use these (Supabase remnants):

```python
# REMOVED - Do not import or use
# get_supabase_client - REMOVED (migrated to AWS RDS PostgreSQL)
# supabase.table(...) - Use SQLAlchemy instead
# supabase.auth.* - Use Firebase dependencies
```

### CORRECT - Use these instead:

```python
# Database access
from app.dependencies import get_db, get_thread_safe_service_provider

# Authentication
from app.dependencies import get_current_user, get_admin_user, get_doctor_user
```

---

## Dependency Exports

### From `app/dependencies/__init__.py`

**Database-related exports:**
- `get_db` - SQLAlchemy session (per-request)
- `get_database` - Alias for get_db
- `get_thread_safe_service_provider` - Service provider with isolated session

**Firebase-related exports:**
- `get_current_user` - Uses Firebase token validation
- `get_current_active_user` - Uses Firebase token validation
- `get_admin_user` - Uses Firebase token validation
- `get_doctor_user` - Uses Firebase token validation

---

## Configuration

### Backend Environment Variables

**Database (Amazon RDS):**
```env
DATABASE_URL=postgresql://user:password@rds-instance.sa-east-1.rds.amazonaws.com:5432/hormonia
DATABASE_ECHO=false
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

**Firebase (Authentication):**
```env
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@...
```

**Redis (Cache):**
```env
REDIS_URL=redis://your-redis-cloud-instance:6379
```

---

## Architecture Summary

```
Authentication: Firebase Admin SDK (PRIMARY)
Database: Amazon RDS PostgreSQL (SQLAlchemy ORM)
Cache: Redis Cloud (REQUIRED)
Migrations: Alembic (22 versions)
```

---

## Related Documentation

- [database/README.md](../../docs/database/README.md) - Database schema documentation
- [database/reference/SCHEMA_DOCUMENTATION.md](../../docs/database/reference/SCHEMA_DOCUMENTATION.md) - Table reference
- [SERVICE_DI_REFACTOR.md](../../docs/deployment/SERVICE_DI_REFACTOR.md) - Dependency injection refactor

---

## Summary

**Key Takeaway:** All database access uses SQLAlchemy + Amazon RDS. Supabase client has been completely removed. Authentication uses Firebase Admin SDK.

**If you need:**
- Authentication -> Use Firebase dependencies (`get_current_user`)
- Database access -> Use `get_db()` or `get_thread_safe_service_provider()`
- Cache -> Use Redis via ServiceProvider

---

Generated: 2025-11-25
