## Activity Router Verification for 26-04

- `backend-hormonia/app/api/v2/routers/admin/activity.py` compiles with `python3 -m py_compile`.
- Source assertions pass:
  - no `db.query(`
  - no `Depends(get_db)`
  - no `UserRepository(`

Result: `activity.py` already satisfies AsyncSession migration requirements for plan 26-04 Task 2.
