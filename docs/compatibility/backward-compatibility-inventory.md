# Backward Compatibility Inventory

## Scope
- In scope: active compatibility layers that keep backend, frontend dashboard, and quiz interface working across old and new contracts.
- Out of scope: internal refactors with no external contract impact.
- Review cadence: once per release wave, and before any breaking change PR.

## Owners
| Owner | Responsibility |
|---|---|
| Backend API Team | API routes, auth/session compatibility, deprecation headers, quiz public APIs |
| Frontend Dashboard Team | Response/type adapters, legacy UI auth guards, websocket protocol adapters |
| Quiz Interface Team | Quiz public endpoint consumption, session recovery, CSRF/session handshake compatibility |
| Platform/Observability | Compatibility metrics dashboards and sunset readiness checks |

## Deprecation Policy
| layer | location | compatibility contract | owner | consumer | sunset trigger | target removal wave/date placeholder | metric to monitor |
|---|---|---|---|---|---|---|---|
| Backend API versioning | `backend-hormonia/app/api/versioning.py` | Deprecated versions must emit `Deprecation`/`Sunset` headers and return `410` after sunset. | Backend API Team | Frontend dashboard, quiz interface, external API clients | Replacement version GA + deprecated version traffic below agreed threshold for 30 days | Wave-Compat-1 (YYYY-MM-DD) | `api_version_usage_total`, `api_deprecated_endpoint_calls_total`, `api_version_sunset_days_remaining` |
| Backend deprecated endpoint tracking | `backend-hormonia/app/monitoring/deprecation_tracking.py` | Deprecated endpoints must be registered and usage tracked before removal approval. | Backend API Team | API maintainers, Platform/Observability | No active clients in deprecation report for 2 release cycles | Wave-Compat-1 (YYYY-MM-DD) | `deprecated_endpoints_active`, deprecation report client list |
| Auth mode transition | `backend-hormonia/app/dependencies/auth_dependencies.py` | Session auth is primary; Firebase bearer-token auth remains compatibility-only until consumers migrate. | Backend API Team | Legacy API consumers using `Authorization: Bearer` | Bearer-path usage below threshold and migration complete | Wave-Compat-2 (YYYY-MM-DD) | Auth-source log split (`cookie`/`x-session-id`/`authorization`) |
| Frontend role guard transition | `frontend-hormonia/src/features/auth/ProtectedRoute.tsx` | `requiredRole`/`requiredRoles` stay available until all routes migrate to `requiredPermission`. | Frontend Dashboard Team | Legacy route definitions in dashboard | Zero legacy prop usage in codebase + regression tests green | Wave-Compat-2 (YYYY-MM-DD) | `rg` count for `requiredRole|requiredRoles` in `frontend-hormonia/src` |

## Route Aliases
| layer | location | compatibility contract | owner | consumer | sunset trigger | target removal wave/date placeholder | metric to monitor |
|---|---|---|---|---|---|---|---|
| Backend API alias | `backend-hormonia/app/api/v2/router.py` | Keep `/api/v2/patients` alias for clients that do not send trailing slash (`/api/v2/patients/`). | Backend API Team | Frontend dashboard and scripts using non-slash path | Alias path traffic reaches near-zero | Wave-Compat-2 (YYYY-MM-DD) | Request count by exact path: `/api/v2/patients` vs `/api/v2/patients/` |
| Backend API alias | `backend-hormonia/app/api/v2/router.py` | Keep `/api/v2/physicians` alias for non-trailing-slash clients. | Backend API Team | Dashboard/API consumers | Alias path traffic near-zero | Wave-Compat-2 (YYYY-MM-DD) | Request count by exact path: `/api/v2/physicians` vs `/api/v2/physicians/` |
| Backend API alias | `backend-hormonia/app/api/v2/router.py` | Keep `/api/v2/roles` alias for non-trailing-slash clients. | Backend API Team | Dashboard/API consumers | Alias path traffic near-zero | Wave-Compat-2 (YYYY-MM-DD) | Request count by exact path: `/api/v2/roles` vs `/api/v2/roles/` |
| Backend endpoint alias | `backend-hormonia/app/api/v2/routers/messages.py` | Keep hidden `POST /api/v2/messages/send` alias to canonical `POST /api/v2/messages`. | Backend API Team | Older message clients | Alias endpoint unused for 2 release cycles | Wave-Compat-2 (YYYY-MM-DD) | Request count on `/api/v2/messages/send` |
| Backend endpoint alias | `backend-hormonia/app/api/v2/routers/flows.py` | Keep hidden `GET /api/v2/flows/` alias to canonical `GET /api/v2/flows`. | Backend API Team | Older flow-list clients | Alias endpoint unused for 2 release cycles | Wave-Compat-2 (YYYY-MM-DD) | Request count on `/api/v2/flows/` |
| Backend router alias | `backend-hormonia/app/api/v2/router.py` | Keep `/api/v2/auth/notifications` mounted as legacy path for notifications. | Backend API Team | Older auth-notification clients | Legacy path traffic near-zero | Wave-Compat-3 (YYYY-MM-DD) | Request count on `/api/v2/auth/notifications*` |

