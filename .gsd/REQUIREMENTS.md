# Requirements

This file is the explicit capability and coverage contract for the project.

Use it to track what is actively in scope, what has been validated by completed work, what is intentionally deferred, and what is explicitly out of scope.

Guidelines:
- Keep requirements capability-oriented, not a giant feature wishlist.
- Requirements should be atomic, testable, and stated in plain language.
- Every **Active** requirement should be mapped to a slice, deferred, blocked with reason, or moved out of scope.
- Each requirement should have one accountable primary owner and may have supporting slices.
- Research may suggest requirements, but research does not silently make them binding.
- Validation means the requirement was actually proven by completed work and verification, not just discussed.

## Active

### R058 — Médico edita templates dia-a-dia por UI simples
- Class: primary-user-loop
- Status: active
- Description: O médico tem uma interface de lista de dias para editar conteúdo, adicionar/remover dias, definir tipo (pergunta, motivação, lembrete), e marcar se espera resposta. Template global por médico.
- Why it matters: Os templates atuais são rascunhos de teste. O médico precisa configurar o fluxo do seu consultório sem complexidade visual estilo N8N.
- Source: user
- Primary owning slice: M007/S03
- Supporting slices: M007/S01, M007/S02
- Validation: mapped
- Notes: O FlowDesigner visual existente (~3300 linhas) é overengineered para o caso real e será removido.

### R059 — Abstrações mortas de fluxo são removidas com prova
- Class: operability
- Status: active
- Description: FlowDesigner visual, FlowTypes fantasma no enum, knowledge graph morto, tombstones residuais e mixin soup são removidos ou simplificados com prova.
- Why it matters: Abstrações mortas dificultam manutenção e escondem bugs no subsistema que mais precisa de clareza.
- Source: inferred
- Primary owning slice: M007/S02
- Supporting slices: none
- Validation: mapped
- Notes: FlowDesigner (~3300 linhas), FlowTypes fantasma (TREATMENT_ADHERENCE, SYMPTOM_TRACKING, etc.), knowledge graph com silent ImportError, flow/templates/manager.py tombstoned.

### R060 — Personalização IA produz reformulações naturais e ancoradas
- Class: differentiator
- Status: active
- Description: A IA reformula perguntas para parecerem naturais e não repetitivas ao longo dos 45+ dias, mantendo grounding no template base. O paciente não percebe que está recebendo variações do mesmo conteúdo.
- Why it matters: Sem reformulação natural, o paciente para de responder depois de alguns dias de mensagens repetitivas.
- Source: user
- Primary owning slice: M007/S04
- Supporting slices: M007/S01
- Validation: mapped
- Notes: O sistema já tem personalização via Gemini com validação de grounding. Precisa review de calibração e qualidade.

### R061 — Respostas livres do paciente são armazenadas e estruturadas
- Class: core-capability
- Status: active
- Description: As respostas em texto livre do paciente via WhatsApp são persistidas com contexto completo (qual dia do fluxo, qual mensagem respondida, timestamp) e estruturadas para consumo pelo resumo IA.
- Why it matters: Sem armazenamento estruturado, o resumo mensal do médico fica sem dados.
- Source: user
- Primary owning slice: M007/S04
- Supporting slices: M007/S01
- Validation: mapped
- Notes: O sistema não é chatbot — o paciente responde livremente, não por menu. As respostas precisam ser linkadas ao contexto do fluxo.

### R062 — Alertas do quiz mensal chegam ao médico de forma acionável
- Class: failure-visibility
- Status: active
- Description: Quando o quiz mensal gera um alerta clínico (dor crítica, febre com calafrios, etc.), o alerta chega ao médico com ação clara — notificação e destaque no dashboard — não fica passivo em Redis.
- Why it matters: Alerta que não chega ao médico é pior que não ter alerta — gera falsa sensação de segurança.
- Source: inferred
- Primary owning slice: M007/S05
- Supporting slices: M007/S04
- Validation: mapped
- Notes: As regras de alerta em `quiz_alert_rules.py` são boas clinicamente. A questão é o caminho até o médico.

