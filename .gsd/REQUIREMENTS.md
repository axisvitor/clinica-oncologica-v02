# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R004 — Usuários autenticados só podem emitir links e consultar status/histórico de quiz mensal para pacientes sob seu escopo autorizado.
- Class: compliance/security
- Status: active
- Description: Usuários autenticados só podem emitir links e consultar status/histórico de quiz mensal para pacientes sob seu escopo autorizado.
- Why it matters: Quiz mensal contém sintomas e dados clínicos; permitir patient_id arbitrário vaza PHI e possibilita abuso de link.
- Source: report
- Primary owning slice: M013/S03
- Supporting slices: M013/S06
- Validation: mapped
- Notes: Cobre F-04 e F-05. Deve reaproveitar `_check_patient_access` ou controle equivalente antes de criar sessão/token ou consultar histórico/status.

### R005 — O fluxo público do quiz deve aceitar apenas sessão/link opaco, válido, não expirado, não revogado e alinhado ao paciente/token estabelecido pelo acesso correto.
- Class: compliance/security
- Status: active
- Description: O fluxo público do quiz deve aceitar apenas sessão/link opaco, válido, não expirado, não revogado e alinhado ao paciente/token estabelecido pelo acesso correto.
- Why it matters: O quiz público cruza uma fronteira autenticado→público; uma sessão forjada ou vazada pode gravar respostas no paciente errado.
- Source: report
- Primary owning slice: M013/S03
- Supporting slices: M013/S06
- Validation: mapped
- Notes: Cobre F-06. O submit público não deve confiar apenas em `quiz_session_id` de cookie controlável; deve validar estado, token hash/binding e expiração.

### R006 — Uploads marcados como privados não podem ser servidos por rota estática pública; acesso privado deve passar por autenticação e ownership.
- Class: compliance/security
- Status: active
- Description: Uploads marcados como privados não podem ser servidos por rota estática pública; acesso privado deve passar por autenticação e ownership.
- Why it matters: URLs de upload podem vazar por logs, UI ou compartilhamento; `is_public=false` precisa ser controle real, não apenas metadado.
- Source: report
- Primary owning slice: M013/S04
- Supporting slices: M013/S06
- Validation: mapped
- Notes: Cobre F-07. Separar público/privado ou substituir serving privado por endpoint autenticado; sem fallback público para conteúdo PHI.

### R007 — PDFs e relatórios de paciente gerados por workers não podem ficar em caminho público determinístico sem autorização de download.
- Class: compliance/security
- Status: active
- Description: PDFs e relatórios de paciente gerados por workers não podem ficar em caminho público determinístico sem autorização de download.
- Why it matters: Relatórios de paciente são PHI concentrado; caminhos determinísticos sob `/uploads/reports` permitem acesso público se a URL for conhecida.
- Source: report
- Primary owning slice: M013/S04
- Supporting slices: M013/S05, M013/S06
- Validation: mapped
- Notes: Cobre F-08. Relatórios devem ser gravados fora do static root ou acessados por endpoint/URL assinada curta com ownership.

### R008 — Downloads, exportações, compartilhamento e histórico de relatórios no escopo M013 devem validar ownership ou patient assignment antes de retornar dados.
- Class: compliance/security
- Status: active
- Description: Downloads, exportações, compartilhamento e histórico de relatórios no escopo M013 devem validar ownership ou patient assignment antes de retornar dados.
- Why it matters: Listagem filtrada não protege download direto por UUID; relatórios podem expor dados clínicos completos.
- Source: report
- Primary owning slice: M013/S05
- Supporting slices: M013/S04, M013/S06
- Validation: mapped
- Notes: Cobre F-09 diretamente e fecha superfícies de relatório relacionadas quando usam o mesmo controle. F-22 médio pode ser parcialmente avançado se compartilhar helper.

