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

### R005 — First-party staff login replaces Firebase Auth
- Class: primary-user-loop
- Status: active
- Description: Admins and doctors authenticate with backend-owned email/password login, without Firebase token exchange in the normal login path.
- Why it matters: Reliable login for the clinical team is a prerequisite for the rest of the product.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03, M002/S04
- Validation: mapped
- Notes: User explicitly requested removal of Firebase Auth; login identifier is email only.

### R006 — Existing Redis session continuity survives the auth cutover
- Class: continuity
- Status: active
- Description: The product keeps Redis-backed session validation, HttpOnly cookie behavior, remember-me continuity, and protected-route authentication after the provider switch.
- Why it matters: Replacing the identity provider should not regress the stable session model already used across the backend.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S03, M002/S04
- Validation: mapped
- Notes: The user chose to keep the current session/cookie architecture instead of moving to a pure JWT model.

### R007 — Existing users regain access without manual recreation
- Class: launchability
- Status: active
- Description: Users already present in the system can recover access through a first-access/reset flow instead of having accounts manually recreated.
- Why it matters: A hard cut without a recovery path would create support load and block real users from logging in.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04
- Validation: mapped
- Notes: The chosen migration path is reset obrigatório / first access, not manual recreation.

### R008 — Admin-managed account provisioning remains canonical
- Class: admin/support
- Status: active
- Description: New staff accounts are created by admins; the system does not add public self-signup during M002.
- Why it matters: The product is an internal clinical system, and admin-mediated onboarding reduces security and support risk.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S03
- Validation: mapped
- Notes: The user explicitly selected admin-created accounts.

### R009 — Users can recover passwords via email reset link
- Class: continuity
- Status: active
- Description: A staff user can request a password reset email, receive a time-limited reset token, and set a new password securely.
- Why it matters: Hard-cutting Firebase without self-service recovery would replace one login pain with another.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04
- Validation: mapped
- Notes: Chosen recovery mode is email reset link, not admin-only reset.

### R010 — Frontend and realtime auth no longer depend on Firebase tokens
- Class: integration
- Status: active
- Description: Dashboard login/logout/session restore and realtime/WebSocket bootstrap work with first-party session semantics only.
- Why it matters: Removing Firebase only on the backend is insufficient if the browser and realtime path still depend on Firebase SDK state.
- Source: inferred
- Primary owning slice: M002/S03
- Supporting slices: M002/S01, M002/S04
- Validation: mapped
- Notes: Current frontend auth path still uses `firebase-auth.ts`, `firebase-lazy.ts`, and Firebase token-based websocket bootstrap.

### R011 — Firebase Auth dependency is hard-cut from runtime and compatibility paths
- Class: constraint
- Status: active
- Description: Staff authentication no longer requires Firebase Auth runtime credentials, SDK calls, or long-lived compatibility mode.
- Why it matters: The user explicitly wants the dependency gone, not just hidden behind another layer.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S03
- Validation: mapped
- Notes: The chosen rollout mode is hard cut, not temporary coexistence.

### R012 — Authentication failures become inspectable instead of opaque
- Class: failure-visibility
- Status: active
- Description: Login, reset, session, and migration failures emit actionable diagnostics and are covered by focused verification so auth regressions stop being mysterious.
- Why it matters: The current pain is not just login failure, but hard-to-debug authentication behavior.
- Source: inferred
- Primary owning slice: M002/S04
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: mapped
- Notes: Existing code already has audit/security patterns that M002 should preserve rather than regress.

## Validated

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

## Deferred

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

## Out of Scope

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

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | continuity | validated | M001/S01 | none | validated |
| R002 | operability | validated | M001/S02 | none | validated |
| R003 | failure-visibility | validated | M001/S03 | none | validated |
| R004 | quality-attribute | validated | M001/S04 | none | validated |
| R005 | primary-user-loop | active | M002/S01 | M002/S03, M002/S04 | mapped |
| R006 | continuity | active | M002/S01 | M002/S03, M002/S04 | mapped |
| R007 | launchability | active | M002/S02 | M002/S04 | mapped |
| R008 | admin/support | active | M002/S02 | M002/S03 | mapped |
| R009 | continuity | active | M002/S02 | M002/S04 | mapped |
| R010 | integration | active | M002/S03 | M002/S01, M002/S04 | mapped |
| R011 | constraint | active | M002/S04 | M002/S01, M002/S03 | mapped |
| R012 | failure-visibility | active | M002/S04 | M002/S01, M002/S02, M002/S03 | mapped |
| R020 | compliance/security | deferred | none | none | unmapped |
| R021 | integration | deferred | none | none | unmapped |
| R022 | quality-attribute | deferred | none | none | unmapped |
| R023 | operability | deferred | none | none | unmapped |
| R030 | anti-feature | out-of-scope | none | none | n/a |
| R031 | constraint | out-of-scope | none | none | n/a |
| R032 | anti-feature | out-of-scope | none | none | n/a |
| R033 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 8
- Mapped to slices: 8
- Validated: 4
- Unmapped active requirements: 0
