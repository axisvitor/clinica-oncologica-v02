# M013: Remediação de Segurança Crítica/Alta

**Gathered:** 2026-05-12
**Status:** Ready for planning

## Project Description

M013 transforma o pacote de análise de segurança em correções executáveis para as fronteiras críticas/altas de PHI/LGPD do sistema de acompanhamento oncológico. O material de entrada é o relatório final `report.md`, com `validation_report.md` e `attack_path_analysis_report.md` como evidência de source/control/sink. O usuário deixou claro que a análise repassada é uma lista completa de correções e otimizações documentadas, e deu liberdade para aplicar melhores práticas.

O milestone foca F-01..F-11: WhatsApp management API sem autenticação, SSRF via media fetch, IDOR/BOLA em mensagens/quiz/flow responses/flow overrides/reports, e exposição pública de uploads privados e PDFs de paciente.

## Why This Milestone

O sistema lida com dados sensíveis de pacientes oncológicos, mensagens WhatsApp, respostas livres, quiz mensal, uploads e relatórios. Os findings críticos/altos expõem controle externo de mensageria, acesso cruzado entre médicos/pacientes e serving público de arquivos privados. Corrigir primeiro essas fronteiras reduz o risco mais imediato sem diluir o trabalho nos findings médios/deferred.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Operar WhatsApp, mensagens, quiz, uploads e relatórios com os fluxos legítimos preservados, mas sem permitir acesso anônimo ou cross-doctor/cross-patient.
- Ver uma matriz de evidência reproduzível mostrando que F-01..F-11 não reproduzem mais por testes negativos e guards compartilhados.
- Continuar usando links públicos legítimos de quiz e downloads autorizados sem fallback público inseguro.

### Entry point / environment

- Entry point: backend FastAPI `/api/v2/*`, WhatsApp/WuzAPI integration, quiz public API, upload/report endpoints, pytest security suites.
- Environment: local dev/test with FastAPI dependency overrides, mocked WuzAPI/queue where live services are unavailable, and fixture data for two doctors/two patients.
- Live dependencies involved: PostgreSQL/SQLAlchemy patterns, Dragonfly/Taskiq-adjacent flows, WuzAPI/WhatsApp boundaries via mocks or local client seams; no production PHI.

## Completion Class

- Contract complete means: F-01..F-11 have mapped fixes and negative tests proving unauthorized/foreign access fails.
- Integration complete means: shared auth/ownership controls are wired through WhatsApp, messages, quiz, uploads/reports and flow patient routes without breaking legitimate assigned-doctor/admin paths.
- Operational complete means: denial paths fail closed with diagnostic logs that omit PHI, tokens and secrets; final evidence matrix is reproducible without production services.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Anonymous requests to WhatsApp management endpoints fail before handlers execute, while authorized mocked/admin paths still work.
- Doctor A cannot access Doctor B's messages, quiz status/history/link creation, flow responses, flow overrides, upload/report downloads or report exports/history through the fixed endpoints.
- Attacker-controlled media URLs to loopback, private/link-local ranges, metadata services, invalid schemes or suspicious redirects are blocked before outbound fetch.
- Private uploads and generated report PDFs are not served by public static `/uploads` paths; authorized access goes through gated download or short-lived signed URL behavior.
- Public quiz submit cannot be driven by a forged/stolen raw `quiz_session_id`; it requires valid, non-expired, non-revoked, patient-bound session/link state.
- The milestone is not considered complete by static review alone; focused pytest/unit/route tests must pass and produce an F-01..F-11 evidence matrix.

## Architectural Decisions

### Shared controls over endpoint-only patches

**Decision:** M013 uses shared FastAPI dependencies/helpers for authentication, role checks and patient ownership wherever possible, rather than one-off checks in each vulnerable endpoint.

**Rationale:** The report found repeated broken authorization across routers. Shared controls reduce inconsistency and make future endpoints harder to misconfigure. The codebase already has patterns in `app/dependencies/auth_dependencies.py`, `app/dependencies/auth_role_dependencies.py`, `app/dependencies/business_dependencies.py` and `app/api/v2/_quiz_shared.py`.

**Alternatives Considered:**
- Patch only the cited lines — faster initially, but likely leaves inconsistent controls and weaker regression proof.

### Fail closed for PHI boundaries

**Decision:** Auth, ownership, SSRF, private file and quiz-session failures deny access by default. Ambiguous ownership is denial, not partial response.

