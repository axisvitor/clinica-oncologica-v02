#!/usr/bin/env python3
"""
Security Key Validation Script

Validates all security keys in .env file for production readiness.

Usage:
    python scripts/validate_security_keys.py
    python scripts/validate_security_keys.py --env-file .env.production
    python scripts/validate_security_keys.py --generate-keys

Security Issue: AUTH-001
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.utils.security_validation import (
    validate_all_secrets,
    validate_key_strength,
    mask_secret_for_logging,
    generate_secure_key,
    is_production_ready,
)


def load_env_file(env_file: str = ".env") -> dict:
    """Load environment variables from .env file."""
    env_vars = {}
    env_path = backend_dir / env_file

    if not env_path.exists():
        print(f"❌ Environment file not found: {env_path}")
        return env_vars

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes
                value = value.strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def validate_environment_keys(env_file: str = ".env", environment: str = "production"):
    """Validate all security keys in environment file."""
    print(f"\n{'='*70}")
    print(f"🔐 Security Key Validation - {environment.upper()}")
    print(f"{'='*70}\n")

    # Load environment variables
    env_vars = load_env_file(env_file)

    if not env_vars:
        print(f"⚠️  No environment variables found in {env_file}")
        return False

    # Collect security keys
    security_keys = {
        "SECURITY_SECRET_KEY": env_vars.get("SECURITY_SECRET_KEY"),
        "AUTH_JWT_SECRET_KEY": env_vars.get("AUTH_JWT_SECRET_KEY"),
        "SECURITY_ENCRYPTION_KEY": env_vars.get("SECURITY_ENCRYPTION_KEY"),
        "SECURITY_CSRF_SECRET_KEY": env_vars.get("SECURITY_CSRF_SECRET_KEY"),
    }

    # Filter out None values
    security_keys = {k: v for k, v in security_keys.items() if v}

    if not security_keys:
        print("⚠️  No security keys found in environment file")
        return False

    print(f"Found {len(security_keys)} security keys to validate:\n")

    # Validate all keys
    results = validate_all_secrets(security_keys, environment=environment)

    # Display results
    all_valid = True
    for key_name, result in results.items():
        masked = mask_secret_for_logging(security_keys[key_name])

        if result.is_valid:
            print(f"✅ {key_name}")
            print(f"   Masked: {masked}")
            print(f"   Entropy: {result.entropy_bits:.1f} bits")
            print(f"   Strength: {result.strength_level}")
            print()
        else:
            all_valid = False
            print(f"❌ {key_name}")
            print(f"   Masked: {masked}")
            print(f"   Entropy: {result.entropy_bits:.1f} bits (minimum: 128)")
            print(f"   Strength: {result.strength_level}")
            print(f"   Issues:")
            for issue in result.issues:
                print(f"      - {issue}")
            print(f"   Recommendations:")
            for rec in result.recommendations[:2]:  # First 2 recommendations
                print(f"      - {rec}")
            print()

    # Summary
    print(f"\n{'='*70}")
    if all_valid:
        print("✅ ALL KEYS VALID - Production Ready!")
    else:
        print("❌ SOME KEYS INVALID - Fix Before Production!")
        print("\nGenerate secure keys with:")
        print("  python -c 'import secrets; print(secrets.token_urlsafe(32))'")
    print(f"{'='*70}\n")

    return all_valid


def generate_secure_keys_for_env():
    """Generate secure keys for all required security settings."""
    print(f"\n{'='*70}")
    print(f"🔑 Generating Secure Keys")
    print(f"{'='*70}\n")

    keys_to_generate = [
        "SECURITY_SECRET_KEY",
        "AUTH_JWT_SECRET_KEY",
        "SECURITY_ENCRYPTION_KEY",
        "SECURITY_CSRF_SECRET_KEY",
    ]

    print("Copy these keys to your .env file:\n")

    for key_name in keys_to_generate:
        secure_key = generate_secure_key(32)
        result = validate_key_strength(secure_key)

        print(f"{key_name}={secure_key}")
        print(f"  # Entropy: {result.entropy_bits:.1f} bits, Strength: {result.strength_level}")
        print()

    print(f"\n{'='*70}")
    print("⚠️  IMPORTANT:")
    print("  - Never commit these keys to version control")
    print("  - Use different keys for each environment")
    print("  - Store production keys in secure secret management")
    print(f"{'='*70}\n")


def quick_check_key(key: str):
    """Quick check if a single key is production ready."""
    print(f"\n{'='*70}")
    print(f"🔍 Quick Key Validation")
    print(f"{'='*70}\n")

    masked = mask_secret_for_logging(key)
    result = validate_key_strength(key, environment="production")

    print(f"Key (masked): {masked}")
    print(f"Length: {result.key_length} chars")
    print(f"Entropy: {result.entropy_bits:.1f} bits")
    print(f"Strength: {result.strength_level}")
    print(f"Production Ready: {'✅ YES' if result.is_valid else '❌ NO'}")

    if not result.is_valid:
        print(f"\nIssues:")
        for issue in result.issues:
            print(f"  - {issue}")
        print(f"\nRecommendations:")
        for rec in result.recommendations:
            print(f"  - {rec}")

    print(f"\n{'='*70}\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate security keys for production readiness"
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Environment file to validate (default: .env)"
    )
    parser.add_argument(
        "--environment",
        choices=["production", "development"],
        default="production",
        help="Environment type for validation thresholds"
    )
    parser.add_argument(
        "--generate-keys",
        action="store_true",
        help="Generate new secure keys"
    )
    parser.add_argument(
        "--check-key",
        help="Quick check a single key"
    )

    args = parser.parse_args()

    if args.generate_keys:
        generate_secure_keys_for_env()
        return

    if args.check_key:
        quick_check_key(args.check_key)
        return

    # Validate environment file
    is_valid = validate_environment_keys(args.env_file, args.environment)

    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
