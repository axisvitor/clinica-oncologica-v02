# Phase 15: Data Integrity Fixes - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix 4 specific data integrity bugs: quiz template crash on missing template (FIX-04), duplicate phase constants across modules (FIX-05), inconsistent quiz cycle calculation (FIX-06), and unrouted failed flow messages (FIX-07). Pure bug-fix and consolidation phase — no new capabilities.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User granted full discretion on all implementation choices. The following guidelines apply:

**Quiz fallback behavior (FIX-04):**
- When a patient has no associated quiz template, send the WhatsApp message without the quiz link (drop the link portion, keep the rest of the message intact)
- Log a warning with patient ID and flow context for operational visibility
- Do NOT alert staff in real-time for missing templates — this is a data setup issue, not an emergency. Surface it in existing monitoring/dashboard
- No separate message template needed; conditionally omit the quiz link section from the existing template

**DLQ retry & exhaustion (FIX-07):**
- Use exponential backoff: 3 retries with delays of 30s, 2min, 10min
- After exhaustion, message stays in DLQ as "failed" with full context preserved for manual review
- Wire into existing DLQ monitoring dashboard (already canonical at `app/services/dlq/`)
- No Slack/WhatsApp alerts for individual failures — aggregate DLQ health surfaced through existing alerting patterns

**Operational alerting (both fixes):**
- Dashboard-only visibility using existing monitoring infrastructure
- No new alert channels; leverage what's already built in the alert_manager and DLQ monitoring
- Log entries at WARNING level for traceability

**Constants consolidation (FIX-05):**
- `app/agents/patient/flow_coordinator/constants.py` is already the canonical source (per MEMORY.md)
- Remove duplicates in `sequential_message_handler` and any other consumers
- Apply shim pattern at old locations if external consumers exist

**Cycle calculation (FIX-06):**
- Extract single `compute_cycle_number(date)` function into the canonical constants module
- Both `flow_coordinator` and `sequential_message_handler` import from canonical source
- Ensure deterministic behavior for edge cases (month boundaries, timezone handling)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User granted full discretion.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 15-data-integrity-fixes*
*Context gathered: 2026-02-24*
