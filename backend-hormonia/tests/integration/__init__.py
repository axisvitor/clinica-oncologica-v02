"""
Integration Tests Module

This module contains integration tests that use real database connections,
real Firebase authentication, and real saga patterns WITHOUT mocking.

WARNING: These tests commit real data to the database and require cleanup.
They should NOT be run in CI by default.

Run with: pytest -m integration
Skip with: pytest -m "not integration"
"""

__all__ = []
