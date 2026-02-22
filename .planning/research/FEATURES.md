# Feature Research

**Domain:** Healthcare WhatsApp patient monitoring — oncology remote symptom tracking with AI-humanized questionnaires
**Researched:** 2026-02-22
**Confidence:** HIGH (codebase verified) / MEDIUM (domain standards from peer-reviewed literature and production healthcare WhatsApp deployments)

---

## Context: Subsequent Milestone Framing

This is a **refinement milestone**, not a greenfield build. The prototype is functionally complete with the following already implemented:

- WhatsApp delivery via Evolution API (UnifiedWhatsAppService)
- LangGraph + Gemini AI humanization pipeline (graphs.py, nodes_ai.py)
- Periodic quiz delivery via Celery Beat (38 tasks)
- Patient flow state machine (dual systems, production + QW-021)
- Alert system with severity levels (INFO/WARNING/CRITICAL/FATAL)
- LGPD consent management, PII redaction before AI calls, encryption
- Saga pattern for patient onboarding with compensation
- Firebase Auth + session management
- Real-time dashboard via WebSocket + Redis Pub/Sub

The question is therefore: **what must be fixed, hardened, and validated before real oncology patients touch this system?** The categories below are calibrated to that context.

---

## Feature Landscape

### Table Stakes (Users Expect These — Missing = Unacceptable for Real Patients)

These are clinical and operational requirements that make the system safe and trustworthy for real-world patient use. The evidence base is the PRO-CTCAE framework (NCI), Lancet Digital Health implementation studies across 33 cancer centers, and LGPD compliance requirements under ANPD oversight.

| Feature | Why Expected | Complexity | Current Status | Notes |
|---------|--------------|------------|----------------|-------|
| **Persistent LGPD deletion audit trail** | Art. 16/18 requires immutable record of patient deletion operations; log-only approach fails regulatory audit | MEDIUM | MISSING — only written to app logs (`repositories/patient/audit.py` lines 190-205) | Must create `patient_deletion_audit` table and write before any deletion; this is a compliance blocker |
| **Patient WhatsApp opt-out handling** | Patients must be able to STOP WhatsApp messages at any time (LGPD Art. 18, Meta policy); absent = regulatory violation and account suspension risk | MEDIUM | MISSING — no "STOP" keyword handler in webhook processing | Webhook handler must detect "STOP", "PARAR", "CANCELAR" etc. and immediately halt messaging + record consent revocation |
| **Proper auth on monitoring endpoints** | Monitoring metrics cannot be publicly accessible; placeholder auth = security breach | LOW | BROKEN — `enhanced_monitoring.py` lines 84-97 uses raw DB query with `# TODO: Replace with actual auth integration` | Replace with standard `get_current_user` + role check dependency |
| **Clinical alert escalation to physician** | Research across 33 cancer centers shows physician notification (not just patient) is the most important factor in symptom monitoring effectiveness (Lancet Regional Health 2024) | MEDIUM | PARTIAL — alert system exists (`services/alerts/`) with escalation strategies, but physician availability endpoint returns empty list silently | Alert delivery confirmed working; escalation path needs validation; physician scheduling endpoint needs implementation |
| **Sync-in-async event loop fix (hot paths)** | Under load, blocking DB calls in async context cause cascading timeouts across ALL requests; with real patients, a Celery spike during quiz delivery stalls the entire API | HIGH | BROKEN — 42+ annotated instances, worst in `flow_core.py` (7), `sequential_message_handler.py` (12), `enhanced_quiz_service.py` (8) | Minimum: fix hot paths (quiz response processing, webhook handling, flow advancement); full AsyncSession migration is v2 |
| **Single flow system (decommission QW-021 or production)** | Two parallel flow engines cause double-maintenance, divergence bugs, and test coverage gaps at seam between systems | HIGH | BROKEN — dual systems coexist in `flow_core.py` + `services/flow/core/manager.py` with no integration tests between them | Pick one, migrate all patients to it, tombstone the other; divergence is a patient safety risk |
| **AI event types in audit enum** | HIPAA/LGPD audit trails must capture AI model queries and responses for regulatory reporting and clinical accountability | LOW | MISSING — `services/audit/reports.py` line 70: `# TODO: Add AI event types` | Add `AI_QUERY`, `AI_HUMANIZATION`, `AI_SENTIMENT`, `AI_FOLLOW_UP` to `AuditEventType`; add Alembic migration |
| **Batch re-encryption for key rotation** | LGPD Art. 46 requires ability to rotate encryption keys; without batch re-encryption, any security incident requiring key rotation is unrecoverable | HIGH | MISSING — `services/encryption/service.py` line 609: `# TODO: Implement batch re-encryption` | Blocking: key rotation cannot work safely without this; Celery task with chunked processing recommended |
| **Test token registry removed from production binary** | Debug bypass code shipped in production binary is an auditable security risk; Firebase bypass active when `APP_ENABLE_DEBUG=True` | LOW | EXISTS — `auth_dependencies.py` lines 43-60: `TEST_TOKEN_REGISTRY` | Move to test-only conftest; remove from production code path entirely |
| **Firebase service account key out of working directory** | Service account key on disk in any developer working directory is a credential leak risk | LOW | AT RISK — file exists at repo root, gitignored but not removed | Store via GCP Secret Manager or mounted volume; remove from disk |
| **Hardcoded metrics stubs removed** | `avg_task_duration_seconds` returns hardcoded `2.5`; physicians and admins cannot trust a dashboard that lies about system health | LOW | BROKEN — `health/service_health.py` line 129 | Instrument Celery task completion times; store rolling average in Redis via Beat task |
| **Rate limiter atomicity (Lua script)** | Race condition in distributed rate limiter under high traffic allows brief burst above limit; WhatsApp API rate limit violations cause account suspension | LOW | KNOWN BUG — `rate_limit_core.py` lines 184-205; Lua script template already in comment | Apply Lua script from existing comment; low effort, high risk if ignored |
| **asyncio.run() replaced with async_to_sync in Celery tasks** | Memory leak from new event loop per call; at 38 periodic tasks with high frequency, this accumulates | LOW | KNOWN BUG — `tasks/flows/flow_tasks.py`; fix pattern already applied in `trigger_tasks.py` and `helpers.py` | Standardize all Celery tasks to `async_to_sync` from asgiref |
| **python-jose import sweep** | Package removed for CVE-2024-23342; any remaining `from jose import` causes silent runtime import failure | LOW | AT RISK — confirmed removal in requirements.txt but no import sweep validated | Grep sweep for `from jose`; replace with `import jwt` (pyjwt) |
| **LangGraph startup health check** | Guarded imports with `None` fallbacks mean LangGraph failures silently no-op; with real patients, silent degradation = unhumanized clinical messages sent undetected | LOW | BROKEN — `ai/langgraph/runtime.py`, `graphs.py`, `consensus.py` use try/except with None | Add startup health check verifying LangGraph availability; convert None fallbacks to `FeatureNotAvailableError` |

