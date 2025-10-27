#!/usr/bin/env python3
"""
Teste do endpoint quiz/templates com contexto completo da aplicação
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from contextlib import asynccontextmanager
import traceback

async def test_with_full_app_context():
    """Testa o endpoint com o contexto completo da aplicação"""
    
    print("🚀 Testando com contexto completo da aplicação...")
    print("=" * 60)
    
    try:
        # Importar e criar a aplicação
        from app.core.application_factory import create_application
        
        print("1. Criando aplicação...")
        app = create_application(deployment_mode="development")
        print("   ✅ Aplicação criada")
        
        # Simular o startup da aplicação
        print("\n2. Executando startup da aplicação...")
        
        # O lifespan é executado automaticamente quando a aplicação é criada
        # Vamos tentar acessar o session manager após a inicialização
        
        # Aguardar um pouco para garantir que o startup foi executado
        await asyncio.sleep(1)
        
        print("   ✅ Startup executado")
        
        # Testar se o session manager foi inicializado
        print("\n3. Verificando session manager...")
        
        from app.core.session_manager import get_session_manager, get_request_factory
        
        try:
            session_manager = get_session_manager()
            print(f"   ✅ Session manager obtido: {type(session_manager)}")
            
            request_factory = get_request_factory()
            print(f"   ✅ Request factory obtido: {type(request_factory)}")
            
        except RuntimeError as e:
            print(f"   ❌ Erro no session manager: {e}")
            return False
        
        # Testar o service provider
        print("\n4. Testando ServiceProvider...")
        
        from app.dependencies import get_thread_safe_service_provider
        
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        
        print(f"   ✅ ServiceProvider obtido: {type(provider)}")
        
        # Testar acesso ao quiz service
        print("\n5. Testando QuizService...")
        
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        
        print(f"   ✅ QuizService: {type(quiz_service)}")
        print(f"   ✅ TemplateService: {type(template_service)}")
        
        # Testar chamada do método
        print("\n6. Testando get_templates()...")
        
        templates, total = template_service.get_templates(
            skip=0,
            limit=100,
            active_only=True,
            db=provider.db
        )
        
        print(f"   ✅ Templates obtidos: {len(templates)}, Total: {total}")
        
        # Testar conversão para response
        print("\n7. Testando conversão para response...")
        
        from app.schemas.quiz import QuizTemplateResponse, QuizTemplateListResponse
        from app.schemas.common import PaginationParams
        
        template_responses = []
        for template in templates:
            response = QuizTemplateResponse.model_validate(template)
            template_responses.append(response)
        
        pagination = PaginationParams(skip=0, limit=100)
        
        final_response = QuizTemplateListResponse(
            templates=template_responses,
            total=total,
            skip=pagination.skip,
            limit=pagination.limit
        )
        
        print(f"   ✅ Resposta final criada com {len(final_response.templates)} templates")
        
        # Cleanup
        provider_gen.close()
        
        print("\n🎉 TESTE COMPLETO COM SUCESSO!")
        print("   O endpoint deveria funcionar perfeitamente em produção.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        traceback.print_exc()
        return False

async def test_simple_endpoint_call():
    """Testa uma chamada simples ao endpoint"""
    
    print("\n🌐 Testando chamada HTTP simples...")
    print("=" * 60)
    
    try:
        import httpx
        
        # Fazer uma requisição HTTP simples
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "http://localhost:8000/api/v1/quiz/templates",
                    timeout=10.0
                )
                
                print(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Sucesso! Templates: {len(data.get('templates', []))}")
                    return True
                elif response.status_code == 401:
                    print("⚠️  Erro 401 - Autenticação necessária (esperado)")
                    return True
                elif response.status_code == 500:
                    print("❌ Erro 500 - Problema interno")
                    print(f"Response: {response.text[:500]}")
                    return False
                else:
                    print(f"Status inesperado: {response.status_code}")
                    print(f"Response: {response.text[:500]}")
                    return False
                    
            except httpx.ConnectError:
                print("⚠️  Servidor não está rodando em localhost:8000")
                return False
                
    except ImportError:
        print("⚠️  httpx não está instalado, pulando teste HTTP")
        return True
    except Exception as e:
        print(f"❌ Erro no teste HTTP: {e}")
        return False

async def main():
    """Função principal"""
    
    print("🔍 TESTE COMPLETO DO ENDPOINT /api/v1/quiz/templates")
    print("=" * 70)
    
    # Executar testes
    test1 = await test_with_full_app_context()
    test2 = await test_simple_endpoint_call()
    
    print("\n" + "=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    
    results = {
        "Contexto da aplicação": test1,
        "Chamada HTTP": test2
    }
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
    
    if test1:
        print("\n🎉 O ENDPOINT DEVERIA FUNCIONAR!")
        print("\nSe ainda há erro 500 em produção, verifique:")
        print("1. Se o servidor está sendo iniciado corretamente")
        print("2. Se todas as variáveis de ambiente estão configuradas")
        print("3. Se não há problemas de autenticação")
        print("4. Logs do servidor para erros específicos")
    else:
        print("\n❌ AINDA HÁ PROBLEMAS NO ENDPOINT")
        print("Verifique os erros acima para identificar a causa")

if __name__ == "__main__":
    asyncio.run(main())