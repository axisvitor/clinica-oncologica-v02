# Table: `system_health_snapshots`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **status** | `VARCHAR(9)` | ❌ | - |  |  |
| **health_score** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **services_status** | `JSONB` | ❌ | - |  |  |
| **metrics** | `JSONB` | ❌ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_system_health_snapshots_created_at | ❌ | `created_at` |
| ix_system_health_snapshots_id | ❌ | `id` |