---

### Differentiators (Competitive Advantage in Healthcare AI)

These are where this system can be meaningfully better than alternatives. The core differentiator is AI-humanized oncology questionnaires via WhatsApp — not EHR integration, not wearables, not video calls. The evidence from JMIR Cancer, PMC, and ASCO confirms this niche is underserved and clinically validated.

| Feature | Value Proposition | Complexity | Current Status | Notes |
|---------|-------------------|------------|----------------|-------|
| **LangGraph humanization graph (validated and hardened)** | Template-based messages sound robotic; AI humanization per patient context significantly improves response rates; breast cancer chatbot study (PMC6521209) showed patients feel more comfortable disclosing to non-judgmental AI; this is the core product value | MEDIUM | PARTIAL — `graphs.py` has `build_humanization_graph()` with `humanize_node`, `sentiment_node`, `question_variation_node`, `empathetic_follow_up_node` but LangGraph import is fragile | Harden the import path, add startup validation, add fallback behavior (send template without humanization vs silent fail) |
| **Sentiment-aware follow-up escalation** | Negative sentiment detected in patient responses triggers empathetic follow-up before clinical alert; reduces false positives and improves patient relationship | MEDIUM | PARTIAL — `NEGATIVE_SENTIMENT` alert rule type exists in `AlertRuleType`; `sentiment_node` in nodes_ai.py; integration with alert escalation needs verification | Verify sentiment detection → alert escalation pipeline is end-to-end connected |
| **Emergency keyword detection** | Patient types "EMERGÊNCIA", "socorro", "dor intensa" → immediate physician notification; literal life-safety feature | MEDIUM | PARTIAL — `EMERGENCY_KEYWORDS` in `AlertRuleType`; needs threshold configuration and response time SLA | Must be tested with real keyword variations in Portuguese; response time < 1 hour SLA should be defined |
| **AI audit trail for clinical accountability** | Every AI-generated message logged with input context, model version, and output; allows physician to review what AI said to patient and why | LOW | MISSING — audit enum doesn't capture AI events (see Table Stakes above) | Directly enables clinical trust; low complexity once audit enum is fixed |
| **PII-safe AI pipeline** | Patient data never reaches Gemini; `pii_redaction.py` strips identifiers before AI calls; differentiates from naive AI integrations that send full PHI to LLMs | LOW | IMPLEMENTED — `app/ai/pii_redaction.py` with explicit allowlist/blocklist | Competitive moat; ensure it is tested and documented |
| **Continuous monitoring between consultations** | Weekly/monthly questionnaires between visits detect problems before the next appointment; Lancet study of 33 centers showed 70% of alerts managed without ER visit | HIGH | PARTIAL — Celery Beat sends questionnaires; flow state machine tracks engagement; alert thresholds configurable | Core clinical value; depends on fixing dual flow systems and alert pipeline reliability |
| **Physician dashboard with real-time patient status** | Oncologist sees all patients' current engagement, recent responses, and active alerts in real-time without checking each individually | MEDIUM | PARTIAL — WebSocket + Redis pub/sub + React admin frontend exist; `flow_monitoring.py` (923 lines) provides status aggregation; WebSocket in-memory = no multi-instance scaling | Address WebSocket scaling (Redis pub/sub already exists via `redis_pubsub_manager.py`); verify dashboard data accuracy |

