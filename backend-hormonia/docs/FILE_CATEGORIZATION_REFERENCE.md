# File Categorization Reference
## Complete Mapping of 88 Documentation Files

Quick lookup table for where each file belongs in the new structure.

---

## API Documentation (11 files)

| File | New Location | Type |
|------|-------------|------|
| `api/API.md` | `api/OVERVIEW.md` | Core API |
| `api/PHYSICIAN_RISK_ASSESSMENT_ENDPOINT.md` | `api/v1/physicians.md` | Endpoint spec |
| `QUIZ_PUBLIC_API.md` | `api/v1/quiz.md` | Endpoint spec |
| `upload_api_guide.md` | `api/upload/UPLOAD_API_GUIDE.md` | Upload guide |
| `upload_security.md` | `api/upload/UPLOAD_SECURITY.md` | Upload security |
| `IDEMPOTENCY.md` | `api/webhooks/IDEMPOTENCY.md` | Webhook pattern |
| `WEBHOOK_IDEMPOTENCY.md` | `api/webhooks/IDEMPOTENCY.md` | Webhook pattern |
| `WEBHOOK_SECURITY.md` | `api/webhooks/WEBHOOK_SECURITY.md` | Webhook security |
| `WEBHOOK_ENDPOINT_FIX.md` | `api/webhooks/WEBHOOK_GUIDE.md` | Webhook guide |
| `WEBHOOK_IDEMPOTENCY_QUICK_START.md` | `api/webhooks/WEBHOOK_GUIDE.md` | Webhook guide |
| `RATE_LIMITING.md` | `api/RATE_LIMITING.md` | API policy |

---

## Architecture & Design (13 files)

| File | New Location | Type |
|------|-------------|------|
| `architecture/DOMAIN_ARCHITECTURE.md` | `architecture/DOMAIN_ARCHITECTURE.md` | Keep as-is |
| `architecture/FLOW_VALIDATION.md` | `architecture/FLOW_VALIDATION.md` | Keep as-is |
| `architecture/QUIZ_CONCURRENCY.md` | `architecture/COMPONENTS/QUIZ_ENGINE.md` | Component |
| `database/DATABASE_OVERVIEW.md` | `architecture/DATABASE/SCHEMA.md` | Schema |
| `database/SCHEMA_REFERENCE.md` | `architecture/DATABASE/SCHEMA.md` | Schema |
| `database/DATA_FLOW_GUIDE.md` | `architecture/DATA_FLOW.md` | Data flow |
| `database/PERFORMANCE_GUIDE.md` | `architecture/DATABASE/PERFORMANCE.md` | Database perf |
| `database/FASE5_DATABASE_ANALYSIS.md` | `archive/other/FASE5_DATABASE_ANALYSIS.md` | Historical |
| `database/PATIENT_FLOW_COMPLETE_ANALYSIS.md` | `archive/other/PATIENT_FLOW_COMPLETE_ANALYSIS.md` | Historical |
| `i18n-architecture.md` | `architecture/INTERNATIONALIZATION.md` | i18n design |
| `QUERY_OPTIMIZATION.md` | `architecture/PATTERNS/QUERY_PATTERNS.md` | Query patterns |
| `QUERY_CACHE_IMPLEMENTATION.md` | `architecture/COMPONENTS/CACHING.md` | Caching |
| `ERROR_HANDLING_INTEGRATION_SUMMARY.md` | `archive/implementation-details/ERROR_HANDLING_INTEGRATION_SUMMARY.md` | Historical |

---

## Database & ORM (8 files)

| File | New Location | Type |
|------|-------------|------|
| `EAGER_LOADING_IMPLEMENTATION_SUMMARY.md` | `archive/implementation-details/EAGER_LOADING_IMPLEMENTATION_SUMMARY.md` | Historical |
| `EAGER_LOADING_QUICK_REFERENCE.md` | `architecture/DATABASE/EAGER_LOADING.md` | Reference |
| `GIN_INDEX_MIGRATION_GUIDE.md` | `guides/database/DATA_MIGRATION_GUIDE.md` | Migration |
| `GIN_INDEXES_IMPLEMENTATION_SUMMARY.md` | `archive/implementation-details/GIN_INDEXES_IMPLEMENTATION_SUMMARY.md` | Historical |
| `GIN_INDEXES_QUICK_REFERENCE.md` | `architecture/DATABASE/INDEXING_STRATEGY.md` | Reference |
| `QUERY_OPTIMIZATION.md` | `architecture/PATTERNS/QUERY_PATTERNS.md` | Patterns |
| `QUERY_CACHE_IMPLEMENTATION.md` | `archive/implementation-details/QUERY_CACHE_IMPLEMENTATION.md` | Historical |
| `SPRINT_1_EAGER_LOADING_IMPLEMENTATION.md` | `archive/implementation-details/SPRINT_1_EAGER_LOADING_IMPLEMENTATION.md` | Historical |

