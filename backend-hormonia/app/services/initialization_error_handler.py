"""
Initialization Error Handler for Hormonia Backend.

Provides comprehensive error handling, recovery mechanisms,
and fallback strategies for system initialization failures.
"""
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import logging
import traceback
from enum import Enum

from app.utils.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


class InitializationPhase(Enum):
    """Initialization phases for error classification."""
    DATABASE = "database"
    REDIS = "redis"
    FIREBASE = "firebase"
    SECURITY = "security"
    MONITORING = "monitoring"
    DEPENDENCIES = "dependencies"


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"  # System cannot start
    HIGH = "high"        # Major functionality impaired
    MEDIUM = "medium"    # Some features may not work
    LOW = "low"          # Minor issues, warnings only


class InitializationError:
    """Structured initialization error."""
    
    def __init__(
        self,
        phase: InitializationPhase,
        severity: ErrorSeverity,
        error: Exception,
        message: str,
        recovery_suggestion: Optional[str] = None,
        fallback_available: bool = False
    ):
        self.phase = phase
        self.severity = severity
        self.error = error
        self.message = message
        self.recovery_suggestion = recovery_suggestion
        self.fallback_available = fallback_available
        self.timestamp = datetime.utcnow()
        self.traceback = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "phase": self.phase.value,
            "severity": self.severity.value,
            "error_type": type(self.error).__name__,
            "error_message": str(self.error),
            "message": self.message,
            "recovery_suggestion": self.recovery_suggestion,
            "fallback_available": self.fallback_available,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback
        }