### R063 — IA gera resumo mensal detalhado para consulta do médico
- Class: differentiator
- Status: active
- Description: O médico acessa um resumo do mês do paciente gerado por IA — síntese das respostas livres, padrões identificados, preocupações clínicas, e pontos de atenção — e economiza tempo de consulta.
- Why it matters: Este é o core value clínico do sistema: diminuir tempo de consulta e melhorar qualidade do atendimento.
- Source: user
- Primary owning slice: M007/S06
- Supporting slices: M007/S04, M007/S05
- Validation: mapped
- Notes: `PatientSummaryService` existe com Gemini 2.5 Flash. Precisa review de integração, qualidade do prompt, e integração com frontend do médico.

## Validated

### R057 — Sequenciamento de mensagens respeita espera de resposta
- Class: core-capability
- Status: validated
- Description: O sistema envia as mensagens do dia na ordem correta, respeitando `expects_response`: quando uma mensagem espera resposta, a próxima só é enviada depois que o paciente responde. Sem disparo em bulk.
- Why it matters: O bug de disparar tudo de uma vez destrói a experiência do paciente e invalida a lógica de acompanhamento gradual.
- Source: user
- Primary owning slice: M007/S01
- Supporting slices: none
- Validation: validated by 11 focused tests in test_sequencing_expects_response.py proving per-message expects_response across all send modes (sequential_auto, wait_each, remaining_after_response) plus edge cases (idempotency, first-message stop, default single mode), with 0 regressions across 36 total flow tests
- Notes: Bug root cause was _send_all_sequential checking expects_response only on the last message. Fixed to check per-iteration inside the loop. All three send functions now use the same per-message pattern.

### R052 — Código morto e compatibilidades restantes são removidos com prova
- Class: operability
- Status: validated
- Description: O restante do código morto, bridges, aliases, tombstones e compatibilidades sem uso real é removido com evidência e verificação, não por gosto.
- Why it matters: A lapidação final só fecha quando o repositório deixa de carregar resíduo morto como se fosse parte legítima do sistema.
- Source: user
- Primary owning slice: M006/S04
- Supporting slices: M006/S01, M006/S02, M006/S03
- Validation: validated by M006-VERIFY.json — 10 proof phases green: residue guards, focused backend packs, schema convergence under Postgres, absence scans, frontend import-boundary/build, and final-schema proof fresh/existing with mounted backend replay
- Notes: M006 closed the M004→M006 convergence arc: dead backend services/auth cluster removed, Firebase-prefixed users schema dropped, dead frontend bridges/barrels deleted, config/manifests/workflows/docs aligned to canonical runtime.

### R001 — Flow continuation no longer stalls silently on delivery/gate failures
- Class: continuity
- Status: validated
- Description: The WhatsApp flow pipeline recovers from sequential-gate mismatch, outbound send failures, deferred follow-up failures, day advancement issues, and malformed day configs.
- Why it matters: Patients cannot be left silently stuck between consultations.
- Source: execution
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S01 unit coverage and downstream integration coverage.

### R002 — Stalled flows are auto-recovered and operators can intervene
- Class: operability
- Status: validated
- Description: Stuck flows are detected periodically, recovered through bounded logic, and exposed to operators through admin reset/advance/unstick surfaces.
- Why it matters: The system needs both automatic recovery and human intervention paths for real operations.
- Source: execution
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S02 service/task/router tests.

### R003 — Flow health, alerts, and trace signals are operationally visible
- Class: failure-visibility
- Status: validated
- Description: Operators can inspect flow health counts, stall alerts, fallback metrics, and correlation IDs across the flow pipeline.
- Why it matters: Recovery only works operationally if failures and degraded paths are visible.
- Source: execution
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S03 service/router/unit coverage.

### R004 — Flow pipeline and recovery paths are proven by integration tests
- Class: quality-attribute
- Status: validated
- Description: The project has integration coverage for webhook ingress, continuation, stalled-flow recovery, and retry mechanics.
- Why it matters: The milestone promise was only credible if the assembled pipeline was exercised end to end.
- Source: execution
- Primary owning slice: M001/S04
- Supporting slices: none
- Validation: validated
- Notes: Verified by M001/S04 integration suites and milestone summary evidence.

