# Quick Start - Fix pkg_resources Deprecation

**TL;DR:** Update Google packages to eliminate deprecation warnings.

---

## 🚀 Quick Fix (5 minutes)

### Windows:
```bash
cd backend-hormonia
scripts\upgrade_google_packages.bat
```

### macOS/Linux:
```bash
cd backend-hormonia
./scripts/upgrade_google_packages.sh
```

---

## ✅ Verify Fix

```bash
py scripts/verify_pkg_resources_fix.py
```

**Expected:** ✅ All checks passed!

---

## 🧪 Test Application

```bash
# Start server
py -m uvicorn app.main:app --reload

# Check for warnings - should see NONE
# Look for: "pkg_resources is deprecated"
```

---

## 🔍 What Was Updated?

| Package | New Version |
|---------|------------|
| googleapis-common-protos | >=1.70.0 |
| google-api-core | >=2.25.0 |
| grpcio | >=1.75.0 |
| firebase-admin | >=6.9.0 |

---

## ⚠️ If Something Breaks

```bash
# Restore from backup (created by upgrade script)
py -m pip install -r requirements.backup.txt

# Or manually reinstall
py -m pip install --upgrade -r requirements.txt
```

---

## 📚 More Info

- **Detailed guide:** `docs/PKG_RESOURCES_FIX.md`
- **Full summary:** `docs/UPGRADE_SUMMARY.md`

---

## 💡 Why This Fix?

`pkg_resources` is being removed from Python. Google packages now use modern `importlib.metadata` instead.

**Before:** ⚠️ Deprecation warnings
**After:** ✅ Clean startup, future-proof code

---

**Last Updated:** 2025-10-05
