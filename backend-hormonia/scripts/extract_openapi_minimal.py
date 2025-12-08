#!/usr/bin/env python3
"""
Extract OpenAPI schema from FastAPI app using minimal initialization.
Bypasses full middleware and monitoring setup to avoid configuration errors.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def create_minimal_app():
    """Create minimal FastAPI app for schema extraction."""
    from fastapi import FastAPI
    from fastapi.openapi.utils import get_openapi

    # Import router
    from app.api.v2.router import api_v2_router

    # Create minimal app
    app = FastAPI(
        title="Hormonia Healthcare Platform API",
        version="2.0.0",
        description="Healthcare communication platform for hormone therapy patients"
    )

    # Include main router
    app.include_router(api_v2_router)

    return app


def enhance_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Add comprehensive enhancements to OpenAPI schema."""

    # Enhanced API description
    schema["info"]["description"] = """
# Hormonia Healthcare Platform API

A comprehensive healthcare communication platform for oncology patients undergoing hormone therapy.

## Overview

The Hormonia Backend System provides a complete suite of APIs for managing patient engagement,
medical assessments, and healthcare provider workflows. The platform integrates WhatsApp messaging,
AI-powered personalization, and comprehensive reporting capabilities.

## Key Capabilities

### Patient Management
- Complete patient lifecycle management with Brazilian healthcare compliance (CPF, SUS)
- Treatment tracking and medication management
- Flow-based patient journey orchestration

### Communication & Messaging
- WhatsApp integration for automated patient engagement
- AI-powered message personalization using Google Gemini
- Real-time WebSocket updates for healthcare providers
- Multi-language support for patient communications

### Medical Assessments
- Structured quiz system for health data collection
- Monthly wellness questionnaires
- Automated risk detection and alerting
- Physician risk assessment workflows

### Analytics & Reporting
- Comprehensive patient analytics and insights
- PDF report generation with customizable templates
- Real-time dashboard metrics
- A/B testing for engagement optimization

### Security & Compliance
- JWT-based authentication with refresh tokens
- Role-based access control (RBAC)
- CSRF protection for session-based authentication
- Rate limiting and API key support
- HIPAA-compliant data handling

## Authentication

This API supports two authentication methods:

### 1. Bearer Token (JWT)
Recommended for programmatic access and API integrations.

```bash
# Login to get tokens
curl -X POST https://api.hormonia.com/api/v2/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email": "user@example.com", "password": "password"}'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}

# Use access token in requests
curl https://api.hormonia.com/api/v2/patients \\
  -H "Authorization: Bearer <access_token>"
```

### 2. API Key
For service-to-service authentication.

```bash
curl https://api.hormonia.com/api/v2/patients \\
  -H "X-API-Key: <your_api_key>"
```

## Rate Limiting

All endpoints are rate limited to ensure fair usage:
- **Default**: 100 requests per minute per IP
- **Authentication endpoints**: 10 requests per minute per IP
- **Heavy operations**: 20 requests per minute per IP

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets (Unix timestamp)

When rate limit is exceeded, API returns HTTP 429 with `Retry-After` header.

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "additional_context"
  },
  "request_id": "req_123456789",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes
- `VALIDATION_ERROR` (422): Request validation failed
- `UNAUTHORIZED` (401): Authentication required
- `FORBIDDEN` (403): Insufficient permissions
- `NOT_FOUND` (404): Resource not found
- `RATE_LIMIT_EXCEEDED` (429): Too many requests
- `INTERNAL_SERVER_ERROR` (500): Server error

## Pagination

List endpoints support pagination with the following parameters:

```
GET /api/v2/patients?limit=20&offset=0
```

**Parameters:**
- `limit`: Number of results per page (default: 20, max: 100)
- `offset`: Number of results to skip (default: 0)

**Response includes pagination metadata:**
```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

## Webhooks

The API supports webhook notifications for events:
- Patient status changes
- Quiz completions
- Alert triggers
- Flow state transitions

Configure webhooks in the admin panel at `/api/v2/admin/webhooks`.

## Data Types

### Date/Time Format
All timestamps use ISO 8601 format in UTC timezone:
```
2024-01-15T10:30:00Z
```

### UUID Format
All resource IDs use UUID v4 format:
```
550e8400-e29b-41d4-a716-446655440000
```

### Brazilian Data Types
- **CPF**: 11-digit Brazilian taxpayer ID (validated with check digits)
- **Phone**: Brazilian phone format with country code (+55)
- **SUS Card**: Brazilian universal health system card number

## Versioning

This is API v2. All endpoints are prefixed with `/api/v2`.

Previous versions:
- `/api/v1` - Deprecated (EOL: 2024-12-31)

## Support

- **Documentation**: https://docs.hormonia.com
- **API Status**: https://status.hormonia.com
- **Support Email**: support@hormonia.com
- **Developer Portal**: https://developers.hormonia.com
"""

    # Add contact and license info
    schema["info"]["contact"] = {
        "name": "Hormonia API Support",
        "email": "support@hormonia.com",
        "url": "https://hormonia.com/support"
    }

    schema["info"]["license"] = {
        "name": "Proprietary",
        "url": "https://hormonia.com/terms"
    }

    # Add servers
    schema["servers"] = [
        {
            "url": "https://api.hormonia.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.hormonia.com",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        }
    ]

    # Ensure components exist
    if "components" not in schema:
        schema["components"] = {}

    # Add security schemes
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT bearer token obtained from /api/v2/auth/login endpoint. Include in Authorization header as: `Bearer <token>`"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service authentication. Contact support to obtain an API key."
        }
    }

    # Add common response schemas
    if "schemas" not in schema["components"]:
        schema["components"]["schemas"] = {}

    schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "required": ["error", "message", "timestamp"],
        "properties": {
            "error": {
                "type": "string",
                "description": "Machine-readable error code",
                "example": "VALIDATION_ERROR"
            },
            "message": {
                "type": "string",
                "description": "Human-readable error message",
                "example": "Request validation failed"
            },
            "details": {
                "type": "object",
                "description": "Additional error context",
                "additionalProperties": True
            },
            "request_id": {
                "type": "string",
                "description": "Unique request identifier for debugging",
                "example": "req_123456789abc"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "ISO 8601 timestamp",
                "example": "2024-01-15T10:30:00Z"
            }
        }
    }

    schema["components"]["schemas"]["PaginationMeta"] = {
        "type": "object",
        "properties": {
            "total": {
                "type": "integer",
                "description": "Total number of items",
                "example": 150
            },
            "limit": {
                "type": "integer",
                "description": "Number of items per page",
                "example": 20
            },
            "offset": {
                "type": "integer",
                "description": "Number of items skipped",
                "example": 0
            },
            "has_more": {
                "type": "boolean",
                "description": "Whether more items are available",
                "example": True
            }
        }
    }

    # Add common examples
    if "examples" not in schema["components"]:
        schema["components"]["examples"] = {}

    schema["components"]["examples"]["ValidationError"] = {
        "summary": "Validation Error",
        "value": {
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {
                "errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "type": "value_error.email"
                    }
                ]
            },
            "request_id": "req_abc123",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    }

    schema["components"]["examples"]["UnauthorizedError"] = {
        "summary": "Unauthorized",
        "value": {
            "error": "UNAUTHORIZED",
            "message": "Authentication credentials required",
            "details": {},
            "request_id": "req_abc123",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    }

    # Add comprehensive tags
    schema["tags"] = [
        {"name": "auth-v2", "description": "Authentication and authorization (JWT, API keys)"},
        {"name": "patients-crud-v2", "description": "Patient CRUD operations"},
        {"name": "patients-flow-v2", "description": "Patient flow management and state transitions"},
        {"name": "patients-import-v2", "description": "Bulk patient import and data migration"},
        {"name": "patients-integrity-v2", "description": "Data integrity checks and validation"},
        {"name": "quiz-v2", "description": "Medical questionnaires and assessments"},
        {"name": "monthly-quiz-v2", "description": "Monthly wellness questionnaires"},
        {"name": "quiz-responses-v2", "description": "Quiz response management"},
        {"name": "quiz-alerts-v2", "description": "Quiz-based alert triggers"},
        {"name": "messages-v2", "description": "WhatsApp messaging and conversations"},
        {"name": "enhanced-messages-v2", "description": "Advanced messaging features"},
        {"name": "flows-v2", "description": "Conversation flow orchestration"},
        {"name": "flow-templates-v2", "description": "Flow template management"},
        {"name": "ai-v2", "description": "AI-powered features and analytics"},
        {"name": "reports-v2", "description": "Report generation and PDF export"},
        {"name": "enhanced-reports-v2", "description": "Advanced reporting features"},
        {"name": "analytics-v2", "description": "Patient and system analytics"},
        {"name": "enhanced-analytics-v2", "description": "Advanced analytics and insights"},
        {"name": "alerts-v2", "description": "Alert management and notifications"},
        {"name": "dashboard-v2", "description": "Dashboard metrics and KPIs"},
        {"name": "admin-v2", "description": "Administrative operations"},
        {"name": "admin-extensions-v2", "description": "Extended admin features"},
        {"name": "roles-v2", "description": "Role-based access control"},
        {"name": "physicians-v2", "description": "Physician management and workflows"},
        {"name": "appointments-v2", "description": "Appointment scheduling"},
        {"name": "treatments-v2", "description": "Treatment tracking"},
        {"name": "medications-v2", "description": "Medication management"},
        {"name": "webhooks-v2", "description": "Webhook endpoints and integrations"},
        {"name": "health-v2", "description": "System health monitoring"},
        {"name": "performance-v2", "description": "Performance metrics"},
        {"name": "system-v2", "description": "System configuration"},
        {"name": "upload-v2", "description": "File upload handling"},
        {"name": "localization-v2", "description": "Multi-language support"},
        {"name": "tasks-v2", "description": "Background task management"},
        {"name": "platform-sync-v2", "description": "External platform synchronization"},
        {"name": "ab-testing-v2", "description": "A/B testing and experiments"},
        {"name": "docs-v2", "description": "API documentation"},
    ]

    return schema


def main():
    """Generate enhanced OpenAPI specification."""
    print("🚀 Generating OpenAPI specification...")

    try:
        print("📦 Creating minimal FastAPI app...")
        app = create_minimal_app()

        print("📋 Extracting base OpenAPI schema...")
        base_schema = app.openapi()

        print("✨ Enhancing schema with comprehensive documentation...")
        enhanced_schema = enhance_schema(base_schema)

        # Save to file
        output_path = project_root / "docs" / "api" / "openapi.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"💾 Saving to {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_schema, f, indent=2, ensure_ascii=False)

        # Print stats
        endpoint_count = len(enhanced_schema.get("paths", {}))
        schema_count = len(enhanced_schema.get("components", {}).get("schemas", {}))
        tag_count = len(enhanced_schema.get("tags", []))

        print("\n✅ OpenAPI specification generated successfully!")
        print(f"📊 Statistics:")
        print(f"   - Endpoints: {endpoint_count}")
        print(f"   - Schemas: {schema_count}")
        print(f"   - Tags: {tag_count}")
        print(f"   - Output: {output_path}")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
