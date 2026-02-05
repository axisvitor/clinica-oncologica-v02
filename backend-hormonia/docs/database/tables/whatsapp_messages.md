# Table: `whatsapp_messages`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `TEXT` | ❌ | - | 🔑 |  |
| **instance_name** | `TEXT` | ❌ | - |  |  |
| **chat_id** | `TEXT` | ❌ | - |  |  |
| **sender_id** | `TEXT` | ❌ | - |  |  |
| **recipient_id** | `TEXT` | ❌ | - |  |  |
| **message_type** | `TEXT` | ❌ | - |  |  |
| **content** | `TEXT` | ✅ | - |  |  |
| **media_url** | `TEXT` | ✅ | - |  |  |
| **media_caption** | `TEXT` | ✅ | - |  |  |
| **status** | `TEXT` | ✅ | `'pending'::text` |  |  |
| **external_id** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **sent_at** | `TIMESTAMP` | ✅ | - |  |  |
| **delivered_at** | `TIMESTAMP` | ✅ | - |  |  |
| **read_at** | `TIMESTAMP` | ✅ | - |  |  |
| **failed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ✅ | `0` |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **message_data** | `JSON` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_whatsapp_messages_chat | ❌ | `chat_id` |
| ix_whatsapp_messages_external | ❌ | `external_id` |
| ix_whatsapp_messages_instance | ❌ | `instance_name` |
| whatsapp_messages_external_id_key | ✅ | `external_id` |
