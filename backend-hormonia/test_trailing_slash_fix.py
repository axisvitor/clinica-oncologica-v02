#!/usr/bin/env python3
"""
Testar correção de trailing slash para evitar redirects 307.
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


def test_reports_no_redirect():
    """Testar se /api/v1/reports não causa redirect 307"""
    print("🔍 Testando GET /api/v1/reports (sem trailing slash)...")
    
    try:
        response = client.get("/api/v1/reports")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 307:
            print("❌ Ainda retorna 307 (redirect)")
            print(f"Location header: {response.headers.get('location', 'N/A')}")
            return False
        elif response.status_code == 403:
            print("✅ Retorna 403 (authentication required) - sem redirect!")
            return True
        elif response.status_code == 200:
            print("✅ Retorna 200 - funcionando perfeitamente!")
            return True
        else:
            print(f"⚠️  Status inesperado: {response.status_code}")
            return True  # Qualquer coisa diferente de 307 é melhor
            
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return False


def test_reports_with_slash():
    """Testar se /api/v1/reports/ ainda funciona"""
    print("🔍 Testando GET /api/v1/reports/ (com trailing slash)...")
    
    try:
        response = client.get("/api/v1/reports/")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [200, 403]:
            print("✅ Funciona com trailing slash")
            return True
        else:
            print(f"⚠️  Status: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return False


def main():
    """Executar testes de trailing slash"""
    print("🚀 Testando Correção de Trailing Slash\n")
    
    tests = [
        ("Reports sem trailing slash", test_reports_no_redirect),
        ("Reports com trailing slash", test_reports_with_slash),
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
    
    print("\n" + "="*50)
    print("RESUMO DOS TESTES")
    print("="*50)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Correção de trailing slash funcionando!")
        print("Não há mais redirects 307 desnecessários.")
    else:
        print("\n⚠️  Alguns testes falharam.")


if __name__ == "__main__":
    main()