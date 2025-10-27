#!/usr/bin/env python3
"""
Simulação do endpoint quiz/templates para identificar o erro 500
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import Optional
import traceback

def simulate_fastapi_context():
    """Simula o contexto do FastAPI para testar o endpoint"""
    
    print("🎭 Simulando contexto do FastAPI...")
    print("=" * 60)
    
    try:
        # Importações necessárias
        from app.dependencies import get_thread_safe_service_provider
        from app.dependencies.auth_dependencies import get_current_user
        from app.dependencies.business_dependencies import get_pagination_params
        from app.schemas.quiz import QuizTemplateResponse, QuizTemplateListResponse
        from app.schemas.common import PaginationParams
        
        print("✅ Importações realizadas com sucesso")
        
        # Simular obtenção do service provider
        print("\n1. Obtendo ServiceProvider...")
        
        # Criar um gerador do service provider
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        print(f"   ✅ ServiceProvider obtido: {type(provider)}")
        print(f"   Session ID: {hex(id(provider.db)) if hasattr(provider, 'db') else 'N/A'}")
        
        # Testar acesso ao quiz service
        print("\n2. Acessando QuizService...")
        
        quiz_service = provider.quiz_service
        print(f"   ✅ QuizService obtido: {type(quiz_service)}")
        
        # Testar acesso ao template service
        print("\n3. Acessando QuizTemplateService...")
        
        template_service = quiz_service.template_service
        print(f"   ✅ QuizTemplateService obtido: {type(template_service)}")
        
        # Simular parâmetros de paginação
        print("\n4. Simulando parâmetros de paginação...")
        
        pagination = PaginationParams(skip=0, limit=100)
        print(f"   ✅ Paginação: skip={pagination.skip}, limit={pagination.limit}")
        
        # Testar chamada do método get_templates
        print("\n5. Chamando template_service.get_templates()...")
        
        templates, total = template_service.get_templates(
            skip=pagination.skip,
            limit=pagination.limit,
            active_only=True,
            db=provider.db
        )
        
        print(f"   ✅ Templates obtidos: {len(templates)}, Total: {total}")
        
        # Testar conversão para response
        print("\n6. Convertendo para QuizTemplateResponse...")
        
        template_responses = []
        for i, template in enumerate(templates):
            try:
                response = QuizTemplateResponse.from_orm(template)
                template_responses.append(response)
                print(f"   ✅ Template {i+1} convertido: {template.name}")
            except Exception as e:
                print(f"   ❌ Erro convertendo template {i+1}: {e}")
                raise
        
        # Testar criação da resposta final
        print("\n7. Criando resposta final...")
        
        final_response = QuizTemplateListResponse(
            templates=template_responses,
            total=total,
            skip=pagination.skip,
            limit=pagination.limit
        )
        
        print(f"   ✅ Resposta criada com {len(final_response.templates)} templates")
        
        # Testar serialização JSON
        print("\n8. Testando serialização JSON...")
        
        json_data = final_response.model_dump()
        print(f"   ✅ JSON serializado com {len(json_data.get('templates', []))} templates")
        
        print("\n🎉 SIMULAÇÃO COMPLETA - ENDPOINT DEVERIA FUNCIONAR!")
        
        # Cleanup
        provider_gen.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro na simulação: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_direct_service_call():
    """Testa chamada direta do serviço sem FastAPI"""
    
    print("\n🔧 Teste direto do serviço...")
    print("=" * 60)
    
    try:
        from app.services.quiz import QuizTemplateService
        from app.database import get_db
        
        # Obter sessão do banco
        db_gen = get_db()
        db = next(db_gen)
        
        # Criar serviço diretamente
        service = QuizTemplateService()
        
        # Chamar método
        templates, total = service.get_templates(
            skip=0,
            limit=100,
            active_only=True,
            db=db
        )
        
        print(f"✅ Serviço direto funcionou: {len(templates)} templates, total: {total}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro no serviço direto: {e}")
        traceback.print_exc()
        return False

def test_schema_conversion():
    """Testa conversão de schemas"""
    
    print("\n📋 Teste de conversão de schemas...")
    print("=" * 60)
    
    try:
        from app.models.quiz import QuizTemplate
        from app.schemas.quiz import QuizTemplateResponse, QuizTemplateListResponse
        from app.database import get_db
        
        # Obter um template do banco
        db_gen = get_db()
        db = next(db_gen)
        
        template = db.query(QuizTemplate).first()
        
        if template:
            print(f"✅ Template encontrado: {template.name}")
            
            # Testar conversão
            response = QuizTemplateResponse.from_orm(template)
            print(f"✅ Conversão para response: {response.name}")
            
            # Testar serialização
            json_data = response.model_dump()
            print(f"✅ Serialização JSON: {json_data.get('name')}")
            
        else:
            print("⚠️  Nenhum template encontrado no banco")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na conversão de schemas: {e}")
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    
    print("🔍 SIMULAÇÃO COMPLETA DO ENDPOINT /api/v1/quiz/templates")
    print("=" * 70)
    
    tests = [
        ("Serviço direto", test_direct_service_call),
        ("Conversão de schemas", test_schema_conversion),
        ("Contexto FastAPI", simulate_fastapi_context)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name.upper()} {'='*20}")
        results[test_name] = test_func()
    
    # Resumo
    print("\n" + "=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
    
    if all(results.values()):
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("\nSe ainda há erro 500, o problema pode estar em:")
        print("1. Middleware de autenticação")
        print("2. Validação de token JWT")
        print("3. Configuração de CORS")
        print("4. Timeout de request")
    else:
        failed = [name for name, result in results.items() if not result]
        print(f"\n❌ TESTES QUE FALHARAM: {', '.join(failed)}")

if __name__ == "__main__":
    main()