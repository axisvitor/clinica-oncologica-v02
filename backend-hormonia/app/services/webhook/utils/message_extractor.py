"""
Message data extraction utilities for webhook processing.
Extracted from webhook_processor.py for modularity.
"""

import logging
from typing import Any, Optional, Dict

from app.models.message import MessageType

logger = logging.getLogger(__name__)


def extract_message_data(event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract relevant message data from Evolution API webhook.

    Args:
        event_data: Raw webhook event data

    Returns:
        Extracted message data or None if invalid
    """
    try:
        data = event_data.get("data", {})

        # Check for required fields
        if not data.get("message") or not data.get("key"):
            return None

        message = data["message"]
        key = data["key"]

        # Extract phone number from remoteJid
        remote_jid = key.get("remoteJid", "")
        phone = _clean_phone_from_jid(remote_jid)

        if not phone:
            return None

        # Extract message content and type
        content, message_type = _extract_content_and_type(message)

        if not content:
            return None

        return {
            "phone": phone,
            "content": content,
            "type": message_type,
            "whatsapp_id": key.get("id"),
            "metadata": {
                "from_me": key.get("fromMe", False),
                "timestamp": message.get("messageTimestamp"),
                "pushName": data.get("pushName"),
            },
        }

    except Exception as e:
        logger.error(f"Error extracting message data: {e}")
        return None


def _clean_phone_from_jid(remote_jid: str) -> str:
    """
    Extract and clean phone number from WhatsApp JID.

    Args:
        remote_jid: WhatsApp remote JID (e.g., "5511987654321@s.whatsapp.net")

    Returns:
        Cleaned phone number
    """
    if "@" in remote_jid:
        phone = remote_jid.split("@")[0]
    else:
        phone = remote_jid

    # Remove non-digit characters except +
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    # Remove leading zeros (but preserve +)
    if cleaned.startswith("+"):
        cleaned = "+" + cleaned[1:].lstrip("0")
    else:
        cleaned = cleaned.lstrip("0")

    return cleaned


def _extract_content_and_type(
    message: Dict[str, Any],
) -> tuple[Optional[str], MessageType]:
    """
    Extract message content and determine message type.

    Args:
        message: Message data from webhook

    Returns:
        Tuple of (content, message_type)
    """
    content = None
    message_type = MessageType.TEXT

    if "extendedTextMessage" in message:
        content = message["extendedTextMessage"].get("text")
    elif "conversation" in message:
        content = message["conversation"]
    elif "imageMessage" in message:
        content = message["imageMessage"].get("caption", "[Image]")
        message_type = MessageType.IMAGE
    elif "audioMessage" in message:
        content = "[Audio message]"
        message_type = MessageType.AUDIO
    elif "videoMessage" in message:
        content = message["videoMessage"].get("caption", "[Video]")
        message_type = MessageType.VIDEO
    elif "documentMessage" in message:
        content = message["documentMessage"].get("fileName", "[Document]")
        message_type = MessageType.DOCUMENT
    elif "stickerMessage" in message:
        content = "[Sticker]"
        message_type = MessageType.STICKER
    elif "locationMessage" in message:
        content = "[Location]"
        message_type = MessageType.LOCATION
    elif "contactMessage" in message:
        content = "[Contact]"
        message_type = MessageType.CONTACT

    return content, message_type
