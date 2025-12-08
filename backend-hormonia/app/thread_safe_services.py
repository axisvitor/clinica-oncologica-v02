"""
Thread-Safe Service Container for the Hormonia Backend System.
Implements proper thread safety for multi-worker FastAPI production deployment.

Features:
- Thread-safe lazy initialization with RLock
- Per-thread service caching to prevent race conditions
- Connection pooling support for database sessions
- Redis client configured for concurrent access
- Proper cleanup and resource management
- Singleton pattern with thread safety
"""

import threading
import weakref
from contextlib import contextmanager
from typing import Dict, Any, Optional, Callable
from sqlalchemy.orm import Session
import logging

from app.services.auth import AuthService
from app.services.patient import PatientService, PatientIntegrityService
from app.services.quiz import QuizService
from app.services.reporting import ReportService
from app.services.analytics import AnalyticsService
from app.domain.messaging.core import MessageService
from app.domain.flows.core import FlowService
from app.services.flow_engine import FlowEngine
from app.services.notification import NotificationService
from app.services.file import FileService
from app.domain.quizzes import MonthlyQuizService
from app.services.metrics_collector import MetricsCollectorService
from app.services.metrics_redis_storage import MetricsRedisStorage

# Import repositories
from app.repositories.user import UserRepository
from app.repositories.patient import PatientRepository
from app.repositories.quiz import QuizRepository

logger = logging.getLogger(__name__)


