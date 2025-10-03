"""
API documentation endpoints for Hormonia Backend System.
"""
import json
from typing import Any
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from fastapi import Request
from app.utils.openapi_tools import (
    generate_postman_collection, 
    get_api_version_info,
    validate_openapi_spec,
    generate_api_changelog
)
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get(
    "/postman-collection",
    response_model=None,
    summary="Generate Postman Collection",
    description="""
    Generate and download a Postman collection for the Hormonia API.
    
    This endpoint creates a complete Postman collection with:
    - All API endpoints organized by functionality
    - Example requests and responses
    - Authentication configuration
    - Environment variables setup
    
    **Usage**: Import the downloaded JSON file into Postman to start testing the API.
    """,
    responses={
        200: {
            "description": "Postman collection generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "info": {
                            "name": "Hormonia Backend API - API Collection",
                            "version": "1.0.0"
                        },
                        "item": []
                    }
                }
            }
        }
    }
)
async def get_postman_collection(request: Request, current_user: User = Depends(get_current_user)) -> Response:
    """Generate Postman collection for API testing."""
    collection = generate_postman_collection(request.app)
    
    # Set appropriate headers for download
    headers = {
        "Content-Disposition": "attachment; filename=hormonia_api_collection.json",
        "Content-Type": "application/json"
    }
    
    return Response(
        content=json.dumps(collection, indent=2),
        media_type="application/json",
        headers=headers
    )


@router.get(
    "/openapi-spec",
    response_model=None,
    summary="Get OpenAPI Specification",
    description="""
    Retrieve the complete OpenAPI 3.0 specification for the Hormonia API.
    
    This endpoint returns the raw OpenAPI specification that can be used with:
    - API documentation generators
    - Code generation tools
    - API testing frameworks
    - Integration with other systems
    """,
    responses={
        200: {
            "description": "OpenAPI specification retrieved successfully"
        }
    }
)
async def get_openapi_spec(request: Request, current_user: User = Depends(get_current_user)) -> JSONResponse:
    """Get the OpenAPI specification."""
    return JSONResponse(content=request.app.openapi())


@router.get(
    "/version-info",
    response_model=None,
    summary="Get API Version Information",
    description="""
    Retrieve information about API versioning strategy and compatibility.
    
    This endpoint provides details about:
    - Current and supported API versions
    - Versioning strategy and policies
    - Deprecation timeline and migration guides
    - Backward and forward compatibility information
    """,
    responses={
        200: {
            "description": "Version information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "current_version": "v1",
                        "supported_versions": ["v1"],
                        "version_strategy": "url_path",
                        "deprecation_policy": {
                            "notice_period": "6 months",
                            "support_period": "12 months"
                        }
                    }
                }
            }
        }
    }
)
async def get_version_info() -> dict[str, Any]:
    """Get API versioning information."""
    return get_api_version_info()


@router.get(
    "/health-check",
    response_model=None,
    summary="API Health Check",
    description="""
    Check the health and availability of the API documentation system.
    
    This endpoint provides status information about:
    - API documentation generation
    - OpenAPI specification validity
    - System readiness for documentation requests
    """,
    responses={
        200: {
            "description": "Documentation system is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "documentation": "available",
                        "openapi_version": "3.0.2",
                        "endpoints_count": 45
                    }
                }
            }
        }
    }
)
async def docs_health_check(request: Request) -> dict[str, Any] | JSONResponse:
    """Health check for documentation system."""
    try:
        # Test OpenAPI generation
        openapi_spec = request.app.openapi()
        endpoints_count = len([
            path for path, methods in openapi_spec.get("paths", {}).items()
            for method in methods.keys()
        ])
        
        return {
            "status": "healthy",
            "documentation": "available",
            "openapi_version": openapi_spec.get("openapi", "unknown"),
            "endpoints_count": endpoints_count,
            "api_version": request.app.version,
            "title": request.app.title
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "documentation": "unavailable",
                "error": str(e)
            }
        )


