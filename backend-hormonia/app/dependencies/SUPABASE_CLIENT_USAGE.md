# Supabase Client Usage Documentation

**Purpose:** DATA LAYER ONLY (Not Authentication)
**Status:** Active for database access
**Last Updated:** 2025-10-01

---

## ⚠️ Critical Clarification

**Supabase in this project is used ONLY for:**
- ✅ PostgreSQL database access
- ✅ Real-time subscriptions (if enabled)
- ✅ Data layer operations

**Supabase is NOT used for:**
- ❌ Authentication (Firebase handles this)
- ❌ Token validation (Firebase Admin SDK)
- ❌ User management (Firebase Auth)

---

## 📁 Exposed Dependencies

### `get_supabase_client()`

**Location:** `app/dependencies/service_dependencies.py:18`

**Purpose:** Provides Supabase Python client for database operations

**Usage Pattern:**
```python
from app.dependencies import get_supabase_client

@router.get("/data")
async def get_data(supabase: Client = Depends(get_supabase_client)):
    # Use for DATABASE queries ONLY
    result = supabase.table("users").select("*").execute()
    return result.data
```

**Important Notes:**
- Uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS)
- Backend handles authorization via Firebase tokens
- RLS policies exist but are bypassed for performance
- Authorization logic is in `dependencies_secure_v2.py`

---

## 🔄 Authentication Flow (Correct)

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Frontend │      │ Firebase │      │ Backend  │      │ Supabase │
│ (React)  │──1──>│   Auth   │──2──>│   API    │──3──>│    DB    │
└──────────┘      └──────────┘      └──────────┘      └──────────┘
```

1. **Frontend** authenticates via Firebase
2. **Backend** validates Firebase token (not Supabase token)
3. **Backend** queries Supabase database with SERVICE_ROLE_KEY

---

## 🚫 What NOT to Use

### DO NOT use Supabase Auth methods:

```python
# ❌ WRONG - DO NOT DO THIS
supabase.auth.sign_in_with_password(...)
supabase.auth.sign_up(...)
supabase.auth.get_user(token)

# ✅ CORRECT - Use Firebase instead
from app.dependencies.auth_dependencies import _firebase_service
user_data = await _firebase_service.verify_token(token)
```

---

## 📦 Dependency Exports

### From `app/dependencies/__init__.py`

**Supabase-related exports:**
- `get_supabase_client` - DATABASE ACCESS ONLY

**Firebase-related exports:**
- `get_current_user` - Uses Firebase token validation
- `get_current_active_user` - Uses Firebase token validation
- `get_admin_user` - Uses Firebase token validation
- `get_doctor_user` - Uses Firebase token validation

---

## 🔧 Configuration

### Backend Environment Variables

**Supabase (Database):**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

**Firebase (Authentication):**
```env
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-xxxxx@...
```

---

## 🎯 Migration Status

**Completed:**
- ✅ Firebase Admin SDK integrated
- ✅ Token validation via Firebase
- ✅ Supabase used only for database
- ✅ All auth endpoints updated

**Architecture:**
```
Authentication: Firebase (PRIMARY)
Database: Supabase PostgreSQL (DATA ONLY)
Cache: Redis Cloud (REQUIRED)
```

---

## 📚 Related Documentation

- [AUTH_MIGRATION.md](../../../../docs/AUTH_MIGRATION.md) - Complete Firebase migration guide
- [FIREBASE_SECURITY.md](../../docs/FIREBASE_SECURITY.md) - Firebase security best practices
- [dependencies_secure_v2.py](../dependencies_secure_v2.py) - Firebase token validation implementation

---

## ✅ Summary

**Key Takeaway:** `get_supabase_client` is safe to use for **database operations only**. All authentication goes through Firebase.

**If you need:**
- Authentication → Use Firebase dependencies (`get_current_user`)
- Database access → Use `get_supabase_client`
- Real-time subscriptions → Use Supabase client (data layer)

---

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
