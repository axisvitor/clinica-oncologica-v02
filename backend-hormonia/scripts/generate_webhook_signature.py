#!/usr/bin/env python3
"""
Webhook Signature Generator

Utility script to generate valid HMAC-SHA256 webhook signatures
for testing WhatsApp webhook endpoints.

Usage:
    python scripts/generate_webhook_signature.py
    python scripts/generate_webhook_signature.py --secret "your_secret" --payload '{"event":"test"}'
"""

import argparse
import hmac
import hashlib
import json
import time
import sys
from typing import Dict, Any


def generate_signature(
    payload: Dict[str, Any],
    secret: str,
    timestamp: str = None
) -> tuple[str, str, str]:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: Webhook payload dictionary
        secret: Webhook secret key
        timestamp: Unix timestamp (defaults to current time)

    Returns:
        Tuple of (signature, timestamp, curl_command)
    """
    # Use current timestamp if not provided
    if timestamp is None:
        timestamp = str(int(time.time()))

    # Serialize payload to JSON
    payload_json = json.dumps(payload, sort_keys=True)

    # Create signature string
    signature_string = f"{timestamp}.{payload_json}"

    # Compute HMAC-SHA256
    signature = hmac.new(
        secret.encode('utf-8'),
        signature_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Generate curl command for testing
    curl_command = f"""curl -X POST http://localhost:8000/api/v2/webhooks/whatsapp \\
  -H "Content-Type: application/json" \\
  -H "X-Webhook-Signature: {signature}" \\
  -H "X-Webhook-Timestamp: {timestamp}" \\
  -H "X-Webhook-Id: test_{int(time.time())}" \\
  -d '{payload_json}'
"""

    return signature, timestamp, curl_command


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate HMAC-SHA256 webhook signatures for testing"
    )
    parser.add_argument(
        "--secret",
        type=str,
        default="test_webhook_secret_1234567890abcdef",
        help="Webhook secret key (default: test secret)"
    )
    parser.add_argument(
        "--payload",
        type=str,
        default=None,
        help="Webhook payload as JSON string"
    )
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="Unix timestamp (defaults to current time)"
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:8000/api/v2/webhooks/whatsapp",
        help="Webhook endpoint URL"
    )
    parser.add_argument(
        "--generate-secret",
        action="store_true",
        help="Generate a new secure webhook secret"
    )

    args = parser.parse_args()

    # Generate secure secret if requested
    if args.generate_secret:
        import secrets
        new_secret = f"wh_secret_{secrets.token_urlsafe(32)}"
        print("\n" + "="*70)
        print("GENERATED WEBHOOK SECRET")
        print("="*70)
        print(f"\n{new_secret}\n")
        print("Add this to your .env file:")
        print(f"EVOLUTION_WEBHOOK_SECRET={new_secret}\n")
        print("="*70 + "\n")
        return

    # Default test payload
    if args.payload is None:
        payload = {
            "event": "message.received",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net"
                },
                "message": {
                    "conversation": "Test message from signature generator"
                },
                "messageTimestamp": str(int(time.time()))
            },
            "instance": "clinica_oncologica",
            "date_time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        }
    else:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON payload: {e}", file=sys.stderr)
            sys.exit(1)

    # Generate signature
    signature, timestamp, curl_command = generate_signature(
        payload=payload,
        secret=args.secret,
        timestamp=args.timestamp
    )

    # Update curl command with custom endpoint
    if args.endpoint != "http://localhost:8000/api/v2/webhooks/whatsapp":
        curl_command = curl_command.replace(
            "http://localhost:8000/api/v2/webhooks/whatsapp",
            args.endpoint
        )

    # Display results
    print("\n" + "="*70)
    print("WEBHOOK SIGNATURE GENERATED")
    print("="*70)
    print(f"\nSecret: {args.secret[:20]}...")
    print(f"Timestamp: {timestamp} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(timestamp)))})")
    print(f"Signature: {signature}")
    print(f"\nPayload:")
    print(json.dumps(payload, indent=2))
    print("\n" + "-"*70)
    print("CURL COMMAND FOR TESTING")
    print("-"*70)
    print(curl_command)
    print("="*70 + "\n")

    # Test invalid signature example
    invalid_signature = "invalid_signature_" + "0" * 48
    invalid_curl = f"""curl -X POST {args.endpoint} \\
  -H "Content-Type: application/json" \\
  -H "X-Webhook-Signature: {invalid_signature}" \\
  -H "X-Webhook-Timestamp: {timestamp}" \\
  -H "X-Webhook-Id: test_invalid_{int(time.time())}" \\
  -d '{json.dumps(payload, sort_keys=True)}'
"""

    print("TEST INVALID SIGNATURE (Should return 401)")
    print("-"*70)
    print(invalid_curl)
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
