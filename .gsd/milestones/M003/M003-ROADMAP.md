# M003: Structural Refactor And Dead-Code Cleanup

**Vision:** Refatorar os hotspots mais pesados do backend e frontend, eliminar código morto comprovadamente morto e reduzir compatibilidades obsoletas, deixando a base mais segura de manter sem introduzir regressão funcional desnecessária.

## Success Criteria

- Os hotspots centrais escolhidos para o milestone ficam materialmente menores e com responsabilidades mais nítidas do que no estado atual.
- Existe evidência explícita para o que foi removido como dead code ou compatibilidade obsoleta; nada importante é apagado “no feeling”.
- Auth/sessão, dashboard/admin e os caminhos críticos afetados continuam funcionando no mesmo contrato visível após a limpeza.
- O milestone fecha com provas focadas e smoke checks suficientes para confiar que a melhora estrutural não custou regressão operacional.

## Key Risks / Unknowns

- Código aparentemente morto ainda ter chamadores reais — isso quebraria runtime ou testes sob o pretexto de cleanup.
- O hotspot de backend auth/session é central e sensível — uma divisão ruim pode regredir login, restore, websocket ou superfícies admin.
- O hotspot de frontend api-client/type surface espalha efeitos para muitas telas — limpar sem critério pode gerar churn grande e pouco ganho.
- O repo já contém shims, tombstones e camadas de compatibilidade por decisão histórica — nem todo resíduo é descartável imediatamente.

## Proof Strategy

- dead code vs. ugly code ambiguity → retire in S01 by proving a ranked inventory, deletion candidates, and guardrails tied to real verification commands.
- backend auth/session hotspot risk → retire in S02 by proving the main auth/session seam was split while focused backend auth/session verification stays green.
- frontend api-client/type hotspot risk → retire in S03 by proving the client/type seam was split while focused frontend auth/session/client verification stays green.
- accidental regression from cleanup/removal → retire in S04 by proving in-scope dead/obsolete layers were removed or isolated with evidence and no critical contract drift.
- cross-runtime drift after refactor → retire in S05 by proving the assembled backend/frontend/auth/dashboard/admin/flow smoke remains intact in the affected surfaces.

## Verification Classes

- Contract verification: static hotspot inventories, import/export checks, dead-code evidence scans, and focused pytest/vitest suites for the targeted seams.
- Integration verification: backend/frontend auth-session flows, dashboard/admin smoke, and affected flow/WhatsApp surfaces where touched by the cleanup.
- Operational verification: backend/frontend boot and critical runtime imports still succeed after refactor, with no new initialization or route-wiring breakage in the touched paths.
- UAT / human verification: quick human spot-check that the resulting seams are actually clearer and the milestone did not preserve obviously dead compatibility sludge in the main path.

## Milestone Definition of Done

This milestone is complete only when all are true:

- All slice deliverables are complete.
- The chosen backend and frontend hotspots are materially smaller and clearer than their starting state.
- Dead-code and obsolete-compatibility removals in scope are backed by evidence and documented rationale.
- Shared components are actually wired together under the same visible contracts as before unless a change was explicitly required.
- Success criteria are re-checked against focused verification plus final cross-surface smoke, not just static artifacts.
- Final integrated acceptance scenarios pass.

## Requirement Coverage

- Covers: R034, R035, R036, R037, R038, R039
- Partially covers: none
- Leaves for later: R040, R041, R042, R043, R044, R045, R046
- Orphan risks: none

## Slices

- [ ] **S01: Evidence Map And Cleanup Guardrails** `risk:high` `depends:[]`
  > After this: there is a ranked hotspot inventory, a dead-code candidate ledger, and explicit guardrails for what must not break.
- [ ] **S02: Backend Auth/Session Hotspot Refactor** `risk:high` `depends:[S01]`
  > After this: the backend auth/session hotspot is split into smaller seams with the same visible contract, proved by focused backend verification.
- [ ] **S03: Frontend Client/Type Surface Refactor** `risk:high` `depends:[S01]`
  > After this: the frontend api-client/type hotspot is broken into clearer seams with less compatibility noise and the same visible behavior, proved by focused frontend verification.
- [ ] **S04: Dead-Code And Obsolete-Compatibility Cleanup** `risk:medium` `depends:[S02,S03]`
  > After this: proven-dead paths and obsolete compat layers in scope are removed or tightly isolated from the main runtime path.
- [ ] **S05: Integrated Proof And Structural Closeout** `risk:medium` `depends:[S02,S03,S04]`
  > After this: focused verification and critical smoke checks prove the structural cleanup held across the real affected backend/frontend surfaces.

## Boundary Map

### S01 → S02

Produces:
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — ranked backend/frontend hotspot inventory with target files, rationale, and recommended attack order.
- cleanup guardrail matrix — critical contracts that must stay stable for auth/session, dashboard/admin, and touched flow/WhatsApp seams.
- deletion candidate ledger — explicit dead-code/compatibility suspects plus the proof required before removal.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- frontend target shortlist — canonical client/type entrypoints to preserve while refactoring.
- repo-wide cleanup guardrails — rules for contract stability, evidence-before-deletion, and acceptable blast radius.

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- backend auth/session seam map — stable exports and responsibilities for `get_current_user_from_session`, `get_current_user`, `get_admin_user`, `get_current_user_websocket`, and related helpers after refactor.
- reduced `backend-hormonia/app/dependencies/auth_dependencies.py` footprint or equivalent package split with preserved import surface where required.
- focused backend regression command(s) for the refactored auth/session seam.

Consumes from S01:
- hotspot ranking and auth/session guardrails.
- deletion candidate ledger for backend auth/session residue.

### S03 → S04

Produces:
- frontend `apiClient` seam map — stable exported `apiClient` surface with smaller internal modules or builders.
- clarified type entrypoint map — canonical vs compatibility exports for the touched frontend type surface.
- focused frontend regression command(s) for auth/session/client/type behavior after refactor.

Consumes from S01:
- hotspot ranking and frontend client/type guardrails.
- deletion candidate ledger for frontend compatibility residue.

### S02 → S05

Produces:
- stable backend auth/session contract after refactor.
- changed-file verification list for final smoke across backend-sensitive surfaces.

Consumes from S01:
- guardrail matrix and proof expectations.

### S03 → S05

Produces:
- stable frontend client/type contract after refactor.
- changed-file verification list for final smoke across frontend-sensitive surfaces.

Consumes from S01:
- guardrail matrix and proof expectations.

### S04 → S05

Produces:
- dead-code cleanup manifest — what was removed, what was isolated, and what proof justified each choice.
- narrowed compatibility surface — explicit list of what remains and why.
- final regression checklist tying the cleanup back to critical user/runtime paths.

Consumes from S02:
- backend seam map and focused backend verification.

Consumes from S03:
- frontend seam map and focused frontend verification.
