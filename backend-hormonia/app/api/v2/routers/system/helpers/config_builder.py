"""
Configuration Builder Helpers.

Provides helper functions for:
- Safe environment variable filtering
- API URL construction
"""

from typing import Dict
import os

from app.config import settings


def _filter_safe_env_vars() -> Dict[str, str]:
    """
    Filter environment variables to only safe, non-sensitive values.

    Whitelist patterns:
    - VITE_* (frontend variables)
    - PUBLIC_* (explicitly public variables)
    - RAILWAY_PUBLIC_* (Railway public metadata)

    NEVER expose:
    - DATABASE_URL, SECRET_KEY, API_KEYS
    - service credentials or secrets
    - legacy third-party auth configuration

    Returns:
        Dict[str, str]: Filtered dictionary of safe environment variables

    Security:
        - Whitelist-based filtering (only safe prefixes allowed)
        - Blacklist check for sensitive terms even in public variables
        - Explicitly excludes legacy auth-related keys from the session-first runtime
    """
    safe_vars = {}
    safe_prefixes = ("VITE_", "PUBLIC_", "RAILWAY_PUBLIC_")

    # Blacklist for sensitive or out-of-scope terms even in public variables
    blocked_terms = (
        "SECRET",
        "PRIVATE",
        "PASSWORD",
        "ADMIN_KEY",
        "SERVICE_ROLE",
        "FIREBASE",
    )

    for key, value in os.environ.items():
        if key.startswith(safe_prefixes):
            if any(term in key.upper() for term in blocked_terms):
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
            if settings.APP_ENVIRONMENT == "production":
                api_url = "https://backend-production.railway.app"
            else:
                port = os.getenv("PORT", "8000")
                api_url = f"http://localhost:{port}"

    api_base_url = f"{api_url}/api/v2"
    ws_base_url = (
        api_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    )

    return {
        "API_URL": api_url,
        "API_BASE_URL": api_base_url,
        "WS_BASE_URL": ws_base_url,
    }


# Public API aliases (without underscore for backward compatibility)
filter_safe_env_vars = _filter_safe_env_vars
build_api_urls = _build_api_urls
