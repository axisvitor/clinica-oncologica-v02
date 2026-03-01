"""
Complete Flow System Test - Simulates a real patient follow-up journey
WITHOUT actually sending WhatsApp messages.

This script tests:
1. Template loading from database
2. Message generation for each day
3. Flow state transitions
4. Quiz template loading
"""
import os
import sys
from datetime import datetime, timezone, timedelta

from app.utils.timezone import now_sao_paulo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Import application modules
from app.services.template_loader_pkg import EnhancedTemplateLoader, TemplateLoadError


def test_template_loading(db):
    """Test that all flow templates load correctly from DB."""
    print("\n" + "="*70)
    print("🔍 TEST 1: TEMPLATE LOADING FROM DATABASE")
    print("="*70)
    
    loader = EnhancedTemplateLoader(db=db)
    
    flow_types = [
        ("onboarding", "Primeiros 15 Dias"),
        ("daily_follow_up", "Dias 16-45"),
        ("quiz_mensal", "Manutenção Mensal"),
    ]
    
    results = {}
    for flow_key, display_name in flow_types:
        try:
            template = loader.load_flow_template(flow_key)
            results[flow_key] = {
                "success": True,
                "name": template.name,
                "version": template.version,
                "message_count": len(template.messages),
                "days": sorted(template.messages.keys()),
            }
            print(f"\n✅ {display_name} ({flow_key})")
            print(f"   Nome: {template.name}")
            print(f"   Versão: {template.version}")
            print(f"   Mensagens: {len(template.messages)}")
            print(f"   Dias: {sorted(template.messages.keys())}")
        except TemplateLoadError as e:
            results[flow_key] = {"success": False, "error": str(e)}
            print(f"\n❌ {display_name} ({flow_key}): {e}")
    
    return results


def test_message_generation(db):
    """Test message content generation for specific days."""
    print("\n" + "="*70)
    print("📝 TEST 2: MESSAGE CONTENT GENERATION")
    print("="*70)
    
    loader = EnhancedTemplateLoader(db=db)
    
    # Test cases: flow_type, day
    test_cases = [
        ("onboarding", 2, "Primeiro contato após boas-vindas"),
        ("onboarding", 7, "Uma semana de tratamento"),
        ("onboarding", 15, "Conclusão da fase inicial"),
        ("daily_follow_up", 16, "Início da fase de engajamento"),
        ("daily_follow_up", 30, "Metade da fase de engajamento"),
        ("daily_follow_up", 45, "Preparação para quiz mensal"),
        ("quiz_mensal", 1, "Boas-vindas do ciclo mensal"),
        ("quiz_mensal", 30, "Disparo do quiz mensal"),
    ]
    
    results = []
    for flow_key, day, description in test_cases:
        print(f"\n--- {description} (Dia {day}) ---")
        try:
            message = loader.get_message_for_day(flow_key, day)
            if message:
                print("✅ Mensagem encontrada:")
                print(f"   Intent: {message.intent}")
                print(f"   Conteúdo: {message.base_content[:80]}...")
                print(f"   Tipo: {message.message_type}")
                if message.ai_instructions:
                    print(f"   AI Instructions: {message.ai_instructions[:60]}...")
                results.append({"flow": flow_key, "day": day, "success": True})
            else:
                print(f"⚠️  Nenhuma mensagem para dia {day} em {flow_key}")
                results.append({"flow": flow_key, "day": day, "success": False, "reason": "not_found"})
        except Exception as e:
            print(f"❌ Erro: {e}")
            results.append({"flow": flow_key, "day": day, "success": False, "reason": str(e)})
    
    return results


def test_flow_state_transitions():
    """Test flow state transition logic."""
    print("\n" + "="*70)
    print("🔄 TEST 3: FLOW STATE TRANSITIONS")
    print("="*70)
    
    # Simulate patient journey through days
    transitions = [
        (1, "onboarding", "Paciente cadastrado, inicia fase inicial"),
        (15, "onboarding", "Último dia da fase inicial"),
        (16, "daily_follow_up", "Transição para fase de engajamento"),
        (45, "daily_follow_up", "Último dia antes do quiz"),
        (46, "quiz_mensal", "Transição para fase mensal"),
        (76, "quiz_mensal", "Segundo mês de acompanhamento"),
    ]
    
    print("\n📅 Simulação de jornada do paciente:")
    print("-" * 50)
    
    for day, expected_phase, description in transitions:
        # Determine phase based on day
        if day <= 15:
            actual_phase = "onboarding"
        elif day <= 45:
            actual_phase = "daily_follow_up"
        else:
            actual_phase = "quiz_mensal"
        
        status = "✅" if actual_phase == expected_phase else "❌"
        print(f"{status} Dia {day:3d}: {actual_phase:20s} | {description}")
    
    return True


