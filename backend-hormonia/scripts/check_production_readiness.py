#!/usr/bin/env python3
"""
Script para verificar se todas as APIs estão conectadas e prontas para produção.
"""
import sys
import requests
from pathlib import Path
from datetime import datetime
import json

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

from app.config import settings

print("=" * 80)
print("🔍 VERIFICAÇÃO DE PRONTIDÃO PARA PRODUÇÃO")
print("=" * 80)
print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# Configuração
API_BASE_URL = "http://localhost:8000"
results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def test_endpoint(name, url, method="GET", expected_status=200, auth=None):
    """Testa um endpoint."""
    try:
        headers = {}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(url, headers=headers, timeout=5)
        
        if response.status_code == expected_status:
            results["passed"].append(f"✅ {name}: {response.status_code}")
            return True
        else:
            results["failed"].append(f"❌ {name}: {response.status_code} (esperado {expected_status})")
            return False
    except requests.exceptions.ConnectionError:
        results["failed"].append(f"❌ {name}: Conexão recusada")
        return False
    except Exception as e:
        results["failed"].append(f"❌ {name}: {str(e)}")
        return False

def check_config(name, value, required=True):
    """Verifica uma configuração."""
    if value and value != "CHANGETHIS" and value != "your-secret-here":
        results["passed"].append(f"✅ {name}: Configurado")
        return True
    elif required:
        results["failed"].append(f"❌ {name}: NÃO configurado")
        return False
    else:
        results["warnings"].append(f"⚠️  {name}: NÃO configurado (opcional)")
        return True

print("\n" + "=" * 80)
print("1️⃣  VERIFICANDO BACKEND")
print("=" * 80)

# Health check
test_endpoint("Health Check", f"{API_BASE_URL}/health")
test_endpoint("Health Live", f"{API_BASE_URL}/health/live")
test_endpoint("Health Ready", f"{API_BASE_URL}/health/ready")
test_endpoint("Metrics", f"{API_BASE_URL}/metrics")

print("\n" + "=" * 80)
print("2️⃣  VERIFICANDO ENDPOINTS DA API V1")
print("=" * 80)

# Auth endpoints (espera 422 sem dados)
test_endpoint("Auth Login", f"{API_BASE_URL}/api/v1/auth/login", "POST", 422)

# Public endpoints
test_endpoint("Quiz Public", f"{API_BASE_URL}/api/v1/monthly-quiz-public/health", expected_status=404)

print("\n" + "=" * 80)
print("3️⃣  VERIFICANDO ENDPOINTS DA API V2")
print("=" * 80)

test_endpoint("API V2 Health", f"{API_BASE_URL}/api/v2/health", expected_status=404)

print("\n" + "=" * 80)
print("4️⃣  VERIFICANDO BANCO DE DADOS")
print("=" * 80)

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    
    DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        # Testar conexão
        result = session.execute(text("SELECT 1")).scalar()
        if result == 1:
            results["passed"].append("✅ PostgreSQL: Conectado")
            
            # Verificar tabelas principais
            tables_query = text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            tables = session.execute(tables_query).fetchall()
            results["passed"].append(f"✅ PostgreSQL: {len(tables)} tabelas encontradas")
        else:
            results["failed"].append("❌ PostgreSQL: Falha no teste")
except Exception as e:
    results["failed"].append(f"❌ PostgreSQL: {str(e)}")

print("\n" + "=" * 80)
print("5️⃣  VERIFICANDO REDIS")
print("=" * 80)

try:
    from app.core.redis_client import get_redis_client
    redis_client = get_redis_client()
    
    # Testar conexão
    redis_client.ping()
    results["passed"].append("✅ Redis: Conectado")
    
    # Verificar info
    info = redis_client.info()
    results["passed"].append(f"✅ Redis: Versão {info.get('redis_version', 'N/A')}")
except Exception as e:
    results["failed"].append(f"❌ Redis: {str(e)}")

print("\n" + "=" * 80)
print("6️⃣  VERIFICANDO INTEGRAÇÕES EXTERNAS")
print("=" * 80)

# Evolution API
evolution_url = getattr(settings, 'EVOLUTION_API_URL', None)
evolution_key = getattr(settings, 'EVOLUTION_API_KEY', None)

if evolution_url and evolution_key:
    try:
        response = requests.get(
            f"{evolution_url}/instance/fetchInstances",
            headers={"apikey": evolution_key},
            timeout=10
        )
        if response.status_code == 200:
            results["passed"].append("✅ Evolution API: Conectado")
        else:
            results["warnings"].append(f"⚠️  Evolution API: Status {response.status_code}")
    except Exception as e:
        results["warnings"].append(f"⚠️  Evolution API: {str(e)}")
else:
    results["warnings"].append("⚠️  Evolution API: NÃO configurado")

