"""
Configuration Builder Helpers.

Provides helper functions for:
- Safe environment variable filtering
- API URL construction
- Firebase public configuration
"""

from typing import Dict, Any
import os

from app.config import settings


def _filter_safe_env_vars() -> Dict[str, str]:
    """
    Filter environment variables to only safe, non-sensitive values.

    Whitelist patterns:
    - VITE_* (Vite frontend variables)
    - PUBLIC_* (explicitly public variables)
    - RAILWAY_PUBLIC_* (Railway public metadata)

    NEVER expose:
    - DATABASE_URL, SECRET_KEY, API_KEYS
    - FIREBASE_ADMIN_PRIVATE_KEY, SERVICE_ROLE_KEY
    - Any credentials or secrets

    Returns:
        Dict[str, str]: Filtered dictionary of safe environment variables

    Security:
        - Whitelist-based filtering (only safe prefixes allowed)
        - Blacklist check for sensitive terms even in public variables
        - Double validation to prevent accidental exposure
    """
    safe_vars = {}
    safe_prefixes = ("VITE_", "PUBLIC_", "RAILWAY_PUBLIC_")

    # Blacklist for sensitive terms even in public variables
    sensitive_terms = ("SECRET", "PRIVATE", "PASSWORD", "ADMIN_KEY", "SERVICE_ROLE")

    for key, value in os.environ.items():
        if key.startswith(safe_prefixes):
            # Double check for sensitive terms
            if any(term in key.upper() for term in sensitive_terms):
                continue
            safe_vars[key] = value

    return safe_vars


def _build_api_urls() -> Dict[str, str]:
    """
    Build API URLs based on environment.

    Returns:
        Dict[str, str]: Dictionary containing:
            - API_URL: Base API URL
            - API_BASE_URL: Versioned API base URL (/api/v2)
            - WS_BASE_URL: WebSocket base URL

    Logic:
        1. Check FRONTEND_API_URL environment variable
        2. Fall back to Railway environment variables
        3. Fall back to environment-based defaults
        4. Generate derivative URLs from base URL
    """
    api_url = os.getenv("FRONTEND_API_URL")

    if not api_url:
        # Check Railway environment
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        railway_static = os.getenv("RAILWAY_STATIC_URL")

        if railway_domain:
            api_url = (
                railway_domain
                if railway_domain.startswith("http")
                else f"https://{railway_domain}"
            )
        elif railway_static:
            api_url = railway_static
        else:
            # Fallback based on environment
            if settings.APP_ENVIRONMENT == "production":
                api_url = "https://backend-production.railway.app"
            else:
                port = os.getenv("PORT", "8000")
                api_url = f"http://localhost:{port}"

    # Build derivative URLs
    api_base_url = f"{api_url}/api/v2"
    ws_base_url = (
        api_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    )

    return {
        "API_URL": api_url,
        "API_BASE_URL": api_base_url,
        "WS_BASE_URL": ws_base_url,
    }


def _get_firebase_public_config() -> Dict[str, Any]:
    """
    Get PUBLIC Firebase configuration (web app keys only, NOT service account).

    Returns:
        Dict[str, Any]: Firebase web app configuration in VITE_ format

    Security:
        - Only returns PUBLIC Firebase web app config
        - NEVER exposes service account credentials
        - NEVER exposes admin SDK private keys
        - Safe to expose to frontend applications

    Note:
        Returns empty dict if Firebase is not configured.
        All keys are prefixed with VITE_ for frontend compatibility.
    """
    firebase_config = {}

    # Only PUBLIC Firebase web app config
    firebase_api_key = os.getenv("FIREBASE_WEB_API_KEY")
    firebase_project_id = os.getenv("FIREBASE_WEB_PROJECT_ID")
    firebase_app_id = os.getenv("FIREBASE_WEB_APP_ID")
    firebase_auth_domain = os.getenv("FIREBASE_AUTH_DOMAIN")

    if firebase_api_key:
        firebase_config["VITE_FIREBASE_API_KEY"] = firebase_api_key
    if firebase_project_id:
        firebase_config["VITE_FIREBASE_PROJECT_ID"] = firebase_project_id
    if firebase_app_id:
        firebase_config["VITE_FIREBASE_APP_ID"] = firebase_app_id
    if firebase_auth_domain:
        firebase_config["VITE_FIREBASE_AUTH_DOMAIN"] = firebase_auth_domain

    return firebase_config


# Public API aliases (without underscore for backward compatibility)
filter_safe_env_vars = _filter_safe_env_vars
build_api_urls = _build_api_urls
get_firebase_public_config = _get_firebase_public_config