---

### Anti-Features (Deliberately NOT Build at This Stage)

These are either scope-creep risks, known overengineering patterns for a single-clinic rollout, or features that would add complexity without clinical value at this stage.

| Anti-Feature | Why Requested | Why Avoid | What to Do Instead |
|--------------|---------------|-----------|-------------------|
| **Autonomous AI clinical recommendations** | "AI can suggest treatment changes" | Research and Lancet Digital Health confirm AI overtrust is the primary risk with healthcare LLMs; patients view AI responses as valid as doctors even when wrong (PMC12325106); this clinic has no regulatory clearance for AI clinical decisions | Keep AI role strictly as humanizer/empathizer of fixed clinical templates; never let AI generate clinical content |
| **Real-time chat with patients** | "WhatsApp is a chat app, let patients message freely" | Unstructured patient messages require 24/7 clinical triage; out of scope per PROJECT.md; Evolution API webhook already handles structured responses | Continue structured questionnaire flow only; unrecognized messages routed to DLQ with physician notification |
| **EHR/HIS integration** | "Connect to hospital records" | Adds external API dependency, security surface, and onboarding complexity; clinic uses this as standalone; not in current scope per PROJECT.md | Export capability (patient data export in CSV/JSON) satisfies data portability under LGPD Art. 18 |
| **Multi-tenant / multi-clinic** | "Other clinics want this too" | Architecture is single-tenant; adding multi-tenancy requires schema isolation, billing, onboarding — a separate product; current codebase has no tenant scoping | Document as v2 product decision; do not add tenant_id columns or routing logic now |
| **Wearable device integration** | "Patients could wear a monitor" | Zero code exists for this; adds hardware dependency and FDA/ANVISA regulatory pathway; clinical value at this stage is unproven vs questionnaire approach | Validate questionnaire approach clinically first before adding data sources |
| **Whatsapp Live Chat (nurse/physician reply via same number)** | "Make it a two-way conversation" | WhatsApp Business API requires message templates for outbound; live chat requires a shared inbox product (Chatwoot, etc.) separate from this system | If physicians need to message patients directly, they use personal WhatsApp — separate channel |
| **Full AsyncSession migration (all 42+ methods at once)** | "Just migrate everything to async" | This is a multi-week project requiring schema query changes throughout; doing it all at once creates large diff, high regression risk, and review bottleneck | Migrate hot paths only: webhook handling, quiz response processing, flow advancement; annotate remainder for v2 |
| **Redux/Zustand global state in frontend** | "The admin frontend needs better state management" | Current React Query + Context pattern is adequate; adding a global store now is premature optimization; out of scope (UI redesign excluded per PROJECT.md) | Keep current frontend patterns; fix backend data accuracy issues instead |
| **Celery Beat HA (redbeat) at launch** | "What if Beat crashes?" | Single Beat instance is adequate for a clinic with <500 patients; adding redbeat adds operational complexity; Beat restarts are recoverable within minutes | Document the risk; add monitoring/alerting when Beat heartbeat is missed; implement HA when patient volume justifies it |