### R005 — First-party staff login replaces Firebase Auth
- Class: primary-user-loop
- Status: validated
- Description: Admins and doctors authenticate with backend-owned email/password login, without Firebase token exchange in the normal login path.
- Why it matters: Reliable login for the clinical team is a prerequisite for the rest of the product.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03, M002/S04
- Validation: validated
- Notes: M002 proved the backend local-login contract in S01, cut the browser happy path over in S03, removed Firebase runtime seams in S04, and replayed `/login` → `/dashboard` locally on a no-Firebase stack.

### R006 — Existing Redis session continuity survives the auth cutover
- Class: continuity
- Status: validated
- Description: The product keeps Redis-backed session validation, HttpOnly cookie behavior, remember-me continuity, and protected-route authentication after the provider switch.
- Why it matters: Replacing the identity provider should not regress the stable session model already used across the backend.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03, M002/S04
- Validation: validated
- Notes: S01 proved backend session issuance/verify/logout/protected-route auth on the first-party identity contract; S03 proved remember-me/session restore/logout in frontend tests; direct browser replay stayed authenticated across reload.

### R007 — Existing users regain access without manual recreation
- Class: launchability
- Status: validated
- Description: Users already present in the system can recover access through a first-access/reset flow instead of having accounts manually recreated.
- Why it matters: A hard cut without a recovery path would create support load and block real users from logging in.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04
- Validation: validated
- Notes: Verified by M002/S02 public/admin recovery suites and `tests/integration/test_password_reset_migration_flow.py`, which covers existing Firebase-era users and admin-created users migrating into local auth.

### R008 — Admin-managed account provisioning remains canonical
- Class: admin/support
- Status: validated
- Description: New staff accounts are created by admins; the system does not add public self-signup during M002.
- Why it matters: The product is an internal clinical system, and admin-mediated onboarding reduces security and support risk.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S03
- Validation: validated
- Notes: M002/S02/T03 kept admin-created first-access and admin-triggered recovery canonical through the shared email-backed reset service while preserving only explicit legacy direct-password compatibility for the pre-cutover admin SPA.

### R009 — Users can recover passwords via email reset link
- Class: continuity
- Status: validated
- Description: A staff user can request a password reset email, receive a time-limited reset token, and set a new password securely.
- Why it matters: Hard-cutting Firebase without self-service recovery would replace one login pain with another.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04
- Validation: validated
- Notes: M002/S02 shipped `POST /api/v2/auth/password/reset-request` and `/reset-confirm` with focused backend proof, and M002/S03 shipped the real routed reset-request/reset-confirm browser UX.

### R010 — Frontend and realtime auth no longer depend on Firebase tokens
- Class: integration
- Status: validated
- Description: Dashboard login/logout/session restore and realtime/WebSocket bootstrap work with first-party session semantics only.
- Why it matters: Removing Firebase only on the backend is insufficient if the browser and realtime path still depend on Firebase SDK state.
- Source: inferred
- Primary owning slice: M002/S03
- Supporting slices: M002/S01, M002/S04
- Validation: validated
- Notes: Verified by the S03 session-first auth and websocket suites, the S04 hard-cut cleanup suite, and no-Firebase browser/network replay with no Firebase-auth requests.

### R011 — Firebase Auth dependency is hard-cut from runtime and compatibility paths
- Class: constraint
- Status: validated
- Description: Staff authentication no longer requires Firebase Auth runtime credentials, SDK calls, or long-lived compatibility mode.
- Why it matters: The user explicitly wants the dependency gone, not just hidden behind another layer.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S03
- Validation: validated
- Notes: M002/S04 removed/tombstoned the shipped staff-auth Firebase seams, `verify-no-firebase-auth.sh` passed, and the local stack booted and authenticated staff users with Firebase env vars blank.

