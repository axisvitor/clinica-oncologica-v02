#!/usr/bin/env python3
"""
Teste simples para verificar se as importações estão funcionando
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Testa as importações do endpoint quiz"""
    
    print("🔧 Testando importações...")
    
    try:
        # Teste 1: Importações de dependências
        print("1. Testando importações de dependências...")
        
        from app.dependencies.service_dependencies import get_quiz_template_service
        print("   ✅ get_quiz_template_service importado")
        
        from app.dependencies.auth_dependencies import get_current_user
        print("   ✅ get_current_user importado")
        
        from app.dependencies.business_dependencies import get_pagination_params
        print("   ✅ get_pagination_params importado")
        
        # Teste 2: Importações de serviços
        print("\n2. Testando importações de serviços...")
        
        from app.services.quiz import QuizTemplateService
        print("   ✅ QuizTemplateService importado")
        
        # Teste 3: Importações de schemas
        print("\n3. Testando importações de schemas...")
        
        from app.schemas.quiz import QuizTemplateResponse, QuizTemplateListResponse
        print("   ✅ Schemas de quiz importados")
        
        # Teste 4: Testar instanciação
        print("\n4. Testando instanciação...")
        
        service = get_quiz_template_service()
        print(f"   ✅ Serviço instanciado: {type(service)}")
        
        print("\n🎉 TODAS AS IMPORTAÇÕES FUNCIONARAM!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erro nas importações: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()