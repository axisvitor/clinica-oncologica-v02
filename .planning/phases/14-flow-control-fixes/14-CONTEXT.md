# Phase 14: Flow Control Fixes - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix patient flow pause, auto-resume, and cancel operations so they work correctly and consistently across the daily processor, Celery Beat, and flow management service. This phase fixes three existing broken behaviors (FIX-01, FIX-02, FIX-03) — no new flow types or UI changes.

</domain>

<decisions>
## Implementation Decisions

### Pause behavior
- Messages stay queued during pause (hold and send later, not skip)
- Pause takes effect immediately, even mid-message-sequence — remaining messages in current batch are held
- On resume, held messages go out first before continuing the schedule
- API response returns pause details (patient, duration, resume date) — no push notification or email needed
- Doctor can optionally set an `auto_resume_at` timestamp; if omitted, pause is indefinite until manual resume

### Auto-resume rules
- Silent auto-resume — no notification to the doctor when auto-resume triggers
- Flow picks up exactly where it stopped (if message 2/3 was last sent, message 3 goes next)
- Normal resume regardless of pause duration — no special handling for long pauses (30+ days)
- Beat job check frequency: Claude's discretion (match existing Beat job patterns)

### Cancel flow lifecycle
- Silent cancellation — no farewell message sent to the patient
- Simple cancel action — no reason required from the doctor
- In-flight messages (queued in Celery) are actively revoked/deleted — clean cut, no message leakage after cancel
- Cancel restartability: Claude's discretion (decide based on flow state model)

### Edge case behavior
- Pause is idempotent — re-pausing updates `auto_resume_at` if changed, returns success, no error
- Patient responses during pause are stored and processed on resume — no data lost
- Cancel overrides pause directly — no need to resume first before cancelling
- All pause/resume/cancel operations are audited (doctor ID, timestamp, action details, endpoint)

### Claude's Discretion
- Celery Beat job frequency for auto-resume checks
- Whether a cancelled flow can be restarted or is permanent (decide based on state model)
- Technical implementation of Celery task revocation for in-flight messages
- Audit log format and storage (use existing audit patterns in codebase)

</decisions>

<specifics>
## Specific Ideas

- The `state_data.paused` field must be the single source of truth — daily processor and flow management both read this, not different fields
- Cancel must clear ALL pending state so no follow-up messages escape after cancellation
- The cancel endpoint should return confirmation to the doctor (API response with cancelled flow details)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-flow-control-fixes*
*Context gathered: 2026-02-24*