class ThreadSafeServiceProvider:
    """
    Thread-safe service provider for multi-worker FastAPI deployment.

    Features:
    - Thread-safe lazy initialization with RLock
    - Per-thread service caching to prevent race conditions
    - Connection pooling support for database sessions
    - Redis client configured for concurrent access
    - Proper cleanup and resource management
    - Singleton pattern with thread safety
    """

    # Class-level locks for thread safety
    _instance_lock = threading.RLock()
    _instances: Dict[int, 'ThreadSafeServiceProvider'] = {}
    _local_data = threading.local()

    def __init__(self, db_session_factory: Callable[[], Session], redis_client):
        """
        Initialize thread-safe service provider.

        Args:
            db_session_factory: Callable that returns a new DB session
            redis_client: Redis client configured for concurrent access
        """
        self.db_session_factory = db_session_factory
        self.redis_client = redis_client
        self._thread_id = threading.get_ident()

        # Thread-safe service cache with RLock
        self._service_cache_lock = threading.RLock()
        self._service_cache: Dict[str, Any] = {}

        # Repository cache lock
        self._repository_cache_lock = threading.RLock()
        self._repository_cache: Dict[str, Any] = {}

        logger.info(f"ServiceProvider initialized for thread {self._thread_id}")

    @classmethod
    def get_instance(cls, db_session_factory=None, redis_client=None) -> 'ThreadSafeServiceProvider':
        """
        Get or create thread-safe singleton instance.

        Returns a unique ServiceProvider instance per thread to avoid
        race conditions while maintaining singleton behavior within threads.
        """
        thread_id = threading.get_ident()

        with cls._instance_lock:
            if thread_id not in cls._instances:
                if db_session_factory is None or redis_client is None:
                    raise ValueError("db_session_factory and redis_client required for new instance")

                instance = cls(db_session_factory, redis_client)
                cls._instances[thread_id] = instance
                logger.info(f"Created new ServiceProvider instance for thread {thread_id}")

            return cls._instances[thread_id]

    @contextmanager
    def get_db_session(self):
        """
        Get database session with proper cleanup.
        Thread-safe session management.
        """
        session = None
        try:
            session = self.db_session_factory()
            yield session
        except Exception as e:
            if session:
                session.rollback()
            raise e
        finally:
            if session:
                session.close()

    def _get_or_create_service(self, service_name: str, factory_func):
        """
        Thread-safe service creation and caching.

        Args:
            service_name: Unique name for the service
            factory_func: Function to create the service instance

        Returns:
            Service instance (cached or newly created)
        """
        with self._service_cache_lock:
            if service_name not in self._service_cache:
                try:
                    logger.debug(f"Creating service '{service_name}' for thread {self._thread_id}")
                    self._service_cache[service_name] = factory_func()
                    logger.debug(f"Service '{service_name}' created successfully")
                except Exception as e:
                    logger.error(f"Failed to create service '{service_name}': {e}")
                    raise

            return self._service_cache[service_name]

    def _get_or_create_repository(self, repo_name: str, factory_func):
        """
        Thread-safe repository creation and caching.

        Args:
            repo_name: Unique name for the repository
            factory_func: Function to create the repository instance

        Returns:
            Repository instance (cached or newly created)
        """
        with self._repository_cache_lock:
            if repo_name not in self._repository_cache:
                try:
                    logger.debug(f"Creating repository '{repo_name}' for thread {self._thread_id}")
                    # Create repository with session factory for thread safety
                    self._repository_cache[repo_name] = factory_func()
                    logger.debug(f"Repository '{repo_name}' created successfully")
                except Exception as e:
                    logger.error(f"Failed to create repository '{repo_name}': {e}")
                    raise

            return self._repository_cache[repo_name]

    # Thread-safe repository properties
    @property
    def user_repository(self) -> UserRepository:
        return self._get_or_create_repository(
            'user_repository',
            lambda: UserRepositoryWrapper(self.db_session_factory)
        )

    @property
    def patient_repository(self) -> PatientRepository:
        return self._get_or_create_repository(
            'patient_repository',
            lambda: PatientRepositoryWrapper(self.db_session_factory)
        )

    @property
    def quiz_repository(self) -> QuizRepository:
        return self._get_or_create_repository(
            'quiz_repository',
            lambda: QuizRepositoryWrapper(self.db_session_factory)
        )

    # Thread-safe service properties with proper dependencies
    @property
    def auth_service(self) -> AuthService:
        return self._get_or_create_service(
            'auth_service',
            lambda: self._create_auth_service()
        )

    def _create_auth_service(self) -> AuthService:
        """Create AuthService with proper session management."""
        try:
            # Try new constructor pattern with session factory
            return AuthService(
                db_session_factory=self.db_session_factory,
                user_repository=self.user_repository,
                redis_client=self.redis_client
            )
        except TypeError:
            # Fallback to original constructor for backward compatibility
            with self.get_db_session() as session:
                return AuthService(
                    db=session,
                    user_repository=self.user_repository,
                    redis_client=self.redis_client
                )

    @property
    def flow_engine(self) -> EnhancedFlowEngine:
        return self._get_or_create_service(
            'flow_engine',
            lambda: self._create_flow_engine()
        )

    def _create_flow_engine(self) -> EnhancedFlowEngine:
        """Create FlowEngine with proper session management."""
        try:
            # Try new constructor pattern
            return EnhancedFlowEngine(db=self.db_session_factory())
        except TypeError:
            # Fallback to original constructor
            with self.get_db_session() as session:
                return EnhancedFlowEngine(db=session)

    @property
    def patient_integrity_service(self) -> PatientIntegrityService:
        return self._get_or_create_service(
            'patient_integrity_service',
            lambda: self._create_patient_integrity_service()
        )

    def _create_patient_integrity_service(self) -> PatientIntegrityService:
        """Create PatientIntegrityService with proper session management."""
        try:
            # Try new constructor pattern
            return PatientIntegrityService(
                db_session_factory=self.db_session_factory,
                patient_repository=self.patient_repository
            )
        except TypeError:
            # Fallback to original constructor
            with self.get_db_session() as session:
                return PatientIntegrityService(
                    db=session,
                    patient_repository=self.patient_repository
                )

    @property
    def quiz_service(self) -> QuizService:
        return self._get_or_create_service(
            'quiz_service',
            lambda: self._create_quiz_service()
        )

    def _create_quiz_service(self) -> QuizService:
        """Create QuizService with proper error handling for different constructors."""
        try:
            # Try with repository and flow engine
            return QuizService(
                db_session_factory=self.db_session_factory,
                quiz_repository=self.quiz_repository,
                flow_engine=self.flow_engine
            )
        except TypeError:
            try:
                # Try with session factory only
                return QuizService(db_session_factory=self.db_session_factory)
            except TypeError:
                # Fallback to original constructor
                with self.get_db_session() as session:
                    return QuizService(db=session)

    @property
    def report_service(self) -> ReportService:
        return self._get_or_create_service(
            'report_service',
            lambda: self._create_basic_service(ReportService)
        )

    @property
    def analytics_service(self) -> AnalyticsService:
        return self._get_or_create_service(
            'analytics_service',
            lambda: self._create_basic_service(AnalyticsService)
        )

    @property
    def message_service(self) -> MessageService:
        return self._get_or_create_service(
            'message_service',
            lambda: self._create_basic_service(MessageService)
        )

    @property
    def flow_service(self) -> FlowService:
        return self._get_or_create_service(
            'flow_service',
            lambda: self._create_basic_service(FlowService)
        )

    @property
    def notification_service(self) -> NotificationService:
        return self._get_or_create_service(
            'notification_service',
            lambda: self._create_basic_service(NotificationService)
        )

    @property
    def file_service(self) -> FileService:
        return self._get_or_create_service(
            'file_service',
            lambda: FileService()
        )

    @property
    def monthly_quiz_service(self) -> MonthlyQuizService:
        return self._get_or_create_service(
            'monthly_quiz_service',
            lambda: self._create_basic_service(MonthlyQuizService)
        )

    @property
    def metrics_collector_service(self) -> MetricsCollectorService:
        return self._get_or_create_service(
            'metrics_collector_service',
            lambda: self._create_metrics_collector_service()
        )

    def _create_metrics_collector_service(self) -> MetricsCollectorService:
        """Create MetricsCollectorService with proper session management."""
        try:
            # Try new constructor pattern
            return MetricsCollectorService(
                db_session_factory=self.db_session_factory,
                redis_client=self.redis_client
            )
        except TypeError:
            # Fallback to original constructor
            with self.get_db_session() as session:
                return MetricsCollectorService(db=session, redis_client=self.redis_client)

    @property
    def metrics_redis_storage(self) -> MetricsRedisStorage:
        return self._get_or_create_service(
            'metrics_redis_storage',
            lambda: MetricsRedisStorage(self.redis_client)
        )

    def _create_basic_service(self, service_class):
        """Create service with basic session management pattern."""
        try:
            # Try new constructor pattern with session factory
            return service_class(db_session_factory=self.db_session_factory)
        except TypeError:
            # Fallback to original constructor with single session
            with self.get_db_session() as session:
                return service_class(db=session)

    def cleanup(self):
        """
        Clean up resources and caches.
        Should be called when shutting down or switching threads.
        """
        thread_id = threading.get_ident()
        logger.info(f"Cleaning up ServiceProvider for thread {thread_id}")

        with self._service_cache_lock:
            # Close any services that have cleanup methods
            for service_name, service in self._service_cache.items():
                if hasattr(service, 'cleanup'):
                    try:
                        service.cleanup()
                        logger.debug(f"Cleaned up service '{service_name}'")
                    except Exception as e:
                        logger.error(f"Error cleaning up service '{service_name}': {e}")

            self._service_cache.clear()

        with self._repository_cache_lock:
            self._repository_cache.clear()

        # Remove from instances cache
        with self._instance_lock:
            if thread_id in self._instances:
                del self._instances[thread_id]
                logger.info(f"Removed ServiceProvider instance for thread {thread_id}")

    @classmethod
    def cleanup_all(cls):
        """Clean up all ServiceProvider instances across threads."""
        with cls._instance_lock:
            thread_ids = list(cls._instances.keys())
            for thread_id in thread_ids:
                try:
                    instance = cls._instances[thread_id]
                    instance.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up ServiceProvider for thread {thread_id}: {e}")

            cls._instances.clear()
            logger.info("All ServiceProvider instances cleaned up")


