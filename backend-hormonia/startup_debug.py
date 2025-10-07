"""
Script de diagnóstico para capturar erros de startup do Railway.
Execute antes do uvicorn para identificar problemas de configuração.
"""
import sys
import os
import logging

# Configure logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def check_environment():
    """Verifica variáveis de ambiente críticas."""
    logger.info("=== STARTUP DEBUG - Verificando Ambiente ===")

    required_vars = [
        'DATABASE_URL',
        'REDIS_URL',
        'SECRET_KEY',
        'FIREBASE_ADMIN_PROJECT_ID',
        'FIREBASE_ADMIN_PRIVATE_KEY',
        'FIREBASE_ADMIN_CLIENT_EMAIL'
    ]

    optional_vars = [
        'PORT',
        'ENVIRONMENT',
        'DEBUG',
        'CSRF_SECRET_KEY',
        'ENCRYPTION_KEY'
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            logger.error(f"❌ MISSING: {var}")
        else:
            # Mask sensitive values
            if 'KEY' in var or 'SECRET' in var or 'PASSWORD' in var:
                display = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
            elif 'URL' in var:
                display = value.split('@')[-1] if '@' in value else value
            else:
                display = value[:50]
            logger.info(f"✓ {var}: {display}")

    for var in optional_vars:
        value = os.getenv(var)
        if value:
            if 'KEY' in var or 'SECRET' in var:
                display = "***"
            else:
                display = value[:50]
            logger.info(f"  {var}: {display}")

    if missing:
        logger.error(f"\n❌ ERRO: {len(missing)} variáveis obrigatórias faltando: {', '.join(missing)}")
        return False

    logger.info("\n✓ Todas as variáveis obrigatórias estão configuradas")
    return True

def check_imports():
    """Verifica imports críticos."""
    logger.info("\n=== Verificando Imports Críticos ===")

    critical_imports = [
        ('fastapi', 'FastAPI'),
        ('pydantic_settings', 'BaseSettings'),
        ('sqlalchemy', 'create_engine'),
        ('redis', 'Redis'),
        ('uvicorn', 'run'),
    ]

    failed = []
    for module, item in critical_imports:
        try:
            mod = __import__(module, fromlist=[item])
            logger.info(f"✓ {module}.{item}")
        except ImportError as e:
            logger.error(f"❌ FAILED: {module}.{item} - {e}")
            failed.append(module)

    if failed:
        logger.error(f"\n❌ {len(failed)} imports críticos falharam")
        return False

    logger.info("\n✓ Todos os imports críticos OK")
    return True

def check_config():
    """Verifica se config.py carrega sem erros."""
    logger.info("\n=== Verificando Config ===")

    try:
        from app.config import settings
        logger.info(f"✓ Config carregado")
        logger.info(f"  DEBUG: {settings.DEBUG}")
        logger.info(f"  ENVIRONMENT: {settings.ENVIRONMENT}")

        # Test database URL parsing
        db_url = settings.DATABASE_URL
        if '@' in db_url:
            logger.info(f"  DATABASE: {db_url.split('@')[-1]}")
        else:
            logger.info(f"  DATABASE: {db_url[:30]}...")

        return True
    except Exception as e:
        logger.error(f"❌ ERRO ao carregar config: {e}")
        logger.error(f"   Tipo: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def check_database():
    """Verifica conexão com database."""
    logger.info("\n=== Verificando Database ===")

    try:
        from app.database import test_connection
        result = test_connection()
        if result:
            logger.info(f"✓ Database conectado: {result}")
            return True
        else:
            logger.error("❌ Database não conectou")
            return False
    except Exception as e:
        logger.error(f"❌ ERRO ao conectar database: {e}")
        logger.error(f"   Tipo: {type(e).__name__}")
        return False

def check_redis():
    """Verifica conexão com Redis."""
    logger.info("\n=== Verificando Redis ===")

    try:
        from app.core.redis_manager import get_redis_manager
        redis_manager = get_redis_manager()

        # Test sync connection
        sync_client = redis_manager.get_compatible_client("sync")
        sync_client.ping()
        logger.info("✓ Redis conectado (sync)")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Redis não conectou: {e}")
        logger.warning("   App pode rodar sem Redis (features limitadas)")
        return False

def check_app_creation():
    """Verifica se app FastAPI pode ser criado."""
    logger.info("\n=== Verificando App Creation ===")

    try:
        from app.main import app
        logger.info(f"✓ FastAPI app criado")
        logger.info(f"  Title: {app.title}")
        logger.info(f"  Version: {app.version}")
        logger.info(f"  Routes: {len(app.routes)}")
        return True
    except Exception as e:
        logger.error(f"❌ ERRO ao criar app: {e}")
        logger.error(f"   Tipo: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Executa todos os checks."""
    logger.info("=" * 60)
    logger.info("RAILWAY STARTUP DIAGNOSTIC")
    logger.info("=" * 60)

    checks = [
        ("Environment Variables", check_environment),
        ("Critical Imports", check_imports),
        ("Configuration", check_config),
        ("Database Connection", check_database),
        ("Redis Connection", check_redis),
        ("App Creation", check_app_creation),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            logger.error(f"❌ {name} check crashed: {e}")
            results[name] = False

    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    for name, result in results.items():
        status = "✓ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {name}")

    all_passed = all(results.values())
    critical_passed = all([
        results.get("Environment Variables", False),
        results.get("Configuration", False),
        results.get("App Creation", False)
    ])

    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("✓ ALL CHECKS PASSED - Ready for startup")
        sys.exit(0)
    elif critical_passed:
        logger.warning("⚠️  SOME CHECKS FAILED - App may run with limited features")
        sys.exit(0)
    else:
        logger.error("❌ CRITICAL CHECKS FAILED - Startup will likely fail")
        sys.exit(1)

if __name__ == "__main__":
    main()
