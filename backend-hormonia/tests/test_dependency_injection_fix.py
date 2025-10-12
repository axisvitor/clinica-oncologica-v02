"""
Unit tests for the critical dependency injection fix.

This module tests that the _ThreadSafeProviderDependency fix properly yields
ServiceProvider instances instead of returning generator objects.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Generator
import sys
import os

# Add the app directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.dependencies.service_dependencies import _ThreadSafeProviderDependency


class TestDependencyInjectionFix:
    """Test suite for the dependency injection generator fix."""

    def test_di_returns_generator_not_provider_directly(self):
        """Test that DI dependency returns a generator, not the provider directly."""
        provider_dep = _ThreadSafeProviderDependency()
        
        # Mock the get_thread_safe_service_provider to avoid full app initialization
        with patch('app.dependencies.get_thread_safe_service_provider') as mock_get_provider:
            # Create a mock provider with expected service attributes
            mock_provider = Mock()
            mock_provider.monthly_quiz_service = Mock()
            mock_provider.quiz_service = Mock()
            mock_provider.patient_service = Mock()
            mock_provider.auth_service = Mock()
            
            # Make the mock function return a generator that yields the provider
            def mock_generator():
                yield mock_provider
            
            mock_get_provider.return_value = mock_generator()
            
            # Call the dependency
            result = provider_dep()
            
            # Verify that the result is a generator
            assert hasattr(result, '__next__'), "provider_dep() should return a generator"
            assert hasattr(result, '__iter__'), "provider_dep() should return an iterable"
            
            # Verify we can get the provider from the generator
            provider = next(result)
            
            # Verify the provider has expected service attributes
            assert hasattr(provider, 'monthly_quiz_service'), "Provider should have monthly_quiz_service"
            assert hasattr(provider, 'quiz_service'), "Provider should have quiz_service"
            assert hasattr(provider, 'patient_service'), "Provider should have patient_service"
            assert hasattr(provider, 'auth_service'), "Provider should have auth_service"
            
            # Most importantly, verify the provider is NOT a generator
            assert not hasattr(provider, '__next__'), "Provider should not be a generator object"

    def test_di_uses_yield_from_not_return(self):
        """Test that the dependency uses yield from instead of return."""
        provider_dep = _ThreadSafeProviderDependency()
        
        with patch('app.dependencies.get_thread_safe_service_provider') as mock_get_provider:
            # Create a mock generator that yields multiple values to test yield from behavior
            provider1 = Mock()
            provider1.name = "provider1"
            provider2 = Mock()
            provider2.name = "provider2"
            
            def mock_generator():
                yield provider1
                yield provider2
            
            mock_get_provider.return_value = mock_generator()
            
            # Call the dependency and collect all yielded values
            result = provider_dep()
            providers = list(result)
            
            # If using yield from correctly, we should get all providers from the underlying generator
            assert len(providers) == 2, "Should yield all providers from underlying generator"
            assert providers[0].name == "provider1"
            assert providers[1].name == "provider2"

    def test_di_handles_generator_properly_for_fastapi(self):
        """Test that the dependency works correctly with FastAPI's dependency injection pattern."""
        provider_dep = _ThreadSafeProviderDependency()
        
        with patch('app.dependencies.get_thread_safe_service_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_provider.monthly_quiz_service = Mock()
            mock_provider.quiz_service = Mock()
            
            def mock_generator():
                yield mock_provider
            
            mock_get_provider.return_value = mock_generator()
            
            # Simulate how FastAPI would use the dependency
            dependency_generator = provider_dep()
            
            # FastAPI calls next() to get the dependency value
            provider_instance = next(dependency_generator)
            
            # Verify the provider instance is usable (not a generator)
            assert provider_instance is mock_provider
            assert hasattr(provider_instance, 'monthly_quiz_service')
            assert hasattr(provider_instance, 'quiz_service')
            
            # Verify it's not a generator (which was the original bug)
            assert not hasattr(provider_instance, '__next__')

    def test_di_lazy_import_works(self):
        """Test that the lazy import mechanism works correctly."""
        provider_dep = _ThreadSafeProviderDependency()
        
        # Verify that the import happens at call time, not at class creation time
        with patch('app.dependencies.get_thread_safe_service_provider') as mock_get_provider:
            mock_provider = Mock()
            
            def mock_generator():
                yield mock_provider
            
            mock_get_provider.return_value = mock_generator()
            
            # The import should happen when we call the dependency
            result = provider_dep()
            next(result)  # Consume the generator
            
            # Verify the function was imported and called
            mock_get_provider.assert_called_once()

    def test_business_dependencies_also_fixed(self):
        """Test that the same fix was applied to business_dependencies.py."""
        from app.dependencies.business_dependencies import _ThreadSafeProviderDependency as BusinessProviderDep
        
        business_provider_dep = BusinessProviderDep()
        
        with patch('app.dependencies.get_thread_safe_service_provider') as mock_get_provider:
            mock_provider = Mock()
            
            def mock_generator():
                yield mock_provider
            
            mock_get_provider.return_value = mock_generator()
            
            # Call the business dependency
            result = business_provider_dep()
            
            # Verify it also returns a generator (not the provider directly)
            assert hasattr(result, '__next__'), "Business dependency should also return a generator"
            
            # Verify we can get the provider
            provider = next(result)
            assert provider is mock_provider
            assert not hasattr(provider, '__next__'), "Provider should not be a generator"


class TestDependencyInjectionIntegration:
    """Integration tests for dependency injection in middleware chains."""

    def test_middleware_receives_proper_service_instances(self):
        """Test that middleware chains receive proper service instances."""
        # This is a conceptual test - in practice, middleware would use the dependency
        # through FastAPI's dependency injection system
        
        provider_dep = _ThreadSafeProviderDependency()
        
        with patch('app.dependencies.get_thread_safe_service_provider') as mock_get_provider:
            # Create a realistic mock provider
            mock_provider = Mock()
            mock_provider.monthly_quiz_service = Mock()
            mock_provider.quiz_service = Mock()
            mock_provider.patient_service = Mock()
            mock_provider.auth_service = Mock()
            mock_provider.analytics_service = Mock()
            
            def mock_generator():
                yield mock_provider
            
            mock_get_provider.return_value = mock_generator()
            
            # Simulate middleware getting the provider through dependency injection
            dependency_result = provider_dep()
            service_provider = next(dependency_result)
            
            # Verify middleware can access all expected services
            assert service_provider.monthly_quiz_service is not None
            assert service_provider.quiz_service is not None
            assert service_provider.patient_service is not None
            assert service_provider.auth_service is not None
            assert service_provider.analytics_service is not None
            
            # Verify these are actual service objects, not generators
            for service_name in ['monthly_quiz_service', 'quiz_service', 'patient_service', 'auth_service', 'analytics_service']:
                service = getattr(service_provider, service_name)
                assert not hasattr(service, '__next__'), f"{service_name} should not be a generator"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])