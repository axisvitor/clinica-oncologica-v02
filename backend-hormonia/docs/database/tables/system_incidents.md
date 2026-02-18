# Table: `system_incidents`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **title** | `VARCHAR(255)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **severity** | `ENUM(incidentseverity)` | ❌ | - |  |  |
| **status** | `ENUM(incidentstatus)` | ❌ | - |  |  |
| **service_name** | `VARCHAR(100)` | ❌ | - |  |  |
| **started_at** | `TIMESTAMP` | ❌ | - |  |  |
| **resolved_at** | `TIMESTAMP` | ✅ | - |  |  |
| **meta_data** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_system_incidents_id | ❌ | `id` |
