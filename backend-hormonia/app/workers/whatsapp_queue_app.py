import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.database import get_async_session_factory
from app.services.unified_whatsapp_service import create_unified_whatsapp_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async_session_factory = get_async_session_factory()
    async with async_session_factory() as db:
        service = create_unified_whatsapp_service(db)
        queue_service = await service._get_queue_service()
        queue_task = asyncio.create_task(queue_service.process_message_queue())

        logger.info("WhatsApp queue worker started.")
        try:
            yield
        finally:
            queue_task.cancel()
            with suppress(asyncio.CancelledError):
                await queue_task
            await service.shutdown()
            logger.info("WhatsApp queue worker stopped.")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
