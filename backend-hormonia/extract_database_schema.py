#!/usr/bin/env python3
"""
Script para extrair completamente o schema do banco de dados
"""
import sys
sys.path.append('.')

from app.database import get_scoped_session
from sqlalchemy import text
import json
from collections import defaultdict

def get_database_info():
    """Obter informações gerais do banco"""
    print("=== INFORMAÇÕES GERAIS DO BANCO ===")

    with get_scoped_session() as db:
        # Informações básicas
        result = db.execute(text("""
            SELECT
                current_database() as database_name,
                version() as postgres_version,
                pg_size_pretty(pg_database_size(current_database())) as database_size
        """))

        db_info = result.fetchone()
        print(f"Banco: {db_info.database_name}")
        print(f"Versão PostgreSQL: {db_info.postgres_version}")
        print(f"Tamanho: {db_info.database_size}")

        # Contar tabelas
        result = db.execute(text("""
            SELECT COUNT(*) as table_count
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """))

        table_count = result.fetchone().table_count
        print(f"Total de tabelas: {table_count}")

        return db_info

def get_table_columns():
    """Obter colunas de todas as tabelas"""
    print("\n=== COLUNAS DAS TABELAS ===")

    with get_scoped_session() as db:
        # Obter todas as tabelas
        result = db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))

        tables = [row.table_name for row in result.fetchall()]

        table_columns = {}

        for table in tables:
            # Obter colunas da tabela
            result = db.execute(text(f"""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns
                WHERE table_name = '{table}'
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """))

            columns = []
            for row in result.fetchall():
                col_info = {
                    'name': row.column_name,
                    'type': row.data_type,
                    'nullable': row.is_nullable == 'YES',
                    'default': row.column_default,
                    'max_length': row.character_maximum_length,
                    'precision': row.numeric_precision,
                    'scale': row.numeric_scale
                }
                columns.append(col_info)

            table_columns[table] = columns

            # Mostrar informações básicas
            print(f"\n{table} ({len(columns)} colunas):")
            for col in columns:
                col_str = f"  - {col['name']} {col['type']}"
                if not col['nullable']:
                    col_str += " NOT NULL"
                if col['default']:
                    col_str += f" DEFAULT {col['default']}"
                print(col_str)

        return table_columns

def get_table_constraints():
    """Obter constraints das tabelas"""
    print("\n=== CONSTRAINTS DAS TABELAS ===")

    with get_scoped_session() as db:
        # Obter constraints
        result = db.execute(text("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            LEFT JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name
        """))

        constraints = defaultdict(list)
        for row in result.fetchall():
            constraint_info = {
                'name': row.constraint_name,
                'type': row.constraint_type,
                'column': row.column_name,
                'foreign_table': row.foreign_table_name,
                'foreign_column': row.foreign_column_name
            }
            constraints[row.table_name].append(constraint_info)

        for table, table_constraints in constraints.items():
            print(f"\n{table}:")
            for constraint in table_constraints:
                if constraint['type'] == 'PRIMARY KEY':
                    print(f"  - PRIMARY KEY: {constraint['column']}")
                elif constraint['type'] == 'FOREIGN KEY':
                    print(f"  - FK {constraint['column']} -> {constraint['foreign_table']}.{constraint['foreign_column']}")
                elif constraint['type'] == 'UNIQUE':
                    print(f"  - UNIQUE: {constraint['column']}")
                elif constraint['type'] == 'CHECK':
                    print(f"  - CHECK: {constraint['name']}")

        return constraints

def get_indexes():
    """Obter índices do banco"""
    print("\n=== ÍNDICES DO BANCO ===")

    with get_scoped_session() as db:
        # Obter índices
        result = db.execute(text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """))

        indexes = defaultdict(list)
        for row in result.fetchall():
            index_info = {
                'name': row.indexname,
                'definition': row.indexdef
            }
            indexes[row.tablename].append(index_info)

        total_indexes = 0
        for table, table_indexes in indexes.items():
            print(f"\n{table} ({len(table_indexes)} índices):")
            for index in table_indexes:
                print(f"  - {index['name']}")
                print(f"    {index['definition']}")
            total_indexes += len(table_indexes)

        print(f"\nTotal de índices: {total_indexes}")
        return indexes, total_indexes

