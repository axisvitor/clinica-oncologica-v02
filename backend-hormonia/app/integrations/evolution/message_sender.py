"""
Message sending functionality for different message types.
"""
from typing import Dict, List, Optional, Any

import structlog

from .validators import format_phone_number, validate_message_content

logger = structlog.get_logger(__name__)


class MessageSender:
    """Handles sending different types of WhatsApp messages."""

    def __init__(self, request_handler, instance_name: str):
        """
        Initialize message sender.

        Args:
            request_handler: Request handler instance
            instance_name: WhatsApp instance name
        """
        self.request_handler = request_handler
        self.instance_name = instance_name

    async def send_text_message(
        self,
        phone_number: str,
        message: str,
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send text message via WhatsApp.

        Args:
            phone_number: Recipient phone number (with country code, e.g., 5511999999999)
            message: Text message content
            delay: Optional delay in milliseconds

        Returns:
            API response with message ID and status
        """
        # Validate message content
        validate_message_content(message)

        # Validate and format phone number
        clean_number = format_phone_number(phone_number)

        # Evolution sendText endpoint requires a top-level "text" field
        payload = {
            "number": clean_number,
            "text": message
        }

        if delay:
            payload["delay"] = delay

        logger.info(
            "Sending text message",
            phone_number=clean_number,
            message_length=len(message),
            has_delay=bool(delay)
        )

        endpoint = f"message/sendText/{self.instance_name}"
        response = await self.request_handler.make_request("POST", endpoint, payload)

        logger.info(
            "Text message sent",
            phone_number=clean_number,
            message_id=response.get('data', {}).get('id'),
            status=response.get('status')
        )

        return response

    async def send_button_message(
        self,
        phone_number: str,
        text: str,
        buttons: List[Dict[str, str]],
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send button message via WhatsApp.

        Args:
            phone_number: Recipient phone number
            text: Message text
            buttons: List of button definitions [{"displayText": "Button 1", "id": "btn1"}]
            delay: Optional delay in milliseconds

        Returns:
            API response with message ID and status
        """
        # Format phone number and validate buttons
        clean_number = format_phone_number(phone_number)

        # Evolution API v2 button format
        formatted_buttons = []
        for i, button in enumerate(buttons):
            if isinstance(button, dict):
                formatted_buttons.append({
                    "index": i + 1,
                    "urlButton": {
                        "displayText": button.get("displayText", button.get("text", f"Opção {i+1}")),
                        "url": button.get("url", f"payload:{button.get('id', f'btn_{i+1}')}")
                    }
                })
            else:
                formatted_buttons.append({
                    "index": i + 1,
                    "urlButton": {
                        "displayText": str(button),
                        "url": f"payload:btn_{i+1}"
                    }
                })

        payload = {
            "number": clean_number,
            "buttonMessage": {
                "text": text,
                "buttons": formatted_buttons
            }
        }

        if delay:
            payload["delay"] = delay

        logger.info(
            "Sending button message",
            phone_number=clean_number,
            button_count=len(formatted_buttons)
        )

        endpoint = f"message/sendButtons/{self.instance_name}"
        response = await self.request_handler.make_request("POST", endpoint, payload)

        logger.info(
            "Button message sent",
            phone_number=clean_number,
            message_id=response.get('data', {}).get('id')
        )

        return response

    async def send_list_message(
        self,
        phone_number: str,
        text: str,
        title: str,
        sections: List[Dict[str, Any]],
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send list message via WhatsApp.

        Args:
            phone_number: Recipient phone number
            text: Message text
            title: List title
            sections: List sections with rows
            delay: Optional delay in milliseconds

        Returns:
            API response with message ID and status
        """
        # Format phone number and sections
        clean_number = format_phone_number(phone_number)

        payload = {
            "number": clean_number,
            "listMessage": {
                "text": text,
                "title": title,
                "sections": sections
            }
        }

        if delay:
            payload["delay"] = delay

        endpoint = f"message/sendList/{self.instance_name}"
        return await self.request_handler.make_request("POST", endpoint, payload)

    async def send_media_message(
        self,
        phone_number: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send media message via WhatsApp.

        Args:
            phone_number: Recipient phone number
            media_url: URL of media file
            media_type: Type of media (image, video, audio, document)
            caption: Optional media caption
            delay: Optional delay in milliseconds

        Returns:
            API response with message ID and status
        """
        # Format phone number and media payload
        clean_number = format_phone_number(phone_number)

        payload = {
            "number": clean_number,
            "mediaMessage": {
                "mediatype": media_type,
                "media": media_url
            }
        }

        if caption:
            payload["mediaMessage"]["caption"] = caption

        if delay:
            payload["delay"] = delay

        endpoint = f"message/sendMedia/{self.instance_name}"
        return await self.request_handler.make_request("POST", endpoint, payload)
