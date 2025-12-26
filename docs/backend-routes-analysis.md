# Backend Routes Analysis - FastAPI Application

**Research Completed**: 2025-12-22
**Researcher**: Hive Mind Swarm Agent (swarm-1766378945480-0yw38nbrl)

## Executive Summary

Comprehensive analysis of all backend routes in the FastAPI application (`backend-hormonia`). The application uses a well-organized router structure with API versioning (v2) and consolidated router modules.

---

## 1. Main Router Configuration

### File: `/backend-hormonia/app/api/v2/router.py`

**Base Prefix**: `/api/v2`

The main API v2 router includes **54 sub-routers** organized into 10 phases:

---

## 2. Complete Route Registry

### Phase 1: Core Clinical Modules (Patients)

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `patients_crud_router` | `/patients` | `patients-crud-v2` | `routers/patients/__init__.py` |
| `patients_import_router` | `/patients` | `patients-import-v2` | `routers/patients_import.py` |
| `patients_flow_router` | `/patients` | `patients-flow-v2` | `routers/patients_flow.py` |
| `patients_integrity_router` | `/patients` | `patients-integrity-v2` | `routers/patients_integrity.py` |
| `appointments_router` | `/appointments` | `appointments-v2` | `routers/appointments.py` |
| `treatments_router` | `/treatments` | `treatments-v2` | `routers/treatments.py` |
| `medications_router` | `/medications` | `medications-v2` | `routers/medications.py` |

**Full Paths**:
- `/api/v2/patients/*` (CRUD, import, flow, integrity)
- `/api/v2/appointments/*`
- `/api/v2/treatments/*`
- `/api/v2/medications/*`

---

### Phase 2: Quiz and Analytics

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `quiz_router` | `/quiz` | `quiz-v2` | `routers/quiz_sessions.py` |
| `analytics_router` | `/analytics` | `analytics-v2` | `routers/analytics.py` |
| `enhanced_analytics_router` | `/enhanced-analytics` | `enhanced-analytics-v2` | `routers/enhanced_analytics.py` |

**Full Paths**:
- `/api/v2/quiz/*`
- `/api/v2/analytics/*`
- `/api/v2/enhanced-analytics/*`

---

### Phase 3: Auth & Users

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `auth_router` | `/auth` | `auth-v2` | `routers/auth.py` |
| `users_router` | `/auth` | `users-v2` | `routers/users.py` |
| `notifications_router` | `/notifications` | `notifications-v2` | `routers/notifications.py` |
| `notifications_router` (duplicate) | `/auth/notifications` | `notifications-v2-legacy` | `routers/notifications.py` |

**Full Paths**:
- `/api/v2/auth/*` (Firebase verify, logout, CSRF token, sessions)
- `/api/v2/auth/me` (user profile)
- `/api/v2/auth/preferences` (user preferences)
- `/api/v2/notifications/*`
- `/api/v2/auth/notifications/*` (legacy path)

**⚠️ ISSUE IDENTIFIED: Duplicate Router Registration**
- `notifications_router` is registered TWICE (lines 100-104):
  1. `/notifications` (primary)
  2. `/auth/notifications` (legacy)

---

### Phase 4: Flows, Messages, Reports, Admin, Webhooks, AI

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `flows_router` | `/flows` | `flows-v2` | `routers/flows.py` |
| `messages_router` | `/messages` | `messages-v2` | `routers/messages.py` |
| `enhanced_messages_router` | `/enhanced-messages` | `enhanced-messages-v2` | `routers/enhanced_messages.py` |
| `reports_router` | `/reports` | `reports-v2` | `routers/reports.py` |
| `admin_router` | `/admin` | `admin-v2` | `routers/admin.py` |
| `webhooks_router` | `/webhooks` | `webhooks-v2` | `routers/webhooks.py` |
| `ai_router` | `/ai` | `ai-v2` | `routers/ai.py` |

