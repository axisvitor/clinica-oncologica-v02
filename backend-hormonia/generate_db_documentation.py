#!/usr/bin/env python3
"""
Script to generate comprehensive database documentation from extracted JSON data.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def load_database_info(json_file: str = 'database_complete_info.json') -> Dict:
    """Load database information from JSON file"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_column_type(column: Dict) -> str:
    """Format column data type with length/precision"""
    data_type = column['data_type']
    
    if column['max_length']:
        return f"{data_type}({column['max_length']})"
    elif column['precision'] and column['scale']:
        return f"{data_type}({column['precision']},{column['scale']})"
    elif column['precision']:
        return f"{data_type}({column['precision']})"
    
    return data_type


def generate_table_section(table_key: str, table_info: Dict) -> str:
    """Generate markdown section for a single table"""
    md = []
    
    # Table header
    md.append(f"### {table_info['name']}")
    md.append("")
    
    if table_info.get('comment'):
        md.append(f"**Descrição:** {table_info['comment']}")
        md.append("")
    
    # Table metadata
    md.append(f"- **Schema:** {table_info['schema']}")
    md.append(f"- **Tipo:** {table_info['type']}")
    md.append(f"- **Tamanho:** {table_info['size']}")
    md.append(f"- **Registros:** {table_info['row_count']:,}")
    md.append("")
    
    # Columns
    if table_info['columns']:
        md.append("#### Colunas")
        md.append("")
        md.append("| Coluna | Tipo | Nullable | Default | Comentário |")
        md.append("|--------|------|----------|---------|------------|")
        
        for col in table_info['columns']:
            col_name = col['name']
            col_type = format_column_type(col)
            nullable = "✓" if col['nullable'] else "✗"
            default = col['default'] if col['default'] else "-"
            comment = col['comment'] if col['comment'] else "-"
            
            # Truncate long defaults
            if len(default) > 40:
                default = default[:37] + "..."
            
            md.append(f"| {col_name} | {col_type} | {nullable} | {default} | {comment} |")
        
        md.append("")
    
    # Indexes
    if table_info.get('indexes'):
        md.append("#### Índices")
        md.append("")
        for idx in table_info['indexes']:
            md.append(f"- **{idx['name']}**")
            md.append(f"  ```sql")
            md.append(f"  {idx['definition']}")
            md.append(f"  ```")
        md.append("")
    
    # Constraints
    if table_info.get('constraints'):
        md.append("#### Constraints")
        md.append("")
        for const in table_info['constraints']:
            const_type = const['type']
            const_name = const['name']
            
            if const_type == 'FOREIGN KEY':
                md.append(f"- **{const_name}** (FK): {', '.join(const['columns'])} → {const['foreign_table']}.{const['foreign_column']}")
                if const.get('delete_rule'):
                    md.append(f"  - ON DELETE: {const['delete_rule']}")
                if const.get('update_rule'):
                    md.append(f"  - ON UPDATE: {const['update_rule']}")
            elif const_type == 'PRIMARY KEY':
                md.append(f"- **{const_name}** (PK): {', '.join(const['columns'])}")
            elif const_type == 'UNIQUE':
                md.append(f"- **{const_name}** (UNIQUE): {', '.join(const['columns'])}")
            elif const_type == 'CHECK':
                md.append(f"- **{const_name}** (CHECK)")
        
        md.append("")
    
    # Triggers
    if table_info.get('triggers'):
        md.append("#### Triggers")
        md.append("")
        for trigger in table_info['triggers']:
            md.append(f"- **{trigger['name']}**")
            md.append(f"  - Timing: {trigger['timing']}")
            md.append(f"  - Event: {trigger['event']}")
            md.append(f"  - Statement: `{trigger['statement'][:100]}...`")
        md.append("")
    
    # RLS Policies
    if table_info.get('rls_policies'):
        md.append("#### RLS Policies")
        md.append("")
        for policy in table_info['rls_policies']:
            md.append(f"- **{policy['name']}**")
            md.append(f"  - Command: {policy['command']}")
            md.append(f"  - Roles: {policy['roles']}")
            if policy.get('using'):
                md.append(f"  - Using: `{policy['using'][:100]}...`")
        md.append("")
    
    md.append("---")
    md.append("")
    
    return "\n".join(md)


