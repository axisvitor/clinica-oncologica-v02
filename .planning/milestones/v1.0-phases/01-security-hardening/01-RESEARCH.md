# Phase 1: Security Hardening - Research

**Researched:** 2026-02-22
**Domain:** Python/FastAPI authentication, credential management, deployment config validation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Auth approach**: Use same auth system as rest of API — `get_current_user` standard + role check
- **Role minimum**: `admin` OR `medico/doctor` can access monitoring/metrics
- **Health checks**: `/health/live`, `/health/ready` remain WITHOUT auth — needed for Railway health probes
- **Monitoring endpoints**: require authenticated session with adequate role

### Claude's Discretion

- TEST_TOKEN_REGISTRY: escolher entre mover para conftest ou remover completamente — priorizar segurança máxima
- Debug endpoints: escolher entre remover de produção ou manter com auth forte — seguir melhores práticas OWASP
- JWT default secret: escolher entre remover default ou manter apenas em dev — seguir melhor prática de credential hygiene
- Firebase key storage: escolher método mais adequado para Railway (env var base64 é o padrão do Railway)
- Local key file: seguir abordagem mais segura
- Deploy validation: escolher entre startup check, CI gate, ou ambos
- Config validation scope: decidir se vale expandir além do debug flag nesta fase

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEC-01 | Monitoring endpoints autenticados com `get_current_user` + role check (substituir placeholder auth em `enhanced_monitoring.py`) | The file already imports `get_admin_user` from admin deps but its *own* `get_admin_user` function is a placeholder that queries the DB directly with no token validation. Replacing it with the canonical `get_admin_user` from `app.dependencies.auth_dependencies` (via session) is the correct fix. |
| SEC-02 | TEST_TOKEN_REGISTRY removido do binário de produção (mover para conftest de testes) | Registry currently lives in `app/dependencies/auth_dependencies.py` and `app/api/v2/routers/admin/dependencies.py`. It is guarded by `APP_ENVIRONMENT` checks, but the symbol still exists in the production binary. Must be moved so `grep -r "TEST_TOKEN_REGISTRY" app/` returns zero results. |
| SEC-03 | Firebase service account key removido do working directory (usar GCP Secret Manager ou env var) | No `.json` service account file was found in the working directory. Firebase credentials already flow through env vars (`FIREBASE_ADMIN_PRIVATE_KEY` etc.), confirmed by `service-api.yaml` which uses `secretKeyRef`. The risk is in the `.gitignore` / developer workflow — a key file may have existed or could be created. Need to verify `.gitignore` coverage and add startup guardrail. |
| SEC-04 | `APP_ENABLE_DEBUG=False` enforced em staging e produção via deployment config validation | `APP_ENABLE_DEBUG` defaults to `True` in `base.py`. No startup validator currently blocks startup when `APP_ENABLE_DEBUG=True` in a production/staging environment. A pydantic model validator in `SecuritySettings` (or `BaseAppSettings`) can enforce this, mirroring the pattern already used for `SECURITY_SECRET_KEY`. |
</phase_requirements>

---

## Summary

Phase 1 addresses four distinct security exposures that must be eliminated before going live with real patients. The work is largely surgical — the infrastructure for proper auth already exists, and the fixes involve replacing a placeholder, removing a test bypass symbol from production code, verifying credential hygiene, and adding a startup guardrail.

**SEC-01** is the most visible fix: `enhanced_monitoring.py` defines its own `get_admin_user` that does a raw DB query and returns the first admin user it finds, bypassing session/token validation entirely. The canonical `get_admin_user` already exists in `app.dependencies.auth_dependencies` (and a similar one in `app.api.v2.routers.admin.dependencies`). The monitoring router just needs to import and use the right dependency.

**SEC-02** requires removing `TEST_TOKEN_REGISTRY` from `app/dependencies/auth_dependencies.py` and `app/api/v2/routers/admin/dependencies.py` entirely, then consolidating all test token wiring into `tests/api/conftest.py` and `tests/api/v2/conftest_auth.py` via `dependency_overrides` only. The symbol must not be importable from any `app/` module.