---

## Feature Dependencies

```
[LGPD Deletion Audit Table]
    └──required by──> [Patient Delete CRUD] (patients cannot be deleted safely without it)
    └──required by──> [LGPD Compliance Certification]

[AI Audit Enum (AI_QUERY, AI_HUMANIZATION)]
    └──required by──> [AI Audit Trail for Clinical Accountability]
    └──required by──> [Full LGPD/HIPAA Audit Coverage]

[Batch Re-Encryption]
    └──required by──> [Encryption Key Rotation]
    └──required by──> [Security Incident Response Capability]

[Single Flow System (dual decommission)]
    └──required by──> [Reliable Alert Pipeline] (alerts read from one flow state)
    └──required by──> [Patient Flow Integration Tests]
    └──required by──> [Physician Dashboard Data Accuracy]

[Sync-in-Async Hot Path Fix]
    └──required by──> [System Stability Under Load]
    └──required by──> [Webhook Reliability] (webhook handler is the primary patient interaction)

[WhatsApp Opt-Out Handling]
    └──required by──> [LGPD Art. 18 Compliance]
    └──required by──> [Meta WhatsApp Business API Policy Compliance] (account not suspended)

[LangGraph Startup Health Check]
    └──required by──> [AI Humanization Reliability]
    └──required by──> [Silent Degradation Prevention]

[Rate Limiter Atomicity]
    └──required by──> [WhatsApp API Rate Compliance] (prevents account suspension)

[Proper Monitoring Auth]
    └──required by──> [Production Security Posture]

[Sentiment Detection → Alert Escalation Pipeline]
    └──requires──> [Single Flow System] (reads from one consistent flow state)
    └──requires──> [Emergency Keyword Detection] (complementary rule)

[Emergency Keyword Detection]
    └──enhances──> [Clinical Alert Escalation to Physician]
    └──requires──> [Alert Severity Thresholds Configured] (Portuguese keyword list)

[Physician Dashboard Accuracy]
    └──requires──> [Single Flow System]
    └──requires──> [WebSocket Scaling Fix] (multi-instance consistency)
    └──requires──> [Hardcoded Metrics Stubs Removed]
```

### Dependency Notes

- **Single Flow System is a root dependency**: Fixing the dual flow coexistence unblocks alert pipeline reliability, physician dashboard data accuracy, and integration test coverage. It should be the first major technical work.
- **LGPD features are independent but time-critical**: Deletion audit trail, batch re-encryption, and AI audit enum can each be done in isolation. They must be done before first real patient, not after.
- **Auth fixes are independent and quick**: Monitoring endpoint auth and test token registry removal are each under 1 hour of work but have security implications. Do these early.
- **Opt-out handling depends only on webhook infrastructure**: WhatsApp STOP handling requires adding keyword detection to the webhook handler; no flow system changes needed.

---

## Production-Readiness Requirements Specific to Healthcare/LGPD

These are not features per se, but production gate criteria before any real patient can use the system.

### Security Gates (All Must Pass)

| Requirement | Evidence Basis | Current Gap |
|-------------|---------------|-------------|
| No placeholder auth in production endpoints | OWASP API Security Top 10; ANPD inspection risk | `enhanced_monitoring.py` placeholder auth |
| No debug bypass code in production binary | LGPD accountability principle; audit risk | `TEST_TOKEN_REGISTRY` in production code path |
| Firebase service account key not on disk | Credential management best practice | File exists at repo root |
| Default JWT secret key rejected even in dev | Credential hygiene; dev habits bleed to prod | `security.py` line 19 default insecure value |
| `APP_ENABLE_DEBUG=False` enforced in staging and production | Debug endpoints expose DB environment data | Requires deployment config validation |

### Compliance Gates (All Must Pass for First Real Patient)

