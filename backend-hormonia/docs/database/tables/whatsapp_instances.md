# Table: `whatsapp_instances`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `TEXT` | ❌ | - | 🔑 |  |
| **name** | `TEXT` | ❌ | - |  |  |
| **status** | `TEXT` | ✅ | `'disconnected'::text` |  |  |
| **qr_code** | `TEXT` | ✅ | - |  |  |
| **webhook_url** | `TEXT` | ✅ | - |  |  |
| **phone_number** | `TEXT` | ✅ | - |  |  |
| **profile_name** | `TEXT` | ✅ | - |  |  |
| **profile_picture_url** | `TEXT` | ✅ | - |  |  |
| **is_connected** | `BOOLEAN` | ✅ | `false` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **last_activity** | `TIMESTAMP` | ✅ | - |  |  |
| **settings** | `JSON` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_whatsapp_instances_name | ❌ | `name` |
| whatsapp_instances_name_key | ✅ | `name` |
