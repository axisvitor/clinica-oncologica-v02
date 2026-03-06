---
phase: 44
slug: adk-runtime-controls
status: passed
verified_on: 2026-03-06
requirements:
  - ADK-09
  - ADK-10
verifier: Codex
---

# Phase 44 Verification

## Verdict

Phase 44 is **passed** for the automated and local evidence scope. Phase 48 closes the missing verification chain by linking the shipped Phase 44 summaries, the runtime/session control code paths, and fresh green pytest evidence for ADK-09 and ADK-10 while explicitly deferring the staging-only multi-instance cancel check to Phase 49.

## Must-Have Checks

| Check | Requirement | Result | Evidence |
|---|---|---|---|
| `max_llm_calls` is accepted as an explicit per-invocation runtime override | ADK-09 | Pass | `backend-hormonia/app/schemas/v2/adk.py:10-24`; `backend-hormonia/app/ai/adk/runtime.py:181-194,631-632`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:472-502` |
| Timeout is enforced at the runtime boundary and recorded as a terminal invocation status | ADK-09 | Pass | `backend-hormonia/app/ai/adk/runtime.py:220-283,627-628`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:441-468` |
| Explicit cancellation marks the invocation terminal instead of leaving it running | ADK-09 | Pass | `backend-hormonia/app/ai/adk/session_store.py:287-302`; `backend-hormonia/app/ai/adk/runtime.py:366-416`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:506-552` |
| Late results are discarded after cancellation | ADK-09 | Pass | `backend-hormonia/app/ai/adk/session_store.py:304-316`; `backend-hormonia/app/ai/adk/runtime.py:226-242`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:506-552` |
| Route validation rejects cancel requests without an invocation id | ADK-09 | Pass | `backend-hormonia/app/schemas/v2/adk.py:139-151`; `backend-hormonia/tests/api/v2/test_adk.py:275-299` |
| Cancelling an invocation does not close the owning session | ADK-09 | Pass | `backend-hormonia/app/ai/adk/session_store.py:138-152,287-316`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:506-552` |
| A session is auto-created when no `session_id` is supplied | ADK-10 | Pass | `backend-hormonia/app/ai/adk/runtime.py:474-526`; `backend-hormonia/app/ai/adk/session_store.py:94-110`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:338-367` |
| Resume is allowed only within the same `tool_name` and merges prior bounded context | ADK-10 | Pass | `backend-hormonia/app/ai/adk/session_store.py:206-242`; `backend-hormonia/app/ai/adk/runtime.py:474-501`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:595-637` |
| Closed sessions are rejected on reuse | ADK-10 | Pass | `backend-hormonia/app/ai/adk/session_store.py:216-217`; `backend-hormonia/app/ai/adk/runtime.py:529-566`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:407-438` |
| Explicit close transitions the session to the terminal `closed` state | ADK-10 | Pass | `backend-hormonia/app/ai/adk/session_store.py:138-152`; `backend-hormonia/app/ai/adk/runtime.py:431-472`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:371-403` |
| Resume-time bounded-state pruning preserves high-value context before execution continues | ADK-10 | Pass | `backend-hormonia/app/ai/adk/session_store.py:193-203,228-242,384-410`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:595-637` |
| Resume is rejected when the session still exceeds the configured budget after pruning | ADK-10 | Pass | `backend-hormonia/app/ai/adk/session_store.py:228-240`; `backend-hormonia/app/ai/adk/runtime.py:545-550`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:555-591` |
| Route validation rejects close requests without a `session_id` | ADK-10 | Pass | `backend-hormonia/app/schemas/v2/adk.py:134-137`; `backend-hormonia/tests/api/v2/test_adk.py:250-271` |
| Session state size accounting is persisted alongside each bounded session payload | ADK-10 | Pass | `backend-hormonia/app/ai/adk/session_store.py:94-108,193-203,228-233`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:555-637` |

## Requirement Coverage

| Requirement | Status | Notes |
|---|---|---|
| ADK-09 | Pass | Phase 44 summaries, runtime/session store code, and fresh pytest evidence confirm per-invocation limit, timeout, cancel, and late-result discard behavior. The only remaining manual check is the multi-instance cancel topology already assigned to Phase 49. |
| ADK-10 | Pass | Phase 44 summaries, lifecycle code, and fresh pytest evidence confirm create/resume/close flows, bounded state pruning, and oversized resume rejection within the local verification scope. |

## Evidence

### 1. Phase 44 artifacts still trace directly to ADK-09 and ADK-10

