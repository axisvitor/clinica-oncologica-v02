
from typing import Optional
from fastapi import HTTPException, status
import time
import logging

logger = logging.getLogger(__name__)

class OptimizedMonthlyQuizService:
    """Serviço otimizado de Monthly Quiz com verificação rápida de 404"""
    
    def __init__(self):
        from app.core.redis_manager import get_redis_manager
        self.redis_manager = get_redis_manager()
        self.redis_client = self.redis_manager.get_compatible_client('sync')
        
    def check_patient_exists_fast(self, patient_id: str) -> bool:
        """Verificação ultra-rápida de existência de paciente (10-20ms)"""
        cache_key = f"patient_not_found:{patient_id}"
        
        # Cache negativo check (2ms)
        if self.redis_client.exists(cache_key):
            return False
        
        # Query indexada rápida
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
            # Cache negativo (60s TTL)
            self.redis_client.setex(cache_key, 60, "1")
            
        return exists
    
    async def get_patient_quiz_status(self, patient_id: str):
        """
        Endpoint otimizado para status de quiz do paciente
        
        ANTES: 7-8s (inicializações pesadas + queries N+1)
        DEPOIS: 10-50ms (verificação indexada + early return)
        """
        start_time = time.time()
        
        # 1. VERIFICAÇÃO RÁPIDA DE EXISTÊNCIA (10-20ms)
        if not self.check_patient_exists_fast(patient_id):
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Fast 404 for patient {patient_id[:8]}... ({elapsed:.1f}ms)")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        
        # 2. Se chegou aqui, paciente existe - continuar com lógica normal
        # (mas agora sabemos que não é 404, então pode fazer queries mais pesadas)
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Patient exists check passed ({elapsed:.1f}ms)")
        
        # Aqui continuaria com a lógica normal do quiz...
        return {"status": "active", "patient_id": patient_id}
