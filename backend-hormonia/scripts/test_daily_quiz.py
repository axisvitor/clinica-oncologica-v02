#!/usr/bin/env python3
"""
Teste completo do sistema de quiz diário
Testa desde a criação do quiz até o envio via WhatsApp
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4, UUID
import traceback
import json

def test_quiz_templates():
    """Testa se os templates de quiz estão funcionando"""
    
    print("📋 Testando Quiz Templates...")
    print("=" * 60)
    
    try:
        from app.core.session_manager import initialize_session_manager
        from app.core.redis_unified import get_sync_redis
        from app.dependencies import get_thread_safe_service_provider
        from app.schemas.quiz import QuizTemplateCreate, QuizQuestion, QuestionType
        
        # Inicializar session manager
        redis_client = get_sync_redis()
        initialize_session_manager(redis_client)
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        
        print("1. Listando templates existentes...")
        templates, total = template_service.get_templates(skip=0, limit=10, active_only=True)
        print(f"   ✅ Templates encontrados: {len(templates)}")
        
        for i, template in enumerate(templates):
            print(f"   {i+1}. {template.name} (v{template.version}) - {template.category}")
        
        # Criar template de quiz diário se não existir
        daily_template_exists = any(t.category == "daily_checkin" for t in templates)
        
        if not daily_template_exists:
            print("\n2. Criando template de quiz diário...")
            
            daily_questions = [
                QuizQuestion(
                    id="mood",
                    text="Como você está se sentindo hoje?",
                    type=QuestionType.SINGLE_CHOICE,
                    options=["😊 Muito bem", "🙂 Bem", "😐 Normal", "😔 Não muito bem", "😞 Mal"],
                    required=True
                ),
                QuizQuestion(
                    id="energy",
                    text="Como está seu nível de energia?",
                    type=QuestionType.SCALE,
                    scale_min=1,
                    scale_max=10,
                    scale_labels={"1": "Muito baixo", "10": "Muito alto"},
                    required=True
                ),
                QuizQuestion(
                    id="symptoms",
                    text="Você está sentindo algum sintoma hoje?",
                    type=QuestionType.MULTIPLE_CHOICE,
                    options=["Dor de cabeça", "Náusea", "Fadiga", "Dor muscular", "Nenhum"],
                    required=False
                ),
                QuizQuestion(
                    id="medication",
                    text="Você tomou sua medicação hoje?",
                    type=QuestionType.BOOLEAN,
                    required=True
                ),
                QuizQuestion(
                    id="notes",
                    text="Alguma observação adicional sobre hoje?",
                    type=QuestionType.TEXT,
                    required=False
                )
            ]
            
            template_data = QuizTemplateCreate(
                name="Check-in Diário",
                version="1.0",
                category="daily_checkin",
                description="Questionário diário para acompanhamento do paciente",
                questions=daily_questions,
                is_active=True
            )
            
            created_template = template_service.create_template(template_data)
            print(f"   ✅ Template criado: {created_template.name}")
        else:
            print("\n2. Template de quiz diário já existe")
        
        provider_gen.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de templates: {e}")
        traceback.print_exc()
        return False

def test_quiz_session_creation():
    """Testa criação de sessão de quiz"""
    
    print("\n🎯 Testando criação de sessão de quiz...")
    print("=" * 60)
    
    try:
        from app.dependencies import get_thread_safe_service_provider
        from app.schemas.quiz import QuizSessionCreate
        from app.models.patient import Patient
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        # Obter um paciente para teste
        patient = provider.db.query(Patient).first()
        if not patient:
            print("❌ Nenhum paciente encontrado para teste")
            return False
        
        print(f"1. Usando paciente: {patient.name} ({patient.phone})")
        
        # Obter template de quiz diário
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        
        templates, _ = template_service.get_templates(skip=0, limit=10, active_only=True)
        daily_template = next((t for t in templates if t.category == "daily_checkin"), None)
        
        if not daily_template:
            print("❌ Template de quiz diário não encontrado")
            return False
        
        print(f"2. Usando template: {daily_template.name}")
        
        # Criar sessão de quiz
        session_data = QuizSessionCreate(
            patient_id=patient.id,
            template_id=UUID(daily_template.id),
            delivery_method="whatsapp"
        )
        
        session_service = quiz_service.session_service
        session = session_service.create_session(session_data)
        
        print(f"   ✅ Sessão criada: {session.id}")
        print(f"   Status: {session.status}")
        print(f"   Método de entrega: {session.delivery_method}")
        
        provider_gen.close()
        return True, session.id, patient.id
        
    except Exception as e:
        print(f"❌ Erro na criação de sessão: {e}")
        traceback.print_exc()
        return False, None, None

def test_quiz_link_generation():
    """Testa geração de link tokenizado para quiz"""
    
    print("\n🔗 Testando geração de link de quiz...")
    print("=" * 60)
    
    try:
        from app.services.monthly_quiz_service import MonthlyQuizService
        from app.dependencies import get_thread_safe_service_provider
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        # Obter um paciente para teste
        from app.models.patient import Patient
        patient = provider.db.query(Patient).first()
        
        if not patient:
            print("❌ Nenhum paciente encontrado")
            return False
        
        # Obter template
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        templates, _ = template_service.get_templates(skip=0, limit=10, active_only=True)
        template = templates[0] if templates else None
        
        if not template:
            print("❌ Nenhum template encontrado")
            return False
        
        print(f"1. Gerando link para paciente: {patient.name}")
        print(f"2. Template: {template.name}")
        
        # Criar serviço de quiz mensal (que tem a lógica de links)
        monthly_service = MonthlyQuizService(provider.db)
        
        # Gerar link tokenizado
        link_data = monthly_service.generate_quiz_link(
            patient_id=patient.id,
            quiz_template_id=UUID(template.id),
            delivery_method="whatsapp",
            expiry_hours=72
        )
        
        print(f"   ✅ Link gerado: {link_data['quiz_url']}")
        print(f"   Token: {link_data['token'][:20]}...")
        print(f"   Expira em: {link_data['expires_at']}")
        
        provider_gen.close()
        return True, link_data
        
    except Exception as e:
        print(f"❌ Erro na geração de link: {e}")
        traceback.print_exc()
        return False, None

def test_flow_engine_integration():
    """Testa integração com Flow Engine para envio automático"""
    
    print("\n⚙️ Testando integração com Flow Engine...")
    print("=" * 60)
    
    try:
        from app.dependencies import get_thread_safe_service_provider
        from app.services.flow_engine import FlowEngine
        from app.models.patient import Patient
        from app.models.flow import FlowKind
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        # Obter paciente
        patient = provider.db.query(Patient).first()
        if not patient:
            print("❌ Nenhum paciente encontrado")
            return False
        
        print(f"1. Testando flow para paciente: {patient.name}")
        
        # Criar flow engine
        flow_engine = FlowEngine(provider.db)
        
        # Verificar status do flow atual
        flow_status = flow_engine.get_flow_status(patient.id)
        print(f"2. Status atual do flow: {flow_status}")
        
        # Verificar se há flows ativos
        flows, current_flow = flow_engine.get_flow_history(patient.id)
        print(f"3. Flows históricos: {len(flows)}")
        
        if current_flow:
            print(f"   Flow ativo: {current_flow.flow_kind}")
            print(f"   Step atual: {current_flow.current_step}")
        
        # Simular processamento de flow diário
        print("\n4. Simulando processamento de flow diário...")
        
        # Verificar se precisa processar flow hoje
        from datetime import datetime, date
        today = date.today()
        
        # Simular que é hora do check-in diário
        print(f"   Data atual: {today}")
        print(f"   Dia de tratamento: {patient.current_day}")
        
        # Verificar templates disponíveis para flow diário
        available_flows = flow_engine.get_available_flows()
        print(f"   Flows disponíveis: {len(available_flows)}")
        
        for flow in available_flows:
            print(f"   - {flow['name']} ({flow['flow_type']})")
        
        provider_gen.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na integração com Flow Engine: {e}")
        traceback.print_exc()
        return False

async def test_whatsapp_integration():
    """Testa integração com WhatsApp para envio de quiz"""
    
    print("\n📱 Testando integração WhatsApp...")
    print("=" * 60)
    
    try:
        from app.services.whatsapp_unified import WhatsAppUnifiedService, MessageType
        from app.integrations.evolution import get_evolution_client
        from app.core.redis_unified import get_async_redis
        
        # Obter clientes
        evolution_client = await get_evolution_client()
        redis_client = await get_async_redis()
        
        # Criar serviço WhatsApp
        whatsapp_service = WhatsAppUnifiedService(
            evolution_api_client=evolution_client,
            redis_client=redis_client
        )
        
        print("1. Serviço WhatsApp inicializado")
        
        # Simular envio de quiz (sem enviar realmente)
        test_phone = "+5511999999999"  # Número de teste
        quiz_link = "https://quiz.hormonia.com/daily/abc123"
        
        message_content = f"""
