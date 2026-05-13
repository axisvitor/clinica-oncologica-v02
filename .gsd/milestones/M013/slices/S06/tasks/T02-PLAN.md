---
estimated_steps: 14
estimated_files: 1
skills_used: []
---

# T02: Assemble the F-01..F-11 critical/high evidence matrix

Expected executor skills/frontmatter: `estimated_steps: 6`, `estimated_files: 1`, `skills_used: [write-docs, security-review, verify-before-complete]`.

Why: M013's final success criterion requires a consolidated evidence matrix rather than relying on scattered task summaries. The matrix must be understandable by a fresh reviewer and must not silently close medium/proof-gap/runtime follow-ups.

Files: create `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`.

Do:
1. Read the M013 context/requirements and completed slice summaries as inputs, then create a concise evidence matrix document under the backend security reports directory.
2. Include a short scope section: M013 covers F-01..F-11 critical/high findings; R012/R013/R014 remain deferred; R015-R018 are non-goals/out-of-scope unless already documented otherwise in requirements.
3. Add a table with one row per finding F-01 through F-11. Each row must include: finding ID, risk surface, requirement IDs, fixed control, primary test files, verification command class, expected S06 fresh evidence field, and PHI-safe diagnostics/negative-test note.
4. Map the known surfaces from completed slices: F-01 WhatsApp management auth (R001), F-02 WuzAPI SSRF/media redirects (R002), message read/list/conversation/read-state/send/bulk/delete/cancel boundaries (R003), flow responses/flow overrides (R009), authenticated quiz ownership (R004), public quiz token/session/logout/submit boundaries (R005), private upload/static serving (R006), generated report artifact privacy (R007), and report download/export/share/history/builder/restore ownership (R008).
5. Add a reusable R010 section naming `backend-hormonia/tests/api/v2/security_boundary_helpers.py` and the two-doctor/two-patient negative suites that consume it.
6. Add an R011 diagnostics section summarizing what denied paths may log/return (IDs, status, reason, failure type) and what they must not expose (PHI, message content, quiz answers, free-text flow response values, tokens, cookies, private paths, URLs, secrets).
7. Add a Deferred Follow-ups section for R012 medium hardening, R013 proof gaps, and R014 production-like runtime harness, with no `TODO`/`TBD` placeholders.

Threat Surface (Q3): the document itself is not runtime-executed, but it must not copy PHI/tokens/private URLs from tests or logs; use synthetic labels and command names only.

Requirement Impact (Q4): documents R001-R011 validation evidence and explicitly preserves R012-R014 as deferred instead of treating them as complete.

Negative Tests (Q7): executable doc validation must prove all F/R IDs are present and placeholders/sentinel unsafe strings are absent.

## Inputs

- `.gsd/REQUIREMENTS.md`
- `.gsd/milestones/M013/M013-CONTEXT.md`
- `.gsd/milestones/M013/M013-ROADMAP.md`
- `.gsd/milestones/M013/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M013/slices/S02/S02-SUMMARY.md`
- `.gsd/milestones/M013/slices/S03/S03-SUMMARY.md`
- `.gsd/milestones/M013/slices/S04/S04-SUMMARY.md`
- `.gsd/milestones/M013/slices/S05/S05-SUMMARY.md`
- `backend-hormonia/tests/api/v2/security_boundary_helpers.py`

## Expected Output

- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`

## Verification

python - <<'PY'
from pathlib import Path
p = Path('backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md')
text = p.read_text(encoding='utf-8')
assert all(f'F-{i:02d}' in text for i in range(1, 12))
for rid in [f'R{i:03d}' for i in range(1, 15)]:
    assert rid in text, rid
for forbidden in ['TODO', 'TBD', 'patient-name', 'jane-doe', 'secret-token']:
    assert forbidden.lower() not in text.lower(), forbidden
assert text.count('| F-') >= 11
PY

## Observability Impact

Creates a durable reviewer-facing inspection surface that ties each critical/high boundary to its verification command and safe diagnostic contract.
