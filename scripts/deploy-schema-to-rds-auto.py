#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy Schema to AWS RDS PostgreSQL (Automated Version)
Executa SCHEMA_MASTER_COMPLETO.sql no RDS sem confirmação interativa
"""

import psycopg2
from psycopg2 import sql
import sys
import os
from pathlib import Path

# Remove emojis for Windows compatibility
ROCKET = "[DEPLOY]"
CHECK = "[OK]"
ERROR = "[ERROR]"
BOOK = "[READ]"
PLUG = "[CONN]"
GEAR = "[EXEC]"
SEARCH = "[VERIFY]"
LIST = "[LIST]"
TARGET = "[NEXT]"

# RDS Configuration
RDS_CONFIG = {
    'host': 'database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com',
    'port': 5432,
    'database': 'postgres',
    'user': 'neoplasias',
    'password': 'imdA4mXfM0IxZuVj778E',
    'connect_timeout': 30,
    'sslmode': 'require'
}

# Schema file path
SCHEMA_FILE = Path(__file__).parent.parent / "backend-hormonia" / "sql" / "SCHEMA_MASTER_COMPLETO.sql"

def check_schema_state():
    """Check current RDS schema state before deployment"""
    try:
        print(f"{SEARCH} Verificando estado atual do schema...")
        conn = psycopg2.connect(**RDS_CONFIG)
        cursor = conn.cursor()

        # Check tables
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        table_count = cursor.fetchone()[0]

        # Check if MessageStatus enum exists
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'messagestatus')")
        enum_exists = cursor.fetchone()[0]

        print(f"   {CHECK} Tabelas existentes: {table_count}")
        print(f"   {CHECK} MessageStatus enum existe: {enum_exists}")

        if enum_exists:
            cursor.execute("""
                SELECT e.enumlabel
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'messagestatus'
                ORDER BY e.enumsortorder
            """)
            values = [row[0] for row in cursor.fetchall()]
            print(f"   {CHECK} Valores do enum: {values}")

        cursor.close()
        conn.close()
        print()

        return table_count, enum_exists

    except Exception as e:
        print(f"   {ERROR} Erro ao verificar estado: {e}")
        return None, None

def deploy_schema():
    """Deploy schema to RDS"""
    print(f"{ROCKET} Deploy do Schema para AWS RDS PostgreSQL")
    print("=" * 60)
    print()

    # Check current state
    table_count, enum_exists = check_schema_state()

    if table_count and table_count > 0:
        print(f"⚠ AVISO: {table_count} tabelas ja existem no banco!")
        print(f"   O schema sera executado de qualquer forma.")
        print(f"   Erros de 'already exists' serao ignorados.")
        print()

    # Check schema file exists
    if not SCHEMA_FILE.exists():
        print(f"{ERROR} Arquivo nao encontrado: {SCHEMA_FILE}")
        return False

    print(f"{BOOK} Schema: {SCHEMA_FILE.name}")
    print(f"{PLUG} Host: {RDS_CONFIG['host']}")
    print(f"   Banco: {RDS_CONFIG['database']}")
    print()

    try:
        # Read schema file
        print(f"{BOOK} Lendo arquivo SQL...")
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        lines = schema_sql.count('\n')
        print(f"   {CHECK} {lines} linhas carregadas")
        print()

        # Connect to RDS
        print(f"{PLUG} Conectando ao RDS...")
        conn = psycopg2.connect(**RDS_CONFIG)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print(f"   {CHECK} Conectado!")
        print()

        # Execute schema
        print(f"{GEAR} Executando schema SQL...")
        print("   (Isso pode levar alguns minutos...)")
        print()

        cursor.execute(schema_sql)

        print(f"   {CHECK} Schema executado com sucesso!")
        print()

        # Verify tables created
        print(f"{SEARCH} Verificando tabelas criadas...")
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        final_table_count = cursor.fetchone()[0]

        print(f"   {CHECK} Total de tabelas: {final_table_count}")
        print()

        # List some tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            LIMIT 15
        """)
        tables = cursor.fetchall()

        print(f"{LIST} Primeiras tabelas criadas:")
        for table in tables:
            print(f"   - {table[0]}")

        if final_table_count > 15:
            print(f"   ... e mais {final_table_count - 15} tabelas")

        print()

        # Verify MessageStatus enum
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'messagestatus')")
        enum_exists = cursor.fetchone()[0]

        if enum_exists:
            cursor.execute("""
                SELECT e.enumlabel
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'messagestatus'
                ORDER BY e.enumsortorder
            """)
            values = [row[0] for row in cursor.fetchall()]
            print(f"{CHECK} MessageStatus enum criado com valores: {values}")
            print()

        # Verify extensions
        cursor.execute("""
            SELECT extname
            FROM pg_extension
            WHERE extname IN ('uuid-ossp', 'pgcrypto', 'pg_trgm', 'pg_stat_statements')
        """)
        extensions = cursor.fetchall()

        print(f"{PLUG} Extensoes instaladas:")
        for ext in extensions:
            print(f"   - {ext[0]}")

        cursor.close()
        conn.close()

        print()
        print("=" * 60)
        print(f"{CHECK} DEPLOY CONCLUIDO COM SUCESSO!")
        print("=" * 60)
        print()
        print(f"{TARGET} Proximos passos:")
        print("   1. Executar migracao: cd backend-hormonia && alembic upgrade head")
        print("   2. Verificar Railway deployment")
        print("   3. Testar aplicacao")
        print()

        return True

    except psycopg2.Error as e:
        print()
        print(f"{ERROR} ERRO NO DEPLOY!")
        print(f"   {str(e)}")
        print()
        return False

    except Exception as e:
        print()
        print(f"{ERROR} ERRO INESPERADO: {str(e)}")
        print()
        return False

if __name__ == "__main__":
    print()
    print("[AVISO] Executando deploy automatico do schema no RDS...")
    print()

    success = deploy_schema()
    sys.exit(0 if success else 1)
