# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

## Validated

### R001 — A API de gestão WhatsApp deve exigir autenticação e autorização antes de permitir envio, leitura, histórico, contatos, filas ou instâncias.
- Class: compliance/security
- Status: validated
- Description: A API de gestão WhatsApp deve exigir autenticação e autorização antes de permitir envio, leitura, histórico, contatos, filas ou instâncias.
- Why it matters: A API controla mensagens e dados PHI; acesso anônimo permite controle externo do canal clínico.
- Source: report
- Primary owning slice: M013/S01
- Supporting slices: M013/S06
- Validation: M013/S01 verified WhatsApp management API auth with focused and final pytest evidence: gsd_exec af1fd56e-266a-44f6-91f3-f4b4fb948c14 and 75ac52dd-e00f-4c71-9f54-244766a9885b passed. Tests cover anonymous/non-admin rejection before service/queue/DB execution, public /api/v2/whatsapp/health, and an authorized admin mocked send operation.
- Notes: Validated by S01; downstream S06 should include this proof in the consolidated security evidence matrix.

### R002 — O fetch de mídia WhatsApp/WuzAPI deve bloquear SSRF por esquema, host, DNS/IP privado, loopback, link-local, metadados cloud, redirects suspeitos e timeout.
- Class: compliance/security
- Status: validated
- Description: O fetch de mídia WhatsApp/WuzAPI deve bloquear SSRF por esquema, host, DNS/IP privado, loopback, link-local, metadados cloud, redirects suspeitos e timeout.
- Why it matters: Media URLs são entrada controlada por atacante e podem forçar o servidor a acessar rede interna ou metadata services.
- Source: report
- Primary owning slice: M013/S01
- Supporting slices: M013/S06
- Validation: M013/S01 verified WuzAPI media SSRF protections with focused and final pytest evidence: gsd_exec 5c8857c7-87d3-4d91-8853-b038a4d5c49f and 75ac52dd-e00f-4c71-9f54-244766a9885b passed. Tests cover blocked schemes, malformed/missing hosts, userinfo, invalid/zero ports, localhost/private/loopback/link-local/multicast/unspecified/reserved/CGNAT/metadata IPs, DNS failure/mixed answers, no GET before validation, manual redirect validation with allow_redirects=False, safe redirects, data-URI behavior, and sanitized unsafe/oversize messages.
- Notes: Validated by S01; downstream S06 should include this proof in the consolidated security evidence matrix.

