#!/usr/bin/env python3
"""Disparar Saga manualmente para paciente existente."""

import asyncio
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Configuração mínima para evitar imports circulares
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("DISPARANDO SAGA PARA PACIENTE EXISTENTE")
print("=" * 70)

# Ler ID do paciente
try:
    with open("last_patient_id.txt", "r", encoding="utf-8") as f:
        patient_id = f.read().strip()
except FileNotFoundError:
    print("❌ Arquivo last_patient_id.txt não encontrado")
    sys.exit(1)

print(f"\nPaciente ID: {patient_id}")

# Importar após configuração do path
from app.config import settings
from app.core.redis_client import get_redis_client
from app.models.patient import Patient
from app.models.flow import PatientFlowState, FlowTemplateVersion
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.templates.whatsapp.welcome_message import get_welcome_message

engine = create_engine(settings.DATABASE_URL)

async def trigger_saga():
    """Disparar Saga manualmente."""
    
    with Session(engine) as db:
        try:
            # 1. Buscar paciente
            print("\n=== 1. BUSCANDO PACIENTE ===")
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            
            if not patient:
                print(f"❌ Paciente {patient_id} não encontrado")
                return
            
            print(f"✅ Paciente encontrado:")
            print(f"   Nome: {patient.name}")
            print(f"   Telefone: {patient.phone}")
            print(f"   Email: {patient.email}")
            
            # 2. Criar Flow State
            print("\n=== 2. CRIANDO FLOW STATE ===")
            
            # Buscar template version ativo para initial_15_days
            template_query = text("""
                SELECT ftv.id 
                FROM flow_template_versions ftv
                JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id
                WHERE fk.kind_key = 'initial_15_days'
                  AND ftv.is_active = true
                LIMIT 1
            """)
            template_result = db.execute(template_query).fetchone()
            
            if not template_result:
                print("❌ Template 'initial_15_days' não encontrado")
                return
            
            template_version_id = template_result[0]
            
            # Verificar se já existe flow state
            existing_flow = db.query(PatientFlowState).filter(
                PatientFlowState.patient_id == patient_id
            ).first()
            
            if existing_flow:
                print(f"⚠️  Flow state já existe: {existing_flow.id}")
            else:
                flow_state = PatientFlowState(
                    patient_id=patient_id,
                    template_version_id=template_version_id,
                    current_step=0,
                    status=None
                )
                db.add(flow_state)
                db.flush()
                print(f"✅ Flow state criado: {flow_state.id}")
            
            # 3. Enviar mensagem de boas-vindas
            print("\n=== 3. ENVIANDO MENSAGEM WHATSAPP ===")
            
            # Gerar mensagem
            welcome_text = get_welcome_message(
                patient_name=patient.name,
                clinic_name=getattr(settings, "CLINIC_NAME", "Clínica"),
                support_phone=getattr(settings, "CLINIC_SUPPORT_PHONE", None)
            )
            
            # Verificar se já existe mensagem
            existing_msg = db.query(Message).filter(
                Message.patient_id == patient_id,
                Message.direction == MessageDirection.OUTBOUND
            ).first()
            
            if existing_msg:
                print(f"⚠️  Mensagem já existe: {existing_msg.id}")
            else:
                message = Message(
                    patient_id=patient_id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=welcome_text,
                    idempotency_key=f"onboarding_{patient_id}_initial",
                    status=MessageStatus.PENDING
                )
                db.add(message)
                db.flush()
                print(f"✅ Mensagem criada: {message.id}")
                print(f"   Status: {message.status}")
                print(f"   Conteúdo (preview): {welcome_text[:100]}...")
            
            # 4. Commit tudo
            db.commit()
            print("\n✅ TODAS AS ALTERAÇÕES FORAM SALVAS!")
            
            # 5. Tentar enviar via Evolution API
            print("\n=== 4. TENTANDO ENVIAR VIA EVOLUTION API ===")
            try:
                from app.integrations.evolution import EvolutionClient
                evolution = EvolutionClient()
                
                # Enviar mensagem
                response = await evolution.send_text_message(
                    phone=patient.phone,
                    message=welcome_text
                )
                
                if response:
                    print(f"✅ Mensagem enviada via Evolution!")
                    print(f"   Response: {response}")
                    
                    # Atualizar status da mensagem
                    if not existing_msg:
                        message.status = MessageStatus.SENT
                        message.whatsapp_id = response.get("key", {}).get("id")
                        db.commit()
                else:
                    print("⚠️  Evolution retornou resposta vazia")
                    
            except Exception as e:
                print(f"⚠️  Erro ao enviar via Evolution: {e}")
                print("   (Mensagem foi criada no banco, mas não enviada)")
            
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise

# Executar
asyncio.run(trigger_saga())

# Validar
print("\n" + "=" * 70)
print("VALIDANDO RESULTADO")
print("=" * 70)

import subprocess
import time
time.sleep(2)

result = subprocess.run(
    [r".\venv\Scripts\python.exe", "check_saga.py"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace"
)
print(result.stdout)

print("\n" + "=" * 70)
print("✅ PROCESSO COMPLETO!")
print("=" * 70)
print(f"\nPaciente: {patient_id}")
print("Telefone: +5594991307744")
print("\nVerifique:")
print("  1. Flow state criado")
print("  2. Mensagem WhatsApp registrada")
print("  3. Se Evolution está configurado, mensagem foi enviada")