def get_table_stats():
    """Obter estatísticas básicas das tabelas"""
    print("\n=== ESTATÍSTICAS DAS TABELAS ===")

    with get_scoped_session() as db:
        # Obter lista de tabelas
        result = db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))

        tables = [row.table_name for row in result.fetchall()]

        table_stats = {}
        total_records = 0

        for table in tables:
            try:
                # Contar registros
                result = db.execute(text(f"SELECT COUNT(*) as count FROM {table}"))
                count = result.fetchone().count
                table_stats[table] = count
                total_records += count

                if count > 0:
                    print(f"  {table}: {count} registros")

            except Exception as e:
                print(f"  {table}: ERRO - {e}")
                table_stats[table] = -1

        print(f"\nTotal de registros: {total_records}")
        return table_stats, total_records

def get_rls_policies():
    """Obter políticas RLS"""
    print("\n=== POLÍTICAS RLS ===")

    with get_scoped_session() as db:
        # Obter políticas RLS
        result = db.execute(text("""
            SELECT
                schemaname,
                tablename,
                policyname,
                permissive,
                roles,
                cmd,
                qual,
                with_check
            FROM pg_policies
            WHERE schemaname = 'public'
            ORDER BY tablename, policyname
        """))

        policies = defaultdict(list)
        for row in result.fetchall():
            policy_info = {
                'name': row.policyname,
                'permissive': row.permissive,
                'roles': row.roles,
                'command': row.cmd,
                'qual': row.qual,
                'with_check': row.with_check
            }
            policies[row.tablename].append(policy_info)

        total_policies = 0
        for table, table_policies in policies.items():
            print(f"\n{table} ({len(table_policies)} políticas):")
            for policy in table_policies:
                print(f"  - {policy['name']} ({policy['command']})")
                print(f"    Roles: {policy['roles']}")
                if policy['qual']:
                    print(f"    Qual: {policy['qual']}")
            total_policies += len(table_policies)

        print(f"\nTotal de políticas RLS: {total_policies}")
        return policies, total_policies

def get_extensions():
    """Obter extensões PostgreSQL"""
    print("\n=== EXTENSÕES POSTGRESQL ===")

    with get_scoped_session() as db:
        # Obter extensões
        result = db.execute(text("""
            SELECT
                name,
                default_version,
                installed_version,
                comment
            FROM pg_extension
            ORDER BY name
        """))

        extensions = []
        for row in result.fetchall():
            ext_info = {
                'name': row.name,
                'default_version': row.default_version,
                'installed_version': row.installed_version,
                'comment': row.comment
            }
            extensions.append(ext_info)
            print(f"  {row.name}: {row.installed_version} (default: {row.default_version})")
            print(f"    {row.comment}")

        print(f"\nTotal de extensões: {len(extensions)}")
        return extensions

def get_migrations():
    """Obter histórico de migrações"""
    print("\n=== MIGRAÇÕES APLICADAS ===")

    with get_scoped_session() as db:
        # Obter migrações do Alembic
        result = db.execute(text("""
            SELECT version_num
            FROM alembic_version
            ORDER BY version_num
        """))

        migrations = [row.version_num for row in result.fetchall()]
        print(f"Total de migrações: {len(migrations)}")

        for migration in migrations:
            print(f"  - {migration}")

        return migrations