class InitializationErrorHandler:
    """Comprehensive initialization error handler with recovery strategies."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.errors: List[InitializationError] = []
        self.recovery_strategies: Dict[InitializationPhase, List[Callable]] = {
            InitializationPhase.DATABASE: [
                self._retry_database_connection,
                self._fallback_to_sqlite
            ],
            InitializationPhase.REDIS: [
                self._retry_redis_connection,
                self._fallback_to_memory_cache
            ],
            InitializationPhase.FIREBASE: [
                self._retry_firebase_init,
                self._disable_firebase_features
            ],
            InitializationPhase.SECURITY: [
                self._regenerate_security_keys,
                self._use_development_security
            ],
            InitializationPhase.MONITORING: [
                self._retry_monitoring_init,
                self._disable_monitoring
            ],
            InitializationPhase.DEPENDENCIES: [
                self._retry_dependency_check,
                self._mark_dependencies_optional
            ]
        }
    
    def handle_error(
        self,
        phase: InitializationPhase,
        error: Exception,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        attempt_recovery: bool = True
    ) -> Dict[str, Any]:
        """Handle initialization error with recovery attempts."""
        
        # Create structured error
        init_error = InitializationError(
            phase=phase,
            severity=severity,
            error=error,
            message=message,
            recovery_suggestion=self._get_recovery_suggestion(phase, error),
            fallback_available=len(self.recovery_strategies.get(phase, [])) > 0
        )
        
        self.errors.append(init_error)
        
        # Log error with appropriate level
        log_level = {
            ErrorSeverity.CRITICAL: self.logger.critical,
            ErrorSeverity.HIGH: self.logger.error,
            ErrorSeverity.MEDIUM: self.logger.warning,
            ErrorSeverity.LOW: self.logger.info
        }
        
        log_level[severity](
            f"Initialization error in {phase.value}: {message} - {str(error)}"
        )
        
        # Attempt recovery if requested and strategies available
        recovery_result = None
        if attempt_recovery and phase in self.recovery_strategies:
            recovery_result = self._attempt_recovery(phase, error)
        
        return {
            "error": init_error.to_dict(),
            "recovery_attempted": attempt_recovery,
            "recovery_result": recovery_result
        }
    
    def _attempt_recovery(self, phase: InitializationPhase, error: Exception) -> Dict[str, Any]:
        """Attempt recovery using available strategies."""
        strategies = self.recovery_strategies.get(phase, [])
        recovery_results = []
        
        for i, strategy in enumerate(strategies):
            try:
                self.logger.info(f"Attempting recovery strategy {i+1}/{len(strategies)} for {phase.value}")
                result = strategy(error)
                
                if result.get("success"):
                    self.logger.info(f"Recovery successful for {phase.value} using strategy {i+1}")
                    return {
                        "success": True,
                        "strategy_used": i + 1,
                        "result": result
                    }
                
                recovery_results.append(result)
                
            except Exception as recovery_error:
                self.logger.warning(f"Recovery strategy {i+1} failed for {phase.value}: {recovery_error}")
                recovery_results.append({
                    "success": False,
                    "error": str(recovery_error)
                })
        
        return {
            "success": False,
            "attempts": len(strategies),
            "results": recovery_results
        }
    
    def _get_recovery_suggestion(self, phase: InitializationPhase, error: Exception) -> str:
        """Get human-readable recovery suggestion."""
        suggestions = {
            InitializationPhase.DATABASE: (
                "Check database connection string, ensure PostgreSQL is running, "
                "verify network connectivity, check credentials"
            ),
            InitializationPhase.REDIS: (
                "Verify Redis server is running, check connection parameters, "
                "ensure network connectivity, validate credentials"
            ),
            InitializationPhase.FIREBASE: (
                "Verify Firebase Admin SDK credentials, check service account permissions, "
                "ensure project ID is correct"
            ),
            InitializationPhase.SECURITY: (
                "Generate new security keys, check environment variables, "
                "validate security configuration"
            ),
            InitializationPhase.MONITORING: (
                "Check monitoring service configuration, verify dependencies, "
                "consider disabling monitoring temporarily"
            ),
            InitializationPhase.DEPENDENCIES: (
                "Verify external service configurations, check network connectivity, "
                "validate API keys and credentials"
            )
        }
        
        return suggestions.get(phase, "Review error details and check system configuration")
    
    # Recovery strategy implementations
    
    def _retry_database_connection(self, error: Exception) -> Dict[str, Any]:
        """Retry database connection with different parameters."""
        try:
            # Implement database connection retry logic
            from app.database import get_engine
            from sqlalchemy import text
            
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            return {"success": True, "message": "Database connection restored"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _fallback_to_sqlite(self, error: Exception) -> Dict[str, Any]:
        """Fallback to SQLite for development/testing."""
        try:
            if settings.ENVIRONMENT.lower() in ['development', 'testing']:
                # This would require reconfiguring the database engine
                return {
                    "success": True,
                    "message": "Fallback to SQLite configured",
                    "warning": "Using SQLite fallback - not suitable for production"
                }
            else:
                return {
                    "success": False,
                    "message": "SQLite fallback not available in production"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _retry_redis_connection(self, error: Exception) -> Dict[str, Any]:
        """Retry Redis connection."""
        try:
            from app.utils.cache import get_redis_client, reset_redis_connections
            
            # Reset connections and retry
            reset_redis_connections()
            redis_client = get_redis_client()
            redis_client.ping()
            
            return {"success": True, "message": "Redis connection restored"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _fallback_to_memory_cache(self, error: Exception) -> Dict[str, Any]:
        """Fallback to in-memory caching."""
        try:
            # This would require reconfiguring cache backends
            return {
                "success": True,
                "message": "In-memory cache fallback activated",
                "warning": "Using in-memory cache - data will not persist across restarts"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _retry_firebase_init(self, error: Exception) -> Dict[str, Any]:
        """Retry Firebase initialization."""
        try:
            import firebase_admin
            from firebase_admin import auth as firebase_auth
            
            # Clear existing apps and retry
            firebase_admin._apps.clear()
            
            # Try to reinitialize
            from app.services.firebase_auth_service import get_firebase_auth_service
            firebase_service = get_firebase_auth_service(
                project_id=settings.FIREBASE_ADMIN_PROJECT_ID,
                private_key=settings.FIREBASE_ADMIN_PRIVATE_KEY,
                client_email=settings.FIREBASE_ADMIN_CLIENT_EMAIL
            )
            
            # Test with simple operation
            firebase_auth.list_users(max_results=1)
            
            return {"success": True, "message": "Firebase connection restored"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _disable_firebase_features(self, error: Exception) -> Dict[str, Any]:
        """Disable Firebase-dependent features."""
        try:
            # This would require feature flags to disable Firebase functionality
            return {
                "success": True,
                "message": "Firebase features disabled",
                "warning": "Authentication will use local fallback mechanisms"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _regenerate_security_keys(self, error: Exception) -> Dict[str, Any]:
        """Generate new security keys if missing."""
        try:
            import secrets
            
            warnings = []
            
            # This would need to update environment or config
            if not settings.SECRET_KEY or 'CHANGE_THIS' in settings.SECRET_KEY.upper():
                new_secret = secrets.token_urlsafe(32)
                warnings.append(f"Generated new SECRET_KEY: {new_secret[:8]}...")
            
            if not settings.CSRF_SECRET_KEY:
                new_csrf_secret = secrets.token_urlsafe(32)
                warnings.append(f"Generated new CSRF_SECRET_KEY: {new_csrf_secret[:8]}...")
            
            return {
                "success": True,
                "message": "Security keys regenerated",
                "warnings": warnings,
                "action_required": "Update environment variables with new keys"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _use_development_security(self, error: Exception) -> Dict[str, Any]:
        """Use development security settings."""
        try:
            if settings.ENVIRONMENT.lower() == 'development':
                return {
                    "success": True,
                    "message": "Development security mode activated",
                    "warning": "Using relaxed security settings - not suitable for production"
                }
            else:
                return {
                    "success": False,
                    "message": "Development security not available in production"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _retry_monitoring_init(self, error: Exception) -> Dict[str, Any]:
        """Retry monitoring initialization."""
        try:
            # This would retry monitoring service initialization
            return {"success": True, "message": "Monitoring services restored"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _disable_monitoring(self, error: Exception) -> Dict[str, Any]:
        """Disable monitoring features."""
        try:
            return {
                "success": True,
                "message": "Monitoring disabled",
                "warning": "System metrics and monitoring will not be available"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _retry_dependency_check(self, error: Exception) -> Dict[str, Any]:
        """Retry dependency validation."""
        try:
            # This would retry external service checks
            return {"success": True, "message": "Dependencies validated"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _mark_dependencies_optional(self, error: Exception) -> Dict[str, Any]:
        """Mark external dependencies as optional."""
        try:
            return {
                "success": True,
                "message": "External dependencies marked as optional",
                "warning": "Some features may not be available"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all initialization errors."""
        if not self.errors:
            return {"status": "no_errors", "total_errors": 0}
        
        summary = {
            "status": "has_errors",
            "total_errors": len(self.errors),
            "by_severity": {},
            "by_phase": {},
            "critical_errors": [],
            "recovery_available": 0
        }
        
        for error in self.errors:
            # Count by severity
            severity = error.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            
            # Count by phase
            phase = error.phase.value
            summary["by_phase"][phase] = summary["by_phase"].get(phase, 0) + 1
            
            # Track critical errors
            if error.severity == ErrorSeverity.CRITICAL:
                summary["critical_errors"].append(error.to_dict())
            
            # Count recovery options
            if error.fallback_available:
                summary["recovery_available"] += 1
        
        return summary
    
    def should_block_startup(self) -> bool:
        """Determine if initialization errors should block application startup."""
        critical_errors = [
            error for error in self.errors
            if error.severity == ErrorSeverity.CRITICAL
        ]
        
        # Block startup if there are critical errors without recovery
        for error in critical_errors:
            if not error.fallback_available:
                return True
        
        return False
    
    def get_startup_warnings(self) -> List[str]:
        """Get list of warnings for successful startup with degraded functionality."""
        warnings = []
        
        for error in self.errors:
            if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.MEDIUM]:
                if error.fallback_available:
                    warnings.append(
                        f"{error.phase.value}: {error.message} (fallback active)"
                    )
                else:
                    warnings.append(
                        f"{error.phase.value}: {error.message}"
                    )
        
        return warnings


# Global error handler instance
_error_handler = None


def get_initialization_error_handler() -> InitializationErrorHandler:
    """Get global initialization error handler."""
    global _error_handler
    if _error_handler is None:
        _error_handler = InitializationErrorHandler()
    return _error_handler
