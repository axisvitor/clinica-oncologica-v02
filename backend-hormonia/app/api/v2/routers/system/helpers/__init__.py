"""
System Management Helpers Module.

This module exports all helper functions used by the system router.
Organized into specialized submodules for better maintainability.

Functions are available both with underscore prefix (private convention)
and without underscore (public API for backward compatibility).
"""

from .auth import (
    _is_admin,
    _get_redis_client,
    is_admin,
    get_redis_client,  # Public aliases
)
from .config_builder import (
    _filter_safe_env_vars,
    _build_api_urls,
    filter_safe_env_vars,
    build_api_urls,
)
from .health_checker import (
    _check_component_health,
    _calculate_health_score,
    check_component_health,
    calculate_health_score,  # Public aliases
)

__all__ = [
    # Auth helpers (private convention with underscore)
    "_is_admin",
    "_get_redis_client",
    # Auth helpers (public API)
    "is_admin",
    "get_redis_client",
    # Config builder helpers (private convention)
    "_filter_safe_env_vars",
    "_build_api_urls",
    # Config builder helpers (public API)
    "filter_safe_env_vars",
    "build_api_urls",
    # Health checker helpers (private convention)
    "_check_component_health",
    "_calculate_health_score",
    # Health checker helpers (public API)
    "check_component_health",
    "calculate_health_score",
]
