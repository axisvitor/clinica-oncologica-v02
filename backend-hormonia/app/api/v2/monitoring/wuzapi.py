"""WuzAPI session monitoring endpoints (Phase 35: SESS-02, SESS-03)."""

import logging
from typing import Any

from fastapi import APIRouter

from app.config import settings
from app.integrations.wuzapi import get_wuzapi_client, normalize_session_status
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/session/status")
async def get_wuzapi_session_status() -> dict[str, Any]:
    """SESS-02: Expose WuzAPI session connection state for operators."""
    token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
    base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
    use_mock = getattr(settings, "WHATSAPP_WUZAPI_USE_MOCK", False)

    if not token and not use_mock:
        return {
            "connected": False,
            "logged_in": False,
            "error": "WHATSAPP_WUZAPI_TOKEN not configured",
        }

    try:
        client = get_wuzapi_client(base_url=base_url, token=token or "")
        await client.connect()
        try:
            result = await client.get_session_status()
            normalized = normalize_session_status(result)
            response: dict[str, Any] = {
                "connected": normalized["connected"],
                "logged_in": normalized["logged_in"],
                "timestamp": now_sao_paulo().isoformat(),
            }
            if use_mock:
                response["mock"] = True
            return response
        finally:
            await client.disconnect()
    except Exception as exc:
        logger.warning("WuzAPI session status check failed: %s", exc)
        return {
            "connected": False,
            "logged_in": False,
            "error": str(exc),
        }


@router.get("/session/qr")
async def get_wuzapi_qr() -> dict[str, Any]:
    """SESS-03: Return base64 QR code for WhatsApp pairing."""
    token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
    base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
    use_mock = getattr(settings, "WHATSAPP_WUZAPI_USE_MOCK", False)

    if not token and not use_mock:
        return {"qr": None, "error": "WHATSAPP_WUZAPI_TOKEN not configured"}

    try:
        client = get_wuzapi_client(base_url=base_url, token=token or "")
        await client.connect()
        try:
            result = await client.get_qr()
            response: dict[str, Any] = {
                "qr": result.get("data"),
                "timestamp": now_sao_paulo().isoformat(),
            }
            if use_mock:
                response["mock"] = True
            return response
        finally:
            await client.disconnect()
    except Exception as exc:
        logger.warning("WuzAPI QR code fetch failed: %s", exc)
        return {"qr": None, "error": str(exc)}
