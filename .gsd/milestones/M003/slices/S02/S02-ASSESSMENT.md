---
date: 2026-03-12
triggering_slice: M003/S02
verdict: no-change
---

# Reassessment: M003/S02

## Changes Made

No changes.

S02 retired the backend auth/session hotspot risk it owned: the stable `app.dependencies.auth_dependencies` façade now delegates into `auth_session_contract.py`, `auth_session_cache.py`, `auth_user_adapter.py`, `auth_role_dependencies.py`, and `auth_legacy_firebase.py`; `auth_dependencies.py` is down to 706 lines; and the focused backend auth/session/websocket/login proof packs passed. The remaining slices still own the remaining work: frontend hotspot split (S03), evidence-based dead/obsolete-compat cleanup (S04), and integrated cross-surface proof (S05).

The existing boundary map still holds. S04/S05 can consume the shipped S02 seam outputs from the split auth modules, stable façade/override surface, and focused backend regression commands. S02’s slice summary/UAT are still placeholders, so the task summaries are the authoritative handoff until those artifacts are repaired; that artifact gap does not justify roadmap changes.

## Requirement Coverage Impact

None.

No requirement ownership or status changed. Requirement coverage remains sound: S02 materially advances R034 and supports R037/R039, while the remaining active requirements are still credibly owned by S03-S05.

- R034 → S03, S04, S05
- R035 → S04, S05
- R036 → S04, S05
- R037 → S03, S04, S05
- R038 → S03, S04, S05
- R039 → S03, S04, S05

## Decision References

Existing M003/S02 decisions that informed this reassessment:

- Keep `app.dependencies.auth_dependencies` as the stable public dependency/override surface while splitting internals into `auth_session_contract.py`, `auth_session_cache.py`, `auth_user_adapter.py`, `auth_role_dependencies.py`, and `auth_legacy_firebase.py`.
- Preserve the current HTTP session precedence contract (`ENABLE_COOKIE_PRIORITY` stays authoritative).
- Make canonical `id` / `user_id` session identities authoritative for admin wrapper lookups, with `firebase_uid` retained only as explicit fallback.
- Isolate Firebase verification, bearer-token auth, and websocket compatibility inside `auth_legacy_firebase.py`.

No new decision was required by the reassessment.

## Success-Criterion Coverage Check

- Os hotspots centrais escolhidos para o milestone ficam materialmente menores e com responsabilidades mais nítidas do que no estado atual. → S03, S05
- Existe evidência explícita para o que foi removido como dead code ou compatibilidade obsoleta; nada importante é apagado “no feeling”. → S04, S05
- Auth/sessão, dashboard/admin e os caminhos críticos afetados continuam funcionando no mesmo contrato visível após a limpeza. → S03, S04, S05
- O milestone fecha com provas focadas e smoke checks suficientes para confiar que a melhora estrutural não custou regressão operacional. → S03, S04, S05
