# Pitfalls Research

**Domain:** Brownfield ADK stability, runtime diagnostics, and observability hardening for a healthcare WhatsApp backend (LGPD-bound)
**Researched:** 2026-03-05
**Confidence:** HIGH for platform/runtime pitfalls, MEDIUM for ADK ecosystem volatility

## Critical Pitfalls

### Pitfall 1: PHI leakage through ADK debug logs and observability payloads

**What goes wrong:**
Teams enable ADK `DEBUG` logging in production during incident response, which can include full LLM prompts, tool args, and conversation context. In healthcare flows, this often contains patient identifiers and clinical details.

**Why it happens:**
ADK logging docs explicitly position `DEBUG` for troubleshooting and show detailed request dumps; brownfield teams under pressure toggle global log level instead of a scoped diagnostic path.

**How to avoid:**
1. Enforce production log level policy (`INFO`/`WARNING`) at process startup; reject `DEBUG` in production env by guard code.
2. Add a centralized redaction pipeline for `patient_name`, CPF, phone, diagnosis, free-text symptoms before log sink and before Sentry event submission.
3. Keep `send_default_pii=False` in Sentry, use `before_send` and `before_send_transaction` scrubbing for spans/breadcrumbs.
4. Create a short-lived "diagnostic mode" flag scoped by request/session ID, with automatic expiry and explicit approval path.

**Warning signs:**
- Sudden jump in log payload size on ADK routes (`/api/v2/adk/run`).
- Sentry event payloads containing route fragments with identifiers (e.g., raw IDs in transaction names).
- On-call runbook includes "set log level DEBUG globally" as first troubleshooting step.

**Phase to address:**
Phase 1 - ADK Guardrails & Privacy Contracts (before additional diagnostics are introduced).

---

### Pitfall 2: Broken correlation across FastAPI -> Celery -> ADK execution chain

**What goes wrong:**
You can see individual failures but cannot reconstruct one patient journey end-to-end. Incidents stay "untriageable" because request IDs, task IDs, and ADK invocation/session IDs are not linked.

**Why it happens:**
OTel was removed; teams often replace telemetry partially (logs only) without a minimum correlation contract across async boundaries.

**How to avoid:**
1. Define mandatory correlation keys: `request_id`, `patient_id_hash`, `celery_task_id`, `adk_invocation_id`, `adk_session_id`, `flow_id`.
2. Propagate these keys explicitly in FastAPI context, Celery task headers/kwargs, and ADK runner invocation metadata.
3. Fail CI on new ADK endpoints/tasks that do not emit correlation keys in structured logs.
4. Add one smoke test that triggers webhook -> Celery -> ADK and asserts all IDs appear in joined logs.

**Warning signs:**
- On-call needs manual timestamp matching to connect API and worker failures.
- Same user incident appears as 3+ unrelated alerts across systems.
- Post-incident report uses "likely related" instead of deterministic trace chain.

**Phase to address:**
Phase 2 - Observability Replacement Baseline (OBS-01).

---

### Pitfall 3: Retry semantics cause duplicate patient messages

**What goes wrong:**
ADK or provider transient failures trigger retries, but outbound WhatsApp send is not idempotent; patients receive duplicated follow-up questions or contradictory instructions.

**Why it happens:**
Brownfield systems already use Celery retries/circuit breakers; ADK error handling is added on top without harmonizing idempotency keys and acknowledgement policy.

**How to avoid:**
1. Enforce idempotency key format `{patient_id}:{flow_step}:{message_type}:{time_bucket}` for outbound sends.
2. Persist send-attempt ledger before provider call; short-circuit if key already finalized.
3. Align Celery retry policy with provider SLA (exponential backoff + jitter + max retries + dead-letter path).
4. Classify errors into retryable vs non-retryable; do not autoretry validation/contract errors.

**Warning signs:**
- Increase in patient complaints of repeated messages.
- DLQ growth for send tasks with same payload hash.
- High retry count with similar failure reason and no idempotency suppression metric.

**Phase to address:**
Phase 3 - Runtime Error Hardening & Idempotency.

---

