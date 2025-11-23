# Database Schema Extraction Report

**Task ID:** db-schema-extraction
**Date:** 2025-11-15
**Status:** ✅ COMPLETED
**Database:** PostgreSQL (AWS RDS)
**Working Directory:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`

---

## Executive Summary

Successfully extracted and documented the complete PostgreSQL database schema for the Hormonia Backend system. The extraction process connected to the production database and generated comprehensive documentation covering all tables, columns, relationships, indexes, triggers, and user-defined types.

### Key Achievements

✅ **Complete Schema Export:** All 47 tables fully documented
✅ **Relationship Mapping:** 57 foreign key relationships identified and mapped
✅ **Index Documentation:** 260 indexes catalogued (BTREE, GIN, UNIQUE, COMPOSITE)
✅ **Type Safety:** 14 user-defined enum types documented
✅ **Visual Diagrams:** Mermaid ER diagram generated
✅ **Analysis Tools:** Python scripts created for reusable extraction

---

## Deliverables

### Documentation Files (476 KB total)

Located in: `backend-hormonia/docs/database/`

| File | Size | Lines | Description |
|------|------|-------|-------------|
| `complete_schema.json` | 382 KB | 13,333 | Complete schema export with all metadata |
| `schema_analysis.json` | 43 KB | 1,703 | Relationship analysis and complexity metrics |
| `SCHEMA_DOCUMENTATION.md` | 12 KB | 331 | Human-readable comprehensive documentation |
| `EXTRACTION_SUMMARY.md` | 9.4 KB | - | Summary of findings and recommendations |
| `schema_diagram.mmd` | 3.7 KB | 48 | Mermaid ER diagram (GitHub/VS Code compatible) |
| `README.md` | 7.7 KB | - | Updated with new documentation links |

### Python Scripts

Located in: `backend-hormonia/scripts/`

| Script | Purpose |
|--------|---------|
| `extract_complete_schema.py` | Extract complete schema from PostgreSQL |
| `analyze_schema_relationships.py` | Analyze relationships and generate insights |

---

## Database Statistics

### Overview
- **Total Tables:** 47
- **Total Columns:** 594
- **Total Indexes:** 260
- **Foreign Key Relationships:** 57
- **Triggers:** 14 (automated timestamp updates)
- **User-Defined Types (Enums):** 14

### Core Tables (Most Referenced)

| Rank | Table | Referenced By | Domain |
|------|-------|---------------|--------|
| 1 | `patients` | 15 tables | Patients & Medical |
| 2 | `users` | 15 tables | System & Meta |
| 3 | `admin_users` | 9 tables | Admin & Security |
| 4 | `flow_template_versions` | 5 tables | Quiz & Flow |
| 5 | `quiz_templates` | 3 tables | Quiz & Flow |

### Most Complex Tables

| Rank | Table | Complexity | Columns | Indexes | FKs | Triggers |
|------|-------|------------|---------|---------|-----|----------|
| 1 | `messages` | 65 | 21 | 18 | 1 | 1 |
| 2 | `patients` | 56 | 18 | 15 | 1 | 1 |
| 3 | `admin_users` | 49 | 24 | 7 | 2 | 1 |
| 4 | `quiz_sessions` | 49 | 16 | 11 | 2 | 1 |
| 5 | `quiz_responses` | 46 | 16 | 8 | 3 | 1 |

**Complexity Formula:** `(columns × 1) + (indexes × 2) + (foreign_keys × 3) + (triggers × 5)`

---

## Domain Organization

### 1. Admin & Security (10 tables)
Complete RBAC system with audit trails, session management, and IP filtering.

**Key Tables:**
- `admin_users` (24 columns, 7 indexes)
- `admin_roles`, `admin_permissions`
- `admin_sessions`, `admin_audit_log`
- `admin_security_events`
- `admin_ip_whitelist`, `admin_ip_blacklist`

### 2. Patients & Medical (5 tables)
Core medical records and patient management.

**Key Tables:**
- `patients` (18 columns, 15 indexes) - **Referenced by 15 tables**
- `appointments`, `medical_reports`
- `patient_flow_states`, `patient_onboarding_saga`

### 3. Messaging & WhatsApp (8 tables)
Multi-channel messaging infrastructure.

**Key Tables:**
- `messages` (21 columns, 18 indexes) - **Most complex table**
- `whatsapp_messages`, `whatsapp_contacts`, `whatsapp_instances`
- `message_status_events`, `flow_messages`

**Note:** 3 WhatsApp tables are isolated (no foreign keys)

### 4. Quiz & Flow Engine (12 tables)
Flow orchestration and quiz management with versioning.

**Key Tables:**
- `flow_template_versions` - **Referenced by 5 tables**
- `quiz_templates` - **Referenced by 3 tables**
- `quiz_sessions`, `quiz_sessions_v2` (V2 migration in progress)
- `quiz_responses`, `flow_analytics`

### 5. Audit & Logging (6 tables)
Comprehensive audit trail for compliance.

**Key Tables:**
- `audit_logs` (15 columns, 9 indexes)
- `security_audit_log` (13 columns, 12 indexes)
- `audit_trail`, `audit_log_entries` (isolated)

**Note:** 3 separate audit systems suggest consolidation opportunity

### 6. System & Meta (6 tables)
User management, notifications, and system metadata.

**Key Tables:**
- `users` (17 columns, 9 indexes) - **Referenced by 15 tables**
- `user_profiles`, `notifications`
- `alerts`, `webhook_events`
- `alembic_version` (migration tracking)

---

## User-Defined Types (Enums)

### Critical Enums

1. **`saga_status`** (10 states)
   - `STARTED`, `STEP_1_PATIENT_CREATED`, `STEP_2_FIREBASE_USER_CREATED`, etc.
   - Used for SAGA orchestration pattern

2. **`message_type`** (14 types)
   - `text`, `button`, `list`, `media`, `location`
   - `quiz_intro`, `quiz_question`, `quiz_completion`
   - `monthly_quiz_link`, `monthly_quiz_reminder`, etc.

3. **`flow_state`** (6 states)
   - `onboarding`, `active`, `paused`, `completed`, `inactive`, `cancelled`

### Duplicates Identified

- `severity_type` / `alert_severity` (both have: low, medium, high, critical)
- `messagestatus` / `deliverystatus` / `message_status` (overlapping values)

**Recommendation:** Consolidate duplicate enums to reduce confusion

---

## Isolated Tables (No Foreign Keys)

9 tables have **no foreign key relationships**:

1. `alembic_version` - Migration tracking (expected)
2. `audit_log_entries` - Standalone audit entries
3. `audit_trail` - Legacy audit trail
4. `error_logs` - Error tracking
5. `flow_template_categories` - Template categorization
6. `webhook_events` - Webhook event log
7. `whatsapp_contacts` - WhatsApp contact registry
8. `whatsapp_instances` - WhatsApp instance config
9. `whatsapp_messages` - WhatsApp message archive

### Recommendations

**Integrate WhatsApp Tables:**
- Link `whatsapp_contacts` to `patients` or `users`
- Connect `whatsapp_messages` to `messages` table
- Reference `whatsapp_instances` from `users`

**Consolidate Audit Tables:**
- Merge `audit_trail` and `audit_log_entries` into `audit_logs`
- Add discriminator column for audit types
- Maintain single audit trail for simplicity

**Link Categorization:**
- Connect `flow_template_categories` to `flow_template_versions`
- Implement category hierarchy

---

## Index Strategy

### Index Distribution

| Type | Count | Purpose |
|------|-------|---------|
| BTREE | ~240 | Standard indexes (default) |
| GIN | ~15 | JSONB column indexing |
| UNIQUE | ~30 | Constraint enforcement |
| COMPOSITE | ~20 | Multi-column queries |

### Heavily Indexed Tables

1. **`messages`** - 18 indexes
   - Performance critical for messaging system
   - Multiple composite indexes for complex queries

2. **`patients`** - 15 indexes
   - Core table, frequent access patterns
   - GIN index on metadata JSONB column

3. **`security_audit_log`** - 12 indexes
   - Audit query performance
   - Time-based and user-based lookups

4. **`quiz_sessions`** - 11 indexes
   - Session management optimization
   - Patient and template lookups

---

## Triggers

### Automated Timestamp Updates

14 tables have `updated_at` triggers:
- `patients`, `users`, `admin_users`
- `messages`, `quiz_sessions`, `quiz_responses`
- `audit_logs`, `whatsapp_delivery_failures`
- And 6 more...

**Implementation:**
```sql
CREATE TRIGGER update_{table_name}_updated_at
BEFORE UPDATE ON {table_name}
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

