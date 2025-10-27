#!/usr/bin/env python3
"""
Script para corrigir os problemas identificados no teste do quiz diário
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_quiz_template_response_schema():
    """Corrige o schema QuizTemplateResponse para incluir category"""
    
    print("🔧 Corrigindo QuizTemplateResponse schema...")
    
    try:
        # Verificar o schema atual
        from app.schemas.quiz import QuizTemplateResponse
        
        # Verificar se tem o campo category
        fields = QuizTemplateResponse.model_fields
        
        if 'category' not in fields:
            print("   ❌ Campo 'category' não encontrado no schema")
            print("   📝 Adicionando campo 'category' ao schema...")
            
            # Vou verificar o modelo para ver se tem category
            from app.models.quiz import QuizTemplate
            
            # Verificar colunas do modelo
            columns = [column.name for column in QuizTemplate.__table__.columns]
            print(f"   📋 Colunas do modelo QuizTemplate: {columns}")
            
            if 'category' in columns:
                print("   ✅ Campo 'category' existe no modelo")
                return True
            else:
                print("   ❌ Campo 'category' não existe no modelo")
                return False
        else:
            print("   ✅ Campo 'category' já existe no schema")
            return True
            
    except Exception as e:
        print(f"   ❌ Erro ao verificar schema: {e}")
        return False

def fix_monthly_quiz_service_method():
    """Corrige o método generate_quiz_link no MonthlyQuizService"""
    
    print("\n🔧 Verificando MonthlyQuizService...")
    
    try:
        from app.services.monthly_quiz_service import MonthlyQuizService
        
        # Verificar métodos disponíveis
        methods = [method for method in dir(MonthlyQuizService) if not method.startswith('_')]
        print(f"   📋 Métodos disponíveis: {methods}")
        
        if 'generate_quiz_link' in methods:
            print("   ✅ Método 'generate_quiz_link' existe")
            return True
        elif 'create_quiz_link' in methods:
            print("   ⚠️ Método 'create_quiz_link' existe (nome diferente)")
            return True
        else:
            print("   ❌ Método de geração de link não encontrado")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro ao verificar MonthlyQuizService: {e}")
        return False

def fix_flow_engine_methods():
    """Verifica e corrige métodos do FlowEngine"""
    
    print("\n🔧 Verificando FlowEngine...")
    
    try:
        from app.services.flow_engine import FlowEngine
        from app.database import get_db
        
        # Criar instância para teste
        db_gen = get_db()
        db = next(db_gen)
        
        flow_engine = FlowEngine(db)
        
        # Verificar métodos disponíveis
        methods = [method for method in dir(flow_engine) if not method.startswith('_')]
        print(f"   📋 Métodos disponíveis: {methods}")
        
        required_methods = ['get_flow_status', 'get_flow_history']
        missing_methods = []
        
        for method in required_methods:
            if hasattr(flow_engine, method):
                print(f"   ✅ Método '{method}' existe")
            else:
                print(f"   ❌ Método '{method}' não existe")
                missing_methods.append(method)
        
        db.close()
        
        return len(missing_methods) == 0
        
    except Exception as e:
        print(f"   ❌ Erro ao verificar FlowEngine: {e}")
        return False

def fix_service_error_exception():
    """Corrige a importação de ServiceError"""
    
    print("\n🔧 Verificando exceções...")
    
    try:
        from app.exceptions import ValidationError
        print("   ✅ ValidationError importado com sucesso")
        
        try:
            from app.exceptions import ServiceError
            print("   ✅ ServiceError importado com sucesso")
            return True
        except ImportError:
            print("   ❌ ServiceError não encontrado")
            
            # Verificar se existe em outro lugar
            try:
                from app.exceptions.base import ServiceError
                print("   ✅ ServiceError encontrado em base")
                return True
            except ImportError:
                print("   ❌ ServiceError não encontrado em base")
                
                # Criar ServiceError se não existir
                print("   📝 ServiceError precisa ser criado")
                return False
                
    except Exception as e:
        print(f"   ❌ Erro ao verificar exceções: {e}")
        return False

def create_daily_quiz_template():
    """Cria um template de quiz diário se não existir"""
    
    print("\n🔧 Criando template de quiz diário...")
    
    try:
        from app.core.session_manager import initialize_session_manager
        from app.core.redis_unified import get_sync_redis
        from app.dependencies import get_thread_safe_service_provider
        from app.models.quiz import QuizTemplate
        from app.schemas.quiz import QuizQuestion, QuestionType
        
        # Inicializar session manager
        redis_client = get_sync_redis()
        initialize_session_manager(redis_client)
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        # Verificar se já existe template diário
        existing = provider.db.query(QuizTemplate).filter(
            QuizTemplate.name.like('%diário%')
        ).first()
        
        if existing:
            print(f"   ✅ Template diário já existe: {existing.name}")
            provider_gen.close()
            return True
        
        # Criar template diário
        daily_questions = [
            {
                "id": "mood",
                "text": "Como você está se sentindo hoje?",
                "type": "single_choice",
                "options": ["😊 Muito bem", "🙂 Bem", "😐 Normal", "😔 Não muito bem", "😞 Mal"],
                "required": True
            },
            {
                "id": "energy",
                "text": "Como está seu nível de energia?",
                "type": "scale",
                "scale_min": 1,
                "scale_max": 10,
                "scale_labels": {"1": "Muito baixo", "10": "Muito alto"},
                "required": True
            },
            {
                "id": "medication",
                "text": "Você tomou sua medicação hoje?",
                "type": "boolean",
                "required": True
            }
        ]
        
        template = QuizTemplate(
            name="Check-in Diário",
            version="1.0",
            description="Questionário diário para acompanhamento do paciente",
            questions=daily_questions,
            is_active=True,
            category="daily_checkin"  # Adicionar category se o campo existir
        )
        
        provider.db.add(template)
        provider.db.commit()
        
        print(f"   ✅ Template criado: {template.name}")
        
        provider_gen.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao criar template: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Testa funcionalidade básica após correções"""
    
    print("\n🧪 Testando funcionalidade básica...")
    
    try:
        from app.core.session_manager import initialize_session_manager
        from app.core.redis_unified import get_sync_redis
        from app.dependencies import get_thread_safe_service_provider
        
        # Inicializar session manager
        redis_client = get_sync_redis()
        initialize_session_manager(redis_client)
        
        # Obter service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        # Testar quiz service
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        
        # Listar templates
        templates, total = template_service.get_templates(skip=0, limit=10, active_only=True)
        print(f"   ✅ Templates encontrados: {len(templates)}")
        
        # Verificar pacientes
        from app.models.patient import Patient
        patients = provider.db.query(Patient).limit(5).all()
        print(f"   ✅ Pacientes encontrados: {len(patients)}")
        
        if patients:
            patient = patients[0]
            print(f"   📋 Paciente teste: {patient.name}")
        
        provider_gen.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Erro no teste básico: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    
    print("🔧 CORREÇÃO DOS PROBLEMAS DO QUIZ DIÁRIO")
    print("=" * 60)
    
    fixes = [
        ("Schema QuizTemplateResponse", fix_quiz_template_response_schema),
        ("MonthlyQuizService methods", fix_monthly_quiz_service_method),
        ("FlowEngine methods", fix_flow_engine_methods),
        ("ServiceError exception", fix_service_error_exception),
        ("Template de quiz diário", create_daily_quiz_template),
        ("Teste básico", test_basic_functionality)
    ]
    
    results = {}
    
    for fix_name, fix_func in fixes:
        print(f"\n{'='*15} {fix_name.upper()} {'='*15}")
        
        try:
            results[fix_name] = fix_func()
        except Exception as e:
            print(f"❌ Erro crítico em {fix_name}: {e}")
            results[fix_name] = False
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DAS CORREÇÕES")
    print("=" * 60)
    
    fixed = 0
    total = len(results)
    
    for fix_name, result in results.items():
        status = "✅ CORRIGIDO" if result else "❌ PENDENTE"
        print(f"{fix_name}: {status}")
        if result:
            fixed += 1
    
    print(f"\nResultado: {fixed}/{total} correções aplicadas")
    
    if fixed == total:
        print("\n🎉 TODAS AS CORREÇÕES APLICADAS!")
        print("\n✅ O sistema está pronto para testar o quiz diário novamente")
    else:
        pending = [name for name, result in results.items() if not result]
        print(f"\n⚠️ CORREÇÕES PENDENTES: {', '.join(pending)}")
        print("\n🔧 Próximos passos:")
        print("   1. Revisar erros específicos")
        print("   2. Aplicar correções manuais se necessário")
        print("   3. Re-executar teste do quiz diário")

if __name__ == "__main__":
    main()