### R012 — Authentication failures become inspectable instead of opaque
- Class: failure-visibility
- Status: validated
- Description: Login, reset, session, and migration failures emit actionable diagnostics and are covered by focused verification so auth regressions stop being mysterious.
- Why it matters: The current pain is not just login failure, but hard-to-debug authentication behavior.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: validated
- Notes: Across M002 the system now emits stable diagnostics for login/session/reset/password/websocket/operational failures (`error`, `message`, `request_id`, websocket auth codes, `session_auth` readiness), with focused pytest/vitest proof across all four slices.

### R035 — Dead-code removal is evidence-based, not taste-based
- Class: failure-visibility
- Status: validated
- Description: Code should only be declared dead and removed when repo evidence, call graph analysis, or focused verification shows it is not part of a live path.
- Why it matters: In a brownfield system, mistaken deletion is worse than untidy code.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S04
- Validation: validated
- Notes: M003/S01 established the evidence map and deletion ledger, and M003/S04 executed the in-scope removals with focused frontend/backend proof, a cleanup manifest, and a green living verifier gate.

### R036 — Obsolete compatibility layers are removed or tightly isolated
- Class: constraint
- Status: validated
- Description: Legacy aliases, shims, and compatibility layers that no longer justify their complexity must either be removed or explicitly isolated away from the main runtime path.
- Why it matters: Compatibility residue keeps the real architecture blurry and makes every future change more dangerous.
- Source: user
- Primary owning slice: M003/S04
- Supporting slices: M003/S02, M003/S03
- Validation: validated
- Notes: M003/S04 deleted the proven-dead frontend alias/type/hook files, kept dead backend auth wrappers off the public surface, and documented `auth_session.py`, `firebase_uid`, and bearer-token fallback as explicit retained compatibility islands instead of ambiguous leftovers.

### R034 — Critical mixed-responsibility hotspots are split into smaller modules
- Class: quality-attribute
- Status: validated
- Description: The milestone must materially reduce the size and responsibility sprawl of the highest-value hotspots instead of leaving the same behavior trapped in giant files.
- Why it matters: Large mixed-responsibility files make safe changes, debugging, and review disproportionately expensive.
- Source: user
- Primary owning slice: M003/S02
- Supporting slices: M003/S03, M003/S04
- Validation: validated
- Notes: M003 closed with the targeted hotspots materially smaller under green proof: `auth_dependencies.py` shrank from 1579 to 675 lines, `src/lib/api-client/index.ts` from 1304 to 223, and `src/lib/api-client/types.ts` from 1159 to 26.

### R037 — Visible contracts remain stable during the cleanup
- Class: continuity
- Status: validated
- Description: The refactor must not unnecessarily change user-visible behavior, critical payload shapes, or the main staff-auth/dashboard/admin/flow entrypoint behavior.
- Why it matters: This work is meant to buy maintainability, not hide regressions behind cleanup language.
- Source: user
- Primary owning slice: M003/S05
- Supporting slices: M003/S02, M003/S03, M003/S04
- Validation: validated
- Notes: Final M003 proof combined focused backend/frontend suites, green direct runtime probes for canonical auth plus legacy `/session/logout`, a green seeded-user Chromium acceptance spec, and green routed smoke for `/dashboard`, `/admin`, and `/whatsapp`.

### R038 — The codebase becomes safer to change in practice
- Class: operability
- Status: validated
- Description: After the milestone, maintainers should be able to reason about and change the targeted areas with less fear because module boundaries and responsibilities are clearer.
- Why it matters: The primary beneficiary is whoever maintains the system next, not just the current cleanup effort.
- Source: user
- Primary owning slice: M003/S05
- Supporting slices: M003/S02, M003/S03, M003/S04
- Validation: validated
- Notes: M003 leaves smaller seams, explicit canonical-vs-legacy ownership boundaries, the S04 cleanup manifest, and `M003-VERIFY.json` as replayable maintenance guidance.

