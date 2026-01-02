"""
Teste de Simulação de 30 Dias de Envios Diários
Simula o fluxo completo de mensagens para um paciente ao longo de 30 dias.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import random

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def generate_valid_cpf() -> str:
    def calc(s, w):
        r = sum(int(d) * ww for d, ww in zip(s, w)) % 11
        return '0' if r < 2 else str(11 - r)
    b = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    return b + calc(b, [10,9,8,7,6,5,4,3,2]) + calc(b + calc(b, [10,9,8,7,6,5,4,3,2]), [11,10,9,8,7,6,5,4,3,2])


class MockWhatsApp:
    """Mock que captura mensagens enviadas."""
    messages = []

    @classmethod
    def send(cls, day, phone, content):
        cls.messages.append({
            "day": day,
            "phone": phone,
            "content": content[:80] if content else "",
            "timestamp": datetime.now().isoformat()
        })
        print(f"   📱 [Mock WhatsApp] Enviando para {phone[:12]}...")


async def run_simulation():
    print("=" * 70)
    print("🧪 SIMULAÇÃO DE 30 DIAS DE ENVIOS")
    print("=" * 70)

    from app.core.database import SessionLocal
    from app.schemas.patient import PatientCreate
    from app.orchestration.saga_orchestrator import SagaOrchestrator
    from app.models.patient import Patient
    from app.models.message import Message, MessageStatus
    from app.models.template import MessageTemplate

    db = SessionLocal()

    try:
        # ========================================
        # 1. CRIAR PACIENTE
        # ========================================
        print("\n📋 PASSO 1: Criando paciente...")

        uid = int(datetime.now().timestamp()) % 100000
        patient_data = PatientCreate(
            name=f"Paciente Sim30 {uid}",
            phone=f"+5511999{uid:05d}",
            email=f"sim{uid}@teste.com",
            cpf=generate_valid_cpf(),
            birth_date="1985-05-15"
        )

        saga = SagaOrchestrator(db)
        result = await saga.execute_patient_onboarding_saga(
            patient_data=patient_data,
            doctor_id=None
        )

        patient = result.patient if hasattr(result, 'patient') else result
        if not patient:
            print("❌ Falha ao criar paciente")
            return

        print(f"✅ Paciente: {patient.name}")
        print(f"   ID: {patient.id}")
        print(f"   Flow: {patient.flow_state}")

        # ========================================
        # 2. BUSCAR TEMPLATES DE MENSAGENS
        # ========================================
        print("\n📋 PASSO 2: Buscando templates...")

        templates = db.query(MessageTemplate).filter(
            MessageTemplate.is_active == True
        ).all()

        print(f"   Templates ativos: {len(templates)}")
        for t in templates[:5]:
            print(f"   - {t.name}")

        # ========================================
        # 3. SIMULAR 30 DIAS
        # ========================================
        print("\n📅 PASSO 3: Simulando 30 dias de envios...")
        print("-" * 70)

        messages_created = []
        base_time = datetime.now(timezone.utc)

        for day in range(1, 31):
            day_time = base_time + timedelta(days=day-1)
            print(f"\n📆 DIA {day:02d} ({day_time.strftime('%d/%m')})")

            # Atualizar current_day do paciente
            patient_obj = db.query(Patient).filter(Patient.id == patient.id).first()
            patient_obj.current_day = day

            # Buscar template para o dia
            day_template = None
            for t in templates:
                if f"day_{day}" in t.name.lower() or f"dia_{day}" in t.name.lower():
                    day_template = t
                    break

            # Se não encontrou template específico, usar template genérico
            if not day_template:
                # Usar primeiro template de follow-up disponível
                for t in templates:
                    if "follow" in t.name.lower() or "daily" in t.name.lower():
                        day_template = t
                        break

            # Criar mensagem do dia
            if day_template:
                try:
                    content = day_template.content.format(
                        patient_name=patient.name,
                        day=day,
                        treatment_day=day
                    ) if day_template.content else f"Mensagem do dia {day}"
                except:
                    content = day_template.content or f"Mensagem do dia {day}"

                msg_id = uuid4()
                message = Message(
                    id=msg_id,
                    patient_id=patient.id,
                    content=content,
                    direction="outbound",
                    status=MessageStatus.PENDING,
                    created_at=day_time,
                    scheduled_for=day_time,
                    idempotency_key=f"sim30-{patient.id}-day{day}-{msg_id}"
                )
                db.add(message)
                messages_created.append({"day": day, "content": content[:60]})
                print(f"   ✅ Mensagem criada: {content[:50]}...")

                # Mock do envio
                MockWhatsApp.send(day, patient_data.phone, content)

            else:
                # Criar mensagem genérica
                content = f"Olá {patient.name}! Este é seu acompanhamento do dia {day}. Como você está se sentindo hoje?"
                msg_id = uuid4()
                message = Message(
                    id=msg_id,
                    patient_id=patient.id,
                    content=content,
                    direction="outbound",
                    status=MessageStatus.PENDING,
                    created_at=day_time,
                    scheduled_for=day_time,
                    idempotency_key=f"sim30-{patient.id}-day{day}-{msg_id}"
                )
                db.add(message)
                messages_created.append({"day": day, "content": content[:60]})
                print(f"   ✅ Mensagem genérica: {content[:50]}...")
                MockWhatsApp.send(day, patient_data.phone, content)

            db.flush()

        db.commit()

        # ========================================
        # 4. RESUMO
        # ========================================
        print("\n" + "=" * 70)
        print("📊 RESUMO DA SIMULAÇÃO")
        print("=" * 70)

        # Contar mensagens no banco
        total_messages = db.query(Message).filter(
            Message.patient_id == patient.id
        ).count()

        print(f"\n📬 Mensagens criadas no banco: {total_messages}")
        print(f"📱 Mensagens via Mock WhatsApp: {len(MockWhatsApp.messages)}")

        # Verificar status
        pending = db.query(Message).filter(
            Message.patient_id == patient.id,
            Message.status == MessageStatus.PENDING
        ).count()

        print("\n📈 Status das mensagens:")
        print(f"   - PENDING: {pending}")
        print(f"   - Total: {total_messages}")

        # Listar alguns exemplos
        print("\n📝 Exemplos de mensagens (primeiros 5 dias):")
        for m in messages_created[:5]:
            print(f"   Dia {m['day']:02d}: {m['content']}...")

        print("\n📝 Últimos 5 dias:")
        for m in messages_created[-5:]:
            print(f"   Dia {m['day']:02d}: {m['content']}...")

        # Estado final
        patient_final = db.query(Patient).filter(Patient.id == patient.id).first()
        print("\n🏁 Estado final:")
        print(f"   - Current Day: {patient_final.current_day}")
        print(f"   - Flow State: {patient_final.flow_state}")

        print("\n" + "=" * 70)
        print("✅ SIMULAÇÃO DE 30 DIAS CONCLUÍDA COM SUCESSO!")
        print("=" * 70)

        return {
            "success": True,
            "patient_id": str(patient.id),
            "messages_created": total_messages,
            "mock_messages": len(MockWhatsApp.messages)
        }

    except Exception as e:
        logger.exception("Erro")
        print(f"\n❌ ERRO: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

    finally:
        db.close()


if __name__ == "__main__":
    result = asyncio.run(run_simulation())
    if result.get("success"):
        print(f"\n🎉 Sucesso! {result.get('messages_created')} mensagens criadas.")
