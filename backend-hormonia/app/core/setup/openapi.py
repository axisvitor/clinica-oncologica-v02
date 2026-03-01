"""
OpenAPI configuration and setup.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def get_api_description(deployment_mode: str = "production") -> str:
    """Get comprehensive API description with deployment-specific information."""
    base_description = """
## Healthcare Communication Platform for Hormone Therapy Patients

The Hormonia Backend System is a comprehensive healthcare communication platform that enables
automated patient engagement through WhatsApp integration, AI-powered conversation flows,
medical questionnaires, and report generation.

### Key Features
- **Patient Management**: Complete patient lifecycle management
- **WhatsApp Integration**: Automated messaging with interactive elements
- **Conversation Flows**: State-machine-driven communication flows
- **AI Personalization**: Google Gemini integration for message humanization
- **Medical Assessments**: Structured quiz system for health data collection
- **Reporting & Analytics**: PDF report generation with insights
- **Real-time Alerts**: Automated detection of concerning patterns
- **WebSocket Communication**: Real-time updates for healthcare providers

### Architecture
This API follows a clean architecture pattern with:
- **Modular Design**: Separated concerns across focused modules
- **Event-Driven**: WebSocket and Redis-based real-time communication
- **Monitoring**: Comprehensive observability with metrics and logging
- **Security**: Enhanced security middleware and rate limiting
- **Scalability**: Redis-backed caching and session management
- **Thread-Safe**: Request-scoped services for multi-worker deployments
"""

    # Add deployment-specific information
    if deployment_mode == "debug":
        base_description += """
### Debug Mode Features
- **Debug Endpoints**: Secured diagnostics under `/api/v2/debug/*` for troubleshooting
- **Enhanced Logging**: Detailed request/response logging
- **Development Tools**: Full OpenAPI documentation available
"""
    elif deployment_mode == "development":
        base_description += """
### Development Environment
- **Enhanced Debugging**: Detailed error messages and stack traces
- **Full Documentation**: Complete OpenAPI specification available
- **Development Tools**: All debugging features enabled
"""

    return base_description


def get_openapi_tags() -> list:
    """Get OpenAPI tags for API documentation."""
    return [
        {
            "name": "Authentication",
            "description": "User authentication and authorization",
        },
        {
            "name": "Admin Users",
            "description": "Administrative user management operations",
        },
        {"name": "Patients", "description": "Patient management operations"},
        {"name": "Messages", "description": "WhatsApp message handling"},
        {"name": "Flows", "description": "Conversation flow management"},
        {"name": "Quiz", "description": "Medical questionnaire system"},
        {"name": "Monthly Quiz", "description": "Monthly wellness questionnaires"},
        {"name": "AI Services", "description": "AI-powered features and analytics"},
        {"name": "Healthcare Metrics", "description": "Clinical metrics and KPIs"},
        {"name": "Reports", "description": "Medical report generation"},
        {"name": "Analytics", "description": "System and patient analytics"},
        {"name": "Enhanced Analytics", "description": "Advanced analytics features"},
        {"name": "Enhanced Messages", "description": "Advanced messaging features"},
        {"name": "Enhanced Quiz", "description": "Advanced quiz features"},
        {"name": "Enhanced Reports", "description": "Advanced reporting features"},
        {"name": "Enhanced Monitoring", "description": "Advanced monitoring features"},
        {"name": "Monitoring", "description": "System monitoring and health checks"},
        {"name": "Health", "description": "System health monitoring"},
        {
            "name": "Performance",
            "description": "Performance monitoring and optimization",
        },
        {"name": "Alerts", "description": "Alert management system"},
        {"name": "Webhooks", "description": "Webhook endpoints for integrations"},
        {"name": "Tasks", "description": "Background task management"},
        {"name": "Localization", "description": "Multi-language support"},
        {"name": "Documentation", "description": "API documentation endpoints"},
        {"name": "Template Management", "description": "Message template management"},
        {"name": "Platform Sync", "description": "External platform synchronization"},
        {"name": "WhatsApp", "description": "WhatsApp integration endpoints"},
        {"name": "Hive-Mind", "description": "AI coordination system"},
        {
            "name": "Debug",
            "description": "Debug and diagnostics endpoints (debug mode only)",
        },
    ]


def setup_enhanced_openapi(app: FastAPI) -> None:
    """Setup enhanced OpenAPI with security schemes (from main_v2.py)."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        # Get base OpenAPI schema from FastAPI
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Ensure components structure exists (robust setdefault pattern)
        openapi_schema.setdefault("components", {})
        openapi_schema["components"].setdefault("securitySchemes", {})
        openapi_schema["components"].setdefault("examples", {})

        # Add security schemes
        openapi_schema["components"]["securitySchemes"].update(
            {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT token obtained from /api/v2/auth/login endpoint",
                },
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key for service-to-service authentication",
                },
            }
        )

        # Add common error response examples (already initialized above)
        openapi_schema["components"]["examples"].update(
            {
                "ValidationError": {
                    "summary": "Validation Error",
                    "value": {
                        "error": "validation_error",
                        "message": "Invalid input data provided",
                        "details": {"field": "email", "issue": "Invalid email format"},
                        "timestamp": "2024-01-01T00:00:00-03:00",
                        "request_id": "req_123456789",
                    },
                },
                "UnauthorizedError": {
                    "summary": "Unauthorized",
                    "value": {
                        "error": "unauthorized",
                        "message": "Authentication credentials required",
                        "details": {},
                        "timestamp": "2024-01-01T00:00:00-03:00",
                        "request_id": "req_123456789",
                    },
                },
                "InternalServerError": {
                    "summary": "Internal Server Error",
                    "value": {
                        "error": "internal_server_error",
                        "message": "An unexpected error occurred",
                        "details": {},
                        "timestamp": "2024-01-01T00:00:00-03:00",
                        "request_id": "req_123456789",
                    },
                },
            }
        )

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
