#!/usr/bin/env python3
"""Limpar pacientes de teste do banco de dados."""

from sqlalchemy import create_engine, text
from app.config import settings

print("Limpando pacientes de teste...")

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    # Deletar pacientes de teste
    result = conn.execute(text("""
        DELETE FROM patients 
        WHERE email LIKE '%@test.com' 
           OR email LIKE 'testsaga%@gmail.com'
           OR email LIKE 'saga.test%@gmail.com'
           OR email LIKE 'teste.onboarding%@gmail.com'
           OR name LIKE 'Test Saga%'
           OR name LIKE 'Paciente Teste%'
           OR name LIKE 'Paciente Saga%'
    """))
    
    conn.commit()
    
    print(f"✅ {result.rowcount} pacientes de teste removidos")

print("Concluído!")