This ensures accurate audit trails and data lineage tracking.

---

## Relationship Patterns

### Hub-and-Spoke Architecture

**Central Hubs:**
1. `patients` - 15 outgoing relationships
2. `users` - 15 outgoing relationships
3. `admin_users` - 9 outgoing relationships

**Spokes (Dependent Tables):**
- Medical: `appointments`, `medical_reports`, `patient_flow_states`
- Messaging: `messages`, `notifications`
- Quiz: `quiz_sessions`, `quiz_responses`
- Audit: `audit_logs`, `security_audit_log`

### Cascade Policies

**ON DELETE CASCADE (52%):**
- Used for dependent data that should be removed with parent
- Examples: `patient_flow_states`, `quiz_sessions`, `messages`

**ON DELETE SET NULL (15%):**
- Used for soft references that can survive parent deletion
- Examples: `audit_logs.user_id`, `whatsapp_delivery_failures.reviewed_by`

**ON DELETE NO ACTION (33%):**
- Used for critical references requiring explicit handling
- Examples: `patients.doctor_id`, `appointments.doctor_id`

---

## Performance Insights

### Query Optimization

**Indexed Patterns:**
- Patient lookups: `idx_patients_doctor_id`, `idx_patients_phone_number`
- Message queries: `idx_messages_patient_id`, `idx_messages_status`
- Quiz sessions: `idx_quiz_sessions_patient_id`, `idx_quiz_sessions_status`
- Time-based: Indexes on `created_at`, `updated_at`, `sent_at`

