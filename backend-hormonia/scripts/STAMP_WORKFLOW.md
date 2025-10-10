# Production Database Stamping - Visual Workflow

## Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION DATABASE STAMPING                  │
│                         Complete Workflow                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: PREPARATION                                            │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐
    │ Install Deps    │
    │ pip install     │
    │ asyncpg alembic │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Review Docs     │
    │ README_STAMP    │
    │ _PRODUCTION_DB  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Run Tests       │
    │ test_stamp      │
    │ _script.py      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Test in Staging │
    │ (if available)  │
    └────────┬────────┘
             │
             ▼

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: ANALYSIS                                               │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────┐
    │ Show Migrations │
    │ --show-         │
    │ migrations      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │ Analyze Schema                                      │
    │ python scripts/stamp_production_db.py --analyze     │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────┐
    │ Review Analysis Results:                │
    │ • Current database state                │
    │ • Tables count                          │
    │ • Current alembic_version               │
    │ • Recommended revision                  │
    │ • Validation issues (if any)            │
    └────────┬────────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │ Validation │
        │   Passed?  │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────┐
           ▼                     ▼
    ┌──────────────┐     ┌──────────────────┐
    │ Continue to  │     │ Fix Schema       │
    │ Phase 3      │     │ Issues OR        │
    └──────────────┘     │ Use Older        │
                         │ Matching         │
                         │ Revision         │
                         └─────┬────────────┘
                               │
                               └──────┐
                                      ▼

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: DRY RUN (SAFE PREVIEW)                                 │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │ Preview Stamp (No DB Changes!)                      │
    │ python scripts/stamp_production_db.py \             │
    │   --stamp REVISION --dry-run                        │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Review Dry Run Output:               │
    │ ✓ Schema validation results          │
    │ ✓ What would be created/updated      │
    │ ✓ Current vs new version             │
    │ ✓ No actual changes made             │
    └────────┬─────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │ Output OK? │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────┐
           ▼                     ▼
    ┌──────────────┐     ┌──────────────────┐
    │ Continue to  │     │ Review Issues    │
    │ Phase 4      │     │ Adjust Revision  │
    └──────────────┘     │ or Fix Schema    │
                         └─────┬────────────┘
                               │
                               └──────┐
                                      ▼

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: BACKUP (CRITICAL!)                                     │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │ Create Database Backup                              │
    │ pg_dump $DATABASE_URL > backup_$(date).sql          │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Verify Backup:                       │
    │ • File size reasonable               │
    │ • Contains all tables                │
    │ • Can be restored if needed          │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Document Backup Location             │
    │ • Path to backup file                │
    │ • Timestamp                          │
    │ • Database size                      │
    └────────┬─────────────────────────────┘
             │
             ▼

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: STAMP EXECUTION                                        │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │ Execute Stamp Command                               │
    │ python scripts/stamp_production_db.py \             │
    │   --stamp REVISION                                  │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Script Performs:                     │
    │ 1. Validates revision exists         │
    │ 2. Connects to database              │
    │ 3. Gets current schema info          │
    │ 4. Validates schema matches revision │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ First Confirmation Prompt:           │
    │ "Are you sure you want to stamp      │
    │  the database?"                      │
    │                                      │
    │ Current alembic_version: None        │
    │ New version will be: REVISION        │
    └────────┬─────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │ Confirm?   │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────┐
           ▼                     ▼
    ┌──────────────┐     ┌──────────────────┐
    │ Continue     │     │ Operation        │
    └──────┬───────┘     │ Cancelled        │
           │             └──────────────────┘
           ▼
    ┌──────────────────────────────────────┐
    │ Second Confirmation Prompt:          │
    │ "FINAL CONFIRMATION:                 │
    │  Proceed with stamping?"             │
    └────────┬─────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │ Confirm?   │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────┐
           ▼                     ▼
    ┌──────────────┐     ┌──────────────────┐
    │ Execute      │     │ Operation        │
    │ Stamp        │     │ Cancelled        │
    └──────┬───────┘     └──────────────────┘
           │
           ▼
    ┌──────────────────────────────────────┐
    │ Stamp Database:                      │
    │ 1. Create alembic_version (if needed)│
    │ 2. INSERT or UPDATE revision         │
    │ 3. Verify stamp successful           │
    └────────┬─────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │  Success?  │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────┐
           ▼                     ▼
    ┌──────────────┐     ┌──────────────────┐
    │ Continue to  │     │ Rollback &       │
    │ Verification │     │ Error Recovery   │
    └──────────────┘     └─────┬────────────┘
                               │
                               └──────┐
                                      ▼

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 6: VERIFICATION                                           │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │ Step 1: Database Verification                       │
    │ SELECT * FROM alembic_version;                      │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Expected Output:                     │
    │ version_num                          │
    │ -------------                        │
    │ REVISION                             │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │ Step 2: Alembic Verification                        │
    │ alembic current                                     │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Expected Output:                     │
    │ REVISION (head)                      │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │ Step 3: Migration History Check                     │
    │ alembic history --verbose                           │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │ Step 4: Pending Migrations Check                    │
    │ alembic upgrade head --sql                          │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Review Pending SQL:                  │
    │ • Should be minimal or none          │
    │ • No CREATE TABLE for existing tables│
    │ • Only expected schema changes       │
    └────────┬─────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │ All OK?    │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────┐
           ▼                     ▼
    ┌──────────────┐     ┌──────────────────┐
    │ SUCCESS!     │     │ Investigate      │
    │ Document     │     │ Issues &         │
    │ Completion   │     │ Rollback if      │
    └──────────────┘     │ Necessary        │
                         └──────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 7: POST-STAMP ACTIONS                                     │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────┐
    │ 1. Document the Stamp:               │
    │    • Which revision was stamped      │
    │    • Why stamping was needed         │
    │    • Date and time                   │
    │    • Who performed it                │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ 2. Test Application:                 │
    │    • Application starts successfully │
    │    • No migration errors in logs     │
    │    • Database operations work        │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ 3. Plan Next Migrations:             │
    │    • Review pending migrations       │
    │    • Schedule application if needed  │
    │    • Test in staging first           │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ 4. Monitor:                          │
    │    • Check application logs          │
    │    • Monitor database performance    │
    │    • Watch for migration errors      │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ ✓ STAMP COMPLETE!                    │
    │   Database ready for future          │
    │   Alembic migrations                 │
    └──────────────────────────────────────┘