**SEC-03** is a verification task with a small guardrail addition. No service account key file was found in the working directory, but the system lacks a startup-time assertion that no such file exists. Adding a check in `lifespan.py` that logs a critical warning (or raises) if a `.json` file containing `service_account` content is found in the working directory provides belt-and-suspenders protection.

**SEC-04** requires adding a pydantic `@model_validator` to `BaseAppSettings` or `SecuritySettings` that raises `ValueError` when `APP_ENABLE_DEBUG=True` and `APP_ENVIRONMENT` is `production` or `staging`. This follows the exact same pattern as the existing `validate_secret_key` validator.

**Primary recommendation:** Fix SEC-01 first (most immediate patient data risk), then SEC-02 (removes debug bypass from binary), then SEC-04 (prevents misconfigured deploy), then SEC-03 verification. All four are independent and can be planned as separate stories within the phase.

---

## Standard Stack

### Core (already in use — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI `Depends` | (current) | Dependency injection for auth | Already used by all other authenticated endpoints |
| pydantic `@model_validator` | v2 (current) | Startup validation | Same pattern as `validate_secret_key` already in `SecuritySettings` |
| python-dotenv | (current) | `.env` loading | Already used in `main.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `app.dependencies.auth_dependencies.get_admin_user` | (internal) | Role-checked admin dependency | SEC-01: replace monitoring placeholder |
| `app.dependencies.auth_dependencies.get_current_active_user` | (internal) | Active-user dependency | SEC-01: for doctor-accessible monitoring |
| `pytest dependency_overrides` | (pytest) | Test fixture injection | SEC-02: only mechanism tests need post-removal |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic validator for debug flag | CI script check only | CI check doesn't prevent manual prod deploy; startup check is more reliable |
| env var for Firebase key (current) | GCP Secret Manager | Secret Manager requires GCP SDK and network at startup — env var via Railway secret is simpler and already working |
| Full removal of TEST_TOKEN_REGISTRY | Keep with strict env guard | The symbol existing in `app/` means it can be imported; removal is safer and the success criterion explicitly requires grep returning zero results |

---

## Architecture Patterns

### Pattern 1: Replace Placeholder Auth in Monitoring Router (SEC-01)

**What:** The `enhanced_monitoring.py` file defines its own `get_admin_user` that bypasses session validation. Replace it with imports from the canonical auth module.

**Current broken code (lines 84–97 of `enhanced_monitoring.py`):**
```python
async def get_admin_user(
    db=Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> User:
    # TODO: Replace with actual auth integration
    user = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, ...)
    return user