**GIN Indexes on JSONB:**
- `patients.metadata` (flexible patient data)
- `quiz_responses.response_value` (structured quiz answers)
- `messages.message_metadata` (message metadata)
- `admin_users.permissions_override` (custom permissions)

### Recommended Optimizations

1. **Partitioning Opportunities:**
   - `messages` table (21 columns, 18 indexes)
   - `audit_logs` (time-series data)
   - `quiz_sessions` (large volume)

2. **Archival Strategy:**
   - Move old `messages` to archive table
   - Compress historical `audit_logs`
   - Prune completed `quiz_sessions`

3. **Index Tuning:**
   - Review unused indexes with `pg_stat_user_indexes`
   - Add partial indexes for filtered queries
   - Consider covering indexes for hot queries

---

## Data Integrity

### Foreign Key Constraints

**57 total relationships** ensure referential integrity:
- Patient → Doctor (15 relationships)
- User relationships (15 relationships)
- Admin relationships (9 relationships)
- Flow/Quiz relationships (8 relationships)
- Message relationships (5 relationships)
- Other (5 relationships)

### Unique Constraints

**Composite Unique Constraints:**
- `patients`: Unique per doctor (phone_number, doctor_id)
- `quiz_sessions`: One active session per patient/template
- `admin_users`: Unique username

**Single-Column Unique:**
- Email addresses
- Phone numbers (global)
- Template names with versions

### Check Constraints

Limited use of CHECK constraints. Opportunities:
- Email format validation
- Phone number format validation
- Date range validation (start_date < end_date)
- Enum validation (though using PostgreSQL enums)

---

## Security & Compliance

### HIPAA Compliance Features

1. **Comprehensive Audit Trail:**
   - `security_audit_log` (12 indexes)
   - `admin_audit_log`
   - `audit_logs`

2. **Access Control:**
   - RBAC system (`admin_roles`, `admin_permissions`)
   - Session management (`admin_sessions`)
   - IP filtering (`admin_ip_whitelist`, `admin_ip_blacklist`)

3. **Data Protection:**
   - Encrypted fields support (noted in documentation)
   - JSONB for flexible metadata
   - Soft deletes with `deleted_at`

### Security Events

`admin_security_events` table tracks:
- Failed login attempts
- Permission changes
- Suspicious activities
- Security policy violations

### Audit Capabilities

**Three Levels of Auditing:**
1. **Application Level:** `audit_logs` (15 columns)
2. **Security Level:** `security_audit_log` (13 columns)
3. **Admin Level:** `admin_audit_log`

**What's Tracked:**
- User actions (who, what, when, where)
- Data changes (before/after values)
- API calls (method, path, IP address)
- System events (errors, warnings)

---

## Migration Status

### Completed Migrations

Database migrations tracked in `alembic_version` table:

- **001-005:** Initial schema setup
- **006:** Message priority support
- **007:** Quiz session indexes
- **008:** Flow execution indexes
- **009:** Patient unique constraints (composite keys)
- **010:** P0 performance indexes
- **011:** HIPAA audit trail enhancement
- **012:** Quiz response JSONB migration

### In-Progress Migrations

**V2 Quiz System:**
- `quiz_sessions_v2` created
- `quiz_template_versions_v2` created
- Migration from V1 to V2 ongoing

**Recommendation:** Complete V2 migration and deprecate V1 tables

---

## Recommendations

### Priority 1: Data Integrity

1. **Integrate Isolated Tables**
   - Add foreign keys to `whatsapp_*` tables
   - Link `webhook_events` to triggering entities
   - Connect `flow_template_categories` to templates

2. **Complete V2 Migration**
   - Finish quiz V2 migration
   - Deprecate V1 tables
   - Update application code

3. **Consolidate Audit Tables**
   - Merge 3 audit systems into one
   - Add discriminator column for types
   - Simplify audit queries