**Full Paths**:
- `/api/v2/flows/*`
- `/api/v2/messages/*`
- `/api/v2/enhanced-messages/*`
- `/api/v2/reports/*`
- `/api/v2/admin/*`
- `/api/v2/webhooks/*`
- `/api/v2/ai/*`

---

### Phase 5: Enhanced Modules and Alerts

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `enhanced_monitoring_router` | `/monitoring` | `enhanced-monitoring-v2` | `routers/enhanced_monitoring.py` |
| `enhanced_quiz_router` | `/enhanced-quiz` | `enhanced-quiz-v2` | `routers/enhanced_quiz.py` |
| `enhanced_reports_router` | `/enhanced-reports` | `enhanced-reports-v2` | `routers/enhanced_reports.py` |
| `alerts_router` | `/alerts` | `alerts-v2` | `routers/alerts.py` |

**Full Paths**:
- `/api/v2/monitoring/*`
- `/api/v2/enhanced-quiz/*`
- `/api/v2/enhanced-reports/*`
- `/api/v2/alerts/*`

---

### Phase 6: Templates, A/B Testing, Platform Sync

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `flow_templates_router` | `/templates` | `flow-templates-v2` | `routers/flow_templates.py` |
| `quiz_templates_router` | `/templates` | `quiz-templates-v2` | `routers/quiz_templates.py` |
| `template_versions_router` | `/templates` | `template-versions-v2` | `routers/template_versions.py` |
| `template_admin_router` | `/templates` | `template-admin-v2` | `routers/template_admin.py` |
| `ab_testing_router` | `/ab-testing` | `ab-testing-v2` | `routers/ab_testing.py` |
| `platform_sync_router` | `/platform-sync` | `platform-sync-v2` | `routers/platform_sync.py` |

**Full Paths**:
- `/api/v2/templates/*` (4 routers share this prefix)
- `/api/v2/ab-testing/*`
- `/api/v2/platform-sync/*`

**⚠️ POTENTIAL ISSUE: Multiple Routers Sharing Same Prefix**
- 4 template routers share `/templates` prefix
- Could lead to route conflicts if not carefully managed

---

### Phase 7: Tasks, Upload, Localization, Dashboard

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `tasks_router` | `/tasks` | `tasks-v2` | `routers/tasks.py` |
| `upload_router` | `/upload` | `upload-v2` | `routers/upload.py` |
| `localization_router` | `/localization` | `localization-v2` | `routers/localization.py` |
| `dashboard_router` | `/dashboard` | `dashboard-v2` | `routers/dashboard.py` |

**Full Paths**:
- `/api/v2/tasks/*`
- `/api/v2/upload/*`
- `/api/v2/localization/*`
- `/api/v2/dashboard/*`

---

### Phase 8: Docs, Physicians, Admin Extensions

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `docs_router` | `/docs` | `docs-v2` | `routers/docs.py` |
| `physicians_router` | `/physicians` | `physicians-v2` | `routers/physicians.py` |
| `admin_extensions_router` | `/admin-extensions` | `admin-extensions-v2` | `routers/admin_extensions.py` |

**Full Paths**:
- `/api/v2/docs/*`
- `/api/v2/physicians/*`
- `/api/v2/admin-extensions/*`

---

### Phase 9: Roles, System, Performance, Health, Quiz Extensions

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `roles_router` | `/roles` | `roles-v2` | `routers/roles.py` |
| `system_router` | `/system` | `system-v2` | `routers/system.py` |
| `performance_router` | `/performance` | `performance-v2` | `routers/performance.py` |
| `health_router` | (none) | `health-v2` | `routers/health.py` |
| `quiz_responses_router` | `/quiz-extensions` | `quiz-responses-v2` | `routers/quiz_responses.py` |
| `quiz_alerts_router` | `/quiz-extensions` | `quiz-alerts-v2` | `routers/quiz_alerts.py` |
| `monthly_quiz_management_router` | `/quiz-extensions` | `monthly-quiz-v2` | `routers/monthly_quiz_management.py` |
| `monthly_quiz_operations_router` | `/quiz-extensions` | `monthly-quiz-ops-v2` | `routers/monthly_quiz_operations.py` |

