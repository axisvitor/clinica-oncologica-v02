# Deferred Items - Phase 20 Schema Fix

## Out-of-scope Fail-Fast Blocker

- Command: `python3 -m pytest -x --tb=short -q`
- Date/Time (UTC): `2026-02-26T16:39:00Z`
- First failing node: `tests/api/v2/test_auth.py::TestSessionManagement::test_list_sessions_success`
- Error class: `sqlalchemy.exc.ProgrammingError` (`psycopg.errors.UndefinedColumn: column "session_token" of relation "sessions" does not exist`)
- Scope note: This sessions schema mismatch is unrelated to Phase 20 alerts model/schema alignment work.
