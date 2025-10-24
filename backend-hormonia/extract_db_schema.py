#!/usr/bin/env python3
"""
Script to extract complete database schema from AWS RDS PostgreSQL
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

# Database connection string from .env
DATABASE_URL = "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def extract_database_schema():
    """Extract complete database schema including tables, columns, constraints, indexes"""
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    schema_data = {
        "extracted_at": datetime.now().isoformat(),
        "database": "postgres",
        "host": "database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com",
        "tables": []
    }
    
    # Get all tables
    cursor.execute("""
        SELECT 
            table_schema,
            table_name,
            (SELECT COUNT(*) FROM information_schema.columns c 
             WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
    """)
    
    tables = cursor.fetchall()
    
    for table in tables:
        schema_name = table['table_schema']
        table_name = table['table_name']
        
        print(f"Extracting: {schema_name}.{table_name}")
        
        table_info = {
            "schema": schema_name,
            "name": table_name,
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
            "indexes": [],
            "constraints": [],
            "row_count": 0
        }
        
        # Get row count
        try:
            cursor.execute(f'SELECT COUNT(*) as count FROM "{schema_name}"."{table_name}"')
            table_info["row_count"] = cursor.fetchone()['count']
        except:
            table_info["row_count"] = "N/A"
        
        # Get columns
        cursor.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default,
                udt_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema_name, table_name))
        
        table_info["columns"] = [dict(col) for col in cursor.fetchall()]
        
        # Get primary keys
        cursor.execute("""
            SELECT a.attname as column_name
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
        """, (f'"{schema_name}"."{table_name}"',))
        
        table_info["primary_keys"] = [row['column_name'] for row in cursor.fetchall()]
        
        # Get foreign keys
        cursor.execute("""
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
        """, (schema_name, table_name))
        
        table_info["foreign_keys"] = [dict(fk) for fk in cursor.fetchall()]
        
        # Get indexes
        cursor.execute("""
            SELECT
                i.relname as index_name,
                a.attname as column_name,
                ix.indisunique as is_unique,
                ix.indisprimary as is_primary
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE t.relname = %s
                AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)
            ORDER BY i.relname
        """, (table_name, schema_name))
        
        table_info["indexes"] = [dict(idx) for idx in cursor.fetchall()]
        
        # Get check constraints
        cursor.execute("""
            SELECT
                con.conname as constraint_name,
                pg_get_constraintdef(con.oid) as definition
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = %s
                AND rel.relname = %s
                AND con.contype = 'c'
        """, (schema_name, table_name))
        
        table_info["constraints"] = [dict(c) for c in cursor.fetchall()]
        
        schema_data["tables"].append(table_info)
    
    cursor.close()
    conn.close()
    
    return schema_data

if __name__ == "__main__":
    print("Extracting database schema from AWS RDS...")
    schema = extract_database_schema()
    
    # Save to JSON
    with open("database_schema_complete.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n✓ Schema extracted successfully!")
    print(f"  - Total tables: {len(schema['tables'])}")
    print(f"  - Output file: database_schema_complete.json")