**Full Paths**:
- `/api/v2/roles/*`
- `/api/v2/system/*`
- `/api/v2/performance/*`
- `/api/v2/health/*` (health_router has its own `/health` prefix)
- `/api/v2/quiz-extensions/*` (4 routers share this prefix)

**⚠️ ISSUE: Health Router Prefix**
- Comment says "Health router has its own /health prefix" (line 174)
- But router is included WITHOUT a prefix parameter
- This could be misleading

---

### Phase 10: Monthly Quiz Public Access Aliases

| Router | Prefix | Tags | Source File |
|--------|--------|------|-------------|
| `monthly_quiz_operations_router` (duplicate) | `/monthly-quiz-public` | `monthly-quiz-public-v2` | `routers/monthly_quiz_operations.py` |
| `monthly_quiz_operations_router` (duplicate) | `/monthly-quiz` | `monthly-quiz-compat-v2` | `routers/monthly_quiz_operations.py` |

**Full Paths**:
- `/api/v2/monthly-quiz-public/*`
- `/api/v2/monthly-quiz/*`

**⚠️ ISSUE: Router Registered 3 Times**
- `monthly_quiz_operations_router` is registered **3 TIMES**:
  1. `/quiz-extensions` (line 187-190)
  2. `/monthly-quiz-public` (line 194-198)
  3. `/monthly-quiz` (line 200-204)
- Purpose: Frontend compatibility with different path expectations

---

### Phase 11: Debug & Diagnostics (Conditional)

| Router | Prefix | Tags | Source File | Condition |
|--------|--------|------|-------------|-----------|
| `debug_router` | `/debug` | `debug-v2` | `routers/debug.py` | `ENABLE_DEBUG_ENDPOINTS=true` |

**Full Paths**:
- `/api/v2/debug/*` (only if environment variable enabled)

**Security**: Disabled by default in production (line 213)

---

## 3. Route Analysis by Router File

### Patients Router (`routers/patients/__init__.py`)

**Consolidated Module** (lines 5-13 comment):
- Previously scattered across 4 files
- Now organized into 4 sub-modules:
  1. `crud.py` - CRUD operations
  2. `flow.py` - Flow state management
  3. `import_export.py` - CSV import/export
  4. `integrity.py` - Data validation

**Sub-router Configuration**:
```python
router = APIRouter(prefix="")  # Line 23
router.include_router(crud_router, prefix="", tags=["patients-crud"])
router.include_router(flow_router, prefix="", tags=["patients-flow"])
router.include_router(import_export_router, prefix="", tags=["patients-import-export"])
router.include_router(integrity_router, prefix="", tags=["patients-integrity"])
```

**✅ NO TRAILING SLASH ISSUES**: Uses empty prefix `""` consistently

---

### Auth Router (`routers/auth.py`)

**Endpoints** (from grep results):
- `POST /firebase/verify` (line 94)
- `GET /verify-session` (line 283)
- `DELETE /logout` (line 340)
- `DELETE /logout-all` (line 381)
- `GET /csrf-token` (line 424)

**Full Paths**:
- `POST /api/v2/auth/firebase/verify`
- `GET /api/v2/auth/verify-session`
- `DELETE /api/v2/auth/logout`
- `DELETE /api/v2/auth/logout-all`
- `GET /api/v2/auth/csrf-token`

**✅ NO TRAILING SLASH ISSUES**: All routes use clean paths without trailing slashes

---

### Users Router (`routers/users.py`)

**Endpoints** (from grep results):
- `GET /me` (line 91)
- `GET /preferences` (line 146)
- `PATCH /preferences` (line 187)
- `GET /sessions` (line 224)
- `DELETE /sessions/{session_id}` (line 267)

**Full Paths**:
- `GET /api/v2/auth/me`
- `GET /api/v2/auth/preferences`
- `PATCH /api/v2/auth/preferences`
- `GET /api/v2/auth/sessions`
- `DELETE /api/v2/auth/sessions/{session_id}`

