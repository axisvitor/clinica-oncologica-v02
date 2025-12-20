"""
Mock Evolution API for testing and development.
Implements the same interface as the real Evolution API client.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from uuid import uuid4
import random

if TYPE_CHECKING:
    from .evolution_client import EvolutionAPIClient

from ..models.message import (
    MessageResponse,
    ContactResponse,
    InstanceStatus,
    MessageStatus,
    MessageType,
)

logger = logging.getLogger(__name__)


class MockEvolutionAPIClient:
    """
    Mock Evolution API client for testing and development.
    Simulates all Evolution API functionality without external dependencies.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str = "mock-api-key",
        global_webhook_url: Optional[str] = None,
        max_retries: int = 3,
        timeout_seconds: int = 30,
        rate_limit_requests: int = 100,
        rate_limit_window: int = 60,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.global_webhook_url = global_webhook_url
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        # Mock data storage
        self.instances: Dict[str, Dict[str, Any]] = {}
        self.messages: Dict[str, Dict[str, Any]] = {}
        self.contacts: Dict[str, List[Dict[str, Any]]] = {}
        self.connected = False

        # Simulation settings
        self.simulate_delays = True
        self.failure_rate = 0.05  # 5% failure rate for testing
        self.qr_code_timeout = 60  # seconds

        logger.info("Initialized Mock Evolution API Client")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Mock connection initialization."""
        if self.simulate_delays:
            await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True
        logger.info("Mock Evolution API client connected")

    async def disconnect(self):
        """Mock connection cleanup."""
        self.connected = False
        logger.info("Mock Evolution API client disconnected")

    async def _simulate_api_call(self, delay: float = 0.1) -> bool:
        """Simulate API call with potential failure."""
        if self.simulate_delays:
            await asyncio.sleep(delay)

        # Simulate random failures
        if random.random() < self.failure_rate:
            raise Exception("Simulated API failure")

        return True

    async def create_instance(
        self,
        instance_name: str,
        webhook_url: Optional[str] = None,
        webhook_events: Optional[List[str]] = None,
    ) -> InstanceStatus:
        """Create a mock WhatsApp instance."""
        await self._simulate_api_call()

        if instance_name in self.instances:
            raise Exception(f"Instance {instance_name} already exists")

        # Generate mock QR code
        qr_code = f"mock-qr-code-{instance_name}-{uuid4().hex[:8]}"

        self.instances[instance_name] = {
            "name": instance_name,
            "status": "created",
            "is_connected": False,
            "qr_code": qr_code,
            "webhook_url": webhook_url or self.global_webhook_url,
            "webhook_events": webhook_events or [],
            "created_at": datetime.now(timezone.utc),
            "phone_number": None,
            "profile_name": None,
        }

        # Initialize empty contacts list
        self.contacts[instance_name] = []

        logger.info(f"Created mock instance: {instance_name}")

        return InstanceStatus(
            name=instance_name, status="created", is_connected=False, qr_code=qr_code
        )

    async def get_instance_status(self, instance_name: str) -> InstanceStatus:
        """Get mock instance status."""
        await self._simulate_api_call(0.05)

        if instance_name not in self.instances:
            raise Exception(f"Instance {instance_name} not found")

        instance = self.instances[instance_name]

        # Simulate connection after some time
        created_at = instance["created_at"]
        if datetime.now(timezone.utc) - created_at > timedelta(seconds=10):
            if not instance["is_connected"]:
                instance["status"] = "open"
                instance["is_connected"] = True
                instance["phone_number"] = f"55119{random.randint(10000000, 99999999)}"
                instance["profile_name"] = f"Mock User {instance_name}"

                # Add some mock contacts
                self._generate_mock_contacts(instance_name)

        return InstanceStatus(
            name=instance_name,
            status=instance["status"],
            is_connected=instance["is_connected"],
            phone_number=instance["phone_number"],
            profile_name=instance["profile_name"],
            qr_code=instance.get("qr_code") if not instance["is_connected"] else None,
        )

    async def get_qr_code(self, instance_name: str) -> Optional[str]:
        """Get mock QR code."""
        await self._simulate_api_call(0.05)

        if instance_name not in self.instances:
            return None

        instance = self.instances[instance_name]
        if instance["is_connected"]:
            return None

        return instance.get("qr_code")

    async def send_text_message(
        self,
        instance_name: str,
        to: str,
        text: str,
        message_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResponse:
        """Send mock text message."""
        await self._simulate_api_call(0.2)

        if instance_name not in self.instances:
            raise Exception(f"Instance {instance_name} not found")

        if not self.instances[instance_name]["is_connected"]:
            raise Exception(f"Instance {instance_name} not connected")

        message_id = f"mock_msg_{uuid4().hex[:16]}"

        # Store message for status simulation
        self.messages[message_id] = {
            "id": message_id,
            "instance_name": instance_name,
            "to": to,
            "text": text,
            "type": "text",
            "status": MessageStatus.SENT,
            "created_at": datetime.now(timezone.utc),
            "message_data": message_data or {},
        }

        # Simulate delivery status updates
        asyncio.create_task(self._simulate_message_delivery(message_id))

        logger.info(f"Mock text message sent: {message_id} to {to}")

        return MessageResponse(
            id=message_id,
            external_id=message_id,
            status=MessageStatus.SENT,
            message="Mock message sent successfully",
            timestamp=datetime.now(timezone.utc),
            message_data=message_data,
        )

    async def send_media_message(
        self,
        instance_name: str,
        to: str,
        media_url: str,
        media_type: MessageType,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        message_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResponse:
        """Send mock media message."""
        await self._simulate_api_call(0.3)  # Media takes longer

        if instance_name not in self.instances:
            raise Exception(f"Instance {instance_name} not found")

        if not self.instances[instance_name]["is_connected"]:
            raise Exception(f"Instance {instance_name} not connected")

        message_id = f"mock_media_{uuid4().hex[:16]}"

        # Store message for status simulation
        self.messages[message_id] = {
            "id": message_id,
            "instance_name": instance_name,
            "to": to,
            "media_url": media_url,
            "media_type": media_type.value,
            "caption": caption,
            "filename": filename,
            "type": "media",
            "status": MessageStatus.SENT,
            "created_at": datetime.now(timezone.utc),
            "message_data": message_data or {},
        }

        # Simulate delivery status updates
        asyncio.create_task(self._simulate_message_delivery(message_id))

        logger.info(f"Mock media message sent: {message_id} to {to}")

        return MessageResponse(
            id=message_id,
            external_id=message_id,
            status=MessageStatus.SENT,
            message="Mock media message sent successfully",
            timestamp=datetime.now(timezone.utc),
            message_data=message_data,
        )

    async def get_contacts(self, instance_name: str) -> List[ContactResponse]:
        """Get mock contacts."""
        await self._simulate_api_call(0.1)

        if instance_name not in self.instances:
            raise Exception(f"Instance {instance_name} not found")

        contacts = self.contacts.get(instance_name, [])

        return [
            ContactResponse(
                id=contact["id"],
                phone_number=contact["phone_number"],
                formatted_number=contact["formatted_number"],
                name=contact["name"],
                profile_picture_url=contact.get("profile_picture_url"),
                is_whatsapp_user=True,
            )
            for contact in contacts
        ]

    async def check_whatsapp_number(
        self, instance_name: str, phone_number: str
    ) -> bool:
        """Mock WhatsApp number check."""
        await self._simulate_api_call(0.1)

        # Simulate 90% of numbers being on WhatsApp
        return random.random() < 0.9

    async def get_message_status(
        self, instance_name: str, message_id: str
    ) -> MessageStatus:
        """Get mock message status."""
        await self._simulate_api_call(0.05)

        if message_id in self.messages:
            return MessageStatus(self.messages[message_id]["status"])

        return MessageStatus.FAILED

    async def set_webhook_url(
        self, instance_name: str, webhook_url: str, events: Optional[List[str]] = None
    ) -> bool:
        """Set mock webhook URL."""
        await self._simulate_api_call(0.1)

        if instance_name not in self.instances:
            return False

        self.instances[instance_name]["webhook_url"] = webhook_url
        self.instances[instance_name]["webhook_events"] = events or []

        logger.info(f"Updated webhook for {instance_name}: {webhook_url}")
        return True

    async def delete_instance(self, instance_name: str) -> bool:
        """Delete mock instance."""
        await self._simulate_api_call(0.1)

        if instance_name in self.instances:
            del self.instances[instance_name]
            if instance_name in self.contacts:
                del self.contacts[instance_name]
            logger.info(f"Deleted mock instance: {instance_name}")
            return True

        return False

    async def restart_instance(self, instance_name: str) -> bool:
        """Restart mock instance."""
        await self._simulate_api_call(0.2)

        if instance_name not in self.instances:
            return False

        # Reset connection status
        self.instances[instance_name]["is_connected"] = False
        self.instances[instance_name]["status"] = "restarting"

        # Simulate reconnection after delay
        async def reconnect():
            await asyncio.sleep(5)
            if instance_name in self.instances:
                self.instances[instance_name]["is_connected"] = True
                self.instances[instance_name]["status"] = "open"

        asyncio.create_task(reconnect())

        logger.info(f"Restarted mock instance: {instance_name}")
        return True

    async def logout_instance(self, instance_name: str) -> bool:
        """Logout mock instance."""
        await self._simulate_api_call(0.1)

        if instance_name not in self.instances:
            return False

        self.instances[instance_name]["is_connected"] = False
        self.instances[instance_name]["status"] = "disconnected"
        self.instances[instance_name]["phone_number"] = None
        self.instances[instance_name]["profile_name"] = None

        logger.info(f"Logged out mock instance: {instance_name}")
        return True

    def _generate_mock_contacts(self, instance_name: str):
        """Generate mock contacts for testing."""
        mock_contacts = [
            {
                "id": f"contact_{i}",
                "phone_number": f"5511{random.randint(900000000, 999999999)}",
                "formatted_number": f"5511{random.randint(900000000, 999999999)}@s.whatsapp.net",
                "name": f"Contact {i}",
                "profile_picture_url": f"https://api.dicebear.com/7.x/personas/svg?seed=contact{i}",
            }
            for i in range(1, 11)  # Generate 10 mock contacts
        ]

        self.contacts[instance_name] = mock_contacts
        logger.info(f"Generated {len(mock_contacts)} mock contacts for {instance_name}")

    async def _simulate_message_delivery(self, message_id: str):
        """Simulate message delivery status updates."""
        if message_id not in self.messages:
            return

        # Simulate delivery after 2-5 seconds
        await asyncio.sleep(random.uniform(2, 5))

        if message_id in self.messages:
            self.messages[message_id]["status"] = MessageStatus.DELIVERED
            logger.debug(f"Mock message {message_id} delivered")

        # Simulate read status after another 5-15 seconds
        await asyncio.sleep(random.uniform(5, 15))

        if message_id in self.messages and random.random() < 0.7:  # 70% read rate
            self.messages[message_id]["status"] = MessageStatus.READ
            logger.debug(f"Mock message {message_id} read")


# Factory function to create the appropriate client
def create_evolution_client(
    base_url: str, api_key: str, use_mock: bool = False, **kwargs
) -> "EvolutionAPIClient":
    """Create Evolution API client (real or mock)."""
    if use_mock or base_url.startswith("mock://"):
        return MockEvolutionAPIClient(base_url, api_key, **kwargs)
    else:
        from .evolution_client import EvolutionAPIClient

        return EvolutionAPIClient(base_url, api_key, **kwargs)