**Rationale:** The system handles PHI/LGPD-protected data. A false positive denial is safer and easier to debug than accidental cross-patient disclosure.

**Alternatives Considered:**
- Preserve permissive fallback for compatibility — rejected because the current risk is data exposure, not harmless incompatibility.

### Private files are application resources, not public static assets

**Decision:** Private uploads and generated reports must not rely on unauthenticated `StaticFiles` serving. They must be served through authorization-aware endpoints or short-lived signed access, with public files separated from private storage.

**Rationale:** `is_public=false` is currently metadata only; public static serving bypasses the authorization layer entirely.

**Alternatives Considered:**
- Keep `/uploads` static and obscure filenames — rejected because URLs are returned/loggable and reports use deterministic names.

### Quiz public access must bind token, session and patient

**Decision:** Public quiz access must use opaque/signed state and validate token hash/link state/expiration/patient binding before accepting submit.

**Rationale:** The public quiz is intentionally reachable by patients, but raw session IDs or cookies cannot be treated as proof of authorization.

**Alternatives Considered:**
- Trust HttpOnly cookie alone — rejected because active link/session disclosure plus cookie-only submit was a high finding.

## Error Handling Strategy

- Missing/invalid authentication returns 401 and does not execute sensitive handlers.
- Authenticated principal without permission returns 403, or 404 when anti-enumeration is more appropriate for resource existence.
- Ownership not proven means denied access; no partial data response.
- SSRF guard rejects invalid schemes, private/loopback/link-local/metadata IPs, suspicious DNS resolution, and redirects that resolve to blocked targets. Timeouts are bounded.
- Private upload/report access has no public fallback. If ownership cannot be proven, the file is not served.
- Quiz public submit/access fails closed for invalid, expired, revoked or patient-mismatched state.
- Logs use structured events with request/resource identifiers where safe, but never PHI, full sensitive URLs, tokens, cookies or secrets.

## Risks and Unknowns

- Existing consumers may rely on `/uploads` URLs for private files — must preserve legitimate access through a gated replacement path.
- Quiz public flow must remain usable by real patients while rejecting forged/stolen session identifiers.
- WhatsApp management hardening must not break internal admin/service operations or queue processing.
- Shared helpers must cover model-vs-dict user contexts already present in the codebase.
- RLS is deferred unless needed for proof; app-layer authorization remains the primary M013 control.

## Existing Codebase / Prior Art

- `backend-hormonia/app/api/v2/router.py` — mounts `whatsapp_router` without a router-level auth dependency.
- `backend-hormonia/app/integrations/whatsapp/api/routes.py` — endpoints currently inject service dependencies but no principal validation.
- `backend-hormonia/app/integrations/wuzapi/media.py` — `aiohttp.ClientSession().get(url)` fetches attacker-controlled media URL without SSRF guard.
- `backend-hormonia/app/core/application_factory.py` — mounts `settings.UPLOAD_DIRECTORY` at public `/uploads` via `StaticFiles`.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — canonical session/auth dependency source.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — role-gated helpers for active/admin/doctor users.
- `backend-hormonia/app/dependencies/business_dependencies.py` — existing patient access validation pattern.
- `backend-hormonia/app/api/v2/_quiz_shared.py` — existing `_check_patient_access` helper that some vulnerable quiz paths do not use.
- `backend-hormonia/tests/validation/` and `backend-hormonia/tests/api/v2/` — existing pytest/TestClient security and API test patterns.

## Relevant Requirements

- R001 — Advances WhatsApp management API authentication/authorization.
- R002 — Advances SSRF prevention for WhatsApp/WuzAPI media fetch.
- R003 — Advances message authorization and cross-patient/cross-doctor protection.
- R004 — Advances quiz link/status/history ownership enforcement.
- R005 — Advances public quiz session/link integrity.
- R006 — Advances private upload access control.
- R007 — Advances generated report PDF confidentiality.
- R008 — Advances report download/export/share/history ownership checks.
- R009 — Advances flow response/override patient ownership.
- R010 — Provides reusable two-doctor/two-patient negative authorization proof.
- R011 — Provides fail-closed diagnostics without PHI/secrets.
- R012/R013/R014 — Deferred follow-on hardening/proof gaps for M014/M015.
- R015/R016/R017/R018 — M013 non-goals.

## Scope

### In Scope