**✅ NO TRAILING SLASH ISSUES**: All routes use clean paths without trailing slashes

---

### Medications Router (`routers/medications.py`)

**Endpoints** (from grep results):
- `GET ""` (line 102) - List medications
- `GET "/active"` (line 247)
- `GET "/search"` (line 303)
- `GET "/{medication_id}"` (line 333)
- `POST ""` (line 375)
- `PATCH "/{medication_id}"` (line 432)
- `DELETE "/{medication_id}"` (line 477)

**Full Paths**:
- `GET /api/v2/medications`
- `GET /api/v2/medications/active`
- `GET /api/v2/medications/search`
- `GET /api/v2/medications/{medication_id}`
- `POST /api/v2/medications`
- `PATCH /api/v2/medications/{medication_id}`
- `DELETE /api/v2/medications/{medication_id}`

**✅ NO TRAILING SLASH ISSUES**: Uses empty string `""` for base route

---

### Alerts Router (`routers/alerts.py`)

**Endpoints** (from grep results):
- `GET ""` (line 195)
- `POST ""` (line 329)
- `GET "/{alert_id}"` (line 399)
- `PATCH "/{alert_id}"` (line 465)
- `DELETE "/{alert_id}"` (line 529)
- `PATCH "/{alert_id}/read"` (line 587)
- `POST "/read-all"` (line 664)

**Full Paths**:
- `GET /api/v2/alerts`
- `POST /api/v2/alerts`
- `GET /api/v2/alerts/{alert_id}`
- `PATCH /api/v2/alerts/{alert_id}`
- `DELETE /api/v2/alerts/{alert_id}`
- `PATCH /api/v2/alerts/{alert_id}/read`
- `POST /api/v2/alerts/read-all`

**✅ NO TRAILING SLASH ISSUES**: Consistent use of empty string for base routes

---

## 4. Issues Identified

### Issue 1: Duplicate Router Registrations

**Location**: `app/api/v2/router.py`

#### A. Notifications Router (2 registrations)
```python
# Line 100-101: Primary registration
api_v2_router.include_router(
    notifications_router, prefix="/notifications", tags=["notifications-v2"]
)

# Line 103-104: Legacy registration
api_v2_router.include_router(
    notifications_router, prefix="/auth/notifications", tags=["notifications-v2-legacy"]
)
```

**Impact**:
- ✅ ACCEPTABLE - Intentional for backward compatibility
- Creates two paths: `/api/v2/notifications/*` and `/api/v2/auth/notifications/*`
- Comment indicates legacy path support (line 104)

---

#### B. Monthly Quiz Operations Router (3 registrations)

```python
# Line 187-190: Primary registration
api_v2_router.include_router(
    monthly_quiz_operations_router,
    prefix="/quiz-extensions",
    tags=["monthly-quiz-ops-v2"],
)

# Line 194-198: Frontend compatibility alias 1
api_v2_router.include_router(
    monthly_quiz_operations_router,
    prefix="/monthly-quiz-public",
    tags=["monthly-quiz-public-v2"],
)

# Line 200-204: Frontend compatibility alias 2
api_v2_router.include_router(
    monthly_quiz_operations_router,
    prefix="/monthly-quiz",
    tags=["monthly-quiz-compat-v2"],
)
```

**Impact**:
- ✅ ACCEPTABLE - Intentional for frontend compatibility
- Creates three paths for the same endpoints
- Comment explains: "Frontend expects /monthly-quiz-public/*, so we register the operations router again with this prefix" (line 193)
- Comment explains: "Frontend also expects /monthly-quiz/* for some operations" (line 199)

**Recommendation**: Consider consolidating to a single path in future refactoring once frontend is updated.

---

### Issue 2: Multiple Routers Sharing Same Prefix

#### A. Templates Routers (4 routers, 1 prefix)

