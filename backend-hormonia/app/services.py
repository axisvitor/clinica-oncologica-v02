"""
Thread-Safe Service Container for the Hormonia Backend System.

Implements proper thread safety for multi-worker FastAPI production deployment
using request-scoped sessions and stateless service instantiation.

This ServiceProvider is designed to be created per-request with its own
database session, ensuring thread safety and proper resource isolation.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.services.auth import AuthService
from app.services.patient import PatientService, PatientIntegrityService
from app.services.quiz import QuizService
from app.services.report import ReportService
from app.services.analytics import AnalyticsService
from app.services.message import MessageService
from app.services.flow import FlowEngineIntegrationService
from app.services.flow_engine import FlowEngine
# from app.services.notification import NotificationService  # TODO: Implement when needed
from app.services.file import FileService
from app.services.monthly_quiz_service import MonthlyQuizService
from app.services.metrics_collector import MetricsCollectorService
from app.services.metrics_redis_storage import MetricsRedisStorage
from app.services.simple_session_service import SimpleSessionService

# Import repositories
from app.repositories.user import UserRepository
from app.repositories.patient import PatientRepository
from app.repositories.quiz import QuizRepository

logger = logging.getLogger(__name__)


class ServiceProvider:
    """
    Thread-safe service provider with proper dependency injection.

    This class is designed to be instantiated per-request with its own
    database session, ensuring thread safety and proper resource isolation.
    Services are lazily instantiated to improve performance.
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
        self._user_repository = None
        self._patient_repository = None
        self._quiz_repository = None

        # Initialize services (lazy loading)
        self._auth_service = None
        self._patient_service = None
        self._patient_integrity_service = None
        self._quiz_service = None
        self._report_service = None
        self._analytics_service = None
        self._message_service = None
        self._flow_engine = None
        self._flow_service = None
        # self._notification_service = None  # TODO: Implement when needed
        self._file_service = None
        self._monthly_quiz_service = None
        self._metrics_collector_service = None
        self._metrics_redis_storage = None
        self._simple_session_service = None

        logger.debug(f"ServiceProvider initialized for request {self._request_id} with {self._redis_client_type} Redis client")

    def __del__(self):
        """Cleanup logging when ServiceProvider is destroyed."""
        try:
            logger.debug(f"ServiceProvider destroyed for request {self._request_id}")
        except:
            pass  # Avoid errors during cleanup

    def _detect_redis_client_type(self, redis_client) -> str:
        """Detect the type of Redis client provided."""
        if redis_client is None:
            return "none"

        # Check for async Redis client
        if hasattr(redis_client, '__aenter__') or 'asyncio' in str(type(redis_client)):
            return "async"

        # Check for compatibility wrapper
        if hasattr(redis_client, 'redis_manager') or hasattr(redis_client, '_run_async'):
            return "wrapper"

        # Check for sync Redis client
        if hasattr(redis_client, 'ping') and not hasattr(redis_client, '__aenter__'):
            return "sync"

        return "unknown"

    def get_redis_client_for_service(self, service_name: str):
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
        async_services = {'metrics_redis_storage', 'websocket_events'}

        # Services that need sync Redis
        sync_services = {'auth_service', 'cache_service'}

        if service_name in async_services:
            # Return async client or wrapper
            if self._redis_client_type in ["async", "wrapper"]:
                return self.redis_client
            else:
                logger.warning(f"Service {service_name} needs async Redis but got {self._redis_client_type}")
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

    def validate_session(self):
        """Validate that the database session is still usable."""
        if not self.is_session_active:
            logger.error(f"Session validation failed for request {self._request_id}")
            logger.error(f"Session object: {self.db}")
            logger.error(f"Session type: {type(self.db)}")

            # Try to get more information about the session state
            try:
                if hasattr(self.db, '_transaction'):
                    logger.error(f"Session transaction state: {self.db._transaction}")
                if hasattr(self.db, 'connection'):
                    logger.error(f"Session connection state: {self.db.connection()}")
            except Exception as info_error:
                logger.error(f"Could not get session state info: {info_error}")

            raise RuntimeError(
                f"Database session for request {self._request_id} is no longer active. "
                "This may indicate a database connection issue or premature session closure."
            )

    # Repository properties
    @property
    def user_repository(self) -> UserRepository:
        if self._user_repository is None:
            self._user_repository = UserRepository(self.db)
        return self._user_repository

    @property
    def patient_repository(self) -> PatientRepository:
        if self._patient_repository is None:
            self._patient_repository = PatientRepository(self.db)
        return self._patient_repository

    @property
    def quiz_repository(self) -> QuizRepository:
        if self._quiz_repository is None:
            self._quiz_repository = QuizRepository(self.db)
        return self._quiz_repository

    # Service properties with proper dependencies
    @property
    def auth_service(self) -> AuthService:
        if self._auth_service is None:
            # AuthService needs: db, UserRepository, RedisClient
            self._auth_service = AuthService(
                db=self.db,
                user_repository=self.user_repository,
                redis_client=self.redis_client
            )
        return self._auth_service

    @property
    def flow_engine(self) -> FlowEngine:
        if self._flow_engine is None:
            # FlowEngine needs db
            self._flow_engine = FlowEngine(self.db)
        return self._flow_engine

    @property
    def patient_integrity_service(self) -> PatientIntegrityService:
        if self._patient_integrity_service is None:
            # PatientIntegrityService needs: db, PatientRepository
            self._patient_integrity_service = PatientIntegrityService(
                db=self.db,
                patient_repository=self.patient_repository
            )
        return self._patient_integrity_service

    @property
    def patient_service(self) -> PatientService:
        if self._patient_service is None:
            # PatientService needs: db, PatientRepository, PatientIntegrityService, FlowEngine
            self._patient_service = PatientService(
                db=self.db,
                patient_repository=self.patient_repository,
                integrity_service=self.patient_integrity_service,
                flow_engine=self.flow_engine
            )
        return self._patient_service

    @property
    def quiz_service(self) -> QuizService:
        if self._quiz_service is None:
            # Assuming QuizService needs similar dependencies
            # Check the actual constructor requirements
            try:
                # Try with repository and flow engine
                self._quiz_service = QuizService(
                    db=self.db,
                    quiz_repository=self.quiz_repository,
                    flow_engine=self.flow_engine
                )
            except TypeError:
                # Fallback to just db if that's all it needs
                self._quiz_service = QuizService(self.db)
        return self._quiz_service

    @property
    def report_service(self) -> ReportService:
        if self._report_service is None:
            self._report_service = ReportService(self.db)
        return self._report_service

    @property
    def analytics_service(self) -> AnalyticsService:
        if self._analytics_service is None:
            self._analytics_service = AnalyticsService(self.db)
        return self._analytics_service

    @property
    def message_service(self) -> MessageService:
        if self._message_service is None:
            self._message_service = MessageService(self.db)
        return self._message_service

    @property
    def flow_service(self) -> FlowEngineIntegrationService:
        if self._flow_service is None:
            self._flow_service = FlowEngineIntegrationService(self.db)
        return self._flow_service

    # @property
    # def notification_service(self) -> NotificationService:
    #     if self._notification_service is None:
    #         self._notification_service = NotificationService(self.db)
    #     return self._notification_service
    # TODO: Implement NotificationService when needed

    @property
    def file_service(self) -> FileService:
        if self._file_service is None:
            self._file_service = FileService()
        return self._file_service

    @property
    def monthly_quiz_service(self) -> MonthlyQuizService:
        if self._monthly_quiz_service is None:
            self._monthly_quiz_service = MonthlyQuizService(self.db)
        return self._monthly_quiz_service

    @property
    def metrics_collector_service(self) -> MetricsCollectorService:
        if self._metrics_collector_service is None:
            redis_client = self.get_redis_client_for_service('metrics_collector_service')
            self._metrics_collector_service = MetricsCollectorService(self.db, redis_client)
        return self._metrics_collector_service

    @property
    def metrics_redis_storage(self) -> MetricsRedisStorage:
        if self._metrics_redis_storage is None:
            # MetricsRedisStorage needs async Redis client
            redis_client = self.get_redis_client_for_service('metrics_redis_storage')
            self._metrics_redis_storage = MetricsRedisStorage(redis_client)
        return self._metrics_redis_storage

    @property
    def session_service(self) -> SimpleSessionService:
        """Get simple synchronous session service for quiz authentication."""
        if self._simple_session_service is None:
            # CRITICAL: SimpleSessionService requires SYNC Redis client
            # The default self.redis_client is async, so we need to get sync client
            from app.core.redis_manager import get_redis_manager
            
            sync_redis_client = None
            if self.redis_client is not None:
                try:
                    redis_manager = get_redis_manager()
                    sync_redis_client = redis_manager.get_compatible_client('sync')
                    logger.debug(f"Obtained sync Redis client for SimpleSessionService (request {self._request_id})")
                except Exception as e:
                    logger.warning(f"Failed to get sync Redis client: {e}, proceeding without Redis")
            
            self._simple_session_service = SimpleSessionService(sync_redis_client)
        return self._simple_session_service


