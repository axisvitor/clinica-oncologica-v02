#!/usr/bin/env python3
"""
Environment Variables Validation Script
Validates backend and frontend .env files for development and production readiness
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import re


class EnvValidator:
    """Environment validation utilities"""

    # Placeholder patterns to detect
    PLACEHOLDER_PATTERNS = [
        r'your[-_]',
        r'changeme',
        r'placeholder',
        r'example',
        r'xxx+',
        r'todo',
        r'replace',
        r'<.*>',
    ]

    # Common insecure values
    INSECURE_VALUES = [
        'secret',
        'password',
        'key',
        '123456',
        'admin',
        'test',
        'dev',
    ]


def parse_env_file(env_path: Path) -> Dict[str, str]:
    """Parse .env file and return key-value pairs"""
    env_vars = {}

    if not env_path.exists():
        return env_vars

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    env_vars[key] = value

    except Exception as e:
        print(f"⚠️  Error reading {env_path}: {e}")

    return env_vars


def is_placeholder(value: str) -> bool:
    """Check if value looks like a placeholder"""
    if not value:
        return True

    value_lower = value.lower()

    # Check against placeholder patterns
    for pattern in EnvValidator.PLACEHOLDER_PATTERNS:
        if re.search(pattern, value_lower):
            return True

    return False


def is_insecure(key: str, value: str) -> bool:
    """Check if value is insecure for production"""
    if not value or len(value) < 16:
        return True

    value_lower = value.lower()

    # Check if value matches key name (e.g., SECRET_KEY=secret_key)
    if value_lower == key.lower():
        return True

    # Check common insecure values
    for insecure in EnvValidator.INSECURE_VALUES:
        if value_lower == insecure:
            return True

    return False


def validate_backend_env() -> Tuple[List[str], List[str]]:
    """Validate backend environment configuration"""
    errors = []
    warnings = []

    env_file = Path('backend-hormonia/.env')

    if not env_file.exists():
        errors.append("❌ backend-hormonia/.env not found")
        return errors, warnings

    env_vars = parse_env_file(env_file)

    # Required variables
    required_vars = [
        'SECRET_KEY',
        'JWT_SECRET_KEY',
        'ENCRYPTION_KEY',
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'DATABASE_URL',
        'REDIS_URL',
    ]

    # Check for missing required vars
    for var in required_vars:
        if var not in env_vars:
            errors.append(f"❌ Missing required variable: {var}")
        elif not env_vars[var]:
            errors.append(f"❌ Empty value for required variable: {var}")

    # Validate SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY
    secret_vars = ['SECRET_KEY', 'JWT_SECRET_KEY', 'ENCRYPTION_KEY']
    for var in secret_vars:
        if var in env_vars:
            value = env_vars[var]

            # Check for placeholders
            if is_placeholder(value):
                errors.append(f"❌ {var} contains placeholder value: '{value}'")

            # Check for insecure values
            elif is_insecure(var, value):
                errors.append(f"❌ {var} is too weak or insecure (min 16 chars, must be random)")

            # Check minimum length
            elif len(value) < 32:
                warnings.append(f"⚠️  {var} should be at least 32 characters for production")

    # Production-specific validations
    env = env_vars.get('ENVIRONMENT', 'development')
    debug = env_vars.get('DEBUG', 'false').lower()

    if env == 'production':
        # DEBUG must be false in production
        if debug != 'false':
            errors.append("❌ DEBUG must be 'false' in production environment")

        # REDIS_SSL should be true
        redis_ssl = env_vars.get('REDIS_SSL', 'false').lower()
        if redis_ssl != 'true':
            warnings.append("⚠️  REDIS_SSL should be 'true' for production")

        # Database URL should use SSL
        db_url = env_vars.get('DATABASE_URL', '')
        if db_url and 'sslmode=require' not in db_url:
            warnings.append("⚠️  DATABASE_URL should include 'sslmode=require' for production")

        # CORS origins should not be wildcard
        cors_origins = env_vars.get('CORS_ORIGINS', '')
        if '*' in cors_origins:
            errors.append("❌ CORS_ORIGINS should not use wildcard (*) in production")

    # Firebase validation (if enabled)
    firebase_enabled = env_vars.get('FIREBASE_ENABLED', 'false').lower()
    if firebase_enabled == 'true':
        firebase_vars = [
            'FIREBASE_TYPE',
            'FIREBASE_PROJECT_ID',
            'FIREBASE_PRIVATE_KEY_ID',
            'FIREBASE_PRIVATE_KEY',
            'FIREBASE_CLIENT_EMAIL',
        ]

        for var in firebase_vars:
            if var not in env_vars or not env_vars[var]:
                errors.append(f"❌ Firebase enabled but missing: {var}")
            elif is_placeholder(env_vars[var]):
                errors.append(f"❌ {var} contains placeholder value")

    # Supabase validation
    supabase_url = env_vars.get('SUPABASE_URL', '')
    if supabase_url:
        if not supabase_url.startswith('https://'):
            errors.append("❌ SUPABASE_URL must use HTTPS")
        if is_placeholder(supabase_url):
            errors.append("❌ SUPABASE_URL contains placeholder value")

    supabase_key = env_vars.get('SUPABASE_KEY', '')
    if supabase_key and is_placeholder(supabase_key):
        errors.append("❌ SUPABASE_KEY contains placeholder value")

    # Redis validation
    redis_url = env_vars.get('REDIS_URL', '')
    if redis_url and is_placeholder(redis_url):
        errors.append("❌ REDIS_URL contains placeholder value")

    return errors, warnings


def validate_frontend_env() -> Tuple[List[str], List[str]]:
    """Validate frontend environment configuration"""
    errors = []
    warnings = []

    env_file = Path('frontend-hormonia/.env')

    if not env_file.exists():
        errors.append("❌ frontend-hormonia/.env not found")
        return errors, warnings

    env_vars = parse_env_file(env_file)

    # Required variables
    required_vars = [
        'VITE_SUPABASE_URL',
        'VITE_SUPABASE_ANON_KEY',
        'VITE_API_URL',
    ]

    # Check for missing required vars
    for var in required_vars:
        if var not in env_vars:
            errors.append(f"❌ Missing required variable: {var}")
        elif not env_vars[var]:
            errors.append(f"❌ Empty value for required variable: {var}")

    # Validate Supabase configuration
    supabase_url = env_vars.get('VITE_SUPABASE_URL', '')
    if supabase_url:
        if not supabase_url.startswith('https://'):
            errors.append("❌ VITE_SUPABASE_URL must use HTTPS")
        if is_placeholder(supabase_url):
            errors.append("❌ VITE_SUPABASE_URL contains placeholder value")
        if 'supabase.co' not in supabase_url and 'localhost' not in supabase_url:
            warnings.append("⚠️  VITE_SUPABASE_URL doesn't look like a valid Supabase URL")

    supabase_key = env_vars.get('VITE_SUPABASE_ANON_KEY', '')
    if supabase_key:
        if is_placeholder(supabase_key):
            errors.append("❌ VITE_SUPABASE_ANON_KEY contains placeholder value")
        if len(supabase_key) < 20:
            errors.append("❌ VITE_SUPABASE_ANON_KEY appears to be invalid (too short)")

    # Validate API URL
    api_url = env_vars.get('VITE_API_URL', '')
    if api_url:
        # Check for placeholder
        if is_placeholder(api_url):
            errors.append("❌ VITE_API_URL contains placeholder value")

        # Production should use HTTPS
        env = env_vars.get('VITE_ENVIRONMENT', 'development')
        if env == 'production':
            if not api_url.startswith('https://'):
                errors.append("❌ VITE_API_URL must use HTTPS in production")

            # Should not point to localhost
            if 'localhost' in api_url or '127.0.0.1' in api_url:
                errors.append("❌ VITE_API_URL should not point to localhost in production")

    # Firebase configuration (if used)
    firebase_api_key = env_vars.get('VITE_FIREBASE_API_KEY', '')
    firebase_project_id = env_vars.get('VITE_FIREBASE_PROJECT_ID', '')

    if firebase_api_key or firebase_project_id:
        firebase_vars = [
            'VITE_FIREBASE_API_KEY',
            'VITE_FIREBASE_AUTH_DOMAIN',
            'VITE_FIREBASE_PROJECT_ID',
            'VITE_FIREBASE_STORAGE_BUCKET',
            'VITE_FIREBASE_MESSAGING_SENDER_ID',
            'VITE_FIREBASE_APP_ID',
        ]

        for var in firebase_vars:
            if var not in env_vars or not env_vars[var]:
                warnings.append(f"⚠️  Firebase config incomplete, missing: {var}")
            elif is_placeholder(env_vars[var]):
                errors.append(f"❌ {var} contains placeholder value")

    # WebSocket URL validation
    ws_url = env_vars.get('VITE_WS_URL', '')
    if ws_url:
        if is_placeholder(ws_url):
            errors.append("❌ VITE_WS_URL contains placeholder value")

        env = env_vars.get('VITE_ENVIRONMENT', 'development')
        if env == 'production' and not ws_url.startswith('wss://'):
            errors.append("❌ VITE_WS_URL must use WSS (secure WebSocket) in production")

    return errors, warnings


def check_env_example_sync():
    """Check if .env.example files are in sync with .env requirements"""
    warnings = []

    # Backend
    backend_env = Path('backend-hormonia/.env')
    backend_example = Path('backend-hormonia/.env.example')

    if backend_env.exists() and backend_example.exists():
        env_keys = set(parse_env_file(backend_env).keys())
        example_keys = set(parse_env_file(backend_example).keys())

        missing_in_example = env_keys - example_keys
        if missing_in_example:
            warnings.append(f"⚠️  Backend .env.example missing keys: {', '.join(sorted(missing_in_example))}")

    # Frontend
    frontend_env = Path('frontend-hormonia/.env')
    frontend_example = Path('frontend-hormonia/.env.example')

    if frontend_env.exists() and frontend_example.exists():
        env_keys = set(parse_env_file(frontend_env).keys())
        example_keys = set(parse_env_file(frontend_example).keys())

        missing_in_example = env_keys - example_keys
        if missing_in_example:
            warnings.append(f"⚠️  Frontend .env.example missing keys: {', '.join(sorted(missing_in_example))}")

    return warnings


def main():
    """Main validation entry point"""
    print("🔍 Validating environment configuration...\n")

    all_errors = []
    all_warnings = []

    # Validate backend
    print("📦 Validating backend environment...")
    backend_errors, backend_warnings = validate_backend_env()
    all_errors.extend(backend_errors)
    all_warnings.extend(backend_warnings)

    if not backend_errors:
        print("   ✅ Backend validation passed")
    print()

    # Validate frontend
    print("🎨 Validating frontend environment...")
    frontend_errors, frontend_warnings = validate_frontend_env()
    all_errors.extend(frontend_errors)
    all_warnings.extend(frontend_warnings)

    if not frontend_errors:
        print("   ✅ Frontend validation passed")
    print()

    # Check .env.example sync
    print("📋 Checking .env.example synchronization...")
    sync_warnings = check_env_example_sync()
    all_warnings.extend(sync_warnings)

    if not sync_warnings:
        print("   ✅ .env.example files are in sync")
    print()

    # Print summary
    print("=" * 60)

    if all_errors:
        print(f"\n❌ Validation FAILED with {len(all_errors)} error(s):\n")
        for error in all_errors:
            print(f"  {error}")

    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} warning(s):\n")
        for warning in all_warnings:
            print(f"  {warning}")

    if not all_errors and not all_warnings:
        print("\n✅ All validations passed! Environment is properly configured.\n")
        return 0
    elif not all_errors:
        print("\n✅ Validation passed with warnings. Review warnings above.\n")
        return 0
    else:
        print("\n❌ Please fix the errors above before deploying.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
