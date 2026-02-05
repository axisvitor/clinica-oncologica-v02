"""
Script para listar todas as tabelas e colunas do banco de dados.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

with conn.cursor() as cur:
    # Listar TODAS as tabelas do banco
    print('=' * 70)
    print('TODAS AS TABELAS DO BANCO DE DADOS')
    print('=' * 70)
    cur.execute('''
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    ''')
    tables = [r['table_name'] for r in cur.fetchall()]
    for t in tables:
        print(f'  - {t}')
    
    print()
    print('=' * 70)
    print('ESTRUTURA DE CADA TABELA')
    print('=' * 70)
    
    for table in tables:
        print()
        print(f'### {table.upper()} ###')
        cur.execute('''
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
        ''', (table,))
        cols = cur.fetchall()
        for c in cols:
            nullable = 'NULL' if c['is_nullable'] == 'YES' else 'NOT NULL'
            print(f"  {c['column_name']:40} {c['data_type']:30} {nullable}")

conn.close()
print()
print('SCHEMA COMPLETO LISTADO!')
