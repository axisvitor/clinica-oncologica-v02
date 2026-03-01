# Deferred Items

- 2026-02-27: `python3 -m pytest tests/api/v2/test_admin.py -x -q` fails at `TestActivityStatistics::test_get_activity_statistics` with `sqlalchemy.exc.ArgumentError` in `backend-hormonia/app/api/v2/routers/admin/stats.py` (`AuditLog.severity` property used in `select(...)`).
- Scope decision: deferred as pre-existing/unrelated to Plan 27-01 task objectives (auth session lookup, TODO cleanup, bulk delete regression).
- 2026-02-28: Full suite run for Plan 27-02 (`DATABASE_URL=sqlite:///./phase27-tests.db TEST_DATABASE_URL=sqlite:///./phase27-tests.db python3 -m pytest tests/ -q --tb=short`) showed broad pre-existing failures unrelated to MissingGreenlet/UndefinedColumn goals.
- Notable deferred categories: `tests/api/v2/test_patients_integration.py` (`httpx.AsyncClient(app=...)` signature mismatch), `tests/api/v2/admin/test_compensation.py` (SQLite JSON operator incompatibility), and broad legacy integration failures listed in `/tmp/phase27-suite-run.txt`.
- Scope decision: deferred as out-of-scope for Plan 27-02 TEST-02 target (only MissingGreenlet and UndefinedColumn stability gates).
