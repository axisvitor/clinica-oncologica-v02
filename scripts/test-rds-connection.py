#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test RDS PostgreSQL Connection
Testa conectividade com AWS RDS antes de executar schema
"""

import psycopg2
from psycopg2 import sql
import sys

# Remove emojis for Windows compatibility
PLUG = "[CONN]"
CHECK = "[OK]"
WARN = "[WARN]"
ERROR = "[ERROR]"
CHART = "[INFO]"
TARGET = "[NEXT]"
SEARCH = "[DEBUG]"

# RDS Configuration
# Try different database names
DATABASES_TO_TRY = ['postgres', 'database-clinica-neoplasias', 'clinica_neoplasias']
# Try different usernames (neoplasias is the correct master username from AWS Console)
USERNAMES_TO_TRY = ['neoplasias', 'postgres', 'admin', 'database-clinica-neoplasias', 'master', 'root']

RDS_CONFIG_BASE = {
    'host': 'database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com',
    'port': 5432,
    'password': 'imdA4mXfM0IxZuVj778E',
    'connect_timeout': 10,
    'sslmode': 'require'  # SSL required for RDS
}

def test_connection():
    """Test basic connection to RDS"""
    print(f"{PLUG} Testando conexao com AWS RDS PostgreSQL...")
    print(f"   Host: {RDS_CONFIG_BASE['host']}")
    print(f"   Porta: {RDS_CONFIG_BASE['port']}")
    print()

    # Try connecting with different username and database combinations
    conn = None
    cursor = None
    successful_db = None
    successful_user = None

    for username in USERNAMES_TO_TRY:
        if conn:
            break
        print(f"{SEARCH} Tentando usuario: {username}")

        for db_name in DATABASES_TO_TRY:
            try:
                print(f"   Tentando banco: {db_name}...")
                config = {**RDS_CONFIG_BASE, 'database': db_name, 'user': username}
                conn = psycopg2.connect(**config)
                cursor = conn.cursor()
                successful_db = db_name
                successful_user = username
                print(f"   {CHECK} SUCESSO! Usuario: {username}, Banco: {db_name}")
                break
            except psycopg2.OperationalError as e:
                error_msg = str(e)
                if "does not exist" in error_msg:
                    print(f"   {WARN} Banco '{db_name}' nao existe")
                    continue
                elif "password authentication failed" in error_msg:
                    print(f"   {WARN} Senha incorreta para usuario '{username}'")
                    break  # Try next username
                elif "no pg_hba.conf entry" in error_msg:
                    print(f"   {WARN} Usuario '{username}' sem permissao de acesso")
                    break  # Try next username
                else:
                    print(f"   {WARN} Erro: {error_msg[:100]}")
                    continue

    if not conn:
        print(f"\n{ERROR} Nao foi possivel conectar!")
        print(f"\n{SEARCH} Usuarios tentados: {', '.join(USERNAMES_TO_TRY)}")
        print(f"{SEARCH} Bancos tentados: {', '.join(DATABASES_TO_TRY)}")
        print(f"\n{TARGET} Verifique no AWS Console:")
        print("   1. Master Username correto")
        print("   2. Senha atual (pode ter sido resetada)")
        print("   3. Security Group permitindo seu IP")
        return False

    print()

    try:

        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        print(f"{CHECK} CONEXAO ESTABELECIDA COM SUCESSO!")
        print(f"   Usuario: {successful_user}")
        print(f"   Banco conectado: {successful_db}")
        print(f"   PostgreSQL Version: {version}")
        print()

        # Check existing tables
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        table_count = cursor.fetchone()[0]

        print(f"{CHART} Tabelas existentes: {table_count}")

        if table_count == 0:
            print(f"   {CHECK} Banco vazio - pronto para receber o schema!")
        else:
            print(f"   {WARN} Banco ja contem tabelas")
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                LIMIT 10
            """)
            tables = cursor.fetchall()
            print("   Primeiras tabelas:")
            for table in tables:
                print(f"      - {table[0]}")

        cursor.close()
        conn.close()

        print()
        print(f"{TARGET} Proximo passo: Executar SCHEMA_MASTER_COMPLETO.sql")
        return True

    except psycopg2.OperationalError as e:
        print(f"{ERROR} ERRO DE CONEXAO!")
        print(f"   {str(e)}")
        print()
        print(f"{SEARCH} Possiveis causas:")
        print("   1. Security Group nao esta configurado corretamente")
        print("   2. RDS ainda esta inicializando (aguarde alguns minutos)")
        print("   3. Credenciais incorretas")
        print("   4. Firewall local bloqueando conexao")
        return False

    except Exception as e:
        print(f"{ERROR} ERRO INESPERADO: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