def generate_documentation(db_info: Dict, output_file: str) -> None:
    """Generate complete markdown documentation"""
    md = []

    # Header
    md.append("# 📊 Documentação Completa do Banco de Dados - Clínica Oncológica Hormonia")
    md.append("")
    md.append(f"**Data de Extração:** {db_info['extraction_date'][:10]}")
    md.append(f"**Banco de Dados:** {db_info['database_info']['name']}")
    md.append(f"**Versão PostgreSQL:** {db_info['database_info']['version'].split(',')[0]}")
    md.append(f"**Usuário:** {db_info['database_info']['current_user']}")
    md.append(f"**Schema:** {db_info['database_info']['current_schema']}")
    md.append(f"**Servidor:** {db_info['database_info']['server_ip']}:{db_info['database_info']['server_port']}")
    md.append("")
    md.append("> 🤖 **Documentação gerada automaticamente** a partir do script `extract_database_complete.py`")
    md.append("")
    md.append("---")
    md.append("")

    # Table of Contents
    md.append("## 📑 Índice")
    md.append("")
    md.append("1. [Resumo Executivo](#resumo-executivo)")
    md.append("2. [Extensões PostgreSQL](#extensões-postgresql)")
    md.append("3. [Enums](#enums)")
    md.append("4. [Tabelas](#tabelas)")
    md.append("5. [Views](#views)")
    md.append("6. [Materialized Views](#materialized-views)")
    md.append("7. [Funções](#funções)")
    md.append("8. [Sequences](#sequences)")
    md.append("")
    md.append("---")
    md.append("")
    
    # Executive Summary
    md.append("## 📊 Resumo Executivo")
    md.append("")
    md.append("| Métrica | Valor |")
    md.append("|---------|-------|")
    md.append(f"| **Total de Tabelas** | {len(db_info['tables'])} |")
    md.append(f"| **Total de Índices** | {len(db_info['indexes'])} |")
    md.append(f"| **Total de Constraints** | {len(db_info['constraints'])} |")
    md.append(f"| **Políticas RLS** | {len(db_info['rls_policies'])} |")
    md.append(f"| **Funções** | {len(db_info['functions'])} |")
    md.append(f"| **Triggers** | {len(db_info['triggers'])} |")
    md.append(f"| **Views** | {len(db_info['views'])} |")
    md.append(f"| **Materialized Views** | {len(db_info['materialized_views'])} |")
    md.append(f"| **Enums** | {len(db_info['enums'])} |")
    md.append(f"| **Extensões** | {len(db_info['extensions'])} |")
    md.append(f"| **Sequences** | {len(db_info['sequences'])} |")
    md.append("")
    
    # Top tables by records
    tables_with_records = [(k, v['row_count']) for k, v in db_info['tables'].items() if v['row_count'] > 0]
    tables_with_records.sort(key=lambda x: x[1], reverse=True)
    
    if tables_with_records:
        md.append("### 📈 Top 10 Tabelas com Mais Registros")
        md.append("")
        md.append("| # | Tabela | Registros |")
        md.append("|---|--------|-----------|")
        for i, (table, count) in enumerate(tables_with_records[:10], 1):
            md.append(f"| {i} | {table} | {count:,} |")
        md.append("")
    
    # Top tables by size
    tables_with_size = [(k, v['size_bytes'], v['size']) for k, v in db_info['tables'].items() if v['size_bytes']]
    tables_with_size.sort(key=lambda x: x[1], reverse=True)
    
    if tables_with_size:
        md.append("### 💾 Top 10 Tabelas Maiores")
        md.append("")
        md.append("| # | Tabela | Tamanho |")
        md.append("|---|--------|---------|")
        for i, (table, size_bytes, size) in enumerate(tables_with_size[:10], 1):
            md.append(f"| {i} | {table} | {size} |")
        md.append("")
    
    md.append("---")
    md.append("")
    
    # Extensions
    md.append("## 🔌 Extensões PostgreSQL")
    md.append("")
    md.append("| Extensão | Versão | Schema | Relocatable |")
    md.append("|----------|--------|--------|-------------|")
    for ext in db_info['extensions']:
        relocatable = "✓" if ext['relocatable'] else "✗"
        md.append(f"| {ext['name']} | {ext['version']} | {ext['schema']} | {relocatable} |")
    md.append("")
    md.append("---")
    md.append("")
    
    # Enums
    if db_info['enums']:
        md.append("## 🏷️ Enums")
        md.append("")
        for enum_key, enum_info in sorted(db_info['enums'].items()):
            md.append(f"### {enum_info['name']}")
            md.append("")
            md.append("**Valores:**")
            md.append("")
            for val in enum_info['values']:
                md.append(f"- `{val['value']}`")
            md.append("")
        md.append("---")
        md.append("")
    
    # Tables
    md.append("## 📋 Tabelas")
    md.append("")
    md.append(f"Total de tabelas: **{len(db_info['tables'])}**")
    md.append("")

    # Group tables by prefix/category
    table_groups = {}
    for table_key, table_info in sorted(db_info['tables'].items()):
        # Extract prefix (e.g., 'admin_', 'flow_', 'quiz_')
        table_name = table_info['name']
        prefix = table_name.split('_')[0] if '_' in table_name else 'other'

        if prefix not in table_groups:
            table_groups[prefix] = []
        table_groups[prefix].append((table_key, table_info))

    # Generate sections for each group
    for prefix in sorted(table_groups.keys()):
        md.append(f"## Grupo: {prefix.upper()} ({len(table_groups[prefix])} tabelas)")
        md.append("")

        for table_key, table_info in sorted(table_groups[prefix]):
            md.append(generate_table_section(table_key, table_info))

    # Views
    if db_info['views']:
        md.append("## 👁️ Views")
        md.append("")
        md.append(f"Total de views: **{len(db_info['views'])}**")
        md.append("")

        for view_key, view_info in sorted(db_info['views'].items()):
            md.append(f"### {view_info['name']}")
            md.append("")
            md.append(f"- **Schema:** {view_info['schema']}")
            md.append(f"- **Updatable:** {'✓' if view_info['updatable'] else '✗'}")
            md.append(f"- **Insertable:** {'✓' if view_info['insertable'] else '✗'}")
            md.append("")

            if view_info.get('definition'):
                md.append("**Definição:**")
                md.append("```sql")
                definition = view_info['definition']
                md.append(definition[:500] + "..." if len(definition) > 500 else definition)
                md.append("```")
                md.append("")

            md.append("---")
            md.append("")

    # Materialized Views
    if db_info['materialized_views']:
        md.append("## 📊 Materialized Views")
        md.append("")
        md.append(f"Total de materialized views: **{len(db_info['materialized_views'])}**")
        md.append("")

        for mv_key, mv_info in sorted(db_info['materialized_views'].items()):
            md.append(f"### {mv_info['name']}")
            md.append("")
            md.append(f"- **Schema:** {mv_info['schema']}")
            md.append(f"- **Populated:** {'✓' if mv_info['is_populated'] else '✗'}")
            md.append("")

            if mv_info.get('definition'):
                md.append("**Definição:**")
                md.append("```sql")
                definition = mv_info['definition']
                md.append(definition[:500] + "..." if len(definition) > 500 else definition)
                md.append("```")
                md.append("")

            md.append("---")
            md.append("")

    # Functions (summary only - too many to list all)
    if db_info['functions']:
        md.append("## ⚙️ Funções")
        md.append("")
        md.append(f"Total de funções: **{len(db_info['functions'])}**")
        md.append("")

        # Group functions by schema
        func_by_schema = {}
        for func_key, func_info in db_info['functions'].items():
            schema = func_info['schema']
            if schema not in func_by_schema:
                func_by_schema[schema] = []
            func_by_schema[schema].append(func_info)

        for schema in sorted(func_by_schema.keys()):
            md.append(f"### Schema: {schema} ({len(func_by_schema[schema])} funções)")
            md.append("")

            # List first 20 functions per schema
            for func in sorted(func_by_schema[schema], key=lambda x: x['name'])[:20]:
                md.append(f"- **{func['name']}**({func['arguments']}) → {func['return_type']}")

            if len(func_by_schema[schema]) > 20:
                md.append(f"- ... e mais {len(func_by_schema[schema]) - 20} funções")

            md.append("")

    # Sequences
    if db_info['sequences']:
        md.append("## 🔢 Sequences")
        md.append("")
        md.append(f"Total de sequences: **{len(db_info['sequences'])}**")
        md.append("")

        md.append("| Sequence | Schema | Start | Min | Max | Increment | Cycle |")
        md.append("|----------|--------|-------|-----|-----|-----------|-------|")

        for seq_key, seq_info in sorted(db_info['sequences'].items()):
            cycle = "✓" if seq_info['cycle_option'] == 'YES' else "✗"
            md.append(f"| {seq_info['name']} | {seq_info['schema']} | {seq_info['start_value']} | {seq_info['minimum_value']} | {seq_info['maximum_value']} | {seq_info['increment']} | {cycle} |")

        md.append("")

    # Write to file
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))

    print(f"✅ Documentação gerada com sucesso: {output_path}")
    print(f"📄 Total de linhas: {len(md)}")


def main():
    """Main function"""
    print("🚀 Gerando documentação do banco de dados...")
    
    # Load database info
    db_info = load_database_info()
    
    # Generate documentation
    output_file = 'docs/db/BANCO_DE_DADOS_COMPLETO.md'
    generate_documentation(db_info, output_file)
    
    print("✅ Processo concluído!")


if __name__ == "__main__":
    main()

