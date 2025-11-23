#!/usr/bin/env python3
"""
Complete PostgreSQL Schema Extraction Script
Extracts all tables, columns, constraints, indexes, and relationships
"""
import psycopg2
import json
from collections import defaultdict
from datetime import datetime

# Database connection string
DATABASE_URL = "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def get_user_defined_types(cursor):
    """Extract all user-defined types (enums, composites, etc.)"""
    cursor.execute("""
        SELECT
            t.typname as type_name,
            t.typtype as type_category,
            ARRAY_AGG(e.enumlabel ORDER BY e.enumsortorder) as enum_values
        FROM pg_type t
        LEFT JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typtype = 'e'  -- enum types
        GROUP BY t.typname, t.typtype
        ORDER BY t.typname;
    """)

    types = {}
    for row in cursor.fetchall():
        types[row[0]] = {
            'type_category': 'enum',
            'values': row[2] if row[2] else []
        }
    return types

def get_all_tables(cursor):
    """Get all tables in the public schema"""
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    return [row[0] for row in cursor.fetchall()]

def get_table_columns(cursor, table_name):
    """Get detailed column information for a table"""
    cursor.execute("""
        SELECT
            c.column_name,
            c.data_type,
            c.udt_name,
            c.character_maximum_length,
            c.numeric_precision,
            c.numeric_scale,
            c.is_nullable,
            c.column_default,
            c.ordinal_position,
            col_description(
                (quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass::oid,
                c.ordinal_position
            ) as column_comment
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        AND c.table_name = %s
        ORDER BY c.ordinal_position;
    """, (table_name,))

    columns = []
    for row in cursor.fetchall():
        column = {
            'name': row[0],
            'data_type': row[1],
            'udt_name': row[2],
            'max_length': row[3],
            'numeric_precision': row[4],
            'numeric_scale': row[5],
            'nullable': row[6] == 'YES',
            'default': row[7],
            'position': row[8],
            'comment': row[9]
        }
        columns.append(column)
    return columns

def get_primary_keys(cursor, table_name):
    """Get primary key constraints for a table"""
    cursor.execute("""
        SELECT
            kcu.column_name,
            tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema = 'public'
        AND tc.table_name = %s
        ORDER BY kcu.ordinal_position;
    """, (table_name,))

    return {
        'constraint_name': None,
        'columns': []
    } if cursor.rowcount == 0 else {
        'constraint_name': cursor.fetchone()[1],
        'columns': [row[0] for row in cursor.fetchall()]
    }