### R010 — O M013 deve deixar uma prova negativa reutilizável de isolamento médico/paciente com dois médicos, pacientes cruzados e endpoints críticos exercitados.
- Class: quality-attribute
- Status: active
- Description: O M013 deve deixar uma prova negativa reutilizável de isolamento médico/paciente com dois médicos, pacientes cruzados e endpoints críticos exercitados.
- Why it matters: Correções de autorização só são confiáveis quando o caminho proibido é exercitado e falha de forma verificável.
- Source: inferred
- Primary owning slice: M013/S06
- Supporting slices: M013/S02, M013/S03, M013/S04, M013/S05
- Validation: mapped
- Notes: A matriz deve cobrir mensagens, quiz, flow responses, flow overrides, reports e upload/report serving conforme aplicável.

### R011 — Falhas de autenticação, autorização, SSRF, arquivo privado e quiz inválido devem falhar fechado e emitir sinais diagnósticos sem PHI, tokens ou segredos.
- Class: failure-visibility
- Status: active
- Description: Falhas de autenticação, autorização, SSRF, arquivo privado e quiz inválido devem falhar fechado e emitir sinais diagnósticos sem PHI, tokens ou segredos.
- Why it matters: Segurança clínica precisa de bloqueio seguro e capacidade de investigar tentativas negadas sem vazar mais dados.
- Source: inferred
- Primary owning slice: M013/S06
- Supporting slices: M013/S01, M013/S02, M013/S03, M013/S04, M013/S05
- Validation: mapped
- Notes: M013/S01 advanced failure visibility for WhatsApp auth and WuzAPI SSRF by failing closed and sanitizing unsafe/oversize media diagnostics; full R011 validation remains owned by M013/S06 across auth, authorization, private files and quiz boundaries.

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

## Deferred

### R012 — Corrigir e provar hardening médio remanescente: ADK auth, RLS, DB TLS, reset replay, CSRF, webhook replay, PHI client cache, deployment secrets e duplicate oracle.
- Class: compliance/security
- Status: deferred
- Description: Corrigir e provar hardening médio remanescente: ADK auth, RLS, DB TLS, reset replay, CSRF, webhook replay, PHI client cache, deployment secrets e duplicate oracle.
- Why it matters: Os findings médios ainda importam para defesa em profundidade, mas não devem diluir a remediação crítica/alta de M013.
- Source: report
- Primary owning slice: M014/provisional
- Supporting slices: none
- Validation: unmapped
- Notes: Provisório para M014. Itens P2 independentes não entram no M013 salvo se forem necessários para provar os controles críticos/altos.

### R013 — Fechar proof gaps deferred: upload stored-XSS, ADK session ownership, JWT revocation multi-worker, X-Forwarded-For/rate-limit e quiz frontend lane incompleta.
- Class: failure-visibility
- Status: deferred
- Description: Fechar proof gaps deferred: upload stored-XSS, ADK session ownership, JWT revocation multi-worker, X-Forwarded-For/rate-limit e quiz frontend lane incompleta.
- Why it matters: Lacunas deferred não devem desaparecer; precisam de owner explícito para revisão posterior.
- Source: report
- Primary owning slice: M014/provisional
- Supporting slices: none
- Validation: unmapped
- Notes: Provisório para M014. Esses itens foram marcados como deferred/uncertain no relatório e exigem validação adicional antes de virar correção final.

### R014 — Construir harness runtime completo com DB, queue, WuzAPI/Gemini e fixtures production-like se a validação dinâmica ampla exigir esse ambiente.
- Class: quality-attribute
- Status: deferred
- Description: Construir harness runtime completo com DB, queue, WuzAPI/Gemini e fixtures production-like se a validação dinâmica ampla exigir esse ambiente.
- Why it matters: A análise original não executou runtime exploitation por falta de dependências; um harness futuro pode transformar isso em regressão dinâmica ampla.
- Source: inferred
- Primary owning slice: M015/provisional
- Supporting slices: none
- Validation: unmapped
- Notes: Provisório para M015. M013 usa testes/mocks/fixtures focados; runtime exploitation real fica fora enquanto dependências e dados production-like não existirem.

## Out of Scope

