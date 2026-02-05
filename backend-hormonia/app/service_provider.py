"""
Thread-Safe Service Container for the Hormonia Backend System.

Implements proper thread safety for multi-worker FastAPI production deployment
using request-scoped sessions and stateless service instantiation.

This ServiceProvider is designed to be created per-request with its own
database session, ensuring thread safety and proper resource isolation.

IMPORTANT: All service imports are done lazily (inside property methods)
to avoid circular import issues with app/services/__init__.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Any
from sqlalchemy.orm import Session

# TYPE_CHECKING imports for type hints only (not executed at runtime)
if TYPE_CHECKING:
    from app.services.auth import AuthService
    from app.services.patient import PatientCRUDService, PatientIntegrityService
    from app.services.quiz import QuizService
    from app.services.reporting import ReportService
    from app.domain.analytics.analytics_service import AnalyticsService
    from app.domain.messaging.core import MessageService
    from app.services.flow import FlowManager
    from app.services.enhanced_flow_engine import EnhancedFlowEngine
    from app.services.notification_service import NotificationService
    from app.services.file import FileService
    from app.services.quiz.quiz_service import MonthlyQuizService
    from app.services.analytics.metrics_collector import MetricsCollectorService
    from app.services.analytics.metrics_redis_storage import MetricsRedisStorage
    from app.services.simple_session_service import SimpleSessionService
    from app.repositories.user import UserRepository
    from app.repositories.patient import PatientRepository
    from app.repositories.quiz import QuizRepository

logger = logging.getLogger(__name__)


class ServiceProvider:
    """
    Thread-safe service provider with proper dependency injection.

    This class is designed to be instantiated per-request with its own
    database session, ensuring thread safety and proper resource isolation.
    Services are lazily instantiated to improve performance and avoid
    circular imports.
    """

    def __init__(self, db: Session, redis_client: Optional[object] = None):
        """
        Initialize ServiceProvider with request-scoped database session.

        Args:
            db: SQLAlchemy database session for this request
            redis_client: Optional Redis client instance (sync, async, or compatibility wrapper)
        """
        self.db = db
        self.redis_client = redis_client
        self._request_id = id(db)  # Use session ID as request identifier

        # Detect Redis client type for better service initialization
        self._redis_client_type = self._detect_redis_client_type(redis_client)

        # Initialize repositories (lazy loading)
        self._user_repository: Optional[UserRepository] = None
        self._patient_repository: Optional[PatientRepository] = None
        self._quiz_repository: Optional[QuizRepository] = None

        # Initialize services (lazy loading)
        self._auth_service: Optional[AuthService] = None
        self._patient_service: Optional[PatientCRUDService] = None
        self._patient_integrity_service: Optional[PatientIntegrityService] = None
        self._quiz_service: Optional[QuizService] = None
        self._report_service: Optional[ReportService] = None
        self._analytics_service: Optional[AnalyticsService] = None
        self._message_service: Optional[MessageService] = None
        self._flow_engine: Optional[EnhancedFlowEngine] = None
        self._flow_service: Optional[FlowManager] = None
        self._notification_service: Optional[NotificationService] = None
        self._file_service: Optional[FileService] = None
        self._monthly_quiz_service: Optional[MonthlyQuizService] = None
        self._metrics_collector_service: Optional[MetricsCollectorService] = None
        self._metrics_redis_storage: Optional[MetricsRedisStorage] = None
        self._simple_session_service: Optional[SimpleSessionService] = None

        logger.debug(
            f"ServiceProvider initialized for request {self._request_id} with {self._redis_client_type} Redis client"
        )

    def __del__(self):
        """Cleanup logging when ServiceProvider is destroyed."""
        try:
            logger.debug(f"ServiceProvider destroyed for request {self._request_id}")
        except Exception:
            pass  # Avoid errors during cleanup (logger may be unavailable)

    def _detect_redis_client_type(self, redis_client: Any) -> str:
        """Detect the type of Redis client provided."""
        if redis_client is None:
            return "none"

        # Check for async Redis client
        if hasattr(redis_client, "__aenter__") or "asyncio" in str(type(redis_client)):
            return "async"

        # Check for compatibility wrapper
        if hasattr(redis_client, "redis_manager") or hasattr(
            redis_client, "_run_async"
        ):
            return "wrapper"

        # Check for sync Redis client
        if hasattr(redis_client, "ping") and not hasattr(redis_client, "__aenter__"):
            return "sync"

        return "unknown"

    def get_redis_client_for_service(self, service_name: str) -> Any:
        """
        Get appropriate Redis client for a specific service.

        Args:
            service_name: Name of the service requesting Redis client

        Returns:
            Redis client appropriate for the service
        """
        if self.redis_client is None:
            logger.warning(f"No Redis client available for service {service_name}")
            return None

        # Services that need async Redis
        async_services = {"metrics_redis_storage", "websocket_events"}

        # Services that need sync Redis
        sync_services = {"auth_service", "cache_service"}

        if service_name in async_services:
            # Return async client or wrapper
            if self._redis_client_type in ["async", "wrapper"]:
                return self.redis_client
            else:
                logger.warning(
                    f"Service {service_name} needs async Redis but got {self._redis_client_type}"
                )
                return self.redis_client

        elif service_name in sync_services:
            # Return sync-compatible client
            return self.redis_client

        else:
            # Default: return as-is
            return self.redis_client

    @property
    def is_session_active(self) -> bool:
        """Check if the database session is still active."""
        try:
            return self.db.is_active
        except Exception:
            return False

    def validate_session(self) -> None:
        """Validate that the database session is still usable."""
        if not self.is_session_active:
            logger.error(f"Session validation failed for request {self._request_id}")
            logger.error(f"Session object: {self.db}")
            logger.error(f"Session type: {type(self.db)}")

            # Try to get more information about the session state
            try:
                if hasattr(self.db, "_transaction"):
                    logger.error(f"Session transaction state: {self.db._transaction}")
                if hasattr(self.db, "connection"):
                    logger.error(f"Session connection state: {self.db.connection()}")
            except Exception as info_error:
                logger.error(f"Could not get session state info: {info_error}")

            raise RuntimeError(
                f"Database session for request {self._request_id} is no longer active. "
                "This may indicate a database connection issue or premature session closure."
            )

    # Repository properties - LAZY IMPORTS to avoid circular dependencies
    @property
    def user_repository(self) -> "UserRepository":
        if self._user_repository is None:
            from app.repositories.user import UserRepository
            self._user_repository = UserRepository(self.db)
        return self._user_repository

    @property
    def patient_repository(self) -> "PatientRepository":
        if self._patient_repository is None:
            from app.repositories.patient import PatientRepository
            self._patient_repository = PatientRepository(self.db)
        return self._patient_repository

    @property
    def quiz_repository(self) -> "QuizRepository":
        if self._quiz_repository is None:
            from app.repositories.quiz import QuizRepository
            self._quiz_repository = QuizRepository(self.db)
        return self._quiz_repository

    # Service properties with proper dependencies - LAZY IMPORTS
    @property
    def auth_service(self) -> "AuthService":
        if self._auth_service is None:
            from app.services.auth import AuthService
            # AuthService needs: db, UserRepository, RedisClient
            self._auth_service = AuthService(
                db=self.db,
                user_repository=self.user_repository,
                redis_client=self.redis_client,
            )
        return self._auth_service

    @property
    def flow_engine(self) -> "EnhancedFlowEngine":
        if self._flow_engine is None:
            from app.services.enhanced_flow_engine import EnhancedFlowEngine
            # FlowEngine needs db
            self._flow_engine = EnhancedFlowEngine(self.db)
        return self._flow_engine

    @property
    def patient_integrity_service(self) -> "PatientIntegrityService":
        if self._patient_integrity_service is None:
            from app.services.patient import PatientIntegrityService
            # PatientIntegrityService needs: db, PatientRepository
            self._patient_integrity_service = PatientIntegrityService(
                db=self.db, patient_repository=self.patient_repository
            )
        return self._patient_integrity_service

    @property
    def patient_service(self) -> "PatientCRUDService":
        if self._patient_service is None:
            from app.services.patient import PatientCRUDService
            # PatientService needs: db, repository
            self._patient_service = PatientCRUDService(
                db=self.db,
                repository=self.patient_repository,
            )
        return self._patient_service

    @property
    def quiz_service(self) -> "QuizService":
        if self._quiz_service is None:
            from app.services.quiz import QuizService
            # Assuming QuizService needs similar dependencies
            # Check the actual constructor requirements
            try:
                # Try with repository and flow engine
                self._quiz_service = QuizService(
                    db=self.db,
                    quiz_repository=self.quiz_repository,
                    flow_engine=self.flow_engine,
                )
            except TypeError:
                # Fallback to just db if that's all it needs
                self._quiz_service = QuizService(self.db)
        return self._quiz_service

    @property
    def report_service(self) -> "ReportService":
        if self._report_service is None:
            from app.services.reporting import ReportService
            self._report_service = ReportService(self.db)
        return self._report_service

    @property
    def analytics_service(self) -> "AnalyticsService":
        if self._analytics_service is None:
            from app.domain.analytics.analytics_service import AnalyticsService
            self._analytics_service = AnalyticsService(self.db)
        return self._analytics_service

    @property
    def message_service(self) -> "MessageService":
        if self._message_service is None:
            from app.domain.messaging.core import MessageService
            self._message_service = MessageService(self.db)
        return self._message_service

    @property
    def flow_service(self) -> "FlowManager":
        if self._flow_service is None:
            from app.services.flow import FlowManager
            self._flow_service = FlowManager(self.db)
        return self._flow_service

    @property
    def notification_service(self) -> "NotificationService":
        """Get multi-channel notification service (singleton)."""
        if self._notification_service is None:
            from app.services.notification_service import get_notification_service
            self._notification_service = get_notification_service()
        return self._notification_service

    @property
    def file_service(self) -> "FileService":
        if self._file_service is None:
            from app.services.file import FileService
            self._file_service = FileService()
        return self._file_service

    @property
    def monthly_quiz_service(self) -> "MonthlyQuizService":
        if self._monthly_quiz_service is None:
            from app.services.quiz.quiz_service import MonthlyQuizService
            self._monthly_quiz_service = MonthlyQuizService(self.db)
        return self._monthly_quiz_service

    @property
    def metrics_collector_service(self) -> "MetricsCollectorService":
        if self._metrics_collector_service is None:
            from app.services.analytics.metrics_collector import MetricsCollectorService
            redis_client = self.get_redis_client_for_service(
                "metrics_collector_service"
            )
            self._metrics_collector_service = MetricsCollectorService(
                self.db, redis_client
            )
        return self._metrics_collector_service

    @property
    def metrics_redis_storage(self) -> "MetricsRedisStorage":
        if self._metrics_redis_storage is None:
            from app.services.analytics.metrics_redis_storage import MetricsRedisStorage
            # MetricsRedisStorage needs async Redis client
            redis_client = self.get_redis_client_for_service("metrics_redis_storage")
            self._metrics_redis_storage = MetricsRedisStorage(redis_client)
        return self._metrics_redis_storage

    @property
    def session_service(self) -> "SimpleSessionService":
        """Get simple synchronous session service for quiz authentication."""
        if self._simple_session_service is None:
            from app.services.simple_session_service import SimpleSessionService
            from app.core.redis_manager import get_redis_manager

            # CRITICAL: SimpleSessionService requires SYNC Redis client
            # The default self.redis_client is async, so we need to get sync client
            sync_redis_client = None
            if self.redis_client is not None:
                try:
                    redis_manager = get_redis_manager()
                    sync_redis_client = redis_manager.get_compatible_client("sync")
                    logger.debug(
                        f"Obtained sync Redis client for SimpleSessionService (request {self._request_id})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to get sync Redis client: {e}, proceeding without Redis"
                    )

            self._simple_session_service = SimpleSessionService(sync_redis_client)
        return self._simple_session_service
