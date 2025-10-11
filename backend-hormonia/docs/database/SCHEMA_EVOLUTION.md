# Database Schema Evolution History

**Database**: AWS RDS PostgreSQL (Production)
**Current State**: alembic_version = NULL (No migrations applied)
**Analysis Date**: 2025-10-11
**Migration Files**: 69 total

---

## Migration Chain Overview

### Primary Chain (Healthy - 66 migrations)

```
001_initial [ROOT]
  → ... [62 migrations] ...
  → 039_fulltext_search
  → 3d3c49dd21c2 [MERGE: 3 branches]
  → 5479068ccdaa [CURRENT HEAD]
```

**Status**: ✅ Fully connected, healthy
**Coverage**: 96% of all migrations (66/69)

### Branch Evolution History

#### Branch 1: Template Versioning (Merged at 54ab19a5b23f)
```
014_add_cpf_migrate_metadata
  → add_performance_indexes
    → 015_add_template_versioning_tables
      → 016_backfill_template_versioning_data
        → 017_remove_legacy_templates
          → 54ab19a5b23f [MERGE INTO PRIMARY]
```

#### Branch 2: Performance Indexes (Merged at 3d3c49dd21c2)
```
add_performance_indexes
  → 20250929_200001 through 20250929_200010
    → 20250930_011500
      → add_firebase_fields
        → 20251006_add_user_sync_log_updated_at
          → 20251006_add_risk_assessment_indexes
            → 20251007_add_sending_status
              → 3d3c49dd21c2 [MERGE]
```

#### Branch 3: GIN Indexes (Orphaned)
```
add_performance_indexes
  → 20251009_210800_add_gin_indexes_for_search
    → 20251009_225600_add_quiz_session_to_alerts [ORPHAN]
```
**Status**: ⚠️ Orphaned - needs merge into primary chain

#### Branch 4: Webhook Chain (BROKEN)
```
[BROKEN ROOT] 20251009_230000_add_whatsapp_delivery_failures
  → 20251009_235500_add_webhook_idempotency
    → 20251009_235900_add_delivery_status
      → 20251010_000000_add_unique_quiz_session_constraint [ORPHAN]
```
**Status**: ❌ BROKEN - revision parsing failed

---

## Historical Schema Changes

### Phase 1: Core Foundation (001-010)
**Period**: Legacy development
**Focus**: Basic clinic management system

**Tables Created**:
- `users` - User authentication and profiles
- `patients` - Patient demographics and medical IDs
- `messages` - WhatsApp message management
- `alerts` - Clinical alerts and notifications
- `medical_reports` - Patient medical reports
- `flow_states` - Conversation flow management
- `quiz_templates` - Quiz and assessment templates
- `quiz_responses` - Patient quiz responses
- `quiz_sessions` - Quiz session tracking

**Key Migrations**:
- `001_initial_migration.py` - Database foundation
- `002_quiz_metadata.py` - Quiz system enhancements
- `003_add_quiz_constraints.py` - Data integrity (v1)
- `006_audit_log.py` - Audit logging system

### Phase 2: System Enhancement (011-020)
**Period**: Mid-development
**Focus**: Advanced features and integrations

**Major Additions**:
- `audit_log_entries` - Comprehensive audit trail
- `flow_kinds` - Flow categorization system
- `flow_template_versions` - Template versioning
- `message_status_events` - Message delivery tracking
- `webhook_events` - Webhook processing (with schema issues)

**Key Migrations**:
- `015_add_template_versioning_tables.py` - Template management
- `018_message_status_events.py` - Message tracking
- `019_webhook_events.py` - Webhook integration (problematic)

### Phase 3: Performance Optimization (021-039)
**Period**: Performance-focused development
**Focus**: Indexes, constraints, and optimization

**Optimizations**:
- Full-text search indexes on multiple tables
- Performance indexes for common queries
- GIN indexes for JSON data
- Constraint optimizations
- Query performance improvements

**Key Migrations**:
- `020_message_status_indexes.py` - Message performance
- `021_webhook_events_indexes.py` - Webhook performance
- `039_add_fulltext_search_indexes.py` - Search optimization

### Phase 4: Feature Expansion (2024-2025)
**Period**: Recent development
**Focus**: A/B testing, advanced features