- The roadmap still defines Phase 48 as the closeout for orphaned ADK-09 and ADK-10 verification evidence at `.planning/ROADMAP.md:40-53`.
- Phase 44 plan summaries already claim the corresponding deliverables: explicit lifecycle contract and session store in `.planning/phases/44-adk-runtime-controls/44-01-SUMMARY.md:9-32,49-52`, timeout/budget/cancel behavior in `.planning/phases/44-adk-runtime-controls/44-02-SUMMARY.md:9-30,47-50`, and bounded-state plus regression lock coverage in `.planning/phases/44-adk-runtime-controls/44-03-SUMMARY.md:9-34,51-54`.
- The Phase 44 validation map already listed the same verification surface and commands at `.planning/phases/44-adk-runtime-controls/44-VALIDATION.md:37-46`, which Phase 48 reran to refresh the evidence chain instead of inventing new tests.

### 2. ADK-09 runtime limit and cancellation semantics are implemented and regression-covered

- Per-invocation runtime controls are part of the request contract in `backend-hormonia/app/schemas/v2/adk.py:10-24`, then normalized into the execution payload in `backend-hormonia/app/ai/adk/runtime.py:181-194,627-632`.
- Timeout is enforced around the execution boundary in `backend-hormonia/app/ai/adk/runtime.py:220-283`, and the matching runtime regression proves the `timeout` terminal state in `backend-hormonia/tests/unit/test_adk_tools_runtime.py:441-468`.
- LLM budget exhaustion is surfaced as `limit_exceeded` in `backend-hormonia/app/ai/adk/runtime.py:303-321`, with regression coverage at `backend-hormonia/tests/unit/test_adk_tools_runtime.py:472-502`.
- Cancellation is explicit and terminal in `backend-hormonia/app/ai/adk/runtime.py:366-416` and `backend-hormonia/app/ai/adk/session_store.py:287-316`; the cancel regression proves both the operator cancel response and the suppressed late result at `backend-hormonia/tests/unit/test_adk_tools_runtime.py:506-552`.
- Route-level validation rejects malformed cancel requests before dispatch in `backend-hormonia/app/schemas/v2/adk.py:139-151`, covered by `backend-hormonia/tests/api/v2/test_adk.py:275-299`.

### 3. ADK-10 session lifecycle and bounded-state semantics are implemented and regression-covered

- Session lifecycle resolution happens before runtime execution in `backend-hormonia/app/ai/adk/runtime.py:421-526`, backed by persistent session metadata created in `backend-hormonia/app/ai/adk/session_store.py:94-110`.
- Auto-create behavior is verified at `backend-hormonia/tests/unit/test_adk_tools_runtime.py:338-367`.
- Explicit close transitions the session into a terminal `closed` state in `backend-hormonia/app/ai/adk/session_store.py:138-152` and `backend-hormonia/app/ai/adk/runtime.py:431-472`, with regression coverage at `backend-hormonia/tests/unit/test_adk_tools_runtime.py:371-403`.
- Resume rejects closed sessions and other invalid reuse states via `backend-hormonia/app/ai/adk/session_store.py:206-242` and `backend-hormonia/app/ai/adk/runtime.py:474-566`, with regression coverage at `backend-hormonia/tests/unit/test_adk_tools_runtime.py:407-438`.
- Bounded-state pruning and size accounting live in `backend-hormonia/app/ai/adk/session_store.py:193-203,228-242,384-410`; resume-prune and oversized rejection are covered by `backend-hormonia/tests/unit/test_adk_tools_runtime.py:555-637`.
- Route-level close validation is enforced in `backend-hormonia/app/schemas/v2/adk.py:134-137` and covered by `backend-hormonia/tests/api/v2/test_adk.py:250-271`.

### 4. Fresh pytest evidence is green

- Full Phase 44 verification suite rerun on 2026-03-06:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py tests/unit/test_adk_tools_runtime.py tests/unit/test_adk_runner_integration.py -q
```

Observed output:

```text
.............................sss              [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/unit/test_adk_runner_integration.py:29: google-adk not installed
SKIPPED [1] tests/unit/test_adk_runner_integration.py:58: google-adk not installed
SKIPPED [1] tests/unit/test_adk_runner_integration.py:96: google-adk not installed
```

- Focused ADK-09 rerun on 2026-03-06:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/unit/test_adk_tools_runtime.py -q -k "timeout or limit or cancel"
```

Observed output:

```text
...                                                                      [100%]
```

- Focused ADK-10 rerun on 2026-03-06:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/unit/test_adk_tools_runtime.py -q -k "session or lifecycle or prune or close or resume or oversized"
```

Observed output:

```text
.....                                                                    [100%]
```

## Remaining Human Validation

- `44-VALIDATION.md` still records the cross-instance cancel confirmation as manual-only at `.planning/phases/44-adk-runtime-controls/44-VALIDATION.md:60-64`.
- That gap is explicitly deferred, not ignored: `.planning/ROADMAP.md:55-64` assigns the staging multi-instance cancel proof to Phase 49.

## Final Assessment

Phase 44 now has a complete verification chain for ADK-09 and ADK-10: the roadmap goal, plan summaries, runtime/session control code, and fresh pytest evidence all line up, and the only remaining non-local check is already routed to Phase 49 as a staging validation item rather than a blocker to this closeout.

**Final status: `passed`**