### Priority 2: Performance

1. **Partition Large Tables**
   - `messages` by date range
   - `audit_logs` by month
   - `quiz_sessions` by status

2. **Archival Strategy**
   - Archive old messages (>1 year)
   - Compress historical audits
   - Prune completed quiz sessions

3. **Index Optimization**
   - Review unused indexes
   - Add partial indexes for filtered queries
   - Consider covering indexes

### Priority 3: Type Safety

1. **Consolidate Duplicate Enums**
   - Merge `severity_type` and `alert_severity`
   - Consolidate message status enums
   - Update dependent code

2. **Add Missing Constraints**
   - Email format validation
   - Phone number format validation
   - Date range validation

---

## Usage Examples

### Querying the Schema

```python
import json

# Load complete schema
with open('backend-hormonia/docs/database/complete_schema.json') as f:
    schema = json.load(f)

# Get all columns for patients table
patients = schema['tables']['patients']
print(f"Patients table has {len(patients['columns'])} columns")

# Find all foreign keys to patients
for table, info in schema['tables'].items():
    for fk in info['foreign_keys']:
        if fk['referenced_table'] == 'patients':
            print(f"{table}.{fk['column']} -> patients.{fk['referenced_column']}")

# List all GIN indexes
for table, info in schema['tables'].items():
    for idx in info['indexes']:
        if idx['type'] == 'gin':
            print(f"GIN index: {table}.{idx['name']} on {idx['columns']}")
```

### Visualizing Relationships

```bash
# View Mermaid diagram in VS Code
code backend-hormonia/docs/database/schema_diagram.mmd

# Or open in browser
open https://mermaid.live/
# Paste contents of schema_diagram.mmd
```

---

## Next Steps

### Immediate Actions

1. **Review Findings:** Share this report with the development team
2. **Prioritize Work:** Decide on integration and consolidation priorities
3. **Plan Migrations:** Schedule V2 completion and table consolidation
4. **Update Documentation:** Keep schema docs in sync with changes

### Future Enhancements

1. **Automated Schema Monitoring:**
   - Set up schema change detection
   - Alert on unauthorized modifications
   - Track schema drift

2. **Performance Monitoring:**
   - Monitor query performance
   - Track index usage
   - Identify slow queries

3. **Documentation Integration:**
   - Add schema docs to API documentation
   - Generate ER diagrams automatically
   - Keep docs in sync with migrations

---

## Support & Maintenance

### Re-running Extraction

```bash
cd backend-hormonia

# Extract complete schema
python3 scripts/extract_complete_schema.py

# Analyze relationships
python3 scripts/analyze_schema_relationships.py
```

### Viewing Files

```bash
# Navigate to docs
cd docs/database

# View summary
cat EXTRACTION_SUMMARY.md

# View human-readable docs
cat SCHEMA_DOCUMENTATION.md

# Query JSON schema
python3 -c "import json; print(json.load(open('complete_schema.json'))['tables']['patients'])"
```

---

## Conclusion

The database schema extraction was **successfully completed**, delivering comprehensive documentation covering all 47 tables, 594 columns, 260 indexes, and 57 relationships. The generated documentation provides multiple formats for different use cases:

- **JSON files** for programmatic access
- **Markdown files** for human reading
- **Mermaid diagrams** for visual understanding
- **Python scripts** for future extractions

The analysis identified key architectural patterns, performance characteristics, and opportunities for optimization. The schema demonstrates a well-designed system with strong data integrity, comprehensive audit trails, and HIPAA-ready security features.

---

**Task Completed:** 2025-11-15
**Documentation Location:** `backend-hormonia/docs/database/`
**Scripts Location:** `backend-hormonia/scripts/`
**Total Files Created:** 5 documentation files + 2 Python scripts
**Total Size:** 476 KB

✅ **Mission Accomplished!**

---

## File Manifest

### Documentation Files

- `/backend-hormonia/docs/database/complete_schema.json` (382 KB)
- `/backend-hormonia/docs/database/schema_analysis.json` (43 KB)
- `/backend-hormonia/docs/database/SCHEMA_DOCUMENTATION.md` (12 KB)
- `/backend-hormonia/docs/database/EXTRACTION_SUMMARY.md` (9.4 KB)
- `/backend-hormonia/docs/database/schema_diagram.mmd` (3.7 KB)
- `/backend-hormonia/docs/database/README.md` (updated)

### Python Scripts

- `/backend-hormonia/scripts/extract_complete_schema.py`
- `/backend-hormonia/scripts/analyze_schema_relationships.py`

### This Report

- `/backend-hormonia/DATABASE_SCHEMA_EXTRACTION_REPORT.md`
