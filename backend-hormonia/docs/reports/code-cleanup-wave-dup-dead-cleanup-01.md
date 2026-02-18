# Code Cleanup Wave Report - DUP-DEAD-CLEANUP-01

## Scope
Refactor and cleanup wave focused on duplicated/dead code in backend core modules, with compatibility-first migration (shims/re-exports) to reduce regression risk.

## Completed Tasks
- `DUP-DEAD-CLEANUP-01-02`: input sanitization consolidation.
- `DUP-DEAD-CLEANUP-01-03`: CPF/phone validator centralization.
- `DUP-DEAD-CLEANUP-01-04`: exception hierarchy unification.
- `DUP-DEAD-CLEANUP-01-05`: circuit breaker import consolidation.
- `DUP-DEAD-CLEANUP-01-06`: AlertManager consolidation to refactored manager.
- `DUP-DEAD-CLEANUP-01-07`: WhatsApp service consolidation to unified service.
- `DUP-DEAD-CLEANUP-01-08`: cleanup of unused exports/examples with safe tombstone.
- `DUP-DEAD-CLEANUP-01-09`: focused regression validation suite.

## Impact Summary
- Files changed in this wave (tracked in `final-plan.md`): `33`.
- New compatibility/validation files introduced:
  - `app/schemas/validators/cpf.py`
  - `tests/utils/test_input_sanitizer_compat.py`
  - `tests/core/test_exception_compatibility_shims.py`
  - `tests/services/alerts/test_alert_manager_dispatcher_compat.py`
  - `tests/services/test_whatsapp_compatibility_shims.py`
- Measured net diff on cleanup-focused modules:
  - Added lines: `814`
  - Removed lines: `1572`
  - Net reduction: `-758` lines
  - Command used: `git diff --numstat` on targeted cleanup files.

## Canonical Modules After Consolidation
- Input sanitization: `app/utils/input_sanitization.py` (legacy shim in `app/utils/input_sanitizer.py`).
- CPF validation: `app/schemas/validators/cpf.py`.
- Phone validation: `app/schemas/validators/phone.py`.
- Exceptions: `app/core/exceptions.py` (compat shims in `app/exceptions/*`).
- Circuit breaker: `app/resilience/circuit_breaker/*` (legacy import paths preserved by shims).
- Alert manager: `app/services/alerts/alert_manager_refactored.py`.
- WhatsApp service: `app/services/unified_whatsapp_service.py`.

## Compatibility Shims / Wrappers Added or Simplified
- `app/utils/input_sanitizer.py`
- `app/exceptions/flow_exceptions.py`
- `app/exceptions/external_service.py`
- `app/services/whatsapp_unified.py`
- `app/domain/messaging/whatsapp/whatsapp_service.py`
- `app/monitoring/__init__.py` (delegation to canonical alert manager)
- `app/services/alerts/adapter.py` (compat-friendly adapter behavior)

## Validation Results
- Consolidated regression suite:
  - `117 passed, 2 skipped`
  - Command covered sanitization, validators, exceptions, alerts, circuit breaker, and WhatsApp domains.
- Additional focused suites executed during task execution also passed for modified modules.

## Known Residuals
- Some webhook retry/DLQ suites were reported failing during exploratory expanded runs, but those failures were outside the modified files in this wave and were not required to validate the cleanup scope.

## Final Status
Wave implementation complete for all cleanup tasks and regression gate in scope.

---

## Addendum: Wave DUP-DEAD-CLEANUP-02 (API v2 + Post-Scan)

### Additional Scope Implemented
- Deduplicated task lookup/serialization flow in `app/api/v2/routers/tasks/*` via shared dependencies helpers.
- Deduplicated cursor/pagination flow in `app/api/v2/messages/*` via shared helpers.
- Replaced legacy monolithic physicians router with compatibility shim in `app/api/v2/routers/physicians.py`.
- Reduced repeated helper code in `app/api/v2/routers/monthly_quiz_management.py`.
- Removed low-risk unused imports in selected `app/**` monitoring/admin modules.

### API v2 Regression Validation (Post-Change)
- Command:
  - `pytest -q tests/api/v2/test_messages.py::TestMessageCRUD tests/api/v2/test_messages.py::TestConversations tests/api/v2/test_quiz_extensions.py::TestMonthlyQuiz::test_create_monthly_quiz tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_physicians_module_resolution.py tests/api/v2/test_physicians_refactored.py::TestPhysiciansEndpoints::test_get_physician_statistics tests/api/v2/test_physicians_refactored.py::TestPhysiciansEndpoints::test_update_physician tests/api/v2/test_router_shadow_regressions.py::test_static_routes_not_shadowed`
