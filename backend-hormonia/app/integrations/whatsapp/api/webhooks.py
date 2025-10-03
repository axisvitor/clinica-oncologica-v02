"""
WhatsApp webhook handlers for Evolution API integration.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.message import (
    WebhookPayload, MessageStatus, WhatsAppMessage, WhatsAppContact,
    WhatsAppInstance
)
from ..services.message_service import WhatsAppMessageService
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhooks"])


@router.post("/evolution/{instance_name}")
async def evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Evolution API webhooks for WhatsApp events.
    """
    try:
        # Get raw payload
        payload = await request.json()

        # Log incoming webhook
        logger.info(f"Received webhook for instance {instance_name}: {payload.get('event', 'unknown')}")

        # Validate webhook payload
        webhook_data = WebhookPayload(
            instance=instance_name,
            data=payload.get('data', {}),
            event=payload.get('event', 'unknown')
        )

        # Process webhook in background
        background_tasks.add_task(
            process_webhook_event,
            webhook_data,
            db
        )

        return {"status": "received", "timestamp": datetime.utcnow()}

    except Exception as e:
        logger.error(f"Error processing webhook for instance {instance_name}: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook processing error: {str(e)}")


async def process_webhook_event(webhook_data: WebhookPayload, db: AsyncSession):
    """Process webhook event in background."""
    try:
        event = webhook_data.event
        data = webhook_data.data
        instance_name = webhook_data.instance

        # Route to appropriate handler based on event type
        if event == "messages.upsert":
            await handle_message_upsert(instance_name, data, db)
        elif event == "messages.update":
            await handle_message_update(instance_name, data, db)
        elif event == "send.message":
            await handle_send_message(instance_name, data, db)
        elif event == "contacts.upsert":
            await handle_contact_upsert(instance_name, data, db)
        elif event == "connection.update":
            await handle_connection_update(instance_name, data, db)
        elif event == "presence.update":
            await handle_presence_update(instance_name, data, db)
        elif event == "chats.upsert":
            await handle_chat_upsert(instance_name, data, db)
        else:
            logger.info(f"Unhandled webhook event: {event}")

    except Exception as e:
        logger.error(f"Error in webhook event processing: {e}")