## Payload/Field Adapters
| layer | location | compatibility contract | owner | consumer | sunset trigger | target removal wave/date placeholder | metric to monitor |
|---|---|---|---|---|---|---|---|
| Frontend user adapter | `frontend-hormonia/src/lib/api-client/normalizers.ts` | Accept both `full_name` and `name`; emit stable frontend user shape. | Frontend Dashboard Team | Dashboard pages/hooks expecting either key | No backend/user responses with legacy key patterns | Wave-Compat-2 (YYYY-MM-DD) | Contract test pass rate for user payload shape |
| Frontend patient adapter | `frontend-hormonia/src/lib/api-client/normalizers.ts` | Map `flow_state`/`status` bidirectionally to keep old and new patient consumers stable. | Frontend Dashboard Team | Dashboard patient flows/components | All consumers migrated to one canonical field model | Wave-Compat-2 (YYYY-MM-DD) | Contract tests for patient normalization/denormalization |
| Frontend pagination adapter | `frontend-hormonia/src/lib/api-client/patients.ts`; `frontend-hormonia/src/lib/api-client/treatments.ts` | Support both legacy `page/size` and v2 `cursor/limit`; normalize `data` and `items`. | Frontend Dashboard Team | List screens using old or new pagination style | No callers using page/size mode and no `items`-only consumers | Wave-Compat-3 (YYYY-MM-DD) | Telemetry of query params (`page`,`size`,`cursor`,`limit`) + API client tests |
| Frontend websocket adapter | `frontend-hormonia/src/lib/websocket.ts` | Convert backend `type` protocol messages to frontend `event` names. | Frontend Dashboard Team | Realtime UI modules relying on `event` contract | Backend and frontend fully aligned on one protocol format | Wave-Compat-3 (YYYY-MM-DD) | Count of converted backend messages vs native frontend event messages |
| Backend sync payload adapter | `backend-hormonia/app/services/platform_synchronization.py` | `sync_patient_record_update` accepts legacy single-payload shapes and maps to normalized interaction list. | Backend API Team | Legacy integrations posting old payload shape | No calls with legacy keys (`flow_advancement`, `patient_response`, etc.) | Wave-Compat-3 (YYYY-MM-DD) | Log count of legacy key mapping path usage |
| Quiz response-type adapter | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | Map legacy question types (`free_text`, `checkbox`, `radio`) to DB-safe response types. | Backend API Team | Quiz interface and template payloads with older question types | No incoming legacy question types for 2 release cycles | Wave-Compat-2 (YYYY-MM-DD) | Count of mapped legacy types in submit path |

