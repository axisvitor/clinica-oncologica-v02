# Follow-up System

## Message Deduplication
- Purpose: Prevent duplicate follow-up messages from being scheduled within a 24-hour window.
- Configuration: `FOLLOW_UP_DEDUP_WINDOW_SECONDS` controls the window (default: 86400 seconds).
- How it works: Redis caches a SHA256-based key derived from patient, normalized content, and follow-up type.
- Metrics: `follow_up_messages_deduplicated_total` tracks blocked duplicates.
- Failure handling: If Redis is unavailable, deduplication is skipped and messages are still scheduled.

## Deduplication Key Format
- Key prefix: `follow_up:dedup:`
- Hash input: `{patient_id}:{content_hash}:{follow_up_type}`
- Content hash: SHA256 of normalized content (whitespace collapsed, case-insensitive).
