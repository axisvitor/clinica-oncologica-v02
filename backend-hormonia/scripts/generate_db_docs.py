#!/usr/bin/env python3
"""
Generate Database Documentation
Generates SCHEMA_DOCUMENTATION.md and TABLES_REFERENCE.md from schema JSONs.
"""
import json
import os
from datetime import datetime

BASE_DIR = '/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/database'
SCHEMA_JSON = os.path.join(BASE_DIR, 'complete_schema.json')
ANALYSIS_JSON = os.path.join(BASE_DIR, 'schema_analysis.json')
DOCS_DIR = os.path.join(BASE_DIR, 'reference')

def load_data():
    with open(SCHEMA_JSON, 'r') as f:
        schema = json.load(f)
    with open(ANALYSIS_JSON, 'r') as f:
        analysis = json.load(f)
    return schema, analysis

def generate_tables_reference(schema, analysis):
    print("Generating TABLES_REFERENCE.md...")
    content = ["# Tables Reference\n"]
    
    domains = analysis['table_domains']
    sorted_domains = sorted(domains.keys())
    
    for domain in sorted_domains:
        tables = sorted(domains[domain])
        if not tables:
            continue
            
        content.append(f"## {domain}")
        
        for table_name in tables:
            if table_name not in schema['tables']:
                continue
                
            table_info = schema['tables'][table_name]
            content.append(f"### `{table_name}`")
            if table_info.get('comment'):
                content.append(f"_{table_info['comment']}_\n")
            else:
                content.append("")
                
            # Columns
            content.append("#### Columns")
            content.append("| Name | Type | Nullable | Default | PK | FK | Description |")
            content.append("|------|------|----------|---------|----|----|-------------|")
            
            for col in table_info['columns']:
                is_pk = col['name'] in table_info['primary_key']['columns']
                pk = "✅" if is_pk else ""
                
                # Check FK
                fk = ""
                for fkey in table_info['foreign_keys']:
                    if col['name'] == fkey['column']:
                        fk = f"-> {fkey['referenced_table']}.{fkey['referenced_column']}"
                        break
                
                default_val = f"`{col['default']}`" if col['default'] is not None else "`None`"
                comment = col['comment'] if col['comment'] else ""
                
                # Escape pipes in description
                comment = comment.replace("|", "\\|")
                
                content.append(f"| `{col['name']}` | `{col['data_type']}` | {col['nullable']} | {default_val} | {pk} | {fk} | {comment} |")
            
            content.append("")
            
            # Indexes
            if table_info['indexes']:
                content.append("#### Indexes")
                content.append("| Name | Columns | Unique |")
                content.append("|------|---------|--------|")
                for idx in table_info['indexes']:
                    cols = ", ".join([c for c in idx['columns'] if c])
                    content.append(f"| `{idx['name']}` | {cols} | {idx['is_unique']} |")
                content.append("")
            
            content.append("---\n")

    with open(os.path.join(DOCS_DIR, 'TABLES_REFERENCE.md'), 'w') as f:
        f.write('\n'.join(content))

def generate_schema_documentation(schema, analysis):
    print("Generating SCHEMA_DOCUMENTATION.md...")
    content = ["# Complete Database Schema Documentation\n"]
    content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d')}")
    content.append(f"**Database:** PostgreSQL")
    content.append(f"**Total Tables:** {analysis['summary']['total_tables']}")
    content.append(f"**Total Relationships:** {analysis['summary']['total_relationships']}")
    content.append(f"**User-Defined Types:** {analysis['summary']['total_user_defined_types']}")
    content.append("\n---\n")
    
    content.append("## 📊 Executive Summary\n")
    content.append("### Database Statistics")
    content.append(f"- **Total Tables:** {analysis['summary']['total_tables']}")
    content.append(f"- **Total Columns:** {schema['total_columns']}")
    content.append(f"- **Total Indexes:** {schema['total_indexes']}")
    content.append(f"- **Foreign Key Relationships:** {analysis['summary']['total_relationships']}")
    content.append(f"- **User-Defined Types (Enums):** {analysis['summary']['total_user_defined_types']}")
    content.append("")
    
    content.append("## 🗂️ Table Organization by Domain\n")
    
    domains = analysis['table_domains']
    sorted_domains = sorted(domains.keys())
    
    for domain in sorted_domains:
        tables = sorted(domains[domain])
        if not tables:
            continue
            
        content.append(f"### {domain} ({len(tables)} tables)\n")
        content.append("| Table | Columns | Indexes | Foreign Keys |")
        content.append("|-------|---------|---------|--------------|")
        
        for table_name in tables:
            if table_name not in analysis['table_complexity']:
                continue
            comp = analysis['table_complexity'][table_name]
            content.append(f"| `{table_name}` | {comp['columns']} | {comp['indexes']} | {comp['foreign_keys']} |")
        content.append("")

    # User Defined Types
    content.append("## 🔤 User-Defined Types (Enums)\n")
    content.append("| Type Name | Values | Used In |")
    content.append("|-----------|--------|---------|")
    
    for type_name, type_info in schema['user_defined_types'].items():
        values = ", ".join(type_info['values'])
        usages = analysis['enum_usage'].get(type_name, [])
        usage_str = ", ".join([f"{u['table']}.{u['column']}" for u in usages[:3]])
        if len(usages) > 3:
            usage_str += ", ..."
        content.append(f"| `{type_name}` | {values} | {usage_str} |")
    content.append("")

    with open(os.path.join(DOCS_DIR, 'SCHEMA_DOCUMENTATION.md'), 'w') as f:
        f.write('\n'.join(content))

def main():
    try:
        schema, analysis = load_data()
        # Add some aggregated stats to schema dict for easier access if missing
        schema['total_columns'] = sum(len(t['columns']) for t in schema['tables'].values())
        schema['total_indexes'] = sum(len(t['indexes']) for t in schema['tables'].values())
        
        generate_tables_reference(schema, analysis)
        generate_schema_documentation(schema, analysis)
        print("✅ Documentation generation complete!")
    except Exception as e:
        print(f"Error generating docs: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()