| Requirement | LGPD Article | Current Gap |
|-------------|-------------|-------------|
| Patient deletion produces immutable audit record | Art. 16/18 | Logs only, not DB-persisted |
| Consent revocation stops messaging immediately | Art. 18 §2 | No opt-out webhook handler |
| Encryption key rotation is operationally possible | Art. 46 | Batch re-encryption not implemented |
| AI actions are auditable (what AI sent, when, with what context) | Art. 37 (accountability) | AI events not in audit enum |
| Patient data export available on request | Art. 18 (portability) | Export endpoint exists (`import_export.py`) — validate it works |

### Observability Gates (Must Have Before Real Patients)

| Requirement | Why | Current Gap |
|-------------|-----|-------------|
| LangGraph availability confirmed at startup | Silent AI failure = robotic messages to cancer patients undetected | Guarded imports with None fallbacks |
| Celery Beat liveness monitoring | If Beat dies, no questionnaires are sent — patients fall off protocol | No Beat heartbeat alerting configured |
| Webhook delivery failure visibility | Missed patient messages are invisible without DLQ monitoring | DLQ exists; verify metrics surfaced to dashboard |
| Real health metrics (no hardcoded stubs) | Physicians and admins need to trust system health data | `avg_task_duration_seconds` hardcoded at 2.5 |

---

## MVP Definition (Production Readiness Phasing)

### Must Be Done Before First Real Patient (v0 → v1)

These are blockers. None can be deferred.

- [x] ~~WhatsApp delivery works~~ (already implemented)
- [x] ~~Quiz questionnaire flow works~~ (already implemented)
- [x] ~~LGPD consent management~~ (already implemented)
- [ ] Fix placeholder auth on monitoring endpoints
- [ ] Remove test token registry from production binary
- [ ] Add persistent LGPD deletion audit table
- [ ] Implement WhatsApp opt-out (STOP keyword) handling
- [ ] Add AI event types to audit enum + migration
- [ ] Implement LangGraph startup health check
- [ ] Fix asyncio.run() → async_to_sync in all Celery tasks (memory leak fix)
- [ ] Apply Lua script to rate limiter (atomic operations)
- [ ] Sweep and remove any remaining `from jose import` statements
- [ ] Confirm `APP_ENABLE_DEBUG=False` in staging and production deployment

### Add After First Patient Cohort (v1.x — Within First 30 Days)

These significantly improve reliability but are not day-one blockers if the patient cohort is small.

- [ ] Consolidate dual flow systems — pick production or QW-021, decommission the other
- [ ] Fix sync-in-async hot paths (webhook, quiz response, flow advancement)
- [ ] Implement physician availability slots (currently returns empty silently)
- [ ] Implement batch re-encryption capability (needed before key rotation event)
- [ ] Add integration tests for single flow system + alert pipeline
- [ ] WebSocket scaling: verify Redis pub/sub integration handles multi-instance
- [ ] Remove hardcoded metrics stubs; instrument real task duration metrics

### Defer to v2 (After Clinical Validation)

- [ ] Full AsyncSession migration (all 42+ methods) — requires major architectural work
- [ ] Celery Beat HA with redbeat — justified only at >500 patients
- [ ] Multi-tenant architecture — separate product decision
- [ ] Wearable/device data integration
- [ ] EHR/HIS integration

---

## Feature Prioritization Matrix

| Feature | Patient Safety Value | Compliance Value | Implementation Cost | Priority |
|---------|---------------------|-----------------|---------------------|----------|
| LGPD deletion audit table | MEDIUM | HIGH | LOW | P1 |
| WhatsApp opt-out handling | HIGH | HIGH | MEDIUM | P1 |
| Monitoring endpoint auth fix | MEDIUM | HIGH | LOW | P1 |
| AI audit enum | LOW | HIGH | LOW | P1 |
| LangGraph startup health check | HIGH | MEDIUM | LOW | P1 |
| asyncio.run → async_to_sync | MEDIUM | LOW | LOW | P1 |
| Rate limiter Lua script | MEDIUM | MEDIUM | LOW | P1 |
| Test token registry removal | MEDIUM | HIGH | LOW | P1 |
| python-jose import sweep | HIGH | MEDIUM | LOW | P1 |
| Dual flow consolidation | HIGH | MEDIUM | HIGH | P2 |
| Sync-in-async hot paths | HIGH | LOW | HIGH | P2 |
| Physician availability slots | MEDIUM | LOW | MEDIUM | P2 |
| Batch re-encryption | LOW | HIGH | HIGH | P2 |
| WebSocket multi-instance scaling | MEDIUM | LOW | MEDIUM | P2 |
| Hardcoded metrics stub removal | LOW | LOW | LOW | P2 |
| Full AsyncSession migration | MEDIUM | LOW | VERY HIGH | P3 |
| Celery Beat HA (redbeat) | MEDIUM | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have before first real patient
- P2: Should have within first 30 days of operation
- P3: Defer until volume justifies complexity