# Legacy function - NOW DISABLED to prevent thread-safety violations
# CRITICAL: This function caused ALL requests to share the same SQLAlchemy session
def get_service_provider(request) -> ServiceProvider:
    """
    ⛔ DEPRECATED AND DISABLED: Get service provider from FastAPI request.

    CRITICAL THREAD-SAFETY VIOLATION:
    This function returned app.state.service_provider which was a GLOBAL SINGLETON,
    causing all concurrent requests to share the same SQLAlchemy session.

    Problem Impact:
    - Session cross-talk between requests
    - Data corruption under concurrent load
    - Unpredictable query results
    - Race conditions in database transactions

    SOLUTION: Use thread-safe dependency injection instead
    --------------------------------------------------
    OLD (UNSAFE):
        def my_endpoint(services = Depends(get_service_provider)):
            user = services.user_service.get_user()

    NEW (THREAD-SAFE):
        from app.dependencies import get_thread_safe_service_provider

        def my_endpoint(services = Depends(get_thread_safe_service_provider)):
            user = services.user_service.get_user()

    Migration Guide: docs/deployment/SERVICE_DI_REFACTOR.md

    Raises:
        RuntimeError: ALWAYS raises to prevent unsafe usage
    """
    import warnings
    warnings.warn(
        "⛔ get_service_provider(request) is DEPRECATED and CAUSES THREAD-SAFETY VIOLATIONS. "
        "Use get_thread_safe_service_provider() dependency injection instead. "
        "See docs/deployment/SERVICE_DI_REFACTOR.md for migration guide.",
        DeprecationWarning,
        stacklevel=2
    )

    # ALWAYS raise to prevent unsafe usage
    raise RuntimeError(
        "❌ Global service provider is DISABLED for thread safety. "
        "This function caused all requests to share the same SQLAlchemy session. "
        "\n\n"
        "SOLUTION: Use get_thread_safe_service_provider() instead:\n"
        "  from app.dependencies import get_thread_safe_service_provider\n"
        "  def my_endpoint(services = Depends(get_thread_safe_service_provider)):\n"
        "      ...\n"
        "\n"
        "See: docs/deployment/SERVICE_DI_REFACTOR.md"
    )