### R003 — Rotas de mensagens devem impedir leitura ou mutação cross-patient/cross-doctor por filtros, IDs diretos, read-state ou conversation endpoints.
- Class: compliance/security
- Status: validated
- Description: Rotas de mensagens devem impedir leitura ou mutação cross-patient/cross-doctor por filtros, IDs diretos, read-state ou conversation endpoints.
- Why it matters: Mensagens carregam PHI e histórico clínico; IDOR em mensagens quebra isolamento médico/paciente.
- Source: report
- Primary owning slice: M013/S02
- Supporting slices: M013/S06
- Validation: M013/S02 verified message read/list/conversation/unread/read-state/send/bulk-send/delete/cancel boundaries with `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exit 0; 1 expected skip for rate limiting disabled).
- Notes: Shared admin-or-assigned-doctor patient ownership helper now gates patient-bound message routes before DB/cache/service side effects; doctor-owned and admin regressions remain passing.

### R004 — Usuários autenticados só podem emitir links e consultar status/histórico de quiz mensal para pacientes sob seu escopo autorizado.
- Class: compliance/security
- Status: validated
- Description: Usuários autenticados só podem emitir links e consultar status/histórico de quiz mensal para pacientes sob seu escopo autorizado.
- Why it matters: Quiz mensal contém sintomas e dados clínicos; permitir patient_id arbitrário vaza PHI e possibilita abuso de link.
- Source: report
- Primary owning slice: M013/S03
- Supporting slices: M013/S06
- Validation: S03 verified authenticated monthly-quiz link creation, status/history, and active-link listing with admin-or-assigned-doctor ownership. Evidence: focused ownership pytest selection exited 0; full S03 proof `tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q` plus planning-artifact audit exited 0.
- Notes: Validated by M013/S03. Foreign-doctor patient_id tampering fails closed before quiz session/token side effects; doctor active-link lists are scoped before PHI serialization while admin/assigned-doctor flows remain functional.

### R005 — O fluxo público do quiz deve aceitar apenas sessão/link opaco, válido, não expirado, não revogado e alinhado ao paciente/token estabelecido pelo acesso correto.
- Class: compliance/security
- Status: validated
- Description: O fluxo público do quiz deve aceitar apenas sessão/link opaco, válido, não expirado, não revogado e alinhado ao paciente/token estabelecido pelo acesso correto.
- Why it matters: O quiz público cruza uma fronteira autenticado→público; uma sessão forjada ou vazada pode gravar respostas no paciente errado.
- Source: report
- Primary owning slice: M013/S03
- Supporting slices: M013/S06
- Validation: S03 verified public quiz current/access/submit/session/logout boundaries for token hash, active link state, signed compatibility session state, patient/template/session binding, and expiration. Evidence: focused public-token and compatibility pytest selections exited 0; full S03 proof `tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q` plus planning-artifact audit exited 0.
- Notes: Validated by M013/S03. Public quiz routes now require signed access/token state plus persisted active QuizSession metadata and reject raw-cookie-only, forged, mismatched, expired, cancelled/used, and token-hash-mismatched states before payload reads or response writes.

### R006 — Uploads marcados como privados não podem ser servidos por rota estática pública; acesso privado deve passar por autenticação e ownership.
- Class: compliance/security
- Status: validated
- Description: Uploads marcados como privados não podem ser servidos por rota estática pública; acesso privado deve passar por autenticação e ownership.
- Why it matters: URLs de upload podem vazar por logs, UI ou compartilhamento; `is_public=false` precisa ser controle real, não apenas metadado.
- Source: report
- Primary owning slice: M013/S04
- Supporting slices: M013/S06
- Validation: M013/S04 verified by `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q` (gsd_exec d7459df8-9e7f-4901-9d7f-28d9d12eb170). Proof covers private upload responses without public `/uploads` URLs, public static denial for private files/derivatives, owner/admin gated download success, and anonymous/foreign/deleted/missing/path-traversal failure cases.
- Notes: Cobre F-07. Separar público/privado ou substituir serving privado por endpoint autenticado; sem fallback público para conteúdo PHI.

### R007 — PDFs e relatórios de paciente gerados por workers não podem ficar em caminho público determinístico sem autorização de download.
- Class: compliance/security
- Status: validated
- Description: PDFs e relatórios de paciente gerados por workers não podem ficar em caminho público determinístico sem autorização de download.
- Why it matters: Relatórios de paciente são PHI concentrado; caminhos determinísticos sob `/uploads/reports` permitem acesso público se a URL for conhecida.
- Source: report
- Primary owning slice: M013/S04
- Supporting slices: M013/S05, M013/S06
- Validation: M013/S06 closed the generated-report artifact/log leakage gap. Fresh closeout evidence: `gsd_exec 0214b6c3-6df3-41f8-a0c9-e81f101ee3de` ran `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q` with exit 0, proving report artifacts use opaque report-id filenames under the private report root and Taskiq diagnostics omit free-form `report_type`; `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008` ran the full S06 integrated security pytest selection with exit 0; matrix validation `gsd_exec ae46a726-c6a3-412b-8305-58a1a316e379` passed.
- Notes: S06/T01 implemented report-id-only `{report_id}.pdf` paths and PHI-safe task diagnostics that retain task/report/status/reason/failure_type observability without raw or sanitized report_type exposure.

### R008 — Downloads, exportações, compartilhamento e histórico de relatórios no escopo M013 devem validar ownership ou patient assignment antes de retornar dados.
- Class: compliance/security
- Status: validated
- Description: Downloads, exportações, compartilhamento e histórico de relatórios no escopo M013 devem validar ownership ou patient assignment antes de retornar dados.
- Why it matters: Listagem filtrada não protege download direto por UUID; relatórios podem expor dados clínicos completos.
- Source: report
- Primary owning slice: M013/S05
- Supporting slices: M013/S04, M013/S06
- Validation: S05 report ownership closure passed focused and integrated backend pytest gates from `backend-hormonia`: `pytest tests/api/v2/test_report_ownership_closure.py -q` and `pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q`. These tests prove base/enhanced report download, export, share/public-link/share listing, builder, history and restore surfaces authorize against raw owner/patient evidence before data, redirects, or download URLs are returned.
- Notes: Validated by M013/S05. Remaining milestone-wide evidence matrix and R010/R011 proof aggregation are left to S06.

### R009 — Respostas livres e overrides de fluxo do paciente devem exigir admin ou médico responsável pelo paciente antes de leitura ou alteração.
- Class: compliance/security
- Status: validated
- Description: Respostas livres e overrides de fluxo do paciente devem exigir admin ou médico responsável pelo paciente antes de leitura ou alteração.
- Why it matters: Respostas livres e conteúdo personalizado podem conter informações clínicas sensíveis e plano de comunicação individual.
- Source: report
- Primary owning slice: M013/S02
- Supporting slices: M013/S06
- Validation: M013/S02 verified flow response and flow override GET/PUT ownership denial and assigned-doctor/admin positives with `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exit 0; boundary suite includes flow-response/override tests).
- Notes: `flow_responses.py` and `flow_overrides.py` now call `load_patient_with_access` before patient-bound response/override queries or mutations; PUT audit attribution resolves actor UUID via shared auth utilities and fails closed when unresolved.

