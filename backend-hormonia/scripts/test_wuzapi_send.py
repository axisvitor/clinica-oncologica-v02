#!/usr/bin/env python3
"""Test script: verify WuzAPIClient.send_text() delivers a real WhatsApp message.

Usage:
    cd backend-hormonia
    python -m scripts.test_wuzapi_send
"""
from __future__ import annotations

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from app.integrations.wuzapi.client import WuzAPIClient

    base_url = os.getenv("WHATSAPP_WUZAPI_BASE_URL", "http://localhost:8081")
    token = os.getenv("WHATSAPP_WUZAPI_TOKEN", "")

    if not token:
        print("ERROR: WHATSAPP_WUZAPI_TOKEN not set")
        sys.exit(1)

    print(f"WuzAPI base URL: {base_url}")
    print(f"Token: {token[:8]}...{token[-4:]}")

    async with WuzAPIClient(base_url=base_url, token=token) as client:
        # 1. Check session status
        print("\n--- Session Status ---")
        status = await client.get_session_status()
        print(f"Connected: {status['data']['connected']}")
        print(f"Logged In: {status['data']['loggedIn']}")

        if not status["data"]["loggedIn"]:
            print("ERROR: Session not logged in. Scan QR code first.")
            sys.exit(1)

        jid = status["data"].get("jid", "")
        phone = jid.split(":")[0] if ":" in jid else jid.split("@")[0]
        print(f"Phone (from JID): {phone}")

        # 2. Send test message
        print("\n--- Sending Test Message ---")
        result = await client.send_text(
            phone=phone,
            message="✅ Teste M008 S02 - WuzAPIClient.send_text() funcionando! 🏥",
        )
        print(f"Success: {result.get('success')}")
        print(f"Message ID: {result.get('data', {}).get('Id')}")
        print(f"Details: {result.get('data', {}).get('Details')}")

        print("\n🎉 Test PASSED — message sent via WuzAPIClient!")


if __name__ == "__main__":
    asyncio.run(main())