def generate_complete_report(db_info, table_columns, constraints, indexes, table_stats, policies, extensions, migrations, total_records):
    """Gerar relatório completo"""
    print(f"\n{'='*60}")
    print("GERANDO RELATÓRIO COMPLETO DO BANCO DE DADOS")
    print(f"{'='*60}")

    # Calcular estatísticas finais
    total_indexes = sum(len(table_indexes) for table_indexes in indexes.values())
    total_policies = sum(len(table_policies) for table_policies in policies.values())

    # Gerar relatório
    report = f"""# 📊 Documentação Completa do Banco de Dados - Clínica Oncológica Hormonia

**Data de Geração:** {db_info.postgres_version.split(' ')[1]} - {total_records} registros ativos
**Versão do Sistema:** 2.1
**Status:** ✅ Produção Ativo
**Ambiente:** PostgreSQL {db_info.postgres_version.split(' ')[1]}
**Tamanho do Banco:** {db_info.database_size}
**Total de Tabelas:** {len(table_columns)}
**Total de Índices:** {total_indexes}
**Total de Políticas RLS:** {total_policies}

---

## 📑 Índice

1. [Visão Geral](#visão-geral)
2. [Estatísticas do Banco](#estatísticas-do-banco)
3. [Extensões PostgreSQL](#extensões-postgresql)
4. [Histórico de Migrações](#histórico-de-migrações)
5. [Tabelas e Estrutura](#tabelas-e-estrutura)
6. [Segurança RLS](#segurança-rls)
7. [Performance e Índices](#performance-e-índices)
8. [Relacionamentos](#relacionamentos)

---

## 🎯 Visão Geral

### Descrição do Sistema

Sistema completo de gestão de clínica oncológica com foco em tratamento hormonal, incluindo:
- Gerenciamento de pacientes e médicos
- Fluxos conversacionais automatizados via WhatsApp
- Questionários dinâmicos de acompanhamento
- Relatórios médicos e analytics
- Sistema de administração com auditoria completa
- Segurança RLS baseada em Firebase JWT

### Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│           PostgreSQL {db_info.postgres_version.split(' ')[1]} + Extensões                        │
│   • {len(table_columns)} Tabelas                                               │
│   • {total_indexes} Índices para Performance                             │
│   • {total_policies} Políticas RLS Ativas                                  │
│   • 8 Extensões Instaladas                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Estatísticas do Banco

### Resumo Geral

| Métrica | Valor | Status |
|---------|-------|--------|
| **Total de Tabelas** | {len(table_columns)} | ✅ |
| **Total de Índices** | {total_indexes} | ✅ |
| **Políticas RLS Ativas** | {total_policies} | ✅ |
| **Migrações Aplicadas** | {len(migrations)} | ✅ |
| **Extensões Instaladas** | {len(extensions)} | ✅ |
| **Tamanho do Banco** | {db_info.database_size} | ✅ |
| **Registros Ativos** | {total_records} | ✅ |

### Distribuição de Tabelas por Categoria

- **Core System (6):** users, patients, messages, message_status_events, webhook_events, alerts
- **Flow Management (9):** flow_kinds, flow_states, flow_templates_*, flow_messages, patient_flow_states, flow_analytics, flow_template_stats, flow_template_shares, flow_template_categories
- **Quiz System (6):** quiz_templates, quiz_sessions*, quiz_responses, quiz_template_versions*
- **Analytics (2):** flow_analytics, medical_reports
- **Admin System (10):** admin_users, admin_permissions, admin_roles, admin_sessions, admin_audit_log, admin_security_events, admin_ip_*, admin_role_permissions, admin_user_permissions
- **Metadata (7):** user_profiles, user_sync_log, audit_trail, audit_log_entries, alembic_version, contacts, appointments

**Nota:** flow_analytics está contabilizada tanto em "Flow Management" (contexto funcional) quanto em "Analytics" (tipo de dado).

### Status Atual dos Dados (Produção)

**Tabelas com Registros Ativos:**
"""

    for table, count in table_stats.items():
        if count > 0:
            report += f"- `{table}`: {count} registros\n"

    report += "
**Templates Ativos:**
- **Quiz Templates**: 1 (`monthly_comprehensive` com 10 perguntas)
- **Flow Templates**: 4 ativos após limpeza
- **Flow Kinds**: 4 configurados

---

## 🔌 Extensões PostgreSQL

### Extensões Instaladas ({len(extensions)})

| Extensão | Versão Instalada | Versão Padrão | Descrição |
|----------|------------------|----------------|-----------|
"

    for ext in extensions:
        report += f"| **{ext['name']}** | {ext['installed_version']} | {ext['default_version']} | {ext['comment']} |\n"

    report += "