@router.get(
    "/endpoint-summary",
    response_model=None,
    summary="Get API Endpoints Summary",
    description="""
    Retrieve a summary of all available API endpoints organized by functionality.
    
    This provides a quick overview of:
    - Available endpoints grouped by tags
    - HTTP methods and paths
    - Authentication requirements
    - Brief descriptions
    """,
    responses={
        200: {
            "description": "Endpoints summary retrieved successfully"
        }
    }
)
async def get_endpoints_summary(request: Request, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Get summary of all API endpoints."""
    openapi_spec = request.app.openapi()
    
    summary = {
        "api_info": {
            "title": openapi_spec.get("info", {}).get("title"),
            "version": openapi_spec.get("info", {}).get("version"),
            "description": openapi_spec.get("info", {}).get("description")
        },
        "endpoints_by_tag": {}
    }
    
    # Group endpoints by tags
    for path, methods in openapi_spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                tags = operation.get("tags", ["Uncategorized"])
                tag = tags[0] if tags else "Uncategorized"
                
                if tag not in summary["endpoints_by_tag"]:
                    summary["endpoints_by_tag"][tag] = []
                
                summary["endpoints_by_tag"][tag].append({
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", "")[:100] + "..." if len(operation.get("description", "")) > 100 else operation.get("description", ""),
                    "requires_auth": "security" in operation or any(auth_tag in ["Patients", "Messages", "Reports"] for auth_tag in tags)
                })
    
    return summary


@router.get(
    "/validate-spec",
    response_model=None,
    summary="Validate OpenAPI Specification",
    description="""
    Validate the OpenAPI specification for completeness and correctness.
    
    This endpoint performs comprehensive validation including:
    - Required fields presence
    - Schema structure validation
    - Documentation completeness check
    - Security configuration validation
    - Response examples coverage
    """,
    responses={
        200: {
            "description": "Validation results",
            "content": {
                "application/json": {
                    "example": {
                        "valid": True,
                        "errors": [],
                        "warnings": ["2 endpoints missing descriptions"],
                        "info": {
                            "total_endpoints": 45,
                            "endpoints_with_descriptions": 43,
                            "endpoints_with_examples": 40
                        }
                    }
                }
            }
        }
    }
)
async def validate_openapi_specification(request: Request, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Validate the OpenAPI specification."""
    return validate_openapi_spec(request.app)


@router.get(
    "/changelog",
    response_model=None,
    summary="Get API Changelog",
    description="""
    Retrieve the API changelog with version history and changes.
    
    This endpoint provides:
    - Version history with dates
    - Added, changed, and removed features
    - Breaking changes and migration notes
    - Deprecation notices
    """,
    responses={
        200: {
            "description": "API changelog retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "version": "1.0.0",
                            "date": "2024-01-01",
                            "type": "major",
                            "changes": [
                                {
                                    "type": "added",
                                    "description": "Initial API release"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }
)
async def get_api_changelog() -> list[dict[str, Any]]:
    """Get API changelog."""
    return generate_api_changelog()


@router.get(
    "/schema-download",
    response_model=None,
    summary="Download OpenAPI Schema",
    description="""
    Download the OpenAPI schema as a JSON file.
    
    This endpoint provides the complete OpenAPI 3.0 specification
    as a downloadable JSON file that can be used with:
    - API documentation tools
    - Code generators
    - Testing frameworks
    """,
    responses={
        200: {
            "description": "OpenAPI schema file",
            "content": {
                "application/json": {
                    "schema": {"type": "object"}
                }
            }
        }
    }
)
async def download_openapi_schema(request: Request, current_user: User = Depends(get_current_user)) -> Response:
    """Download OpenAPI schema as JSON file."""
    openapi_spec = request.app.openapi()
    
    headers = {
        "Content-Disposition": "attachment; filename=hormonia_openapi_schema.json",
        "Content-Type": "application/json"
    }
    
    return Response(
        content=json.dumps(openapi_spec, indent=2),
        media_type="application/json",
        headers=headers
    )