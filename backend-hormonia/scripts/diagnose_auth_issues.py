#!/usr/bin/env python3
"""
Script para diagnosticar problemas de autenticação
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importações diretas para evitar circular imports
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from app.config import settings


async def diagnose_auth_issues():
    """Diagnostica problemas de autenticação"""
    
    print("🔍 DIAGNÓSTICO DE AUTENTICAÇÃO")
    print("=" * 50)
    
    # 1. Verificar configuração Firebase
    print("\n1. 📋 Verificando configuração Firebase...")
    
    firebase_project_id = getattr(settings, 'FIREBASE_ADMIN_PROJECT_ID', None)
    firebase_private_key = getattr(settings, 'FIREBASE_ADMIN_PRIVATE_KEY', None)
    firebase_client_email = getattr(settings, 'FIREBASE_ADMIN_CLIENT_EMAIL', None)
    
    if not firebase_project_id:
        print("   ❌ FIREBASE_ADMIN_PROJECT_ID não configurado")
    else:
        print(f"   ✅ Project ID: {firebase_project_id}")
    
    if not firebase_private_key:
        print("   ❌ FIREBASE_ADMIN_PRIVATE_KEY não configurado")
    else:
        print("   ✅ Private Key configurado")
    
    if not firebase_client_email:
        print("   ❌ FIREBASE_ADMIN_CLIENT_EMAIL não configurado")
    else:
        print(f"   ✅ Client Email: {firebase_client_email}")
    
    # 2. Verificar usuários no banco
    print("\n2. 👥 Verificando usuários no banco...")
    
    try:
        # Conectar diretamente ao banco
        database_url = getattr(settings, 'DATABASE_URL', None)
        if not database_url:
            print("   ❌ DATABASE_URL não configurado")
            return
        
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Contar usuários
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            total_users = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
            active_users = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin'"))
            admin_users = result.scalar()
            
            print(f"   📊 Total de usuários: {total_users}")
            print(f"   ✅ Usuários ativos: {active_users}")
            print(f"   👑 Administradores: {admin_users}")
            
            # Listar alguns usuários
            result = conn.execute(text("SELECT email, role, is_active FROM users LIMIT 5"))
            users = result.fetchall()
            
            print("\n   📋 Primeiros 5 usuários:")
            for user in users:
                status = "✅ Ativo" if user.is_active else "❌ Inativo"
                print(f"      - {user.email} ({user.role}) {status}")
        
    except Exception as e:
        print(f"   ❌ Erro ao acessar banco: {e}")
    
    # 3. Verificar Redis
    print("\n3. 🔗 Verificando Redis...")
    
    try:
        import redis
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        
        # Testar conexão
        r.ping()
        print("   ✅ Redis conectado")
        
        # Verificar chaves de rate limit
        keys = r.keys("rate_limit:*")
        print(f"   📊 Chaves de rate limit ativas: {len(keys)}")
        
        if keys:
            print("   📋 Algumas chaves ativas:")
            for key in keys[:5]:
                value = r.get(key)
                ttl = r.ttl(key)
                print(f"      - {key.decode()}: {value} (TTL: {ttl}s)")
                
    except Exception as e:
        print(f"   ❌ Erro ao conectar Redis: {e}")
    
    # 4. Verificar rate limiting
    print("\n4. 🚦 Verificando configuração de rate limiting...")
    
    try:
        from app.middleware.distributed_rate_limiter import DistributedRateLimiter
        from app.core.redis_manager import get_sync_redis
        
        redis_client = get_sync_redis()
        if redis_client:
            print("   ✅ Redis conectado")
            
            # Verificar chaves de rate limit
            keys = redis_client.keys("rate_limit:*")
            print(f"   📊 Chaves de rate limit ativas: {len(keys)}")
            
            if keys:
                print("   📋 Algumas chaves ativas:")
                for key in keys[:5]:
                    value = redis_client.get(key)
                    ttl = redis_client.ttl(key)
                    print(f"      - {key.decode()}: {value} (TTL: {ttl}s)")
        else:
            print("   ❌ Redis não conectado")
            
    except Exception as e:
        print(f"   ❌ Erro ao verificar rate limiting: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Diagnóstico concluído!")


if __name__ == "__main__":
    asyncio.run(diagnose_auth_issues())