### Pitfall 4: ADK callback/tool contract drift silently bypasses safety controls

**What goes wrong:**
After ADK upgrades, callback signatures or tool context contracts change; the safety hook still "runs" but no longer blocks unsafe tool invocations or fails open.

**Why it happens:**
ADK release cadence is fast and includes breaking changes; brownfield teams pin loosely and rely on smoke-only checks rather than policy-behavior tests.

**How to avoid:**
1. Pin ADK to tested minor version; upgrade only through a contract test suite.
2. Add explicit tests for `before_tool_callback`/`before_agent_callback` behavior (block/allow cases) using synthetic PHI and malicious prompt input.
3. Maintain a small "compatibility matrix" doc mapping app wrappers to ADK version assumptions.
4. Add startup assertion that expected callback hooks are registered and invoked at least once in health smoke.

**Warning signs:**
- Dependency bumps pass unit tests but incident rate rises on tool misuse.
- Callback logs exist, but blocked-call counters drop to near zero.
- Security controls only validated manually, not by CI.

**Phase to address:**
Phase 1 - ADK Guardrails & Privacy Contracts.

---

### Pitfall 5: Session strategy mismatch makes runtime diagnostics unreliable

**What goes wrong:**
Production uses ephemeral/in-memory ADK sessions in multi-instance deployment, so context disappears on restart/scale events and incident replay is impossible.

**Why it happens:**
InMemory sessions are easiest to start with and work in local tests; teams defer durable session architecture while adding production features.

**How to avoid:**
1. For production ADK paths, use durable session storage (`DatabaseSessionService` or equivalent controlled store).
2. Define retention windows by data class (minimal PHI, strict TTL) and deletion workflows aligned to LGPD rights.
3. Add replay-safe diagnostics endpoint using hashed identifiers only.
4. Include schema migration checks in deploy pipeline (ADK session schema has changed across releases).

**Warning signs:**
- "Works until pod restart" behavior in ADK-driven conversations.
- Session-not-found spikes after deploys/autoscaling.
- Postmortems blocked because prior invocation state cannot be recovered.

**Phase to address:**
Phase 2 - Observability Replacement Baseline (OBS-01), with migration checks before rollout.

---

### Pitfall 6: Metric cardinality explosion blinds alerts and increases cost

**What goes wrong:**
Teams add observability quickly and label metrics with patient, phone, message text hash, tool args, or model prompt fragments. Time series blow up; dashboards slow; alerts become noisy or throttled.

**Why it happens:**
Brownfield migrations from OTel often overcompensate by adding every "useful" dimension directly as labels.

**How to avoid:**
1. Whitelist low-cardinality labels only (`agent_name`, `tool_name`, `error_type`, `provider`, `status_code_group`).
2. Keep patient-level context in logs (hashed), not metrics dimensions.
3. Set SLO-driven metrics first: p50/p95 latency, success rate, retry rate, timeout rate, circuit-open rate.
4. Add a cardinality budget check in staging before enabling new metrics.

**Warning signs:**
- Rapid growth in active series count after deploy.
- Query latency and dashboard timeouts in monitoring backend.
- Alert fatigue caused by fragmented, per-label noisy rules.

**Phase to address:**
Phase 2 - Observability Replacement Baseline (OBS-02).

---

### Pitfall 7: Error taxonomy collapse (everything becomes HTTP 500)

**What goes wrong:**
ADK, provider, validation, and policy failures are collapsed into generic 500s. Operations cannot triage quickly, and automated mitigation (retry vs stop vs escalate) fails.

**Why it happens:**
Wrapper layers are added fast; exception translation is skipped or performed only at endpoint boundary.

**How to avoid:**
1. Define explicit error classes and mapping table: `PolicyBlocked`, `ValidationError`, `ProviderTimeout`, `ProviderQuota`, `ToolExecutionError`, `SessionStateError`.
2. Map each class to HTTP status, retry policy, alert severity, and runbook action.
3. Emit structured error fields (`error_code`, `retryable`, `safe_message`, `correlation_keys`).
4. Add contract tests verifying error mapping for top failure modes.

