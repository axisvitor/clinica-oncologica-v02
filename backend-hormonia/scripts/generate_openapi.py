#!/usr/bin/env python3
"""
Generate comprehensive OpenAPI 3.0 specification for Hormonia Backend API.

This script extracts the OpenAPI schema from the FastAPI application and enhances it with:
- Detailed endpoint descriptions
- Request/response examples
- Authentication documentation
- Rate limiting information
- Error response schemas
"""
import json
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.application_factory import create_application


def enhance_openapi_schema(schema: dict) -> dict:
    """
    Enhance the base OpenAPI schema with additional documentation.

    Args:
        schema: Base OpenAPI schema from FastAPI

    Returns:
        Enhanced OpenAPI schema with comprehensive documentation
    """
    # Add comprehensive API information
    schema["info"].update({
        "title": "Hormonia Healthcare Platform API",
        "version": "2.0.0",
        "description": """
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

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "additional_context"
  },
  "request_id": "req_123456789",
  "timestamp": "2024-01-01T00:00:00Z"
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

List endpoints support cursor-based pagination:

```
GET /api/v2/patients?limit=20&offset=0
```

Parameters:
- `limit`: Number of results per page (default: 20, max: 100)
- `offset`: Number of results to skip (default: 0)

Response includes pagination metadata:
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

## Versioning

This is API v2. The base path for all endpoints is `/api/v2`.

## Support

- Documentation: https://docs.hormonia.com
- API Status: https://status.hormonia.com
- Support: support@hormonia.com
""",
        "contact": {
            "name": "Hormonia Support",
            "email": "support@hormonia.com",
            "url": "https://hormonia.com/support"
        },
        "license": {
            "name": "Proprietary",
            "url": "https://hormonia.com/terms"
        }
    })

    # Add server information
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

    # Ensure components structure exists
    if "components" not in schema:
        schema["components"] = {}

    if "securitySchemes" not in schema["components"]:
        schema["components"]["securitySchemes"] = {}

    if "examples" not in schema["components"]:
        schema["components"]["examples"] = {}

    if "responses" not in schema["components"]:
        schema["components"]["responses"] = {}

    # Add comprehensive security schemes
    schema["components"]["securitySchemes"].update({
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
    })

    # Add common response examples
    schema["components"]["examples"].update({
        "ValidationError": {
            "summary": "Validation Error Example",
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
                "request_id": "req_123456789abc",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        },
        "UnauthorizedError": {
            "summary": "Unauthorized Access Example",
            "value": {
                "error": "UNAUTHORIZED",
                "message": "Authentication credentials required",
                "details": {},
                "request_id": "req_123456789abc",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        },
        "ForbiddenError": {
            "summary": "Forbidden Access Example",
            "value": {
                "error": "FORBIDDEN",
                "message": "Insufficient permissions to access this resource",
                "details": {
                    "required_role": "admin",
                    "current_role": "user"
                },
                "request_id": "req_123456789abc",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        },
        "NotFoundError": {
            "summary": "Resource Not Found Example",
            "value": {
                "error": "NOT_FOUND",
                "message": "The requested resource was not found",
                "details": {
                    "resource_type": "patient",
                    "resource_id": "550e8400-e29b-41d4-a716-446655440000"
                },
                "request_id": "req_123456789abc",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        },
        "RateLimitError": {
            "summary": "Rate Limit Exceeded Example",
            "value": {
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "details": {
                    "limit": 100,
                    "window": "1 minute",
                    "retry_after": 45
                },
                "request_id": "req_123456789abc",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        },
        "InternalServerError": {
            "summary": "Internal Server Error Example",
            "value": {
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
                "request_id": "req_123456789abc",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    })

    # Add common response schemas
    schema["components"]["responses"].update({
        "ValidationError": {
            "description": "Request validation failed",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "examples": {
                        "validation_error": {
                            "$ref": "#/components/examples/ValidationError"
                        }
                    }
                }
            }
        },
        "UnauthorizedError": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "examples": {
                        "unauthorized": {
                            "$ref": "#/components/examples/UnauthorizedError"
                        }
                    }
                }
            }
        },
        "ForbiddenError": {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "examples": {
                        "forbidden": {
                            "$ref": "#/components/examples/ForbiddenError"
                        }
                    }
                }
            }
        },
        "NotFoundError": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "examples": {
                        "not_found": {
                            "$ref": "#/components/examples/NotFoundError"
                        }
                    }
                }
            }
        },
        "RateLimitError": {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "examples": {
                        "rate_limit": {
                            "$ref": "#/components/examples/RateLimitError"
                        }
                    }
                }
            },
            "headers": {
                "X-RateLimit-Limit": {
                    "description": "Maximum requests allowed",
                    "schema": {"type": "integer"}
                },
                "X-RateLimit-Remaining": {
                    "description": "Remaining requests in current window",
                    "schema": {"type": "integer"}
                },
                "X-RateLimit-Reset": {
                    "description": "Time when rate limit resets (Unix timestamp)",
                    "schema": {"type": "integer"}
                },
                "Retry-After": {
                    "description": "Seconds until rate limit resets",
                    "schema": {"type": "integer"}
                }
            }
        },
        "InternalServerError": {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    },
                    "examples": {
                        "server_error": {
                            "$ref": "#/components/examples/InternalServerError"
                        }
                    }
                }
            }
        }
    })

    # Add error response schema if not present
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
                "description": "Additional error context and details",
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
                "description": "ISO 8601 timestamp when error occurred",
                "example": "2024-01-15T10:30:00Z"
            }
        }
    }

    # Add tags with enhanced descriptions
    schema["tags"] = [
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints. Supports JWT bearer tokens and API keys.",
            "externalDocs": {
                "description": "Authentication Guide",
                "url": "https://docs.hormonia.com/authentication"
            }
        },
        {
            "name": "Patients",
            "description": "Patient management operations including CRUD, flow management, and integrity checks. Supports Brazilian healthcare compliance (CPF, SUS)."
        },
        {
            "name": "Quiz",
            "description": "Medical questionnaire system for health data collection, wellness assessments, and patient monitoring."
        },
        {
            "name": "Monthly Quiz",
            "description": "Monthly wellness questionnaires with automated scheduling and completion tracking."
        },
        {
            "name": "Messages",
            "description": "WhatsApp message handling and conversation management with AI-powered personalization."
        },
        {
            "name": "Flows",
            "description": "State-machine-driven conversation flows for patient engagement journeys."
        },
        {
            "name": "AI Services",
            "description": "AI-powered features including message humanization, risk assessment, and predictive analytics."
        },
        {
            "name": "Reports",
            "description": "Medical report generation with customizable templates and PDF export."
        },
        {
            "name": "Analytics",
            "description": "Patient analytics, engagement metrics, and system insights."
        },
        {
            "name": "Alerts",
            "description": "Automated alert system for risk detection and concerning health patterns."
        },
        {
            "name": "Admin Users",
            "description": "Administrative user management with role-based access control."
        },
        {
            "name": "Health",
            "description": "System health monitoring and status endpoints."
        },
        {
            "name": "Webhooks",
            "description": "Webhook endpoints for external integrations including WhatsApp Evolution API."
        }
    ]

    return schema


def main():
    """Generate and save the enhanced OpenAPI specification."""
    print("🚀 Generating OpenAPI specification...")

    try:
        # Create application instance
        print("📦 Creating FastAPI application...")
        app = create_application(
            enable_monitoring=False,  # Disable monitoring for schema generation
            deployment_mode="development",
            enable_enhanced_openapi=True
        )

        # Get OpenAPI schema
        print("📋 Extracting OpenAPI schema...")
        openapi_schema = app.openapi()

        # Enhance the schema
        print("✨ Enhancing schema with comprehensive documentation...")
        enhanced_schema = enhance_openapi_schema(openapi_schema)

        # Save to file
        output_path = project_root / "docs" / "api" / "openapi.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"💾 Saving OpenAPI specification to {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_schema, f, indent=2, ensure_ascii=False)

        # Print statistics
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
        print(f"\n❌ Error generating OpenAPI specification: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
