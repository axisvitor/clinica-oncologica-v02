"""
System Management schemas for API v2.

Comprehensive schemas for system health, configuration, initialization,
component management, and metrics with enhanced Redis caching support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# System Health Schemas
# ============================================================================

class ComponentHealth(BaseModel):
    """Individual component health status."""

    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Component status: healthy, degraded, unhealthy")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    last_check: datetime = Field(..., description="Last health check timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional component metadata")

    @validator("status")
    def validate_status(cls, v):
        allowed = ["healthy", "degraded", "unhealthy", "unknown"]
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "database",
                "status": "healthy",
                "latency_ms": 12.5,
                "error": None,
                "last_check": "2025-11-07T10:30:00Z",
                "metadata": {"pool_size": 10, "active_connections": 3}
            }
        }


class SystemHealthResponse(BaseModel):
    """Comprehensive system health check response."""

    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: Dict[str, ComponentHealth] = Field(..., description="Component health details")
    overall_score: float = Field(..., ge=0, le=100, description="Overall health score (0-100)")
    degraded_components: List[str] = Field(default_factory=list, description="List of degraded components")
    unhealthy_components: List[str] = Field(default_factory=list, description="List of unhealthy components")

    @validator("status")
    def validate_status(cls, v):
        allowed = ["healthy", "degraded", "unhealthy"]
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-11-07T10:30:00Z",
                "overall_score": 95.0,
                "components": {
                    "database": {
                        "name": "database",
                        "status": "healthy",
                        "latency_ms": 12.5,
                        "last_check": "2025-11-07T10:30:00Z"
                    },
                    "redis": {
                        "name": "redis",
                        "status": "healthy",
                        "latency_ms": 2.1,
                        "last_check": "2025-11-07T10:30:00Z"
                    }
                },
                "degraded_components": [],
                "unhealthy_components": []
            }
        }


# ============================================================================
# System Initialization Schemas
# ============================================================================

class InitializationError(BaseModel):
    """Initialization error details."""

    component: str = Field(..., description="Component that failed initialization")
    error_message: str = Field(..., description="Error message")
    timestamp: datetime = Field(..., description="Error timestamp")
    recoverable: bool = Field(True, description="Whether error is recoverable")

    class Config:
        json_schema_extra = {
            "example": {
                "component": "firebase",
                "error_message": "Failed to initialize Firebase Admin SDK",
                "timestamp": "2025-11-07T10:30:00Z",
                "recoverable": True
            }
        }


class InitializationRequest(BaseModel):
    """Request to initialize system (optional parameters)."""

    force: bool = Field(False, description="Force reinitialization even if already initialized")
    components: Optional[List[str]] = Field(None, description="Specific components to initialize (all if None)")
    skip_health_check: bool = Field(False, description="Skip health check after initialization")

    class Config:
        json_schema_extra = {
            "example": {
                "force": False,
                "components": ["database", "redis", "firebase"],
                "skip_health_check": False
            }
        }


class InitializationStatusResponse(BaseModel):
    """System initialization status response."""

    started_at: Optional[datetime] = Field(None, description="Initialization start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Initialization completion timestamp")
    status: str = Field(..., description="Initialization status")
    components: Dict[str, Any] = Field(..., description="Component initialization status")
    errors: List[InitializationError] = Field(default_factory=list, description="Initialization errors")
    warnings: List[str] = Field(default_factory=list, description="Initialization warnings")
    duration_ms: Optional[float] = Field(None, description="Initialization duration in milliseconds")

    @validator("status")
    def validate_status(cls, v):
        allowed = ["pending", "in_progress", "completed", "failed", "partial"]
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "started_at": "2025-11-07T10:00:00Z",
                "completed_at": "2025-11-07T10:00:05Z",
                "status": "completed",
                "duration_ms": 5234.5,
                "components": {
                    "database": "initialized",
                    "redis": "initialized",
                    "firebase": "initialized"
                },
                "errors": [],
                "warnings": []
            }
        }


# ============================================================================
# System Information Schemas
# ============================================================================

class SystemInfoResponse(BaseModel):
    """System information response."""

    environment: str = Field(..., description="Environment name (production, staging, development)")
    debug_mode: bool = Field(..., description="Debug mode enabled")
    version: str = Field(..., description="API version")
    uptime: str = Field(..., description="System uptime")
    build_info: Optional[Dict[str, Any]] = Field(None, description="Build information")
    features: Dict[str, bool] = Field(..., description="Feature flags")
    python_version: Optional[str] = Field(None, description="Python version")
    dependencies: Optional[Dict[str, str]] = Field(None, description="Key dependency versions")

    class Config:
        json_schema_extra = {
            "example": {
                "environment": "production",
                "debug_mode": False,
                "version": "2.0.0",
                "uptime": "5d 12h 34m",
                "python_version": "3.11.5",
                "features": {
                    "firebase_auth": True,
                    "whatsapp_integration": True,
                    "ai_humanization": True,
                    "monitoring": True,
                    "rate_limiting": True
                },
                "build_info": {
                    "git_commit": "abc123def456",
                    "build_date": "2025-11-01T10:00:00Z"
                }
            }
        }


# ============================================================================
# Component Management Schemas
# ============================================================================

class ComponentInfo(BaseModel):
    """Individual component information."""

    name: str = Field(..., description="Component name")
    type: str = Field(..., description="Component type: service, database, cache, external")
    status: str = Field(..., description="Current status")
    version: Optional[str] = Field(None, description="Component version")
    restartable: bool = Field(..., description="Whether component can be restarted")
    dependencies: List[str] = Field(default_factory=list, description="Component dependencies")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional component metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "redis",
                "type": "cache",
                "status": "running",
                "version": "7.0",
                "restartable": True,
                "dependencies": [],
                "metadata": {"memory_usage_mb": 256}
            }
        }


class ComponentListResponse(BaseModel):
    """List of system components."""

    components: List[ComponentInfo] = Field(..., description="List of components")
    total: int = Field(..., description="Total component count")
    healthy_count: int = Field(..., description="Count of healthy components")

    class Config:
        json_schema_extra = {
            "example": {
                "components": [
                    {
                        "name": "database",
                        "type": "database",
                        "status": "running",
                        "restartable": False
                    },
                    {
                        "name": "redis",
                        "type": "cache",
                        "status": "running",
                        "restartable": True
                    }
                ],
                "total": 2,
                "healthy_count": 2
            }
        }


class ComponentRestartRequest(BaseModel):
    """Request to restart system component(s)."""

    component: str = Field(..., description="Component name to restart")
    graceful: bool = Field(True, description="Graceful restart (drain connections first)")
    timeout_seconds: int = Field(30, ge=5, le=300, description="Restart timeout in seconds")

    @validator("component")
    def validate_component(cls, v):
        allowed = ["redis", "cache", "workers", "monitoring"]
        if v not in allowed:
            raise ValueError(f"Component must be one of: {', '.join(allowed)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "component": "redis",
                "graceful": True,
                "timeout_seconds": 30
            }
        }


class ComponentRestartResponse(BaseModel):
    """Response after component restart."""

    component: str = Field(..., description="Component name")
    status: str = Field(..., description="Restart status")
    restarted_at: datetime = Field(..., description="Restart timestamp")
    duration_ms: float = Field(..., description="Restart duration in milliseconds")
    previous_status: str = Field(..., description="Status before restart")
    current_status: str = Field(..., description="Status after restart")
    message: str = Field(..., description="Restart message")

    class Config:
        json_schema_extra = {
            "example": {
                "component": "redis",
                "status": "success",
                "restarted_at": "2025-11-07T10:30:00Z",
                "duration_ms": 1523.4,
                "previous_status": "running",
                "current_status": "running",
                "message": "Redis cache restarted successfully"
            }
        }


# ============================================================================
# Configuration Validation Schemas
# ============================================================================

class ConfigValidationRequest(BaseModel):
    """Request to validate configuration."""

    strict: bool = Field(False, description="Strict validation (treat warnings as errors)")
    categories: Optional[List[str]] = Field(None, description="Config categories to validate")

    class Config:
        json_schema_extra = {
            "example": {
                "strict": False,
                "categories": ["security", "database", "external_services"]
            }
        }


class ConfigValidationResponse(BaseModel):
    """Configuration validation response."""

    valid: bool = Field(..., description="Overall validation status")
    warnings: List[str] = Field(default_factory=list, description="Configuration warnings")
    errors: List[str] = Field(default_factory=list, description="Configuration errors")
    checked_at: datetime = Field(..., description="Validation timestamp")
    categories_checked: List[str] = Field(default_factory=list, description="Categories validated")
    recommendations: List[str] = Field(default_factory=list, description="Configuration recommendations")

    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "warnings": [
                    "Firebase Admin SDK not fully configured",
                    "Rate limiting disabled in production"
                ],
                "errors": [],
                "checked_at": "2025-11-07T10:30:00Z",
                "categories_checked": ["security", "database", "external_services"],
                "recommendations": [
                    "Enable rate limiting in production",
                    "Configure HTTPS redirect for production"
                ]
            }
        }


# ============================================================================
# Public Configuration Schemas
# ============================================================================

class PublicConfigResponse(BaseModel):
    """PUBLIC configuration for frontend applications (NO SENSITIVE DATA)."""

    # API URLs (VITE_ format for Vite/frontend compatibility)
    VITE_API_BASE_URL: str = Field(..., description="Base API URL")
    VITE_WS_BASE_URL: str = Field(..., description="WebSocket base URL")
    VITE_API_URL: str = Field(..., description="API server URL")

    # Environment
    VITE_ENVIRONMENT: str = Field(..., description="Environment name")

    # Localization
    VITE_DEFAULT_LOCALE: str = Field(..., description="Default locale")
    VITE_SUPPORTED_LOCALES: List[str] = Field(..., description="Supported locales")

    # Feature flags (PUBLIC ONLY)
    features: Dict[str, bool] = Field(..., description="Public feature flags")

    # CORS info (for debugging)
    cors: Dict[str, Any] = Field(..., description="CORS configuration")

    # Optional Firebase PUBLIC config (web app keys only, NOT service account)
    VITE_FIREBASE_API_KEY: Optional[str] = Field(None, description="Firebase web API key (public)")
    VITE_FIREBASE_PROJECT_ID: Optional[str] = Field(None, description="Firebase project ID (public)")
    VITE_FIREBASE_APP_ID: Optional[str] = Field(None, description="Firebase app ID (public)")
    VITE_FIREBASE_AUTH_DOMAIN: Optional[str] = Field(None, description="Firebase auth domain (public)")

    # Optional quiz URL
    VITE_MONTHLY_QUIZ_URL: Optional[str] = Field(None, description="Monthly quiz URL")

    class Config:
        json_schema_extra = {
            "example": {
                "VITE_API_BASE_URL": "https://api.example.com/api/v1",
                "VITE_WS_BASE_URL": "wss://api.example.com/ws",
                "VITE_API_URL": "https://api.example.com",
                "VITE_ENVIRONMENT": "production",
                "VITE_DEFAULT_LOCALE": "pt-BR",
                "VITE_SUPPORTED_LOCALES": ["pt-BR", "en-US", "es-ES"],
                "features": {
                    "enableRealtime": True,
                    "enableAnalytics": True,
                    "enableEvolution": True,
                    "enableAIHumanization": True
                },
                "cors": {
                    "allowedOrigins": ["https://app.example.com"],
                    "credentials": True
                }
            }
        }


# ============================================================================
# System Metrics Schemas
# ============================================================================

class SystemMetrics(BaseModel):
    """System-level performance metrics."""

    timestamp: datetime = Field(..., description="Metrics timestamp")

    # CPU metrics
    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    cpu_count: int = Field(..., description="CPU core count")

    # Memory metrics
    memory_total_mb: float = Field(..., description="Total memory in MB")
    memory_used_mb: float = Field(..., description="Used memory in MB")
    memory_percent: float = Field(..., ge=0, le=100, description="Memory usage percentage")

    # Disk metrics
    disk_total_gb: float = Field(..., description="Total disk space in GB")
    disk_used_gb: float = Field(..., description="Used disk space in GB")
    disk_percent: float = Field(..., ge=0, le=100, description="Disk usage percentage")

    # Network metrics
    network_connections: int = Field(..., description="Active network connections")

    # Application metrics
    active_sessions: int = Field(..., description="Active user sessions")
    request_rate_per_min: float = Field(..., description="Request rate per minute")

    # Database metrics
    db_connections: int = Field(..., description="Active database connections")
    db_pool_size: int = Field(..., description="Database connection pool size")

    # Cache metrics
    cache_hit_rate: Optional[float] = Field(None, ge=0, le=100, description="Cache hit rate percentage")
    cache_memory_mb: Optional[float] = Field(None, description="Cache memory usage in MB")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-07T10:30:00Z",
                "cpu_percent": 45.2,
                "cpu_count": 4,
                "memory_total_mb": 16384.0,
                "memory_used_mb": 8192.0,
                "memory_percent": 50.0,
                "disk_total_gb": 100.0,
                "disk_used_gb": 45.5,
                "disk_percent": 45.5,
                "network_connections": 125,
                "active_sessions": 42,
                "request_rate_per_min": 450.5,
                "db_connections": 8,
                "db_pool_size": 10,
                "cache_hit_rate": 85.5,
                "cache_memory_mb": 256.0
            }
        }