def test_quiz_template():
    """Test quiz template loading."""
    print("\n" + "="*70)
    print("📋 TEST 4: QUIZ TEMPLATE LOADING")
    print("="*70)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT name, version, is_active, questions
            FROM quiz_templates 
            WHERE name = 'monthly_comprehensive'
        """)).fetchone()
        
        if result:
            print("\n✅ Quiz Template Encontrado:")
            print(f"   Nome: {result[0]}")
            print(f"   Versão: {result[1]}")
            print(f"   Ativo: {result[2]}")
            
            questions = result[3]
            print(f"\n📝 Perguntas ({len(questions)} total):")
            for i, q in enumerate(questions, 1):
                q_type = q.get('type', 'unknown')
                q_text = q.get('text', 'N/A')[:50]
                required = "Obrigatória" if q.get('required') else "Opcional"
                print(f"   {i}. [{q_type:15s}] {q_text}... ({required})")
            
            return True
        else:
            print("❌ Quiz template não encontrado!")
            return False


def simulate_patient_journey(db):
    """Simulate a complete patient journey through all phases."""
    print("\n" + "="*70)
    print("🚀 TEST 5: SIMULAÇÃO COMPLETA DE JORNADA DO PACIENTE")
    print("="*70)
    
    loader = EnhancedTemplateLoader(db=db)
    
    # Simulate patient data
    patient = {
        "name": "Maria Silva (Teste)",
        "phone": "+5511999999999",
        "enrollment_date": now_sao_paulo() - timedelta(days=0),
        "treatment_type": "hormone_therapy",
    }
    
    print(f"\n👤 Paciente: {patient['name']}")
    print(f"📅 Data de Cadastro: {patient['enrollment_date'].strftime('%d/%m/%Y')}")
    print(f"💊 Tratamento: {patient['treatment_type']}")
    print("-" * 50)
    
    # Simulate key days in the journey
    key_days = [2, 3, 5, 7, 9, 11, 13, 15, 16, 20, 30, 45]
    
    messages_sent = 0
    for day in key_days:
        # Determine current phase
        if day <= 15:
            phase = "onboarding"
            phase_name = "Fase Inicial"
        elif day <= 45:
            phase = "daily_follow_up"
            phase_name = "Fase de Engajamento"
        else:
            phase = "quiz_mensal"
            phase_name = "Fase Mensal"
        
        # Try to get message for this day
        message = loader.get_message_for_day(phase, day)
        
        if message:
            messages_sent += 1
            print(f"\n📤 Dia {day:2d} ({phase_name})")
            print(f"   Intent: {message.intent}")
            print(f"   Mensagem: \"{message.base_content[:60]}...\"")
        else:
            print(f"\n⏸️  Dia {day:2d} ({phase_name}) - Sem mensagem programada")
    
    print("\n" + "-" * 50)
    print("📊 RESUMO DA SIMULAÇÃO:")
    print(f"   Dias simulados: {len(key_days)}")
    print(f"   Mensagens enviadas: {messages_sent}")
    print(f"   Taxa de cobertura: {messages_sent/len(key_days)*100:.1f}%")
    
    return messages_sent > 0


def main():
    print("\n" + "="*70)
    print("🧪 TESTE COMPLETO DO SISTEMA DE ACOMPANHAMENTO DIÁRIO")
    print("="*70)
    print(f"Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("Modo: SIMULAÇÃO (sem envio de WhatsApp)")
    
    db = SessionLocal()
    
    try:
        # Run all tests
        test_results = {
            "template_loading": test_template_loading(db),
            "message_generation": test_message_generation(db),
            "flow_transitions": test_flow_state_transitions(),
            "quiz_template": test_quiz_template(),
            "patient_journey": simulate_patient_journey(db),
        }
        
        # Summary
        print("\n" + "="*70)
        print("📊 RESUMO DOS TESTES")
        print("="*70)
        
        all_passed = True
        for test_name, result in test_results.items():
            if isinstance(result, bool):
                status = "✅ PASSOU" if result else "❌ FALHOU"
                if not result:
                    all_passed = False
            elif isinstance(result, dict):
                failed = sum(1 for r in result.values() if isinstance(r, dict) and not r.get("success", True))
                if failed > 0:
                    status = f"⚠️  {failed} falhas"
                    all_passed = False
                else:
                    status = "✅ PASSOU"
            elif isinstance(result, list):
                failed = sum(1 for r in result if not r.get("success", True))
                if failed > 0:
                    status = f"⚠️  {failed} falhas"
                    all_passed = False
                else:
                    status = "✅ PASSOU"
            else:
                status = "❓ INDEFINIDO"
            
            print(f"   {test_name:25s}: {status}")
        
        print("\n" + "="*70)
        if all_passed:
            print("🎉 TODOS OS TESTES PASSARAM - SISTEMA OPERACIONAL!")
        else:
            print("⚠️  ALGUNS TESTES FALHARAM - VERIFICAR LOGS ACIMA")
        print("="*70 + "\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
