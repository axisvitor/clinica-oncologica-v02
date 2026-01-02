# Table: `ab_experiment_audit`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **experiment_id** | `UUID` | ❌ | - |  | ➡️ [ab_experiments]( ab_experiments.md ).id |
| **action** | `VARCHAR(100)` | ❌ | - |  |  |
| **actor** | `VARCHAR(255)` | ❌ | - |  |  |
| **actor_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **action_details** | `JSONB` | ✅ | - |  |  |
| **previous_state** | `JSONB` | ✅ | - |  |  |
| **new_state** | `JSONB` | ✅ | - |  |  |
| **ip_address** | `VARCHAR(45)` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **session_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **hipaa_logged** | `BOOLEAN` | ❌ | - |  |  |
| **gdpr_compliant** | `BOOLEAN` | ❌ | - |  |  |
| **timestamp** | `TIMESTAMP` | ❌ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_ab_audit_actor_time | ❌ | `actor, timestamp` |
| ix_ab_audit_compliance | ❌ | `hipaa_logged, gdpr_compliant` |
| ix_ab_audit_exp_action | ❌ | `experiment_id, action` |
| ix_ab_experiment_audit_action | ❌ | `action` |
| ix_ab_experiment_audit_experiment_id | ❌ | `experiment_id` |
| ix_ab_experiment_audit_id | ❌ | `id` |
| ix_ab_experiment_audit_timestamp | ❌ | `timestamp` |
