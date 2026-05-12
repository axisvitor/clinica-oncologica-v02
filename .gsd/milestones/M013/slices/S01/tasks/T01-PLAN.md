---
estimated_steps: 36
estimated_files: 2
skills_used: []
---

# T01: Require admin sessions for WhatsApp management routes

Executor metadata:
- estimated_steps: 8
- estimated_files: 2
- skills_used: api-design, security-review, tdd, verify-before-complete

Why: closes R001 by making the existing `/api/v2/whatsapp` management surface fail closed before WhatsApp service, WuzAPI client or queue side effects run.

Files:
- `backend-hormonia/app/integrations/whatsapp/api/routes.py`
- `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`

Do:
1. Add a focused test module for the management auth contract. Use the existing `client` fixture from `backend-hormonia/tests/conftest.py` and dependency overrides on `app.main.app`.
2. In the anonymous test, override `app.integrations.whatsapp.api.routes.get_message_service` with a spy/failing dependency and monkeypatch `app.integrations.whatsapp.api.routes.MessageQueue` with a failing/recording class so service/queue construction would be visible if auth ordering is wrong.
3. Exercise representative management operations without auth: `POST /api/v2/whatsapp/messages`, `GET /api/v2/whatsapp/messages?instance=primary`, `GET /api/v2/whatsapp/messages/stats?instance=primary`, `GET /api/v2/whatsapp/messages/primary/statistics`, `GET /api/v2/whatsapp/messages/primary/history/chat-1`, `POST /api/v2/whatsapp/contacts/primary/sync`, `GET /api/v2/whatsapp/contacts/primary`, `GET /api/v2/whatsapp/queue/stats`, `POST /api/v2/whatsapp/queue/process`, and `GET /api/v2/whatsapp/instances`; assert each is 401/403 and spies were not called.
4. Add an explicit public-health test for `GET /api/v2/whatsapp/health` returning 200.
5. Add an authorized admin test by overriding `get_current_active_admin` or `get_current_user_from_session` with an admin-shaped session mapping and overriding `get_message_service` with a fake service whose `send_message` returns a valid `MessageResponse`-shaped object/dict.
6. Refactor `routes.py` to use the existing `get_current_active_admin` dependency from `app.dependencies.auth_dependencies`; do not invent API-key or service-principal auth in this slice.
7. Prefer a split-router shape: keep `router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])` for public health, create a management sub-router with `dependencies=[Depends(get_current_active_admin)]`, move all management decorators to it, and include it into `router` after endpoint definitions.
8. Ensure auth dependency ordering blocks `get_message_service`, direct `MessageQueue`, and database-backed handlers for anonymous callers before handler bodies execute.

Failure Modes (Q5):

| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|------------------------|
| Session/admin dependency | Return 401/403 and do not construct WhatsApp services | Let canonical auth timeout/failure propagate as a closed request; do not execute handler body | Treat as unauthenticated/unauthorized; do not execute handler body |
| Fake/real WhatsApp service | For authenticated requests only, return existing endpoint error behavior | For authenticated requests only, preserve existing endpoint error behavior | For authenticated requests only, preserve response-model validation |

Load Profile (Q6):

- **Shared resources**: auth session cache/DB fallback only for rejected anonymous calls; WuzAPI, Redis queue and message service resources must not be touched before auth succeeds.
- **Per-operation cost**: one FastAPI auth dependency chain before management handler dependencies.
- **10x breakpoint**: auth backend/cache pressure, not WhatsApp/WuzAPI side effects; this task must not add per-route duplicate service construction.

Negative Tests (Q7):

- **Malformed inputs**: send-message body can be valid while auth is missing; auth must reject before request reaches fake service.
- **Error paths**: missing session/header and non-admin session return 401/403.
- **Boundary conditions**: health remains the only public route; queue stats and instance listing are not accidentally left public because they do not use `get_message_service`.

Must-haves:
- [ ] Anonymous management calls return 401/403 before service/queue construction.
- [ ] Admin session reaches a mocked send operation successfully.
- [ ] `/api/v2/whatsapp/health` remains public.
- [ ] Uses canonical auth dependencies; no new auth scheme.

Done when: the focused WhatsApp auth test file passes and demonstrates both negative and positive management behavior.

## Inputs

- `backend-hormonia/app/integrations/whatsapp/api/routes.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_role_dependencies.py`
- `backend-hormonia/tests/conftest.py`
- `backend-hormonia/tests/utils/async_test_client.py`

## Expected Output

- `backend-hormonia/app/integrations/whatsapp/api/routes.py`
- `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q

## Observability Impact

Auth failures should remain generic 401/403 without PHI. The test spies create a durable diagnostic proof that unauthorized calls do not initialize WuzAPI/queue/service resources.
