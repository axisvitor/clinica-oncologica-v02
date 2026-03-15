---
estimated_steps: 4
estimated_files: 10
---

# T02: Republish canonical user/profile/admin/physician surfaces and fixtures

**Slice:** S02 — Remover o resíduo de schema que ainda prende o runtime ao passado
**Milestone:** M006

## Description

Once T01 removes the live auth/session fallback, the remaining risk shifts to helper defaults, route serializers, and fixtures that still read or repopulate the Firebase-era `users` columns. This task republishes those runtime and harness surfaces onto the canonical fields that survive the cut.

## Steps

1. Flip the `User` helper contract to canonical-only for the fields that stay on `users`, so normal writes stop mirroring back into `firebase_*` columns or `firebase_custom_claims`.
2. Replace direct `firebase_*` reads/writes in physician, admin, and analytics-adjacent runtime helpers with canonical getters/fields, choosing the canonical activity signal used for user metrics.
3. Republish shared fixtures and auth/session test payload builders so seeded users carry canonical `last_login`, `display_name`, `photo_url`, and preferences data instead of relying on Firebase-era mirrors.
4. Extend the focused API proof for canonical profile mutation, physician search/detail, and admin user/stats responses.

## Must-Haves

- [ ] No live serializer, search, update, or metric surface in this task still reads or writes the `users.firebase_*` columns slated for removal.
- [ ] Shared fixtures and focused API tests describe canonical `last_login` / profile data only.

## Verification

- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`

## Observability Impact

- Signals added/changed: focused API assertions should call out canonical field drift (`last_login`, `display_name`, `photo_url`, `active_users`) rather than legacy mirror behavior.
- How a future agent inspects this: run the focused API pack and compare seeded canonical fixture values with the serialized admin/user/physician responses.
- Failure state exposed: physician search/detail drift, admin user serialization drift, and user-metrics regressions fail as targeted assertions instead of surfacing first as migration-time missing-column errors.

## Inputs

- `backend-hormonia/app/models/user.py` — still mirrors canonical writes into Firebase-era columns/claims by default.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — still searches `firebase_display_name` and writes compatibility claims.
- `backend-hormonia/tests/api/v2/conftest.py` — shared API fixtures still seed `last_login` from Firebase-era fields.
- `backend-hormonia/app/services/analytics/admin_stats_service.py` — still carries a direct `firebase_last_sign_in` reader that needs either republication or explicit retirement.

## Expected Output

- `backend-hormonia/app/models/user.py` — canonical-only helper defaults for the fields that survive the S02 cut.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — physician search/detail/update behavior that stays on canonical storage.
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` — focused proof that canonical profile/admin/physician payloads stay green without Firebase-era mirrors.
- `backend-hormonia/tests/unit/services/test_admin_stats_service.py` — targeted proof for whichever canonical user-activity signal survives the cut.
