# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| D001 | M009/S01/T02 | M009/S01/T02 | Taskiq health check strategy during Celery coexistence | Health endpoints check Taskiq first (async Redis ping), then Celery (control.inspect), report both; workers check passes if either is healthy | During migration (S02-S04), both Celery and Taskiq may be running simultaneously. The readiness probe must not report unhealthy just because one system is down while the other handles tasks. Taskiq check is async + fast (Redis ping), Celery check is thread-based + slow (inspect with 0.5s timeout). | Yes — once Celery is fully removed (after S04), drop Celery checks entirely |