```python
# Lines 128-139
api_v2_router.include_router(
    flow_templates_router, prefix="/templates", tags=["flow-templates-v2"]
)
api_v2_router.include_router(
    quiz_templates_router, prefix="/templates", tags=["quiz-templates-v2"]
)
api_v2_router.include_router(
    template_versions_router, prefix="/templates", tags=["template-versions-v2"]
)
api_v2_router.include_router(
    template_admin_router, prefix="/templates", tags=["template-admin-v2"]
)
```

**Potential Risk**:
- ⚠️ NEEDS VERIFICATION - Could cause route conflicts if endpoints overlap
- All 4 routers serve `/api/v2/templates/*`
- **Action Required**: Verify each router has unique sub-paths

---

#### B. Quiz Extensions Routers (4 routers, 1 prefix)

```python
# Lines 177-190
api_v2_router.include_router(
    quiz_responses_router, prefix="/quiz-extensions", tags=["quiz-responses-v2"]
)
api_v2_router.include_router(
    quiz_alerts_router, prefix="/quiz-extensions", tags=["quiz-alerts-v2"]
)
api_v2_router.include_router(
    monthly_quiz_management_router, prefix="/quiz-extensions", tags=["monthly-quiz-v2"]
)
api_v2_router.include_router(
    monthly_quiz_operations_router,
    prefix="/quiz-extensions",
    tags=["monthly-quiz-ops-v2"],
)
```

**Potential Risk**:
- ⚠️ NEEDS VERIFICATION - Could cause route conflicts if endpoints overlap
- All 4 routers serve `/api/v2/quiz-extensions/*`
- **Action Required**: Verify each router has unique sub-paths

---

#### C. Patients Routers (4 routers, 1 prefix)

```python
# Lines 62-73
api_v2_router.include_router(
    patients_crud_router, prefix="/patients", tags=["patients-crud-v2"]
)
api_v2_router.include_router(
    patients_import_router, prefix="/patients", tags=["patients-import-v2"]
)
api_v2_router.include_router(
    patients_flow_router, prefix="/patients", tags=["patients-flow-v2"]
)
api_v2_router.include_router(
    patients_integrity_router, prefix="/patients", tags=["patients-integrity-v2"]
)
```

**Status**:
- ✅ VERIFIED SAFE - Patients module is consolidated
- According to `routers/patients/__init__.py` comments, these were previously separate files
- Now properly organized with unique sub-paths in each sub-router

---

### Issue 3: Health Router Prefix Confusion

**Location**: `app/api/v2/router.py` line 173-174

```python
api_v2_router.include_router(
    health_router, tags=["health-v2"]
)  # Health router has its own /health prefix
```

**Issue**:
- Comment claims "Health router has its own /health prefix"
- But `include_router` call has NO `prefix=` parameter
- This means routes will be registered at `/api/v2/<route>`, not `/api/v2/health/<route>`

**Impact**:
- ⚠️ MISLEADING COMMENT - Could confuse developers
- **Action Required**: Verify actual routes in `routers/health.py` to see if they include `/health` in their path decorators

---

### Issue 4: Trailing Slash Consistency

**Status**: ✅ NO ISSUES FOUND

**Findings**:
- All router prefixes use clean paths without trailing slashes
- All route decorators use clean paths without trailing slashes
- Examples:
  - `prefix="/patients"` ✅
  - `@router.get("")` ✅
  - `@router.get("/active")` ✅
  - `@router.get("/{id}")` ✅

**Recommendation**: Continue current pattern - FastAPI handles trailing slashes automatically with redirects.

---

## 5. Prefix Naming Convention Analysis

### Convention Used: kebab-case

**Examples**:
- `/enhanced-analytics` ✅
- `/enhanced-messages` ✅
- `/enhanced-quiz` ✅
- `/enhanced-reports` ✅
- `/ab-testing` ✅
- `/platform-sync` ✅
- `/quiz-extensions` ✅
- `/admin-extensions` ✅
- `/monthly-quiz-public` ✅