🌟 *Olá! Hora do seu check-in diário*

Como você está se sentindo hoje? Seu bem-estar é importante para nós.

📋 Responda seu questionário diário:
{quiz_link}

⏰ Leva apenas 2 minutos
💙 Sua resposta nos ajuda a cuidar melhor de você

_Equipe Hormonia_
        """.strip()
        
        print("2. Mensagem preparada:")
        print(f"   Para: {test_phone}")
        print(f"   Conteúdo: {message_content[:100]}...")
        
        # Verificar rate limiting
        rate_limit_ok = await whatsapp_service._check_rate_limit(test_phone)
        print(f"3. Rate limit OK: {rate_limit_ok}")
        
        # Simular envio (comentado para não enviar realmente)
        print("4. ⚠️ Envio simulado (não enviado realmente)")
        # result = await whatsapp_service.send_message(
        #     phone_number=test_phone,
        #     message_type=MessageType.TEXT,
        #     content={"text": message_content}
        # )
        
        result = {
            "status": "simulated",
            "message_id": "sim_" + str(uuid4()),
            "phone": test_phone
        }
        
        print(f"   ✅ Resultado simulado: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na integração WhatsApp: {e}")
        traceback.print_exc()
        return False

def test_complete_daily_quiz_flow():
    """Testa o fluxo completo do quiz diário"""
    
    print("\n🔄 Testando fluxo completo do quiz diário...")
    print("=" * 60)
    
    try:
        from app.dependencies import get_thread_safe_service_provider
        from app.models.patient import Patient
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        # Obter paciente
        patient = provider.db.query(Patient).first()
        if not patient:
            print("❌ Nenhum paciente encontrado")
            return False
        
        print(f"1. Paciente selecionado: {patient.name}")
        print(f"   Telefone: {patient.phone}")
        print(f"   Dia de tratamento: {patient.current_day}")
        print(f"   Status do flow: {patient.flow_state}")
        
        # Verificar se é elegível para quiz diário
        from datetime import datetime, date
        today = date.today()
        
        # Simular lógica de elegibilidade
        is_eligible = True  # Simplificado para teste
        
        if not is_eligible:
            print("2. ⚠️ Paciente não elegível para quiz hoje")
            return True
        
        print("2. ✅ Paciente elegível para quiz diário")
        
        # Obter template de quiz diário
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        
        templates, _ = template_service.get_templates(skip=0, limit=10, active_only=True)
        daily_template = next((t for t in templates if t.category == "daily_checkin"), None)
        
        if not daily_template:
            print("3. ❌ Template de quiz diário não encontrado")
            return False
        
        print(f"3. ✅ Template encontrado: {daily_template.name}")
        
        # Gerar link do quiz
        from app.services.monthly_quiz_service import MonthlyQuizService
        monthly_service = MonthlyQuizService(provider.db)
        
        link_data = monthly_service.generate_quiz_link(
            patient_id=patient.id,
            quiz_template_id=UUID(daily_template.id),
            delivery_method="whatsapp",
            expiry_hours=24  # Quiz diário expira em 24h
        )
        
        print(f"4. ✅ Link gerado: {link_data['quiz_url']}")
        
        # Preparar mensagem personalizada
        message = f"""
