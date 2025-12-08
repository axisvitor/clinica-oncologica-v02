"""Optimized Monthly Quiz service with fast 404 checks."""
from typing import Any
import logging
import time

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class OptimizedMonthlyQuizService:
    """Servico otimizado do Monthly Quiz com verificacao rapida de 404."""

    def __init__(self):
        from app.core.redis_manager import get_redis_manager

        self.redis_manager = get_redis_manager()
        self.redis_client = self.redis_manager.get_compatible_client("sync")

    def check_patient_exists_fast(self, patient_id: str) -> bool:
        """Verificacao ultra-rapida de existencia de paciente (10-20ms)."""
        cache_key = f"patient_not_found:{patient_id}"

        # Cache negativo (aprox. 2ms)
        if self.redis_client.exists(cache_key):
            return False

        from sqlalchemy import text

        from app.database import get_scoped_session

        with get_scoped_session() as db:
            result = db.execute(
                text(
                    """
                    SELECT 1 FROM patients 
                    WHERE id = :patient_id 
                    LIMIT 1
                    """
                ),
                {"patient_id": patient_id},
            )

            exists = result.fetchone() is not None

        if not exists:
            # Cache negativo com TTL de 60 segundos
            self.redis_client.setex(cache_key, 60, "1")

        return exists

    async def get_patient_quiz_status(self, patient_id: str):
        """Retorna status do quiz do paciente com verificacao otimizada."""
        start_time = time.time()

        # 1) Verificacao rapida de existencia
        if not self.check_patient_exists_fast(patient_id):
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Fast 404 for patient {patient_id[:8]}... ({elapsed:.1f}ms)")

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # 2) Se chegou aqui, o paciente existe — continue com a logica normal
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Patient exists check passed ({elapsed:.1f}ms)")

        # TODO: adicionar logica completa do quiz
        return {"status": "active", "patient_id": patient_id}
