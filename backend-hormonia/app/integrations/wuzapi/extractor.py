"""WuzAPI webhook payload extractor."""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WuzAPIInboundMessage:
    """Parsed inbound message from WuzAPI webhook."""

    message_id: str
    phone: str
    text: str
    is_lid: bool
    push_name: str = ""
    is_from_me: bool = False
    raw_message: dict | None = None


@dataclass
class WuzAPIReceiptEvent:
    """Parsed receipt event from WuzAPI webhook."""

    message_ids: list[str]
    receipt_type: str
    sender_phone: str


RECEIPT_TYPE_TO_STATUS: dict[str, str] = {
    "": "delivered",
    "sender": "sent",
    "read": "read",
    "read-self": "read",
    "played": "played",
    "played-self": "played",
    "retry": "delivered",
}


class WuzAPIMessageExtractor:
    """Extract structured data from WuzAPI webhook payloads."""

    @classmethod
    def extract_message(cls, payload: dict[str, Any]) -> WuzAPIInboundMessage | None:
        """Extract inbound message from wrapped or flat WuzAPI payload."""
        event = payload.get("event") or payload
        info = event.get("Info") or {}
        message_id = info.get("ID") or ""
        if not message_id:
            logger.warning("WuzAPI Message event missing Info.ID")
            return None

        sender_jid = info.get("Sender") or ""
        is_lid = sender_jid.endswith("@lid") or sender_jid.endswith("@hosted.lid")
        phone = cls._jid_to_phone(sender_jid)
        if not phone:
            logger.warning(
                "WuzAPI Message event: could not extract phone from Sender=%r",
                sender_jid,
            )
            return None

        msg = event.get("Message") or {}
        text = msg.get("Conversation") or ((msg.get("ExtendedTextMessage") or {}).get("Text")) or ""

        return WuzAPIInboundMessage(
            message_id=message_id,
            phone=phone,
            text=text,
            is_lid=is_lid,
            push_name=info.get("PushName") or "",
            is_from_me=bool(info.get("IsFromMe")),
            raw_message=msg,
        )

    @classmethod
    def extract_receipt(cls, payload: dict[str, Any]) -> WuzAPIReceiptEvent | None:
        """Extract receipt event from wrapped or flat WuzAPI payload."""
        event = payload.get("event") or payload
        info = event.get("Info") or {}
        receipt = event.get("Receipt") or {}

        sender_jid = info.get("Sender") or ""
        phone = cls._jid_to_phone(sender_jid)

        receipt_type = receipt.get("Type")
        if receipt_type is None:
            receipt_type = ""

        message_ids = receipt.get("MessageIDs") or []
        if not message_ids:
            fallback_id = info.get("ID")
            if fallback_id:
                message_ids = [fallback_id]
        message_ids = [message_id for message_id in message_ids if message_id]

        if not message_ids:
            logger.warning("WuzAPI Receipt event: no message IDs found")
            return None

        return WuzAPIReceiptEvent(
            message_ids=message_ids,
            receipt_type=receipt_type,
            sender_phone=phone,
        )

    @classmethod
    def _jid_to_phone(cls, jid: str) -> str:
        """Extract raw phone digits from a WhatsApp JID."""
        if not jid:
            return ""

        user = jid.split("@")[0] if "@" in jid else jid

        if ":" in user and "." in user:
            user = user.split(".")[0]
        elif ":" in user:
            user = user.split(":")[0]

        return re.sub(r"[^\d]", "", user)
