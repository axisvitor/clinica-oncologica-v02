#!/usr/bin/env python3
"""
Testar autenticação admin e endpoint /auth/me
"""
import sys
sys.path.append('.')

import asyncio
from app.dependencies.auth_dependencies import get_permissions_for_role
from app.database import get_scoped_session
from sqlalchemy import text

async def test_auth_me_response():
    """Simular resposta do endpoint /auth/me para admin"""
    
    print("🧪 Testando resposta do endpoint /auth/me...")
    
    # Simular dados do usuário admin
    admin_email = "admin@neoplasiaslitoral.com"
    
    with get_scoped_session() as db:
        # Buscar dados do usuário
        result = db.execute(text("""
            SELECT id, email, full_name, role, is_active, firebase_uid
            FROM users 
            WHERE email = :email
        """), {"email": admin_email})
        
        user = result.fetchone()
        
        if not user:
            print(f"❌ Usuário {admin_email} não encontrado!")
            return
        
        # Gerar permissões
        permissions = get_permissions_for_role(user.role)
        
        # Simular resposta do /auth/me
        auth_me_response = {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "firebase_uid": user.firebase_uid
            },
            "permissions": permissions,
            "session": {
                "authenticated": True,
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }
        
        print(f"✅ Resposta simulada do GET /api/v1/auth/me:")
        print(f"")
        print(f"📊 User Info:")
        print(f"   Email: {auth_me_response['user']['email']}")
        print(f"   Role: {auth_me_response['user']['role']}")
        print(f"   Active: {auth_me_response['user']['is_active']}")
        
        print(f"")
        print(f"🔐 Permissions ({len(permissions)}):")
        
        # Verificar permissões críticas para o frontend
        critical_permissions = [
            'admin.read',
            'admin.templates.read',
            'users.read', 
            'security.read',
            'reports.read',
            'settings.read'
        ]
        
        for perm in critical_permissions:
            status = "✅" if perm in permissions else "❌"
            print(f"   {status} {perm}")
        
        print(f"")
        print(f"📋 Todas as permissões:")
        for perm in sorted(permissions):
            print(f"   - {perm}")
        
        # Verificar se todas as permissões críticas estão presentes
        missing_permissions = [p for p in critical_permissions if p not in permissions]
        
        if missing_permissions:
            print(f"")
            print(f"❌ PERMISSÕES FALTANDO:")
            for perm in missing_permissions:
                print(f"   - {perm}")
            return False
        else:
            print(f"")
            print(f"✅ TODAS AS PERMISSÕES CRÍTICAS PRESENTES!")
            return True

def verify_database_state():
    """Verificar estado atual do banco"""
    
    print(f"\n🔍 Verificando estado do banco de dados...")
    
    with get_scoped_session() as db:
        # Verificar usuário admin
        result = db.execute(text("""
            SELECT email, role, is_active 
            FROM users 
            WHERE email = 'admin@neoplasiaslitoral.com'
        """))
        
        admin_user = result.fetchone()
        
        if admin_user:
            print(f"✅ Usuário admin encontrado:")
            print(f"   Email: {admin_user.email}")
            print(f"   Role: {admin_user.role}")
            print(f"   Active: {admin_user.is_active}")
            
            if admin_user.role == 'admin' and admin_user.is_active:
                print(f"✅ Configuração do usuário admin está correta!")
                return True
            else:
                print(f"❌ Usuário admin precisa de correção!")
                return False
        else:
            print(f"❌ Usuário admin não encontrado!")
            return False

async def main():
    """Executar todos os testes"""
    
    print("🚀 TESTANDO AUTENTICAÇÃO ADMIN")
    print("=" * 50)
    
    # 1. Verificar banco
    db_ok = verify_database_state()
    
    if not db_ok:
        print(f"\n❌ Problemas no banco de dados!")
        return
    
    # 2. Testar resposta do /auth/me
    auth_ok = await test_auth_me_response()
    
    print(f"\n" + "=" * 50)
    
    if auth_ok:
        print(f"🎉 TESTES PASSARAM!")
        print(f"\n📋 O que fazer agora:")
        print(f"1. Faça login com admin@neoplasiaslitoral.com")
        print(f"2. Chame GET /api/v1/auth/me")
        print(f"3. Verifique se role = 'admin'")
        print(f"4. Confirme se permissions contém admin.read, users.read, etc.")
        print(f"5. O menu admin deve aparecer no frontend!")
    else:
        print(f"❌ TESTES FALHARAM!")
        print(f"Verifique as permissões e configurações.")

if __name__ == "__main__":
    asyncio.run(main())