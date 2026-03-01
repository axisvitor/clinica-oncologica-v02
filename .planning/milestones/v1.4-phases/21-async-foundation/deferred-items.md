# Deferred Items - Phase 21 Async Foundation

- Full-suite pytest failure unrelated to plan 21-03 changes: `tests/api/v2/test_admin.py::TestBulkDelete::test_bulk_delete_success` returned HTTP 400 (expected 200) during `python3 -m pytest -x --tb=short -q`.
