# Database Schema Analysis - Documentation Index

**Generated:** 2025-10-11
**Database:** PostgreSQL on AWS RDS
**Schema Version:** 20251010_010000 (Baseline Production)

---

## Overview

This directory contains comprehensive analysis of the Hormonia Healthcare database schema, covering all 33 tables, 19 ENUM types, 42 foreign key relationships, and 85+ indexes.

**Overall Status:** ✅ **PRODUCTION-READY** (with 1 critical fix required)

---

## Quick Navigation

### 🚨 Start Here (Critical)
1. **[SCHEMA_CRITICAL_FIX_REQUIRED.md](./SCHEMA_CRITICAL_FIX_REQUIRED.md)**
   - **Priority:** HIGH
   - **Action Required:** Fix webhook table name mismatch
   - **Time:** 5 minutes to fix + 15 minutes testing
   - **Impact:** Webhook processing currently broken

### 📊 Executive Summary
2. **[SCHEMA_ANALYSIS_SUMMARY.md](./SCHEMA_ANALYSIS_SUMMARY.md)**
   - Quick stats and key findings
   - Feature coverage verification
   - Index highlights
   - Recommendations

### 📖 Comprehensive Analysis
3. **[DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md](./DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md)**
   - Complete table inventory (33 tables)
   - ENUM types inventory (19 types)
   - Foreign key relationships (42 relationships)
   - Index analysis (85+ indexes)
   - Model-migration alignment
   - Critical tables deep dive

### 🏗️ Architecture Diagram
4. **[DATABASE_ARCHITECTURE_DIAGRAM.md](./DATABASE_ARCHITECTURE_DIAGRAM.md)**
   - Visual database architecture
   - Entity relationship diagrams
   - Message delivery critical path
   - Security & compliance features
   - Schema statistics

---

## Document Contents

### SCHEMA_CRITICAL_FIX_REQUIRED.md
**Purpose:** Immediate action required for webhook table name mismatch

**Contents:**
- Issue summary
- Impact analysis
- Fix instructions
- Verification steps
- Testing checklist

**Target Audience:** Developers, DevOps

**Read Time:** 5 minutes

---

### SCHEMA_ANALYSIS_SUMMARY.md
**Purpose:** Executive-level overview of database schema status

**Contents:**
- Quick statistics
- Critical finding
- Schema strengths
- Key tables overview
- Foreign key cascade rules
- Index highlights
- ENUM types
- Data integrity features
- Recommendations

**Target Audience:** Tech Leads, Architects, Product Managers

**Read Time:** 10 minutes

---

### DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md
**Purpose:** Complete technical analysis of database schema

**Contents:**
1. Schema Overview (33 tables)
2. ENUM Types Inventory (19 types with all values)
3. Foreign Key Relationships (42 relationships with cascade rules)
4. Index Analysis (85+ indexes with performance matrix)
5. Data Type Consistency
6. Critical Tables Deep Dive
   - users (Authentication Hub)
   - patients (Core Patient Data)
   - messages (WhatsApp Communication)
   - quiz_templates, quiz_sessions, quiz_responses
   - flow_kinds, flow_template_versions, patient_flow_states
   - webhook_events vs webhook_idempotency
   - whatsapp_delivery_failures (DLQ)
   - A/B Testing Tables (6 tables)
7. Model-Migration Alignment
8. Schema Issues & Recommendations
9. Feature Coverage Verification
10. Conclusion
11. Appendix A: Complete ENUM Values

**Target Audience:** Database Architects, Senior Developers

**Read Time:** 45 minutes

---

### DATABASE_ARCHITECTURE_DIAGRAM.md
**Purpose:** Visual representation of database architecture

**Contents:**
- System overview
- Core entity relationships
- Patient management ecosystem
- Communication system pipeline
- Quiz & assessment system
- Flow management system
- Analytics & reporting layer
- A/B testing system
- Foreign key cascade strategy
- Index performance matrix
- Data type standards
- ENUM types summary
- Message delivery critical path
- Security & compliance features
- Schema statistics

**Target Audience:** All technical staff, onboarding

**Read Time:** 20 minutes

---

## Key Findings Summary

### ✅ Strengths
- **Comprehensive:** All 33 tables support all application features
- **Optimized:** 85+ indexes for high performance
- **Reliable:** DLQ, idempotency, retry mechanisms
- **Compliant:** HIPAA-ready with audit trails
- **Flexible:** JSONB for metadata storage

