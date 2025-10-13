#!/usr/bin/env python3
"""
Corrigir usuário admin no banco de dados
"""
import sys
sys.path.append('.')

from app.database import get_scoped_session
from sqlalchemy import text

def fix_admin_user():
    """Verificar e corrigir usuário admin"""
    
    admin_email = "admin@neoplasiaslitoral.com"
    
    print(f"🔍 Verificando usuário admin: {admin_email}")
    
    with get_scoped_session() as db:
        # 1. Verificar se usuário existe
        result = db.execute(text("""
            SELECT email, role, is_active, firebase_uid 
            FROM users 
            WHERE email = :email
        """), {"email": admin_email})
        
        user = result.fetchone()
        
        if user:
            print(f"✅ Usuário encontrado:")
            print(f"   Email: {user.email}")
            print(f"   Role: {user.role}")
            print(f"   Active: {user.is_active}")
            print(f"   Firebase UID: {user.firebase_uid}")
            
            # 2. Corrigir se necessário
            needs_update = False
            updates = []
            
            if user.role != 'admin':
                updates.append("role = 'admin'")
                needs_update = True
                print(f"   ⚠️  Role precisa ser corrigido: {user.role} → admin")
            
            if not user.is_active:
                updates.append("is_active = true")
                needs_update = True
                print(f"   ⚠️  Usuário precisa ser ativado")
            
            if needs_update:
                update_sql = f"""
                    UPDATE users 
                    SET {', '.join(updates)}
                    WHERE email = :email
                """
                
                db.execute(text(update_sql), {"email": admin_email})
                db.commit()
                
                print(f"✅ Usuário admin corrigido!")
            else:
                print(f"✅ Usuário admin já está correto!")
                
        else:
            print(f"❌ Usuário admin não encontrado!")
            print(f"   Você precisa criar o usuário {admin_email} primeiro")
            
            # Listar usuários existentes
            result = db.execute(text("SELECT email, role FROM users LIMIT 5"))
            users = result.fetchall()
            
            if users:
                print(f"\n📋 Usuários existentes:")
                for u in users:
                    print(f"   - {u.email} ({u.role})")
            else:
                print(f"\n📋 Nenhum usuário encontrado no banco")

def test_permissions():
    """Testar as novas permissões"""
    
    print(f"\n🧪 Testando permissões corrigidas...")
    
    from app.dependencies.auth_dependencies import get_permissions_for_role
    
    admin_permissions = get_permissions_for_role("ADMIN")
    
    print(f"📊 Permissões ADMIN ({len(admin_permissions)}):")
    
    # Verificar permissões específicas que o frontend precisa
    required_permissions = [
        'admin.read',
        'admin.templates.read', 
        'users.read',
        'security.read',
        'reports.read',
        'settings.read'
    ]
    
    for perm in required_permissions:
        if perm in admin_permissions:
            print(f"   ✅ {perm}")
        else:
            print(f"   ❌ {perm} - FALTANDO!")
    
    print(f"\n📋 Todas as permissões:")
    for perm in sorted(admin_permissions):
        print(f"   - {perm}")

def main():
    """Executar correções do usuário admin"""
    
    print("🔧 CORRIGINDO USUÁRIO ADMIN")
    print("=" * 40)
    
    # 1. Corrigir usuário no banco
    fix_admin_user()
    
    # 2. Testar permissões
    test_permissions()
    
    print("\n" + "=" * 40)
    print("🎉 CORREÇÃO CONCLUÍDA!")
    
    print(f"\n📋 Próximos passos:")
    print(f"1. Teste GET /api/v1/auth/me com admin@neoplasiaslitoral.com")
    print(f"2. Verifique se role = 'admin'")
    print(f"3. Confirme se permissions contém admin.read, users.read, etc.")
    print(f"4. Teste o menu admin no frontend")

if __name__ == "__main__":
    main()