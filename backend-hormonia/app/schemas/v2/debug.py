"""
Debug schemas for API v2
ADMIN-ONLY diagnostic and debugging tools with strict security controls.

WARNING: Debug endpoints are disabled by default in production.
Set ENABLE_DEBUG_ENDPOINTS=true in dev/staging ONLY.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
from app.utils.timezone import now_sao_paulo_naive


# ============================================================================
# Enums
# ============================================================================


class DebugSeverity(str, Enum):
    """Severity level for debug diagnostics"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ConnectionStatus(str, Enum):
    """Connection status for services"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ============================================================================
# General Debug Schemas
# ============================================================================


class EnvironmentVariable(BaseModel):
    """Safe environment variable (sanitized)"""

    key: str = Field(..., description="Environment variable key")
    value: str = Field(..., description="Sanitized value (masked if sensitive)")
    is_set: bool = Field(..., description="Whether the variable is set")
    is_masked: bool = Field(False, description="Whether the value is masked")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "DATABASE_URL",
                "value": "postgresql://***:***@localhost:5432/***",
                "is_set": True,
                "is_masked": True,
            }
        }
    )


class EnvironmentInfo(BaseModel):
    """Safe environment information (whitelist only)"""

    environment: str = Field(
        ..., description="Environment name (dev/staging/production)"
    )
    debug_mode: bool = Field(..., description="Debug mode status")
    python_version: str = Field(..., description="Python version")
    variables: List[EnvironmentVariable] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=now_sao_paulo_naive)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "environment": "development",
                "debug_mode": True,
                "python_version": "3.11.0",
                "variables": [
                    {
                        "key": "DATABASE_URL",
                        "value": "postgresql://***",
                        "is_set": True,
                        "is_masked": True,
                    }
                ],
                "timestamp": "2025-11-07T10:00:00-03:00",
            }
        }
    )


class DatabasePoolInfo(BaseModel):
    """Database connection pool information"""

    size: int = Field(..., description="Current pool size")
    checked_out: int = Field(..., description="Connections in use")
    overflow: int = Field(..., description="Overflow connections")
    checked_in: int = Field(..., description="Available connections")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"size": 10, "checked_out": 3, "overflow": 0, "checked_in": 7}
        }
    )


class DatabaseDiagnostics(BaseModel):
    """Database connection diagnostics"""

    status: ConnectionStatus = Field(..., description="Database connection status")
    connected: bool = Field(..., description="Whether connected to database")
    pool_info: Optional[DatabasePoolInfo] = Field(
        None, description="Connection pool info"
    )
    response_time_ms: Optional[float] = Field(
        None, description="Query response time (ms)"
    )
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    timestamp: datetime = Field(default_factory=now_sao_paulo_naive)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "connected": True,
                "pool_info": {
                    "size": 10,
                    "checked_out": 3,
                    "overflow": 0,
                    "checked_in": 7,
                },
                "response_time_ms": 2.5,
                "timestamp": "2025-11-07T10:00:00-03:00",
            }
        }
    )


class TestQueryRequest(BaseModel):
    """Request to test SQL query execution (sanitized)"""

    query: str = Field(
        ..., max_length=1000, description="SQL query to test (read-only)"
    )
    timeout_seconds: int = Field(5, ge=1, le=30, description="Query timeout in seconds")

    @field_validator("query")
    @classmethod
    def validate_query_safety(cls, v):
        """Ensure query is read-only (SELECT only)"""
        query_upper = v.strip().upper()

        # Only allow SELECT statements
        if not query_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        # Block dangerous keywords
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "EXEC",
            "EXECUTE",
            "GRANT",
            "REVOKE",
        ]
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"Dangerous keyword '{keyword}' not allowed")

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "SELECT COUNT(*) FROM users WHERE is_active = true",
                "timeout_seconds": 5,
            }
        }
    )


class TestQueryResult(BaseModel):
    """Result of test query execution"""

    success: bool = Field(..., description="Whether query executed successfully")
    rows_returned: Optional[int] = Field(None, description="Number of rows returned")
    execution_time_ms: Optional[float] = Field(None, description="Execution time (ms)")
    result: Optional[List[Dict[str, Any]]] = Field(
        None, description="Query results (limited)"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    query_sanitized: str = Field(..., description="Sanitized query (safe to display)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "rows_returned": 1,
                "execution_time_ms": 3.2,
                "result": [{"count": 42}],
                "query_sanitized": "SELECT COUNT(*) FROM users...",
            }
        }
    )


# ============================================================================
# Auth Debug Schemas
# ============================================================================


class TokenClaim(BaseModel):
    """JWT token claim (masked if sensitive)"""

    claim: str = Field(..., description="Claim name")
    value: Any = Field(..., description="Claim value (masked if sensitive)")
    is_masked: bool = Field(False, description="Whether value is masked")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "claim": "user_id",
                "value": "123e4567-e89b-12d3-a456-426614174000",
                "is_masked": False,
            }
        }
    )


class TokenDebugInfo(BaseModel):
    """Decoded JWT token information (sensitive data masked)"""

    valid: bool = Field(..., description="Whether token is valid")
    expired: bool = Field(..., description="Whether token is expired")
    claims: List[TokenClaim] = Field(default_factory=list)
    issued_at: Optional[datetime] = Field(None, description="Token issue time")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")
    error: Optional[str] = Field(None, description="Error if invalid")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "expired": False,
                "claims": [
                    {"claim": "user_id", "value": "123e4567", "is_masked": False},
                    {"claim": "role", "value": "admin", "is_masked": False},
                ],
                "issued_at": "2025-11-07T10:00:00-03:00",
                "expires_at": "2025-11-08T10:00:00-03:00",
            }
        }
    )


class LoginTestRequest(BaseModel):
    """Request to test login flow"""

    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password")
    skip_2fa: bool = Field(True, description="Skip 2FA for testing")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin@test.com",
                "password": "TestPassword123",
                "skip_2fa": True,
            }
        }
    )


class LoginTestResult(BaseModel):
    """Result of login flow test"""

    success: bool = Field(..., description="Whether login succeeded")
    user_found: bool = Field(..., description="Whether user exists")
    password_valid: bool = Field(..., description="Whether password is valid")
    account_active: bool = Field(..., description="Whether account is active")
    account_locked: bool = Field(False, description="Whether the account is currently locked")
    session_created: bool = Field(..., description="Whether session creation would succeed")
    token_generated: Optional[str] = Field(None, description="Compatibility-only masked session/token marker")
    error: Optional[str] = Field(None, description="Human-readable diagnostic summary")
    error_code: Optional[str] = Field(None, description="Stable auth error code for failed diagnostics")
    steps_completed: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "user_found": True,
                "password_valid": True,
                "account_active": True,
                "account_locked": False,
                "session_created": True,
                "token_generated": "session_***",
                "steps_completed": ["user_lookup", "password_verify", "account_status_check", "session_create_simulated"],
            }
        }
    )


class PermissionTestRequest(BaseModel):
    """Request to test permission checks"""

    user_id: str = Field(..., description="User ID to test")
    permission: str = Field(..., description="Permission to check")
    resource_id: Optional[str] = Field(None, description="Resource ID (if applicable)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "permission": "patients:read",
                "resource_id": "patient_123",
            }
        }
    )


class PermissionTestResult(BaseModel):
    """Result of permission check test"""

    has_permission: bool = Field(..., description="Whether user has permission")
    user_role: str = Field(..., description="User's role")
    permissions_granted: List[str] = Field(default_factory=list)
    reason: Optional[str] = Field(None, description="Reason for decision")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "has_permission": True,
                "user_role": "admin",
                "permissions_granted": ["patients:read", "patients:write", "admin:*"],
                "reason": "Admin role has all permissions",
            }
        }
    )


class AuthSimulationRequest(BaseModel):
    """Request to simulate user authentication"""

    user_id: str = Field(..., description="User ID to simulate")
    simulate_session: bool = Field(True, description="Create temporary session")
    duration_minutes: int = Field(
        5, ge=1, le=60, description="Session duration (max 60 min)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "simulate_session": True,
                "duration_minutes": 5,
            }
        }
    )


class AuthSimulationResult(BaseModel):
    """Result of authentication simulation"""

    success: bool = Field(..., description="Whether simulation succeeded")
    session_id: Optional[str] = Field(None, description="Temporary session ID")
    token: Optional[str] = Field(None, description="Temporary auth token (masked)")
    expires_at: Optional[datetime] = Field(None, description="Session expiration")
    user_info: Optional[Dict[str, Any]] = Field(None, description="Simulated user info")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "session_id": "debug_sess_abc123",
                "token": "debug_***...***",
                "expires_at": "2025-11-07T10:05:00-03:00",
                "user_info": {
                    "id": "123e4567",
                    "email": "admin@test.com",
                    "role": "admin",
                },
            }
        }
    )


# ============================================================================
# Debug Session Management
# ============================================================================


class DebugSession(BaseModel):
    """Debug session tracking"""

    session_id: str = Field(..., description="Debug session ID")
    admin_user_id: str = Field(..., description="Admin user who started session")
    admin_email: str = Field(..., description="Admin email")
    started_at: datetime = Field(default_factory=now_sao_paulo_naive)
    expires_at: datetime = Field(..., description="Session expiration (max 1 hour)")
    operations_count: int = Field(0, description="Number of debug operations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "debug_sess_abc123",
                "admin_user_id": "admin_123",
                "admin_email": "admin@test.com",
                "started_at": "2025-11-07T10:00:00-03:00",
                "expires_at": "2025-11-07T11:00:00-03:00",
                "operations_count": 5,
            }
        }
    )


class DebugAuditLog(BaseModel):
    """Audit log for debug operations"""

    id: str = Field(..., description="Audit log ID")
    timestamp: datetime = Field(default_factory=now_sao_paulo_naive)
    admin_user_id: str = Field(..., description="Admin user ID")
    admin_email: str = Field(..., description="Admin email")
    endpoint: str = Field(..., description="Debug endpoint called")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result_summary: str = Field(..., description="Sanitized result summary")
    ip_address: Optional[str] = Field(None, description="Request IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    severity: DebugSeverity = Field(DebugSeverity.INFO)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "audit_123",
                "timestamp": "2025-11-07T10:00:00-03:00",
                "admin_user_id": "admin_123",
                "admin_email": "admin@test.com",
                "endpoint": "/api/v2/debug/database",
                "parameters": {},
                "result_summary": "Database healthy, 10ms response",
                "ip_address": "192.168.1.1",
                "severity": "info",
            }
        }
    )


# ============================================================================
# Response Wrappers
# ============================================================================


class DebugResponse(BaseModel):
    """Standard debug response wrapper"""

    success: bool = Field(..., description="Whether operation succeeded")
    data: Any = Field(..., description="Debug data")
    audit_logged: bool = Field(True, description="Whether operation was audit logged")
    timestamp: datetime = Field(default_factory=now_sao_paulo_naive)
    warning: Optional[str] = Field(None, description="Security warning if applicable")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {"status": "healthy"},
                "audit_logged": True,
                "timestamp": "2025-11-07T10:00:00-03:00",
                "warning": "Debug mode enabled - disable in production",
            }
        }
    )


class DebugErrorResponse(BaseModel):
    """Debug error response"""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    audit_logged: bool = Field(True, description="Whether error was audit logged")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "DebugDisabled",
                "message": "Debug endpoints are disabled in production",
                "audit_logged": True,
            }
        }
    )