async def handle_message_upsert(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle incoming messages."""
    try:
        messages = data if isinstance(data, list) else [data]

        for message_data in messages:
            message_info = message_data.get('message', {})
            key = message_data.get('key', {})

            # Skip status messages
            if message_info.get('messageStubType'):
                continue

            # Extract message details
            message_id = key.get('id', '')
            chat_id = key.get('remoteJid', '')
            sender_id = key.get('participant') or key.get('remoteJid', '')

            # Determine message type and content
            message_type = "text"
            content = ""
            media_url = None
            media_caption = None

            if 'conversation' in message_info:
                content = message_info['conversation']
            elif 'extendedTextMessage' in message_info:
                content = message_info['extendedTextMessage'].get('text', '')
            elif 'imageMessage' in message_info:
                message_type = "image"
                media_caption = message_info['imageMessage'].get('caption', '')
                media_url = message_info['imageMessage'].get('url', '')
            elif 'documentMessage' in message_info:
                message_type = "document"
                media_caption = message_info['documentMessage'].get('caption', '')
                media_url = message_info['documentMessage'].get('url', '')
            elif 'audioMessage' in message_info:
                message_type = "audio"
                media_url = message_info['audioMessage'].get('url', '')
            elif 'videoMessage' in message_info:
                message_type = "video"
                media_caption = message_info['videoMessage'].get('caption', '')
                media_url = message_info['videoMessage'].get('url', '')

            # Check if message already exists
            stmt = select(WhatsAppMessage).where(WhatsAppMessage.external_id == message_id)
            result = await db.execute(stmt)
            existing_message = result.scalar_one_or_none()

            if not existing_message:
                # Create new message record
                message = WhatsAppMessage(
                    id=f"incoming_{message_id}",
                    instance_name=instance_name,
                    chat_id=chat_id,
                    sender_id=sender_id,
                    recipient_id="self",  # This is an incoming message
                    message_type=message_type,
                    content=content,
                    media_url=media_url,
                    media_caption=media_caption,
                    status=MessageStatus.DELIVERED,
                    external_id=message_id,
                    created_at=datetime.fromtimestamp(message_data.get('messageTimestamp', 0)),
                    delivered_at=datetime.utcnow(),
                    message_data={
                        "incoming": True,
                        "message_data": message_data
                    }
                )

                db.add(message)
                await db.commit()

                logger.info(f"Stored incoming message {message_id} from {sender_id}")

    except Exception as e:
        logger.error(f"Error handling message upsert: {e}")


async def handle_message_update(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle message status updates."""
    try:
        updates = data if isinstance(data, list) else [data]

        for update_data in updates:
            key = update_data.get('key', {})
            update_info = update_data.get('update', {})

            message_id = key.get('id', '')
            status_update = update_info.get('status')

            if not message_id or not status_update:
                continue

            # Map Evolution API status to our status
            status_map = {
                1: MessageStatus.SENT,
                2: MessageStatus.DELIVERED,
                3: MessageStatus.READ
            }

            new_status = status_map.get(status_update, MessageStatus.SENT)

            # Update message status
            stmt = select(WhatsAppMessage).where(WhatsAppMessage.external_id == message_id)
            result = await db.execute(stmt)
            message = result.scalar_one_or_none()

            if message:
                message.status = new_status
                message.updated_at = datetime.utcnow()

                if new_status == MessageStatus.DELIVERED:
                    message.delivered_at = datetime.utcnow()
                elif new_status == MessageStatus.READ:
                    message.read_at = datetime.utcnow()

                await db.commit()
                logger.info(f"Updated message {message_id} status to {new_status}")

    except Exception as e:
        logger.error(f"Error handling message update: {e}")


async def handle_send_message(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle outgoing message confirmation."""
    try:
        key = data.get('key', {})
        message_id = key.get('id', '')

        if message_id:
            # Update message with external ID
            stmt = select(WhatsAppMessage).where(
                WhatsAppMessage.instance_name == instance_name,
                WhatsAppMessage.external_id.is_(None),
                WhatsAppMessage.status == MessageStatus.PENDING
            )
            result = await db.execute(stmt)
            message = result.first()

            if message:
                message[0].external_id = message_id
                message[0].status = MessageStatus.SENT
                message[0].sent_at = datetime.utcnow()
                await db.commit()

                logger.info(f"Updated outgoing message with external ID {message_id}")

    except Exception as e:
        logger.error(f"Error handling send message: {e}")


async def handle_contact_upsert(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle contact updates."""
    try:
        contacts = data if isinstance(data, list) else [data]

        for contact_data in contacts:
            contact_id = contact_data.get('id', '')
            phone_number = contact_id.split('@')[0] if '@' in contact_id else contact_id

            # Check if contact exists
            stmt = select(WhatsAppContact).where(
                WhatsAppContact.instance_name == instance_name,
                WhatsAppContact.phone_number == phone_number
            )
            result = await db.execute(stmt)
            existing_contact = result.scalar_one_or_none()

            if existing_contact:
                # Update existing contact
                existing_contact.name = contact_data.get('pushName') or contact_data.get('name')
                existing_contact.profile_picture_url = contact_data.get('profilePictureUrl')
                existing_contact.updated_at = datetime.utcnow()
            else:
                # Create new contact
                contact = WhatsAppContact(
                    id=f"contact_{contact_id}",
                    instance_name=instance_name,
                    phone_number=phone_number,
                    formatted_number=contact_id,
                    name=contact_data.get('pushName') or contact_data.get('name'),
                    profile_picture_url=contact_data.get('profilePictureUrl')
                )
                db.add(contact)

            await db.commit()

    except Exception as e:
        logger.error(f"Error handling contact upsert: {e}")


async def handle_connection_update(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle instance connection updates."""
    try:
        state = data.get('state', '')

        # Update instance status
        stmt = select(WhatsAppInstance).where(WhatsAppInstance.name == instance_name)
        result = await db.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance:
            instance.status = state
            instance.is_connected = state == 'open'
            instance.last_activity = datetime.utcnow()
            instance.updated_at = datetime.utcnow()

            # Update phone number and profile if available
            if 'number' in data:
                instance.phone_number = data['number']
            if 'profileName' in data:
                instance.profile_name = data['profileName']

            await db.commit()
            logger.info(f"Updated instance {instance_name} connection status to {state}")

    except Exception as e:
        logger.error(f"Error handling connection update: {e}")


async def handle_presence_update(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle presence updates (online/offline status)."""
    try:
        contact_id = data.get('id', '')
        presence = data.get('presences', {})

        if contact_id and presence:
            phone_number = contact_id.split('@')[0] if '@' in contact_id else contact_id

            # Update contact last seen
            stmt = select(WhatsAppContact).where(
                WhatsAppContact.instance_name == instance_name,
                WhatsAppContact.phone_number == phone_number
            )
            result = await db.execute(stmt)
            contact = result.scalar_one_or_none()

            if contact:
                last_seen_timestamp = presence.get('lastSeen')
                if last_seen_timestamp:
                    contact.last_seen = datetime.fromtimestamp(last_seen_timestamp)
                    contact.updated_at = datetime.utcnow()
                    await db.commit()

    except Exception as e:
        logger.error(f"Error handling presence update: {e}")


async def handle_chat_upsert(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle chat updates."""
    try:
        chats = data if isinstance(data, list) else [data]

        for chat_data in chats:
            chat_id = chat_data.get('id', '')

            # For individual chats, update contact information
            if '@s.whatsapp.net' in chat_id:
                phone_number = chat_id.split('@')[0]

                stmt = select(WhatsAppContact).where(
                    WhatsAppContact.instance_name == instance_name,
                    WhatsAppContact.phone_number == phone_number
                )
                result = await db.execute(stmt)
                contact = result.scalar_one_or_none()

                if contact:
                    # Update contact with chat information
                    if 'name' in chat_data:
                        contact.name = chat_data['name']
                    contact.updated_at = datetime.utcnow()
                    await db.commit()

    except Exception as e:
        logger.error(f"Error handling chat upsert: {e}")


# Health check endpoint for webhooks
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "whatsapp-webhooks"
    }


# Webhook validation endpoint
@router.post("/validate")
async def validate_webhook(request: Request):
    """Validate webhook configuration."""
    try:
        payload = await request.json()
        return {
            "status": "valid",
            "received_data": payload,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {str(e)}")