```

**Correct replacement (import from canonical module):**
```python
# At top of file — replace local get_admin_user definition entirely
from app.dependencies.auth_dependencies import (
    get_current_active_user,
    get_admin_user,
)
```

The canonical `get_admin_user` in `auth_dependencies.py` (line 1462) requires `get_current_active_user` which requires `get_current_user`, enforcing Firebase token validation + session validation. The CONTEXT.md decision says admin OR doctor can access monitoring — this means some endpoints should use `get_admin_user` (admin only) and others `get_current_active_user` (any authenticated user). Use `get_admin_user` for mutation/action endpoints (`/actions/*`, `/config PUT`, `/reset-stats`) and `get_current_active_user` for read endpoints.

**Note on `/health` endpoint:** It has no auth (`get_admin_user` not in its signature). This must stay unauthenticated (health probe). The `/export/prometheus` endpoint also currently has no auth — this should remain consistent with the OWASP recommendation to not require auth on prometheus scrape endpoints, OR add auth if Prometheus is not being used. The context says health checks stay open; Prometheus is a separate discretionary call.

### Pattern 2: Remove TEST_TOKEN_REGISTRY from Production Binary (SEC-02)

**What:** The registry lives in `app/dependencies/auth_dependencies.py` and is imported by `app/api/v2/routers/admin/dependencies.py`. Tests access it directly.

**Files to change:**
1. `app/dependencies/auth_dependencies.py` — delete the `TEST_TOKEN_REGISTRY` variable declaration and all usage blocks (lines 42–65 and the check at lines 1207–1217)
2. `app/api/v2/routers/admin/dependencies.py` — remove the import and usage of `TEST_TOKEN_REGISTRY` (lines 15–17 and 80–88)
3. `tests/api/conftest.py` — replace `from app.dependencies.auth_dependencies import TEST_TOKEN_REGISTRY` with pure `dependency_overrides` only (already uses `app.dependency_overrides[get_current_user] = lambda: admin_user` — just remove the registry manipulation)
4. Any other `tests/` files that import `TEST_TOKEN_REGISTRY` — switch to `dependency_overrides`

**After removal, test auth pattern (tests only, never app/):**
```python
# In conftest.py fixtures — no TEST_TOKEN_REGISTRY needed
@pytest.fixture
def admin_token(admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield f"admin_token_{admin_user.id}"
    app.dependency_overrides.pop(get_current_user, None)
```

**Verification command (must return 0 results):**
```bash
grep -r "TEST_TOKEN_REGISTRY" app/
```

### Pattern 3: Firebase Credential Guardrail (SEC-03)

**What:** No service account key file found on disk. The deployment already uses env vars (`secretKeyRef` in `service-api.yaml`). The gap is lack of an explicit runtime assertion.

**Add to `lifespan.py` startup, before accepting traffic:**
```python
import glob as _glob

def _check_no_service_account_file():
    """Fail fast if a Firebase service account key file is found in the working directory."""
    patterns = ["*service_account*.json", "*firebase_adminsdk*.json", "*serviceAccountKey*.json"]
    for pattern in patterns:
        found = _glob.glob(pattern) + _glob.glob(f"**/{pattern}", recursive=True)
        # Exclude .venv and test fixtures
        found = [f for f in found if ".venv" not in f and "/tests/" not in f]
        if found:
            import logging
            logging.getLogger(__name__).critical(
                "SECURITY: Firebase service account key file found in working directory: %s. "
                "Remove it immediately and use env vars (FIREBASE_ADMIN_PRIVATE_KEY).",
                found,
            )
            # In production, fail hard
            if settings.APP_ENVIRONMENT.lower() in ("production", "staging"):
                raise RuntimeError(f"Service account key file found in production: {found}")
```

**Additionally, verify `.gitignore` covers:** `*service_account*.json`, `*firebase_adminsdk*.json`, `*.json` (or more targeted patterns).

### Pattern 4: Startup Validation for APP_ENABLE_DEBUG (SEC-04)

**What:** Add a `@model_validator` to `BaseAppSettings` that mirrors the existing `validate_secret_key` pattern.

**Location:** `/backend-hormonia/app/config/settings/base.py`

**New validator:**
```python
@model_validator(mode="after")
def validate_debug_flag(self) -> "BaseAppSettings":
    """
    Prevent deployment with APP_ENABLE_DEBUG=True in production or staging.
    Mirrors validate_secret_key pattern in SecuritySettings.
    """
    import logging
    logger = logging.getLogger(__name__)
    env = self.APP_ENVIRONMENT.lower()
    if self.APP_ENABLE_DEBUG and env in ("production", "prod", "staging"):
        raise ValueError(
            f"APP_ENABLE_DEBUG=True is not allowed in {env} environment.\n"
            "Set APP_ENABLE_DEBUG=False in your deployment configuration.\n"
            "This prevents debug routes and test token bypasses from being active."
        )
    return self
