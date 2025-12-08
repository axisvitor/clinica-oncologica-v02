#!/usr/bin/env python3
"""
Schema Relationship Analysis
Creates visual relationship maps and detailed analysis
"""
import json
from collections import defaultdict

def load_schema():
    """Load the extracted schema"""
    with open('/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/database/complete_schema.json', 'r') as f:
        return json.load(f)

def analyze_relationships(schema):
    """Analyze table relationships and dependencies"""

    # Build relationship graph
    graph = defaultdict(lambda: {'references': [], 'referenced_by': []})

    for rel in schema['relationships']:
        from_table = rel['from_table']
        to_table = rel['to_table']

        graph[from_table]['references'].append({
            'table': to_table,
            'from_column': rel['from_column'],
            'to_column': rel['to_column'],
            'on_delete': rel['on_delete'],
            'on_update': rel['on_update']
        })

        graph[to_table]['referenced_by'].append({
            'table': from_table,
            'from_column': rel['from_column'],
            'to_column': rel['to_column']
        })

    return graph

def analyze_table_complexity(schema):
    """Analyze table complexity metrics"""
    complexity = {}

    for table_name, table_info in schema['tables'].items():
        complexity[table_name] = {
            'columns': len(table_info['columns']),
            'indexes': len(table_info['indexes']),
            'foreign_keys': len(table_info['foreign_keys']),
            'unique_constraints': len(table_info['unique_constraints']),
            'check_constraints': len(table_info['check_constraints']),
            'triggers': len(table_info['triggers']),
            'complexity_score': (
                len(table_info['columns']) * 1 +
                len(table_info['indexes']) * 2 +
                len(table_info['foreign_keys']) * 3 +
                len(table_info['triggers']) * 5
            )
        }

    return complexity

def identify_core_tables(schema, graph):
    """Identify core/central tables based on relationships"""
    core_tables = []

    for table_name in schema['tables'].keys():
        ref_count = len(graph[table_name]['references'])
        ref_by_count = len(graph[table_name]['referenced_by'])

        # Tables referenced by many others are core tables
        if ref_by_count >= 3:
            core_tables.append({
                'table': table_name,
                'referenced_by_count': ref_by_count,
                'references_count': ref_count,
                'importance_score': ref_by_count * 2 + ref_count
            })

    return sorted(core_tables, key=lambda x: x['importance_score'], reverse=True)

def identify_isolated_tables(schema, graph):
    """Identify tables with no relationships"""
    isolated = []

    for table_name in schema['tables'].keys():
        if (len(graph[table_name]['references']) == 0 and
            len(graph[table_name]['referenced_by']) == 0):
            isolated.append(table_name)

    return sorted(isolated)

def group_tables_by_domain(schema):
    """Group tables by functional domain based on naming patterns"""
    domains = {
        'Admin & Security': [],
        'Patients & Medical': [],
        'Messaging & WhatsApp': [],
        'Quiz & Flow': [],
        'Audit & Logging': [],
        'System & Meta': []
    }

    for table_name in schema['tables'].keys():
        if table_name.startswith('admin_'):
            domains['Admin & Security'].append(table_name)
        elif any(x in table_name for x in ['patient', 'medical', 'appointment']):
            domains['Patients & Medical'].append(table_name)
        elif any(x in table_name for x in ['whatsapp', 'message', 'contact']):
            domains['Messaging & WhatsApp'].append(table_name)
        elif any(x in table_name for x in ['quiz', 'flow']):
            domains['Quiz & Flow'].append(table_name)
        elif any(x in table_name for x in ['audit', 'log', 'security_audit']):
            domains['Audit & Logging'].append(table_name)
        else:
            domains['System & Meta'].append(table_name)

    return domains

def analyze_enum_usage(schema):
    """Analyze how enums are used across tables"""
    enum_usage = defaultdict(list)

    for table_name, table_info in schema['tables'].items():
        for column in table_info['columns']:
            if column['udt_name'] in schema['user_defined_types']:
                enum_usage[column['udt_name']].append({
                    'table': table_name,
                    'column': column['name']
                })

    return enum_usage

