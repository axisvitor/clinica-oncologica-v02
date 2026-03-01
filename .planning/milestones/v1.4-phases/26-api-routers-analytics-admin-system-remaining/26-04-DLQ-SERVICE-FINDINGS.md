## DLQService Findings for 26-04

- `DLQService.retry_message` uses `self.db.query(FailedMessage)` and sync `self.db.commit()`.
- `DLQService.discard_message` uses `self.db.query(FailedMessage)` via `DeadLetterHandler.discard_message`.
- `DLQService.get_stats` delegates to `DeadLetterHandler.get_stats`, which uses sync `self.db.query(...)` counts.

Conclusion: `DLQService` is sync-bound for these methods. Router migration must inline AsyncSession DB operations for retry, discard, and stats to avoid `MissingGreenlet` runtime failures.