### R010 — O M013 deve deixar uma prova negativa reutilizável de isolamento médico/paciente com dois médicos, pacientes cruzados e endpoints críticos exercitados.
- Class: quality-attribute
- Status: validated
- Description: O M013 deve deixar uma prova negativa reutilizável de isolamento médico/paciente com dois médicos, pacientes cruzados e endpoints críticos exercitados.
- Why it matters: Correções de autorização só são confiáveis quando o caminho proibido é exercitado e falha de forma verificável.
- Source: inferred
- Primary owning slice: M013/S06
- Supporting slices: M013/S02, M013/S03, M013/S04, M013/S05
- Validation: M013/S06 fresh integrated proof `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008` exited 0 for patient ownership helpers/boundaries, messages, RBAC, quiz link/session, private upload, report ownership, enhanced reports, report task, and compatibility suites. The evidence matrix validation `gsd_exec ae46a726-c6a3-412b-8305-58a1a316e379` confirmed F-01..F-11 and R001..R014 mapping with Fresh S06 exit-0 evidence and deferred R012-R014 called out.
- Notes: S06 evidence matrix consolidates the reusable negative isolation proof inherited from S02/S03/S05 across two-doctor/two-patient patient ownership, messages, flow responses/overrides, quiz, uploads, and reports.

### R011 — Falhas de autenticação, autorização, SSRF, arquivo privado e quiz inválido devem falhar fechado e emitir sinais diagnósticos sem PHI, tokens ou segredos.
- Class: failure-visibility
- Status: validated
- Description: Falhas de autenticação, autorização, SSRF, arquivo privado e quiz inválido devem falhar fechado e emitir sinais diagnósticos sem PHI, tokens ou segredos.
- Why it matters: Segurança clínica precisa de bloqueio seguro e capacidade de investigar tentativas negadas sem vazar mais dados.
- Source: inferred
- Primary owning slice: M013/S06
- Supporting slices: M013/S01, M013/S02, M013/S03, M013/S04, M013/S05
- Validation: M013/S06 fresh focused and integrated proof passed: `gsd_exec 0214b6c3-6df3-41f8-a0c9-e81f101ee3de` validated report-task PHI-safe artifact/log behavior; `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008` validated fail-closed auth, SSRF, ownership, quiz, private-file, and report boundaries; document validation `gsd_exec 4808c7f0-2d25-498d-b6b6-5bb59fe37ad0` and `gsd_exec ae46a726-c6a3-412b-8305-58a1a316e379` confirmed the matrix has no TODO/TBD or unsafe sentinel values and retains Fresh S06 exit-0 evidence.
- Notes: S06 preserves failure visibility through allowed diagnostic fields and matrix notes while forbidding PHI, tokens, unsafe paths, patient-name sentinels, and report_type leakage in proof artifacts.

