#!/usr/bin/env python3
"""Limpar TODOS os dados de teste e paciente real do banco de dados."""

from sqlalchemy import create_engine, text
from app.config import settings

print("=" * 70)
print("LIMPEZA COMPLETA DE DADOS DE TESTE")
print("=" * 70)

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    # 1. Deletar sagas de teste
    print("\n=== 1. DELETANDO SAGAS DE TESTE ===")
    saga_result = conn.execute(text("""
        DELETE FROM patient_onboarding_saga 
        WHERE patient_id IN (
            SELECT id FROM patients 
            WHERE email LIKE '%@test.com' 
               OR email LIKE 'testsaga%@gmail.com'
               OR email LIKE 'saga.test%@gmail.com'
               OR email LIKE 'teste.onboarding%@gmail.com'
               OR name LIKE 'Test Saga%'
               OR name LIKE 'Paciente Teste%'
               OR name LIKE 'Paciente Saga%'
               OR phone LIKE '+55949%'
        )
    """))
    print(f"   ✅ {saga_result.rowcount} sagas de teste removidas")
    
    # 2. Deletar mensagens de teste
    print("\n=== 2. DELETANDO MENSAGENS DE TESTE ===")
    msg_result = conn.execute(text("""
        DELETE FROM messages 
        WHERE patient_id IN (
            SELECT id FROM patients 
            WHERE email LIKE '%@test.com' 
               OR email LIKE 'testsaga%@gmail.com'
               OR email LIKE 'saga.test%@gmail.com'
               OR email LIKE 'teste.onboarding%@gmail.com'
               OR name LIKE 'Test Saga%'
               OR name LIKE 'Paciente Teste%'
               OR name LIKE 'Paciente Saga%'
               OR phone LIKE '+55949%'
        )
    """))
    print(f"   ✅ {msg_result.rowcount} mensagens de teste removidas")
    
    # 3. Deletar flow states de teste
    print("\n=== 3. DELETANDO FLOW STATES DE TESTE ===")
    flow_result = conn.execute(text("""
        DELETE FROM patient_flow_states 
        WHERE patient_id IN (
            SELECT id FROM patients 
            WHERE email LIKE '%@test.com' 
               OR email LIKE 'testsaga%@gmail.com'
               OR email LIKE 'saga.test%@gmail.com'
               OR email LIKE 'teste.onboarding%@gmail.com'
               OR name LIKE 'Test Saga%'
               OR name LIKE 'Paciente Teste%'
               OR name LIKE 'Paciente Saga%'
               OR phone LIKE '+55949%'
        )
    """))
    print(f"   ✅ {flow_result.rowcount} flow states de teste removidos")
    
    # 4. Deletar pacientes de teste
    print("\n=== 4. DELETANDO PACIENTES DE TESTE ===")
    patient_result = conn.execute(text("""
        DELETE FROM patients 
        WHERE email LIKE '%@test.com' 
           OR email LIKE 'testsaga%@gmail.com'
           OR email LIKE 'saga.test%@gmail.com'
           OR email LIKE 'teste.onboarding%@gmail.com'
           OR name LIKE 'Test Saga%'
           OR name LIKE 'Paciente Teste%'
           OR name LIKE 'Paciente Saga%'
           OR phone LIKE '+55949%'
    """))
    print(f"   ✅ {patient_result.rowcount} pacientes de teste removidos")
    
    # 5. Deletar paciente real específico (se existir)
    print("\n=== 5. DELETANDO PACIENTE REAL ANTERIOR (se existir) ===")
    
    # Primeiro deletar sagas do paciente real
    conn.execute(text("""
        DELETE FROM patient_onboarding_saga 
        WHERE patient_id IN (
            SELECT id FROM patients WHERE phone = '+5594991307744'
        )
    """))
    
    # Deletar mensagens do paciente real
    conn.execute(text("""
        DELETE FROM messages 
        WHERE patient_id IN (
            SELECT id FROM patients WHERE phone = '+5594991307744'
        )
    """))
    
    # Deletar flow states do paciente real
    conn.execute(text("""
        DELETE FROM patient_flow_states 
        WHERE patient_id IN (
            SELECT id FROM patients WHERE phone = '+5594991307744'
        )
    """))
    
    # Deletar paciente real
    real_patient_result = conn.execute(text("""
        DELETE FROM patients WHERE phone = '+5594991307744'
    """))
    print(f"   ✅ {real_patient_result.rowcount} paciente(s) real(is) removido(s)")
    
    # Commit todas as alterações
    conn.commit()

print("\n" + "=" * 70)
print("✅ LIMPEZA COMPLETA CONCLUÍDA!")
print("=" * 70)
