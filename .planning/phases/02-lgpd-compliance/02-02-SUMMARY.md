---
phase: 02-lgpd-compliance
plan: 02
subsystem: database
tags: [lgpd, whatsapp, opt-out, consent, sqlalchemy, alembic, webhook]

# Dependency graph
requires:
  - phase: 02-lgpd-compliance-plan-01
    provides: PatientDeletionAudit model and lgpd01 Alembic migration (down_revision reference)

provides:
  - messaging_stopped_at nullable DateTime column on Patient model
  - lgpd02 Alembic migration with partial index for opt-out lookups
  - is_opt_out_message() keyword detector and OPT_OUT_KEYWORDS frozenset in message_handler
  - _handle_opt_out() method: stamps timestamp, revokes COMMUNICATION consents via ConsentService
  - Opt-out interception in process_message() before any flow advancement
  - Last-resort send guard in UnifiedWhatsAppService.send_message()

affects: [03-data-portability, messaging, webhook, flow-engine, celery-tasks]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resilient opt-out: primary action (timestamp) always applied, secondary (consent revocation) is best-effort"
    - "Last-resort guard pattern: UnifiedWhatsAppService refuses opted-out patients even if scheduler missed them"
    - "Partial index (WHERE NOT NULL) for efficient minority-subset lookups without indexing majority of NULLs"
    - "Pre-existing test failures confirmed via git stash to distinguish from new failures"

key-files:
  created:
    - backend-hormonia/alembic/versions/lgpd02_add_whatsapp_opt_out_flag.py
  modified:
    - backend-hormonia/app/models/patient.py
    - backend-hormonia/app/services/webhook/handlers/message_handler.py
    - backend-hormonia/app/services/unified_whatsapp_service.py

key-decisions:
  - "Opt-out interception placed after patient lookup (Step 3) and before flow advancement (Step 4) to prevent any outbound message being triggered post-revocation"
  - "Consent revocation is best-effort wrapped in try/except — messaging_stopped_at is persisted regardless, satisfying LGPD Art. 18 immediacy requirement"
  - "Guard in UnifiedWhatsAppService.send_message() logs and continues on guard failure — guard errors must never block legitimate sends"
  - "OPT_OUT_KEYWORDS uses exact-match only (no substring) to prevent false positives in medical conversations"
  - "Both accented (não quero) and unaccented (nao quero) Portuguese forms included for keyboard/IME resilience"
  - "migration down_revision points to lgpd01_add_patient_deletion_audit (single head, no merge needed)"

patterns-established:
  - "Opt-out guard pattern: check messaging_stopped_at before send in UnifiedWhatsAppService"
  - "Resilience pattern: wrap secondary LGPD actions in try/except, always commit primary action"

requirements-completed: [LGPD-02]

# Metrics
duration: 10min
completed: 2026-02-22
---

# Phase 02 Plan 02: WhatsApp Opt-Out Handler Summary

**LGPD Art. 18 opt-out via STOP/PARAR/CANCELAR keywords: timestamps patient, revokes COMMUNICATION consents, and blocks all future sends via UnifiedWhatsAppService guard**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-22T17:41:54Z
- **Completed:** 2026-02-22T17:51:38Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- Patient model now has `messaging_stopped_at` nullable DateTime column with Alembic migration and partial index
- process_message() intercepts 12 opt-out keywords (STOP, PARAR, CANCELAR, and Portuguese variants) before any flow advancement or outbound message creation
- `_handle_opt_out()` stamps the timestamp and revokes active COMMUNICATION consents via ConsentService, resilient to missing consent records
- UnifiedWhatsAppService.send_message() has a last-resort guard that refuses to send to opted-out patients even if the Celery scheduler misses them

## Task Commits

Each task was committed atomically:

1. **Task 1: Add messaging_stopped_at column to Patient model and create Alembic migration** - `57d06e00` (feat)
2. **Task 2: Implement opt-out detection in message handler and send guard in WhatsApp service** - `32814fed` (feat)

**Plan metadata:** (pending, will be committed with SUMMARY.md)

## Files Created/Modified

- `backend-hormonia/app/models/patient.py` - Added `messaging_stopped_at = Column(DateTime(timezone=True), nullable=True)` near `deleted_at`
- `backend-hormonia/alembic/versions/lgpd02_add_whatsapp_opt_out_flag.py` - Migration adding column + partial index `idx_patients_messaging_stopped`
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` - Added `OPT_OUT_KEYWORDS`, `is_opt_out_message()`, opt-out interception in `process_message()`, and `_handle_opt_out()` method
- `backend-hormonia/app/services/unified_whatsapp_service.py` - Added last-resort opt-out guard at top of `send_message()`

## Decisions Made

- Opt-out interception placed after patient lookup (Step 3) and before flow advancement (Step 4) to prevent any outbound message being triggered post-revocation
- Consent revocation is best-effort wrapped in try/except — `messaging_stopped_at` is persisted regardless, satisfying LGPD Art. 18 immediacy requirement
- Guard in `UnifiedWhatsAppService.send_message()` logs and continues on guard failure — guard errors must never block legitimate sends
- `OPT_OUT_KEYWORDS` uses exact-match only (no substring) to prevent false positives in medical conversations where "parar" may appear mid-sentence
- Both accented (`não quero`) and unaccented (`nao quero`) Portuguese forms included for keyboard/IME resilience
- `message_data["content"]` confirmed as the extracted text field (from reading `message_extractor.py`)
- Migration `down_revision` points to `lgpd01_add_patient_deletion_audit` (single Alembic head, no merge tuple needed)

## Deviations from Plan

None - plan executed exactly as written.

The pre-existing test failure `TestFlowAdvanceGate::test_handle_flow_message_does_not_use_pending_prompt_as_received_context` was confirmed via `git stash` to have been failing before our changes. It is unrelated to opt-out functionality.

## Issues Encountered

- `python` command not found in shell (WSL environment uses `python3`) — switched to `python3` for verification. No impact on deliverables.
- One pre-existing test failure confirmed via git stash as pre-existing, not introduced by this plan.

## User Setup Required

None - no external service configuration required. The Alembic migration must be applied to the database with `alembic upgrade head` during the next deployment, which is handled by the existing CI/CD pipeline.

## Next Phase Readiness

- LGPD-02 complete: WhatsApp opt-out handling is now LGPD Art. 18 compliant
- The Celery task scheduler (beat_schedule) should also be updated to filter patients with `messaging_stopped_at IS NOT NULL` from scheduled messaging tasks — this is a performance optimization (avoid wasted task dispatch) and can be addressed in Plan 02-03 or Phase 3
- Plan 02-03 should address the patient data export endpoint (LGPD Art. 18 portability requirement noted as research gap in STATE.md)

---
*Phase: 02-lgpd-compliance*
*Completed: 2026-02-22*