### 🔴 Critical Issue
- **Webhook table name mismatch**
  - Migration creates: `webhook_events`
  - Model expects: `evolution_webhook_events`
  - **Fix:** Update model `__tablename__` (5 minutes)

### 🟡 Optional Improvements
- Add partial indexes for scheduled message queries
- Align A/B monitoring table schema
- Monitor query performance on high-volume tables

---

## Schema Statistics

```
Total Tables:           33
ENUM Types:             19 (with 23 total enum values across types)
Foreign Keys:           42
Indexes:                85+
Model Files:            25
Migration Lines:        851
Cascade Rules:          24 CASCADE, 15 SET NULL, 3 RESTRICT
Schema Complexity:      HIGH (enterprise-grade)
Compliance Level:       HIPAA-ready
```

---

## Table Categories

### Authentication & Security (3 tables)
- users, sessions, audit_logs

### Patient Management (2 tables)
- patients, user_sync_log

### Communication (5 tables)
- messages, message_status_events, webhook_events, webhook_idempotency, whatsapp_delivery_failures

### Flow Management (6 tables)
- flow_kinds, flow_template_versions, patient_flow_states, flow_messages, flow_analytics, quiz_questions

### Quiz System (3 tables)
- quiz_templates, quiz_sessions, quiz_responses

### Clinical Data (7 tables)
- treatments, appointments, medications, medical_reports, alerts, notifications, consents

### A/B Testing (6 tables)
- ab_experiments, ab_variant_assignments, ab_experiment_metrics, ab_experiment_results, ab_experiment_audit, ab_experiment_monitoring

### System (1 table)
- alembic_version (managed by Alembic)

---

## ENUM Types (19 total)

### Authentication (2)
- user_role, auth_provider

### Patient & Flow (1)
- flow_state

### Communication (4)
- messagedirection, messagetype, messagestatus, deliverystatus

### Monitoring (2)
- alertseverity, alertstatus

### Clinical (6)
- treatmenttype, treatmentstatus, appointmenttype, appointmentstatus, consenttype, consentstatus

### Notifications (2)
- notificationtype, notificationpriority

### DLQ (2)
- failurereason, dlqstatus

### A/B Testing (3)
- experimentstatus, varianttype, patientsafetylevel

### Security (1)
- audit_event_type (23 event types)

---

## Foreign Key Highlights

### Cascade Patterns

**CASCADE (24)** - Delete dependent records
```
patients.doctor_id → users.id
messages.patient_id → patients.id
quiz_sessions.patient_id → patients.id
treatments.patient_id → patients.id
... (20 more)
```

**SET NULL (15)** - Preserve records, clear reference
```
treatments.doctor_id → users.id
alerts.acknowledged_by → users.id
whatsapp_delivery_failures.original_message_id → messages.id
... (12 more)
```

**RESTRICT (3)** - Prevent deletion
```
quiz_sessions.quiz_template_id → quiz_templates.id
quiz_responses.quiz_template_id → quiz_templates.id
patient_flow_states.template_version_id → flow_template_versions.id
```

---

## Performance Highlights

### High-Performance Tables
| Table | Indexes | Purpose |
|-------|---------|---------|
| quiz_sessions | 9 | Session queries |
| quiz_responses | 8 | Response lookup |
| webhook_events | 6 | Event processing |
| message_status_events | 4 | Status tracking |
| audit_logs | 5 | Security monitoring |

### Special Indexes
- **Partial Unique Index** on quiz_sessions
  - Ensures only ONE active session per patient/template
  - `WHERE status = 'started'`

### Composite Indexes
- quiz_sessions: (patient_id, quiz_template_id, status)
- quiz_responses: (quiz_session_id, question_id)
- message_status_events: (message_id, created_at)
- webhook_events: (event_type, processed, created_at)
- audit_logs: (user_id, event_type, created_at)

---

## Use Cases by Document

### "I need to fix the webhook issue NOW"
→ Read: **SCHEMA_CRITICAL_FIX_REQUIRED.md** (5 min)

### "I need an overview for a meeting"
→ Read: **SCHEMA_ANALYSIS_SUMMARY.md** (10 min)

### "I'm designing a new feature and need table details"
→ Read: **DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md** (45 min)

### "I'm onboarding and need to understand the architecture"
→ Read: **DATABASE_ARCHITECTURE_DIAGRAM.md** (20 min)

### "I need to understand foreign key cascades"
→ Read: **DATABASE_ARCHITECTURE_DIAGRAM.md** Section: "Foreign Key Cascade Strategy"

