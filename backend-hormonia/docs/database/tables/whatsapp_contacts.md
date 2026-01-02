# Table: `whatsapp_contacts`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `TEXT` | ❌ | - | 🔑 |  |
| **instance_name** | `TEXT` | ❌ | - |  |  |
| **phone_number** | `TEXT` | ❌ | - |  |  |
| **formatted_number** | `TEXT` | ❌ | - |  |  |
| **name** | `TEXT` | ✅ | - |  |  |
| **profile_picture_url** | `TEXT` | ✅ | - |  |  |
| **is_whatsapp_user** | `BOOLEAN` | ✅ | `true` |  |  |
| **last_seen** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **contact_data** | `JSON` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_whatsapp_contacts_instance | ❌ | `instance_name` |
| ix_whatsapp_contacts_phone | ❌ | `phone_number` |
