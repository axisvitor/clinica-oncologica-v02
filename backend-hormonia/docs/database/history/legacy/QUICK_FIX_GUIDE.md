# Quick Fix Guide - Post-Migration Validation

**TL;DR:** Application works, but migration tracking is broken. Follow these steps to fix.

---

## 🚨 Critical Fix (Do This First)

### Fix #1: Update Patient Name Queries

**Problem:** Code uses `full_name` but database has `name`

**Find and replace in your codebase:**
```python
# ❌ WRONG - Will fail
patients = db.query(Patient.full_name)

# ✅ CORRECT
patients = db.query(Patient.name)
```

**Files likely affected:**
- `app/api/v2/patients*.py`
- `app/services/patient*.py`
- `app/repositories/patient.py`

**Quick search:**
```bash
grep -r "full_name" app/ | grep -i patient
```

---

## 🔧 Standard Fixes (Do Today)

### Fix #2: Stamp Migration State

**Problem:** Only 2/18 migrations tracked in database

**Solution:**
```bash
cd backend-hormonia

# Option A: Stamp to latest (recommended)
alembic stamp head

# Option B: Stamp to specific migration
alembic stamp 018_seed_flow_templates_for_onboarding

# Verify
alembic current
```

**Expected output:**
```
018_seed_flow_templates_for_onboarding (head)
```

---

### Fix #3: Create Missing Tables

**Problem:** `uploads` and `flow_templates` tables don't exist

**Solution:**

#### Option A: Apply Migrations (Preferred)
```bash
# Create uploads table
alembic upgrade 015_rename_upload_metadata_column

# Seed flow templates
alembic upgrade 018_seed_flow_templates_for_onboarding

# Verify
psql $DATABASE_URL -c "\dt uploads flow_templates"
```

#### Option B: Manual SQL (If migrations fail)
```sql
-- Create uploads table
CREATE TABLE uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    file_size INTEGER,
    file_metadata JSONB,
    uploaded_by UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create flow_templates table
CREATE TABLE flow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template_data JSONB NOT NULL,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_uploads_uploaded_by ON uploads(uploaded_by);
CREATE INDEX idx_flow_templates_category ON flow_templates(category);
CREATE INDEX idx_flow_templates_is_active ON flow_templates(is_active);
```

---

### Fix #4: Add Missing Column

**Problem:** `patient_flow_states.last_retry_at` doesn't exist

**Solution:**
```sql
-- Add missing column
ALTER TABLE patient_flow_states
ADD COLUMN last_retry_at TIMESTAMP;

-- Add index for performance
CREATE INDEX idx_patient_flow_states_last_retry
ON patient_flow_states(last_retry_at)
WHERE last_retry_at IS NOT NULL;
```

**Verify:**
```sql
\d patient_flow_states
```

Should show `last_retry_at` in column list.

---

## ✅ Verification Steps

### Step 1: Check Migration State
```bash
alembic current
```
**Expected:** Shows latest migration (018 or head)

### Step 2: Check Tables Exist
```sql
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('uploads', 'flow_templates', 'patients')
ORDER BY table_name;
```
**Expected:** All 3 tables listed

### Step 3: Check Patient Columns
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'patients'
  AND column_name IN ('name', 'deleted_at', 'metadata')
ORDER BY column_name;
```
**Expected:** All 3 columns listed (NOT full_name)

### Step 4: Test Application
```bash
python3 -c "from app.main import app; print('✅ App OK')"
```
**Expected:** No errors, prints "✅ App OK"

---

## 🎯 Before You Start

### Pre-Flight Checklist
- [ ] Database backup created
- [ ] Environment variables loaded (`.env`)
- [ ] PostgreSQL accessible
- [ ] Alembic installed (`pip install alembic`)
- [ ] No active connections to database

### Backup Command
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
```

---

## 🚑 If Something Goes Wrong

### Rollback Migration Stamp
```bash
# Go back to known good state
alembic stamp 004_add_flow_state_version
```

### Restore from Backup
```bash
# If you need to rollback completely
psql $DATABASE_URL < backup_YYYYMMDD_HHMMSS.sql
```

### Check What Broke
```sql
-- Check table exists
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'your_table'
);

-- Check column exists
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'your_table'
      AND column_name = 'your_column'
);

-- Check alembic state
SELECT version_num FROM alembic_version;
```

