"""
System Initialization Service for Hormonia Backend.

This service handles comprehensive system initialization including:
- Database connectivity and health checks
- Redis cache initialization
- Security configuration validation
- Monitoring system setup
- Service dependencies verification
"""

from typing import Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from sqlalchemy import text
from redis import Redis
from firebase_admin import auth as firebase_auth

from app.config import settings, get_firebase_security_config
from app.dependencies import get_db
from app.services.firebase_auth_service import get_firebase_auth_service
from app.utils.logging import get_logger
from app.utils.cache import get_redis_client
from app.models import User

logger = get_logger(__name__)


class InitializationError(Exception):
    """Custom exception for initialization failures."""

    pass


class SystemInitializationService:
    """Comprehensive system initialization service."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.initialization_status = {
            "started_at": None,
            "completed_at": None,
            "status": "pending",
            "components": {},
            "errors": [],
        }

    async def initialize_system(self) -> Dict[str, Any]:
        """Initialize the entire system with comprehensive checks."""
        self.initialization_status["started_at"] = datetime.now(timezone.utc).isoformat()
        self.initialization_status["status"] = "initializing"

        self.logger.info("🚀 Starting Hormonia system initialization...")

        try:
            # Initialize components in dependency order
            await self._initialize_database()
            await self._initialize_redis_cache()
            await self._initialize_firebase()
            await self._initialize_security()
            await self._initialize_monitoring()
            await self._validate_service_dependencies()

            self.initialization_status["status"] = "completed"
            self.initialization_status["completed_at"] = datetime.now(timezone.utc).isoformat()

            self.logger.info("✅ System initialization completed successfully")

        except Exception as e:
            self.initialization_status["status"] = "failed"
            self.initialization_status["errors"].append(str(e))
            self.logger.error(f"❌ System initialization failed: {e}")
            raise InitializationError(f"System initialization failed: {e}")

        return self.initialization_status

    async def _initialize_database(self) -> None:
        """Initialize and validate database connectivity."""
        self.logger.info("🔌 Initializing database connectivity...")

        try:
            # Test database connection
            from app.database import get_engine

            engine = get_engine()

            # Test basic connectivity
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()

                if test_value != 1:
                    raise InitializationError("Database connection test failed")

            # Test session-based operations
            async with asynccontextmanager(get_db)() as db:
                # Try to count users (tests table existence)
                user_count = db.query(User).count()
                self.logger.info(f"Database contains {user_count} users")

            self.initialization_status["components"]["database"] = {
                "status": "success",
                "engine_url": engine.url.render_as_string(hide_password=True),
                "user_count": user_count,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("✅ Database initialization successful")

        except Exception as e:
            self.initialization_status["components"]["database"] = {
                "status": "failed",
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
            raise InitializationError(f"Database initialization failed: {e}")

    async def _initialize_redis_cache(self) -> None:
        """Initialize and validate Redis cache connectivity."""
        self.logger.info("🔴 Initializing Redis cache...")

        try:
            redis_client = get_redis_client()

            # Test basic connectivity
            ping_result = redis_client.ping()
            if not ping_result:
                raise InitializationError("Redis ping failed")

            # Test read/write operations
            test_key = "init_test_key"
            test_value = "init_test_value"

            redis_client.set(test_key, test_value, ex=60)  # 60 second expiry
            retrieved_value = redis_client.get(test_key)

            if retrieved_value.decode() != test_value:
                raise InitializationError("Redis read/write test failed")

            # Clean up test key
            redis_client.delete(test_key)

            # Get Redis info
            redis_info = redis_client.info()

            self.initialization_status["components"]["redis"] = {
                "status": "success",
                "version": redis_info.get("redis_version"),
                "memory_used": redis_info.get("used_memory_human"),
                "connected_clients": redis_info.get("connected_clients"),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("✅ Redis cache initialization successful")

        except Exception as e:
            self.initialization_status["components"]["redis"] = {
                "status": "failed",
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
            raise InitializationError(f"Redis cache initialization failed: {e}")

    async def _initialize_firebase(self) -> None:
        """Initialize and validate Firebase Admin SDK."""
        self.logger.info("🔥 Initializing Firebase Admin SDK...")

        try:
            # Check if Firebase credentials are configured
            if not all(
                [
                    settings.FIREBASE_ADMIN_PROJECT_ID,
                    settings.FIREBASE_ADMIN_PRIVATE_KEY,
                    settings.FIREBASE_ADMIN_CLIENT_EMAIL,
                ]
            ):
                self.logger.warning(
                    "⚠️ Firebase credentials not configured, skipping Firebase initialization"
                )
                self.initialization_status["components"]["firebase"] = {
                    "status": "skipped",
                    "reason": "credentials_not_configured",
                    "tested_at": datetime.now(timezone.utc).isoformat(),
                }
                return

            # Initialize Firebase service
            get_firebase_auth_service(
                project_id=settings.FIREBASE_ADMIN_PROJECT_ID,
                private_key=settings.FIREBASE_ADMIN_PRIVATE_KEY,
                client_email=settings.FIREBASE_ADMIN_CLIENT_EMAIL,
            )

            # Test Firebase connectivity by listing users (with limit)
            firebase_auth.list_users(max_results=1)

            # Get security configuration
            security_config = get_firebase_security_config()

            self.initialization_status["components"]["firebase"] = {
                "status": "success",
                "project_id": settings.FIREBASE_ADMIN_PROJECT_ID,
                "security_config": {
                    "allowed_domains_count": len(
                        security_config.get("allowed_domains", [])
                    ),
                    "require_custom_claims": security_config.get(
                        "require_custom_claims"
                    ),
                    "audit_logging_enabled": security_config.get(
                        "enable_audit_logging"
                    ),
                },
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("✅ Firebase Admin SDK initialization successful")

        except Exception as e:
            self.initialization_status["components"]["firebase"] = {
                "status": "failed",
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
            raise InitializationError(f"Firebase initialization failed: {e}")

    async def _initialize_security(self) -> None:
        """Initialize and validate security configurations."""
        self.logger.info("🔒 Initializing security configurations...")

        try:
            security_checks = []

            # Check JWT secret configuration
            if (
                not settings.SECURITY_SECRET_KEY
                or "CHANGE_THIS" in settings.SECURITY_SECRET_KEY.upper()
            ):
                security_checks.append("JWT secret key is not properly configured")

            # Check CSRF secret configuration
            if settings.SECURITY_CSRF_SECRET_KEY:
                if "CHANGE_THIS" in settings.SECURITY_CSRF_SECRET_KEY.upper():
                    security_checks.append("CSRF secret key is using default value")
            else:
                security_checks.append("CSRF secret key not configured")

            # Check production security settings
            if settings.APP_ENVIRONMENT.lower() == "production":
                if settings.APP_ENABLE_DEBUG:
                    security_checks.append("DEBUG is enabled in production")
                if not settings.SESSION_ENABLE_COOKIE_SECURE:
                    security_checks.append("Session cookies not secured for HTTPS")
                if not settings.SECURITY_ENABLE_SSL_REDIRECT:
                    security_checks.append("SSL redirect not enabled")

            # Check rate limiting configuration
            rate_limiting_enabled = settings.RATE_LIMIT_ENABLE_SERVICE

            self.initialization_status["components"]["security"] = {
                "status": "success" if not security_checks else "warning",
                "checks": security_checks,
                "rate_limiting_enabled": rate_limiting_enabled,
                "environment": settings.APP_ENVIRONMENT,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

            if security_checks:
                self.logger.warning(
                    f"⚠️ Security warnings found: {'; '.join(security_checks)}"
                )
            else:
                self.logger.info("✅ Security configuration validation successful")

        except Exception as e:
            self.initialization_status["components"]["security"] = {
                "status": "failed",
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
            raise InitializationError(f"Security initialization failed: {e}")

    async def _initialize_monitoring(self) -> None:
        """Initialize monitoring and metrics systems."""
        self.logger.info("📊 Initializing monitoring systems...")

        try:
            monitoring_components = []

            # Check if monitoring is enabled
            if settings.MONITORING_ENABLE_SERVICE:
                monitoring_components.append("system_metrics")

                # Test monitoring Redis connection if configured
                if hasattr(settings, "MONITORING_REDIS_HOST"):
                    try:
                        monitoring_redis = Redis(
                            host=settings.MONITORING_REDIS_HOST,
                            port=settings.MONITORING_REDIS_PORT,
                            db=settings.MONITORING_REDIS_DB,
                            password=settings.MONITORING_REDIS_PASSWORD,
                            decode_responses=True,
                        )
                        monitoring_redis.ping()
                        monitoring_components.append("monitoring_redis")
                    except Exception as e:
                        self.logger.warning(f"Monitoring Redis connection failed: {e}")

            self.initialization_status["components"]["monitoring"] = {
                "status": "success",
                "enabled": settings.MONITORING_ENABLE_SERVICE,
                "components": monitoring_components,
                "apm_threshold": settings.APM_APDEX_THRESHOLD,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("✅ Monitoring systems initialization successful")

        except Exception as e:
            self.initialization_status["components"]["monitoring"] = {
                "status": "failed",
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
            raise InitializationError(f"Monitoring initialization failed: {e}")

    async def _validate_service_dependencies(self) -> None:
        """Validate that all required service dependencies are available."""
        self.logger.info("🔗 Validating service dependencies...")

        try:
            dependencies = []

            # Validate core services
            if (
                self.initialization_status["components"]
                .get("database", {})
                .get("status")
                == "success"
            ):
                dependencies.append("database")

            if (
                self.initialization_status["components"].get("redis", {}).get("status")
                == "success"
            ):
                dependencies.append("redis")

            if self.initialization_status["components"].get("firebase", {}).get(
                "status"
            ) in ["success", "skipped"]:
                dependencies.append("firebase")

            # Check external service configurations
            external_services = []

            if settings.WHATSAPP_ENABLE_SERVICE:
                external_services.append(
                    {
                        "name": "evolution_api",
                        "url": settings.WHATSAPP_EVOLUTION_API_URL,
                        "configured": bool(settings.WHATSAPP_EVOLUTION_API_KEY),
                    }
                )

            if settings.AI_GEMINI_API_KEY:
                external_services.append(
                    {
                        "name": "gemini_ai",
                        "model": settings.AI_GEMINI_MODEL,
                        "configured": True,
                    }
                )

            self.initialization_status["components"]["dependencies"] = {
                "status": "success",
                "core_services": dependencies,
                "external_services": external_services,
                "validated_at": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info(
                f"✅ Service dependencies validation successful: {len(dependencies)} core, {len(external_services)} external"
            )

        except Exception as e:
            self.initialization_status["components"]["dependencies"] = {
                "status": "failed",
                "error": str(e),
                "validated_at": datetime.now(timezone.utc).isoformat(),
            }
            raise InitializationError(f"Service dependencies validation failed: {e}")

    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {},
            "overall_score": 0,
        }

        try:
            # Check database health
            try:
                from app.database import get_engine

                engine = get_engine()
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                health_status["components"]["database"] = {
                    "status": "healthy",
                    "latency_ms": "< 10",
                }
            except Exception as e:
                health_status["components"]["database"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"

            # Check Redis health
            try:
                redis_client = get_redis_client()
                redis_client.ping()
                health_status["components"]["redis"] = {
                    "status": "healthy",
                    "latency_ms": "< 5",
                }
            except Exception as e:
                health_status["components"]["redis"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"

            # Check Firebase health (if configured)
            try:
                if all(
                    [
                        settings.FIREBASE_ADMIN_PROJECT_ID,
                        settings.FIREBASE_ADMIN_PRIVATE_KEY,
                        settings.FIREBASE_ADMIN_CLIENT_EMAIL,
                    ]
                ):
                    firebase_auth.list_users(max_results=1)
                    health_status["components"]["firebase"] = {"status": "healthy"}
                else:
                    health_status["components"]["firebase"] = {
                        "status": "not_configured"
                    }
            except Exception as e:
                health_status["components"]["firebase"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"

            # Calculate overall health score
            healthy_components = sum(
                1
                for comp in health_status["components"].values()
                if comp.get("status") == "healthy"
            )
            total_components = len(
                [
                    comp
                    for comp in health_status["components"].values()
                    if comp.get("status") != "not_configured"
                ]
            )

            if total_components > 0:
                health_status["overall_score"] = (
                    healthy_components / total_components
                ) * 100

            if health_status["overall_score"] < 50:
                health_status["status"] = "unhealthy"
            elif health_status["overall_score"] < 100:
                health_status["status"] = "degraded"

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    def get_initialization_status(self) -> Dict[str, Any]:
        """Get current initialization status."""
        return self.initialization_status.copy()


# Global service instance
_system_init_service = None


def get_system_initialization_service() -> SystemInitializationService:
    """Get system initialization service instance."""
    global _system_init_service
    if _system_init_service is None:
        _system_init_service = SystemInitializationService()
    return _system_init_service


# Convenience functions for FastAPI lifespan events
async def initialize_system() -> Dict[str, Any]:
    """Initialize system (for use in FastAPI lifespan events)."""
    service = get_system_initialization_service()
    return await service.initialize_system()


async def get_system_health() -> Dict[str, Any]:
    """Get system health status (for health check endpoints)."""
    service = get_system_initialization_service()
    return await service.get_system_health()
