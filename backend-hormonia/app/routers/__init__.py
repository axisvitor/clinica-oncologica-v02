"""
App Routers - legacy compatibility package

This package intentionally keeps only compatibility-safe routers:
- auth_session: Session-based authentication with Firebase + Redis
- health: basic readiness/liveness endpoints
"""

# Empty __init__.py to make this a valid Python package
# Modules are imported directly in router_registry.py to avoid circular imports
