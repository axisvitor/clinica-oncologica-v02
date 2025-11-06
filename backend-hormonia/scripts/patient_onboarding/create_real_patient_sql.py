#!/usr/bin/env python3
"""Criar paciente real usando SQL direto e disparar Saga via API interna."""

import uuid
import requests
from datetime import date
from sqlalchemy import create_engine, text
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

print("=" * 70)
print("CRIAÇÃO DE PACIENTE REAL - SQL DIRETO")
print("=" * 70)

# Dados do paciente REAL
patient_id = str(uuid.uuid4())
patient_data = {
    "id": patient_id,
    "name": "Paciente Real Teste",
    "phone": "+5594991307744",
    "email": "paciente.real@neoplasiaslitoral.com",
    "cpf": "12345678901",
    "birth_date": "1980-01-15",
    "gender": "M",
}

print("\nPaciente:")
print(f"  Nome: {patient_data['name']}")
print(f"  Telefone: {patient_data['phone']}")
print(f"  Email: {patient_data['email']}")

# Conectar ao banco
engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    # 1. Obter ID do doctor
    print("\n=== 1. OBTENDO DOCTOR ===")
    doctor_query = text("""
        SELECT id, email FROM users 
        WHERE email = 'admin@neoplasiaslitoral.com'
        LIMIT 1
    """)
    doctor_result = conn.execute(doctor_query).fetchone()
    
    if not doctor_result:
        print("❌ Doctor admin não encontrado no banco")
        sys.exit(1)
    
    doctor_id = str(doctor_result[0])
    print(f"✅ Doctor: {doctor_result[1]}")
    print(f"   ID: {doctor_id}")
    
    # 2. Inserir paciente diretamente no banco
    print("\n=== 2. INSERINDO PACIENTE NO BANCO ===")
    
    insert_query = text("""
        INSERT INTO patients (
            id, name, phone, email, cpf, birth_date, doctor_id,
            flow_state, current_day, created_at, updated_at
        ) VALUES (
            :id, :name, :phone, :email, :cpf, :birth_date, :doctor_id,
            'onboarding', 0, NOW(), NOW()
        )
        RETURNING id, name, phone, email
    """)
    
    try:
        result = conn.execute(insert_query, {
            "id": patient_id,
            "name": patient_data["name"],
            "phone": patient_data["phone"],
            "email": patient_data["email"],
            "cpf": patient_data["cpf"],
            "birth_date": patient_data["birth_date"],
            "doctor_id": doctor_id
        })
        
        patient_row = result.fetchone()
        conn.commit()
        
        print(f"✅ PACIENTE INSERIDO!")
        print(f"   ID: {patient_row[0]}")
        print(f"   Nome: {patient_row[1]}")
        print(f"   Telefone: {patient_row[2]}")
        print(f"   Email: {patient_row[3]}")
        
        # Salvar ID para validação
        with open("last_patient_id.txt", "w", encoding="utf-8") as f:
            f.write(str(patient_row[0]))
        
    except Exception as e:
        print(f"❌ ERRO ao inserir paciente: {e}")
        conn.rollback()
        sys.exit(1)

# 3. Disparar Saga manualmente via chamada interna
print("\n=== 3. DISPARANDO SAGA MANUALMENTE ===")
print("Nota: A Saga deveria ter sido disparada automaticamente pelo endpoint.")
print("Como criamos direto no banco, precisamos disparar manualmente.")

# Tentar via API local
try:
    # Obter token Firebase
    print("\nObtendo token Firebase...")
    import subprocess
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "get_firebase_token.ps1"],  # pragma: allowlist secret - token gerado dinamicamente
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    if result.returncode == 0:
        firebase_token = result.stdout.strip().split('\n')[-1]  # Última linha
        print("✅ Token obtido")
        
        # Criar flow state e mensagem via API (se houver endpoint)
        print("\n⚠️  Saga não foi disparada automaticamente (paciente criado via SQL)")
        print("   Para fluxo completo, use o endpoint da API que dispara a Saga")
        
    else:
        print("⚠️  Não foi possível obter token Firebase")
        
except Exception as e:
    print(f"⚠️  Erro ao tentar disparar Saga: {e}")

# 4. Validar no banco
print("\n" + "=" * 70)
print("VALIDANDO DADOS NO BANCO")
print("=" * 70)

import subprocess
import time
time.sleep(2)

result = subprocess.run(
    [r".\venv\Scripts\python.exe", "check_saga.py"],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print("\n" + "=" * 70)
print("✅ PACIENTE CRIADO (SEM SAGA AUTOMÁTICA)")
print("=" * 70)
print("\n⚠️  IMPORTANTE:")
print("  - Paciente foi criado diretamente no banco")
print("  - Saga NÃO foi executada (sem flow state, sem mensagem WhatsApp)")
print("  - Para testar o fluxo completo com Saga, use o endpoint da API")
print(f"\n  ID do paciente: {patient_id}")
print(f"  Telefone: {patient_data['phone']}")
