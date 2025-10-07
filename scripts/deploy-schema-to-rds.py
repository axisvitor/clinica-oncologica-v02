#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deploy Schema to AWS RDS PostgreSQL
Executa SCHEMA_MASTER_COMPLETO.sql no RDS
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
    'user': 'neoplasias',  # Master username from AWS Console
    'password': 'imdA4mXfM0IxZuVj778E',
    'connect_timeout': 30,
    'sslmode': 'require'  # SSL required for RDS
}

# Schema file path
SCHEMA_FILE = Path(__file__).parent.parent / "backend-hormonia" / "sql" / "SCHEMA_MASTER_COMPLETO.sql"

def deploy_schema():
    """Deploy schema to RDS"""
    print(f"{ROCKET} Deploy do Schema para AWS RDS PostgreSQL")
    print("=" * 60)
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
        table_count = cursor.fetchone()[0]

        print(f"   {CHECK} Total de tabelas: {table_count}")
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

        if table_count > 15:
            print(f"   ... e mais {table_count - 15} tabelas")

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
        print("   1. Atualizar variaveis de ambiente (.env)")
        print("   2. Atualizar variaveis no Railway")
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
    input("[ATENCAO] Este script vai executar o schema completo no RDS.\n"
          "   Pressione ENTER para continuar ou Ctrl+C para cancelar... ")
    print()

    success = deploy_schema()
    sys.exit(0 if success else 1)