```

**Why `BaseAppSettings` and not `SecuritySettings`:** `APP_ENABLE_DEBUG` is defined in `BaseAppSettings`. Adding the validator there ensures it runs before any other settings class that inherits from it. The existing `validate_secret_key` is in `SecuritySettings` because it validates `SECURITY_SECRET_KEY` which is defined there — same locality principle.

### Anti-Patterns to Avoid

- **Don't use `get_current_user` (Firebase Bearer) for monitoring**: The system has migrated to session-based auth (`get_current_user_from_session`). The admin role dependencies chain correctly through sessions. Using the deprecated `get_current_user` would require Firebase Bearer tokens to access monitoring, which is inconsistent.
- **Don't keep TEST_TOKEN_REGISTRY with just an environment guard**: A symbol that can be imported from `app/` can be misused. The success criterion requires zero grep results — removal is the only option.
- **Don't validate APP_ENABLE_DEBUG only in CI**: A CI check that can be bypassed by manual deploys doesn't satisfy the success criterion ("falha na validação de configuração antes de aceitar tráfego").
- **Don't use `APP_ENABLE_DEBUG` as a proxy for test environment in `admin/dependencies.py`**: The `_is_test_environment()` check (line 27–32) uses `PYTEST_CURRENT_TEST` env var and `TESTING=1` — this is safe. The `APP_ENABLE_DEBUG` path in `auth_dependencies.py` is what needs removal.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Role check for monitoring | Custom role check in each endpoint | `get_admin_user` / `get_current_active_user` from `auth_dependencies.py` | Already handles session + Firebase token + role + active user in one dependency |
| Firebase credential validation pattern | Custom validator | pydantic `@model_validator` (same pattern as `validate_secret_key`) | Already established pattern in the codebase, runs at startup before app accepts traffic |
| Test auth bypass | Keep registry with guards | `app.dependency_overrides` (pytest FastAPI pattern) | Proper FastAPI test pattern, no production symbol needed |

**Key insight:** Every pattern needed already exists in the codebase. This phase is exclusively about applying existing patterns to the gaps.

---

## Common Pitfalls

### Pitfall 1: Breaking the Monitoring Tests (SEC-01)

**What goes wrong:** `tests/api/v2/test_enhanced_monitoring.py` uses fixtures that may depend on the placeholder `get_admin_user` in `enhanced_monitoring.py`. Replacing it with the canonical dependency changes the injection point tests must override.

**Why it happens:** The test file patches `enhanced_monitoring.get_admin_user` or patches at the module level. After the fix, tests must override `auth_dependencies.get_admin_user` or `get_current_user`.

**How to avoid:** After replacing the dependency, update test overrides to use `app.dependency_overrides[get_current_user] = lambda: admin_user` at the `get_current_user` level (the root of the auth chain).

**Warning signs:** Tests start returning 403 or 503 errors after the fix.

### Pitfall 2: TEST_TOKEN_REGISTRY Removal Breaks Admin Dependency Tests (SEC-02)

**What goes wrong:** `app/api/v2/routers/admin/dependencies.py` imports `TEST_TOKEN_REGISTRY` and uses it in its `get_admin_user` function (lines 80–88). After removal, the admin dependency needs to be re-tested.

**Why it happens:** The admin `get_admin_user` has a test-environment fast path (lines 71–78) that queries the DB for any admin user when no session headers are present. This path remains safe after removal. The registry lookup (lines 80–88) is the part being removed.

**How to avoid:** Verify that after removal, tests that currently inject tokens via the registry instead use `dependency_overrides`. The `_is_test_environment()` path in `admin/dependencies.py` is a separate (safe) test accommodation that should be left alone for now.

**Warning signs:** Admin endpoint tests start returning 401 instead of the expected response.

### Pitfall 3: Pydantic Validator Ordering (SEC-04)

**What goes wrong:** Pydantic v2 runs `@model_validator(mode="after")` validators after all field assignments. If `APP_ENVIRONMENT` defaults to `"development"` and is not set in the test environment, the validator could block test startup.

**Why it happens:** `APP_ENABLE_DEBUG` defaults to `True` in `base.py`. If a test environment doesn't explicitly set `APP_ENABLE_DEBUG=False`, the validator would fire if `APP_ENVIRONMENT` were `"staging"` or `"production"`.

**How to avoid:** The validator only fires when `APP_ENVIRONMENT` is `production/prod/staging`. Test environments use the default `development`. Confirm that CI test configuration does NOT set `APP_ENVIRONMENT=production`. Also verify that pydantic settings evaluation at import time (module-level `settings = ...`) does not block test imports.

**Warning signs:** `ImportError` or `ValueError` on test collection when test env var config is reviewed.

### Pitfall 4: `/export/prometheus` Authentication Decision (SEC-01 adjacent)

**What goes wrong:** The Prometheus scrape endpoint (`/export/prometheus`) currently has no auth. If you add `get_admin_user` to it, Prometheus scraping will break because Prometheus doesn't send auth headers by default.

**Why it happens:** The standard `get_admin_user` dependency requires session cookies or Bearer tokens. Prometheus uses HTTP Basic Auth or bearer tokens only if explicitly configured.

**How to avoid:** Leave `/export/prometheus` without session-based auth. The CONTEXT.md decision is that monitoring endpoints require auth — the Prometheus endpoint is a metrics *export* for Prometheus scraping, not a monitoring dashboard endpoint. It should be protected by network policy (internal-only) rather than application auth. This is the OWASP-recommended pattern for Prometheus endpoints.

---

## Code Examples

### SEC-01: Corrected `enhanced_monitoring.py` auth imports

```python
# Source: existing canonical pattern in app/dependencies/auth_dependencies.py

