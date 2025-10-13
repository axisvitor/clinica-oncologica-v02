#!/usr/bin/env python3
"""
Verificar estrutura da tabela patients
"""
import sys
sys.path.append('.')

from app.database import get_scoped_session
from sqlalchemy import text

def check_patients_table():
    """Verificar estrutura da tabela patients"""
    
    with get_scoped_session() as db:
        # Verificar se tabela existe
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%patient%'
        """))
        
        tables = [row[0] for row in result.fetchall()]
        print("Tabelas relacionadas a patient:")
        for table in tables:
            print(f"  - {table}")
        
        if 'patients' in tables:
            # Verificar colunas da tabela patients
            result = db.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'patients' 
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            print(f"\nColunas da tabela 'patients' ({len(columns)} colunas):")
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"  - {col[0]} ({col[1]}) {nullable}")
        else:
            print("\n❌ Tabela 'patients' não encontrada!")

if __name__ == "__main__":
    check_patients_table()