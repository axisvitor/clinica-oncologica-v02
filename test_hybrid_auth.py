#!/usr/bin/env python3
"""
Test script para verificar autenticação híbrida
Testa se endpoints funcionam com Bearer token quando session não está disponível
"""

import requests
import json
import os
from datetime import datetime

# Configuração
BASE_URL = "http://localhost:8000"
FIREBASE_TOKEN = "test-firebase-token-123"  # Token de teste

def test_endpoint(endpoint, method="GET", data=None, use_bearer=True, use_session=False):
    """Testa um endpoint com diferentes tipos de autenticação"""
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Adicionar Bearer token se solicitado
    if use_bearer:
        headers["Authorization"] = f"Bearer {FIREBASE_TOKEN}"
    
    # Para session, usaríamos cookies (simulado aqui)
    cookies = {}
    if use_session:
        cookies["session_id"] = "test-session-123"
    
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, cookies=cookies)
        elif method == "POST":
            response = requests.post(url, headers=headers, cookies=cookies, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, cookies=cookies, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, cookies=cookies)
        
        return {
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "response": response.json() if response.content else None,
            "error": None
        }
    
    except Exception as e:
        return {
            "status_code": None,
            "success": False,
            "response": None,
            "error": str(e)
        }

def main():
    print("🧪 Testando Autenticação Híbrida")
    print("=" * 50)
    
    # Endpoints para testar
    test_cases = [
        # API v2 (já migrados para session)
        {
            "name": "API v2 Analytics - Patients Overview",
            "endpoint": "/api/v2/analytics/patients/overview",
            "method": "GET",
            "expected_auth": "session"
        },
        {
            "name": "API v2 Patients - List",
            "endpoint": "/api/v2/patients/",
            "method": "GET", 
            "expected_auth": "session"
        },
        
        # API v1 (ainda com Bearer token)
        {
            "name": "API v1 Patients - List",
            "endpoint": "/api/v1/patients/",
            "method": "GET",
            "expected_auth": "bearer"
        },
        {
            "name": "API v1 Messages - List",
            "endpoint": "/api/v1/messages/",
            "method": "GET",
            "expected_auth": "bearer"
        },
        {
            "name": "API v1 Quiz - Templates",
            "endpoint": "/api/v1/quiz/templates/",
            "method": "GET",
            "expected_auth": "bearer"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n📋 {test_case['name']}")
        print(f"   Endpoint: {test_case['endpoint']}")
        print(f"   Expected Auth: {test_case['expected_auth']}")
        
        # Teste com Bearer token
        bearer_result = test_endpoint(
            test_case['endpoint'], 
            test_case['method'], 
            use_bearer=True, 
            use_session=False
        )
        
        # Teste com Session (simulado)
        session_result = test_endpoint(
            test_case['endpoint'], 
            test_case['method'], 
            use_bearer=False, 
            use_session=True
        )
        
        print(f"   Bearer Token: {'✅' if bearer_result['success'] else '❌'} ({bearer_result['status_code']})")
        print(f"   Session Cookie: {'✅' if session_result['success'] else '❌'} ({session_result['status_code']})")
        
        results.append({
            "test_case": test_case,
            "bearer_result": bearer_result,
            "session_result": session_result
        })
    
    # Resumo
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES")
    print("=" * 50)
    
    bearer_success = sum(1 for r in results if r['bearer_result']['success'])
    session_success = sum(1 for r in results if r['session_result']['success'])
    total_tests = len(results)
    
    print(f"Bearer Token: {bearer_success}/{total_tests} sucessos")
    print(f"Session Cookie: {session_success}/{total_tests} sucessos")
    
    # Análise por tipo de API
    v1_results = [r for r in results if '/api/v1/' in r['test_case']['endpoint']]
    v2_results = [r for r in results if '/api/v2/' in r['test_case']['endpoint']]
    
    if v1_results:
        v1_bearer = sum(1 for r in v1_results if r['bearer_result']['success'])
        print(f"\nAPI v1 (Bearer): {v1_bearer}/{len(v1_results)} sucessos")
    
    if v2_results:
        v2_session = sum(1 for r in v2_results if r['session_result']['success'])
        print(f"API v2 (Session): {v2_session}/{len(v2_results)} sucessos")
    
    # Recomendações
    print("\n🎯 RECOMENDAÇÕES:")
    
    failed_bearer = [r for r in results if not r['bearer_result']['success'] and r['bearer_result']['status_code'] == 403]
    if failed_bearer:
        print("❌ Endpoints com erro 403 (Bearer token):")
        for r in failed_bearer:
            print(f"   - {r['test_case']['endpoint']}")
        print("   → Estes endpoints precisam ser migrados para session auth")
    
    failed_session = [r for r in results if not r['session_result']['success'] and r['session_result']['status_code'] == 403]
    if failed_session:
        print("❌ Endpoints com erro 403 (Session):")
        for r in failed_session:
            print(f"   - {r['test_case']['endpoint']}")
        print("   → Estes endpoints ainda dependem de Bearer token")
    
    # Salvar resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hybrid_auth_test_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "bearer_success": bearer_success,
                "session_success": session_success
            },
            "results": results
        }, f, indent=2)
    
    print(f"\n💾 Resultados salvos em: {filename}")

if __name__ == "__main__":
    main()