### R012 — Corrigir e provar hardening médio remanescente: ADK auth, RLS, DB TLS, reset replay, CSRF, webhook replay, PHI client cache, deployment secrets e duplicate oracle.
- Class: compliance/security
- Status: validated
- Description: Corrigir e provar hardening médio remanescente: ADK auth, RLS, DB TLS, reset replay, CSRF, webhook replay, PHI client cache, deployment secrets e duplicate oracle.
- Why it matters: Os findings médios ainda importam para defesa em profundidade, mas não devem diluir a remediação crítica/alta de M013.
- Source: report
- Primary owning slice: M015/S01
- Supporting slices: M015/S05
- Validation: Validated by M014/S05 controlled proof and `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`: backend integrated command passed with 149 tests, frontend persistence command passed with 5 tests, quiz storage command passed with 8 tests. Matrix rows close CSRF, reset replay, webhook replay, duplicate oracle, XFF/rate-limit, ADK, PHI cache, upload/report artifact, JWT/config posture, and explicitly defer live DB TLS/RLS/runtime proof to R014/M015.
- Notes: M015 plans to close the remaining runtime DB TLS/RLS proof boundary from M014 using a local TLS-enabled PostgreSQL service and RLS fixtures; already-proven controlled hardening items remain prior evidence rather than being reopened.

### R013 — Fechar proof gaps deferred: upload stored-XSS, ADK session ownership, JWT revocation multi-worker, X-Forwarded-For/rate-limit e quiz frontend lane incompleta.
- Class: failure-visibility
- Status: validated
- Description: Fechar proof gaps deferred: upload stored-XSS, ADK session ownership, JWT revocation multi-worker, X-Forwarded-For/rate-limit e quiz frontend lane incompleta.
- Why it matters: Lacunas deferred não devem desaparecer; precisam de owner explícito para revisão posterior.
- Source: report
- Primary owning slice: M015/S02
- Supporting slices: M015/S05
- Validation: M015/S02 fresh runtime closeout validates the deferred cross-process session/JWT revocation proof boundary through gsd_exec evidence: a1a0c466-dbbe-4c8a-8422-ee9ebe587cfe passed runner syntax, Compose config, seam listing, and unknown/omitted seam fail-closed checks; 16c8d3a4-5224-458b-a882-6afa0c6091b9 passed the backend session runtime/canonical identity pytest suite; 41eb6f1b-39f7-4de2-a56c-2b4996f68050 passed task-level auth revocation and runner-contract regressions; 4b0a9e6d-0e98-4439-b24f-2bacd530f513 ran the real M015 session seam across FastAPI, Dragonfly, PostgreSQL, and Taskiq with exit 0; 826e2e68-b5b1-4385-b57f-e2832a07c241 confirmed durable session evidence is redaction-valid and contains the expected current, legacy-denied, cache-fallback, stale revoked/expired denial, explicit revocation invalidation, and worker DB re-check outcomes.
- Notes: S02 closes the runtime session/cache/DB/worker proof gap for R013 using synthetic-only evidence. S05 still needs to fold this proof into the final M015 matrix alongside provider and artifact seams; this update does not claim live provider, production data, browser/frontend, CDN/object-storage, or all-seam closure guarantees.

## Deferred