def generate_mermaid_diagram(schema, graph, core_tables):
    """Generate Mermaid ER diagram for core tables"""

    # Focus on top 10 core tables to keep diagram readable
    top_tables = [t['table'] for t in core_tables[:10]]

    mermaid = ["erDiagram"]

    # Add relationships
    for rel in schema['relationships']:
        if rel['from_table'] in top_tables or rel['to_table'] in top_tables:
            on_delete = rel['on_delete'].replace(' ', '_')
            mermaid.append(
                f"    {rel['from_table']} ||--o{{ {rel['to_table']} : \"{rel['from_column']} (ON DELETE {on_delete})\""
            )

    return '\n'.join(mermaid)

def create_analysis_report(schema):
    """Create comprehensive analysis report"""

    graph = analyze_relationships(schema)
    complexity = analyze_table_complexity(schema)
    core_tables = identify_core_tables(schema, graph)
    isolated_tables = identify_isolated_tables(schema, graph)
    domains = group_tables_by_domain(schema)
    enum_usage = analyze_enum_usage(schema)

    report = {
        'summary': {
            'total_tables': len(schema['tables']),
            'total_relationships': len(schema['relationships']),
            'total_user_defined_types': len(schema['user_defined_types']),
            'core_tables_count': len(core_tables),
            'isolated_tables_count': len(isolated_tables)
        },
        'core_tables': core_tables,
        'isolated_tables': isolated_tables,
        'table_domains': domains,
        'relationship_graph': dict(graph),
        'table_complexity': complexity,
        'enum_usage': dict(enum_usage),
        'user_defined_types': schema['user_defined_types'],
        'mermaid_diagram': generate_mermaid_diagram(schema, graph, core_tables)
    }

    return report

def main():
    print("Loading schema...")
    schema = load_schema()

    print("Analyzing relationships and structure...")
    report = create_analysis_report(schema)

    print("\n📊 SCHEMA ANALYSIS REPORT")
    print("=" * 60)

    print(f"\n📈 Summary:")
    print(f"   Total Tables: {report['summary']['total_tables']}")
    print(f"   Total Relationships: {report['summary']['total_relationships']}")
    print(f"   User-Defined Types: {report['summary']['total_user_defined_types']}")
    print(f"   Core Tables: {report['summary']['core_tables_count']}")
    print(f"   Isolated Tables: {report['summary']['isolated_tables_count']}")

    print(f"\n🎯 Top 10 Core Tables (Most Referenced):")
    for i, table in enumerate(report['core_tables'][:10], 1):
        print(f"   {i:2d}. {table['table']:35s} (referenced by {table['referenced_by_count']} tables, score: {table['importance_score']})")

    print(f"\n🏝️  Isolated Tables (No Relationships):")
    for table in report['isolated_tables']:
        print(f"   - {table}")

    print(f"\n🗂️  Tables by Domain:")
    for domain, tables in report['table_domains'].items():
        print(f"   {domain}: {len(tables)} tables")
        for table in sorted(tables):
            print(f"      - {table}")

    print(f"\n🔤 User-Defined Types (Enums):")
    for type_name, type_info in report['user_defined_types'].items():
        usage_count = len(report['enum_usage'].get(type_name, []))
        print(f"   {type_name} ({usage_count} usages): {', '.join(type_info['values'])}")

    print(f"\n💾 Most Complex Tables (by complexity score):")
    top_complex = sorted(report['table_complexity'].items(),
                        key=lambda x: x[1]['complexity_score'],
                        reverse=True)[:10]
    for table, metrics in top_complex:
        print(f"   {table:35s} Score: {metrics['complexity_score']:3d} (cols:{metrics['columns']:2d}, idx:{metrics['indexes']:2d}, fk:{metrics['foreign_keys']:2d}, trg:{metrics['triggers']:2d})")

    # Save detailed analysis
    output_path = '/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/database/schema_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Detailed analysis saved to: {output_path}")

    # Save Mermaid diagram
    mermaid_path = '/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/database/schema_diagram.mmd'
    with open(mermaid_path, 'w', encoding='utf-8') as f:
        f.write(report['mermaid_diagram'])

    print(f"✅ Mermaid diagram saved to: {mermaid_path}")

if __name__ == '__main__':
    main()