---

## 📋 Code Changes Required

### Update Patient Model Queries

**Before:**
```python
# app/api/v2/patients.py
@router.get("/patients")
async def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient.id, Patient.full_name).all()
```

**After:**
```python
# app/api/v2/patients.py
@router.get("/patients")
async def list_patients(db: Session = Depends(get_db)):
    return db.query(Patient.id, Patient.name).all()
```

### Update Patient Schemas

**Before:**
```python
# app/schemas/patient.py
class PatientResponse(BaseModel):
    id: UUID
    full_name: str
```

**After:**
```python
# app/schemas/patient.py
class PatientResponse(BaseModel):
    id: UUID
    name: str
```

---

## 🔍 Testing After Fixes

### Test 1: Patient Query
```python
from app.database import SessionLocal
from app.models.patient import Patient

db = SessionLocal()
patient = db.query(Patient.id, Patient.name).first()
print(f"✅ Patient query works: {patient}")
db.close()
```

### Test 2: File Upload (if implemented)
```python
from app.models.upload import Upload

db = SessionLocal()
upload = Upload(
    filename="test.txt",
    content_type="text/plain",
    file_size=1024
)
db.add(upload)
db.commit()
print(f"✅ Upload created: {upload.id}")
db.close()
```

### Test 3: Flow Template
```python
from app.models.flow_template import FlowTemplate

db = SessionLocal()
template = FlowTemplate(
    name="Test Template",
    template_data={"steps": []}
)
db.add(template)
db.commit()
print(f"✅ Template created: {template.id}")
db.close()
```

---

## 📞 Need Help?

### Common Issues

**Issue:** `alembic stamp head` fails
**Fix:** Check alembic.ini has correct database URL

**Issue:** Migrations conflict
**Fix:** Use `alembic upgrade --sql` to preview SQL, apply manually

**Issue:** Column still missing after migration
**Fix:** Check migration actually ran: `alembic history --verbose`

### Debug Commands
```bash
# Show migration history
alembic history --verbose

# Show current state
alembic current --verbose

# Show SQL that would run (don't execute)
alembic upgrade head --sql

# Show pending migrations
alembic upgrade head --dry-run
```

---

## ✅ Success Criteria

After following this guide, you should have:

- ✅ Alembic tracking 18 migrations
- ✅ `uploads` table exists
- ✅ `flow_templates` table exists
- ✅ `patient_flow_states.last_retry_at` exists
- ✅ All patient queries use `name` (not `full_name`)
- ✅ Application imports without errors
- ✅ All tests pass

---

## 📊 Validation Script

**Run this to verify everything works:**

```bash
#!/bin/bash
echo "🔍 Validating database fixes..."

# Check migration state
echo "1. Checking migration state..."
alembic current | grep -q "head" && echo "✅ Migration state OK" || echo "❌ Migration state FAILED"

# Check tables
echo "2. Checking tables exist..."
psql $DATABASE_URL -c "SELECT 'uploads' WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='uploads')" -t | grep -q "uploads" && echo "✅ uploads table OK" || echo "❌ uploads table MISSING"
psql $DATABASE_URL -c "SELECT 'flow_templates' WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='flow_templates')" -t | grep -q "flow_templates" && echo "✅ flow_templates table OK" || echo "❌ flow_templates table MISSING"

# Check columns
echo "3. Checking patient columns..."
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='patients' AND column_name='name'" -t | grep -q "name" && echo "✅ patients.name OK" || echo "❌ patients.name MISSING"
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='patient_flow_states' AND column_name='last_retry_at'" -t | grep -q "last_retry_at" && echo "✅ last_retry_at OK" || echo "❌ last_retry_at MISSING"

# Check application
echo "4. Testing application..."
python3 -c "from app.main import app" 2>&1 | grep -q "Error" && echo "❌ App import FAILED" || echo "✅ App import OK"

echo "✅ Validation complete!"
```

Save as `validate_fixes.sh`, make executable, and run:
```bash
chmod +x validate_fixes.sh
./validate_fixes.sh
```

---

**Last Updated:** 2025-11-16
**Related Docs:**
- Detailed report: `POST_MIGRATION_VALIDATION.md`
- Schema reference: `ACTUAL_SCHEMA_STRUCTURE.md`
- Executive summary: `VALIDATION_EXECUTIVE_SUMMARY.md`