# REMOVE the local get_admin_user definition (lines 84-97)
# ADD this import near the top of enhanced_monitoring.py

from app.dependencies.auth_dependencies import (
    get_admin_user,          # for admin-only endpoints
    get_current_active_user, # for read endpoints accessible to doctors too
)

# The endpoints using current_user: User = Depends(get_admin_user) remain unchanged
# The /health endpoint stays with no auth dependency (health probe)
# The /export/prometheus endpoint stays with no auth dependency (Prometheus scraping)
```

### SEC-02: Post-removal conftest pattern (tests/ only)

```python
# Source: FastAPI docs — dependency_overrides pattern
# In tests/api/conftest.py

@pytest.fixture
def admin_token(admin_user):
    """Provide an admin token using dependency_overrides only (no TEST_TOKEN_REGISTRY)."""
    from app.dependencies.auth_dependencies import get_current_user
    token = f"admin_token_{admin_user.id}"
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield token
    app.dependency_overrides.pop(get_current_user, None)
```

### SEC-04: Debug flag validator in BaseAppSettings

```python
# Source: existing validate_secret_key pattern in SecuritySettings
# Location: app/config/settings/base.py

@model_validator(mode="after")
def validate_debug_flag(self) -> "BaseAppSettings":
    """Block startup with APP_ENABLE_DEBUG=True in production/staging."""
    import logging
    logger = logging.getLogger(__name__)
    env = self.APP_ENVIRONMENT.lower()
    if self.APP_ENABLE_DEBUG and env in ("production", "prod", "staging"):
        raise ValueError(
            f"APP_ENABLE_DEBUG=True is not allowed in '{env}' environment.\n"
            "Set APP_ENABLE_DEBUG=False in your deployment configuration.\n"
            "This prevents debug routes and authentication bypasses in production."
        )
    if self.APP_ENABLE_DEBUG and env not in ("development", "dev", "test", "testing"):
        logger.warning(
            "APP_ENABLE_DEBUG=True in environment '%s'. "
            "This is only safe in development/test environments.",
            env,
        )
    return self
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|-----------------|-------|
| Firebase Bearer token validation | Session-based auth (Redis) | Both still work; `get_current_user` (Firebase) is deprecated; `get_current_user_from_session` is preferred |
| In-app test token registry | `dependency_overrides` (FastAPI test pattern) | Registry is a workaround that predates proper test patterns |
| Manual environment checks | Pydantic model validators at startup | Already used for `SECURITY_SECRET_KEY` — extend to debug flag |

---

## Open Questions

1. **Should `/export/prometheus` require any auth for SEC-01?**
   - What we know: Prometheus scraping usually uses network-level isolation, not app-level auth. The endpoint is currently unauthenticated. The CONTEXT.md says "monitoring endpoints requerem sessão autenticada" but does not explicitly mention Prometheus.
   - What's unclear: Whether Prometheus is actively scraping this endpoint in production or if it's unused.
   - Recommendation: Leave unauthenticated for now (consistent with standard practice). If Prometheus is not deployed, the endpoint is harmless. If deployed, network policy already restricts access.

