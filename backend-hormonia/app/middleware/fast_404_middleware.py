"""Fast 404 middleware for patient resources."""
import logging
import re
import time
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class Fast404Middleware:
    """Middleware para retornar 404s ultra-rapidos em endpoints especificos."""

    def __init__(self, app):
        self.app = app
        from app.core.redis_manager import get_redis_manager

        self.redis_manager = get_redis_manager()
        self.redis_client = self.redis_manager.get_compatible_client("sync")

        # Padroes de URL que exigem verificacao imediata
        self.fast_404_patterns = []

    async def __call__(self, request: Request, call_next: Callable):
        start_time = time.time()

        path = request.url.path
        patient_id = None

        for pattern in self.fast_404_patterns:
            match = re.match(pattern, path)
            if match:
                patient_id = match.group(1)
                break

        if patient_id:
            if not self._check_patient_exists_fast(patient_id):
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"Fast 404 middleware: {path} ({elapsed:.1f}ms)")

                return JSONResponse(
                    status_code=404,
                    content={"detail": "Patient not found"},
                )

        response = await call_next(request)
        return response

    def _check_patient_exists_fast(self, patient_id: str) -> bool:
        """Verificacao rapida com cache negativo."""
        cache_key = f"patient_not_found:{patient_id}"

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
            self.redis_client.setex(cache_key, 60, "1")

        return exists
