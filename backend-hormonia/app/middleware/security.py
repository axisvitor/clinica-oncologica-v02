"""
Security middleware wrapper module.

This module provides a wrapper/alias for the SecurityHeadersMiddleware
to maintain compatibility with test imports while keeping the actual
implementation in security_headers.py.
"""

from .security_headers import (
    SecurityHeadersMiddleware,
    create_production_security_middleware
)

# Re-export for compatibility
__all__ = [
    "SecurityHeadersMiddleware",
    "create_production_security_middleware"
]