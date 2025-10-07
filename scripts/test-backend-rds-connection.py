#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Backend Connection to AWS RDS
Testa se o backend consegue conectar ao RDS usando SQLAlchemy
"""

import sys
import os

# Set development mode for testing
os.environ['ENVIRONMENT'] = 'development'
os.environ['DEBUG'] = 'true'

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# Console symbols
CHECK = "[OK]"
ERROR = "[ERROR]"
INFO = "[INFO]"
WARN = "[WARN]"

# RDS Connection String
DATABASE_URL = "postgresql+psycopg://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def test_backend_connection():
    """Test SQLAlchemy connection to RDS"""
    print(f"{INFO} Testando conexao do backend com AWS RDS...")
    print()

    try:
        # Create engine
        print(f"{INFO} Criando SQLAlchemy engine...")
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,  # No pooling for test
            echo=False
        )

        print(f"{CHECK} Engine criado com sucesso!")
        print()

        # Test connection
        print(f"{INFO} Testando conexao...")
        with engine.connect() as conn:
            # Test basic query
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"{CHECK} Conexao estabelecida!")
            print(f"   PostgreSQL: {version.split(',')[0]}")
            print()

            # Count tables
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            table_count = result.fetchone()[0]
            print(f"{CHECK} Tabelas encontradas: {table_count}")
            print()

            # Check alembic version
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'alembic_version'
                )
            """))
            has_alembic = result.fetchone()[0]

            if has_alembic:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                row = result.fetchone()
                if row:
                    print(f"{CHECK} Alembic version: {row[0]}")
                else:
                    print(f"{WARN} Alembic table existe mas esta vazia (nenhuma migracao aplicada)")
            else:
                print(f"{WARN} Alembic nao configurado ainda")
            print()

            # List some tables
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                LIMIT 10
            """))
            tables = result.fetchall()

            print(f"{INFO} Primeiras tabelas:")
            for table in tables:
                print(f"   - {table[0]}")
            print()

        print(f"{CHECK} TESTE CONCLUIDO COM SUCESSO!")
        print()
        print(f"{INFO} O backend esta pronto para conectar ao RDS!")
        return True

    except Exception as e:
        print(f"{ERROR} Erro ao conectar:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_backend_connection()
    sys.exit(0 if success else 1)