### R014 — Construir harness runtime completo com DB, queue, WuzAPI/Gemini e fixtures production-like se a validação dinâmica ampla exigir esse ambiente.
- Class: quality-attribute
- Status: deferred
- Description: Construir harness runtime completo com DB, queue, WuzAPI/Gemini e fixtures production-like se a validação dinâmica ampla exigir esse ambiente.
- Why it matters: A análise original não executou runtime exploitation por falta de dependências; um harness futuro pode transformar isso em regressão dinâmica ampla.
- Source: inferred
- Primary owning slice: M015/S01
- Supporting slices: M015/S02, M015/S03, M015/S04, M015/S05
- Validation: Not validated by M014 unless the milestone is explicitly re-scoped; evidence matrix must avoid claiming live-provider/production-like guarantees.
- Notes: M015 roadmap maps this deferred runtime harness requirement across the full milestone: S01 establishes the synthetic runtime stack and DB TLS/RLS proof; S02-S04 close session/queue/provider/artifact seams; S05 validates evidence completeness and strict red-signal closure.

## Out of Scope

### R015 — M013 não executa exploração contra produção nem usa dados reais de paciente para provar vulnerabilidades.
- Class: anti-feature
- Status: out-of-scope
- Description: M013 não executa exploração contra produção nem usa dados reais de paciente para provar vulnerabilidades.
- Why it matters: Exploração em produção ou com dados reais aumentaria risco operacional e de privacidade sem necessidade para planejar correções.
- Source: inferred
- Primary owning slice: M015/S01
- Supporting slices: M015/S02, M015/S03, M015/S04, M015/S05
- Validation: M014/S05 evidence matrix and operational verification must document commands as controlled and PHI/secret-safe.
- Notes: M015 keeps the anti-feature boundary explicit: the validation harness is synthetic-only and excludes production exploitation, real PHI, live provider credentials, browser/frontend validation, and CDN/object-storage guarantees.

### R016 — M013 não reescreve o frontend/dashboard nem redesenha UX salvo mudança mínima necessária para fechar F-01..F-11.
- Class: anti-feature
- Status: out-of-scope
- Description: M013 não reescreve o frontend/dashboard nem redesenha UX salvo mudança mínima necessária para fechar F-01..F-11.
- Why it matters: O objetivo do milestone é fechar fronteiras de segurança críticas/altas, não iniciar redesign ou refatoração visual ampla.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Privacidade local do dashboard/quiz e melhorias UX ficam para M014 salvo acoplamento direto com os findings críticos/altos.

### R017 — M013 não trata arquivos locais git-ignored como segredo commitado do repositório.
- Class: anti-feature
- Status: out-of-scope
- Description: M013 não trata arquivos locais git-ignored como segredo commitado do repositório.
- Why it matters: Evita gastar M013 em falso positivo de repositório quando os riscos críticos/altos ativos estão em authz, SSRF e serving privado.
- Source: report
- Primary owning slice: M015/S05
- Supporting slices: M015/S01, M015/S02, M015/S03, M015/S04
- Validation: Each M014 slice includes PHI-safe diagnostics criteria; S05 performs final artifact review through the evidence matrix.
- Notes: M015 maps PHI-safe evidence and diagnostics to the final matrix/redaction gate, with every seam required to produce sanitized logs, stub captures, runner output, and evidence rows.

