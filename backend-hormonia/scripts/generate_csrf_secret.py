#!/usr/bin/env python3
"""
Script to generate a secure CSRF secret key.

This script generates a cryptographically secure random key suitable
for use as CSRF_SECRET_KEY in the .env file.

Usage:
    python scripts/generate_csrf_secret.py
"""

import secrets


def generate_csrf_secret():
    """
    Generate a secure CSRF secret key.

    Returns:
        str: A URL-safe base64-encoded random string (32 bytes)
    """
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    secret = generate_csrf_secret()
    print("=" * 80)
    print("CSRF Secret Key Generator")
    print("=" * 80)
    print()
    print("Generated CSRF Secret Key:")
    print(secret)
    print()
    print("Add this to your .env file:")
    print(f"CSRF_SECRET_KEY={secret}")
    print()
    print("=" * 80)
    print()
    print("Security Notes:")
    print("- Keep this secret safe and never commit it to version control")
    print("- Use a different secret for each environment (dev, staging, production)")
    print("- Rotate secrets regularly (every 90 days recommended)")
    print("- Store secrets in a secure vault in production (AWS Secrets Manager, etc.)")
    print()
