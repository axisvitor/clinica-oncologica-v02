"""
Thread-safe service container with request-scoped dependencies.
Replaces the problematic ServiceProvider with proper dependency injection.
"""
from typing import Dict, Any, Optional, Callable
from sqlalchemy.orm import Session
from functools import lru_cache
import logging
from contextlib import contextmanager

from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Thread-safe service container that creates fresh services per request.

    Key improvements:
    1. No shared state between requests
    2. Fresh database sessions per request
    3. Proper resource cleanup
    4. Thread-safe service instantiation
    """

    def __init__(self, db: Session, redis_client=None):
        """Initialize container with request-scoped dependencies."""
        self._db = db
        self._redis_client = redis_client
        self._services_cache: Dict[str, Any] = {}
        self._logger = logger

    @contextmanager
    def get_db_session(self):
        """Context manager for database session with proper cleanup."""
        try:
            yield self._db
        except Exception as e:
            self._db.rollback()
            self._logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            # Session cleanup handled by FastAPI dependency system
            pass

    # Repository factories (thread-safe, per-request instances)
    def get_user_repository(self):
        """Get fresh UserRepository instance."""
        if 'user_repository' not in self._services_cache:
            from app.repositories.user import UserRepository
            self._services_cache['user_repository'] = UserRepository(self._db)
        return self._services_cache['user_repository']

    def get_patient_repository(self):
        """Get fresh PatientRepository instance."""
        if 'patient_repository' not in self._services_cache:
            from app.repositories.patient import PatientRepository
            self._services_cache['patient_repository'] = PatientRepository(self._db)
        return self._services_cache['patient_repository']

    def get_quiz_repository(self):
        """Get fresh QuizRepository instance."""
        if 'quiz_repository' not in self._services_cache:
            from app.repositories.quiz import QuizRepository
            self._services_cache['quiz_repository'] = QuizRepository(self._db)
        return self._services_cache['quiz_repository']

    # Service factories (thread-safe, dependency-injected)
    def get_auth_service(self):
        """Get AuthService with fresh dependencies."""
        if 'auth_service' not in self._services_cache:
            from app.services.auth import AuthService
            self._services_cache['auth_service'] = AuthService(
                db=self._db,
                user_repository=self.get_user_repository(),
                redis_client=self._redis_client
            )
        return self._services_cache['auth_service']

    def get_patient_service(self):
        """Get PatientService with fresh dependencies."""
        if 'patient_service' not in self._services_cache:
            from app.services.patient import PatientService, PatientIntegrityService

            # Create integrity service first
            integrity_service = PatientIntegrityService(
                db=self._db,
                patient_repository=self.get_patient_repository()
            )

            self._services_cache['patient_service'] = PatientService(
                db=self._db,
                patient_repository=self.get_patient_repository(),
                integrity_service=integrity_service,
                flow_engine=self.get_flow_engine()
            )
        return self._services_cache['patient_service']

    def get_flow_engine(self):
        """Get FlowEngine with fresh database session."""
        if 'flow_engine' not in self._services_cache:
            from app.services.flow_engine_v2 import FlowEngineV2  # New thread-safe version
            self._services_cache['flow_engine'] = FlowEngineV2(self._db)
        return self._services_cache['flow_engine']

    def get_quiz_service(self):
        """Get QuizService with fresh dependencies."""
        if 'quiz_service' not in self._services_cache:
            from app.services.quiz import QuizService
            self._services_cache['quiz_service'] = QuizService(
                db=self._db,
                quiz_repository=self.get_quiz_repository(),
                flow_engine=self.get_flow_engine()
            )
        return self._services_cache['quiz_service']

    def get_message_service(self):
        """Get MessageService with fresh dependencies."""
        if 'message_service' not in self._services_cache:
            from app.services.message import MessageService
            self._services_cache['message_service'] = MessageService(self._db)
        return self._services_cache['message_service']

    def get_flow_integration_service(self):
        """Get consolidated FlowIntegrationService."""
        if 'flow_integration_service' not in self._services_cache:
            from app.services.flow_integration_v2 import FlowIntegrationServiceV2  # Consolidated version
            self._services_cache['flow_integration_service'] = FlowIntegrationServiceV2(
                db=self._db,
                flow_engine=self.get_flow_engine(),
                message_service=self.get_message_service()
            )
        return self._services_cache['flow_integration_service']

    def get_monthly_quiz_service(self):
        """Get MonthlyQuizService with fresh dependencies."""
        if 'monthly_quiz_service' not in self._services_cache:
            from app.services.monthly_quiz_service import MonthlyQuizService
            self._services_cache['monthly_quiz_service'] = MonthlyQuizService(self._db)
        return self._services_cache['monthly_quiz_service']

    def cleanup(self):
        """Clean up resources (called by FastAPI dependency system)."""
        try:
            # Clear service cache to prevent memory leaks
            self._services_cache.clear()
            self._logger.debug("Service container cleaned up")
        except Exception as e:
            self._logger.error(f"Error during service container cleanup: {e}")


# Request-scoped container factory
def get_service_container(
    db: Session = None,  # Will be injected by FastAPI dependency
    redis_client=None   # Will be injected by FastAPI dependency
) -> ServiceContainer:
    """
    Factory for creating request-scoped service container.

    This replaces the problematic ServiceProvider pattern with
    proper request-scoped dependency injection.
    """
    return ServiceContainer(db=db, redis_client=redis_client)