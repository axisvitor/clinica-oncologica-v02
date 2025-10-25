#!/usr/bin/env python3
"""
Script para investigar o problema do Auth Login.
"""
import sys
import requests
from pathlib import Path

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

print("=" * 60)
print("🔍 INVESTIGANDO PROBLEMA DO AUTH LOGIN")
print("=" * 60)

API_BASE_URL = "http://localhost:8000"

# 1. Testar health (não depende de auth)
print("\n1️⃣ Testando /health...")
try:
    response = requests.get(f"{API_BASE_URL}/health", timeout=5)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Health OK")
    else:
        print(f"   ❌ Health falhou")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# 2. Testar endpoint de test (se DEBUG=True)
print("\n2️⃣ Testando /test...")
try:
    response = requests.get(f"{API_BASE_URL}/test", timeout=5)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Test OK: {data}")
    else:
        print(f"   ⚠️  Test endpoint não disponível (DEBUG=False)")
except Exception as e:
    print(f"   ⚠️  {e}")

# 3. Testar login com dados válidos
print("\n3️⃣ Testando /api/v1/auth/login...")
try:
    response = requests.post(
        f"{API_BASE_URL}/api/v1/auth/login",
        data={"username": "test@test.com", "password": "test"},
        timeout=5
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    if response.status_code == 410:
        print(f"   ✅ Login desabilitado (esperado - Firebase only)")
    elif response.status_code == 500:
        print(f"   ❌ Erro 500 - Service provider initialization failed")
        print(f"   Causa: Problema na inicialização do AuthService")
    else:
        print(f"   ⚠️  Status inesperado")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# 4. Verificar se session_manager está inicializado
print("\n4️⃣ Verificando session_manager...")
try:
    from app.core.session_manager import get_request_factory
    
    try:
        factory = get_request_factory()
        print(f"   ✅ Session manager inicializado")
    except RuntimeError as e:
        print(f"   ❌ Session manager NÃO inicializado: {e}")
        print(f"   Solução: Inicializar session_manager no startup")
except Exception as e:
    print(f"   ❌ Erro ao importar: {e}")

# 5. Verificar ServiceProvider
print("\n5️⃣ Verificando ServiceProvider...")
try:
    from app.services import ServiceProvider
    from app.database import get_db
    
    # Tentar criar um ServiceProvider manualmente
    db = next(get_db())
    provider = ServiceProvider(db)
    print(f"   ✅ ServiceProvider pode ser criado manualmente")
    
    # Tentar acessar auth_service
    try:
        auth_service = provider.auth_service
        print(f"   ✅ AuthService acessível")
    except Exception as e:
        print(f"   ❌ Erro ao acessar AuthService: {e}")
        
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("\n" + "=" * 60)
print("📊 DIAGNÓSTICO")
print("=" * 60)

print("""
PROBLEMA IDENTIFICADO:
- Auth Login retorna 500 com "Service provider initialization failed"
- Causa: get_thread_safe_service_provider() falha ao inicializar

POSSÍVEIS CAUSAS:
1. Session manager não foi inicializado no startup
2. Erro na validação da sessão
3. Problema com dependências circulares

SOLUÇÃO:
1. Verificar se initialize_session_manager() é chamado no startup
2. Verificar logs do backend para erro específico
3. Considerar usar endpoint sem autenticação para testes
""")

print("=" * 60)