## Legacy Auth/Session Shims
| layer | location | compatibility contract | owner | consumer | sunset trigger | target removal wave/date placeholder | metric to monitor |
|---|---|---|---|---|---|---|---|
| Backend session resolver shim | `backend-hormonia/app/dependencies/auth_dependencies.py` | Resolve session from cookie, `X-Session-ID`, or `Authorization` fallback (configurable priority). | Backend API Team | Browser, websocket, and legacy header-token clients | Header/bearer fallback usage near-zero | Wave-Compat-2 (YYYY-MM-DD) | Auth-source usage split from logs |
| Backend session endpoints shim | `backend-hormonia/app/routers/auth_session.py` | `/session/validate` and `/session/logout` accept cookie primary + `X-Session-ID` fallback. | Backend API Team | Older clients still using `X-Session-ID` | Header fallback usage near-zero | Wave-Compat-2 (YYYY-MM-DD) | Request share containing `X-Session-ID` |
| Backend legacy token auth shim | `backend-hormonia/app/dependencies/auth_dependencies.py` | Keep deprecated Firebase token path (`get_current_user`) while session auth migration finishes. | Backend API Team | Legacy API clients using Firebase bearer token | Bearer-token auth traffic near-zero | Wave-Compat-3 (YYYY-MM-DD) | Calls through `get_current_user` vs `get_current_user_from_session` |
| Frontend medico auth shim | `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` | Preserve legacy `{ state, signIn, signOut }` contract over new auth provider. | Frontend Dashboard Team | Legacy medico screens/hooks | No imports of `useMedicoAuth` and legacy `state` usage | Wave-Compat-3 (YYYY-MM-DD) | Import/reference count for `useMedicoAuth` |
| Quiz client session alias | `quiz-mensal-interface/lib/api-client.ts` | Keep `getSessionStatus()` as alias to `recoverSession()` for older call sites. | Quiz Interface Team | Legacy quiz hooks/components | No calls to `getSessionStatus()` for 2 release cycles | Wave-Compat-3 (YYYY-MM-DD) | Call-site count for `getSessionStatus` |

## Quiz Compatibility Endpoints
| layer | location | compatibility contract | owner | consumer | sunset trigger | target removal wave/date placeholder | metric to monitor |
|---|---|---|---|---|---|---|---|
| Quiz public CSRF shim | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | Keep `GET /auth/csrf-token` under monthly-quiz-public prefix for quiz interface handshake. | Backend API Team | `quiz-mensal-interface` API client | Quiz client migrated to canonical CSRF path (if changed) | Wave-Compat-2 (YYYY-MM-DD) | Request count on `/api/v2/monthly-quiz-public/auth/csrf-token` |
| Quiz access shim | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | `POST /access` creates/recovers session and sets `quiz_session_id` HttpOnly cookie. | Backend API Team | `quiz-mensal-interface` and short-link flow | New canonical access flow adopted everywhere | Wave-Compat-2 (YYYY-MM-DD) | Success/error rate for `/api/v2/monthly-quiz-public/access` |
| Quiz session recovery shim | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | `GET /session/active` supports F5/session recovery from cookie. | Backend API Team | `quiz-mensal-interface` | Client no longer relies on cookie session recovery endpoint | Wave-Compat-3 (YYYY-MM-DD) | Request count and 401/404 rate for `/session/active` |
| Quiz submit shim | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | `POST /submit` accepts compatibility payload and returns legacy-friendly response shape. | Backend API Team | `quiz-mensal-interface` | Client migrated to canonical submit schema | Wave-Compat-3 (YYYY-MM-DD) | 4xx/5xx rate and payload validation failures on `/submit` |
| Quiz logout shim | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | `POST /logout` clears compatibility cookie and finalizes session state. | Backend API Team | `quiz-mensal-interface` | No active clients calling compatibility logout endpoint | Wave-Compat-3 (YYYY-MM-DD) | Request count on `/logout` |
| Quiz prefix alias mount | `backend-hormonia/app/api/v2/router.py` | Keep both `/api/v2/monthly-quiz-public/*` and `/api/v2/monthly-quiz/*` mapped to monthly quiz operations for client compatibility. | Backend API Team | Quiz interface and legacy integrations | One prefix fully unused for 2 release cycles | Wave-Compat-3 (YYYY-MM-DD) | Traffic split by prefix (`/monthly-quiz-public` vs `/monthly-quiz`) |
| Legacy token decoding shim | `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py` | Accept JWT (preferred) and legacy base64 JSON tokens in `_decode_quiz_token`. | Backend API Team | Old quiz links and external senders | Legacy base64 token usage near-zero | Wave-Compat-2 (YYYY-MM-DD) | Count of legacy-token decode path + warning logs |
| Quiz short-link bridge | `backend-hormonia/app/core/router_registry.py` | Keep `/q/{code}` short link resolution and redirect to tokenized monthly quiz URL. | Backend API Team | WhatsApp/SMS links and external link distributors | New link format fully adopted and short links no longer generated | Wave-Compat-3 (YYYY-MM-DD) | Hit count + 404/410 rate for `/q/{code}` |

