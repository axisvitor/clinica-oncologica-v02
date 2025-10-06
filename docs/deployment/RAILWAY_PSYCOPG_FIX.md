# Railway Deployment: psycopg v3 Migration Fix

## ❌ Error Encountered

```
ModuleNotFoundError: No module named 'psycopg2'
sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres
```

## 🔍 Root Cause Analysis

### Problem
Railway deployment crashes on startup because:

1. **SQLAlchemy Driver Detection**: When using `postgresql://` in DATABASE_URL, SQLAlchemy's PostgreSQL dialect **automatically tries to import `psycopg2` first** as the default driver
2. **Python 3.13 Compatibility**: The project uses Python 3.13, which requires `psycopg` v3 (not `psycopg2`)
3. **requirements.txt**: Only `psycopg[binary]>=3.1.8` is installed (correct for Python 3.13)
4. **Missing Explicit Driver**: The DATABASE_URL doesn't specify which driver to use

### Why It Fails
```python
# SQLAlchemy's driver preference order for postgresql://
1. Try psycopg2 (FAILS - not installed)
2. Try psycopg2-binary (FAILS - not installed)
3. Try psycopg (NEVER REACHED - crashes before this)
```

## ✅ Solution: Explicit Driver Declaration

### Change DATABASE_URL Format

**❌ Old (Implicit Driver - Causes Error)**:
```bash
DATABASE_URL=postgresql://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

**✅ New (Explicit psycopg Driver)**:
```bash
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

### Why This Works

The `+psycopg` suffix tells SQLAlchemy to:
- **Skip** trying to import `psycopg2`
- **Directly use** the `psycopg` (v3) driver
- **Avoid** the ModuleNotFoundError completely

## 📋 Railway Deployment Checklist

### 1. Update Railway Environment Variables

In Railway dashboard, update:

```bash
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

### 2. Verify Python Version (Optional)

Railway will auto-detect from `runtime.txt`:
```
python-3.13.3
```

### 3. Verify Dependencies

Ensure `requirements.txt` includes:
```txt
# Database driver for Python 3.13
psycopg[binary]>=3.1.8,<3.3.0
sqlalchemy>=2.0.23,<2.1.0
```

### 4. Test Locally (Optional)

```bash
# Set environment variable
export DATABASE_URL="postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"

# Test connection
python -c "from sqlalchemy import create_engine; engine = create_engine('${DATABASE_URL}'); print('✅ Connection successful')"
```

## 🔧 Technical Details

### SQLAlchemy Dialect System

SQLAlchemy uses the URL format to determine which database driver to load:

| URL Format | Driver Loaded | Python 3.13 Support |
|-----------|---------------|---------------------|
| `postgresql://` | psycopg2 (default) | ❌ No (limited wheels) |
| `postgresql+psycopg2://` | psycopg2 (explicit) | ❌ No |
| `postgresql+psycopg://` | psycopg v3 | ✅ Yes (native support) |
| `postgresql+asyncpg://` | asyncpg | ✅ Yes (async only) |

### Python 3.13 Compatibility Matrix

| Package | Version | Python 3.13 | Notes |
|---------|---------|-------------|-------|
| psycopg2 | 2.9.x | ⚠️ Limited | Binary wheels not available for all platforms |
| psycopg2-binary | 2.9.x | ⚠️ Limited | Same as psycopg2 |
| **psycopg** | **3.1.8+** | **✅ Full** | **Recommended - Native Python 3.13 support** |
| asyncpg | 0.29.0+ | ✅ Full | Async-only, no sync support |

### Why psycopg v3?

1. **Python 3.13 Native Support**: Built with modern Python in mind
2. **Binary Wheels Available**: Fast installation, no compilation needed
3. **Better Performance**: Optimized for Python 3.10+
4. **SQLAlchemy 2.0 Compatible**: Full support for latest SQLAlchemy features
5. **Active Maintenance**: Actively developed and maintained

## 📊 Expected Startup Logs (After Fix)

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
DEBUG:    Database engine initialized: postgresql+psycopg://postgres.***@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 🚨 Common Mistakes to Avoid

### ❌ DON'T: Use postgresql:// alone
```bash
# This will crash on Railway with Python 3.13
DATABASE_URL=postgresql://...
```

### ❌ DON'T: Install psycopg2 for Python 3.13
```txt
# requirements.txt - WRONG
psycopg2-binary==2.9.9  # Limited Python 3.13 support
```

### ✅ DO: Use explicit driver + psycopg v3
```bash
# Railway environment variable
DATABASE_URL=postgresql+psycopg://...
```

```txt
# requirements.txt - CORRECT
psycopg[binary]>=3.1.8,<3.3.0
```

## 🔗 References

- **psycopg Documentation**: https://www.psycopg.org/psycopg3/docs/
- **SQLAlchemy PostgreSQL Dialects**: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- **Python 3.13 Compatibility**: https://docs.python.org/3.13/whatsnew/3.13.html

## 📝 Summary

| Item | Value |
|------|-------|
| **Error** | `ModuleNotFoundError: No module named 'psycopg2'` |
| **Root Cause** | DATABASE_URL uses implicit driver (tries psycopg2 first) |
| **Solution** | Use `postgresql+psycopg://` to explicitly select psycopg v3 |
| **Python Version** | 3.13.3 (requires psycopg v3) |
| **Railway Variable** | `DATABASE_URL=postgresql+psycopg://...` |

---

**Last Updated**: 2025-10-06
**Deployment Status**: ✅ Ready for Railway
