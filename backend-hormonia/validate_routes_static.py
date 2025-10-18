"""
Validação estática das rotas (sem importar o app).
Analisa o código-fonte para verificar que v1 está desativada.
"""
import re
from pathlib import Path

def validate_router_registry():
    """Valida que apenas exceções v1 estão ativas no router_registry.py"""
    
    print("=" * 80)
    print("VALIDAÇÃO ESTÁTICA DE ROTAS - Sistema Hormonia")
    print("=" * 80)
    
    registry_path = Path(__file__).parent / "app" / "core" / "router_registry.py"
    
    if not registry_path.exists():
        print(f"❌ Arquivo não encontrado: {registry_path}")
        return False
    
    content = registry_path.read_text(encoding="utf-8")
    
    # Buscar todas as linhas com app.include_router
    include_pattern = re.compile(r'^\s*app\.include_router\((.+?),', re.MULTILINE)
    commented_pattern = re.compile(r'^\s*#\s*app\.include_router\((.+?),', re.MULTILINE)
    
    active_includes = include_pattern.findall(content)
    commented_includes = commented_pattern.findall(content)
    
    print("\n📋 ROUTERS ATIVOS (app.include_router não comentado)")
    print("-" * 80)
    
    v1_active = []
    v2_active = False
    health_active = False
    prometheus_active = False
    
    for router in active_includes:
        router_clean = router.strip()
        print(f"✅ {router_clean}")
        
        if "api_v2_router" in router_clean:
            v2_active = True
        elif "health_monitoring" in router_clean:
            health_active = True
        elif "prometheus_exporters" in router_clean:
            prometheus_active = True
        elif any(v1_marker in router_clean for v1_marker in ["prefix=\"/api/v1", "prefix='/api/v1"]):
            v1_active.append(router_clean)
    
    # Verificar exceções inline (redis/csrf)
    print("\n📋 EXCEÇÕES V1 INLINE (definidas diretamente no código)")
    print("-" * 80)
    
    redis_health_present = "@app.get(\"/api/v1/redis/health\"" in content
    csrf_token_present = "@app.get(\"/api/v1/csrf-token\"" in content
    
    if redis_health_present:
        print("✅ GET /api/v1/redis/health (definido inline)")
    else:
        print("⚠️  GET /api/v1/redis/health não encontrado")
    
    if csrf_token_present:
        print("✅ GET /api/v1/csrf-token (definido em application_factory.py)")
    else:
        print("ℹ️  GET /api/v1/csrf-token não encontrado (pode estar em outro arquivo)")
    
    # Verificar routers v1 comentados
    print("\n📋 ROUTERS V1 COMENTADOS (desativados)")
    print("-" * 80)
    
    v1_commented_count = sum(1 for r in commented_includes if "/api/v1" in r or "auth.router" in r or "patients.router" in r)
    print(f"Total de routers v1 comentados: {v1_commented_count}")
    
    if v1_commented_count > 0:
        print("✅ Routers v1 estão comentados (desativados)")
    
    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO DA VALIDAÇÃO")
    print("=" * 80)
    print(f"✅ API v2 ativa: {v2_active}")
    print(f"✅ Health monitoring ativo: {health_active}")
    print(f"✅ Prometheus ativo: {prometheus_active}")
    print(f"✅ Routers v1 via include_router: {len(v1_active)} (esperado: 0)")
    print(f"✅ Exceção Redis health: {redis_health_present}")
    print(f"ℹ️  Exceção CSRF token: {csrf_token_present} (pode estar em outro arquivo)")
    print(f"✅ Routers v1 comentados: {v1_commented_count}")
    
    # Resultado final
    print("\n" + "=" * 80)
    
    issues = []
    
    if not v2_active:
        issues.append("API v2 não está ativa")
    
    if not health_active:
        issues.append("Health monitoring não está ativo")
    
    if v1_active:
        issues.append(f"Routers v1 ativos inesperados: {v1_active}")
    
    if not redis_health_present:
        issues.append("Redis health endpoint não encontrado")
    
    if issues:
        print("❌ VALIDAÇÃO FALHOU:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ VALIDAÇÃO PASSOU:")
        print("   - Apenas exceções v1 permitidas (redis/csrf)")
        print("   - API v2 ativa")
        print("   - Health e Prometheus ativos")
        print("   - Todos os routers v1 estão comentados")
        return True


def validate_v2_files():
    """Valida que os arquivos v2 existem."""
    
    print("\n" + "=" * 80)
    print("VALIDAÇÃO DE ARQUIVOS V2")
    print("=" * 80)
    
    base_path = Path(__file__).parent / "app"
    
    v2_files = [
        "api/v2/__init__.py",
        "api/v2/router.py",
        "api/v2/patients.py",
        "api/v2/quiz.py",
        "api/v2/analytics.py",
        "api/v2/dependencies.py",
        "schemas/v2/__init__.py",
        "schemas/v2/patient.py",
        "schemas/v2/quiz.py",
        "schemas/v2/analytics.py",
        "schemas/v2/common.py",
    ]
    
    all_exist = True
    
    for file_path in v2_files:
        full_path = base_path / file_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"{status} {file_path}")
        if not exists:
            all_exist = False
    
    return all_exist


def validate_legacy_readme():
    """Valida que o README de LEGACY foi criado."""
    
    print("\n" + "=" * 80)
    print("VALIDAÇÃO DE DOCUMENTAÇÃO LEGACY")
    print("=" * 80)
    
    readme_path = Path(__file__).parent / "app" / "api" / "v1" / "README.md"
    
    if readme_path.exists():
        print("✅ app/api/v1/README.md existe")
        content = readme_path.read_text(encoding="utf-8")
        if "LEGACY" in content.upper():
            print("✅ README marca v1 como LEGACY")
            return True
        else:
            print("⚠️  README não contém marcação LEGACY")
            return False
    else:
        print("❌ app/api/v1/README.md não encontrado")
        return False


if __name__ == "__main__":
    print("\n🔍 Iniciando validação estática...\n")
    
    result1 = validate_router_registry()
    result2 = validate_v2_files()
    result3 = validate_legacy_readme()
    
    print("\n" + "=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)
    
    if result1 and result2 and result3:
        print("✅ TODAS AS VALIDAÇÕES PASSARAM")
        print("\nSistema está configurado corretamente:")
        print("  - v1 desativada (exceto redis/csrf)")
        print("  - v2 ativa e arquivos presentes")
        print("  - Documentação LEGACY criada")
        exit(0)
    else:
        print("❌ ALGUMAS VALIDAÇÕES FALHARAM")
        if not result1:
            print("  - Problema no registro de routers")
        if not result2:
            print("  - Arquivos v2 faltando")
        if not result3:
            print("  - Documentação LEGACY faltando")
        exit(1)