🌅 *Bom dia, {patient.name}!*

Como você está se sentindo hoje? 

📋 *Seu check-in diário está pronto:*
{link_data['quiz_url']}

⏰ Leva apenas 2 minutos
💙 Suas respostas nos ajudam a cuidar melhor de você

_Responda até às 23:59 de hoje_
_Equipe Hormonia_
        """.strip()
        
        print("5. ✅ Mensagem personalizada preparada")
        print(f"   Tamanho: {len(message)} caracteres")
        
        # Simular envio via WhatsApp
        print("6. 📱 Simulando envio via WhatsApp...")
        print(f"   Para: {patient.phone}")
        print(f"   Método: whatsapp")
        print(f"   ⚠️ Envio simulado (não enviado realmente)")
        
        # Registrar tentativa de envio
        print("7. ✅ Fluxo completo simulado com sucesso!")
        
        # Estatísticas do teste
        print("\n📊 Estatísticas do teste:")
        print(f"   - Paciente: {patient.name}")
        print(f"   - Template: {daily_template.name}")
        print(f"   - Link válido até: {link_data['expires_at']}")
        print(f"   - Tamanho da mensagem: {len(message)} chars")
        
        provider_gen.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro no fluxo completo: {e}")
        traceback.print_exc()
        return False

async def main():
    """Função principal de teste"""
    
    print("🧪 TESTE COMPLETO DO SISTEMA DE QUIZ DIÁRIO")
    print("=" * 70)
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # Executar testes sequencialmente
    tests = [
        ("Templates de Quiz", test_quiz_templates),
        ("Criação de Sessão", test_quiz_session_creation),
        ("Geração de Links", test_quiz_link_generation),
        ("Flow Engine", test_flow_engine_integration),
        ("WhatsApp Integration", test_whatsapp_integration),
        ("Fluxo Completo", test_complete_daily_quiz_flow)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name.upper()} {'='*20}")
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            # Lidar com retornos múltiplos
            if isinstance(result, tuple):
                results[test_name] = result[0]
            else:
                results[test_name] = result
                
        except Exception as e:
            print(f"❌ Erro crítico no teste {test_name}: {e}")
            results[test_name] = False
    
    # Resumo final
    print("\n" + "=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("\n✅ O sistema de quiz diário está funcionando corretamente")
        print("\n📋 Próximos passos:")
        print("   1. Configurar agendamento automático (Celery)")
        print("   2. Testar em ambiente de produção")
        print("   3. Monitorar métricas de entrega")
        print("   4. Configurar alertas para falhas")
    else:
        failed_tests = [name for name, result in results.items() if not result]
        print(f"\n❌ TESTES QUE FALHARAM: {', '.join(failed_tests)}")
        print("\n🔧 Ações necessárias:")
        print("   1. Verificar logs de erro detalhados")
        print("   2. Corrigir problemas identificados")
        print("   3. Re-executar testes")
    
    print(f"\n⏰ Teste concluído em: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())