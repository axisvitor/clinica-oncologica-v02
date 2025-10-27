"""
Debug endpoints para problemas de autenticação
APENAS PARA DESENVOLVIMENTO - REMOVER EM PRODUÇÃO
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.database import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.firebase_auth_service import get_firebase_auth_service
from app.config import settings
from app.utils.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug-auth", tags=["debug-auth"])


@router.get("/user-info/{email}")
@limiter.limit("10/minute")
async def debug_user_info(
    request: Request,
    email: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Debug: Verificar informações de usuário por email
    APENAS DESENVOLVIMENTO
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email.strip().lower())
        
        if not user:
            return {
                "found": False,
                "email": email,
                "message": "Usuário não encontrado no banco"
            }
        
        return {
            "found": True,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "firebase_uid": getattr(user, 'firebase_uid', None)
            }
        }
        
    except Exception as e:
        logger.error(f"Error in debug_user_info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-token")
@limiter.limit("5/minute")
async def debug_verify_token(
    request: Request,
    token_data: Dict[str, str],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Debug: Verificar token Firebase
    APENAS DESENVOLVIMENTO
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    token = token_data.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    
    try:
        # Verificar configuração Firebase
        firebase_project_id = getattr(settings, 'FIREBASE_ADMIN_PROJECT_ID', None)
        firebase_private_key = getattr(settings, 'FIREBASE_ADMIN_PRIVATE_KEY', None)
        firebase_client_email = getattr(settings, 'FIREBASE_ADMIN_CLIENT_EMAIL', None)
        
        if not all([firebase_project_id, firebase_private_key, firebase_client_email]):
            return {
                "valid": False,
                "error": "Firebase configuration incomplete",
                "config": {
                    "project_id": bool(firebase_project_id),
                    "private_key": bool(firebase_private_key),
                    "client_email": bool(firebase_client_email)
                }
            }
        
        # Verificar token
        firebase_service = get_firebase_auth_service(
            project_id=firebase_project_id,
            private_key=firebase_private_key,
            client_email=firebase_client_email
        )
        
        user_data = await firebase_service.verify_token(token)
        
        # Verificar usuário no banco
        email = user_data.get('email', '').strip().lower()
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email) if email else None
        
        return {
            "valid": True,
            "firebase_data": {
                "email": user_data.get('email'),
                "uid": user_data.get('uid'),
                "name": user_data.get('name'),
                "role": user_data.get('role'),
                "email_verified": user_data.get('email_verified')
            },
            "database_user": {
                "found": bool(user),
                "active": user.is_active if user else False,
                "role": user.role if user else None,
                "id": str(user.id) if user else None
            } if user else {"found": False}
        }
        
    except Exception as e:
        logger.error(f"Error in debug_verify_token: {e}")
        return {
            "valid": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/rate-limit-status/{ip}")
@limiter.limit("10/minute")
async def debug_rate_limit_status(
    request: Request,
    ip: str
) -> Dict[str, Any]:
    """
    Debug: Verificar status de rate limiting para IP
    APENAS DESENVOLVIMENTO
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        from app.core.redis_manager import get_sync_redis
        
        redis_client = get_sync_redis()
        if not redis_client:
            return {"error": "Redis not connected"}
        
        # Buscar chaves relacionadas ao IP
        pattern = f"rate_limit:*{ip}*"
        keys = redis_client.keys(pattern)
        
        rate_limit_data = {}
        for key in keys:
            value = redis_client.get(key)
            ttl = redis_client.ttl(key)
            rate_limit_data[key.decode()] = {
                "value": int(value) if value else 0,
                "ttl": ttl
            }
        
        return {
            "ip": ip,
            "active_limits": rate_limit_data,
            "total_keys": len(keys)
        }
        
    except Exception as e:
        logger.error(f"Error in debug_rate_limit_status: {e}")
        return {"error": str(e)}


@router.get("/config")
@limiter.limit("5/minute")
async def debug_config(request: Request) -> Dict[str, Any]:
    """
    Debug: Verificar configurações de autenticação
    APENAS DESENVOLVIMENTO
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "firebase": {
            "project_id_set": bool(getattr(settings, 'FIREBASE_ADMIN_PROJECT_ID', None)),
            "private_key_set": bool(getattr(settings, 'FIREBASE_ADMIN_PRIVATE_KEY', None)),
            "client_email_set": bool(getattr(settings, 'FIREBASE_ADMIN_CLIENT_EMAIL', None))
        },
        "debug_mode": settings.DEBUG,
        "environment": getattr(settings, 'ENVIRONMENT', 'unknown')
    }