class RepositoryWrapper:
    """
    Base class for thread-safe repository wrappers.
    Manages database sessions per operation to ensure thread safety.
    """

    def __init__(self, db_session_factory: Callable[[], Session], repository_class):
        self.db_session_factory = db_session_factory
        self.repository_class = repository_class
        self._lock = threading.RLock()

    def _execute_with_session(self, operation, *args, **kwargs):
        """Execute repository operation with a fresh session."""
        with self.db_session_factory() as session:
            try:
                repo = self.repository_class(session)
                return operation(repo, *args, **kwargs)
            except Exception as e:
                session.rollback()
                raise e

    def __getattr__(self, name):
        """Proxy all method calls to the repository with session management."""
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        def method(*args, **kwargs):
            return self._execute_with_session(
                lambda repo, *a, **kw: getattr(repo, name)(*a, **kw),
                *args, **kwargs
            )

        return method


class UserRepositoryWrapper(RepositoryWrapper):
    """Thread-safe wrapper for UserRepository."""

    def __init__(self, db_session_factory):
        super().__init__(db_session_factory, UserRepository)


class PatientRepositoryWrapper(RepositoryWrapper):
    """Thread-safe wrapper for PatientRepository."""

    def __init__(self, db_session_factory):
        super().__init__(db_session_factory, PatientRepository)


class QuizRepositoryWrapper(RepositoryWrapper):
    """Thread-safe wrapper for QuizRepository."""

    def __init__(self, db_session_factory):
        super().__init__(db_session_factory, QuizRepository)


def get_service_provider(request) -> ThreadSafeServiceProvider:
    """
    Get thread-safe service provider from FastAPI request.

    This function ensures that each worker/thread gets its own ServiceProvider
    instance to prevent race conditions in multi-worker deployments.
    """
    # Get the global service provider factory from app state
    if hasattr(request.app.state, 'service_provider_factory'):
        # Use factory to get thread-safe instance
        return request.app.state.service_provider_factory()

    # Fallback to legacy behavior for backward compatibility
    if hasattr(request.app.state, 'service_provider'):
        logger.warning("Using legacy non-thread-safe ServiceProvider. Consider upgrading to factory pattern.")
        return request.app.state.service_provider

    raise RuntimeError("ServiceProvider not initialized in app state")


def create_service_provider_factory(db_session_factory, redis_client):
    """
    Create a factory function for thread-safe ServiceProvider instances.

    Args:
        db_session_factory: Function that creates new database sessions
        redis_client: Redis client configured for concurrent access

    Returns:
        Factory function that returns thread-safe ServiceProvider instances
    """
    def factory() -> ThreadSafeServiceProvider:
        return ThreadSafeServiceProvider.get_instance(
            db_session_factory=db_session_factory,
            redis_client=redis_client
        )

    return factory


# Backward compatibility alias
ServiceProvider = ThreadSafeServiceProvider

# Legacy compatibility - use ThreadSafeServiceProvider by default
__all__ = [
    'ThreadSafeServiceProvider',
    'ServiceProvider',  # Alias for backward compatibility
    'get_service_provider',
    'create_service_provider_factory',
    'RepositoryWrapper',
    'UserRepositoryWrapper',
    'PatientRepositoryWrapper',
    'QuizRepositoryWrapper'
]