---

## Operations & Deployment (8 files)

| File | New Location | Type |
|------|-------------|------|
| `DEPLOYMENT_CONFIGURATION.md` | `operations/deployment/DEPLOYMENT_GUIDE.md` | Deployment |
| `PRODUCTION_MONITORING_CHECKLIST.md` | `operations/PRODUCTION_CHECKLIST.md` | Checklist |
| `PRODUCTION_READINESS_FINAL.md` | `operations/PRODUCTION_CHECKLIST.md` | Checklist |
| `MONITORING.md` | `operations/monitoring/MONITORING_GUIDE.md` | Monitoring |
| `SECURITY_HEADERS.md` | `operations/security/SECURITY_HEADERS.md` | Security |
| `SECURITY_HEADERS_SUMMARY.md` | `operations/security/SECURITY_HEADERS.md` | Security |
| `SYSTEM_CONFIGURATION_ANALYSIS.md` | `guides/deployment/DEPLOYMENT_GUIDE.md` | Deployment |
| `UPGRADE_SUMMARY.md` | `archive/other/UPGRADE_SUMMARY.md` | Historical |

---

## Guides & Quick Starts (5 files)

| File | New Location | Type |
|------|-------------|------|
| `PATIENT_ONBOARDING_CONFIGURATION.md` | `guides/GETTING_STARTED.md` | Getting started |
| `PYTHON_313_UPGRADE.md` | `reference/PYTHON_313_MIGRATION.md` | Reference |
| `QUICK_START_MIGRATIONS.md` | `guides/database/MIGRATIONS_QUICKSTART.md` | Quick start |
| `CONFIG_ENDPOINT.md` | `reference/CONFIG_SCHEMA.md` | Reference |
| `TROUBLESHOOTING_WELCOME_MESSAGE.md` | `guides/troubleshooting/COMMON_ISSUES.md` | Troubleshooting |

---

## Migration Reports (13 files) → Archive

| File | New Location | Type |
|------|-------------|------|
| `CONSOLIDATION_EXECUTIVE_SUMMARY.md` | `archive/migration-reports/CONSOLIDATION_EXECUTIVE_SUMMARY.md` | Report |
| `analytics-migration-guide.md` | `archive/migration-reports/analytics-migration-guide.md` | Report |
| `analytics-refactoring-report.md` | `archive/migration-reports/analytics-refactoring-report.md` | Report |
| `dashboard-v2-migration.md` | `archive/migration-reports/dashboard-v2-migration.md` | Report |
| `DASHBOARD_SCHEMA_FIXES_SUMMARY.md` | `archive/bug-fixes/DASHBOARD_SCHEMA_FIXES_SUMMARY.md` | Bug fix |
| `enhanced-messages-v2-migration-report.md` | `archive/migration-reports/enhanced-messages-v2-migration-report.md` | Report |
| `ENHANCED_MONITORING_V2_MIGRATION_REPORT.md` | `archive/migration-reports/ENHANCED_MONITORING_V2_MIGRATION_REPORT.md` | Report |
| `LOCALIZATION_V2_MIGRATION_COMPLETE.md` | `archive/migration-reports/LOCALIZATION_V2_MIGRATION_COMPLETE.md` | Report |
| `MIGRATION_AND_VALIDATION_SUMMARY.md` | `archive/migration-reports/MIGRATION_AND_VALIDATION_SUMMARY.md` | Report |
| `PHYSICIAN_MANAGEMENT_V2_MIGRATION.md` | `archive/migration-reports/PHYSICIAN_MANAGEMENT_V2_MIGRATION.md` | Report |
| `V2_TEMPLATES_MIGRATION_REPORT.md` | `archive/migration-reports/V2_TEMPLATES_MIGRATION_REPORT.md` | Report |
| `v2-platform-sync-migration.md` | `archive/migration-reports/v2-platform-sync-migration.md` | Report |
| `api/v2/TASKS_MIGRATION.md` | `archive/migration-reports/api-v2-TASKS_MIGRATION.md` | Report |

---

## Phase & Testing Reports (8 files) → Archive

