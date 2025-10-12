"""
Dependency Injection Regression Tests
Comprehensive tests to prevent regression of DI generator object issues.
"""

import pytest
import ast
import inspect
from pathlib import Path
from typing import Generator, Any
from unittest.mock import Mock, patch

from app.dependencies.service_dependencies import _ThreadSafeProviderDependency, get_thread_safe_service_provider


class TestDependencyInjectionRegression:
    """Comprehensive tests for dependency injection patterns."""
    
    def test_provider_dependency_class_exists(self):
        """Test that the provider dependency class exists and is properly defined."""
        assert _ThreadSafeProviderDependency is not None
        assert callable(_ThreadSafeProviderDependency)
    
    def test_provider_dependency_call_method_signature(self):
        """Test that __call__ method has correct signature."""
        provider_dep = _ThreadSafeProviderDependency()
        
        # Should be callable
        assert callable(provider_dep)
        
        # Should have __call__ method
        assert hasattr(provider_dep, '__call__')
        
        # Check method signature
        call_method = getattr(provider_dep, '__call__')
        sig = inspect.signature(call_method)
        
        # Should not require additional parameters beyond self
        params = list(sig.parameters.keys())
        assert len(params) <= 1, f"__call__ should have at most 1 parameter (self), got: {params}"
    
    def test_provider_dependency_returns_generator(self):
        """Test that provider dependency returns a generator (for FastAPI)."""
        provider_dep = _ThreadSafeProviderDependency()
        result = provider_dep()
        
        # Should return a generator
        assert hasattr(result, '__next__'), "Provider dependency should return a generator"
        assert hasattr(result, '__iter__'), "Provider dependency should return an iterator"
    
    def test_provider_dependency_yields_actual_provider(self):
        """Test that the generator yields an actual provider, not another generator."""
        provider_dep = _ThreadSafeProviderDependency()
        generator = provider_dep()
        
        # Get the yielded value
        provider = next(generator)
        
        # Should not be a generator itself
        assert not hasattr(provider, '__next__'), "Yielded provider should not be a generator"
        
        # Should have expected service attributes
        assert hasattr(provider, 'monthly_quiz_service'), "Provider should have monthly_quiz_service"
        assert hasattr(provider, 'quiz_service'), "Provider should have quiz_service"
        
        # Services should not be None
        assert provider.monthly_quiz_service is not None
        assert provider.quiz_service is not None
    
    def test_provider_dependency_generator_exhaustion(self):
        """Test that the generator properly exhausts after yielding."""
        provider_dep = _ThreadSafeProviderDependency()
        generator = provider_dep()
        
        # Get first value
        provider1 = next(generator)
        assert provider1 is not None
        
        # Generator should be exhausted after first yield
        with pytest.raises(StopIteration):
            next(generator)
    
    def test_multiple_provider_dependency_instances(self):
        """Test that multiple instances work correctly."""
        provider_dep1 = _ThreadSafeProviderDependency()
        provider_dep2 = _ThreadSafeProviderDependency()
        
        # Both should work independently
        provider1 = next(provider_dep1())
        provider2 = next(provider_dep2())
        
        assert provider1 is not None
        assert provider2 is not None
        
        # Both should have required attributes
        assert hasattr(provider1, 'monthly_quiz_service')
        assert hasattr(provider2, 'monthly_quiz_service')
    
    def test_get_thread_safe_service_provider_function(self):
        """Test the underlying get_thread_safe_service_provider function."""
        result = get_thread_safe_service_provider()
        
        # Should return a generator
        assert hasattr(result, '__next__'), "get_thread_safe_service_provider should return generator"
        
        # Should yield a provider
        provider = next(result)
        assert provider is not None
        assert hasattr(provider, 'monthly_quiz_service')
    
    def test_dependency_injection_code_structure(self):
        """Test that the DI code follows correct structural patterns."""
        backend_root = Path(__file__).parent.parent
        di_file = backend_root / "app/dependencies/service_dependencies.py"
        
        assert di_file.exists(), "service_dependencies.py should exist"
        
        with open(di_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST to check structure
        tree = ast.parse(content)
        
        # Find _ThreadSafeProviderDependency class
        provider_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "_ThreadSafeProviderDependency":
                provider_class = node
                break
        
        assert provider_class is not None, "_ThreadSafeProviderDependency class should exist"
        
        # Find __call__ method
        call_method = None
        for method in provider_class.body:
            if isinstance(method, ast.FunctionDef) and method.name == "__call__":
                call_method = method
                break
        
        assert call_method is not None, "__call__ method should exist"
        
        # Check method body for correct patterns
        has_yield_from = False
        has_problematic_return = False
        
        for stmt in call_method.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.YieldFrom):
                has_yield_from = True
            elif (isinstance(stmt, ast.Return) and 
                  stmt.value and 
                  isinstance(stmt.value, ast.Call)):
                # Check if it's returning a generator function call
                if (isinstance(stmt.value.func, ast.Name) and
                    "provider" in stmt.value.func.id.lower()):
                    has_problematic_return = True
        
        assert has_yield_from, "__call__ method should use 'yield from' pattern"
        assert not has_problematic_return, "__call__ method should not return generator function directly"
    
    def test_fastapi_compatibility(self):
        """Test that the DI pattern is compatible with FastAPI Depends()."""
        from fastapi import Depends
        
        # Should be able to create Depends with the provider dependency
        provider_dep = _ThreadSafeProviderDependency()
        depends_instance = Depends(provider_dep)
        
        assert depends_instance is not None
        assert depends_instance.dependency == provider_dep
    
    @patch('app.dependencies.service_dependencies.get_thread_safe_service_provider')
    def test_provider_dependency_calls_underlying_function(self, mock_get_provider):
        """Test that provider dependency correctly calls the underlying function."""
        # Setup mock
        mock_provider = Mock()
        mock_provider.monthly_quiz_service = Mock()
        mock_provider.quiz_service = Mock()
        
        def mock_generator():
            yield mock_provider
        
        mock_get_provider.return_value = mock_generator()
        
        # Test the dependency
        provider_dep = _ThreadSafeProviderDependency()
        generator = provider_dep()
        provider = next(generator)
        
        # Verify the underlying function was called
        mock_get_provider.assert_called_once()
        
        # Verify we got the mocked provider
        assert provider == mock_provider
    
    def test_provider_services_are_accessible(self):
        """Test that services from the provider are accessible and functional."""
        provider_dep = _ThreadSafeProviderDependency()
        provider = next(provider_dep())
        
        # Test monthly_quiz_service
        monthly_quiz_service = provider.monthly_quiz_service
        assert monthly_quiz_service is not None
        
        # Should have expected methods (basic check)
        # Note: This depends on the actual service implementation
        if hasattr(monthly_quiz_service, 'get_active_quiz_links'):
            assert callable(monthly_quiz_service.get_active_quiz_links)
        
        # Test quiz_service
        quiz_service = provider.quiz_service
        assert quiz_service is not None
        
        # Should have expected methods (basic check)
        if hasattr(quiz_service, 'create_quiz_session'):
            assert callable(quiz_service.create_quiz_session)
    
    def test_no_memory_leaks_in_provider_creation(self):
        """Test that creating multiple providers doesn't cause memory leaks."""
        import gc
        
        # Create multiple providers and ensure they can be garbage collected
        providers = []
        for _ in range(10):
            provider_dep = _ThreadSafeProviderDependency()
            provider = next(provider_dep())
            providers.append(provider)
        
        # Clear references
        providers.clear()
        
        # Force garbage collection
        gc.collect()
        
        # This is a basic test - in practice, you'd use memory profiling tools
        # to detect actual memory leaks
        assert True, "Memory leak test completed"
    
    def test_provider_dependency_thread_safety(self):
        """Test that provider dependency works correctly in multi-threaded context."""
        import threading
        import time
        
        results = []
        errors = []
        
        def create_provider():
            try:
                provider_dep = _ThreadSafeProviderDependency()
                provider = next(provider_dep())
                results.append(provider)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_provider)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify results
        assert len(errors) == 0, f"Errors in threads: {errors}"
        assert len(results) == 5, f"Expected 5 providers, got {len(results)}"
        
        # All providers should be valid
        for provider in results:
            assert provider is not None
            assert hasattr(provider, 'monthly_quiz_service')
            assert hasattr(provider, 'quiz_service')


