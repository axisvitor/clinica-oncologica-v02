# Index Usage Analysis Report

**Date**: 2026-01-09  
**Database**: Hormonia Production  
**Context**: Post-migration analysis of 445 indexes with `idx_scan = 0`

---

## Executive Summary

After applying the FK and GIN index migrations, we identified 445 indexes with zero scans (`idx_scan = 0`). This report categorizes them and provides recommendations.

> [!NOTE]
> An index with `idx_scan = 0` doesn't necessarily mean it's unused. It could be:
> - Recently created (stats not yet accumulated)
> - Used for rare operations (admin-only, monthly reports)
> - Required for FK constraint enforcement (never "scanned" but essential)

---

## Index Categories

### Category 1: **KEEP** - FK Constraint Indexes

These indexes support foreign key relationships and are required for efficient `DELETE`/`UPDATE CASCADE` operations, even if they show zero scans.

| Index Pattern | Example Tables | Recommendation |
|---------------|----------------|----------------|
| `idx_*_patient_id` | messages, alerts, quiz_sessions | **Keep** |
| `idx_*_user_id` | audit_logs, sessions, uploads | **Keep** |
| `idx_*_doctor_id` | appointments, patients | **Keep** |
| `idx_*_flow_template_version_id` | flow_messages, flow_analytics | **Keep** |
| `idx_*_created_by` | flow_template_versions, admin_users | **Keep** |
| `idx_*_session_id` | admin_audit_log, admin_security_events | **Keep** |

**New indexes from migration `21f306d5c4b8`:**
- `idx_flow_template_versions_created_by`
- `idx_admin_users_created_by`
- `idx_admin_users_updated_by`
- `idx_admin_user_permissions_granted_by`
- `idx_admin_audit_log_session_id`
- `idx_admin_security_events_session_id`
- `idx_admin_ip_whitelist_added_by`
- `idx_admin_ip_blacklist_blocked_by`
- `idx_contacts_related_patient_id`
- `idx_contacts_related_user_id`
- `idx_whatsapp_delivery_failures_original_message_id`
- `idx_whatsapp_delivery_failures_reviewed_by`
- `idx_patient_summaries_generated_by`
- `idx_consents_witness_id`
- `idx_lgpd_data_access_requests_assigned_to_id`

> **Action**: No removal needed. These are essential for referential integrity.

---

### Category 2: **MONITOR** - Recently Created (Wait 30 Days)

GIN indexes from migration `4697ee3a60f4` were just created and need time to accumulate usage stats:

| Index | Table | Column |
|-------|-------|--------|
| `idx_messages_message_metadata_gin` | messages | message_metadata |
| `idx_patient_onboarding_saga_execution_log_gin` | patient_onboarding_saga | execution_log |
| `idx_patient_onboarding_saga_step_data_gin` | patient_onboarding_saga | step_data |
| `idx_patient_onboarding_saga_patient_data_gin` | patient_onboarding_saga | patient_data |
| `idx_patient_flow_states_flow_metadata_gin` | patient_flow_states | flow_metadata |
| `idx_patient_flow_states_step_data_gin` | patient_flow_states | step_data |
| `idx_flow_states_state_data_gin` | flow_states | state_data |

> **Action**: Re-evaluate after 2026-02-09 (30 days post-migration).

---

### Category 3: **REVIEW** - Potential Removal Candidates

After 30+ days of production usage, these patterns commonly indicate truly unused indexes:

| Pattern | Typical Cause | Before Removal |
|---------|---------------|----------------|
| Composite indexes with rarely-queried columns | Over-optimization | Verify no slow queries would result |
| Duplicate coverage (column indexed twice) | Schema evolution | Check if single-column index suffices |
| Indexes on low-cardinality columns | `is_active`, `status` | Postgres may ignore these anyway |

> **Action**: Generate query plan analysis before removing any index.

---

## Recommended Monitoring Query

Run this query monthly to track index usage trends:

```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 50;
```

---

## Next Steps

1. [x] Applied FK indexes migration
2. [x] Applied GIN JSONB indexes migration  
3. [ ] **30-day wait**: Re-run analysis on 2026-02-09
4. [ ] **Identify removals**: After 30 days, indexes still at 0 scans can be reviewed
5. [ ] **Test removals**: Use `EXPLAIN ANALYZE` on production queries before dropping

---

## Reference: Full Index List

For the complete list of 445 indexes with `idx_scan = 0`, run:

```sql
SELECT indexname, tablename, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY tablename, indexname;
```
