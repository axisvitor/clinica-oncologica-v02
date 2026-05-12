import os

try:
    from app.integrations.wuzapi.client import WuzAPIClient, normalize_session_status
except ModuleNotFoundError:  # pragma: no cover - interim during incremental setup
    WuzAPIClient = None
    normalize_session_status = None
from app.integrations.wuzapi.errors import MediaTooLargeError, UnsafeMediaUrlError, WuzAPIError
from app.integrations.wuzapi.extractor import (
    RECEIPT_TYPE_TO_STATUS,
    WuzAPIInboundMessage,
    WuzAPIMessageExtractor,
    WuzAPIReceiptEvent,
)
from app.integrations.wuzapi.media import fetch_and_encode_media
from app.integrations.wuzapi.mock import MockWuzAPIClient
from app.integrations.wuzapi.models import WuzAPISendResponse


def get_wuzapi_client(base_url: str = "", token: str = "", **kwargs):
    use_mock = os.environ.get("WHATSAPP_WUZAPI_USE_MOCK", "").lower() == "true"
    if use_mock:
        return MockWuzAPIClient(**kwargs)

    if WuzAPIClient is None:
        raise RuntimeError("WuzAPIClient is unavailable in this environment")

    return WuzAPIClient(base_url=base_url, token=token, **kwargs)


__all__ = [
    "WuzAPIClient",
    "MockWuzAPIClient",
    "get_wuzapi_client",
    "normalize_session_status",
    "WuzAPIError",
    "MediaTooLargeError",
    "UnsafeMediaUrlError",
    "WuzAPISendResponse",
    "fetch_and_encode_media",
    "WuzAPIMessageExtractor",
    "WuzAPIInboundMessage",
    "WuzAPIReceiptEvent",
    "RECEIPT_TYPE_TO_STATUS",
]
