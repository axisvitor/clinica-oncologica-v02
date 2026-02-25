# Deferred Items

## 2026-02-24

- `backend-hormonia/app/services/flow/__init__.py` currently imports `.analytics`, but `backend-hormonia/app/services/flow/analytics/__init__.py` is already tombstoned and raises `ImportError` at package import time.
- This is pre-existing and out of scope for `16-01-PLAN.md` (which only tombstones `flow/constants.py` and `flow/template_lookup.py`).
- Impact during this plan: `import app.services.flow.constants` is intercepted by package-level ImportError before reaching `constants.py`; verification used direct module execution to validate tombstone sentinel content.