```

---

## Emergency Rollback Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│ IF SOMETHING GOES WRONG - ROLLBACK PROCEDURE                    │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────┐
    │ Problem Detected                     │
    │ (Wrong revision, errors, etc.)       │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ STOP! Don't run more migrations      │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Option 1: Fix alembic_version Table │
    └────────┬─────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │ DELETE FROM alembic_version;                        │
    │ INSERT INTO alembic_version (version_num)           │
    │   VALUES ('CORRECT_REVISION');                      │
    └────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │ Verify:                              │
    │ SELECT * FROM alembic_version;       │
    │ alembic current                      │
    └────────┬─────────────────────────────┘
             │
             ▼
        ┌────────────┐
        │  Fixed?    │
        └──┬──────┬──┘
           │      │
       YES │      │ NO
           │      │
           │      └──────────────────────────┐
           ▼                                 ▼
    ┌──────────────┐             ┌─────────────────────┐
    │ SUCCESS!     │             │ Option 2:           │
    └──────────────┘             │ Full Database       │
                                 │ Restore             │
                                 └─────┬───────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │ psql $DATABASE_URL <        │
                         │   backup_TIMESTAMP.sql      │
                         └─────┬───────────────────────┘
                               │
                               ▼
                         ┌─────────────────────────────┐
                         │ Verify Restore:             │
                         │ • Check table counts        │
                         │ • Verify data integrity     │
                         │ • Test application          │
                         └─────┬───────────────────────┘
                               │
                               ▼
                         ┌─────────────────────────────┐
                         │ Re-run Stamp:               │
                         │ python scripts/             │
                         │   stamp_production_db.py \  │
                         │   --stamp CORRECT_REVISION  │
                         └─────────────────────────────┘
```

---

## Safety Checkpoints

```
Before Each Phase:

✓ PHASE 1 (Preparation)
  [ ] Dependencies installed
  [ ] Documentation reviewed
  [ ] Tests passed
  [ ] Staging tested (if available)

✓ PHASE 2 (Analysis)
  [ ] Schema analyzed
  [ ] Validation passed or issues understood
  [ ] Correct revision identified

✓ PHASE 3 (Dry Run)
  [ ] Dry run executed
  [ ] Output reviewed
  [ ] No unexpected changes

✓ PHASE 4 (Backup)
  [ ] Backup created
  [ ] Backup verified
  [ ] Backup location documented

✓ PHASE 5 (Execution)
  [ ] Both confirmations provided
  [ ] Stamp completed successfully
  [ ] No errors in output

✓ PHASE 6 (Verification)
  [ ] alembic_version correct
  [ ] Alembic sees revision
  [ ] Migration history correct
  [ ] No unexpected pending migrations

✓ PHASE 7 (Post-Stamp)
  [ ] Action documented
  [ ] Application tested
  [ ] No errors in logs
  [ ] Monitoring in place
```

---

## Quick Reference Commands

```bash
# Analysis
python scripts/stamp_production_db.py --analyze

# Dry Run (Safe Preview)
python scripts/stamp_production_db.py --stamp REVISION --dry-run

# Actual Stamp
python scripts/stamp_production_db.py --stamp REVISION

# Verification
psql $DATABASE_URL -c "SELECT * FROM alembic_version;"
alembic current
alembic history --verbose

# Rollback
psql $DATABASE_URL -c "DELETE FROM alembic_version;"
psql $DATABASE_URL -c "INSERT INTO alembic_version VALUES ('CORRECT_REVISION');"
```

---

## Remember

🔴 **CRITICAL SAFETY RULES:**
1. Always backup before stamping
2. Always use --dry-run first
3. Never skip validation (unless you know why)
4. Always verify after stamping
5. Test in staging first

🟡 **WARNING SIGNS:**
- Validation fails unexpectedly
- Dry run shows unexpected changes
- Migration history looks wrong
- Application errors after stamp

🟢 **SUCCESS INDICATORS:**
- alembic_version shows correct revision
- Alembic current shows (head)
- No unexpected pending migrations
- Application runs without errors