### R018 — M013 não corrige todos os findings médios se eles não sustentarem a prova dos riscos críticos/altos.
- Class: anti-feature
- Status: out-of-scope
- Description: M013 não corrige todos os findings médios se eles não sustentarem a prova dos riscos críticos/altos.
- Why it matters: Manter foco evita uma remediação larga demais e mal provada.
- Source: inferred
- Primary owning slice: M015/S05
- Supporting slices: M015/S01, M015/S02, M015/S03, M015/S04
- Validation: M014/S05 evidence matrix row M014-17 validates that independent medium findings were not silently dropped: every R012/R013/R018-relevant lane is listed with closed, not-applicable, or deferred status and executable matrix validation.
- Notes: M015 maps no-silent-drop proof accounting to the final evidence matrix and validator: every M014-deferred runtime item must be fresh evidence, explicit non-goal, or fixed outcome.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | compliance/security | validated | M013/S01 | M013/S06 | M013/S01 verified WhatsApp management API auth with focused and final pytest evidence: gsd_exec af1fd56e-266a-44f6-91f3-f4b4fb948c14 and 75ac52dd-e00f-4c71-9f54-244766a9885b passed. Tests cover anonymous/non-admin rejection before service/queue/DB execution, public /api/v2/whatsapp/health, and an authorized admin mocked send operation. |
| R002 | compliance/security | validated | M013/S01 | M013/S06 | M013/S01 verified WuzAPI media SSRF protections with focused and final pytest evidence: gsd_exec 5c8857c7-87d3-4d91-8853-b038a4d5c49f and 75ac52dd-e00f-4c71-9f54-244766a9885b passed. Tests cover blocked schemes, malformed/missing hosts, userinfo, invalid/zero ports, localhost/private/loopback/link-local/multicast/unspecified/reserved/CGNAT/metadata IPs, DNS failure/mixed answers, no GET before validation, manual redirect validation with allow_redirects=False, safe redirects, data-URI behavior, and sanitized unsafe/oversize messages. |
| R003 | compliance/security | validated | M013/S02 | M013/S06 | M013/S02 verified message read/list/conversation/unread/read-state/send/bulk-send/delete/cancel boundaries with `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exit 0; 1 expected skip for rate limiting disabled). |
| R004 | compliance/security | validated | M013/S03 | M013/S06 | S03 verified authenticated monthly-quiz link creation, status/history, and active-link listing with admin-or-assigned-doctor ownership. Evidence: focused ownership pytest selection exited 0; full S03 proof `tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q` plus planning-artifact audit exited 0. |
| R005 | compliance/security | validated | M013/S03 | M013/S06 | S03 verified public quiz current/access/submit/session/logout boundaries for token hash, active link state, signed compatibility session state, patient/template/session binding, and expiration. Evidence: focused public-token and compatibility pytest selections exited 0; full S03 proof `tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_phase25_messages_quiz_async.py -q` plus planning-artifact audit exited 0. |
| R006 | compliance/security | validated | M013/S04 | M013/S06 | M013/S04 verified by `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q` (gsd_exec d7459df8-9e7f-4901-9d7f-28d9d12eb170). Proof covers private upload responses without public `/uploads` URLs, public static denial for private files/derivatives, owner/admin gated download success, and anonymous/foreign/deleted/missing/path-traversal failure cases. |
| R007 | compliance/security | validated | M013/S04 | M013/S05, M013/S06 | M013/S06 closed the generated-report artifact/log leakage gap. Fresh closeout evidence: `gsd_exec 0214b6c3-6df3-41f8-a0c9-e81f101ee3de` ran `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q` with exit 0, proving report artifacts use opaque report-id filenames under the private report root and Taskiq diagnostics omit free-form `report_type`; `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008` ran the full S06 integrated security pytest selection with exit 0; matrix validation `gsd_exec ae46a726-c6a3-412b-8305-58a1a316e379` passed. |
| R008 | compliance/security | validated | M013/S05 | M013/S04, M013/S06 | S05 report ownership closure passed focused and integrated backend pytest gates from `backend-hormonia`: `pytest tests/api/v2/test_report_ownership_closure.py -q` and `pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q`. These tests prove base/enhanced report download, export, share/public-link/share listing, builder, history and restore surfaces authorize against raw owner/patient evidence before data, redirects, or download URLs are returned. |
| R009 | compliance/security | validated | M013/S02 | M013/S06 | M013/S02 verified flow response and flow override GET/PUT ownership denial and assigned-doctor/admin positives with `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exit 0; boundary suite includes flow-response/override tests). |
| R010 | quality-attribute | validated | M013/S06 | M013/S02, M013/S03, M013/S04, M013/S05 | M013/S06 fresh integrated proof `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008` exited 0 for patient ownership helpers/boundaries, messages, RBAC, quiz link/session, private upload, report ownership, enhanced reports, report task, and compatibility suites. The evidence matrix validation `gsd_exec ae46a726-c6a3-412b-8305-58a1a316e379` confirmed F-01..F-11 and R001..R014 mapping with Fresh S06 exit-0 evidence and deferred R012-R014 called out. |
| R011 | failure-visibility | validated | M013/S06 | M013/S01, M013/S02, M013/S03, M013/S04, M013/S05 | M013/S06 fresh focused and integrated proof passed: `gsd_exec 0214b6c3-6df3-41f8-a0c9-e81f101ee3de` validated report-task PHI-safe artifact/log behavior; `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008` validated fail-closed auth, SSRF, ownership, quiz, private-file, and report boundaries; document validation `gsd_exec 4808c7f0-2d25-498d-b6b6-5bb59fe37ad0` and `gsd_exec ae46a726-c6a3-412b-8305-58a1a316e379` confirmed the matrix has no TODO/TBD or unsafe sentinel values and retains Fresh S06 exit-0 evidence. |
| R012 | compliance/security | validated | M015/S01 | M015/S05 | Validated by M014/S05 controlled proof and `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`: backend integrated command passed with 149 tests, frontend persistence command passed with 5 tests, quiz storage command passed with 8 tests. Matrix rows close CSRF, reset replay, webhook replay, duplicate oracle, XFF/rate-limit, ADK, PHI cache, upload/report artifact, JWT/config posture, and explicitly defer live DB TLS/RLS/runtime proof to R014/M015. |
| R013 | failure-visibility | validated | M015/S02 | M015/S05 | M015/S02 fresh runtime closeout validates the deferred cross-process session/JWT revocation proof boundary through gsd_exec evidence: a1a0c466-dbbe-4c8a-8422-ee9ebe587cfe passed runner syntax, Compose config, seam listing, and unknown/omitted seam fail-closed checks; 16c8d3a4-5224-458b-a882-6afa0c6091b9 passed the backend session runtime/canonical identity pytest suite; 41eb6f1b-39f7-4de2-a56c-2b4996f68050 passed task-level auth revocation and runner-contract regressions; 4b0a9e6d-0e98-4439-b24f-2bacd530f513 ran the real M015 session seam across FastAPI, Dragonfly, PostgreSQL, and Taskiq with exit 0; 826e2e68-b5b1-4385-b57f-e2832a07c241 confirmed durable session evidence is redaction-valid and contains the expected current, legacy-denied, cache-fallback, stale revoked/expired denial, explicit revocation invalidation, and worker DB re-check outcomes. |
| R014 | quality-attribute | deferred | M015/S01 | M015/S02, M015/S03, M015/S04, M015/S05 | Not validated by M014 unless the milestone is explicitly re-scoped; evidence matrix must avoid claiming live-provider/production-like guarantees. |
| R015 | anti-feature | out-of-scope | M015/S01 | M015/S02, M015/S03, M015/S04, M015/S05 | M014/S05 evidence matrix and operational verification must document commands as controlled and PHI/secret-safe. |
| R016 | anti-feature | out-of-scope | none | none | n/a |
| R017 | anti-feature | out-of-scope | M015/S05 | M015/S01, M015/S02, M015/S03, M015/S04 | Each M014 slice includes PHI-safe diagnostics criteria; S05 performs final artifact review through the evidence matrix. |
| R018 | anti-feature | out-of-scope | M015/S05 | M015/S01, M015/S02, M015/S03, M015/S04 | M014/S05 evidence matrix row M014-17 validates that independent medium findings were not silently dropped: every R012/R013/R018-relevant lane is listed with closed, not-applicable, or deferred status and executable matrix validation. |

## Coverage Summary

- Active requirements: 0
- Mapped to slices: 0
- Validated: 13 (R001, R002, R003, R004, R005, R006, R007, R008, R009, R010, R011, R012, R013)
- Unmapped active requirements: 0