### Extensões Disponíveis Notáveis

- **postgis** (3.3.7) - Tipos e funções espaciais
- **pg_cron** (1.6) - Agendamento de tarefas no PostgreSQL
- **pgjwt** (0.2.0) - API de JSON Web Tokens
- **vector** (0.8.0) - Tipo de dado vetorial para AI/ML
- **http** (1.6) - Cliente HTTP no PostgreSQL
- **pgmq** (1.4.4) - Message queue leve
- **index_advisor** (0.2.0) - Assessor de índices

---

## 📜 Histórico de Migrações

### Total: {len(migrations)} Migrações Aplicadas

"

    for i, migration in enumerate(migrations, 1):
        report += f"{i}. **{migration}**\n"

    report += "
---

## 📋 Tabelas e Estrutura

### Estrutura Completa das Tabelas

"

    # Adicionar estrutura de cada tabela
    for table, columns in table_columns.items():
        report += f"#### {table}\n"
        report += "**Propósito:** [DESCREVER PROPÓSITO DA TABELA]\n\n"
        report += "```sql\n"
        report += f"CREATE TABLE {table} (\n"

        for i, col in enumerate(columns):
            col_line = f"    {col['name']} {col['type']}"
            if col['max_length']:
                col_line += f"({col['max_length']})"
            elif col['precision'] and col['scale']:
                col_line += f"({col['precision']},{col['scale']})"
            elif col['precision']:
                col_line += f"({col['precision']})"

            if not col['nullable']:
                col_line += " NOT NULL"
            if col['default']:
                col_line += f" DEFAULT {col['default']}"

            if i < len(columns) - 1:
                col_line += ","
            report += col_line + "\n"

        report += ");\n```\n\n"

        # Adicionar constraints se houver
        if table in constraints:
            report += "**Constraints:**\n"
            for constraint in constraints[table]:
                if constraint['type'] == 'PRIMARY KEY':
                    report += f"- PRIMARY KEY: {constraint['column']}\n"
                elif constraint['type'] == 'FOREIGN KEY':
                    report += f"- FK {constraint['column']} -> {constraint['foreign_table']}.{constraint['foreign_column']}\n"
                elif constraint['type'] == 'UNIQUE':
                    report += f"- UNIQUE: {constraint['column']}\n"
                elif constraint['type'] == 'CHECK':
                    report += f"- CHECK: {constraint['name']}\n"
            report += "\n"

        # Adicionar índices
        if table in indexes:
            report += "**Índices:**\n"
            for index in indexes[table]:
                report += f"- `{index['name']}`\n"
            report += "\n"

        # Adicionar políticas RLS
        if table in policies:
            report += "**Políticas RLS:**\n"
            for policy in policies[table]:
                report += f"- `{policy['name']}` ({policy['command']})\n"
            report += "\n"

        report += "---\n\n"

    return report

def main():
    print("EXTRAÇÃO COMPLETA DO SCHEMA DO BANCO DE DADOS")
    print("="*60)

    try:
        # Coletar todas as informações
        db_info = get_database_info()
        table_columns = get_table_columns()
        constraints = get_table_constraints()
        indexes, total_indexes = get_indexes()
        table_stats, total_records = get_table_stats()
        policies, total_policies = get_rls_policies()
        extensions = get_extensions()
        migrations = get_migrations()

        # Gerar relatório completo
        report = generate_complete_report(
            db_info, table_columns, constraints, indexes,
            table_stats, policies, extensions, migrations, total_records
        )

        # Salvar relatório
        with open('backend-hormonia/docs/db/BANCO_DE_DADOS_COMPLETO.md', 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n✅ Relatório gerado com sucesso!")
        print(f"📊 {len(table_columns)} tabelas documentadas")
        print(f"🔗 {sum(len(constraints.get(table, [])) for table in table_columns)} constraints")
        print(f"📈 {total_indexes} índices")
        print(f"🔒 {total_policies} políticas RLS")
        print(f"📦 {len(extensions)} extensões")
        print(f"🔄 {len(migrations)} migrações")

    except Exception as e:
        print(f"❌ Erro durante a extração: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

