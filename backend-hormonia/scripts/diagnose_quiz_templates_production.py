#!/usr/bin/env python3
"""
Script para diagnosticar o erro 500 no endpoint /api/v1/quiz/templates em produção
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from typing import Dict, Any
import traceback

def test_endpoint_direct():
    """Testa o endpoint diretamente via HTTP"""
    
    print("🌐 Testando endpoint /api/v1/quiz/templates via HTTP")
    print("=" * 60)
    
    # URL base (ajuste conforme necessário)
    base_url = "http://localhost:8000"  # ou sua URL de produção
    endpoint = f"{base_url}/api/v1/quiz/templates"
    
    try:
        print(f"1. Fazendo requisição GET para: {endpoint}")
        
        # Teste sem autenticação primeiro
        print("\n   Teste 1: Sem autenticação")
        response = requests.get(endpoint, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 401:
            print("   ✅ Erro 401 - Autenticação necessária (esperado)")
        elif response.status_code == 500:
            print("   ❌ Erro 500 - Problema interno")
            print(f"   Response: {response.text[:500]}")
        else:
            print(f"   Response: {response.text[:500]}")
        
        # Teste com token (se disponível)
        print("\n   Teste 2: Com token de autenticação")
        
        # Primeiro, tentar fazer login para obter token
        login_url = f"{base_url}/api/v1/auth/login"
        login_data = {
            "email": "admin@hormonia.com",  # ajuste conforme necessário
            "password": "admin123"  # ajuste conforme necessário
        }
        
        try:
            login_response = requests.post(login_url, json=login_data, timeout=10)
            print(f"   Login status: {login_response.status_code}")
            
            if login_response.status_code == 200:
                token_data = login_response.json()
                access_token = token_data.get("access_token")
                
                if access_token:
                    headers = {"Authorization": f"Bearer {access_token}"}
                    auth_response = requests.get(endpoint, headers=headers, timeout=10)
                    
                    print(f"   Status com auth: {auth_response.status_code}")
                    print(f"   Response time: {auth_response.elapsed.total_seconds():.3f}s")
                    
                    if auth_response.status_code == 500:
                        print("   ❌ Ainda erro 500 mesmo com autenticação")
                        print(f"   Response: {auth_response.text[:500]}")
                    elif auth_response.status_code == 200:
                        print("   ✅ Sucesso com autenticação!")
                        data = auth_response.json()
                        print(f"   Templates retornados: {len(data.get('templates', []))}")
                    else:
                        print(f"   Status inesperado: {auth_response.status_code}")
                        print(f"   Response: {auth_response.text[:500]}")
                else:
                    print("   ❌ Token não encontrado na resposta do login")
            else:
                print(f"   ❌ Falha no login: {login_response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Erro no teste com autenticação: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste HTTP: {e}")
        traceback.print_exc()
        return False

def test_dependencies():
    """Testa as dependências do endpoint"""
    
    print("\n🔧 Testando dependências do endpoint")
    print("=" * 60)
    
    try:
        # Teste 1: Importações
        print("1. Testando importações...")
        
        from app.api.v1.quiz import get_quiz_templates
        from app.dependencies.services import get_quiz_template_service
        from app.dependencies.auth import get_current_user
        from app.dependencies.pagination import get_pagination_params
        from app.services.quiz import QuizTemplateService
        
        print("   ✅ Todas as importações funcionaram")
        
        # Teste 2: Instanciação do serviço
        print("\n2. Testando instanciação do serviço...")
        service = get_quiz_template_service()
        print(f"   ✅ Serviço instanciado: {type(service)}")
        
        # Teste 3: Verificar se há problemas com schemas
        print("\n3. Testando schemas de resposta...")
        from app.schemas.quiz import QuizTemplateResponse, QuizTemplateListResponse
        print("   ✅ Schemas importados com sucesso")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro nas dependências: {e}")
        traceback.print_exc()
        return False

def test_database_connection():
    """Testa conexão com banco de dados"""
    
    print("\n🗄️ Testando conexão com banco de dados")
    print("=" * 60)
    
    try:
        from app.core.database import get_db
        from app.models.quiz import QuizTemplate
        
        print("1. Obtendo sessão do banco...")
        db_gen = get_db()
        db = next(db_gen)
        print("   ✅ Sessão obtida")
        
        print("\n2. Testando query simples...")
        count = db.query(QuizTemplate).count()
        print(f"   ✅ Total de templates: {count}")
        
        print("\n3. Testando query com filtros...")
        active_count = db.query(QuizTemplate).filter(QuizTemplate.is_active == True).count()
        print(f"   ✅ Templates ativos: {active_count}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na conexão com banco: {e}")
        traceback.print_exc()
        return False

def test_middleware_and_auth():
    """Testa middleware e autenticação"""
    
    print("\n🔐 Testando middleware e autenticação")
    print("=" * 60)
    
    try:
        # Teste 1: Verificar configuração de CORS
        print("1. Verificando configuração de CORS...")
        from app.core.config import settings
        print(f"   CORS origins: {getattr(settings, 'BACKEND_CORS_ORIGINS', 'Não configurado')}")
        
        # Teste 2: Verificar middleware de autenticação
        print("\n2. Verificando middleware de autenticação...")
        from app.dependencies.auth import get_current_user
        print("   ✅ Função de autenticação importada")
        
        # Teste 3: Verificar JWT settings
        print("\n3. Verificando configurações JWT...")
        jwt_secret = getattr(settings, 'SECRET_KEY', None)
        if jwt_secret:
            print("   ✅ JWT secret configurado")
        else:
            print("   ❌ JWT secret não configurado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de middleware: {e}")
        traceback.print_exc()
        return False

def check_environment():
    """Verifica variáveis de ambiente"""
    
    print("\n🌍 Verificando variáveis de ambiente")
    print("=" * 60)
    
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'ALGORITHM',
        'ACCESS_TOKEN_EXPIRE_MINUTES'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mascarar valores sensíveis
            if 'SECRET' in var or 'PASSWORD' in var or 'KEY' in var:
                display_value = f"{'*' * (len(value) - 4)}{value[-4:]}" if len(value) > 4 else "***"
            else:
                display_value = value
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ❌ {var}: NÃO CONFIGURADO")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n   ⚠️  Variáveis faltando: {', '.join(missing_vars)}")
        return False
    
    return True

def main():
    """Função principal"""
    
    print("🔍 DIAGNÓSTICO COMPLETO - Quiz Templates Endpoint")
    print("=" * 70)
    
    # Executar todos os testes
    tests = [
        ("Variáveis de ambiente", check_environment),
        ("Dependências", test_dependencies),
        ("Conexão com banco", test_database_connection),
        ("Middleware e autenticação", test_middleware_and_auth),
        ("Endpoint HTTP", test_endpoint_direct)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name.upper()} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Erro crítico no teste {test_name}: {e}")
            results[test_name] = False
    
    # Resumo final
    print("\n" + "=" * 70)
    print("📊 RESUMO DO DIAGNÓSTICO")
    print("=" * 70)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
    
    failed_tests = [name for name, result in results.items() if not result]
    
    if failed_tests:
        print(f"\n❌ TESTES QUE FALHARAM: {', '.join(failed_tests)}")
        print("\n🔧 PRÓXIMOS PASSOS:")
        
        if "Variáveis de ambiente" in failed_tests:
            print("   1. Configurar variáveis de ambiente faltando")
        
        if "Conexão com banco" in failed_tests:
            print("   2. Verificar conexão com banco de dados")
        
        if "Middleware e autenticação" in failed_tests:
            print("   3. Verificar configuração de autenticação")
        
        if "Endpoint HTTP" in failed_tests:
            print("   4. Verificar logs do servidor para erros específicos")
    else:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("\n   Se ainda há erro 500, verifique:")
        print("   1. Logs do servidor em tempo real")
        print("   2. Configuração de proxy/load balancer")
        print("   3. Limites de recursos (CPU/memória)")

if __name__ == "__main__":
    main()