def get_foreign_keys(cursor, table_name):
    """Get foreign key constraints for a table"""
    cursor.execute("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON rc.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        AND tc.table_name = %s
        ORDER BY tc.constraint_name;
    """, (table_name,))

    foreign_keys = []
    for row in cursor.fetchall():
        fk = {
            'constraint_name': row[0],
            'column': row[1],
            'referenced_table': row[2],
            'referenced_column': row[3],
            'on_update': row[4],
            'on_delete': row[5]
        }
        foreign_keys.append(fk)
    return foreign_keys

def get_unique_constraints(cursor, table_name):
    """Get unique constraints for a table"""
    cursor.execute("""
        SELECT
            tc.constraint_name,
            STRING_AGG(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'UNIQUE'
        AND tc.table_schema = 'public'
        AND tc.table_name = %s
        GROUP BY tc.constraint_name
        ORDER BY tc.constraint_name;
    """, (table_name,))

    constraints = []
    for row in cursor.fetchall():
        constraints.append({
            'constraint_name': row[0],
            'columns': row[1].split(', ')
        })
    return constraints

def get_check_constraints(cursor, table_name):
    """Get check constraints for a table"""
    cursor.execute("""
        SELECT
            tc.constraint_name,
            cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
        WHERE tc.constraint_type = 'CHECK'
        AND tc.table_schema = 'public'
        AND tc.table_name = %s
        ORDER BY tc.constraint_name;
    """, (table_name,))

    constraints = []
    for row in cursor.fetchall():
        constraints.append({
            'constraint_name': row[0],
            'check_clause': row[1]
        })
    return constraints

def get_indexes(cursor, table_name):
    """Get all indexes for a table"""
    cursor.execute("""
        SELECT
            i.relname as index_name,
            am.amname as index_type,
            ARRAY_AGG(a.attname ORDER BY k.ordinality) as columns,
            ix.indisunique as is_unique,
            ix.indisprimary as is_primary,
            pg_get_indexdef(i.oid) as index_definition
        FROM pg_class t
        JOIN pg_index ix ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_am am ON i.relam = am.oid
        JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ordinality) ON true
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
        WHERE t.relname = %s
        AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        GROUP BY i.relname, am.amname, ix.indisunique, ix.indisprimary, i.oid
        ORDER BY i.relname;
    """, (table_name,))

    indexes = []
    for row in cursor.fetchall():
        indexes.append({
            'name': row[0],
            'type': row[1],
            'columns': row[2],
            'is_unique': row[3],
            'is_primary': row[4],
            'definition': row[5]
        })
    return indexes

def get_triggers(cursor, table_name):
    """Get all triggers for a table"""
    cursor.execute("""
        SELECT
            t.tgname as trigger_name,
            t.tgenabled as is_enabled,
            pg_get_triggerdef(t.oid) as trigger_definition,
            CASE
                WHEN t.tgtype & 1 = 1 THEN 'ROW'
                ELSE 'STATEMENT'
            END as level,
            CASE
                WHEN t.tgtype & 2 = 2 THEN 'BEFORE'
                WHEN t.tgtype & 64 = 64 THEN 'INSTEAD OF'
                ELSE 'AFTER'
            END as timing,
            ARRAY(
                SELECT CASE
                    WHEN t.tgtype & 4 = 4 THEN 'INSERT'
                    WHEN t.tgtype & 8 = 8 THEN 'DELETE'
                    WHEN t.tgtype & 16 = 16 THEN 'UPDATE'
                    WHEN t.tgtype & 32 = 32 THEN 'TRUNCATE'
                END
                FROM generate_series(1,5)
                WHERE (t.tgtype & (POWER(2, generate_series)::int)) != 0
            ) as events
        FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        WHERE c.relname = %s
        AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        AND NOT t.tgisinternal
        ORDER BY t.tgname;
    """, (table_name,))

    triggers = []
    for row in cursor.fetchall():
        triggers.append({
            'name': row[0],
            'enabled': row[1] == 'O',
            'definition': row[2],
            'level': row[3],
            'timing': row[4],
            'events': [e for e in row[5] if e]
        })
    return triggers

def get_table_comment(cursor, table_name):
    """Get table comment"""
    cursor.execute("""
        SELECT obj_description(
            (quote_ident('public')||'.'||quote_ident(%s))::regclass::oid,
            'pg_class'
        );
    """, (table_name,))
    result = cursor.fetchone()
    return result[0] if result and result[0] else None

def get_table_size(cursor, table_name):
    """Get table size information"""
    cursor.execute("""
        SELECT
            pg_size_pretty(pg_total_relation_size(quote_ident(%s)::regclass)) as total_size,
            pg_size_pretty(pg_relation_size(quote_ident(%s)::regclass)) as table_size,
            pg_size_pretty(pg_indexes_size(quote_ident(%s)::regclass)) as indexes_size
    """, (table_name, table_name, table_name))

    row = cursor.fetchone()
    return {
        'total_size': row[0],
        'table_size': row[1],
        'indexes_size': row[2]
    }

def extract_complete_schema():
    """Main function to extract complete database schema"""
    print(f"Starting schema extraction at {datetime.now()}")

    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    schema = {
        'extraction_date': datetime.now().isoformat(),
        'database_url': 'postgresql://neoplasias@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres',
        'user_defined_types': {},
        'tables': {},
        'relationships': [],
        'statistics': {}
    }

    print("\n1. Extracting user-defined types...")
    schema['user_defined_types'] = get_user_defined_types(cursor)
    print(f"   Found {len(schema['user_defined_types'])} user-defined types")

    print("\n2. Getting list of all tables...")
    tables = get_all_tables(cursor)
    print(f"   Found {len(tables)} tables")

    print("\n3. Extracting detailed schema for each table...")
    for i, table_name in enumerate(tables, 1):
        print(f"   [{i}/{len(tables)}] Processing {table_name}...")

        table_info = {
            'name': table_name,
            'comment': get_table_comment(cursor, table_name),
            'columns': get_table_columns(cursor, table_name),
            'primary_key': get_primary_keys(cursor, table_name),
            'foreign_keys': get_foreign_keys(cursor, table_name),
            'unique_constraints': get_unique_constraints(cursor, table_name),
            'check_constraints': get_check_constraints(cursor, table_name),
            'indexes': get_indexes(cursor, table_name),
            'triggers': get_triggers(cursor, table_name),
            'size': get_table_size(cursor, table_name)
        }

        schema['tables'][table_name] = table_info

        # Build relationships list
        for fk in table_info['foreign_keys']:
            schema['relationships'].append({
                'from_table': table_name,
                'from_column': fk['column'],
                'to_table': fk['referenced_table'],
                'to_column': fk['referenced_column'],
                'constraint_name': fk['constraint_name'],
                'on_update': fk['on_update'],
                'on_delete': fk['on_delete']
            })

    print("\n4. Calculating statistics...")
    schema['statistics'] = {
        'total_tables': len(tables),
        'total_user_defined_types': len(schema['user_defined_types']),
        'total_relationships': len(schema['relationships']),
        'total_columns': sum(len(t['columns']) for t in schema['tables'].values()),
        'total_indexes': sum(len(t['indexes']) for t in schema['tables'].values()),
        'total_triggers': sum(len(t['triggers']) for t in schema['tables'].values()),
        'tables_with_foreign_keys': sum(1 for t in schema['tables'].values() if t['foreign_keys']),
        'tables_with_unique_constraints': sum(1 for t in schema['tables'].values() if t['unique_constraints']),
        'tables_with_check_constraints': sum(1 for t in schema['tables'].values() if t['check_constraints']),
    }

    cursor.close()
    conn.close()

    print("\n5. Writing schema to JSON file...")
    output_path = '/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/docs/database/complete_schema.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n✅ Schema extraction complete!")
    print(f"   Output saved to: {output_path}")
    print(f"\n📊 Summary:")
    print(f"   - Tables: {schema['statistics']['total_tables']}")
    print(f"   - User-defined types: {schema['statistics']['total_user_defined_types']}")
    print(f"   - Total columns: {schema['statistics']['total_columns']}")
    print(f"   - Total indexes: {schema['statistics']['total_indexes']}")
    print(f"   - Total triggers: {schema['statistics']['total_triggers']}")
    print(f"   - Total relationships: {schema['statistics']['total_relationships']}")

    return schema

if __name__ == '__main__':
    extract_complete_schema()