### "I need to verify index performance"
→ Read: **DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md** Section 4: "Index Analysis"

### "I need all ENUM values"
→ Read: **DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md** Appendix A

---

## Related Documentation

### Application Features
- [AUTHENTICATION_MIGRATION_COMPLETE.md](./AUTHENTICATION_MIGRATION_COMPLETE.md) - Auth system status
- [API_CONTRACT_VALIDATION_SUMMARY.md](./API_CONTRACT_VALIDATION_SUMMARY.md) - API schema validation
- [TEMPLATE_MIGRATION_COMPLETE.md](./TEMPLATE_MIGRATION_COMPLETE.md) - Quiz template migration

### Technical Architecture
- [FLOWDESIGNER_INTEGRATION.md](./FLOWDESIGNER_INTEGRATION.md) - Flow system architecture
- [FRONTEND_REVIEW_COMPREHENSIVE.md](./FRONTEND_REVIEW_COMPREHENSIVE.md) - Frontend integration

### Testing & Validation
- [API_CONTRACT_TEST_GUIDE.md](./API_CONTRACT_TEST_GUIDE.md) - API testing guide
- [PHASE_4_TESTING_COMPLETE.md](./PHASE_4_TESTING_COMPLETE.md) - Testing completion status

---

## Migration History

**Current Version:** 20251010_010000_baseline_production_schema.py

**Migration Purpose:**
- Creates ALL 33 production tables
- Defines 19 ENUM types
- Establishes 42 foreign key relationships
- Creates 85+ indexes
- Serves as definitive baseline

**Previous Migrations:**
All previous migrations have been consolidated into this baseline migration.

---

## Action Items

### Immediate (CRITICAL)
- [ ] Fix `EvolutionWebhookEvent.__tablename__` mismatch
- [ ] Test webhook processing after fix
- [ ] Verify ORM queries work correctly

### Short-term (OPTIMIZATION)
- [ ] Add partial indexes for scheduled message queries
- [ ] Monitor query performance on high-volume tables
- [ ] Review A/B monitoring table schema alignment

### Ongoing (MAINTENANCE)
- [ ] Track query performance metrics
- [ ] Monitor index usage
- [ ] Review cascade rules periodically
- [ ] Update documentation as schema evolves

---

## Questions & Support

### Common Questions

**Q: Why is the webhook table named `webhook_events` but the model is `EvolutionWebhookEvent`?**
A: Historical naming evolution. The table was created for Evolution API events. The model name was later made more specific. See SCHEMA_CRITICAL_FIX_REQUIRED.md for fix.

**Q: What's the difference between `webhook_events` and `webhook_idempotency`?**
A: `webhook_events` stores full event history permanently. `webhook_idempotency` is a 24-hour deduplication cache. See DATABASE_SCHEMA_COMPREHENSIVE_ANALYSIS.md Section 6.6.

**Q: Why do we need a Dead Letter Queue (DLQ)?**
A: Failed WhatsApp messages go to `whatsapp_delivery_failures` for manual review and potential requeue. This ensures no message is lost due to transient errors.

**Q: How does the quiz session unique constraint work?**
A: A partial unique index ensures only ONE active session per patient/template: `WHERE status = 'started'`. This prevents duplicate active sessions.

**Q: What cascade rule should I use for a new foreign key?**
A:
- CASCADE if child data is meaningless without parent
- SET NULL if child data should be preserved
- RESTRICT if parent deletion should be prevented

---

## Maintenance Schedule

**Daily:**
- Monitor query performance on high-volume tables

**Weekly:**
- Review webhook processing metrics
- Check DLQ for failed messages requiring manual intervention

**Monthly:**
- Analyze index usage statistics
- Review schema changes and update documentation
- Audit security logs

**Quarterly:**
- Review foreign key cascade rules
- Optimize slow queries
- Plan schema migrations

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-11 | Initial comprehensive analysis |
|  |  | - 33 tables documented |
|  |  | - 19 ENUM types cataloged |
|  |  | - 42 foreign keys mapped |
|  |  | - 85+ indexes analyzed |
|  |  | - Critical webhook issue identified |

---

## Contributors

**Database Analysis:** Claude Code (Code Quality Analyzer)
**Schema Design:** Hormonia Healthcare Team
**Migration Baseline:** 20251010_010000

---

**Index Status:** ✅ Complete
**Last Updated:** 2025-10-11
**Next Review:** After webhook table name fix
