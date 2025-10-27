#!/usr/bin/env python3
"""
Script para corrigir o problema do session manager não inicializado
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_session_manager_initialization():
    """Corrige a inicialização do session manager"""
    
    print("🔧 Corrigindo inicialização do session manager...")
    print("=" * 60)
    
    try:
        # Importar e inicializar manualmente
        from app.core.session_manager import initialize_session_manager, get_session_manager
        
        print("1. Verificando estado atual...")
        
        try:
            session_manager = get_session_manager()
            print("   ✅ Session manager já inicializado")
            return True
        except RuntimeError:
            print("   ⚠️  Session manager não inicializado, inicializando...")
        
        print("\n2. Inicializando session manager...")
        
        # Tentar obter Redis client
        redis_client = None
        try:
            from app.core.redis_unified import get_sync_redis
            redis_client = get_sync_redis()
            print("   ✅ Redis client obtido")
        except Exception as e:
            print(f"   ⚠️  Redis não disponível: {e}")
        
        # Inicializar session manager
        session_manager = initialize_session_manager(redis_client)
        print(f"   ✅ Session manager inicializado: {type(session_manager)}")
        
        # Verificar se funcionou
        test_manager = get_session_manager()
        print(f"   ✅ Verificação: {type(test_manager)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na correção: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_endpoint_after_fix():
    """Testa o endpoint após a correção"""
    
    print("\n🧪 Testando endpoint após correção...")
    print("=" * 60)
    
    try:
        # Testar service provider
        from app.dependencies import get_thread_safe_service_provider
        
        print("1. Obtendo ServiceProvider...")
        provider_gen = get_thread_safe_service_provider()
        provider = next(provider_gen)
        print(f"   ✅ ServiceProvider: {type(provider)}")
        
        # Testar quiz service
        print("\n2. Testando QuizService...")
        quiz_service = provider.quiz_service
        template_service = quiz_service.template_service
        print(f"   ✅ TemplateService: {type(template_service)}")
        
        # Testar método
        print("\n3. Testando get_templates()...")
        templates, total = template_service.get_templates(
            skip=0,
            limit=100,
            active_only=True
        )
        print(f"   ✅ Templates: {len(templates)}, Total: {total}")
        
        # Testar conversão
        print("\n4. Testando conversão para response...")
        from app.schemas.quiz import QuizTemplateResponse, QuizTemplateListResponse
        from app.schemas.common import PaginationParams
        
        template_responses = []
        for template in templates:
            response = QuizTemplateResponse.model_validate(template)
            template_responses.append(response)
        
        pagination = PaginationParams(skip=0, limit=100)
        final_response = QuizTemplateListResponse(
            items=template_responses,
            total=total,
            page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
            size=pagination.limit
        )
        
        print(f"   ✅ Resposta final: {len(final_response.templates)} templates")
        
        # Cleanup
        provider_gen.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_startup_fix():
    """Cria um patch para garantir que o session manager seja inicializado"""
    
    print("\n🛠️ Criando patch de inicialização...")
    print("=" * 60)
    
    patch_content = '''"""
Patch para garantir que o session manager seja inicializado.

Este patch deve ser importado no início da aplicação para garantir
que o session manager seja inicializado mesmo se o lifespan falhar.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

def ensure_session_manager_initialized() -> bool:
    """
    Garante que o session manager esteja inicializado.
    
    Returns:
        bool: True se inicializado com sucesso, False caso contrário
    """
    try:
        from app.core.session_manager import get_session_manager, initialize_session_manager
        
        # Verificar se já está inicializado
        try:
            get_session_manager()
            logger.info("Session manager já inicializado")
            return True
        except RuntimeError:
            logger.info("Session manager não inicializado, inicializando...")
        
        # Tentar obter Redis client
        redis_client = None
        try:
            from app.core.redis_unified import get_sync_redis
            redis_client = get_sync_redis()
            logger.info("Redis client obtido para session manager")
        except Exception as e:
            logger.warning(f"Redis não disponível para session manager: {e}")
        
        # Inicializar session manager
        session_manager = initialize_session_manager(redis_client)
        logger.info(f"Session manager inicializado: {type(session_manager)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Falha ao inicializar session manager: {e}")
        return False

# Auto-inicializar quando o módulo for importado
if __name__ != "__main__":
    ensure_session_manager_initialized()
'''
    
    try:
        with open("backend-hormonia/app/core/session_manager_patch.py", "w", encoding="utf-8") as f:
            f.write(patch_content)
        
        print("   ✅ Patch criado: app/core/session_manager_patch.py")
        
        # Criar importação no __init__.py das dependências
        init_patch = '''
# Garantir que o session manager seja inicializado
try:
    from app.core.session_manager_patch import ensure_session_manager_initialized
    ensure_session_manager_initialized()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Session manager patch failed: {e}")
'''
        
        # Ler o arquivo atual
        with open("backend-hormonia/app/dependencies/__init__.py", "r", encoding="utf-8") as f:
            current_content = f.read()
        
        # Adicionar o patch no início se não estiver presente
        if "session_manager_patch" not in current_content:
            new_content = '"""Dependencies package for FastAPI dependency injection."""\n\n' + init_patch + '\n' + current_content.split('"""Dependencies package for FastAPI dependency injection."""\n\n')[1]
            
            with open("backend-hormonia/app/dependencies/__init__.py", "w", encoding="utf-8") as f:
                f.write(new_content)
            
            print("   ✅ Patch adicionado ao __init__.py das dependências")
        else:
            print("   ⚠️  Patch já presente no __init__.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar patch: {e}")
        return False

def main():
    """Função principal"""
    
    print("🔧 CORREÇÃO DO SESSION MANAGER")
    print("=" * 70)
    
    # Executar correções
    fix1 = fix_session_manager_initialization()
    fix2 = test_endpoint_after_fix() if fix1 else False
    fix3 = create_startup_fix()
    
    print("\n" + "=" * 70)
    print("📊 RESUMO DAS CORREÇÕES")
    print("=" * 70)
    
    results = {
        "Inicialização manual": fix1,
        "Teste do endpoint": fix2,
        "Patch de startup": fix3
    }
    
    for fix_name, result in results.items():
        status = "✅ SUCESSO" if result else "❌ FALHOU"
        print(f"{fix_name}: {status}")
    
    if fix1 and fix2:
        print("\n🎉 CORREÇÃO APLICADA COM SUCESSO!")
        print("\nO endpoint /api/v1/quiz/templates agora deveria funcionar.")
        print("\nPara aplicar permanentemente:")
        print("1. Reinicie o servidor")
        print("2. O patch será aplicado automaticamente")
        print("3. Verifique os logs para confirmar a inicialização")
    else:
        print("\n❌ CORREÇÃO PARCIAL OU FALHADA")
        print("Verifique os erros acima e tente novamente")

if __name__ == "__main__":
    main()