### R015 — M013 não executa exploração contra produção nem usa dados reais de paciente para provar vulnerabilidades.
- Class: anti-feature
- Status: out-of-scope
- Description: M013 não executa exploração contra produção nem usa dados reais de paciente para provar vulnerabilidades.
- Why it matters: Exploração em produção ou com dados reais aumentaria risco operacional e de privacidade sem necessidade para planejar correções.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Usar fixtures, mocks e ambientes locais/controlados. Qualquer runtime validation futura deve evitar PHI real.

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
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: O relatório suprimiu esse item como committed-secret finding porque `.env` e service-account local estão ignorados; continuam sensíveis, mas não são escopo de correção de código M013.

### R018 — M013 não corrige todos os findings médios se eles não sustentarem a prova dos riscos críticos/altos.
- Class: anti-feature
- Status: out-of-scope
- Description: M013 não corrige todos os findings médios se eles não sustentarem a prova dos riscos críticos/altos.
- Why it matters: Manter foco evita uma remediação larga demais e mal provada.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Findings médios independentes ficam em R012/R013 para M014; exceções podem ser feitas quando compartilhar o mesmo helper/controle de M013 for mais seguro.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | compliance/security | validated | M013/S01 | M013/S06 | M013/S01 verified WhatsApp management API auth with focused and final pytest evidence: gsd_exec af1fd56e-266a-44f6-91f3-f4b4fb948c14 and 75ac52dd-e00f-4c71-9f54-244766a9885b passed. Tests cover anonymous/non-admin rejection before service/queue/DB execution, public /api/v2/whatsapp/health, and an authorized admin mocked send operation. |
| R002 | compliance/security | validated | M013/S01 | M013/S06 | M013/S01 verified WuzAPI media SSRF protections with focused and final pytest evidence: gsd_exec 5c8857c7-87d3-4d91-8853-b038a4d5c49f and 75ac52dd-e00f-4c71-9f54-244766a9885b passed. Tests cover blocked schemes, malformed/missing hosts, userinfo, invalid/zero ports, localhost/private/loopback/link-local/multicast/unspecified/reserved/CGNAT/metadata IPs, DNS failure/mixed answers, no GET before validation, manual redirect validation with allow_redirects=False, safe redirects, data-URI behavior, and sanitized unsafe/oversize messages. |
| R003 | compliance/security | validated | M013/S02 | M013/S06 | M013/S02 verified message read/list/conversation/unread/read-state/send/bulk-send/delete/cancel boundaries with `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exit 0; 1 expected skip for rate limiting disabled). |
| R004 | compliance/security | active | M013/S03 | M013/S06 | mapped |
| R005 | compliance/security | active | M013/S03 | M013/S06 | mapped |
| R006 | compliance/security | active | M013/S04 | M013/S06 | mapped |
| R007 | compliance/security | active | M013/S04 | M013/S05, M013/S06 | mapped |
| R008 | compliance/security | active | M013/S05 | M013/S04, M013/S06 | mapped |
| R009 | compliance/security | validated | M013/S02 | M013/S06 | M013/S02 verified flow response and flow override GET/PUT ownership denial and assigned-doctor/admin positives with `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py -q` (exit 0; boundary suite includes flow-response/override tests). |
| R010 | quality-attribute | active | M013/S06 | M013/S02, M013/S03, M013/S04, M013/S05 | mapped |
| R011 | failure-visibility | active | M013/S06 | M013/S01, M013/S02, M013/S03, M013/S04, M013/S05 | mapped |
| R012 | compliance/security | deferred | M014/provisional | none | unmapped |
| R013 | failure-visibility | deferred | M014/provisional | none | unmapped |
| R014 | quality-attribute | deferred | M015/provisional | none | unmapped |
| R015 | anti-feature | out-of-scope | none | none | n/a |
| R016 | anti-feature | out-of-scope | none | none | n/a |
| R017 | anti-feature | out-of-scope | none | none | n/a |
| R018 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 7
- Mapped to slices: 7
- Validated: 4 (R001, R002, R003, R009)
- Unmapped active requirements: 0
