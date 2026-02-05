# Retry Timing Analysis

Compensation backoff (spec vs code):
- Spec: 1s, 2s, 4s
- Code: (2**attempt) * 1.0 => 1s, 2s, 4s

Saga retry backoff:
- Spec: 2s, 4s, 8s
- Code: Implemented in `backend-hormonia/app/tasks/saga_retry.py` with 60s, 120s, 240s (capped at 600s).
