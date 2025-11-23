# Database Schema - Quick Start Guide

**Last Updated:** 2025-11-15

---

## 🚀 What Was Extracted?

✅ **47 tables** completely documented
✅ **594 columns** with full metadata
✅ **260 indexes** (BTREE, GIN, UNIQUE, COMPOSITE)
✅ **57 foreign key relationships** mapped
✅ **14 triggers** documented
✅ **14 user-defined types** (enums) catalogued

---

## 📁 Where to Start?

### For Humans 👨‍💻
1. **[EXTRACTION_SUMMARY.md](./EXTRACTION_SUMMARY.md)** - Start here! Quick overview and key findings
2. **[SCHEMA_DOCUMENTATION.md](../../../reference/SCHEMA_DOCUMENTATION.md)** - Comprehensive human-readable docs
3. **[schema_diagram.mmd](../../../reference/schema_diagram.mmd)** - Visual ER diagram (open in VS Code/GitHub)

### For Developers 💻
1. **[complete_schema.json](../../../reference/complete_schema.json)** - Complete schema export (382 KB)
2. **[schema_analysis.json](../../../reference/schema_analysis.json)** - Relationship analysis (43 KB)

### For Architects 🏗️
1. **[DATABASE_SCHEMA_EXTRACTION_REPORT.md](../../DATABASE_SCHEMA_EXTRACTION_REPORT.md)** - Full technical report (18 KB)

---

## 🔍 Quick Lookups

### Top 5 Core Tables

| Table | Referenced By | Columns | Indexes | Domain |
|-------|---------------|---------|---------|--------|
| `patients` | 15 tables | 18 | 15 | Medical |
| `users` | 15 tables | 17 | 9 | System |
| `admin_users` | 9 tables | 24 | 7 | Admin |
| `flow_template_versions` | 5 tables | - | - | Flow Engine |
| `quiz_templates` | 3 tables | - | - | Quiz System |

### Most Complex Tables

| Table | Complexity Score | Why? |
|-------|------------------|------|
| `messages` | 65 | 21 columns, 18 indexes - messaging hub |
| `patients` | 56 | 18 columns, 15 indexes - medical core |
| `admin_users` | 49 | 24 columns, RBAC system |

### Isolated Tables (No Foreign Keys)

9 tables have no relationships:
- `alembic_version` (expected)
- `whatsapp_contacts`, `whatsapp_instances`, `whatsapp_messages`
- `audit_log_entries`, `audit_trail`, `error_logs`
- `flow_template_categories`, `webhook_events`

**→ Action Item:** Consider integrating these tables

---

## 📊 Domain Breakdown

| Domain | Tables | Description |
|--------|--------|-------------|
| **Admin & Security** | 10 | RBAC, audit trails, IP filtering |
| **Patients & Medical** | 5 | Patient records, appointments, reports |
| **Messaging & WhatsApp** | 8 | Multi-channel messaging |
| **Quiz & Flow Engine** | 12 | Flow orchestration, quiz management |
| **Audit & Logging** | 6 | Compliance and audit trails |
| **System & Meta** | 6 | Users, notifications, webhooks |

---

## 🔤 User-Defined Types (Enums)

**14 enums** provide type safety:

| Enum | Values (count) | Used In |
|------|----------------|---------|
| `saga_status` | 10 states | SAGA orchestration |
| `message_type` | 14 types | Message categorization |
| `flow_state` | 6 states | Patient journey |
| `admin_role_type` | 4 roles | Admin RBAC |
| `severity_type` | 4 levels | Alert system |

**⚠️ Duplicates Found:**
- `severity_type` / `alert_severity`
- `messagestatus` / `deliverystatus` / `message_status`

→ **Recommendation:** Consolidate duplicate enums

---

## 💡 Quick Tips

### Query the Schema
```python
import json

# Load schema
with open('complete_schema.json') as f:
    schema = json.load(f)

# Get table info
patients = schema['tables']['patients']
print(f"Columns: {len(patients['columns'])}")
print(f"Indexes: {len(patients['indexes'])}")
print(f"Foreign keys: {len(patients['foreign_keys'])}")
```

### View Relationships
```python
# Find all tables that reference patients
for table, info in schema['tables'].items():
    for fk in info['foreign_keys']:
        if fk['referenced_table'] == 'patients':
            print(f"{table} -> patients")
```

### Check Indexes
```python
# List all GIN indexes (for JSONB)
for table, info in schema['tables'].items():
    for idx in info['indexes']:
        if idx['type'] == 'gin':
            print(f"{table}: {idx['name']}")
```

---

## 🛠️ Maintenance

### Re-run Extraction
```bash
cd backend-hormonia

# Extract complete schema
python3 scripts/extract_complete_schema.py

# Analyze relationships
python3 scripts/analyze_schema_relationships.py
```

### View Mermaid Diagram
- **In VS Code:** Install "Markdown Preview Mermaid Support" extension
- **In Browser:** Copy contents to https://mermaid.live/
- **In GitHub:** Diagrams render automatically

---

## 🎯 Common Tasks

### Find a Table
```bash
# Search in complete_schema.json
cat complete_schema.json | python3 -c "import json, sys; s=json.load(sys.stdin); print('\n'.join(s['tables'].keys()))"
```

### Get Table Details
```bash
# Get patients table info
cat complete_schema.json | python3 -c "import json, sys; s=json.load(sys.stdin); import pprint; pprint.pprint(s['tables']['patients'])"
```

### List All Foreign Keys
```bash
# Show all relationships
cat schema_analysis.json | python3 -c "import json, sys; s=json.load(sys.stdin); [print(f\"{r['from_table']}.{r['from_column']} -> {r['to_table']}.{r['to_column']}\") for r in s['relationship_graph'].values()]"
```

---

## 📚 Full Documentation

| Document | Description |
|----------|-------------|
| [EXTRACTION_SUMMARY.md](./EXTRACTION_SUMMARY.md) | Quick overview and findings |
| [SCHEMA_DOCUMENTATION.md](../../../reference/SCHEMA_DOCUMENTATION.md) | Comprehensive docs |
| [DATABASE_SCHEMA_EXTRACTION_REPORT.md](../../DATABASE_SCHEMA_EXTRACTION_REPORT.md) | Full technical report |
| [complete_schema.json](../../../reference/complete_schema.json) | Complete schema export |
| [schema_analysis.json](../../../reference/schema_analysis.json) | Relationship analysis |
| [schema_diagram.mmd](../../../reference/schema_diagram.mmd) | Mermaid ER diagram |

---

## 🆘 Need Help?

1. **Check the docs:** Read EXTRACTION_SUMMARY.md first
2. **Query the JSON:** Use the Python examples above
3. **View the diagram:** Open schema_diagram.mmd
4. **Read the report:** Full details in DATABASE_SCHEMA_EXTRACTION_REPORT.md

---

**Generated:** 2025-11-15
**Database:** PostgreSQL (AWS RDS)
**Total Documentation:** 476 KB

✅ **Happy Schema Exploration!**
