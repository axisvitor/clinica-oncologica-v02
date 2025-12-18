"""
Request logging middleware module.

This module provides a wrapper/alias for the RequestLoggingMiddleware
to maintain compatibility with test imports while keeping the actual
implementation in enhanced_middleware.py.
"""

from .enhanced_middleware import RequestLoggingMiddleware

# Re-export for compatibility
__all__ = ["RequestLoggingMiddleware"]