| File | New Location | Type |
|------|-------------|------|
| `QW-020-PHASE4-COMPLETE.md` | `archive/phase-reports/QW-020-PHASE4-COMPLETE.md` | Phase |
| `QW-020-PHASE4-SESSION-SUMMARY.md` | `archive/phase-reports/QW-020-PHASE4-SESSION-SUMMARY.md` | Phase |
| `QW-020-PHASE4-SESSION2-SUMMARY.md` | `archive/phase-reports/QW-020-PHASE4-SESSION2-SUMMARY.md` | Phase |
| `QW-020-PHASE4-SESSION3-SUMMARY.md` | `archive/phase-reports/QW-020-PHASE4-SESSION3-SUMMARY.md` | Phase |
| `QW-020-PHASE4-TESTING-PROGRESS.md` | `archive/phase-reports/QW-020-PHASE4-TESTING-PROGRESS.md` | Phase |
| `QW-020-PHASE5-DAY1-PROGRESS.md` | `archive/phase-reports/QW-020-PHASE5-DAY1-PROGRESS.md` | Phase |
| `QW-020-TESTING-PLAN.md` | `archive/phase-reports/QW-020-TESTING-PLAN.md` | Testing |
| `QW-020-TESTING-STATUS.md` | `archive/phase-reports/QW-020-TESTING-STATUS.md` | Testing |

---

## Implementation & Feature Details (7 files) → Archive

| File | New Location | Type |
|------|-------------|------|
| `EAGER_LOADING_IMPLEMENTATION_SUMMARY.md` | `archive/implementation-details/EAGER_LOADING_IMPLEMENTATION_SUMMARY.md` | Implementation |
| `ERROR_HANDLING_INTEGRATION_SUMMARY.md` | `archive/implementation-details/ERROR_HANDLING_INTEGRATION_SUMMARY.md` | Implementation |
| `GIN_INDEXES_IMPLEMENTATION_SUMMARY.md` | `archive/implementation-details/GIN_INDEXES_IMPLEMENTATION_SUMMARY.md` | Implementation |
| `QUIZ_ALERT_EVALUATION_IMPLEMENTATION.md` | `archive/implementation-details/QUIZ_ALERT_EVALUATION_IMPLEMENTATION.md` | Feature |
| `SPRINT_1_EAGER_LOADING_IMPLEMENTATION.md` | `archive/implementation-details/SPRINT_1_EAGER_LOADING_IMPLEMENTATION.md` | Sprint |
| `STAMP_PRODUCTION_DB_IMPLEMENTATION.md` | `archive/implementation-details/STAMP_PRODUCTION_DB_IMPLEMENTATION.md` | Implementation |
| `IMPLEMENTATION_PHYSICIAN_RISK_ASSESSMENT.md` | `archive/implementation-details/IMPLEMENTATION_PHYSICIAN_RISK_ASSESSMENT.md` | Feature |

---

## Quick References (6 files) → Archive

| File | New Location | Type |
|------|-------------|------|
| `EAGER_LOADING_QUICK_REFERENCE.md` | `archive/quick-references/EAGER_LOADING_QUICK_REFERENCE.md` | Quick ref |
| `GIN_INDEXES_QUICK_REFERENCE.md` | `archive/quick-references/GIN_INDEXES_QUICK_REFERENCE.md` | Quick ref |
| `MIGRATION_QUICK_REFERENCE.md` | `archive/quick-references/MIGRATION_QUICK_REFERENCE.md` | Quick ref |
| `QUIZ_ALERT_QUICK_REFERENCE.md` | `archive/quick-references/QUIZ_ALERT_QUICK_REFERENCE.md` | Quick ref |
| `WEBHOOK_IDEMPOTENCY_QUICK_START.md` | `archive/quick-references/WEBHOOK_IDEMPOTENCY_QUICK_START.md` | Quick ref |
| `QUICK_START_PKG_RESOURCES_FIX.md` | `archive/quick-references/QUICK_START_PKG_RESOURCES_FIX.md` | Quick ref |

---

## Bug Fixes & Refactoring (12 files) → Archive

