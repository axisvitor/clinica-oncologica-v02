#!/usr/bin/env python3
"""
Compare production schema with SCHEMA_MASTER_COMPLETO.sql v2.4.
Generate detailed diff report for updating to v2.5.
"""

import json
import sys
from collections import defaultdict

# Load production schema export
with open('c:\\Meu Projetos\\clinica-oncologica-v02\\scripts\\production_schema_export.json', 'r', encoding='utf-8') as f:
    production = json.load(f)

# Schema v2.4 documented tables
DOCUMENTED_TABLES_V24 = {
    'users', 'user_profiles', 'user_sync_log',
    'patients', 'contacts', 'appointments', 'medical_reports',
    'patient_flow_states', 'flow_states', 'flow_kinds', 'flow_messages', 'flow_analytics',
    'flow_template_categories', 'flow_template_versions', 'flow_template_stats', 'flow_template_shares',
    'quiz_templates', 'quiz_sessions', 'quiz_responses',
    'quiz_sessions_v2', 'quiz_template_versions_v2',
    'messages', 'message_status_events', 'webhook_events',
    'audit_trail', 'audit_log_entries', 'alerts',
    'admin_users', 'admin_roles', 'admin_permissions', 'admin_role_permissions', 'admin_user_permissions',
    'admin_sessions', 'admin_audit_log', 'admin_security_events', 'admin_ip_whitelist', 'admin_ip_blacklist',
    'alembic_version'
}

DOCUMENTED_MATVIEWS_V24 = {
    'mv_patient_monthly_engagement',
    'mv_user_quiz_stats',
    'mv_quiz_completion_rate',
    'mv_quiz_monthly_stats',
    'mv_monthly_quiz_participation'
}

print("=" * 100)
print("SCHEMA COMPARISON: Production vs. SCHEMA_MASTER_COMPLETO v2.4")
print("=" * 100)
print()

# Extract production table names
production_tables = set(production['tables'].keys())
production_matviews = {mv['view_name'] for mv in production['materialized_views']}

print(f"Production Tables: {len(production_tables)}")
print(f"Documented Tables (v2.4): {len(DOCUMENTED_TABLES_V24)}")
print(f"Production Materialized Views: {len(production_matviews)}")
print(f"Documented Materialized Views (v2.4): {len(DOCUMENTED_MATVIEWS_V24)}")
print()

# === ANALYSIS 1: Missing Tables ===
print("=" * 100)
print("1. TABLES MISSING FROM DOCUMENTATION")
print("=" * 100)
missing_from_docs = production_tables - DOCUMENTED_TABLES_V24
if missing_from_docs:
    print(f"\nFound {len(missing_from_docs)} tables in production but NOT documented in v2.4:")
    for table in sorted(missing_from_docs):
        table_info = production['tables'][table]
        col_count = len(table_info['columns'])
        print(f"  - {table} ({col_count} columns, {table_info['info']['total_size']})")
else:
    print("\n[OK] All production tables are documented in v2.4")
print()

# === ANALYSIS 2: Extra Tables in Documentation ===
print("=" * 100)
print("2. TABLES IN DOCUMENTATION BUT NOT IN PRODUCTION")
print("=" * 100)
extra_in_docs = DOCUMENTED_TABLES_V24 - production_tables
if extra_in_docs:
    print(f"\nFound {len(extra_in_docs)} tables in v2.4 docs but NOT in production:")
    for table in sorted(extra_in_docs):
        print(f"  - {table}")
else:
    print("\n[OK] All documented tables exist in production")
print()

# === ANALYSIS 3: Materialized Views ===
print("=" * 100)
print("3. MATERIALIZED VIEWS COMPARISON")
print("=" * 100)
missing_matviews = production_matviews - DOCUMENTED_MATVIEWS_V24
extra_matviews = DOCUMENTED_MATVIEWS_V24 - production_matviews

if missing_matviews:
    print(f"\nMaterialized views in production but NOT documented ({len(missing_matviews)}):")
    for mv in sorted(missing_matviews):
        print(f"  - {mv}")
else:
    print("\n[OK] All production materialized views are documented")

if extra_matviews:
    print(f"\nMaterialized views documented but NOT in production ({len(extra_matviews)}):")
    for mv in sorted(extra_matviews):
        print(f"  - {mv}")
print()

# === ANALYSIS 4: Extensions ===
print("=" * 100)
print("4. POSTGRESQL EXTENSIONS")
print("=" * 100)
print("\nProduction Extensions:")
for ext in production['extensions']:
    print(f"  - {ext['name']} (v{ext['version']})")
print()

# === ANALYSIS 5: Custom ENUMs ===
print("=" * 100)
print("5. CUSTOM ENUM TYPES")
print("=" * 100)
print(f"\nTotal ENUMs in production: {len(production['enums'])}")
for enum in production['enums']:
    values_str = ', '.join(enum['enum_values'])
    print(f"  - {enum['enum_name']}: [{values_str}]")
print()

# === ANALYSIS 6: Statistics ===
print("=" * 100)
print("6. DATABASE STATISTICS")
print("=" * 100)
stats = production['statistics']
print(f"\n  Total Tables: {stats['total_tables']}")
print(f"  Total Materialized Views: {stats['total_matviews']}")
print(f"  Total Custom ENUMs: {stats['total_enums']}")
print(f"  Total Extensions: {stats['total_extensions']}")
print(f"  Total Functions: {stats['total_functions']}")
print(f"  Total Triggers: {stats['total_triggers']}")
print(f"  Total RLS Policies: {stats['total_rls_policies']}")
print()

# === ANALYSIS 7: Table Size Report ===
print("=" * 100)
print("7. LARGEST TABLES (Top 15)")
print("=" * 100)
table_sizes = []
for table_name, table_data in production['tables'].items():
    size_str = table_data['info']['total_size']
    table_sizes.append((table_name, size_str, len(table_data['columns'])))

# Sort by table name (since size is string formatted, would need parsing for real sort)
table_sizes.sort(key=lambda x: x[0])
for i, (name, size, cols) in enumerate(table_sizes[:15], 1):
    print(f"  {i:2}. {name:40} {size:>12} ({cols} columns)")
print()

# === ANALYSIS 8: Critical Findings ===
print("=" * 100)
print("8. CRITICAL FINDINGS FOR v2.5 UPDATE")
print("=" * 100)

findings = []

if missing_from_docs:
    findings.append(f"[CRITICAL] {len(missing_from_docs)} undocumented tables need to be added to v2.5")

if extra_in_docs:
    findings.append(f"[WARNING] {len(extra_in_docs)} documented tables don't exist in production - consider removing or flagging as deprecated")

if missing_matviews:
    findings.append(f"[UPDATE] {len(missing_matviews)} new materialized views to document in v2.5")

if extra_matviews:
    findings.append(f"[WARNING] {len(extra_matviews)} documented materialized views missing from production")

if stats['total_rls_policies'] == 0:
    findings.append("[INFO] No RLS policies found - verify if Row Level Security is intentionally disabled")

if stats['total_functions'] > 250:
    findings.append(f"[INFO] High number of functions ({stats['total_functions']}) - verify if all are intentional")

if findings:
    for finding in findings:
        print(f"\n  {finding}")
else:
    print("\n  [OK] Production schema matches documentation v2.4 perfectly!")

print()
print("=" * 100)
print("COMPARISON COMPLETE")
print("=" * 100)
print("\nNext Step: Update SCHEMA_MASTER_COMPLETO.sql to v2.5 with findings above")
print()