- F-01 through F-11 from `report.md`.
- Shared auth/role/ownership helpers and wiring through affected FastAPI routers.
- SSRF guard for WuzAPI/WhatsApp media fetch.
- Private upload/report serving boundary changes.
- Quiz link/session validation for high-risk public submit/link paths.
- Focused pytest/unit/route verification with fixture data and mocks.
- Evidence matrix mapping F-01..F-11 to passing proof.

### Out of Scope / Non-Goals

- Runtime exploitation against production or data with real PHI.
- Full remediation of all medium findings unless the same control is necessary for F-01..F-11.
- Broad frontend redesign or dashboard UX changes.
- Treating local git-ignored `.env`/service-account files as committed-secret findings.
- Full production-like DB/queue/WuzAPI/Gemini harness unless required later by M015.

## Technical Constraints

- Preserve legitimate WhatsApp operation, quiz public flow and report/download use cases.
- Prefer existing project patterns (`Depends`, auth dependencies, patient access helpers, pytest/TestClient) over new security frameworks.
- Do not log secrets, tokens, cookies, PHI or full sensitive URLs.
- Tests must not require production WuzAPI/Gemini credentials or patient fixtures.
- Existing Taskiq/DB import gotchas in `.gsd/KNOWLEDGE.md` still apply.

## Integration Points

- FastAPI v2 router tree — auth/role dependencies and route behavior.
- WhatsApp/WuzAPI integration — management endpoints, queue operations and media fetch.
- PostgreSQL/SQLAlchemy models for User, Patient, Message, QuizSession, Report, Upload and flow state/override data.
- Upload/report storage — static mount, storage metadata, report generation task output.
- Quiz public and authenticated operations — link creation, active links, status/history and submit.
- Test infrastructure — pytest, TestClient/dependency overrides, mocked outbound clients and fixture users/patients.

## Testing Requirements

- Add or extend backend pytest suites for each F-01..F-11 path.
- Include unauthenticated tests for every `/api/v2/whatsapp/*` management route in scope.
- Include SSRF unit tests for invalid schemes, loopback, private ranges, link-local, metadata IPs, DNS rebinding-like resolution and redirects.
- Include two-doctor/two-patient negative authorization tests for messages, quiz, flow responses, flow overrides and reports.
- Include private file/report tests proving public static URL access fails and authorized gated access succeeds.
- Include quiz tests for forged/raw session ID, expired/revoked/mismatched link/session and valid patient flow.
- Final slice must produce an evidence matrix linking findings F-01..F-11 to commands and passing test names.

## Acceptance Criteria

### S01 — WhatsApp Auth + SSRF Guard
- Anonymous WhatsApp send/list/history/contact/queue/instance routes return 401/403 before service execution.
- Authorized admin/service-principal paths still reach mocked service behavior.
- Media fetch rejects blocked schemes, hosts, IP ranges and redirects; valid allowed HTTP(S) media still passes under size limit.

### S02 — Patient Ownership Boundary
- Doctor A cannot read/mutate Doctor B messages, flow responses or flow overrides.
- Assigned doctor and admin still access legitimate patient data.
- Shared helper behavior is covered for model and mapping-style user contexts if both are used.

### S03 — Quiz Link/Session Boundary
- Authenticated users cannot mint links or query status/history/active links for patients outside their scope.
- Public submit rejects forged/stolen raw session IDs, expired/revoked state and mismatched patient/token combinations.
- Legitimate quiz access/submit path remains functional with fixture data.

### S04 — Private Upload/Report Serving
- Private uploads are not accessible through unauthenticated static `/uploads` URLs.
- Generated patient PDFs are not written to or exposed from public deterministic paths.
- Authorized owner/admin download path works through gated access.

### S05 — Report Ownership Closure
- Direct report download/export/share/history validates generated_by or patient assignment before returning data.
- Cross-user/cross-doctor report IDs fail safely.
- Existing legitimate owner/admin report operations remain functional.

### S06 — Integrated Security Proof
- F-01..F-11 evidence matrix exists with command, test name and pass/fail status.
- Focused pytest/security suites pass.
- Denial logs/errors are useful but do not leak PHI, tokens or secrets.
- Deferred findings R012/R013/R014 are explicitly left for future milestones, not silently forgotten.

## Open Questions

- Whether RLS should be pulled into M013 will be decided only if app-layer proof for F-01..F-11 requires it; default is defer to M014.
- Exact signed/private-file access mechanism may be endpoint-based or short-lived signed URL, chosen by implementation based on existing storage patterns.