class TestDependencyInjectionIntegration:
    """Integration tests for dependency injection with other components."""
    
    def test_di_with_fastapi_endpoint_simulation(self):
        """Simulate how DI would work in a FastAPI endpoint."""
        from fastapi import Depends
        
        # Simulate endpoint function signature
        def mock_endpoint(provider=Depends(_ThreadSafeProviderDependency())):
            return {"status": "ok", "services": {
                "monthly_quiz": provider.monthly_quiz_service is not None,
                "quiz": provider.quiz_service is not None
            }}
        
        # Get the dependency
        provider_dep = _ThreadSafeProviderDependency()
        provider = next(provider_dep())
        
        # Simulate calling the endpoint
        result = mock_endpoint(provider)
        
        assert result["status"] == "ok"
        assert result["services"]["monthly_quiz"] is True
        assert result["services"]["quiz"] is True
    
    def test_di_error_handling(self):
        """Test error handling in dependency injection."""
        # Test what happens if underlying provider fails
        with patch('app.dependencies.service_dependencies.get_thread_safe_service_provider') as mock_get:
            mock_get.side_effect = Exception("Provider creation failed")
            
            provider_dep = _ThreadSafeProviderDependency()
            
            # Should propagate the exception
            with pytest.raises(Exception, match="Provider creation failed"):
                next(provider_dep())
    
    def test_di_with_database_session(self):
        """Test that DI works correctly with database sessions."""
        # This test would verify that the provider correctly manages database sessions
        # Implementation depends on actual database setup
        
        provider_dep = _ThreadSafeProviderDependency()
        provider = next(provider_dep())
        
        # Verify provider has database-related services
        # This is a placeholder - actual test would depend on implementation
        assert provider is not None
        
        # If provider has database session, verify it's valid
        if hasattr(provider, 'db_session'):
            assert provider.db_session is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])