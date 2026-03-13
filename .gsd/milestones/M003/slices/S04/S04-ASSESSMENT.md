---
date: 2026-03-13
triggering_slice: M003/S04
verdict: no-change
---

# Reassessment: M003/S04

## Coverage Check

- Os hotspots centrais escolhidos para o milestone ficam materialmente menores e com responsabilidades mais nítidas do que no estado atual. → S05
- Existe evidência explícita para o que foi removido como dead code ou compatibilidade obsoleta; nada importante é apagado “no feeling”. → S05
- Auth/sessão, dashboard/admin e os caminhos críticos afetados continuam funcionando no mesmo contrato visível após a limpeza. → S05
- O milestone fecha com provas focadas e smoke checks suficientes para confiar que a melhora estrutural não custou regressão operacional. → S05

Coverage check passed.

## Changes Made

No changes.

S04 appears to have retired the risk it was supposed to retire:
- the strongest proven-dead frontend compatibility files were actually deleted and pinned by a negative contract test;
- the already-pruned backend auth dependency surface was locked in with explicit absence checks instead of reviving obsolete wrappers;
- the cleanup boundary is now explicit through `S04-CLEANUP-MANIFEST.md`, the updated evidence-map verifier, and the retained-compatibility ledger.

Nothing in the slice summary shows a new ordering problem or a broken assumption that would justify rewriting the remaining roadmap. The boundary map still matches what was built:
- S04 did produce the cleanup manifest, narrowed compatibility surface, and final regression checklist inputs promised to S05;
- the retained compatibility islands (`auth_session.py`, `firebase_uid`, bearer-token fallback) are documented, bounded, and still appropriate for integrated smoke rather than an unplanned extra cleanup slice;
- S05 is still the correct owner for the final cross-surface proof across backend/frontend auth-session, dashboard/admin continuity, and affected runtime paths.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- `R034` stays materially advanced by S02/S03 and can be rechecked at milestone closeout through S05.
- `R037`, `R038`, and `R039` still have credible ownership in S05 exactly as the roadmap states.
- `R035` and `R036` remain validated by the evidence-first cleanup work already completed through S01 and S04.

No ownership or status change is needed in `.gsd/REQUIREMENTS.md`.

## Decision References

- "M003/S04 plans cleanup in three passes: delete the strongest frontend dead files first, prune dead backend auth exports second, then publish a manifest that distinguishes removed residue from retained compat islands."
- "M003/S04 keeps `backend-hormonia/app/routers/auth_session.py`, `firebase_uid` fallbacks, and bearer-token auth fallback out of deletion scope; this slice isolates them through documentation/proof instead of broadening into live compat-route removal."
- "M003/S04/T02 does not restore removed backend auth wrappers for test compatibility; split-contract and websocket tests must assert export absence and explicit rejection of legacy `firebase`/`auto` websocket auth modes instead of reviving shims."
- "M003/S04/T03 treats the S01 evidence-map verifier as a living gate: when tracked cleanup candidates are intentionally deleted, the verifier and anchored metrics must be updated to reflect the post-cleanup repo rather than failing on stale bookkeeping."
