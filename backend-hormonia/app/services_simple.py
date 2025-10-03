"""
Simplified Service Container for the Hormonia Backend System.

This is a production-ready, simplified version that removes complex thread safety
mechanisms in favor of straightforward dependency injection. Designed to fix
the "Service provider initialization error" in production.

Key changes:
- Direct database session usage without complex context variables
- Synchronous Redis client to avoid async/sync conflicts
- Simple service instantiation without lazy loading complexity
- Comprehensive error handling with fallback mechanisms
- Minimal dependencies to reduce initialization failure points
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import redis
from contextlib import contextmanager

# Import only essential services to avoid circular dependencies
from app.services.auth import AuthService
from app.repositories.user import UserRepository
from app.config import settings

logger = logging.getLogger(__name__)


class SimplifiedServiceProvider:
    """
    Simplified service provider with direct dependency injection.
    
    This class removes complex thread safety mechanisms in favor of
    simple, direct service instantiation. Designed for production stability.
    """
    
    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        """
        Initialize simplified service provider.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Optional Redis client (sync)
        """
        self.db = db
        self.redis_client = redis_client
        self._initialized = False
        self._services: Dict[str, Any] = {}
        
        # Initialize essential services immediately
        try:
            self._initialize_core_services()
            self._initialized = True
            logger.info(f"SimplifiedServiceProvider initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SimplifiedServiceProvider: {e}")
            # Don't raise - allow fallback mechanisms to work
            self._initialized = False
    
    def _initialize_core_services(self):
        """Initialize essential services required for authentication."""
        try:
            # Create user repository
            self._services['user_repository'] = UserRepository(self.db)
            
            # Create auth service with fallback for missing Redis
            self._services['auth_service'] = AuthService(
                db=self.db,
                user_repository=self._services['user_repository'],
                redis_client=self.redis_client  # Can be None - AuthService should handle it
            )
            
            logger.debug("Core services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize core services: {e}")
            raise
    
    @property
    def is_initialized(self) -> bool:
        """Check if service provider was initialized successfully."""
        return self._initialized
    
    @property
    def auth_service(self) -> AuthService:
        """Get auth service with error handling."""
        if not self._initialized:
            raise RuntimeError("Service provider not properly initialized")
        
        if 'auth_service' not in self._services:
            raise RuntimeError("Auth service not available")
        
        return self._services['auth_service']
    
    @property
    def user_repository(self) -> UserRepository:
        """Get user repository with error handling."""
        if not self._initialized:
            raise RuntimeError("Service provider not properly initialized")
        
        if 'user_repository' not in self._services:
            raise RuntimeError("User repository not available")
        
        return self._services['user_repository']
    
    def validate_session(self):
        """Validate database session is active."""
        if not hasattr(self.db, 'is_active'):
            # Fallback check
            try:
                self.db.execute("SELECT 1")
            except Exception as e:
                raise RuntimeError(f"Database session validation failed: {e}")
        elif not self.db.is_active:
            raise RuntimeError("Database session is not active")


def create_redis_client() -> Optional[redis.Redis]:
    """
    Create a synchronous Redis client with proper error handling.
    
    Returns:
        Optional[redis.Redis]: Redis client or None if unavailable
    """
    try:
        if not hasattr(settings, 'REDIS_URL') or not settings.REDIS_URL:
            logger.warning("Redis URL not configured - Redis features disabled")
            return None
        
        # Create synchronous Redis client
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],
            retry_on_timeout=True
        )
        
        # Test connection
        client.ping()
        logger.info("Redis client created and connected successfully")
        return client
        
    except Exception as e:
        logger.warning(f"Failed to create Redis client: {e} - Redis features disabled")
        return None


@contextmanager
def get_simple_service_provider(db: Session):
    """
    Context manager for simplified service provider.
    
    Args:
        db: Database session
        
    Yields:
        SimplifiedServiceProvider: Service provider instance
    """
    redis_client = None
    provider = None
    
    try:
        # Create Redis client (can fail gracefully)
        redis_client = create_redis_client()
        
        # Create service provider
        provider = SimplifiedServiceProvider(db, redis_client)
        
        if not provider.is_initialized:
            raise RuntimeError("Failed to initialize service provider")
        
        yield provider
        
    except Exception as e:
        logger.error(f"Error in simple service provider context: {e}")
        raise
    finally:
        # Cleanup Redis connection if needed
        if redis_client:
            try:
                redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")


def create_simple_service_provider_dependency():
    """
    Create a FastAPI dependency for the simplified service provider.
    
    Returns:
        Callable: FastAPI dependency function
    """
    def get_simple_provider(db: Session) -> SimplifiedServiceProvider:
        """FastAPI dependency for simplified service provider."""
        try:
            # Create Redis client
            redis_client = create_redis_client()
            
            # Create and validate service provider
            provider = SimplifiedServiceProvider(db, redis_client)
            
            if not provider.is_initialized:
                logger.error("Service provider failed to initialize")
                raise RuntimeError("Service provider initialization failed")
            
            return provider
            
        except Exception as e:
            logger.error(f"Failed to create service provider: {e}")
            raise RuntimeError(f"Service provider creation failed: {e}")
    
    return get_simple_provider