**Warning signs:**
- >70% ADK failures logged as generic internal error.
- On-call triage starts with "reproduce locally" because logs lack machine-actionable error code.
- Retry queue receives validation/policy errors that should be non-retryable.

**Phase to address:**
Phase 3 - Runtime Error Hardening & Contracts.

---

### Pitfall 8: Big-bang rollout of ADK hardening without shadow validation

**What goes wrong:**
New wrapper/diagnostics/alerting stack is switched on globally. Latency regressions or policy false-positives immediately impact active patient follow-ups.

**Why it happens:**
Brownfield teams treat stability work as internal-only and skip phased rollout because "no product feature changed".

**How to avoid:**
1. Run shadow mode: execute ADK path in parallel for sampled traffic without affecting patient-facing output.
2. Gate progression by explicit thresholds (latency delta, error budget burn, duplicate-message rate, PHI leak count = 0).
3. Roll out by cohort/clinic and maintain instant rollback switch.
4. Freeze non-essential infra changes during reliability rollout window.

**Warning signs:**
- First meaningful load test is production traffic.
- No pre/post baseline for ADK latency and error rates.
- Rollback requires code deploy instead of config/feature flag.

**Phase to address:**
Phase 4 - Controlled Rollout, Alerting, and Runbook Validation.

---

## Technical Debt Patterns

Shortcuts that feel fast but create reliability/compliance debt.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use global `DEBUG` logs during incidents | Fast visibility | PHI exposure risk and noisy logs | Never in production healthcare data paths |
| Keep ad-hoc correlation IDs per module | Quick local debugging | Impossible end-to-end incident reconstruction | Never |
| Add retries without idempotency ledger | Fewer transient failures | Duplicate patient messages and trust erosion | Never |
| Pin ADK loosely (`^1.x`) | Fewer dependency chores | Silent behavior drift on callbacks/tools | Only in non-prod experimentation |
| Put patient identifiers as metric labels | Fast filtering in dashboards | Cardinality explosion and observability outages | Never |

## Integration Gotchas

Common mistakes when integrating ADK into this existing production stack.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI -> ADK Runner | Calling ADK without propagating request context | Pass correlation metadata (request/flow/invocation IDs) into every run |
| Celery -> ADK | Retrying tool/model failures blindly | Retry only retryable classes with backoff+jitter and idempotency key |
| ADK callbacks + PIISafe wrapper | Assuming wrapper is enough without callback tests | Enforce callback behavior tests for block/allow and PHI redaction paths |
| Sentry + structured logs | Relying on default scrubbing only | Keep `send_default_pii=False`, custom scrubber, `before_send` hooks |
| ADK session service + multi-instance deploy | Using in-memory sessions in production | Use durable session service and verify migration compatibility |

## Performance Traps

Patterns that pass staging but fail under production load.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full payload logging for every ADK call | CPU/log I/O spikes, slower response times | Sample debug logs by correlation ID only | Often at first traffic spike (>100 concurrent flows) |
| Single worker pool for long and short tasks | Queue latency oscillation | Route long-running diagnostics separately | At moderate sustained load (10-15 min queue growth) |
| Missing timeout budgets between layers | Requests pile up, cascading failures | Set per-hop timeouts and end-to-end budget | During provider slowdowns/outages |
| No metric cardinality budget | Monitoring backend degradation | Enforce low-cardinality label policy | Immediately after rich labels rollout |

## Security Mistakes

Domain-specific risks beyond generic web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging raw prompt/tool payloads with health data | LGPD non-compliance and breach risk | Redact-before-log, default INFO, scoped diagnostics only |
| Persisting session state with unnecessary PHI | Enlarged blast radius in incidents | Data minimization + TTL + hashed identifiers |
| Missing tool-level authorization guardrails | Unauthorized record access/exfiltration | In-tool policy checks + callback enforcement |
| Unescaped model output in downstream UIs | Prompt-injection-to-XSS path | Escape/sanitize model output before rendering |

## "Looks Done But Isn't" Checklist