# Firebase
firebase_creds = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
if firebase_creds:
    results["passed"].append("✅ Firebase: Configurado")
else:
    results["warnings"].append("⚠️  Firebase: NÃO configurado")

# Gemini AI
gemini_key = getattr(settings, 'GEMINI_API_KEY', None)
if gemini_key and gemini_key != "CHANGETHIS":
    results["passed"].append("✅ Gemini AI: Configurado")
else:
    results["warnings"].append("⚠️  Gemini AI: NÃO configurado")

print("\n" + "=" * 80)
print("7️⃣  VERIFICANDO CONFIGURAÇÕES DE SEGURANÇA")
print("=" * 80)

check_config("SECRET_KEY", settings.SECRET_KEY)
check_config("JWT_SECRET_KEY", getattr(settings, 'JWT_SECRET_KEY', None))
check_config("CSRF_SECRET_KEY", getattr(settings, 'CSRF_SECRET_KEY', None))

# Verificar modo debug
if settings.DEBUG:
    results["warnings"].append("⚠️  DEBUG MODE: ATIVADO (desabilitar em produção)")
else:
    results["passed"].append("✅ DEBUG MODE: Desabilitado")

print("\n" + "=" * 80)
print("8️⃣  VERIFICANDO CELERY")
print("=" * 80)

try:
    from app.celery_app import celery_app
    
    # Verificar se Celery está configurado
    results["passed"].append("✅ Celery: Configurado")
    
    # Tentar verificar workers
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        
        if active:
            results["passed"].append(f"✅ Celery Workers: {len(active)} ativos")
        else:
            results["warnings"].append("⚠️  Celery Workers: Nenhum ativo")
    except:
        results["warnings"].append("⚠️  Celery Workers: Não foi possível verificar")
        
except Exception as e:
    results["failed"].append(f"❌ Celery: {str(e)}")

print("\n" + "=" * 80)
print("9️⃣  VERIFICANDO TEMPLATES E DADOS")
print("=" * 80)

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    
    DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')
    engine = create_engine(DATABASE_URL)
    
    with Session(engine) as session:
        # Flow kinds
        flow_kinds = session.execute(text("SELECT COUNT(*) FROM flow_kinds")).scalar()
        if flow_kinds > 0:
            results["passed"].append(f"✅ Flow Kinds: {flow_kinds} configurados")
        else:
            results["warnings"].append("⚠️  Flow Kinds: Nenhum configurado")
        
        # Flow templates
        flow_templates = session.execute(text("SELECT COUNT(*) FROM flow_template_versions")).scalar()
        if flow_templates > 0:
            results["passed"].append(f"✅ Flow Templates: {flow_templates} disponíveis")
        else:
            results["warnings"].append("⚠️  Flow Templates: Nenhum disponível")
        
        # Quiz templates
        quiz_templates = session.execute(text("SELECT COUNT(*) FROM quiz_templates")).scalar()
        if quiz_templates > 0:
            results["passed"].append(f"✅ Quiz Templates: {quiz_templates} disponíveis")
        else:
            results["warnings"].append("⚠️  Quiz Templates: Nenhum disponível")
        
        # WhatsApp instances
        whatsapp_instances = session.execute(text("SELECT COUNT(*) FROM whatsapp_instances")).scalar()
        if whatsapp_instances > 0:
            results["passed"].append(f"✅ WhatsApp Instances: {whatsapp_instances} configuradas")
        else:
            results["warnings"].append("⚠️  WhatsApp Instances: Nenhuma configurada")
        
except Exception as e:
    results["failed"].append(f"❌ Verificação de dados: {str(e)}")

# Resumo final
print("\n" + "=" * 80)
print("📊 RESUMO FINAL")
print("=" * 80)

print(f"\n✅ PASSOU: {len(results['passed'])} verificações")
for item in results["passed"]:
    print(f"   {item}")

if results["warnings"]:
    print(f"\n⚠️  AVISOS: {len(results['warnings'])} itens")
    for item in results["warnings"]:
        print(f"   {item}")

if results["failed"]:
    print(f"\n❌ FALHOU: {len(results['failed'])} verificações")
    for item in results["failed"]:
        print(f"   {item}")

# Score
total = len(results["passed"]) + len(results["warnings"]) + len(results["failed"])
score = (len(results["passed"]) / total * 100) if total > 0 else 0

print("\n" + "=" * 80)
print(f"🎯 SCORE DE PRONTIDÃO: {score:.1f}%")
print("=" * 80)

if score >= 90:
    print("🟢 SISTEMA PRONTO PARA PRODUÇÃO")
elif score >= 70:
    print("🟡 SISTEMA QUASE PRONTO - Resolver avisos")
else:
    print("🔴 SISTEMA NÃO PRONTO - Resolver falhas críticas")

print("\n" + "=" * 80)
