# Coverage Status

Coverage run command:
```
pytest tests/orchestration/ tests/integration/ tests/services/ \
  -v \
  --cov=app/orchestration/saga_orchestrator \
  --cov=app/core/distributed_lock \
  --cov=app/models/patient_onboarding_saga \
  --cov-report=html \
  --cov-report=term-missing \
  --cov-branch
```

Result: Aborted. Test initialization stalled during settings/bootstrap and was interrupted.
No htmlcov output was produced.

Blockers:
- app.main loads .env with override=True, forcing production-like settings during tests.
- Integration tests require DATABASE_URL containing "test".

Next step: configure a test .env or isolate test settings so coverage can run.