| File | New Location | Type |
|------|-------------|------|
| `DASHBOARD_SCHEMA_FIXES_SUMMARY.md` | `archive/bug-fixes/DASHBOARD_SCHEMA_FIXES_SUMMARY.md` | Bug fix |
| `DELIVERY_STATUS_FIX.md` | `archive/bug-fixes/DELIVERY_STATUS_FIX.md` | Bug fix |
| `PATIENTS_REDIRECT_FIX.md` | `archive/bug-fixes/PATIENTS_REDIRECT_FIX.md` | Bug fix |
| `PKG_RESOURCES_FIX.md` | `archive/bug-fixes/PKG_RESOURCES_FIX.md` | Bug fix |
| `QUIZ_SESSION_ID_FIX.md` | `archive/bug-fixes/QUIZ_SESSION_ID_FIX.md` | Bug fix |
| `REFACTORING_DUPLICATE_INITIALIZATIONS.md` | `archive/bug-fixes/REFACTORING_DUPLICATE_INITIALIZATIONS.md` | Refactoring |
| `REMAINING_ROLE_FIXES_SUMMARY.md` | `archive/bug-fixes/REMAINING_ROLE_FIXES_SUMMARY.md` | Bug fix |
| `SUPABASE_REMOVAL_FIX.md` | `archive/bug-fixes/SUPABASE_REMOVAL_FIX.md` | Bug fix |
| `TRAILING_SLASH_REDIRECT_FIX.md` | `archive/bug-fixes/TRAILING_SLASH_REDIRECT_FIX.md` | Bug fix |
| `VALIDATION_RULE_SCHEMA_FIX.md` | `archive/bug-fixes/VALIDATION_RULE_SCHEMA_FIX.md` | Bug fix |
| `WEBHOOK_ENDPOINT_FIX.md` | `archive/bug-fixes/WEBHOOK_ENDPOINT_FIX.md` | Bug fix |
| `TROUBLESHOOTING_WELCOME_MESSAGE.md` | `archive/bug-fixes/TROUBLESHOOTING_WELCOME_MESSAGE.md` | Bug fix |

---

## Other/Miscellaneous (6 files) → Archive

| File | New Location | Type |
|------|-------------|------|
| `BACKEND_TABLE_USAGE_AUDIT.md` | `archive/other/BACKEND_TABLE_USAGE_AUDIT.md` | Audit |
| `alerts_v2_safety_security_report.md` | `archive/other/alerts_v2_safety_security_report.md` | Report |
| `CONFIG_ENDPOINT.md` | `reference/CONFIG_SCHEMA.md` | Reference |
| `RUNBOOK_QUIZ_METRICS.md` | `archive/other/RUNBOOK_QUIZ_METRICS.md` | Runbook |
| `MIGRATIONS.md` | `archive/other/MIGRATIONS.md` | Reference |
| `FINAL_VALIDATION_CHECKLIST.md` | `archive/other/FINAL_VALIDATION_CHECKLIST.md` | Checklist |

---

## Files Already in Subfolders (7 files) → Keep/Update

| File | Status | Action |
|------|--------|--------|
| `migrations/FINAL_VALIDATION_CHECKLIST.md` | OK | Keep in place |
| `migrations/MIGRATION_IMPACT_SUMMARY.md` | OK | Keep in place |
| `migrations/PHASE_3_SERVICES_CONSOLIDATION.md` | OK | Keep in place |
| `migrations/QUIZ_SERVICES_MIGRATION.md` | OK | Keep in place |
| `database/DATABASE_OVERVIEW.md` | Reorganize | Move to `architecture/DATABASE/` |
| `database/SCHEMA_REFERENCE.md` | Reorganize | Move to `architecture/DATABASE/` |
| `database/DATA_FLOW_GUIDE.md` | Reorganize | Move to `architecture/` |

---

## Summary Statistics

| Category | Count | Destination |
|----------|-------|-------------|
| API Docs | 11 | `api/` |
| Architecture/Design | 13 | `architecture/` |
| Database/ORM | 8 | `architecture/DATABASE/` + `archive/` |
| Operations/Deployment | 8 | `operations/` |
| Guides/Quick Starts | 5 | `guides/` |
| Migration Reports | 13 | `archive/migration-reports/` |
| Phase Reports | 8 | `archive/phase-reports/` |
| Implementation Details | 7 | `archive/implementation-details/` |
| Quick References | 6 | `archive/quick-references/` |
| Bug Fixes | 12 | `archive/bug-fixes/` |
| Other/Misc | 6 | `archive/other/` + `reference/` |
| **TOTAL** | **88** | **Organized into 6 categories** |

---

## Legend

- **New Location**: Where file should go in new structure
- **Type**: Category of documentation (Report, Quick ref, Pattern, etc.)
- **→ Archive**: Indicates historical/obsolete documentation
- **Keep as-is**: Already in appropriate location

---

**Note**: Some files may be consolidated during migration (e.g., multiple QUICK_REFERENCE files combined into single reference). This mapping shows recommended new locations.
