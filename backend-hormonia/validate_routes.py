"""
Script de validação rápida das rotas montadas no app.
Verifica que apenas as exceções v1 permitidas estão presentes.
"""
from app.main import app
from fastapi.routing import APIRoute

def validate_routes():
    """Lista todas as rotas e valida que v1 está desativada (exceto exceções)."""
    
    print("=" * 80)
    print("VALIDAÇÃO DE ROTAS - Sistema Hormonia")
    print("=" * 80)
    
    # Coletar todas as rotas
    all_routes = []
    v1_routes = []
    v2_routes = []
    health_routes = []
    other_routes = []
    
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            methods = ", ".join(route.methods)
            all_routes.append((path, methods))
            
            if path.startswith("/api/v1/"):
                v1_routes.append((path, methods))
            elif path.startswith("/api/v2/"):
                v2_routes.append((path, methods))
            elif path.startswith("/health"):
                health_routes.append((path, methods))
            else:
                other_routes.append((path, methods))
    
    # Validar v1
    print("\n📋 ROTAS V1 (devem ser apenas exceções permitidas)")
    print("-" * 80)
    allowed_v1 = {"/api/v1/redis/health", "/api/v1/csrf-token"}
    
    if not v1_routes:
        print("✅ Nenhuma rota v1 encontrada (exceto as definidas inline)")
    else:
        for path, methods in sorted(v1_routes):
            if path in allowed_v1:
                print(f"✅ {methods:20} {path} (exceção permitida)")
            else:
                print(f"❌ {methods:20} {path} (NÃO DEVERIA ESTAR MONTADA!)")
    
    unexpected_v1 = {path for path, _ in v1_routes} - allowed_v1
    
    # Validar v2
    print("\n📋 ROTAS V2 (devem estar todas ativas)")
    print("-" * 80)
    if v2_routes:
        for path, methods in sorted(v2_routes):
            print(f"✅ {methods:20} {path}")
    else:
        print("❌ Nenhuma rota v2 encontrada! (PROBLEMA)")
    
    # Health routes
    print("\n📋 ROTAS HEALTH (centralizadas)")
    print("-" * 80)
    if health_routes:
        for path, methods in sorted(health_routes):
            print(f"✅ {methods:20} {path}")
    else:
        print("⚠️  Nenhuma rota /health encontrada")
    
    # Outras rotas
    print("\n📋 OUTRAS ROTAS")
    print("-" * 80)
    for path, methods in sorted(other_routes):
        if path in ["/metrics", "/docs", "/redoc", "/openapi.json", "/test"]:
            print(f"ℹ️  {methods:20} {path}")
        else:
            print(f"   {methods:20} {path}")
    
    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO DA VALIDAÇÃO")
    print("=" * 80)
    print(f"Total de rotas: {len(all_routes)}")
    print(f"Rotas v1: {len(v1_routes)} (esperado: 0-2 exceções)")
    print(f"Rotas v2: {len(v2_routes)} (esperado: 15+)")
    print(f"Rotas health: {len(health_routes)} (esperado: 5+)")
    print(f"Outras rotas: {len(other_routes)}")
    
    # Resultado final
    print("\n" + "=" * 80)
    if unexpected_v1:
        print(f"❌ FALHOU: Rotas v1 inesperadas encontradas: {sorted(unexpected_v1)}")
        return False
    elif not v2_routes:
        print("❌ FALHOU: Nenhuma rota v2 encontrada!")
        return False
    else:
        print("✅ VALIDAÇÃO PASSOU: Apenas exceções v1 permitidas, v2 ativa")
        return True

if __name__ == "__main__":
    success = validate_routes()
    exit(0 if success else 1)
