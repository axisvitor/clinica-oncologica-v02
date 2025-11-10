
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import time
import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)

class Fast404Middleware:
    """Middleware para retornar 404s ultra-rápidos em endpoints específicos"""
    
    def __init__(self, app):
        self.app = app
        from app.core.redis_manager import get_redis_manager
        self.redis_manager = get_redis_manager()
        self.redis_client = self.redis_manager.get_compatible_client('sync')
        
        # Padrões de URL que devem ter verificação rápida
        self.fast_404_patterns = []
    
    async def __call__(self, request: Request, call_next: Callable):
        start_time = time.time()
        
        # Verificar se é um endpoint que precisa de verificação rápida
        path = request.url.path
        patient_id = None
        
        for pattern in self.fast_404_patterns:
            match = re.match(pattern, path)
            if match:
                patient_id = match.group(1)
                break
        
        if patient_id:
            # Fazer verificação rápida de existência
            if not self._check_patient_exists_fast(patient_id):
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"Fast 404 middleware: {path} ({elapsed:.1f}ms)")
                
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Patient not found"}
                )
        
        # Continuar com processamento normal
        response = await call_next(request)
        return response
    
    def _check_patient_exists_fast(self, patient_id: str) -> bool:
        """Verificação rápida com cache negativo"""
        cache_key = f"patient_not_found:{patient_id}"
        
        # Cache negativo
        if self.redis_client.exists(cache_key):
            return False
        
        # Query indexada
        from app.database import get_scoped_session
        from sqlalchemy import text
        
        with get_scoped_session() as db:
            result = db.execute(text("""
                SELECT 1 FROM patients 
                WHERE id = :patient_id 
                LIMIT 1
            """), {"patient_id": patient_id})
            
            exists = result.fetchone() is not None
        
        if not exists:
            self.redis_client.setex(cache_key, 60, "1")
            
        return exists