- [ ] **Correlation:** One incident can be traced API -> Celery -> ADK with deterministic IDs.
- [ ] **Privacy:** `DEBUG` disabled in production and redaction tests cover logs + Sentry.
- [ ] **Retries:** Duplicate-send prevention metric exists and is green under retry test.
- [ ] **Errors:** Top ADK failure modes map to explicit error codes and runbook actions.
- [ ] **Sessions:** Production uses durable session backend; restart does not lose active context.
- [ ] **Metrics:** Cardinality budget check passes before enabling new dimensions.
- [ ] **Rollout:** Shadow-mode baseline and rollback switch validated before full enablement.

## Recovery Strategies

When pitfalls happen despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| PHI in logs/Sentry | HIGH | Rotate access, scrub/erase retained events where possible, notify DPO/incident process, patch redaction and logging level guards |
| Broken API->Celery->ADK correlation | MEDIUM | Hotfix correlation propagation headers/fields, replay one failed scenario, update dashboard joins |
| Duplicate patient sends from retries | HIGH | Stop outbound queue, dedupe pending tasks by idempotency key, send corrective communication workflow |
| Callback contract drift after ADK upgrade | MEDIUM | Roll back ADK version, re-run contract suite, release behind feature flag |
| Monitoring collapse from high cardinality | MEDIUM | Drop high-cardinality labels, purge/disable offending series, restore SLO-only dashboard set |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| PHI leakage via debug telemetry | Phase 1 - Guardrails & Privacy Contracts | Redaction tests green; production log policy rejects DEBUG |
| Callback/tool contract drift | Phase 1 - Guardrails & Privacy Contracts | Contract tests pass against pinned ADK version |
| Correlation gaps across runtime boundaries | Phase 2 - Observability Baseline (OBS-01) | Single flow trace includes all required IDs |
| Session durability/diagnostic blind spots | Phase 2 - Observability Baseline (OBS-01) | Session survives restart and replay diagnostics work |
| Metric cardinality explosion | Phase 2 - Observability Baseline (OBS-02) | Cardinality budget and dashboard latency within target |
| Duplicate sends from retries | Phase 3 - Runtime Hardening | Retry tests show zero duplicate outbound sends |
| Error taxonomy collapse | Phase 3 - Runtime Hardening | Error mapping contract tests for major failure classes |
| Big-bang rollout regressions | Phase 4 - Controlled Rollout & Runbook | Shadow KPIs pass and rollback switch tested |

## Sources

- ADK Observability Logging (DEBUG includes full prompts; production guidance): https://google.github.io/adk-docs/observability/logging/ (HIGH)
- ADK Safety/Security (guardrails, callback-based validation, tool controls): https://google.github.io/adk-docs/safety/ (HIGH)
- ADK Callback types and lifecycle hooks: https://google.github.io/adk-docs/callbacks/types-of-callbacks/ (HIGH)
- ADK Sessions and persistence options (InMemory/Database/Vertex): https://google.github.io/adk-docs/sessions/session/ (HIGH)
- ADK release notes pointer + fast release cadence: https://google.github.io/adk-docs/release-notes/ (HIGH)
- ADK Python releases (breaking changes, bug-fix churn, session/observability changes): https://github.com/google/adk-python/releases (MEDIUM-HIGH)
- OpenTelemetry guidance on handling sensitive data: https://opentelemetry.io/docs/security/handling-sensitive-data/ (MEDIUM)
- Sentry Python sensitive-data scrubbing and `send_default_pii`: https://docs.sentry.io/platforms/python/data-management/sensitive-data/ (HIGH)
- Celery task idempotency/retry semantics and late-ack caveats: https://docs.celeryq.dev/en/stable/userguide/tasks.html (HIGH)
- Celery optimization and prefetch/reliability tradeoffs: https://docs.celeryq.dev/en/stable/userguide/optimizing.html (HIGH)
- LGPD legal basis/principles for sensitive health data (Lei 13.709/2018): https://planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm (HIGH)

---
*Pitfalls research for: Clinica Oncologica - v1.8 ADK Stability & Error Hardening milestone*
*Researched: 2026-03-05*
