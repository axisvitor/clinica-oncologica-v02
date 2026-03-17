# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R089 — Visão geral patient-centric com contexto clínico por paciente como tela principal do physician dashboard.
- Class: primary-user-loop
- Status: active
- Description: O physician dashboard mostra todos os pacientes do médico com fase do fluxo (onboarding/follow-up/quiz), dia atual, último contato, e flags de atenção (alertas não reconhecidos, sem resposta há dias, fluxo parado) visíveis diretamente na lista, sem precisar clicar.
- Why it matters: O médico precisa de um relance para decidir quem precisa de atenção. A tela atual é analytics-heavy e não mostra contexto clínico por paciente.
- Source: user
- Primary owning slice: M010/S01
- Supporting slices: none
- Validation: unmapped
- Notes: Substitui a tabela de risk assessment atual por uma visão patient-centric com dados de fluxo.

### R090 — Tela de preparo pré-consulta consolidada: resumo IA + respostas livres + alertas + status fluxo num clique.
- Class: primary-user-loop
- Status: active
- Description: Ao clicar num paciente no dashboard, o médico vê numa tela consolidada o resumo IA do mês, as respostas livres recentes, alertas do quiz, e o status atual do fluxo — tudo visível sem navegar por tabs.
- Why it matters: O médico prepara a consulta em 5 minutos. Se precisa navegar por 4 tabs para juntar informação, perde tempo e perde contexto.
- Source: user
- Primary owning slice: M010/S02
- Supporting slices: M010/S01
- Validation: unmapped
- Notes: Reusa e recompõe PatientAISummary, FlowStatus, QuizResponseViewer existentes.

### R091 — API backend enriquecida para lista de pacientes do médico com dados de fluxo.
- Class: integration
- Status: active
- Description: A API de listagem de pacientes do physician dashboard retorna, para cada paciente, a fase do fluxo (onboarding/daily_follow_up/quiz_mensal), o dia atual do fluxo, a data do último contato, e contagem de alertas não reconhecidos — num único endpoint, sem N+1.
- Why it matters: Sem dados de fluxo na listagem, o frontend faria N+1 requests para buscar status de cada paciente individualmente.
- Source: inferred
- Primary owning slice: M010/S01
- Supporting slices: none
- Validation: unmapped
- Notes: Pode ser um novo endpoint /api/v2/physician/patients ou enriquecer o risk-assessments existente.

### R092 — Acesso ao resumo IA em no máximo 1 clique a partir da lista de pacientes.
- Class: primary-user-loop
- Status: active
- Description: Da lista de pacientes no dashboard, 1 clique leva o médico direto à tela com o resumo IA do paciente visível sem ação adicional.
- Why it matters: Se o resumo IA precisa de 3+ cliques, o médico para de usar.
- Source: user
- Primary owning slice: M010/S02
- Supporting slices: M010/S01
- Validation: unmapped
- Notes: Atualmente existe o Brain icon na PhysicianRiskTable que navega para ?tab=ai-summary. O refinamento deve tornar isso mais direto.

### R093 — Interface responsiva de verdade em desktop e mobile para dashboard e detalhe do paciente.
- Class: quality-attribute
- Status: active
- Description: O dashboard do médico e a tela de detalhe do paciente funcionam bem em desktop (tabela densa com informação) e mobile (cards touch-friendly, fontes legíveis, interações de toque). Não é apenas "não quebra" — é "funciona bem" nos dois.
- Why it matters: Médico checa no celular entre consultas e usa desktop no consultório. Ambos precisam ser experiências completas.
- Source: user
- Primary owning slice: M010/S04
- Supporting slices: M010/S01, M010/S02
- Validation: unmapped
- Notes: Envolve responsive breakpoints, mobile-first cards, tabela adaptativa desktop→cards mobile.