---

## Competitor Feature Analysis

This system occupies a specific niche: WhatsApp-based ePRO (electronic patient-reported outcomes) for oncology in Brazil. The relevant comparisons are not generic chatbot platforms but dedicated ePRO and remote patient monitoring systems.

| Feature | Dedicated ePRO Systems (Medidata Rave, ICON, etc.) | Generic WhatsApp Healthcare Platforms (BotMD, ChatArchitect) | This System |
|---------|----------------------------------------------------|-------------------------------------------------------------|-------------|
| Validated questionnaire frameworks (PRO-CTCAE, ESAS) | YES — clinical gold standard | NO — generic forms | PARTIAL — custom templates, not standardized frameworks |
| Alert escalation to clinical team | YES | PARTIAL | YES — alert system with escalation strategies |
| EHR/HIS integration | YES | PARTIAL | NO (out of scope) |
| WhatsApp delivery | NO — email/app | YES | YES |
| AI humanization of clinical messages | NO | NO | YES — core differentiator |
| LGPD compliance | N/A (US-focused) | PARTIAL | YES — explicit LGPD compliance layer |
| Brazil Portuguese language native | NO | PARTIAL | YES |
| Cost (clinic perspective) | Very high (enterprise) | Medium | Low (self-hosted) |

The system's competitive advantage is clear: WhatsApp delivery + AI humanization + LGPD compliance + Portuguese-native in a single integrated system. No competitor combines all four. The risk is operational reliability — clinical systems must work every time.

---

## Sources

- [Optimization of alert notifications in ePRO remote symptom monitoring (PMC11825061)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11825061/) — alert threshold research, 38% suppression finding
- [Implementation of remote symptom monitoring in 33 cancer centres, Lancet Regional Health 2024](https://www.thelancet.com/journals/lanepe/article/PIIS2666-7762(24)00172-8/fulltext) — physician notification as key factor
- [How Should Oncologists Choose an ePRO System, JMIR 2021](https://www.jmir.org/2021/9/e30549) — system selection criteria, EHR integration, real-time alerts
- [Remote Oncology Care: Review of Current Technology, PMC7526951](https://pmc.ncbi.nlm.nih.gov/articles/PMC7526951/) — clinical benefits overview
- [When Chatbots Meet Patients: One-Year Study, PMC6521209](https://pmc.ncbi.nlm.nih.gov/articles/PMC6521209/) — breast cancer chatbot acceptance
- [LLM Risks in Consumer Health, PMC12325106](https://pmc.ncbi.nlm.nih.gov/articles/PMC12325106/) — AI overtrust risk in healthcare
- [Generative AI consumer health framework, Frontiers Digital Health 2025](https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1616488/full) — clinical safety with LLMs
- [LangGraph in Production, LangChain Blog](https://blog.langchain.com/is-langgraph-used-in-production/) — production use including healthcare (Komodo Health)
- [WhatsApp Business API Healthcare Compliance Guide](https://tringtring.ai/blog/whatsapp-ai/compliance-guide-whatsapp-business-api-regulations-by-country/) — Brazil LGPD + Meta policy
- [LGPD Compliance Checklist, Captain Compliance 2026](https://captaincompliance.com/education/lgpd-compliance-checklist/) — Art. 16/18 deletion requirements
- [Healthcare SaaS Compliance Checklist, Neumetric](https://www.neumetric.com/journal/compliance-checklist-for-healthcare-saas-2566/) — audit trail, consent management
- [PRO-CTCAE Overview, NCI](https://healthcaredelivery.cancer.gov/pro-ctcae/overview.html) — validated symptom reporting framework
- Codebase analysis: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/` — all gaps verified directly in code

---

*Feature research for: Healthcare WhatsApp oncology patient monitoring (production refinement milestone)*
*Researched: 2026-02-22*