### R039 — Structural cleanup leaves strong proof, not just nicer files
- Class: quality-attribute
- Status: validated
- Description: The milestone must leave focused verification and smoke evidence that the refactor preserved critical auth/session, dashboard/admin, and WhatsApp flow behavior.
- Why it matters: Refactors are only worth trusting if the new structure is backed by proof, not aesthetics.
- Source: inferred
- Primary owning slice: M003/S05
- Supporting slices: M003/S01, M003/S02, M003/S03, M003/S04
- Validation: validated
- Notes: Milestone closeout now rests on the green evidence-map gate, focused backend/frontend packs, a seeded-user Chromium acceptance spec, direct assembled-stack probes, and routed `/dashboard` / `/admin` / `/whatsapp` smoke.

### R048 — Auth/sessão converge para um contrato canônico único
- Class: continuity
- Status: validated
- Description: O sistema oficial da equipe autentica, restaura sessão e revoga sessão por um único contrato canônico, sem caminhos duplos ainda aceitos por inércia histórica.
- Why it matters: Caminhos paralelos de auth/sessão tornam qualquer manutenção futura arriscada e difícil de raciocinar.
- Source: inferred
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S03, M004/S04
- Validation: validated
- Notes: Verified by the combined M004/S02–S04 proof: canonical login/verify-session/restore/logout stayed green on the cookie-backed contract, the official frontend already consumed only that contract, and S04 retired `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket `session_id` fallback as accepted runtime transport.

### R049 — A identidade canônica deixa de depender de `firebase_uid` no runtime
- Class: integration
- Status: validated
- Description: O runtime resolve identidade, cache, sessão e superfícies oficiais por `id` / `user_id`, sem precisar de `firebase_uid` no happy path nem como pivô funcional oculto.
- Why it matters: Enquanto `firebase_uid` continuar sendo chave funcional no runtime, o hard cut permanece incompleto.
- Source: inferred
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S04, M004/S05
- Validation: validated
- Notes: Verified by the combined M004/S02+S05 proof: Redis session creation/listing/invalidation, shared auth/cache restore, login-written payloads, websocket-adjacent auth, audit/admin/docs serialization, and adjacent frontend type surfaces all stay on canonical `id` / `user_id` semantics while the green residue guard now lists only passive compatibility/rejection bookkeeping and M005 keeps the schema drop.

### R050 — O frontend oficial usa apenas o contrato canônico sem resíduo funcional de Firebase
- Class: primary-user-loop
- Status: validated
- Description: `/login`, `/dashboard`, `/admin` e superfícies oficiais relacionadas usam apenas o contrato session-first canônico, sem lógica funcional, comentários operacionais ou tipos oficiais ancorados em Firebase.
- Why it matters: Não basta o backend estar cortado se o app oficial ainda age como se Firebase estivesse vivo.
- Source: inferred
- Primary owning slice: M004/S03
- Supporting slices: M004/S01, M004/S04, M004/S05, M004/S06
- Validation: validated
- Notes: Verified by M004/S03’s focused frontend proof packs, green routed `/login` → `/admin/*` coverage, green websocket diagnostic proof, green build, and a green residue guard showing zero approved frontend auth/session/Firebase residue.

### R047 — Firebase sai de vez do runtime oficial
- Class: constraint
- Status: validated
- Description: O runtime oficial do sistema deixa de depender de Firebase para autenticação, sessão, identidade da equipe ou narrativa operacional do caminho feliz.
- Why it matters: Enquanto Firebase ainda estiver vivo no runtime oficial, a base continua com transição aberta e comportamento ambíguo.
- Source: user
- Primary owning slice: M004/S05
- Supporting slices: M004/S01, M004/S02, M004/S03, M004/S04, M004/S06
- Validation: validated
- Notes: S05 fechou a dependência funcional adjacente de Firebase no runtime por prova de contrato e S06 revalidou o estado montado sem Firebase Auth.

### R051 — Schema e migrações refletem o modelo final, não o legado de transição
- Class: quality-attribute
- Status: validated
- Description: O schema ativo, os modelos e o grafo Alembic deixam de carregar resíduo estrutural de Firebase/legado como parte necessária do sistema atual.
- Why it matters: Sem fechar o banco e as migrações, a convergência fica incompleta e frágil para novos ambientes ou upgrades.
- Source: user
- Primary owning slice: M005/S03
- Supporting slices: M005/S01, M005/S02
- Validation: validated by M005/S03 clean+existing head convergence proof and canonical runtime contract suites
- Notes: S01 tornou o controle plane do Alembic operável só com configuração de banco; S02 publicou a fronteira histórica explícita para `firebase_sync_history`, `audit_logs.firebase_uid` e payloads canônicos; S03 provou em Postgres real que `base -> head` e `m005_s02_t01_publish_firebase_history_boundary -> head` convergem para o mesmo head `m005_s03_t02_align_audit_history_head`, com `users`, `audit_logs` e `firebase_sync_history` alinhados ao contrato canônico vivo sem reviver resíduo Firebase estrutural. Milestone closeout consolidado em `.gsd/milestones/M005/M005-SUMMARY.md`.

### R053 — A convergência final fecha com prova integrada, não só com cleanup estático
- Class: quality-attribute
- Status: validated
- Description: O encerramento da frente M004–M006 precisa provar o sistema montado em estado final, em vez de depender apenas de grep, manifests e diffs de código.
- Why it matters: Cleanup sem prova integrada deixa dúvida sobre o que realmente continua funcionando.
- Source: inferred
- Primary owning slice: M005/S04
- Supporting slices: M004/S06, M005/S01, M005/S03
- Validation: validated by M004/S06 mounted runtime proof plus M005/S04 final-schema fresh/existing backend replay on the canonical head
- Notes: M004/S06 validou o stack montado sem Firebase no runtime oficial; M005/S01 acrescentou a prova de operabilidade/replay do controle plane de migrations em Postgres real; M005/S03 acrescentou a prova de convergência estrutural do head canônico em Postgres real; M005/S04 fechou a lacuna operacional ao reexecutar o backend real e os loops críticos pós-M004 nesse head consolidado para histories `fresh` e `existing`. Milestone closeout consolidado em `.gsd/milestones/M005/M005-SUMMARY.md`.

### R048 — Auth/sessão converge para um contrato canônico único
- Class: continuity
- Status: validated
- Description: O sistema oficial da equipe autentica, restaura sessão e revoga sessão por um único contrato canônico, sem caminhos duplos ainda aceitos por inércia histórica.
- Why it matters: Caminhos paralelos de auth/sessão tornam qualquer manutenção futura arriscada e difícil de raciocinar.
- Source: inferred
- Primary owning slice: M004/S02
- Supporting slices: M004/S01, M004/S03, M004/S04
- Validation: validated
- Notes: Verified by the combined M004/S02–S04 proof: canonical login/verify-session/restore/logout stayed green on the cookie-backed contract, the official frontend already consumed only that contract, and S04 retired `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket `session_id` fallback as accepted runtime transport.

## Deferred

### R064 — Override de template por paciente individual
- Class: admin/support
- Status: deferred
- Description: Possibilidade de ajustar dias específicos do fluxo para um paciente individual, em cima do template global do médico.
- Why it matters: Pode ser útil para personalizar acompanhamento de pacientes com necessidades especiais.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred — o template global por médico cobre o caso principal. Override por paciente adiciona complexidade significativa.

### R020 — Multi-factor authentication for staff access
- Class: compliance/security
- Status: deferred
- Description: Add a second factor for high-privilege staff authentication.
- Why it matters: It may become necessary for stronger operational security later.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred because the immediate priority is removing Firebase Auth cleanly without expanding scope.

### R021 — External SSO / OIDC for clinic organizations
- Class: integration
- Status: deferred
- Description: Allow organizations to authenticate staff through an external identity provider.
- Why it matters: It could matter if the product grows into multi-organization enterprise onboarding.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Explicitly not part of M002.

### R022 — Standardized ADK HTTP error taxonomy
- Class: quality-attribute
- Status: deferred
- Description: Map ADK errors to a stable HTTP envelope with deterministic categories.
- Why it matters: This remains useful future work but is unrelated to the current auth cutover milestone.
- Source: execution
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Carries forward prior deferred project work.

### R023 — Retryable/non-retryable ADK idempotency policy
- Class: operability
- Status: deferred
- Description: Define a project-wide policy for retryable ADK calls and idempotent handling.
- Why it matters: It is important future stabilization work, but not part of the current login cutover.
- Source: execution
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Carries forward prior deferred project work.

### R040 — Repo-wide file-size budgets are enforced in CI
- Class: quality-attribute
- Status: deferred
- Description: Add automated size ceilings or architectural budget checks so new hotspots do not quietly regrow after M003.
- Why it matters: Manual cleanup without a guardrail can decay back into the same problem.
- Source: research
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Useful follow-up, but not required to make the first cleanup milestone shippable.

### R041 — AI/ADK subsystem receives a dedicated deep modularization pass
- Class: integration
- Status: deferred
- Description: Apply the same hotspot-splitting discipline to the AI/ADK runtime and related large modules once the first cleanup wave is complete.
- Why it matters: Those areas are large and risky, but they are not the first attack zone for this milestone.
- Source: discussion
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: The user prioritized backend auth/session first; AI/ADK stays sensitive and deserves its own focused pass later.

### R042 — Frontend-wide export/type unification extends beyond the targeted surfaces
- Class: operability
- Status: deferred
- Description: Finish broad export-surface and duplicate-type cleanup across all frontend domains after the highest-value client/type hotspots are stabilized.
- Why it matters: The frontend has many re-export layers and compatibility aliases, but M003 should focus first on the central client/type seam.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred to avoid turning the current milestone into a repo-wide churn event.

## Out of Scope

### R065 — Interação chatbot com menu/opções para paciente
- Class: anti-feature
- Status: out-of-scope
- Description: O paciente não navega por menus ou opções pré-definidas. Responde livremente com texto.
- Why it matters: A liberdade de resposta é o diferencial — paciente conversa, não opera um menu.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Decisão explícita do usuário. O sistema processa texto livre, não limita opções.

### R066 — Designer visual de fluxo estilo N8N para médicos
- Class: anti-feature
- Status: out-of-scope
- Description: Interface visual com canvas, nós e conexões para o médico montar fluxos. Substituído por editor simples de lista de dias.
- Why it matters: Médico não tem tempo nem interesse em montar workflows visuais. Quer editar texto e tipo de dia.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: O FlowDesigner existente (~3300 linhas) será removido em M007/S02.

### R030 — Public self-signup for staff users
- Class: anti-feature
- Status: out-of-scope
- Description: Staff users do not create their own accounts publicly during M002.
- Why it matters: This prevents scope creep into a very different security and onboarding problem.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Account creation remains admin-managed.

### R031 — CRM-only or dual-identifier login in M002
- Class: constraint
- Status: out-of-scope
- Description: M002 does not support CRM-only login or dual email+CRM login.
- Why it matters: Standardizing on email keeps the cutover smaller and more supportable.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The user explicitly chose email-only login.

### R032 — Long-lived Firebase/local hybrid auth mode
- Class: anti-feature
- Status: out-of-scope
- Description: The milestone does not preserve a prolonged dual-auth runtime mode after cutover.
- Why it matters: The user’s stated goal is to remove the dependency, not carry it indefinitely.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Short implementation scaffolding during execution is acceptable; the shipped state must be hard cut.

### R033 — Patient/quiz authentication redesign as part of M002
- Class: constraint
- Status: out-of-scope
- Description: M002 does not redesign the public patient/quiz auth flows beyond any incidental compatibility impact.
- Why it matters: The immediate pain and asked-for scope are staff authentication, not patient-facing access.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Quiz session flows remain separate unless a concrete dependency emerges during implementation.

### R043 — New product capabilities are added during the cleanup milestone
- Class: anti-feature
- Status: out-of-scope
- Description: M003 does not expand product scope with new features while refactoring the existing system.
- Why it matters: Feature work would blur whether the milestone actually paid down structural risk.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The milestone is about maintainability and safe cleanup, not new end-user functionality.

### R044 — Public API contracts are redesigned without necessity
- Class: constraint
- Status: out-of-scope
- Description: M003 does not intentionally redesign stable visible contracts unless a change is required to remove proven dead or obsolete structure.
- Why it matters: The user explicitly does not want the refactor to cross into unnecessary behavior or payload drift.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Contract continuity is a core guardrail for the milestone.

### R045 — Full architecture rewrite or replatform
- Class: anti-feature
- Status: out-of-scope
- Description: M003 does not attempt to replace the project architecture wholesale or replatform major subsystems under the banner of cleanup.
- Why it matters: A rewrite would destroy the milestone’s constraint of making the current system safer to change.
- Source: discussion
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The user wants aggressive cleanup, not a disguised restart.

### R046 — Broad database schema redesign unrelated to hotspot cleanup
- Class: constraint
- Status: out-of-scope
- Description: M003 does not broaden into schema redesign work except for incidental adjustments directly required by in-scope cleanup.
- Why it matters: Schema churn would expand the blast radius far beyond the stated maintainability target.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Redis/Postgres session behavior is sensitive and should be preserved, not redesigned, during this milestone.

### R054 — Novas features de produto durante a convergência final
- Class: anti-feature
- Status: out-of-scope
- Description: A frente M004–M006 não existe para expandir produto; ela existe para convergir runtime, schema e legado restante.
- Why it matters: Adicionar feature nova misturaria lapidação estrutural com expansão de escopo e tornaria a prova final menos honesta.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Melhorias funcionais novas entram em milestone própria depois da convergência.

### R055 — Preservar um modo híbrido duradouro com compatibilidade Firebase por segurança
- Class: anti-feature
- Status: out-of-scope
- Description: A nova frente não vai manter Firebase vivo em paralelo ao runtime oficial apenas por precaução.
- Why it matters: Isso contradiz diretamente a decisão do usuário de não utilizar mais Firebase no sistema.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Compatibilidades só sobrevivem se forem pontes explicitamente justificadas e com prazo claro de remoção.

### R056 — Reescrita ampla ou replatform sob o pretexto de lapidação
- Class: anti-feature
- Status: out-of-scope
- Description: M004–M006 não são licença para recomeçar a arquitetura do zero ou trocar a base tecnológica em bloco.
- Why it matters: O objetivo é convergir a base atual com segurança e prova, não esconder uma reescrita dentro de cleanup.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Mudanças amplas só entram se uma pesquisa futura provar necessidade real e escopo separado.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R057 | core-capability | validated | M007/S01 | none | validated by 11 tests + 0 regressions |
| R058 | primary-user-loop | active | M007/S03 | M007/S01, M007/S02 | mapped |
| R059 | operability | active | M007/S02 | none | mapped |
| R060 | differentiator | active | M007/S04 | M007/S01 | mapped |
| R061 | core-capability | active | M007/S04 | M007/S01 | mapped |
| R062 | failure-visibility | active | M007/S05 | M007/S04 | mapped |
| R063 | differentiator | active | M007/S06 | M007/S04, M007/S05 | mapped |
| R064 | admin/support | deferred | none | none | unmapped |
| R065 | anti-feature | out-of-scope | none | none | n/a |
| R066 | anti-feature | out-of-scope | none | none | n/a |
| R047 | constraint | validated | M004/S05 | M004/S01, M004/S02, M004/S03, M004/S04, M004/S06 | validated |
| R048 | continuity | validated | M004/S02 | M004/S01, M004/S03, M004/S04 | validated |
| R049 | integration | validated | M004/S02 | M004/S01, M004/S04, M004/S05 | validated |
| R050 | primary-user-loop | validated | M004/S03 | M004/S01, M004/S04, M004/S05, M004/S06 | validated |
| R051 | quality-attribute | validated | M005/S03 | M005/S01, M005/S02 | validated |
| R052 | operability | validated | M006/S04 | M006/S01, M006/S02, M006/S03 | validated by M006-VERIFY.json |
| R053 | quality-attribute | validated | M005/S04 | M004/S06, M005/S01, M005/S03 | validated by M004/S06 mounted runtime proof plus M005/S04 final-schema backend replay |
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
| R054 | anti-feature | out-of-scope | none | none | n/a |
| R055 | anti-feature | out-of-scope | none | none | n/a |
| R056 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 6
- Mapped to slices: 6
- Validated: 27
- Unmapped active requirements: 0