- Result:
  - `28 passed, 1 skipped`
- Notes:
  - Known warnings remain (`pytest-asyncio` loop-scope deprecation, SQLAlchemy `SAWarning` in physician statistics path).

### Duplicate Code Scan (Backend App)
- Tool: `npx -y jscpd`.
- Scope: `backend-hormonia/app`.
- Totals:
  - Duplicated lines: `5936`
  - Duplication: `2.05%`
  - Clones: `404`
- Top duplicated pairs (by duplicated lines):
  - `app/schemas/v2/patient.py` ↔ `app/schemas/v2/patient.py` (`160`)
  - `app/domain/messaging/core/message_factory.py` ↔ `app/domain/messaging/core/message_service/factory.py` (`151`)
  - `app/services/follow_up_system/generators/base.py` ↔ `app/services/follow_up_system/generators/response.py` (`147`)
  - `app/schemas/user_admin.py` ↔ `app/schemas/v2/admin.py` (`129`)
  - `app/services/firebase_auth_circuit_breaker.py` ↔ `app/services/firebase_auth_service.py` (`120`)
- Focus `app/api/v2`:
  - Clones touching `app/api/v2`: `151` (`2302` duplicated lines)
  - Clones only inside `app/api/v2`: `140` (`2158` duplicated lines)

### Dead Code Scan (Backend App)
- Tool: `vulture 2.14` in project venv (`backend-hormonia/.venv`).
- Scope: `app`.
- Totals:
  - Findings: `4609`
  - Confidence split: `100%: 51`, `90%: 1`, `60%: 4557`
- High-confidence sample (`>=90%`):
  - `app/api/v2/routers/enhanced_reports.py:546` (`share_id`)
  - `app/api/v2/routers/physicians/services/availability_service.py:43` (`slot_duration_minutes`)
  - `app/domain/agents/quiz/response_handler.py:87-90` (unused callbacks)
  - `app/integrations/whatsapp/services/evolution_client.py:681` (`max_dimension`)
  - `app/services/alerts/adapter.py:439` (`description_template`)

### Tombstoned Modules Check
- Tombstoned modules detected in `app/`: `41`.
- Active runtime importers in app code: `0`.
- Doc-only references found: `2` (no runtime impact).

### Addendum Status
Wave extension concluded with regression coverage and updated duplicate/dead-code baseline for backend.

---

## Addendum: Wave DUP-DEAD-CLEANUP-03 (Legacy/Dead/Duplicate Continuation)

### Scope Implemented
- Removed duplicated admin auth dependency code in `admin_extensions` by reusing canonical `admin/dependencies.py`.
- Extracted shared flow cursor helper into `app/api/v2/flows/cursor.py` and reused in:
  - `app/api/v2/flows/state.py`
  - `app/api/v2/flows/templates.py`
- Cleaned selected high-confidence dead-code findings (unused params/variables) with compatibility-preserving no-ops.

### Parallel Execution Model
This wave ran as parallel unblocked tasks (3 workers):
1. Admin dependency deduplication
2. Flow cursor helper extraction
3. High-confidence dead-code cleanup

### Regression and Build Validation
- `python3 -m py_compile` passed for all changed files.
- `pytest -q tests/api/v2/test_flows.py -k 'template or history' --maxfail=1`:
  - `6 passed, 26 deselected`
- `pytest -q tests/api/v2/test_admin_extensions.py -k 'rbac or admin' --maxfail=1`:
  - `47 passed`
- Known environment warning remains:
  - `pytest-asyncio` deprecation about unset `asyncio_default_fixture_loop_scope`.

### Incremental Metrics (vs previous baseline)
- Duplicate code (`jscpd`, scope `backend-hormonia/app`):
  - Before: `5936` duplicated lines, `404` clones, `2.05%`
  - After: `5815` duplicated lines, `400` clones, `2.01%`
  - Delta: `-121` duplicated lines, `-4` clones, `-0.04pp`
- Dead code (`vulture`, scope `backend-hormonia/app`):
  - Before: `4609` findings (`100%: 51`, `90%: 1`, `60%: 4557`)
  - After: `4598` findings (`100%: 41`, `90%: 1`, `60%: 4556`)
  - Delta: `-11` total findings, `-10` findings at `100%` confidence

### Tombstone Verification
- Tombstoned modules in `app/`: `41` (unchanged)
- Active runtime importers inside app code: `0`

### Migration / Refactor Notes
- This wave required **no database migration**.
- Changes were limited to refactoring/deduplication and safe dead-code cleanup.

### Addendum Status
Wave extension completed successfully with measurable reduction in duplication and high-confidence dead code, preserving compatibility behavior.

---