2. **Should the debug router be removed from production builds or just kept disabled?**
   - What we know: `debug/__init__.py` says "NEVER enable in production". The router is only registered when `enable_debug_endpoints=True` (which requires `APP_ENABLE_DEBUG=True`, which SEC-04 now blocks in production). So fixing SEC-04 transitively prevents debug routes.
   - What's unclear: Whether there is value in removing the router registration entirely vs. relying on the `APP_ENABLE_DEBUG` gate.
   - Recommendation: SEC-04 fix is sufficient. The debug router registration in `application_factory.py` is gated by `APP_ENABLE_DEBUG`, so after SEC-04 adds a startup error for `APP_ENABLE_DEBUG=True` in production, debug endpoints become unreachable in production by construction. No additional change needed.

3. **Should `admin/dependencies.py`'s `_is_test_environment()` bypass be removed?**
   - What we know: Lines 71–78 of `admin/dependencies.py` allow any admin DB user to authenticate when there are no session headers in a test environment. This is separate from `TEST_TOKEN_REGISTRY`.
   - What's unclear: Whether this bypass should be in scope for Phase 1 or deferred.
   - Recommendation: Keep `_is_test_environment()` bypass for now — it is strictly scoped to `PYTEST_CURRENT_TEST` / `TESTING=1` env vars which are never set in production. It does not appear in the production binary's critical path. Defer cleanup to a later phase.

---

## Sources

### Primary (HIGH confidence — direct codebase investigation)

- `/backend-hormonia/app/api/v2/routers/enhanced_monitoring.py` — confirmed placeholder `get_admin_user` definition (lines 84–97 with TODO comment)
- `/backend-hormonia/app/dependencies/auth_dependencies.py` — confirmed `TEST_TOKEN_REGISTRY` location (lines 42–65), canonical `get_admin_user` at line 1462, `get_current_active_user` at line 1425
- `/backend-hormonia/app/api/v2/routers/admin/dependencies.py` — confirmed second `TEST_TOKEN_REGISTRY` import and usage
- `/backend-hormonia/app/config/settings/base.py` — confirmed `APP_ENABLE_DEBUG` definition (line 32, default `True`), no startup validator for debug flag
- `/backend-hormonia/app/config/settings/security.py` — confirmed existing `validate_secret_key` `@model_validator` pattern (lines 244–304), confirmed Firebase credentials are env-var based (lines 132–143)
- `/backend-hormonia/config/cloud-run/service-api.yaml` — confirmed `APP_ENABLE_DEBUG=false` in Cloud Run config, `FIREBASE_ADMIN_PRIVATE_KEY` via `secretKeyRef` (no file)
- `/backend-hormonia/tests/api/conftest.py` — confirmed current TEST_TOKEN_REGISTRY usage pattern in test fixtures

### Secondary (MEDIUM confidence — doc cross-reference)

- `/backend-hormonia/.env.production.template` — confirms `APP_ENABLE_DEBUG=false` is the documented production value
- `/backend-hormonia/worker/.env.example` — confirms `APP_ENABLE_DEBUG=false` in worker config
- Filesystem scan: no `*service_account*.json` or `*firebase_adminsdk*.json` files found outside `.venv`

---

## Metadata

**Confidence breakdown:**
- SEC-01 (monitoring auth): HIGH — exact lines of code identified, replacement pattern is clear
- SEC-02 (TEST_TOKEN_REGISTRY removal): HIGH — all 7 affected files identified, post-removal test pattern established
- SEC-03 (Firebase credential management): HIGH — verified no key file exists, env var pattern confirmed in deployment config; guardrail addition is straightforward
- SEC-04 (debug flag validation): HIGH — `validate_secret_key` pattern is identical, just different field

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (stable codebase, no fast-moving dependencies)
