import asyncio
import logging
import signal
from contextlib import suppress

from app.database import get_async_session_factory
from app.services.unified_whatsapp_service import create_unified_whatsapp_service

logger = logging.getLogger(__name__)
_shutdown_event = asyncio.Event()


def _handle_shutdown(*_args) -> None:
    logger.info("Shutdown signal received; stopping queue worker.")
    _shutdown_event.set()


def _on_worker_done(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:  # pragma: no cover - defensive logging in worker process
        logger.exception("Queue worker exited unexpectedly.")
    _shutdown_event.set()


async def run_worker() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _handle_shutdown())

    async_session_factory = get_async_session_factory()
    async with async_session_factory() as db:
        service = create_unified_whatsapp_service(db)
        queue_service = await service._get_queue_service()
        queue_task = asyncio.create_task(queue_service.process_message_queue())
        queue_task.add_done_callback(_on_worker_done)

        await _shutdown_event.wait()

        queue_task.cancel()
        with suppress(asyncio.CancelledError):
            await queue_task

        await service.shutdown()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