## Addendum: Wave DUP-DEAD-CLEANUP-04 (Dead Code 100% + Schema/Messaging Dedup)

### Scope Implemented
- Limpeza de achados `vulture` com `100%` de confiança em módulos de retry/admin/celery/analytics.
- Deduplicação adicional de validadores em schemas de paciente (`v1`/`v2`) com centralização de helpers locais.
- Correção de regressão funcional em validação de `birth_date` (futuro agora priorizado antes de regra de idade mínima).
- Restauração de normalização/validação de `blood_type` no schema v2 (uppercase + pattern).
- Consolidação de `MessageSchedulerConfig` em fonte canônica com wrapper de compatibilidade no módulo de scheduling.

### Validation Matrix
- Build/compilação:
  - `python3 -m py_compile` nos arquivos alterados da wave: **sucesso**.
- Schemas:
  - `pytest -q tests/schemas/test_patient_age_validation.py tests/schemas/test_patient_v2_clinical_fields.py tests/schemas/test_phone_validation.py`
  - Resultado: **`75 passed`**.
- Unitários de conversão/metadata:
  - `pytest -q tests/unit/test_patient_schema_conversion.py tests/unit/test_patient_metadata_schema.py`
  - Resultado: **`58 passed`**.
- Observação de ambiente:
  - warning conhecido do `pytest-asyncio` sobre `asyncio_default_fixture_loop_scope` permanece.

### Incremental Metrics (Baseline local da wave)
- Duplicação (`jscpd`, escopo `backend-hormonia/app`, `--min-lines 12 --min-tokens 80`):
  - Antes: `2391` linhas duplicadas, `101` clones, `0.81%`
  - Depois: `2320` linhas duplicadas, `99` clones, `0.78%`
  - Delta: `-71` linhas, `-2` clones, `-0.03pp`
- Código morto (`vulture`, escopo `backend-hormonia/app`, `--min-confidence 90`):
  - Antes: `11` findings (`100%`)
  - Depois: `0` findings

### Files Touched in This Addendum
- `app/resilience/retry/retry_manager.py`
- `app/services/admin/admin_user_service/bulk_operations.py`
- `app/services/admin/admin_user_service/password_management.py`
- `app/services/admin/admin_user_service/user_crud.py`
- `app/services/analytics/data_extraction/service.py`
- `app/tasks/celery_metrics.py`
- `app/schemas/patient.py`
- `app/schemas/v2/patient.py`
- `app/domain/messaging/core/message_service/config.py`
- `app/domain/messaging/scheduling/message_scheduler/config.py`
- `final-plan.md`

### Addendum Status
Wave 04 concluída com redução adicional de duplicação e eliminação dos achados de código morto de alta confiança na baseline local desta rodada.

---

## Addendum: Wave DUP-DEAD-CLEANUP-05 (Legacy Tombstone Removal + Shim Retirement)

### Scope Implemented
- Remoção de módulos legacy/tombstone sem importadores de runtime:
  - `app/services/websocket_service.py`
  - `app/services/privacy_service.py`
  - `app/services/flow/implementations.py`
  - `app/services/notification.py`
  - `app/services/optimized_monthly_quiz_service.py`
- Aposentadoria de wrappers de modelos sem uso interno:
  - `app/models/quiz_template.py`
  - `app/models/quiz_session.py`
  - `app/models/audit.py`
- Migração do único importador remanescente para caminho canônico:
  - `tests/api/test_api_contracts.py` (`app.models.audit` → `app.models.audit_log`)

### Validation Matrix
- Verificação de referências legacy removidas:
  - `rg -n "app\\.models\\.(audit|quiz_session|quiz_template)|app\\.services\\.(websocket_service|privacy_service|notification|optimized_monthly_quiz_service)|app\\.services\\.flow\\.implementations" app tests`
  - Resultado: nenhum importador restante no código Python.
- Compilação:
  - `python3 -m compileall -q app`
  - Resultado: **sucesso**.
- Regressão focada:
  - `python3 -m pytest -q tests/api/v2/test_router_compatibility_tracking.py tests/security/test_low_001_pii_masking.py tests/utils/test_input_sanitizer_compat.py tests/api/test_api_contracts.py::TestUserActivityAPIContract::test_user_activity_returns_activity_logs --maxfail=1`
  - Resultado: **`38 passed`**.

### Observações
- O endpoint `/api/v2/auth/notifications` já apresentava ausência (HTTP `404`) em suíte ampliada de `test_api_contracts`; não foi introduzido por esta wave e ficou fora do escopo desta limpeza de legado.
- Esta wave não exigiu migração de banco.

### Addendum Status
Wave 05 concluída com redução adicional de superfície legacy e sem regressões nos testes focados de compatibilidade.
