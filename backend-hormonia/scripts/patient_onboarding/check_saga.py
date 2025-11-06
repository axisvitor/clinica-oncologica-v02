#!/usr/bin/env python3
"""Script para verificar se a Saga foi executada e validar o fluxo completo."""

import sys
from sqlalchemy import create_engine, text
from app.config import settings

# Ler ID do paciente
try:
    with open("last_patient_id.txt", "r", encoding="utf-8-sig") as f:
        patient_id = f.read().strip()
except FileNotFoundError:
    print("❌ Arquivo last_patient_id.txt não encontrado")
    sys.exit(1)

print(f"Verificando Saga para paciente: {patient_id}")
print("=" * 60)

# Conectar ao banco
engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    # 1. Verificar Saga
    print("\n=== 1. SAGA DE ONBOARDING ===")
    saga_query = text("""
        SELECT id, patient_id, doctor_id, status, current_step, 
               started_at, completed_at, error_message
        FROM patient_onboarding_saga 
        WHERE patient_id = :patient_id
        ORDER BY started_at DESC
        LIMIT 1
    """)
    saga_result = conn.execute(saga_query, {"patient_id": patient_id}).fetchone()
    
    if saga_result:
        print(f"✅ Saga encontrada!")
        print(f"   ID: {saga_result[0]}")
        print(f"   Status: {saga_result[3]}")
        print(f"   Step: {saga_result[4]}")
        print(f"   Iniciada: {saga_result[5]}")
        print(f"   Completada: {saga_result[6]}")
        if saga_result[7]:
            print(f"   Erro: {saga_result[7]}")
    else:
        print("⚠️  Saga não encontrada (pode ter sido executada em modo direto)")
    
    # 2. Verificar Mensagens WhatsApp
    print("\n=== 2. MENSAGENS WHATSAPP ===")
    msg_query = text("""
        SELECT id, content, status, sent_at, delivered_at
        FROM messages 
        WHERE patient_id = :patient_id
        ORDER BY sent_at DESC
        LIMIT 3
    """)
    msg_results = conn.execute(msg_query, {"patient_id": patient_id}).fetchall()
    
    if msg_results:
        print(f"✅ {len(msg_results)} mensagem(ns) encontrada(s):")
        for msg in msg_results:
            content_preview = msg[1][:50] + "..." if len(msg[1]) > 50 else msg[1]
            print(f"   - [{msg[2]}] {content_preview}")
            print(f"     Enviada: {msg[3]}")
    else:
        print("⚠️  Nenhuma mensagem encontrada")
    
    # 3. Verificar Fluxo Diário
    print("\n=== 3. FLUXO DE ACOMPANHAMENTO DIÁRIO ===")
    flow_query = text("""
        SELECT fs.id,
               fk.kind_key AS flow_type,
               fs.current_step,
               fs.status,
               fs.started_at,
               fs.last_interaction_at
        FROM patient_flow_states fs
        JOIN flow_template_versions ftv ON ftv.id = fs.flow_template_version_id
        JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id
        WHERE fs.patient_id = :patient_id
        ORDER BY fs.started_at DESC
        LIMIT 1
    """)
    flow_result = conn.execute(flow_query, {"patient_id": patient_id}).fetchone()
    
    if flow_result:
        print(f"✅ Fluxo encontrado!")
        print(f"   ID: {flow_result[0]}")
        print(f"   Tipo: {flow_result[1]}")
        print(f"   Step atual: {flow_result[2]}")
        print(f"   Status: {flow_result[3]}")
        print(f"   Iniciado: {flow_result[4]}")
        print(f"   Última interação: {flow_result[5]}")
    else:
        print("⚠️  Fluxo não encontrado")
    
    # 4. Verificar Paciente
    print("\n=== 4. DADOS DO PACIENTE ===")
    patient_query = text("""
        SELECT id, name, phone, email, created_at
        FROM patients 
        WHERE id = :patient_id
    """)
    patient_result = conn.execute(patient_query, {"patient_id": patient_id}).fetchone()
    
    if patient_result:
        print(f"✅ Paciente encontrado!")
        print(f"   Nome: {patient_result[1]}")
        print(f"   Telefone: {patient_result[2]}")
        print(f"   Email: {patient_result[3]}")
        print(f"   Criado em: {patient_result[4]}")
    else:
        print("❌ Paciente não encontrado no banco!")

print("\n" + "=" * 60)
print("Verificação completa!")