**New Systems**:
- A/B Testing Framework (migrations 022-028)
  - `ab_experiments` - Experiment definitions
  - `ab_variant_assignments` - User variant tracking
  - `ab_experiment_metrics` - Performance metrics
  - `ab_experiment_results` - Result analysis
  - `ab_experiment_audit` - Experiment audit trail
  - `ab_experiment_monitoring` - Real-time monitoring
- Quiz Questions Library (`quiz_questions`)
- WhatsApp Delivery Failure Tracking
- Webhook Idempotency System

### Phase 5: Recent Additions (October 2025)
**Period**: Current development
**Focus**: Reliability and monitoring
**Status**: ⚠️ Contains broken migrations

**Recent Features**:
- `whatsapp_delivery_failures` - WhatsApp error tracking
- `webhook_idempotency` - Duplicate webhook prevention
- Enhanced quiz session constraints
- GIN indexes for improved search performance

---

## Production Database Status

### Table Status Matrix

#### ✅ Core Tables (In Migration + Production - 14 tables)
| Table | Migration | Production | Schema Match |
|-------|-----------|------------|-------------|
| users | 001_initial | ✅ | 🟢 Perfect |
| patients | 001_initial | ✅ | 🟢 Perfect |
| messages | 001_initial | ✅ | 🟢 Perfect |
| alerts | 001_initial | ✅ | 🟢 Perfect |
| medical_reports | 001_initial | ✅ | 🟢 Perfect |
| flow_states | 001_initial | ✅ | 🟢 Perfect |
| quiz_templates | 001_initial | ✅ | 🟢 Perfect |
| quiz_responses | 001_initial | ✅ | 🟢 Perfect |
| quiz_sessions | 002 | ✅ | 🟢 Perfect |
| audit_log_entries | 006 | ✅ | 🟢 Perfect |
| flow_kinds | 015 | ✅ | 🟢 Perfect |
| flow_template_versions | 015 | ✅ | 🟢 Perfect |
| message_status_events | 018 | ✅ | 🟢 Perfect |
| webhook_events | 019 | ✅ | 🟡 47% match |

#### ❌ Missing Tables (In Migration, Not in Production - 6 tables)
| Table | Migration | Impact | Reason |
|-------|-----------|--------|--------|
| ab_experiments | 022 | A/B testing disabled | Migration not applied |
| ab_variant_assignments | 023 | A/B testing disabled | Migration not applied |
| ab_experiment_metrics | 024 | A/B testing disabled | Migration not applied |
| ab_experiment_results | 025 | A/B testing disabled | Migration not applied |
| ab_experiment_audit | 026 | A/B testing disabled | Migration not applied |
| ab_experiment_monitoring | 027 | A/B testing disabled | Migration not applied |
| quiz_questions | 029 | Quiz library unavailable | Migration not applied |
| whatsapp_delivery_failures | 20251009_230000 | No failure tracking | Broken migration |
| webhook_idempotency | 20251009_235500 | Duplicate webhooks possible | Broken migration |

#### ➕ Extra Tables (In Production, Not in Migration - 13 tables)
| Table | Purpose | Created By |
|-------|---------|------------|
| admin_users | Admin authentication | Manual SQL |
| admin_roles | Role-based access control | Manual SQL |
| admin_permissions | Permission system | Manual SQL |
| admin_role_permissions | Role-permission mapping | Manual SQL |
| admin_user_permissions | User-permission overrides | Manual SQL |
| admin_sessions | Admin session tracking | Manual SQL |
| admin_security_events | Security audit log | Manual SQL |
| admin_ip_whitelist | IP access control | Manual SQL |
| admin_ip_blacklist | IP blocking | Manual SQL |
| admin_audit_log | Admin action audit | Manual SQL |
| flow_template_categories | Flow categorization | Manual SQL |
| flow_template_shares | Template sharing | Manual SQL |
| flow_template_stats | Template analytics | Manual SQL |

---

## Schema Mismatch Analysis

### webhook_events Table Discrepancy

