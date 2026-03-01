# Table: `uploads`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **user_id** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **file_name** | `VARCHAR(500)` | ❌ | - |  |  |
| **file_size** | `INTEGER` | ❌ | - |  |  |
| **file_type** | `VARCHAR(100)` | ✅ | - |  |  |
| **storage_path** | `VARCHAR(1000)` | ❌ | - |  |  |
| **storage_provider** | `VARCHAR(50)` | ❌ | `'local'::character varying` |  |  |
| **content_hash** | `VARCHAR(64)` | ✅ | - |  |  |
| **file_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **is_public** | `BOOLEAN` | ❌ | `false` |  |  |
| **virus_scanned** | `BOOLEAN` | ❌ | `false` |  |  |
| **virus_clean** | `BOOLEAN` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_uploads_content_hash | ❌ | `content_hash` |
| ix_uploads_id | ❌ | `id` |
| ix_uploads_storage_path | ❌ | `storage_path` |
| ix_uploads_user_id | ❌ | `user_id` |
| uploads_storage_path_key | ✅ | `storage_path` |
