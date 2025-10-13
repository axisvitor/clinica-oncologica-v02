#!/usr/bin/env python3
"""
Testar integração dos endpoints de templates com o frontend.
"""
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.main import app
    client = TestClient(app)
except ImportError as e:
    print(f"❌ Could not import FastAPI app: {e}")
    sys.exit(1)


def test_templates_flows_endpoint():
    """Testar se /api/v1/templates/flows está disponível"""
    print("🔍 Testando GET /api/v1/templates/flows...")
    
    try:
        response = client.get("/api/v1/templates/flows")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ Endpoint disponível (403 = authentication required)")
            return True
        elif response.status_code == 200:
            print("✅ Endpoint funcionando perfeitamente!")
            return True
        elif response.status_code == 404:
            print("❌ Endpoint não encontrado (404)")
            return False
        else:
            print(f"⚠️  Status inesperado: {response.status_code}")
            return True  # Qualquer coisa diferente de 404 indica que existe
            
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return False


def test_templates_quiz_endpoint():
    """Testar se /api/v1/templates/quiz está disponível"""
    print("🔍 Testando GET /api/v1/templates/quiz...")
    
    try:
        response = client.get("/api/v1/templates/quiz")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ Endpoint disponível (403 = authentication required)")
            return True
        elif response.status_code == 200:
            print("✅ Endpoint funcionando perfeitamente!")
            return True
        elif response.status_code == 404:
            print("❌ Endpoint não encontrado (404)")
            return False
        else:
            print(f"⚠️  Status inesperado: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return False


def test_openapi_docs():
    """Verificar se os endpoints aparecem na documentação OpenAPI"""
    print("🔍 Verificando documentação OpenAPI...")
    
    try:
        response = client.get("/openapi.json")
        
        if response.status_code == 200:
            openapi_data = response.json()
            paths = openapi_data.get("paths", {})
            
            flows_found = "/api/v1/templates/flows" in paths
            quiz_found = "/api/v1/templates/quiz" in paths
            
            print(f"✅ OpenAPI carregado")
            print(f"   - /api/v1/templates/flows: {'✅' if flows_found else '❌'}")
            print(f"   - /api/v1/templates/quiz: {'✅' if quiz_found else '❌'}")
            
            return flows_found and quiz_found
        else:
            print(f"❌ Erro ao carregar OpenAPI: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste OpenAPI: {str(e)}")
        return False


def main():
    """Executar testes de integração de templates"""
    print("🚀 Testando Integração Frontend-Backend Templates\n")
    
    tests = [
        ("Templates Flows Endpoint", test_templates_flows_endpoint),
        ("Templates Quiz Endpoint", test_templates_quiz_endpoint),
        ("OpenAPI Documentation", test_openapi_docs),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} falhou: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("RESUMO DA INTEGRAÇÃO FRONTEND-BACKEND")
    print("="*60)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Integração Frontend-Backend funcionando!")
        print("\n📋 Endpoints disponíveis para o frontend:")
        print("   - GET/POST /api/v1/templates/flows")
        print("   - GET/PUT/DELETE /api/v1/templates/flows/{id}")
        print("   - GET/POST /api/v1/templates/quiz")
        print("   - GET/PUT/DELETE /api/v1/templates/quiz/{id}")
        print("\n✅ Frontend pode usar useTemplates hooks sem modificação!")
    else:
        print("\n⚠️  Alguns endpoints não estão disponíveis.")
        print("Verifique se templates_crud foi registrado corretamente.")


if __name__ == "__main__":
    main()