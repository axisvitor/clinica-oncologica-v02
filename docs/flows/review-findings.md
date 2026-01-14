# Flow System Review Findings

This document captures findings from the flow system review and the resulting tickets.

## Findings (prioritized)

### P0
- None identified.

### P1
- Flow template versioning had mismatched repository signatures and model aliases, causing runtime errors when creating or publishing versions.
- Flow state transitions lacked optimistic locking and sequential step validation in the flow management layer.

### P2
- FlowKind and FlowType keys were inconsistent between backend and frontend, leading to drift in template creation and UI labels.
- Flow template CRUD endpoints allowed ambiguous step payload shapes without validation, increasing risk of invalid data.
- Analytics endpoint returned partial metrics and omitted average duration, which is required by the dashboard.

### P3
- Versioning UI lacked diff/rollback visibility and relied on manual version entry.
- Flow analytics export endpoint did not exist for CSV/JSON downloads.

## Tickets

| Priority | Ticket | Description | Estimate |
| --- | --- | --- | --- |
| P1 | FLOW-101 | Align flow template repository signatures and add is_draft column support | 0.5d |
| P1 | FLOW-102 | Enforce sequential step progression and optimistic locking in flow management | 0.5d |
| P2 | FLOW-201 | Normalize flow kind keys across backend/frontend and update docs | 0.5d |
| P2 | FLOW-202 | Validate steps payloads on template CRUD endpoints | 0.5d |
| P2 | FLOW-203 | Expand flow analytics to include duration and per-kind breakdown | 0.5d |
| P3 | FLOW-301 | Add version diff/rollback UI for flow templates | 0.5d |
| P3 | FLOW-302 | Add analytics export endpoint (CSV/JSON) | 0.5d |

## Recommendations

- Keep `FlowType` canonical keys (`onboarding`, `daily_follow_up`, `quiz_mensal`, `custom`) in new templates.
- Track version migrations explicitly in `flow_metadata` to preserve auditability.
- Extend analytics ingestion with scheduled aggregation once baseline metrics stabilize.