### R094 — Remoção completa do código morto /medico/*.
- Class: operability
- Status: active
- Description: MedicoDashboard.tsx, PacientesList.tsx, ProntuarioView.tsx, MedicoAuthContext.tsx, useMedicoDashboardStats.ts, e todas as rotas /medico/* exceto redirects essenciais são removidos. Zero código de dashboard/paciente morto.
- Why it matters: Código morto confunde manutenção e gera falsos positivos em buscas.
- Source: user
- Primary owning slice: M010/S03
- Supporting slices: none
- Validation: unmapped
- Notes: Rotas /medico/* já redirecionam para /physician/*. MedicoLogin pode ser mantido se tiver uso real ou removido se redundante.

### R095 — Dashboards admin e médico permanecem separados.
- Class: constraint
- Status: active
- Description: O dashboard admin (/dashboard, DashboardPage.tsx) e o physician dashboard (/physician/dashboard, PhysicianDashboard.tsx) são telas separadas, cada uma otimizada para seu público (admin operacional vs. médico clínico).
- Why it matters: Misturar admin e clínico num só dashboard cria ruído para ambos os públicos.
- Source: user
- Primary owning slice: M010/S01
- Supporting slices: none
- Validation: unmapped
- Notes: DashboardPage não é alterado por M010.

### R100 — Endpoints hot-path do médico cacheados no Redis/Dragonfly com TTL adequado.
- Class: quality-attribute
- Status: validated
- Description: Os endpoints mais acessados pelo médico (physician/patients, dashboard/main) usam @cache_response com TTL adequado no Dragonfly, eliminando queries repetidas ao banco.
- Why it matters: Sem cache, cada refresh do dashboard dispara JOINs pesados no PostgreSQL — stress desnecessário no banco.
- Source: inferred
- Primary owning slice: M011/S01
- Supporting slices: none
- Validation: validated by S01 — per-user Redis caching on physician/patients (TTL=60s, user_id in cache key) and dashboard/main (TTL=120s, per-user key). verify-m011.sh group 5 confirms TTL values and user_id presence.
- Notes: S01 used manual redis_cache.get/set (not @cache_response decorator) to include user_id in key preventing cross-doctor data leaks. Dashboard caching was already correct — unchanged.

### R101 — Index composto em patient_flow_states para window function do physician patients.
- Class: quality-attribute
- Status: validated
- Description: Index composto em patient_flow_states(patient_id, started_at DESC) para que a window function ROW_NUMBER() do endpoint physician/patients use index scan em vez de seq scan.
- Why it matters: Sem index, a window function faz sort em memória para cada paciente — escala mal com muitos flow states.
- Source: inferred
- Primary owning slice: M011/S01
- Supporting slices: none
- Validation: validated by S01 — Alembic migration m011_s01_patient_flow_states_index creates composite index idx_pfs_patient_started on patient_flow_states(patient_id, started_at DESC) with if_not_exists=True. verify-m011.sh group 7 confirms.
- Notes: Index accelerates ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY started_at DESC) window function in physician/patients endpoint.

### R102 — Frontend hooks com staleTime/gcTime consistentes e refetchInterval reduzido.
- Class: quality-attribute
- Status: validated
- Description: Hooks de dashboard e pacientes usam staleTime ≥ 60s, refetchInterval ≥ 120s (exceto monitoring real-time). Elimina requests redundantes que martelam o backend a cada 10-30s.
- Why it matters: Hooks com staleTime de 10s e refetchInterval de 30s geram requests desnecessários — o dado não muda tão rápido.
- Source: inferred
- Primary owning slice: M011/S02
- Supporting slices: none
- Validation: validated by S02 — 21 frontend hooks normalized: staleTime ≥ 60s (dashboard/patient), ≥ 120s (admin), refetchInterval ≥ 120s. verify-m011.sh group 6 confirmed 58 timing values comply. Monitoring hooks verified untouched.
- Notes: Global default staleTime bumped 30s→60s. Monitoring/real-time hooks (system health, WhatsApp, agent swarm) explicitly exempt per D020.

## Validated

### R001 — The WhatsApp flow pipeline recovers from sequential-gate mismatch, outbound send failures, deferred follow-up failures, day advancement issues, and malformed day configs.
- Class: continuity
- Status: validated
- Description: The WhatsApp flow pipeline recovers from sequential-gate mismatch, outbound send failures, deferred follow-up failures, day advancement issues, and malformed day configs.
- Why it matters: Patients cannot be left silently stuck between consultations.
- Source: execution
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S01 unit coverage and downstream integration coverage.

### R002 — Stuck flows are detected periodically, recovered through bounded logic, and exposed to operators through admin reset/advance/unstick surfaces.
- Class: operability
- Status: validated
- Description: Stuck flows are detected periodically, recovered through bounded logic, and exposed to operators through admin reset/advance/unstick surfaces.
- Why it matters: The system needs both automatic recovery and human intervention paths for real operations.
- Source: execution
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S02 service/task/router tests.

### R003 — Operators can inspect flow health counts, stall alerts, fallback metrics, and correlation IDs across the flow pipeline.
- Class: failure-visibility
- Status: validated
- Description: Operators can inspect flow health counts, stall alerts, fallback metrics, and correlation IDs across the flow pipeline.
- Why it matters: Recovery only works operationally if failures and degraded paths are visible.
- Source: execution
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S03 service/router/unit coverage.

### R004 — The project has integration coverage for webhook ingress, continuation, stalled-flow recovery, and retry mechanics.
- Class: quality-attribute
- Status: validated
- Description: The project has integration coverage for webhook ingress, continuation, stalled-flow recovery, and retry mechanics.
- Why it matters: The milestone promise was only credible if the assembled pipeline was exercised end to end.
- Source: execution
- Primary owning slice: M001/S04
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S04 integration suites and milestone summary evidence.

### R005 — Admins and doctors authenticate with backend-owned email/password login, without Firebase token exchange in the normal login path.
- Class: primary-user-loop
- Status: validated
- Description: Admins and doctors authenticate with backend-owned email/password login, without Firebase token exchange in the normal login path.
- Why it matters: Reliable login for the clinical team is a prerequisite for the rest of the product.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03, M002/S04
- Validation: validated
- Notes: M002 proved the backend local-login contract in S01, cut the browser happy path over in S03, removed Firebase runtime seams in S04, and replayed `/login` → `/dashboard` locally on a no-Firebase stack.

### R006 — The product keeps Redis-backed session validation, HttpOnly cookie behavior, remember-me continuity, and protected-route authentication after the provider switch.
- Class: continuity
- Status: validated
- Description: The product keeps Redis-backed session validation, HttpOnly cookie behavior, remember-me continuity, and protected-route authentication after the provider switch.
- Why it matters: Replacing the identity provider should not regress the stable session model already used across the backend.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03, M002/S04
- Validation: validated
- Notes: S01 proved backend session issuance/verify/logout/protected-route auth on the first-party identity contract; S03 proved remember-me/session restore/logout in frontend tests; direct browser replay stayed authenticated across reload.

### R007 — Users already present in the system can recover access through a first-access/reset flow instead of having accounts manually recreated.
- Class: launchability
- Status: validated
- Description: Users already present in the system can recover access through a first-access/reset flow instead of having accounts manually recreated.
- Why it matters: A hard cut without a recovery path would create support load and block real users from logging in.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04
- Validation: validated
- Notes: Verified by M002/S02 public/admin recovery suites and `tests/integration/test_password_reset_migration_flow.py`, which covers existing Firebase-era users and admin-created users migrating into local auth.

### R008 — New staff accounts are created by admins; the system does not add public self-signup during M002.
- Class: admin/support
- Status: validated
- Description: New staff accounts are created by admins; the system does not add public self-signup during M002.
- Why it matters: The product is an internal clinical system, and admin-mediated onboarding reduces security and support risk.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S03
- Validation: validated
- Notes: M002/S02/T03 kept admin-created first-access and admin-triggered recovery canonical through the shared email-backed reset service while preserving only explicit legacy direct-password compatibility for the pre-cutover admin SPA.

### R009 — A staff user can request a password reset email, receive a time-limited reset token, and set a new password securely.
- Class: continuity
- Status: validated
- Description: A staff user can request a password reset email, receive a time-limited reset token, and set a new password securely.
- Why it matters: Hard-cutting Firebase without self-service recovery would replace one login pain with another.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04
- Validation: validated
- Notes: M002/S02 shipped `POST /api/v2/auth/password/reset-request` and `/reset-confirm` with focused backend proof, and M002/S03 shipped the real routed reset-request/reset-confirm browser UX.

### R010 — Dashboard login/logout/session restore and realtime/WebSocket bootstrap work with first-party session semantics only.
- Class: integration
- Status: validated
- Description: Dashboard login/logout/session restore and realtime/WebSocket bootstrap work with first-party session semantics only.
- Why it matters: Removing Firebase only on the backend is insufficient if the browser and realtime path still depend on Firebase SDK state.
- Source: inferred
- Primary owning slice: M002/S03
- Supporting slices: M002/S01, M002/S04
- Validation: validated
- Notes: Verified by the S03 session-first auth and websocket suites, the S04 hard-cut cleanup suite, and no-Firebase browser/network replay with no Firebase-auth requests.

### R011 — Staff authentication no longer requires Firebase Auth runtime credentials, SDK calls, or long-lived compatibility mode.
- Class: constraint
- Status: validated
- Description: Staff authentication no longer requires Firebase Auth runtime credentials, SDK calls, or long-lived compatibility mode.
- Why it matters: The user explicitly wants the dependency gone, not just hidden behind another layer.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S03
- Validation: validated
- Notes: M002/S04 removed/tombstoned the shipped staff-auth Firebase seams, `verify-no-firebase-auth.sh` passed, and the local stack booted and authenticated staff users with Firebase env vars blank.

### R012 — Login, reset, session, and migration failures emit actionable diagnostics and are covered by focused verification so auth regressions stop being mysterious.
- Class: failure-visibility
- Status: validated
- Description: Login, reset, session, and migration failures emit actionable diagnostics and are covered by focused verification so auth regressions stop being mysterious.
- Why it matters: The current pain is not just login failure, but hard-to-debug authentication behavior.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: validated
- Notes: Across M002 the system now emits stable diagnostics for login/session/reset/password/websocket/operational failures (`error`, `message`, `request_id`, websocket auth codes, `session_auth` readiness), with focused pytest/vitest proof across all four slices.

### R034 — The milestone must materially reduce the size and responsibility sprawl of the highest-value hotspots instead of leaving the same behavior trapped in giant files.
- Class: quality-attribute
- Status: validated
- Description: The milestone must materially reduce the size and responsibility sprawl of the highest-value hotspots instead of leaving the same behavior trapped in giant files.
- Why it matters: Large mixed-responsibility files make safe changes, debugging, and review disproportionately expensive.
- Source: user
- Primary owning slice: M003/S02
- Supporting slices: M003/S03, M003/S04
- Validation: validated
- Notes: M003 closed with the targeted hotspots materially smaller under green proof: `auth_dependencies.py` shrank from 1579 to 675 lines, `src/lib/api-client/index.ts` from 1304 to 223, and `src/lib/api-client/types.ts` from 1159 to 26.

### R035 — Code should only be declared dead and removed when repo evidence, call graph analysis, or focused verification shows it is not part of a live path.
- Class: failure-visibility
- Status: validated
- Description: Code should only be declared dead and removed when repo evidence, call graph analysis, or focused verification shows it is not part of a live path.
- Why it matters: In a brownfield system, mistaken deletion is worse than untidy code.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S04
- Validation: validated
- Notes: M003/S01 established the evidence map and deletion ledger, and M003/S04 executed the in-scope removals with focused frontend/backend proof, a cleanup manifest, and a green living verifier gate.

### R036 — Legacy aliases, shims, and compatibility layers that no longer justify their complexity must either be removed or explicitly isolated away from the main runtime path.
- Class: constraint
- Status: validated
- Description: Legacy aliases, shims, and compatibility layers that no longer justify their complexity must either be removed or explicitly isolated away from the main runtime path.
- Why it matters: Compatibility residue keeps the real architecture blurry and makes every future change more dangerous.
- Source: user
- Primary owning slice: M003/S04
- Supporting slices: M003/S02, M003/S03
- Validation: validated
- Notes: M003/S04 deleted the proven-dead frontend alias/type/hook files, kept dead backend auth wrappers off the public surface, and documented `auth_session.py`, `firebase_uid`, and bearer-token fallback as explicit retained compatibility islands instead of ambiguous leftovers.

### R037 — The refactor must not unnecessarily change user-visible behavior, critical payload shapes, or the main staff-auth/dashboard/admin/flow entrypoint behavior.
- Class: continuity
- Status: validated
- Description: The refactor must not unnecessarily change user-visible behavior, critical payload shapes, or the main staff-auth/dashboard/admin/flow entrypoint behavior.
- Why it matters: This work is meant to buy maintainability, not hide regressions behind cleanup language.
- Source: user
- Primary owning slice: M003/S05
- Supporting slices: M003/S02, M003/S03, M003/S04
- Validation: validated
- Notes: Final M003 proof combined focused backend/frontend suites, green direct runtime probes for canonical auth plus legacy `/session/logout`, a green seeded-user Chromium acceptance spec, and green routed smoke for `/dashboard`, `/admin`, and `/whatsapp`.

### R038 — After the milestone, maintainers should be able to reason about and change the targeted areas with less fear because module boundaries and responsibilities are clearer.
- Class: operability
- Status: validated
- Description: After the milestone, maintainers should be able to reason about and change the targeted areas with less fear because module boundaries and responsibilities are clearer.
- Why it matters: The primary beneficiary is whoever maintains the system next, not just the current cleanup effort.
- Source: user
- Primary owning slice: M003/S05
- Supporting slices: M003/S02, M003/S03, M003/S04
- Validation: validated
- Notes: M003 leaves smaller seams, explicit canonical-vs-legacy ownership boundaries, the S04 cleanup manifest, and `M003-VERIFY.json` as replayable maintenance guidance.

### R039 — The milestone must leave focused verification and smoke evidence that the refactor preserved critical auth/session, dashboard/admin, and WhatsApp flow behavior.
- Class: quality-attribute
- Status: validated
- Description: The milestone must leave focused verification and smoke evidence that the refactor preserved critical auth/session, dashboard/admin, and WhatsApp flow behavior.
- Why it matters: Refactors are only worth trusting if the new structure is backed by proof, not aesthetics.
- Source: inferred
- Primary owning slice: M003/S05
- Supporting slices: M003/S01, M003/S02, M003/S03, M003/S04
- Validation: validated
- Notes: Milestone closeout now rests on the green evidence-map gate, focused backend/frontend packs, a seeded-user Chromium acceptance spec, direct assembled-stack probes, and routed `/dashboard` / `/admin` / `/whatsapp` smoke.

### R047 — O runtime oficial do sistema deixa de depender de Firebase para autenticação, sessão, identidade da equipe ou narrativa operacional do caminho feliz.
- Class: constraint
- Status: validated
- Description: O runtime oficial do sistema deixa de depender de Firebase para autenticação, sessão, identidade da equipe ou narrativa operacional do caminho feliz.
- Why it matters: Enquanto Firebase ainda estiver vivo no runtime oficial, a base continua com transição aberta e comportamento ambíguo.
- Source: user
- Primary owning slice: M004/S05
- Supporting slices: M004/S01, M004/S02, M004/S03, M004/S04, M004/S06
- Validation: validated
- Notes: S05 fechou a dependência funcional adjacente de Firebase no runtime por prova de contrato e S06 revalidou o estado montado sem Firebase Auth.

### R048 — O sistema oficial da equipe autentica, restaura sessão e revoga sessão por um único contrato canônico, sem caminhos duplos ainda aceitos por inércia histórica.
- Class: continuity
- Status: validated
- Description: O sistema oficial da equipe autentica, restaura sessão e revoga sessão por um único contrato canônico, sem caminhos duplos ainda aceitos por inércia histórica.
- Why it matters: Caminhos paralelos de auth/sessão tornam qualquer manutenção futura arriscada e difícil de raciocinar.
- Source: inferred
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S03, M004/S04
- Validation: validated
- Notes: Verified by the combined M004/S02–S04 proof: canonical login/verify-session/restore/logout stayed green on the cookie-backed contract, the official frontend already consumed only that contract, and S04 retired `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket `session_id` fallback as accepted runtime transport.

### R049 — O runtime resolve identidade, cache, sessão e superfícies oficiais por `id` / `user_id`, sem precisar de `firebase_uid` no happy path nem como pivô funcional oculto.
- Class: integration
- Status: validated
- Description: O runtime resolve identidade, cache, sessão e superfícies oficiais por `id` / `user_id`, sem precisar de `firebase_uid` no happy path nem como pivô funcional oculto.
- Why it matters: Enquanto `firebase_uid` continuar sendo chave funcional no runtime, o hard cut permanece incompleto.
- Source: inferred
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S04, M004/S05
- Validation: validated
- Notes: Verified by the combined M004/S02+S05 proof: Redis session creation/listing/invalidation, shared auth/cache restore, login-written payloads, websocket-adjacent auth, audit/admin/docs serialization, and adjacent frontend type surfaces all stay on canonical `id` / `user_id` semantics while the green residue guard now lists only passive compatibility/rejection bookkeeping and M005 keeps the schema drop.

### R050 — `/login`, `/dashboard`, `/admin` e superfícies oficiais relacionadas usam apenas o contrato session-first canônico, sem lógica funcional, comentários operacionais ou tipos oficiais ancorados em Firebase.
- Class: primary-user-loop
- Status: validated
- Description: `/login`, `/dashboard`, `/admin` e superfícies oficiais relacionadas usam apenas o contrato session-first canônico, sem lógica funcional, comentários operacionais ou tipos oficiais ancorados em Firebase.
- Why it matters: Não basta o backend estar cortado se o app oficial ainda age como se Firebase estivesse vivo.
- Source: inferred
- Primary owning slice: M004/S03
- Supporting slices: M004/S01, M004/S04, M004/S05, M004/S06
- Validation: validated
- Notes: Verified by M004/S03’s focused frontend proof packs, green routed `/login` → `/admin/*` coverage, green websocket diagnostic proof, green build, and a green residue guard showing zero approved frontend auth/session/Firebase residue.

### R051 — O schema ativo, os modelos e o grafo Alembic deixam de carregar resíduo estrutural de Firebase/legado como parte necessária do sistema atual.
- Class: quality-attribute
- Status: validated
- Description: O schema ativo, os modelos e o grafo Alembic deixam de carregar resíduo estrutural de Firebase/legado como parte necessária do sistema atual.
- Why it matters: Sem fechar o banco e as migrações, a convergência fica incompleta e frágil para novos ambientes ou upgrades.
- Source: user
- Primary owning slice: M005/S03
- Supporting slices: M005/S01, M005/S02
- Validation: validated by M005/S03 clean+existing head convergence proof and canonical runtime contract suites
- Notes: S01 tornou o controle plane do Alembic operável só com configuração de banco; S02 publicou a fronteira histórica explícita para `firebase_sync_history`, `audit_logs.firebase_uid` e payloads canônicos; S03 provou em Postgres real que `base -> head` e `m005_s02_t01_publish_firebase_history_boundary -> head` convergem para o mesmo head `m005_s03_t02_align_audit_history_head`, com `users`, `audit_logs` e `firebase_sync_history` alinhados ao contrato canônico vivo sem reviver resíduo Firebase estrutural. Milestone closeout consolidado em `.gsd/milestones/M005/M005-SUMMARY.md`.

### R052 — O restante do código morto, bridges, aliases, tombstones e compatibilidades sem uso real é removido com evidência e verificação, não por gosto.
- Class: operability
- Status: validated
- Description: O restante do código morto, bridges, aliases, tombstones e compatibilidades sem uso real é removido com evidência e verificação, não por gosto.
- Why it matters: A lapidação final só fecha quando o repositório deixa de carregar resíduo morto como se fosse parte legítima do sistema.
- Source: user
- Primary owning slice: M006/S04
- Supporting slices: M006/S01, M006/S02, M006/S03
- Validation: validated by M006-VERIFY.json — 10 proof phases green: residue guards, focused backend packs, schema convergence under Postgres, absence scans, frontend import-boundary/build, and final-schema proof fresh/existing with mounted backend replay
- Notes: M006 closed the M004→M006 convergence arc: dead backend services/auth cluster removed, Firebase-prefixed users schema dropped, dead frontend bridges/barrels deleted, config/manifests/workflows/docs aligned to canonical runtime.

### R053 — O encerramento da frente M004–M006 precisa provar o sistema montado em estado final, em vez de depender apenas de grep, manifests e diffs de código.
- Class: quality-attribute
- Status: validated
- Description: O encerramento da frente M004–M006 precisa provar o sistema montado em estado final, em vez de depender apenas de grep, manifests e diffs de código.
- Why it matters: Cleanup sem prova integrada deixa dúvida sobre o que realmente continua funcionando.
- Source: inferred
- Primary owning slice: M005/S04
- Supporting slices: M004/S06, M005/S01, M005/S03
- Validation: validated by M004/S06 mounted runtime proof plus M005/S04 final-schema fresh/existing backend replay on the canonical head
- Notes: M004/S06 validou o stack montado sem Firebase no runtime oficial; M005/S01 acrescentou a prova de operabilidade/replay do controle plane de migrations em Postgres real; M005/S03 acrescentou a prova de convergência estrutural do head canônico em Postgres real; M005/S04 fechou a lacuna operacional ao reexecutar o backend real e os loops críticos pós-M004 nesse head consolidado para histories `fresh` e `existing`. Milestone closeout consolidado em `.gsd/milestones/M005/M005-SUMMARY.md`.

### R057 — O sistema envia as mensagens do dia na ordem correta, respeitando `expects_response`: quando uma mensagem espera resposta, a próxima só é enviada depois que o paciente responde. Sem disparo em bulk.
- Class: core-capability
- Status: validated
- Description: O sistema envia as mensagens do dia na ordem correta, respeitando `expects_response`: quando uma mensagem espera resposta, a próxima só é enviada depois que o paciente responde. Sem disparo em bulk.
- Why it matters: O bug de disparar tudo de uma vez destrói a experiência do paciente e invalida a lógica de acompanhamento gradual.
- Source: user
- Primary owning slice: M007/S01
- Supporting slices: none
- Validation: validated by 11 focused tests in test_sequencing_expects_response.py proving per-message expects_response across all send modes (sequential_auto, wait_each, remaining_after_response) plus edge cases (idempotency, first-message stop, default single mode), with 0 regressions across 36 total flow tests
- Notes: Bug root cause was _send_all_sequential checking expects_response only on the last message. Fixed to check per-iteration inside the loop. All three send functions now use the same per-message pattern.

### R058 — O médico tem uma interface de lista de dias para editar conteúdo, adicionar/remover dias, definir tipo (pergunta, motivação, lembrete), e marcar se espera resposta. Template global por médico.
- Class: primary-user-loop
- Status: validated
- Description: O médico tem uma interface de lista de dias para editar conteúdo, adicionar/remover dias, definir tipo (pergunta, motivação, lembrete), e marcar se espera resposta. Template global por médico.
- Why it matters: Os templates atuais são rascunhos de teste. O médico precisa configurar o fluxo do seu consultório sem complexidade visual estilo N8N.
- Source: user
- Primary owning slice: M007/S03
- Supporting slices: M007/S01, M007/S02
- Validation: validated by S03 — GET/PUT /flows/{template_id}/days API with physician-friendly DayConfigItem projection/hydration, DayConfigEditor dialog in FlowTemplateCard, 30 focused tests proving round-trip fidelity and validate_day_config() loader compatibility, frontend typecheck + build green
- Notes: O FlowDesigner visual existente (~3300 linhas) foi removido em M007/S02. Substituído por editor simples de lista de dias.

### R059 — FlowDesigner visual, FlowTypes fantasma no enum, knowledge graph morto, tombstones residuais e mixin soup são removidos ou simplificados com prova.
- Class: operability
- Status: validated
- Description: FlowDesigner visual, FlowTypes fantasma no enum, knowledge graph morto, tombstones residuais e mixin soup são removidos ou simplificados com prova.
- Why it matters: Abstrações mortas dificultam manutenção e escondem bugs no subsistema que mais precisa de clareza.
- Source: inferred
- Primary owning slice: M007/S02
- Supporting slices: none
- Validation: validated by S02 — FlowDesigner visual (~4800 lines) deleted, 7 phantom FlowType members removed from enum (only ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM remain), tombstoned flow/templates package deleted (4 files), ~4600 lines of dead tests deleted (8 files), normalize_flow_type stale fallback proven, frontend build + typecheck green, backend flow tests green (84 passed, 0 failed), separate enums (AlertRuleType, MetricType, AnalyticsEventType) untouched
- Notes: FlowDesigner (~3300 linhas), FlowTypes fantasma (TREATMENT_ADHERENCE, SYMPTOM_TRACKING, etc.), knowledge graph com silent ImportError, flow/templates/manager.py tombstoned. Knowledge graph cleanup and mixin soup simplification were not in S02 scope.

### R060 — A IA reformula perguntas para parecerem naturais e não repetitivas ao longo dos 45+ dias, mantendo grounding no template base. O paciente não percebe que está recebendo variações do mesmo conteúdo.
- Class: differentiator
- Status: validated
- Description: A IA reformula perguntas para parecerem naturais e não repetitivas ao longo dos 45+ dias, mantendo grounding no template base. O paciente não percebe que está recebendo variações do mesmo conteúdo.
- Why it matters: Sem reformulação natural, o paciente para de responder depois de alguns dias de mensagens repetitivas.
- Source: user
- Primary owning slice: M007/S04
- Supporting slices: M007/S01
- Validation: validated by S04 — 25 focused unit tests proving _personalization_is_grounded() boundary cases (similarity ≥ 0.6, keyword overlap ≥ 0.2, no-keyword ≥ 0.35), _select_template_variation() determinism, _lightly_rephrase_question() logic, and AI-skip for non-response messages. All tests use realistic Portuguese oncology content.
- Notes: O sistema já tem personalização via Gemini com validação de grounding. Calibração provada por testes; avaliação subjetiva humana de qualidade a longo prazo requer interação real com pacientes.

### R061 — As respostas em texto livre do paciente via WhatsApp são persistidas com contexto completo (qual dia do fluxo, qual mensagem respondida, timestamp) e estruturadas para consumo pelo resumo IA.
- Class: core-capability
- Status: validated
- Description: As respostas em texto livre do paciente via WhatsApp são persistidas com contexto completo (qual dia do fluxo, qual mensagem respondida, timestamp) e estruturadas para consumo pelo resumo IA.
- Why it matters: Sem armazenamento estruturado, o resumo mensal do médico fica sem dados.
- Source: user
- Primary owning slice: M007/S04
- Supporting slices: M007/S01
- Validation: validated by S04 — PatientFlowResponse model + Alembic migration, dual-write in process_patient_response() persisting to patient_flow_responses alongside step_data JSONB in same transaction, GET /api/v2/patients/{id}/flow-responses with date-range filtering, 14 integration tests proving write-through and query paths, 0 regressions across 154 flow tests
- Notes: O sistema não é chatbot — o paciente responde livremente, não por menu. As respostas são linkadas ao contexto do fluxo (day_number, message_index, flow_state_id nullable).

### R062 — Quando o quiz mensal gera um alerta clínico (dor crítica, febre com calafrios, etc.), o alerta chega ao médico com ação clara — notificação e destaque no dashboard — não fica passivo em Redis.
- Class: failure-visibility
- Status: validated
- Description: Quando o quiz mensal gera um alerta clínico (dor crítica, febre com calafrios, etc.), o alerta chega ao médico com ação clara — notificação e destaque no dashboard — não fica passivo em Redis.
- Why it matters: Alerta que não chega ao médico é pior que não ter alerta — gera falsa sensação de segurança.
- Source: inferred
- Primary owning slice: M007/S05
- Supporting slices: M007/S04
- Validation: validated by S05 — QuizResponseEvaluator wired into complete_quiz_session(), Notification records created for patient's doctor on triggered alerts, duplicate alert guard, _serialize_alert() returns title/message/recommendation, PhysicianDashboard renders recommendation text. Proven by 14 focused tests covering full chain + 42 API tests with 0 regressions.
- Notes: As regras de alerta em `quiz_alert_rules.py` são boas clinicamente. A questão é o caminho até o médico.

### R063 — O médico acessa um resumo do mês do paciente gerado por IA — síntese das respostas livres, padrões identificados, preocupações clínicas, e pontos de atenção — e economiza tempo de consulta.
- Class: differentiator
- Status: validated
- Description: O médico acessa um resumo do mês do paciente gerado por IA — síntese das respostas livres, padrões identificados, preocupações clínicas, e pontos de atenção — e economiza tempo de consulta.
- Why it matters: Este é o core value clínico do sistema: diminuir tempo de consulta e melhorar qualidade do atendimento.
- Source: user
- Primary owning slice: M007/S06
- Supporting slices: M007/S04, M007/S05
- Validation: validated by S06 — SummaryDataAggregator wired to patient_flow_responses + enriched alerts (description + recommendation from JSONB), prompt template with {flow_responses} section, Brain icon quick-access in PhysicianDashboard navigating to ?tab=ai-summary, 13 focused tests proving aggregator integration + 0 regressions across 181 flow tests, frontend typecheck green
- Notes: `PatientSummaryService` (Gemini 2.5 Flash) was not modified — only its data aggregator was enhanced. Subjective AI summary quality for clinical use requires ongoing human evaluation.

### R067 — O stack completo (Postgres + Dragonfly + backend + Celery worker + WuzAPI) sobe localmente e se comunica. Health checks verdes, worker conectado ao broker, schema atualizado.
- Class: operability
- Status: validated
- Description: O stack completo (Postgres + Dragonfly + backend + Celery worker + WuzAPI) sobe localmente e se comunica. Health checks verdes, worker conectado ao broker, schema atualizado.
- Why it matters: Sem stack funcional, nenhuma prova de integração é possível.
- Source: user
- Primary owning slice: M008/S01
- Supporting slices: none
- Validation: validated by S01 — backend health checks green (both /health and /api/v2/health), Celery worker connected to Dragonfly broker (inspect ping → pong), PostgreSQL hormonia_dev at Alembic head (m008_s01_t03_sessions_align), admin user seeded with functional login and session persistence in Dragonfly, .env configured with all required secrets and infra URLs. WuzAPI in mock mode for S01 — real connection validated by S02.
- Notes: Non-standard ports: Dragonfly on 6380, Postgres on 5434. Sessions table required alignment migration.

### R068 — WuzAPI rodando via Docker com número de teste conectado. Mensagem enviada via API chega no WhatsApp real.
- Class: integration
- Status: validated
- Description: WuzAPI rodando via Docker com número de teste conectado. Mensagem enviada via API chega no WhatsApp real.
- Why it matters: O valor do sistema depende de mensagens reais chegarem no WhatsApp do paciente.
- Source: user
- Primary owning slice: M008/S02
- Supporting slices: none
- Validation: validated by S02 — WuzAPI container running on port 8081 (healthy), WhatsApp number connected via QR code (JID confirmed), WuzAPIClient.send_text() delivered messages to real WhatsApp (multiple message IDs confirmed), user visual confirmation of receipt on phone, webhook URL and HMAC security configured. Critical auth fix: Token header instead of Authorization.
- Notes: Processo de QR code é manual e depende do usuário parear o número. WuzAPI on port 8081 (8080 taken by evolution_api).

### R069 — Templates de onboarding com 15 dias de conteúdo clínico real existem no banco via FlowTemplateVersion, com send_mode e expects_response corretos por mensagem.
- Class: core-capability
- Status: validated
- Description: Templates de onboarding com 15 dias de conteúdo clínico real existem no banco via FlowTemplateVersion, com send_mode e expects_response corretos por mensagem.
- Why it matters: Sem templates reais, o paciente recebe placeholders ou nenhuma mensagem.
- Source: inferred
- Primary owning slice: M008/S03
- Supporting slices: none
- Validation: validated by S03 — migration 9b4e2d1c7f66 seeds 9 onboarding steps (days 1,2,3,5,7,9,11,13,15) with real clinical content from markdown snapshots. EnhancedTemplateLoader.get_message_for_day() returns content for all protocol days with correct send_mode (sequential_auto, wait_response) and expects_response values. Verified by SQL queries + verify_templates.py + verify_template_metadata.py scripts.
- Notes: Not every calendar day has a step — 9 steps across 15 days, gaps intentional per clinical protocol.

### R070 — Médico cria paciente no dashboard, saga executa (create → flow → welcome → commit), welcome message chega no WhatsApp real do paciente.
- Class: primary-user-loop
- Status: validated
- Description: Médico cria paciente no dashboard, saga executa (create → flow → welcome → commit), welcome message chega no WhatsApp real do paciente.
- Why it matters: Este é o primeiro contato do paciente com o sistema. Se não funcionar, todo o resto é irrelevante.
- Source: user
- Primary owning slice: M008/S04
- Supporting slices: M008/S01, M008/S02, M008/S03
- Validation: validated by S04 — POST /api/v2/patients triggers 4-step onboarding saga (create → flow → welcome → commit), PatientFlowState created with status=active and flow_kind=onboarding, welcome message delivered via Celery → WuzAPI with status=sent and delivery_status=sent in messages table. Hybrid sync/async fix in PatientFlowService enabled AsyncSession compatibility in saga path.
- Notes: Celery beat not configured — welcome dispatch requires manual trigger via send_scheduled_message.delay() or running worker that picks up the task.

### R071 — process_daily_flows executa, seleciona template do dia correto, personaliza com IA (Gemini), e entrega mensagem no WhatsApp real do paciente.
- Class: core-capability
- Status: validated
- Description: process_daily_flows executa, seleciona template do dia correto, personaliza com IA (Gemini), e entrega mensagem no WhatsApp real do paciente.
- Why it matters: O acompanhamento diário é o core do produto. Precisa funcionar de verdade, não só em testes.
- Source: user
- Primary owning slice: M008/S04
- Supporting slices: M008/S01, M008/S02, M008/S03
- Validation: validated by S04 — process_daily_flows_async() executed successfully (processed_count=1, success_count=1, error_count=0), loaded day 1 onboarding template, personalized with Gemini 2.5, delivered via WuzAPI with status=sent. step_data updated with last_message_sent, current_flow_day=1, next_scheduled_at=tomorrow 9AM. Hybrid _resolve/_execute/_commit helpers in FlowCoreOperationsMixin enabled sync Session compatibility in async code paths.
- Notes: Inclui personalização IA se Gemini key estiver configurada. Celery beat not configured — daily processing requires manual trigger.

### R072 — Paciente responde livremente no WhatsApp, webhook do WuzAPI envia pro backend, MessageWebhookHandler processa, resposta persiste em patient_flow_responses com day_number e message_index.
- Class: core-capability
- Status: validated
- Description: Paciente responde livremente no WhatsApp, webhook do WuzAPI envia pro backend, MessageWebhookHandler processa, resposta persiste em patient_flow_responses com day_number e message_index.
- Why it matters: Sem captura de resposta, o resumo mensal do médico fica vazio.
- Source: user
- Primary owning slice: M008/S05
- Supporting slices: M008/S04
- Validation: validated by S05 — WuzAPI webhook _handle_message wired to full pipeline: _process_patient_message() finds patient by phone, creates inbound message record, _process_flow_response() dual-writes to patient_flow_responses (flow_state_id, day_number, message_index, response_text, responded_at) AND step_data.responses_by_message. Sequential continuation triggered after persistence. Proven by 23 webhook tests (flow processing, patient-not-found, general_chat paths) + code path verification.
- Notes: Uses db.run_sync() bridge pattern since WuzAPI webhook is async but repositories are sync. is_from_me guard skips WuzAPI echo messages.

### R073 — Quando current_day atinge 16, determine_flow_type() retorna DAILY_FOLLOW_UP e _transition_flow_type() muda o flow_type no PatientFlowState. Transição registrada em step_data.transitions.
- Class: continuity
- Status: validated
- Description: Quando current_day atinge 16, determine_flow_type() retorna DAILY_FOLLOW_UP e _transition_flow_type() muda o flow_type no PatientFlowState. Transição registrada em step_data.transitions.
- Why it matters: Se a transição não funcionar, paciente fica preso no onboarding ou pula direto pro quiz mensal.
- Source: inferred
- Primary owning slice: M008/S05
- Supporting slices: M008/S04
- Validation: validated by S05 — determine_flow_type boundary logic verified (≤15→onboarding, 16-45→daily_follow_up, 46+→quiz_mensal), _transition_flow_type records in step_data.transitions with {from_flow, to_flow, at_day, timestamp}, advance_patient_flow(force_day=16) triggers full transition with broadcaster and platform sync. Proven by 19 unit tests covering all boundary conditions, recording, and integration. Error handling + structured logging added.
- Notes: Transition logic pre-existed in FlowCoreTransitionsMixin. S05 focused on verification, proof, and observability rather than new implementation.

### R074 — Templates de daily follow-up com conteúdo clínico para dias 16-45 existem no banco com send_mode e expects_response corretos.
- Class: core-capability
- Status: validated
- Description: Templates de daily follow-up com conteúdo clínico para dias 16-45 existem no banco com send_mode e expects_response corretos.
- Why it matters: Sem templates de daily follow-up, a transição de fase no dia 16 resulta em "no template for day".
- Source: inferred
- Primary owning slice: M008/S03
- Supporting slices: none
- Validation: validated by S03 — migration 9b4e2d1c7f66 seeds 16 daily_follow_up steps (days 16,18,20,...,44,45) with real clinical content from markdown snapshots. EnhancedTemplateLoader.get_message_for_day() returns content for all protocol days with correct send_mode (single) and expects_response values. Verified by SQL queries + verify_templates.py + verify_template_metadata.py scripts.
- Notes: 16 steps across 30 calendar days; gap days return None from loader (intentional).

### R077 — Taskiq broker (Redis-backed via Dragonfly) e scheduler substituem celery_app.py. Worker processa tasks, scheduler dispara periodic tasks, FastAPI lifespan integra startup/shutdown.
- Class: operability
- Status: validated
- Description: Taskiq broker (Redis-backed via Dragonfly) e scheduler substituem celery_app.py. Worker processa tasks, scheduler dispara periodic tasks, FastAPI lifespan integra startup/shutdown.
- Why it matters: O Celery é sync-first num codebase async-first. A substituição elimina ~900 linhas de bridging code e simplifica o runtime.
- Source: user
- Primary owning slice: M009/S01
- Supporting slices: none
- Validation: validated — S01 proved runtime (ListQueueBroker on Dragonfly 6380, SmartRetryMiddleware, FastAPI lifespan, health checks), S05 proved Celery-free operation (celery_app.py deleted, imports clean), S06 proved test suite clean (4796 collected, zero Celery errors, AST scan PASS).
- Notes: Broker module reads env vars directly (not app.config.settings) for lightweight import. redis bumped to <8.0.0 for taskiq-redis compatibility.

### R078 — Abstração base para tasks Taskiq com SmartRetryMiddleware (exponential backoff + jitter), logging estruturado, e DB session via dependency injection (TaskiqDepends).
- Class: quality-attribute
- Status: validated
- Description: Abstração base para tasks Taskiq com SmartRetryMiddleware (exponential backoff + jitter), logging estruturado, e DB session via dependency injection (TaskiqDepends).
- Why it matters: BaseTask do Celery tem retry config, logging, e session management — a abstração Taskiq precisa cobrir o mesmo sem bridging.
- Source: inferred
- Primary owning slice: M009/S01
- Supporting slices: none
- Validation: validated — S01 proved SmartRetryMiddleware (3 retries, 60s base, 600s cap, jitter), DbSession=TaskiqDepends(get_db_session), structured logging. S06 proved all 29 test files adapted to Taskiq retry patterns (exception propagation instead of .retry() mocks). All collecting clean.
- Notes: Replaces Celery BaseTask + sync get_scoped_session() pattern. New pattern: @broker.task + async def + DbSession default param.

### R079 — send_scheduled_message, process_scheduled_messages, retry_failed_messages, send_bulk_messages, DLQ processing, e demais tasks de messaging operam via Taskiq worker.
- Class: core-capability
- Status: validated
- Description: send_scheduled_message, process_scheduled_messages, retry_failed_messages, send_bulk_messages, DLQ processing, e demais tasks de messaging operam via Taskiq worker.
- Why it matters: Messaging é o hot path — envio de mensagens WhatsApp para pacientes. Precisa funcionar sem interrupção.
- Source: user
- Primary owning slice: M009/S02
- Supporting slices: M009/S01
- Validation: validated — S02 proved messaging tasks operate via Taskiq (send_scheduled_message.kiq(), process_scheduled_messages, retry_failed_messages, DLQ). S05 deleted Celery messaging.py. S06 proved all messaging test files use messaging_taskiq imports exclusively (AST PASS).
- Notes: Inclui migração de call sites (.delay → .kiq) dentro do domínio messaging.

### R080 — process_daily_flows, flow_automation, saga_retry, stuck_detection, monthly_tasks, e demais tasks de flow operam via Taskiq worker com async nativo.
- Class: core-capability
- Status: validated
- Description: process_daily_flows, flow_automation, saga_retry, stuck_detection, monthly_tasks, e demais tasks de flow operam via Taskiq worker com async nativo.
- Why it matters: Flow tasks são o core do acompanhamento diário — process_daily_flows usa async DB, IA Gemini, e WuzAPI.
- Source: user
- Primary owning slice: M009/S03
- Supporting slices: M009/S01, M009/S02
- Validation: validated — S03 proved flow tasks async-native (process_daily_flows, saga_retry, stuck_detection, monthly_tasks, flow_automation). S05 deleted Celery flows/ directory. S06 proved all flow test files use flows_taskiq/helpers.flow_helpers imports (AST PASS, 32+ flow tests collected).
- Notes: Com Taskiq async-native, tasks podem usar await direto sem hybrid _resolve/_execute.

### R081 — Quiz link tasks, trigger tasks, response tasks, alertas, follow-up, LGPD, audit cleanup, webhook DLQ, e monitoring tasks operam via Taskiq.
- Class: core-capability
- Status: validated
- Description: Quiz link tasks, trigger tasks, response tasks, alertas, follow-up, LGPD, audit cleanup, webhook DLQ, e monitoring tasks operam via Taskiq.
- Why it matters: Completa a migração de todas as tasks restantes para Taskiq.
- Source: user
- Primary owning slice: M009/S04
- Supporting slices: M009/S01
- Validation: validated — S04 proved 72 @broker.task declarations across 13 modules (quiz, alerts, follow_up, LGPD, audit, webhook_dlq, monitoring). S05 deleted Celery originals. S06 proved all test files use *_taskiq imports (AST PASS, 4796 tests collected).
- Notes: Combined with S02 (messaging) and S03 (flows/saga), all task groups now have Taskiq equivalents. MonitoringTask class hierarchy flattened, quiz_flow 4-file subpackage consolidated.

### R082 — Todas as 40+ entries do Celery beat_schedule estão no Taskiq scheduler com timing equivalente (crontab e interval).
- Class: continuity
- Status: validated
- Description: Todas as 40+ entries do Celery beat_schedule estão no Taskiq scheduler com timing equivalente (crontab e interval).
- Why it matters: Sem schedule periódico, tasks como process_daily_flows, retry_failed_messages, e check_patient_alerts não disparam automaticamente.
- Source: inferred
- Primary owning slice: M009/S04
- Supporting slices: M009/S02, M009/S03
- Validation: validated — S04 proved 47/47 schedule parity via verify_schedule_parity.sh. S05 removed Celery beat_schedule. S06 verified 72 @broker.task decorators across 13 *_taskiq.py files, with schedule configuration in LabelScheduleSource.
- Notes: Schedule labels come from S02 (7 messaging), S03 (12 flow/saga), and S04 (28 remaining) — combined total 47.

### R083 — Todos os ~20 call sites que usam .delay() ou .apply_async() foram migrados para .kiq() do Taskiq.
- Class: continuity
- Status: validated
- Description: Todos os ~20 call sites que usam .delay() ou .apply_async() foram migrados para .kiq() do Taskiq.
- Why it matters: Call sites são a interface entre services/handlers e o task queue — cada um não migrado é um ponto de falha.
- Source: inferred
- Primary owning slice: M009/S04
- Supporting slices: M009/S02, M009/S03
- Validation: validated — S04 proved zero external .delay()/.apply_async() call sites. S05 deleted all Celery dispatch code. S06 proved zero apply_async/schedule_celery_task/cancel_celery_task references in tests/ (grep PASS).
- Notes: 3 remaining call sites are in sync code chains that require cascading async conversion — S05 handles these when Celery is removed.

### R084 — async_context_manager.py, run_async_in_celery(), async_helpers.py (partes que só existem para Celery), e demais bridge code removidos.
- Class: operability
- Status: validated
- Description: async_context_manager.py, run_async_in_celery(), async_helpers.py (partes que só existem para Celery), e demais bridge code removidos.
- Why it matters: Com Taskiq async-native, o bridge code é dead weight — complexidade sem valor.
- Source: user
- Primary owning slice: M009/S05
- Supporting slices: none
- Validation: validated by S05 — celery_app.py (run_async_in_celery), async_context_manager.py, async_helpers.py, event_loop_manager.py, async_handler.py all deleted. 12 Celery task files deleted. flows/, quiz_flow/, lgpd/ directories deleted. tasks/base.py, config.py, celery_metrics.py, queue_monitor.py deleted. AST scan confirms zero Celery imports across entire app/ directory (V1 PASS). 30 files removed total.
- Notes: Helpers extracted to app/tasks/helpers/ before deletion (9 domain modules). tasks/__init__.py re-exports 72 task functions from 13 *_taskiq.py modules.

### R085 — celery, celery[redis], kombu, amqp, billiard, flower, e qualquer dep que só existe para Celery são removidos.
- Class: operability
- Status: validated
- Description: celery, celery[redis], kombu, amqp, billiard, flower, e qualquer dep que só existe para Celery são removidos.
- Why it matters: Dependências mortas aumentam superfície de ataque, tempo de install, e confusão de manutenção.
- Source: user
- Primary owning slice: M009/S05
- Supporting slices: none
- Validation: validated by S05 — celery>=5.6.2, celery[redis]>=5.6.2, asgiref>=3.11.0, flower==2.0.1 removed from requirements.txt. grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' returns nothing (V3 PASS). docker-compose.yml worker/beat commands use taskiq. Makefile targets use taskiq-worker/taskiq-scheduler.
- Notes: asgiref also removed — only used for sync_to_async/async_to_sync bridging in Celery context. prometheus-client retained (used by Taskiq metrics).

### R086 — O pipeline completo provado em M008 funciona via Taskiq: create patient → welcome → daily flow → response → transition.
- Class: integration
- Status: validated
- Description: O pipeline completo provado em M008 funciona via Taskiq: create patient → welcome → daily flow → response → transition.
- Why it matters: M008 é a prova de que o sistema funciona. Se regredir com a migração, o milestone falha.
- Source: inferred
- Primary owning slice: M009/S06
- Supporting slices: M009/S02, M009/S03, M009/S05
- Validation: validated by S06 — 4796 tests collected (zero Celery-related errors), AST scan confirms zero deleted-module imports in tests/, all M008 pipeline test files (test_patient_onboarding_e2e, test_saga_orchestrator, test_saga_onboarding_happy_path, test_flow_recovery_retry_e2e, test_flow_tasks_hardening) use Taskiq-only imports (.kiq, messaging_taskiq, flows_taskiq). Combined with S02 runtime proof (send_scheduled_message via Taskiq worker → WuzAPI) and S03 runtime proof (process_daily_flows async-native), the full create→welcome→daily→response→transition pipeline operates via Taskiq.
- Notes: Terminal verification — S06 closed the test-suite gap, S02/S03/S05 provided implementation+runtime proof. Milestone M009 complete.

## Deferred

### R020 — Add a second factor for high-privilege staff authentication.
- Class: compliance/security
- Status: deferred
- Description: Add a second factor for high-privilege staff authentication.
- Why it matters: It may become necessary for stronger operational security later.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred because the immediate priority is removing Firebase Auth cleanly without expanding scope.

### R021 — Allow organizations to authenticate staff through an external identity provider.
- Class: integration
- Status: deferred
- Description: Allow organizations to authenticate staff through an external identity provider.
- Why it matters: It could matter if the product grows into multi-organization enterprise onboarding.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Explicitly not part of M002.

### R022 — Map ADK errors to a stable HTTP envelope with deterministic categories.
- Class: quality-attribute
- Status: deferred
- Description: Map ADK errors to a stable HTTP envelope with deterministic categories.
- Why it matters: This remains useful future work but is unrelated to the current auth cutover milestone.
- Source: execution
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Carries forward prior deferred project work.

### R023 — Define a project-wide policy for retryable ADK calls and idempotent handling.
- Class: operability
- Status: deferred
- Description: Define a project-wide policy for retryable ADK calls and idempotent handling.
- Why it matters: It is important future stabilization work, but not part of the current login cutover.
- Source: execution
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Carries forward prior deferred project work.

### R040 — Add automated size ceilings or architectural budget checks so new hotspots do not quietly regrow after M003.
- Class: quality-attribute
- Status: deferred
- Description: Add automated size ceilings or architectural budget checks so new hotspots do not quietly regrow after M003.
- Why it matters: Manual cleanup without a guardrail can decay back into the same problem.
- Source: research
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Useful follow-up, but not required to make the first cleanup milestone shippable.

### R041 — Apply the same hotspot-splitting discipline to the AI/ADK runtime and related large modules once the first cleanup wave is complete.
- Class: integration
- Status: deferred
- Description: Apply the same hotspot-splitting discipline to the AI/ADK runtime and related large modules once the first cleanup wave is complete.
- Why it matters: Those areas are large and risky, but they are not the first attack zone for this milestone.
- Source: discussion
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: The user prioritized backend auth/session first; AI/ADK stays sensitive and deserves its own focused pass later.

### R042 — Finish broad export-surface and duplicate-type cleanup across all frontend domains after the highest-value client/type hotspots are stabilized.
- Class: operability
- Status: deferred
- Description: Finish broad export-surface and duplicate-type cleanup across all frontend domains after the highest-value client/type hotspots are stabilized.
- Why it matters: The frontend has many re-export layers and compatibility aliases, but M003 should focus first on the central client/type seam.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred to avoid turning the current milestone into a repo-wide churn event.

### R064 — Possibilidade de ajustar dias específicos do fluxo para um paciente individual, em cima do template global do médico.
- Class: admin/support
- Status: deferred
- Description: Possibilidade de ajustar dias específicos do fluxo para um paciente individual, em cima do template global do médico.
- Why it matters: Pode ser útil para personalizar acompanhamento de pacientes com necessidades especiais.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred — o template global por médico cobre o caso principal. Override por paciente adiciona complexidade significativa.

### R096 — Notificações push/realtime para alertas críticos do quiz (push browser, badge no menu).
- Class: failure-visibility
- Status: deferred
- Description: Quando um alerta crítico é gerado pelo quiz do paciente, o médico recebe notificação push no browser e/ou badge visível no menu do dashboard, sem precisar estar na tela de alertas.
- Why it matters: Alerta que depende do médico navegar até a tela de alertas pode ser visto tarde demais.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred — M010 foca em polimento da visão geral e preparo pré-consulta. Push notifications entram em milestone futuro.

### R097 — Export de relatório do paciente em PDF real para levar para consulta.
- Class: admin/support
- Status: deferred
- Description: O médico exporta um relatório completo do paciente (resumo IA + respostas + alertas + fluxo) em PDF formatado para impressão ou referência durante consulta.
- Why it matters: Alguns médicos preferem ter papel ou PDF aberto durante a consulta em vez de navegar pelo dashboard.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred — o export atual gera JSON. PDF real requer formatting library. Milestone futuro.

## Out of Scope

### R030 — Staff users do not create their own accounts publicly during M002.
- Class: anti-feature
- Status: out-of-scope
- Description: Staff users do not create their own accounts publicly during M002.
- Why it matters: This prevents scope creep into a very different security and onboarding problem.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Account creation remains admin-managed.

### R031 — M002 does not support CRM-only login or dual email+CRM login.
- Class: constraint
- Status: out-of-scope
- Description: M002 does not support CRM-only login or dual email+CRM login.
- Why it matters: Standardizing on email keeps the cutover smaller and more supportable.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The user explicitly chose email-only login.

### R032 — The milestone does not preserve a prolonged dual-auth runtime mode after cutover.
- Class: anti-feature
- Status: out-of-scope
- Description: The milestone does not preserve a prolonged dual-auth runtime mode after cutover.
- Why it matters: The user’s stated goal is to remove the dependency, not carry it indefinitely.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Short implementation scaffolding during execution is acceptable; the shipped state must be hard cut.

### R033 — M002 does not redesign the public patient/quiz auth flows beyond any incidental compatibility impact.
- Class: constraint
- Status: out-of-scope
- Description: M002 does not redesign the public patient/quiz auth flows beyond any incidental compatibility impact.
- Why it matters: The immediate pain and asked-for scope are staff authentication, not patient-facing access.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Quiz session flows remain separate unless a concrete dependency emerges during implementation.

### R043 — M003 does not expand product scope with new features while refactoring the existing system.
- Class: anti-feature
- Status: out-of-scope
- Description: M003 does not expand product scope with new features while refactoring the existing system.
- Why it matters: Feature work would blur whether the milestone actually paid down structural risk.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The milestone is about maintainability and safe cleanup, not new end-user functionality.

### R044 — M003 does not intentionally redesign stable visible contracts unless a change is required to remove proven dead or obsolete structure.
- Class: constraint
- Status: out-of-scope
- Description: M003 does not intentionally redesign stable visible contracts unless a change is required to remove proven dead or obsolete structure.
- Why it matters: The user explicitly does not want the refactor to cross into unnecessary behavior or payload drift.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Contract continuity is a core guardrail for the milestone.

### R045 — M003 does not attempt to replace the project architecture wholesale or replatform major subsystems under the banner of cleanup.
- Class: anti-feature
- Status: out-of-scope
- Description: M003 does not attempt to replace the project architecture wholesale or replatform major subsystems under the banner of cleanup.
- Why it matters: A rewrite would destroy the milestone’s constraint of making the current system safer to change.
- Source: discussion
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The user wants aggressive cleanup, not a disguised restart.

### R046 — M003 does not broaden into schema redesign work except for incidental adjustments directly required by in-scope cleanup.
- Class: constraint
- Status: out-of-scope
- Description: M003 does not broaden into schema redesign work except for incidental adjustments directly required by in-scope cleanup.
- Why it matters: Schema churn would expand the blast radius far beyond the stated maintainability target.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Redis/Postgres session behavior is sensitive and should be preserved, not redesigned, during this milestone.

### R054 — A frente M004–M006 não existe para expandir produto; ela existe para convergir runtime, schema e legado restante.
- Class: anti-feature
- Status: out-of-scope
- Description: A frente M004–M006 não existe para expandir produto; ela existe para convergir runtime, schema e legado restante.
- Why it matters: Adicionar feature nova misturaria lapidação estrutural com expansão de escopo e tornaria a prova final menos honesta.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Melhorias funcionais novas entram em milestone própria depois da convergência.

### R055 — A nova frente não vai manter Firebase vivo em paralelo ao runtime oficial apenas por precaução.
- Class: anti-feature
- Status: out-of-scope
- Description: A nova frente não vai manter Firebase vivo em paralelo ao runtime oficial apenas por precaução.
- Why it matters: Isso contradiz diretamente a decisão do usuário de não utilizar mais Firebase no sistema.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Compatibilidades só sobrevivem se forem pontes explicitamente justificadas e com prazo claro de remoção.

### R056 — M004–M006 não são licença para recomeçar a arquitetura do zero ou trocar a base tecnológica em bloco.
- Class: anti-feature
- Status: out-of-scope
- Description: M004–M006 não são licença para recomeçar a arquitetura do zero ou trocar a base tecnológica em bloco.
- Why it matters: O objetivo é convergir a base atual com segurança e prova, não esconder uma reescrita dentro de cleanup.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Mudanças amplas só entram se uma pesquisa futura provar necessidade real e escopo separado.

### R065 — O paciente não navega por menus ou opções pré-definidas. Responde livremente com texto.
- Class: anti-feature
- Status: out-of-scope
- Description: O paciente não navega por menus ou opções pré-definidas. Responde livremente com texto.
- Why it matters: A liberdade de resposta é o diferencial — paciente conversa, não opera um menu.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Decisão explícita do usuário. O sistema processa texto livre, não limita opções.

### R066 — Interface visual com canvas, nós e conexões para o médico montar fluxos. Substituído por editor simples de lista de dias.
- Class: anti-feature
- Status: out-of-scope
- Description: Interface visual com canvas, nós e conexões para o médico montar fluxos. Substituído por editor simples de lista de dias.
- Why it matters: Médico não tem tempo nem interesse em montar workflows visuais. Quer editar texto e tipo de dia.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: O FlowDesigner existente (~3300 linhas) será removido em M007/S02.

### R075 — Prova ponta-a-ponta do ciclo de quiz mensal (dia 30+) não está no escopo de M008.
- Class: constraint
- Status: out-of-scope
- Description: Prova ponta-a-ponta do ciclo de quiz mensal (dia 30+) não está no escopo de M008.
- Why it matters: O ciclo de 30+ dias é impraticável de provar no mesmo milestone que setup do stack. Lógica de quiz já provada em M007/S05.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Quiz mensal pode ser milestone futuro se necessário.

### R076 — Deploy automatizado em ambiente de produção ou staging não está no escopo de M008.
- Class: constraint
- Status: out-of-scope
- Description: Deploy automatizado em ambiente de produção ou staging não está no escopo de M008.
- Why it matters: Separar setup local de deploy evita misturar riscos.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Deploy seria milestone separado.

### R087 — Polimento da experiência do médico no dashboard não está no escopo de M009.
- Class: anti-feature
- Status: out-of-scope
- Description: Polimento da experiência do médico no dashboard não está no escopo de M009.
- Why it matters: M009 é infraestrutura de task queue — misturar com UX seria escopo cruzado.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Dashboard polish é M010.

### R088 — M009 não adiciona tasks novas nem muda comportamento — migração preserva paridade funcional exata.
- Class: anti-feature
- Status: out-of-scope
- Description: M009 não adiciona tasks novas nem muda comportamento — migração preserva paridade funcional exata.
- Why it matters: Adicionar features durante migração de infraestrutura mistura riscos e torna regressões difíceis de isolar.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Melhorias funcionais entram em milestone posterior.

### R098 — M010 não muda lógica de backend de fluxos, tasks, ou processamento de mensagens.
- Class: constraint
- Status: out-of-scope
- Description: M010 é UX/frontend com ajustes mínimos de API de listagem. Não altera lógica de processamento de fluxos, tasks Taskiq, envio de mensagens, ou pipeline de dados.
- Why it matters: Misturar refactor de UX com mudanças de backend de processamento cria riscos cruzados.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Backend changes limitados a endpoint de listagem enriquecida.

### R099 — M010 não redesenha o dashboard admin (/dashboard).
- Class: constraint
- Status: out-of-scope
- Description: O DashboardPage.tsx (/dashboard) para admin/operacional não é alterado por M010. Foco exclusivo no physician dashboard.
- Why it matters: Evita escopo cruzado e mantém o milestone focado no público médico.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Admin dashboard pode ser milestone futuro se necessário.

### R103 — M011 não muda comportamento funcional — otimização pura, zero regressão.
- Class: constraint
- Status: out-of-scope
- Description: M011 otimiza performance sem alterar comportamento funcional. Nenhum endpoint muda sua response shape, nenhuma feature é adicionada ou removida.
- Why it matters: Mudanças de performance que alteram comportamento são bugs, não otimizações.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Build green e mesma response shape são os gates.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | continuity | validated | M001/S01 | none | validated |
| R002 | operability | validated | M001/S02 | none | validated |
| R003 | failure-visibility | validated | M001/S03 | none | validated |
| R004 | quality-attribute | validated | M001/S04 | none | validated |
| R005 | primary-user-loop | validated | M002/S01 | M002/S03, M002/S04 | validated |
| R006 | continuity | validated | M002/S01 | M002/S03, M002/S04 | validated |
| R007 | launchability | validated | M002/S02 | M002/S04 | validated |
| R008 | admin/support | validated | M002/S02 | M002/S03 | validated |
| R009 | continuity | validated | M002/S02 | M002/S04 | validated |
| R010 | integration | validated | M002/S03 | M002/S01, M002/S04 | validated |
| R011 | constraint | validated | M002/S04 | M002/S01, M002/S03 | validated |
| R012 | failure-visibility | validated | M002/S04 | M002/S01, M002/S02, M002/S03 | validated |
| R020 | compliance/security | deferred | none | none | unmapped |
| R021 | integration | deferred | none | none | unmapped |
| R022 | quality-attribute | deferred | none | none | unmapped |
| R023 | operability | deferred | none | none | unmapped |
| R030 | anti-feature | out-of-scope | none | none | n/a |
| R031 | constraint | out-of-scope | none | none | n/a |
| R032 | anti-feature | out-of-scope | none | none | n/a |
| R033 | constraint | out-of-scope | none | none | n/a |
| R034 | quality-attribute | validated | M003/S02 | M003/S03, M003/S04 | validated |
| R035 | failure-visibility | validated | M003/S01 | M003/S04 | validated |
| R036 | constraint | validated | M003/S04 | M003/S02, M003/S03 | validated |
| R037 | continuity | validated | M003/S05 | M003/S02, M003/S03, M003/S04 | validated |
| R038 | operability | validated | M003/S05 | M003/S02, M003/S03, M003/S04 | validated |
| R039 | quality-attribute | validated | M003/S05 | M003/S01, M003/S02, M003/S03, M003/S04 | validated |
| R040 | quality-attribute | deferred | none | none | unmapped |
| R041 | integration | deferred | none | none | unmapped |
| R042 | operability | deferred | none | none | unmapped |
| R043 | anti-feature | out-of-scope | none | none | n/a |
| R044 | constraint | out-of-scope | none | none | n/a |
| R045 | anti-feature | out-of-scope | none | none | n/a |
| R046 | constraint | out-of-scope | none | none | n/a |
| R047 | constraint | validated | M004/S05 | M004/S01, M004/S02, M004/S03, M004/S04, M004/S06 | validated |
| R048 | continuity | validated | M004/S02 | M004/S01, M004/S03, M004/S04 | validated |
| R049 | integration | validated | M004/S02 | M004/S01, M004/S04, M004/S05 | validated |
| R050 | primary-user-loop | validated | M004/S03 | M004/S01, M004/S04, M004/S05, M004/S06 | validated |
| R051 | quality-attribute | validated | M005/S03 | M005/S01, M005/S02 | validated by M005/S03 clean+existing head convergence proof and canonical runtime contract suites |
| R052 | operability | validated | M006/S04 | M006/S01, M006/S02, M006/S03 | validated by M006-VERIFY.json — 10 proof phases green: residue guards, focused backend packs, schema convergence under Postgres, absence scans, frontend import-boundary/build, and final-schema proof fresh/existing with mounted backend replay |
| R053 | quality-attribute | validated | M005/S04 | M004/S06, M005/S01, M005/S03 | validated by M004/S06 mounted runtime proof plus M005/S04 final-schema fresh/existing backend replay on the canonical head |
| R054 | anti-feature | out-of-scope | none | none | n/a |
| R055 | anti-feature | out-of-scope | none | none | n/a |
| R056 | anti-feature | out-of-scope | none | none | n/a |
| R057 | core-capability | validated | M007/S01 | none | validated by 11 focused tests in test_sequencing_expects_response.py proving per-message expects_response across all send modes (sequential_auto, wait_each, remaining_after_response) plus edge cases (idempotency, first-message stop, default single mode), with 0 regressions across 36 total flow tests |
| R058 | primary-user-loop | validated | M007/S03 | M007/S01, M007/S02 | validated by S03 — GET/PUT /flows/{template_id}/days API with physician-friendly DayConfigItem projection/hydration, DayConfigEditor dialog in FlowTemplateCard, 30 focused tests proving round-trip fidelity and validate_day_config() loader compatibility, frontend typecheck + build green |
| R059 | operability | validated | M007/S02 | none | validated by S02 — FlowDesigner visual (~4800 lines) deleted, 7 phantom FlowType members removed from enum (only ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM remain), tombstoned flow/templates package deleted (4 files), ~4600 lines of dead tests deleted (8 files), normalize_flow_type stale fallback proven, frontend build + typecheck green, backend flow tests green (84 passed, 0 failed), separate enums (AlertRuleType, MetricType, AnalyticsEventType) untouched |
| R060 | differentiator | validated | M007/S04 | M007/S01 | validated by S04 — 25 focused unit tests proving _personalization_is_grounded() boundary cases (similarity ≥ 0.6, keyword overlap ≥ 0.2, no-keyword ≥ 0.35), _select_template_variation() determinism, _lightly_rephrase_question() logic, and AI-skip for non-response messages. All tests use realistic Portuguese oncology content. |
| R061 | core-capability | validated | M007/S04 | M007/S01 | validated by S04 — PatientFlowResponse model + Alembic migration, dual-write in process_patient_response() persisting to patient_flow_responses alongside step_data JSONB in same transaction, GET /api/v2/patients/{id}/flow-responses with date-range filtering, 14 integration tests proving write-through and query paths, 0 regressions across 154 flow tests |
| R062 | failure-visibility | validated | M007/S05 | M007/S04 | validated by S05 — QuizResponseEvaluator wired into complete_quiz_session(), Notification records created for patient's doctor on triggered alerts, duplicate alert guard, _serialize_alert() returns title/message/recommendation, PhysicianDashboard renders recommendation text. Proven by 14 focused tests covering full chain + 42 API tests with 0 regressions. |
| R063 | differentiator | validated | M007/S06 | M007/S04, M007/S05 | validated by S06 — SummaryDataAggregator wired to patient_flow_responses + enriched alerts (description + recommendation from JSONB), prompt template with {flow_responses} section, Brain icon quick-access in PhysicianDashboard navigating to ?tab=ai-summary, 13 focused tests proving aggregator integration + 0 regressions across 181 flow tests, frontend typecheck green |
| R064 | admin/support | deferred | none | none | unmapped |
| R065 | anti-feature | out-of-scope | none | none | n/a |
| R066 | anti-feature | out-of-scope | none | none | n/a |
| R067 | operability | validated | M008/S01 | none | validated by S01 — backend health checks green (both /health and /api/v2/health), Celery worker connected to Dragonfly broker (inspect ping → pong), PostgreSQL hormonia_dev at Alembic head (m008_s01_t03_sessions_align), admin user seeded with functional login and session persistence in Dragonfly, .env configured with all required secrets and infra URLs. WuzAPI in mock mode for S01 — real connection validated by S02. |
| R068 | integration | validated | M008/S02 | none | validated by S02 — WuzAPI container running on port 8081 (healthy), WhatsApp number connected via QR code (JID confirmed), WuzAPIClient.send_text() delivered messages to real WhatsApp (multiple message IDs confirmed), user visual confirmation of receipt on phone, webhook URL and HMAC security configured. Critical auth fix: Token header instead of Authorization. |
| R069 | core-capability | validated | M008/S03 | none | validated by S03 — migration 9b4e2d1c7f66 seeds 9 onboarding steps (days 1,2,3,5,7,9,11,13,15) with real clinical content from markdown snapshots. EnhancedTemplateLoader.get_message_for_day() returns content for all protocol days with correct send_mode (sequential_auto, wait_response) and expects_response values. Verified by SQL queries + verify_templates.py + verify_template_metadata.py scripts. |
| R070 | primary-user-loop | validated | M008/S04 | M008/S01, M008/S02, M008/S03 | validated by S04 — POST /api/v2/patients triggers 4-step onboarding saga (create → flow → welcome → commit), PatientFlowState created with status=active and flow_kind=onboarding, welcome message delivered via Celery → WuzAPI with status=sent and delivery_status=sent in messages table. Hybrid sync/async fix in PatientFlowService enabled AsyncSession compatibility in saga path. |
| R071 | core-capability | validated | M008/S04 | M008/S01, M008/S02, M008/S03 | validated by S04 — process_daily_flows_async() executed successfully (processed_count=1, success_count=1, error_count=0), loaded day 1 onboarding template, personalized with Gemini 2.5, delivered via WuzAPI with status=sent. step_data updated with last_message_sent, current_flow_day=1, next_scheduled_at=tomorrow 9AM. Hybrid _resolve/_execute/_commit helpers in FlowCoreOperationsMixin enabled sync Session compatibility in async code paths. |
| R072 | core-capability | validated | M008/S05 | M008/S04 | validated by S05 — WuzAPI webhook _handle_message wired to full pipeline: _process_patient_message() finds patient by phone, creates inbound message record, _process_flow_response() dual-writes to patient_flow_responses (flow_state_id, day_number, message_index, response_text, responded_at) AND step_data.responses_by_message. Sequential continuation triggered after persistence. Proven by 23 webhook tests (flow processing, patient-not-found, general_chat paths) + code path verification. |
| R073 | continuity | validated | M008/S05 | M008/S04 | validated by S05 — determine_flow_type boundary logic verified (≤15→onboarding, 16-45→daily_follow_up, 46+→quiz_mensal), _transition_flow_type records in step_data.transitions with {from_flow, to_flow, at_day, timestamp}, advance_patient_flow(force_day=16) triggers full transition with broadcaster and platform sync. Proven by 19 unit tests covering all boundary conditions, recording, and integration. Error handling + structured logging added. |
| R074 | core-capability | validated | M008/S03 | none | validated by S03 — migration 9b4e2d1c7f66 seeds 16 daily_follow_up steps (days 16,18,20,...,44,45) with real clinical content from markdown snapshots. EnhancedTemplateLoader.get_message_for_day() returns content for all protocol days with correct send_mode (single) and expects_response values. Verified by SQL queries + verify_templates.py + verify_template_metadata.py scripts. |
| R075 | constraint | out-of-scope | none | none | n/a |
| R076 | constraint | out-of-scope | none | none | n/a |
| R077 | operability | validated | M009/S01 | none | validated — S01 proved runtime (ListQueueBroker on Dragonfly 6380, SmartRetryMiddleware, FastAPI lifespan, health checks), S05 proved Celery-free operation (celery_app.py deleted, imports clean), S06 proved test suite clean (4796 collected, zero Celery errors, AST scan PASS). |
| R078 | quality-attribute | validated | M009/S01 | none | validated — S01 proved SmartRetryMiddleware (3 retries, 60s base, 600s cap, jitter), DbSession=TaskiqDepends(get_db_session), structured logging. S06 proved all 29 test files adapted to Taskiq retry patterns (exception propagation instead of .retry() mocks). All collecting clean. |
| R079 | core-capability | validated | M009/S02 | M009/S01 | validated — S02 proved messaging tasks operate via Taskiq (send_scheduled_message.kiq(), process_scheduled_messages, retry_failed_messages, DLQ). S05 deleted Celery messaging.py. S06 proved all messaging test files use messaging_taskiq imports exclusively (AST PASS). |
| R080 | core-capability | validated | M009/S03 | M009/S01, M009/S02 | validated — S03 proved flow tasks async-native (process_daily_flows, saga_retry, stuck_detection, monthly_tasks, flow_automation). S05 deleted Celery flows/ directory. S06 proved all flow test files use flows_taskiq/helpers.flow_helpers imports (AST PASS, 32+ flow tests collected). |
| R081 | core-capability | validated | M009/S04 | M009/S01 | validated — S04 proved 72 @broker.task declarations across 13 modules (quiz, alerts, follow_up, LGPD, audit, webhook_dlq, monitoring). S05 deleted Celery originals. S06 proved all test files use *_taskiq imports (AST PASS, 4796 tests collected). |
| R082 | continuity | validated | M009/S04 | M009/S02, M009/S03 | validated — S04 proved 47/47 schedule parity via verify_schedule_parity.sh. S05 removed Celery beat_schedule. S06 verified 72 @broker.task decorators across 13 *_taskiq.py files, with schedule configuration in LabelScheduleSource. |
| R083 | continuity | validated | M009/S04 | M009/S02, M009/S03 | validated — S04 proved zero external .delay()/.apply_async() call sites. S05 deleted all Celery dispatch code. S06 proved zero apply_async/schedule_celery_task/cancel_celery_task references in tests/ (grep PASS). |
| R084 | operability | validated | M009/S05 | none | validated by S05 — celery_app.py (run_async_in_celery), async_context_manager.py, async_helpers.py, event_loop_manager.py, async_handler.py all deleted. 12 Celery task files deleted. flows/, quiz_flow/, lgpd/ directories deleted. tasks/base.py, config.py, celery_metrics.py, queue_monitor.py deleted. AST scan confirms zero Celery imports across entire app/ directory (V1 PASS). 30 files removed total. |
| R085 | operability | validated | M009/S05 | none | validated by S05 — celery>=5.6.2, celery[redis]>=5.6.2, asgiref>=3.11.0, flower==2.0.1 removed from requirements.txt. grep -iE 'celery|kombu|amqp|billiard|flower|asgiref' returns nothing (V3 PASS). docker-compose.yml worker/beat commands use taskiq. Makefile targets use taskiq-worker/taskiq-scheduler. |
| R086 | integration | validated | M009/S06 | M009/S02, M009/S03, M009/S05 | validated by S06 — 4796 tests collected (zero Celery-related errors), AST scan confirms zero deleted-module imports in tests/, all M008 pipeline test files (test_patient_onboarding_e2e, test_saga_orchestrator, test_saga_onboarding_happy_path, test_flow_recovery_retry_e2e, test_flow_tasks_hardening) use Taskiq-only imports (.kiq, messaging_taskiq, flows_taskiq). Combined with S02 runtime proof (send_scheduled_message via Taskiq worker → WuzAPI) and S03 runtime proof (process_daily_flows async-native), the full create→welcome→daily→response→transition pipeline operates via Taskiq. |
| R087 | anti-feature | out-of-scope | none | none | n/a |
| R088 | anti-feature | out-of-scope | none | none | n/a |
| R089 | primary-user-loop | active | M010/S01 | none | unmapped |
| R090 | primary-user-loop | active | M010/S02 | M010/S01 | unmapped |
| R091 | integration | active | M010/S01 | none | unmapped |
| R092 | primary-user-loop | active | M010/S02 | M010/S01 | unmapped |
| R093 | quality-attribute | active | M010/S04 | M010/S01, M010/S02 | unmapped |
| R094 | operability | active | M010/S03 | none | unmapped |
| R095 | constraint | active | M010/S01 | none | unmapped |
| R096 | failure-visibility | deferred | none | none | unmapped |
| R097 | admin/support | deferred | none | none | unmapped |
| R098 | constraint | out-of-scope | none | none | n/a |
| R099 | constraint | out-of-scope | none | none | n/a |
| R100 | quality-attribute | validated | M011/S01 | none | validated by S01 + verify-m011.sh group 5 |
| R101 | quality-attribute | validated | M011/S01 | none | validated by S01 + verify-m011.sh group 7 |
| R102 | quality-attribute | validated | M011/S02 | none | validated by S02 + verify-m011.sh group 6 |
| R103 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 7 (R089–R095)
- Mapped to slices: 10
- Validated: 50
- Deferred: 10
- Out of scope: 20
- Unmapped active requirements: 0
