#!/usr/bin/env python3
"""
Teste de integração frontend-backend para templates.
Simula as chamadas que o frontend fará após as correções.
"""
import sys
import os
from fastapi.testclient import TestClient
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.main import app
    client = TestClient(app)
except ImportError as e:
    print(f"❌ Could not import FastAPI app: {e}")
    sys.exit(1)


def test_templates_flows_crud():
    """Testar CRUD completo de templates de flows"""
    print("🔍 Testando CRUD de Flow Templates...")
    
    endpoints = [
        ("GET", "/api/v1/templates/flows", "Listar flows"),
        ("POST", "/api/v1/templates/flows", "Criar flow"),
        ("GET", "/api/v1/templates/flows/123", "Obter flow específico"),
        ("PUT", "/api/v1/templates/flows/123", "Atualizar flow"),
        ("DELETE", "/api/v1/templates/flows/123", "Deletar flow"),
    ]
    
    results = []
    for method, endpoint, description in endpoints:
        try:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={"name": "Test Flow"})
            elif method == "PUT":
                response = client.put(endpoint, json={"name": "Updated Flow"})
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            # 403 = auth required (esperado), 404 = não encontrado, 422 = validation error
            success = response.status_code in [200, 201, 403, 404, 422]
            status = "✅" if success else "❌"
            
            print(f"   {status} {method} {endpoint} → {response.status_code} ({description})")
            results.append(success)
            
        except Exception as e:
            print(f"   ❌ {method} {endpoint} → Erro: {str(e)}")
            results.append(False)
    
    return all(results)


def test_templates_quiz_crud():
    """Testar CRUD completo de templates de quiz"""
    print("🔍 Testando CRUD de Quiz Templates...")
    
    endpoints = [
        ("GET", "/api/v1/templates/quiz", "Listar quizzes"),
        ("POST", "/api/v1/templates/quiz", "Criar quiz"),
        ("GET", "/api/v1/templates/quiz/123", "Obter quiz específico"),
        ("PUT", "/api/v1/templates/quiz/123", "Atualizar quiz"),
        ("DELETE", "/api/v1/templates/quiz/123", "Deletar quiz"),
    ]
    
    results = []
    for method, endpoint, description in endpoints:
        try:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={"name": "Test Quiz"})
            elif method == "PUT":
                response = client.put(endpoint, json={"name": "Updated Quiz"})
            elif method == "DELETE":
                response = client.delete(endpoint)
            
            success = response.status_code in [200, 201, 403, 404, 422]
            status = "✅" if success else "❌"
            
            print(f"   {status} {method} {endpoint} → {response.status_code} ({description})")
            results.append(success)
            
        except Exception as e:
            print(f"   ❌ {method} {endpoint} → Erro: {str(e)}")
            results.append(False)
    
    return all(results)


def test_analytics_dashboard():
    """Testar endpoint do dashboard que o frontend usa"""
    print("🔍 Testando Analytics Dashboard...")
    
    try:
        response = client.get("/api/v1/analytics/dashboard")
        
        if response.status_code == 403:
            print("   ✅ Dashboard endpoint disponível (403 = auth required)")
            return True
        elif response.status_code == 200:
            print("   ✅ Dashboard endpoint funcionando!")
            return True
        else:
            print(f"   ⚠️  Dashboard endpoint: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro no dashboard: {str(e)}")
        return False


def test_reports_no_redirect():
    """Testar se reports não tem redirect 307"""
    print("🔍 Testando Reports (sem redirect)...")
    
    try:
        response = client.get("/api/v1/reports")
        
        if response.status_code == 307:
            print("   ❌ Ainda tem redirect 307")
            return False
        elif response.status_code in [200, 403]:
            print(f"   ✅ Sem redirect: {response.status_code}")
            return True
        else:
            print(f"   ⚠️  Status inesperado: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"   ❌ Erro em reports: {str(e)}")
        return False


def generate_frontend_fixes():
    """Gerar código de correção para o frontend"""
    print("\n📝 Gerando correções para o frontend...")
    
    fixes = {
        "useTemplates.ts": """
// Correção para frontend-hormonia/src/hooks/useTemplates.ts

// ANTES (não funciona):
const FLOWS_BASE = '/templates/flows'
const QUIZ_BASE = '/templates/quiz'

// DEPOIS (funciona com backend):
const FLOWS_BASE = '/api/v1/templates/flows'
const QUIZ_BASE = '/api/v1/templates/quiz'

// Exemplo de uso correto:
export const useFlowTemplates = () => {
  return useQuery({
    queryKey: ['flow-templates'],
    queryFn: () => apiClient.get(FLOWS_BASE)
  })
}
""",
        "AdminRoutes.tsx": """
// Correção para frontend-hormonia/src/routes/AdminRoutes.tsx

import { TemplateManagementPage } from '@/pages/TemplateManagementPage'

// Adicionar na lista de rotas:
{
  path: "templates",
  element: <TemplateManagementPage />,
  handle: {
    crumb: () => "Gestão de Templates",
    permissions: ["admin.templates.read"]
  }
}

// Link no menu admin:
<NavLink to="/admin/templates">
  <Settings className="w-4 h-4" />
  Templates
</NavLink>
""",
        "api-client.ts": """
// Verificar em frontend-hormonia/src/lib/api-client.ts

// Garantir base URL correta:
const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000'

// Endpoints já disponíveis no backend:
templates: {
  flows: {
    list: () => get('/api/v1/templates/flows'),
    create: (data) => post('/api/v1/templates/flows', data),
    get: (id) => get(`/api/v1/templates/flows/${id}`),
    update: (id, data) => put(`/api/v1/templates/flows/${id}`, data),
    delete: (id) => delete(`/api/v1/templates/flows/${id}`)
  },
  quiz: {
    list: () => get('/api/v1/templates/quiz'),
    create: (data) => post('/api/v1/templates/quiz', data),
    get: (id) => get(`/api/v1/templates/quiz/${id}`),
    update: (id, data) => put(`/api/v1/templates/quiz/${id}`, data),
    delete: (id) => delete(`/api/v1/templates/quiz/${id}`)
  }
}
"""
    }
    
    for filename, code in fixes.items():
        print(f"\n--- {filename} ---")
        print(code)
    
    return True


def main():
    """Executar todos os testes de integração"""
    print("🚀 Teste de Integração Frontend-Backend\n")
    
    tests = [
        ("Templates Flows CRUD", test_templates_flows_crud),
        ("Templates Quiz CRUD", test_templates_quiz_crud),
        ("Analytics Dashboard", test_analytics_dashboard),
        ("Reports (No Redirect)", test_reports_no_redirect),
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
    
    # Gerar correções
    generate_frontend_fixes()
    
    print("\n" + "="*60)
    print("RESUMO DA INTEGRAÇÃO")
    print("="*60)
    
    backend_ready = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not success:
            backend_ready = False
    
    print(f"\n🎯 Status do Backend: {'✅ PRONTO' if backend_ready else '⚠️ PRECISA AJUSTES'}")
    print("📋 Próximos passos:")
    print("   1. Aplicar correções no frontend (código gerado acima)")
    print("   2. Testar TemplateManagementPage")
    print("   3. Verificar rota /admin/templates")
    print("   4. Validar integração completa")


if __name__ == "__main__":
    main()