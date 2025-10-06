"""
Database connection and session management with Supabase RLS integration.

This module provides enhanced database connection management that supports
both service_role (bypassRLS) and JWT-based RLS context injection for
Row Level Security policies.
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError
from typing import Generator, Optional, Dict, Any
import logging
import time
from contextlib import contextmanager
import jwt
from datetime import datetime, timezone

from app.config import settings
from app.utils.database_optimization import create_optimized_engine, ConnectionPoolMonitor
from app.utils.query_performance import QueryPerformanceMonitor, IndexManager

logger = logging.getLogger(__name__)

# Database engine configurations for different RLS modes
_engines = {}
_session_factories = {}

class RLSConnectionManager:
    """
    Manages database connections with Row Level Security context.

    Supports two modes:
    1. Service Role (bypassRLS): Uses service_role key for full access
    2. JWT Context: Injects user JWT for RLS policy enforcement
    """

    def __init__(self):
        self.pool_monitor = None
        self._initialize_engines()

    def _initialize_engines(self):
        """Initialize database engines for different RLS modes."""
        global _engines, _session_factories

        # Service Role Engine (bypassRLS)
        service_role_engine = create_optimized_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=settings.RLS_POOL_SIZE if hasattr(settings, 'RLS_POOL_SIZE') else 30,  # SECURITY FIX: Increased from 25
            max_overflow=settings.RLS_POOL_MAX_OVERFLOW if hasattr(settings, 'RLS_POOL_MAX_OVERFLOW') else 50,  # SECURITY FIX: Increased from 35
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=30,
            pool_reset_on_return='commit',
            pool_logging_name='hormonia_service_role',
            connect_args={
                'connect_timeout': 30,  # Aumentado de 10 para 30 para conexões lentas
                'statement_timeout': 30000,  # SECURITY FIX: 30s query timeout prevents DoS
                'sslmode': 'require',        # SECURITY FIX: Enforce SSL to prevent MITM
                'prepare_threshold': 0,      # Evita problemas com prepared statements em SSL
                'tcp_user_timeout': 30000,   # Previne timeouts silenciosos (30s)
                'application_name': 'hormonia_service_role',
                'keepalives': 1,             # Habilita TCP keepalive
                'keepalives_idle': 30,       # Reduzido de 600 para detectar falhas mais rápido
                'keepalives_interval': 10,   # Reduzido de 30 para detectar falhas mais rápido
                'keepalives_count': 5,       # Aumentado de 3 para tolerar mais pacotes perdidos
            },
            echo=settings.DEBUG,
            echo_pool=settings.DEBUG if hasattr(settings, 'DEBUG') else False
        )

        # RLS Context Engine (with JWT)
        rls_engine = create_optimized_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=15,  # Smaller pool for RLS context
            max_overflow=25,
            pool_pre_ping=True,
            pool_recycle=1800,  # Shorter recycle for security
            pool_timeout=30,
            pool_reset_on_return='commit',
            pool_logging_name='hormonia_rls',
            connect_args={
                'connect_timeout': 30,       # Aumentado de 10 para 30 para conexões lentas
                'statement_timeout': 30000,  # SECURITY FIX: 30s query timeout prevents DoS
                'sslmode': 'require',        # SECURITY FIX: Enforce SSL to prevent MITM
                'prepare_threshold': 0,      # Evita problemas com prepared statements em SSL
                'tcp_user_timeout': 30000,   # Previne timeouts silenciosos (30s)
                'application_name': 'hormonia_rls',
                'keepalives': 1,             # Habilita TCP keepalive
                'keepalives_idle': 30,       # Reduzido de 600 para detectar falhas mais rápido
                'keepalives_interval': 10,   # Reduzido de 30 para detectar falhas mais rápido
                'keepalives_count': 5,       # Aumentado de 3 para tolerar mais pacotes perdidos
            },
            echo=settings.DEBUG,
            echo_pool=settings.DEBUG if hasattr(settings, 'DEBUG') else False
        )

        # Adicionar retry logic para reconexão automática em caso de falha SSL
        @event.listens_for(service_role_engine, "handle_error")
        def handle_service_role_error(exception_context):
            """Retry automaticamente em caso de erro SSL."""
            if isinstance(exception_context.original_exception, OperationalError):
                error_msg = str(exception_context.original_exception)
                if "SSL connection has been closed" in error_msg or "consuming input failed" in error_msg:
                    logger.warning(f"SSL connection lost on service_role engine: {error_msg[:100]}... Pool pre-ping will reconnect automatically")
                    # Retorna None para permitir que o pool pre-ping reconecte
                    return None

        @event.listens_for(rls_engine, "handle_error")
        def handle_rls_error(exception_context):
            """Retry automaticamente em caso de erro SSL."""
            if isinstance(exception_context.original_exception, OperationalError):
                error_msg = str(exception_context.original_exception)
                if "SSL connection has been closed" in error_msg or "consuming input failed" in error_msg:
                    logger.warning(f"SSL connection lost on rls engine: {error_msg[:100]}... Pool pre-ping will reconnect automatically")
                    # Retorna None para permitir que o pool pre-ping reconecte
                    return None

        _engines['service_role'] = service_role_engine
        _engines['rls'] = rls_engine

        _session_factories['service_role'] = sessionmaker(
            autocommit=False, autoflush=False, bind=service_role_engine
        )
        _session_factories['rls'] = sessionmaker(
            autocommit=False, autoflush=False, bind=rls_engine
        )

        self.pool_monitor = ConnectionPoolMonitor(service_role_engine)

        # Set up RLS context injection for RLS engine
        self._setup_rls_context_injection(rls_engine)

    def _setup_rls_context_injection(self, engine):
        """Set up automatic RLS context injection for connections."""

        @event.listens_for(engine, "connect")
        def set_rls_context(dbapi_connection, connection_record):
            """Inject RLS context when connection is established."""
            try:
                # This will be set per-session when we have user context
                # For now, just ensure the connection is ready for RLS
                with dbapi_connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('app.current_user_id', '', false)")
                    cursor.execute("SELECT set_config('app.current_user_role', 'authenticated', false)")

            except Exception as e:
                logger.warning(f"Failed to set initial RLS context: {e}")

    def get_engine(self, use_service_role: bool = None) -> Any:
        """
        Get database engine based on RLS configuration.

        Args:
            use_service_role: Override for service_role usage.
                            If None, uses settings.SUPABASE_USE_SERVICE_ROLE

        Returns:
            SQLAlchemy engine instance
        """
        if use_service_role is None:
            use_service_role = getattr(settings, 'SUPABASE_USE_SERVICE_ROLE', True)

        engine_type = 'service_role' if use_service_role else 'rls'
        return _engines[engine_type]

    def get_session_factory(self, use_service_role: bool = None):
        """Get session factory based on RLS configuration."""
        if use_service_role is None:
            use_service_role = getattr(settings, 'SUPABASE_USE_SERVICE_ROLE', True)

        engine_type = 'service_role' if use_service_role else 'rls'
        return _session_factories[engine_type]

    def create_rls_session(self, jwt_token: Optional[str] = None, user_id: Optional[str] = None) -> Session:
        """
        Create a database session with RLS context.

        Args:
            jwt_token: JWT token for user authentication
            user_id: User ID for RLS context (alternative to JWT)

        Returns:
            SQLAlchemy session with RLS context
        """
        use_service_role = getattr(settings, 'SUPABASE_USE_SERVICE_ROLE', True)

        if use_service_role:
            # Use service role (bypass RLS)
            session = _session_factories['service_role']()
        else:
            # Use RLS context
            session = _session_factories['rls']()
            self._inject_rls_context(session, jwt_token, user_id)

        return session

    def _inject_rls_context(self, session: Session, jwt_token: Optional[str] = None, user_id: Optional[str] = None):
        """
        Inject RLS context into the database session.

        Args:
            session: SQLAlchemy session
            jwt_token: JWT token for user authentication
            user_id: User ID for RLS context
        """
        try:
            if jwt_token:
                # Decode JWT to get user information
                try:
                    decoded_token = jwt.decode(
                        jwt_token,
                        settings.SUPABASE_SERVICE_ROLE_KEY,  # SECURITY FIX: Added key for verification
                        algorithms=["HS256"],                 # SECURITY FIX: Specify algorithm
                        options={"verify_signature": True}    # SECURITY FIX: Changed from False to True
                    )
                    user_id = decoded_token.get('sub') or decoded_token.get('user_id')
                    user_role = decoded_token.get('role', 'authenticated')
                    user_email = decoded_token.get('email')
                except jwt.InvalidTokenError as e:
                    logger.warning(f"Invalid JWT token for RLS context: {e}")
                    user_role = 'authenticated'
            else:
                user_role = 'authenticated'

            # Set RLS context variables
            if user_id:
                session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"),
                              {'user_id': user_id})

            session.execute(text("SELECT set_config('app.current_user_role', :role, true)"),
                          {'role': user_role})

            # Set JWT token for Supabase auth
            if jwt_token:
                session.execute(text("SELECT set_config('request.jwt.token', :token, true)"),
                              {'token': jwt_token})
                session.execute(text("SELECT set_config('request.jwt.claims', :claims, true)"),
                              {'claims': jwt_token})

            # Enable audit logging if configured
            if getattr(settings, 'RLS_ENABLE_AUDIT_LOGGING', True):
                session.execute(text("SELECT set_config('app.audit_enabled', 'true', true)"))

            session.commit()

        except Exception as e:
            logger.error(f"Failed to inject RLS context: {e}")
            session.rollback()
            raise

# Global connection manager instance
connection_manager = RLSConnectionManager()

# Backward compatibility - use the main service role engine as default
engine = connection_manager.get_engine(use_service_role=True)
SessionLocal = connection_manager.get_session_factory(use_service_role=True)

# Base class for all models
Base = declarative_base()


def get_db(jwt_token: Optional[str] = None, user_id: Optional[str] = None) -> Generator[Session, None, None]:
    """
    Dependency to get database session with optional RLS context.

    Args:
        jwt_token: JWT token for RLS context
        user_id: User ID for RLS context

    Yields:
        Database session with appropriate RLS context
    """
    session_kwargs = {}
    if jwt_token is not None:
        session_kwargs['jwt_token'] = jwt_token
    if user_id is not None:
        session_kwargs['user_id'] = user_id

    session = connection_manager.create_rls_session(**session_kwargs)
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_db_with_rls(jwt_token: str) -> Generator[Session, None, None]:
    """
    Dependency specifically for RLS-enabled database sessions.

    Args:
        jwt_token: JWT token for user context

    Yields:
        Database session with RLS context
    """
    return get_db(jwt_token=jwt_token)


def get_db_service_role() -> Generator[Session, None, None]:
    """
    Dependency specifically for service role database sessions (bypass RLS).

    Yields:
        Database session with service role permissions
    """
    yield from get_db()


@contextmanager
def get_scoped_session(jwt_token: Optional[str] = None, user_id: Optional[str] = None):
    """
    Context manager for scoped database sessions with RLS support.

    Args:
        jwt_token: JWT token for RLS context
        user_id: User ID for RLS context

    Yields:
        Database session with appropriate RLS context
    """
    session = connection_manager.create_rls_session(jwt_token=jwt_token, user_id=user_id)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables():
    """Create all database tables."""
    try:
        # Use service role for DDL operations
        service_engine = connection_manager.get_engine(use_service_role=True)
        Base.metadata.create_all(bind=service_engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def drop_tables():
    """Drop all database tables (use with caution)."""
    try:
        # Use service role for DDL operations
        service_engine = connection_manager.get_engine(use_service_role=True)
        Base.metadata.drop_all(bind=service_engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise


def test_connection(use_service_role: bool = True) -> Dict[str, Any]:
    """
    Test database connection and return status information.

    Args:
        use_service_role: Whether to test service role or RLS connection

    Returns:
        Connection status with details
    """
    try:
        with get_scoped_session() as session:
            # Test basic query
            result = session.execute(text("SELECT 1 as test")).fetchone()

            # Test RLS context if not using service role
            rls_context = {}
            if not use_service_role:
                try:
                    user_id_result = session.execute(text("SELECT current_setting('app.current_user_id', true)")).fetchone()
                    user_role_result = session.execute(text("SELECT current_setting('app.current_user_role', true)")).fetchone()
                    rls_context = {
                        'current_user_id': user_id_result[0] if user_id_result else None,
                        'current_user_role': user_role_result[0] if user_role_result else None
                    }
                except Exception as e:
                    rls_context = {'error': str(e)}

            # Test pool status
            engine_instance = connection_manager.get_engine(use_service_role=use_service_role)
            pool_status = {
                "pool_size": engine_instance.pool.size(),
                "checked_in": engine_instance.pool.checkedin(),
                "checked_out": engine_instance.pool.checkedout(),
                "overflow": engine_instance.pool.overflow(),
            }

            return {
                "status": "healthy",
                "test_query_result": result[0] if result else None,
                "rls_mode": "service_role" if use_service_role else "rls_context",
                "rls_context": rls_context,
                "pool_info": pool_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "rls_mode": "service_role" if use_service_role else "rls_context",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def get_pool_status(use_service_role: bool = True) -> Dict[str, Any]:
    """Get database connection pool status."""
    engine_instance = connection_manager.get_engine(use_service_role=use_service_role)
    return {
        "engine_type": "service_role" if use_service_role else "rls_context",
        "pool_size": engine_instance.pool.size(),
        "checked_in": engine_instance.pool.checkedin(),
        "checked_out": engine_instance.pool.checkedout(),
        "overflow": engine_instance.pool.overflow(),
    }


def is_pool_healthy(use_service_role: bool = True) -> bool:
    """Check if database connection pool is healthy."""
    try:
        pool_status = get_pool_status(use_service_role=use_service_role)
        return pool_status["checked_out"] < pool_status["pool_size"] + pool_status["overflow"]
    except Exception:
        return False


class RLSError(Exception):
    """Custom exception for RLS-related errors."""
    pass


class RLSAccessDeniedError(RLSError):
    """Raised when RLS policies deny access."""
    pass


class RLSContextError(RLSError):
    """Raised when RLS context is invalid or missing."""
    pass


# Supabase client initialization (backward compatibility)
# Module-level sentinel to prevent duplicate initialization
_SUPABASE_CLIENT_INITIALIZED = False
supabase_client = None

def init_supabase_client():
    """Initialize Supabase client safely (idempotent)."""
    global supabase_client, _SUPABASE_CLIENT_INITIALIZED

    # Return early if already initialized
    if _SUPABASE_CLIENT_INITIALIZED:
        return supabase_client is not None

    try:
        from supabase import create_client, Client

        # Use service role key for bypassing RLS when needed
        supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )

        _SUPABASE_CLIENT_INITIALIZED = True
        logger.info("Supabase client initialized successfully")
        return True

    except ImportError:
        _SUPABASE_CLIENT_INITIALIZED = True
        logger.warning("Supabase client not available. Install supabase-py for full functionality.")
        return False
    except Exception as e:
        _SUPABASE_CLIENT_INITIALIZED = True
        logger.error(f"Error initializing Supabase client: {e}")
        return False

# Try to initialize on import (idempotent - will only log once)
init_supabase_client()


def get_supabase():
    """Get Supabase client instance."""
    if supabase_client is None:
        raise RuntimeError("Supabase client not initialized")
    return supabase_client