**Migration 019 Expected Schema**:
```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY,
    event_type webhook_event_type,  -- ENUM
    webhook_id VARCHAR(255),
    raw_payload JSONB,
    related_message_id UUID REFERENCES messages(id),
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Production Reality**:
```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY,
    event_type VARCHAR,  -- NO ENUM
    payload JSONB,  -- WRONG NAME
    related_message_id UUID,
    created_at TIMESTAMP WITH TIME ZONE,
    -- Extra columns:
    max_retries INTEGER,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    error_stack_trace TEXT,
    related_patient_id UUID,
    event_hash VARCHAR,
    is_duplicate BOOLEAN,
    original_event_id UUID
);
```

**Match Score**: 47% (8/17 columns match)
**Impact**: Webhook processing works but with custom schema

---

## Migration Statistics

### By Time Period
- **Legacy (001-039)**: 39 migrations - Core system foundation
- **2024**: 1 migration - Quiz session metadata
- **2025-09**: 10 migrations - September performance work
- **2025-10**: 12 migrations - October feature additions
- **Other**: 7 migrations - Merge and descriptive migrations

### By Purpose Category
- **Schema creation**: 15 migrations (tables, columns)
- **Indexes**: 24 migrations (performance optimization)
- **Constraints**: 8 migrations (data integrity)
- **Data migrations**: 5 migrations (backfills, transformations)
- **Fixes**: 13 migrations (bugs, corrections)
- **Merges**: 2 migrations (branch consolidation)
- **Other**: 2 migrations (triggers, functions)

### By Complexity
- **Simple** (< 50 lines): 18 migrations
- **Medium** (50-100 lines): 32 migrations
- **Complex** (> 100 lines): 19 migrations

---

## Historical Issues & Resolutions

### Resolved Issues
1. **Multiple Template Systems** (2024)
   - **Problem**: Conflicting template management approaches
   - **Resolution**: Template versioning system (migrations 015-017)
   - **Status**: ✅ Resolved

2. **Performance Degradation** (September 2025)
   - **Problem**: Slow queries on large datasets
   - **Resolution**: Comprehensive indexing strategy (migrations 20250929_*)
   - **Status**: ✅ Resolved

3. **Firebase Integration** (September 2025)
   - **Problem**: Firebase field synchronization issues
   - **Resolution**: Add firebase fields migration
   - **Status**: ✅ Resolved

### Current Issues (Unresolved)
1. **Broken Migration Chain** (October 2025)
   - **Problem**: Type hints break Alembic parsing
   - **Affected**: 2 recent webhook migrations
   - **Status**: ❌ Requires immediate fix

2. **Production Alignment** (October 2025)
   - **Problem**: Production schema diverged from migrations
   - **Impact**: 13 tables not in migration system
   - **Status**: ❌ Requires alignment strategy

3. **Orphaned Migration Branches** (October 2025)
   - **Problem**: 3 separate root migrations
   - **Impact**: Unpredictable migration order
   - **Status**: ❌ Requires merge migrations

---

## Future Schema Considerations

### Planned Enhancements
1. **Field-level Encryption** - PII protection for LGPD compliance
2. **Row Level Security Policies** - Fine-grained access control
3. **Audit Trail Enhancement** - More detailed tracking
4. **Performance Monitoring Tables** - System metrics storage
5. **Integration Tables** - Third-party service connections

### Technical Debt
1. **Legacy Migration Consolidation** - Reduce 39 old migrations to 1
2. **Naming Standardization** - Enforce date-based naming
3. **Documentation Generation** - Auto-generate from migration comments
4. **Testing Automation** - Automated migration testing pipeline

---

## Schema Health Metrics

| Category | Score | Explanation |
|----------|-------|-------------|
| **Chain Integrity** | 6/10 | Main chain healthy, but 2 broken roots |
| **Organization** | 7/10 | Clear structure, some orphans |
| **Naming Consistency** | 6/10 | Multiple patterns, moving to date-based |
| **Documentation** | 4/10 | Comments in files, no comprehensive docs |
| **Testability** | 8/10 | All reversible, good downgrade() functions |
| **Production Alignment** | 4/10 | 13 extra tables, 6 missing tables |
| **Overall** | 5.8/10 | Good foundation, needs significant cleanup |

---

## Recommendations

### Immediate (This Week)
1. Fix type hints in 2 broken migrations
2. Reconnect orphaned migration chains
3. Test migration sequence in development
4. Create production alignment strategy

### Short-term (Next Month)
1. Implement production database alignment
2. Create migrations for manually-created tables
3. Establish migration testing pipeline
4. Document current schema state

### Long-term (Next Quarter)
1. Consolidate legacy migrations (if possible)
2. Implement automated schema validation
3. Create comprehensive migration documentation
4. Establish schema change governance

---

**Document Version**: 1.0
**Last Updated**: 2025-10-11
**Next Review**: 2025-11-11
**Status**: 🔴 Critical issues require immediate attention