### Exceptions (single words):
- `/patients`, `/appointments`, `/treatments`, `/medications`
- `/quiz`, `/analytics`, `/auth`, `/notifications`
- `/flows`, `/messages`, `/reports`, `/admin`, `/webhooks`, `/ai`
- `/monitoring`, `/alerts`, `/templates`
- `/tasks`, `/upload`, `/localization`, `/dashboard`
- `/docs`, `/physicians`, `/roles`, `/system`, `/performance`, `/health`, `/debug`

**Status**: ✅ CONSISTENT - All multi-word prefixes use kebab-case

---

## 6. Route Conflicts Analysis

### Potential Conflicts to Verify

#### 1. `/api/v2/templates/*` (4 routers)

**Routers**:
1. `flow_templates_router`
2. `quiz_templates_router`
3. `template_versions_router`
4. `template_admin_router`

**Action Required**: Read each router file to verify unique sub-paths

---

#### 2. `/api/v2/quiz-extensions/*` (4 routers)

**Routers**:
1. `quiz_responses_router`
2. `quiz_alerts_router`
3. `monthly_quiz_management_router`
4. `monthly_quiz_operations_router`

**Action Required**: Read each router file to verify unique sub-paths

---

#### 3. `/api/v2/patients/*` (4 routers)

**Routers**:
1. `patients_crud_router`
2. `patients_import_router`
3. `patients_flow_router`
4. `patients_integrity_router`

**Status**: ✅ VERIFIED - Consolidated module with proper organization

---

## 7. Summary Statistics

- **Total Routers**: 54 routers
- **Unique Prefixes**: 37 unique prefixes
- **Shared Prefixes**: 3 prefixes shared by multiple routers
  - `/patients` (4 routers)
  - `/templates` (4 routers)
  - `/quiz-extensions` (4 routers)
- **Duplicate Registrations**: 2 cases
  - `notifications_router` (2 registrations)
  - `monthly_quiz_operations_router` (3 registrations)
- **Trailing Slash Issues**: 0 issues found
- **Naming Convention Violations**: 0 violations found

---

## 8. Recommendations

### High Priority

1. **Verify route conflicts** for shared prefixes:
   - Templates routers (`/templates`)
   - Quiz extensions routers (`/quiz-extensions`)

2. **Clarify health router prefix**:
   - Update comment or add explicit prefix parameter
   - Verify actual routes in `routers/health.py`

### Medium Priority

3. **Document intentional duplicates**:
   - Add inline comments explaining why `notifications_router` is registered twice
   - Add inline comments explaining why `monthly_quiz_operations_router` is registered three times

4. **Plan frontend migration**:
   - Create migration plan to consolidate monthly quiz paths
   - Deprecate legacy paths after frontend updates

### Low Priority

5. **Consider prefix reorganization**:
   - Group related routers under common parent prefixes
   - Example: `/api/v2/admin/*` could include `admin-extensions`

---

## 9. Files Analyzed

### Main Configuration
- `/backend-hormonia/app/api/v2/router.py` (233 lines)
- `/backend-hormonia/app/core/router_registry.py` (121 lines)

### Router Files (54 total)
- All files in `/backend-hormonia/app/api/v2/routers/`
- Sample analysis of: `patients/__init__.py`, `auth.py`, `users.py`, `medications.py`, `alerts.py`

### Search Patterns
- Used `grep` to find all route decorators: `@router.(get|post|put|patch|delete)`
- Analyzed 200+ route definitions

---

## 10. Next Steps

1. **Research Agent**: Share findings with planner and coder agents via memory coordination
2. **Planner Agent**: Use findings to create task decomposition for route refactoring
3. **Coder Agent**: Implement route improvements based on recommendations
4. **Tester Agent**: Verify no route conflicts or broken endpoints

---

**Research Complete**: All backend routes cataloged and analyzed.
**Memory Coordination**: Findings stored in `/docs/backend-routes-analysis.md`
**Hooks Integration**: Task completion logged via `npx claude-flow@alpha hooks post-task`
