#!/usr/bin/env python3
"""
Script para verificar o status do Celery e suas tasks.
"""
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

print("=" * 60)
print("🔍 VERIFICANDO CONFIGURAÇÃO DO CELERY")
print("=" * 60)

try:
    from app.config import settings
    
    print("\n📋 Configurações do Celery:")
    print(f"   CELERY_BROKER_URL: {settings.CELERY_BROKER_URL[:50]}...")
    print(f"   CELERY_RESULT_BACKEND: {settings.CELERY_RESULT_BACKEND[:50]}...")
    
    # Tentar importar o celery app
    print("\n🔧 Importando Celery App...")
    from app.celery_app import celery_app
    
    print("   ✅ Celery App importado com sucesso")
    
    # Listar tasks registradas
    print("\n📝 Tasks registradas:")
    registered_tasks = list(celery_app.tasks.keys())
    
    # Filtrar apenas tasks do app (não built-in)
    app_tasks = [t for t in registered_tasks if not t.startswith('celery.')]
    
    if app_tasks:
        for task in sorted(app_tasks):
            print(f"   - {task}")
        print(f"\n   Total: {len(app_tasks)} tasks")
    else:
        print("   ⚠️  Nenhuma task do app encontrada")
    
    # Verificar se há tasks relacionadas a onboarding/saga
    print("\n🔍 Tasks relacionadas a onboarding/saga:")
    onboarding_tasks = [t for t in app_tasks if 'onboard' in t.lower() or 'saga' in t.lower()]
    
    if onboarding_tasks:
        for task in onboarding_tasks:
            print(f"   ✅ {task}")
    else:
        print("   ⚠️  Nenhuma task de onboarding encontrada")
    
    # Verificar configuração de ENABLE_SAGA_PATTERN
    print("\n⚙️  Configurações de Saga:")
    enable_saga = settings.get("ENABLE_SAGA_PATTERN", True)
    print(f"   ENABLE_SAGA_PATTERN: {enable_saga}")
    
    # Tentar verificar se Celery está rodando
    print("\n🔌 Verificando conexão com Celery...")
    try:
        # Tentar fazer ping no Celery
        inspect = celery_app.control.inspect()
        active = inspect.active()
        
        if active:
            print(f"   ✅ Celery está rodando!")
            print(f"   Workers ativos: {len(active)}")
            for worker, tasks in active.items():
                print(f"      - {worker}: {len(tasks)} tasks ativas")
        else:
            print("   ⚠️  Celery não está respondendo")
            print("   ℹ️  Nenhum worker ativo encontrado")
            
    except Exception as e:
        print(f"   ❌ Não foi possível conectar ao Celery: {e}")
        print("   ℹ️  Celery provavelmente não está rodando")
    
    print("\n" + "=" * 60)
    print("📊 RESUMO")
    print("=" * 60)
    print(f"✅ Celery configurado: Sim")
    print(f"✅ Tasks registradas: {len(app_tasks)}")
    print(f"{'✅' if onboarding_tasks else '⚠️ '} Tasks de onboarding: {len(onboarding_tasks)}")
    print(f"⚙️  Saga habilitada: {enable_saga}")
    
    print("\n💡 Para iniciar o Celery:")
    print("   cd backend-hormonia")
    print("   celery -A app.celery_app worker --beat --loglevel=info --pool=solo")
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
