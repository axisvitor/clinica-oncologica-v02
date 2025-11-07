"""
Documentation schemas for API v2
Models for API documentation, guides, examples, and changelog.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


# ==================== API Endpoint Documentation ====================

class APIEndpointParameter(BaseModel):
    """API endpoint parameter schema."""

    name: str = Field(..., description="Parameter name")
    in_: str = Field(..., alias="in", description="Parameter location (path, query, header)")
    description: Optional[str] = Field(None, description="Parameter description")
    required: bool = Field(False, description="Whether parameter is required")
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema", description="Parameter schema")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "name": "patient_id",
                "in": "path",
                "description": "Patient UUID",
                "required": True,
                "schema": {"type": "string", "format": "uuid"}
            }
        }


class APIEndpointResponse(BaseModel):
    """Basic API endpoint information."""

    id: str = Field(..., description="Endpoint unique identifier")
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Endpoint path")
    summary: str = Field(..., description="Brief summary")
    description: str = Field(..., description="Detailed description")
    tags: List[str] = Field(..., description="Endpoint tags")
    category: str = Field(..., description="Primary category")
    requires_auth: bool = Field(..., description="Whether authentication is required")
    deprecated: bool = Field(False, description="Whether endpoint is deprecated")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "a1b2c3d4e5f6",
                "method": "GET",
                "path": "/api/v2/patients",
                "summary": "List patients",
                "description": "Retrieve paginated list of patients",
                "tags": ["Patients", "List"],
                "category": "Patients",
                "requires_auth": True,
                "deprecated": False
            }
        }


class APIEndpointDetail(APIEndpointResponse):
    """Detailed API endpoint documentation."""

    parameters: List[Dict[str, Any]] = Field([], description="Endpoint parameters")
    request_body: Optional[Dict[str, Any]] = Field(None, description="Request body schema")
    responses: Dict[str, Any] = Field({}, description="Response schemas")
    related_endpoints: List[Dict[str, str]] = Field([], description="Related endpoints")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "a1b2c3d4e5f6",
                "method": "GET",
                "path": "/api/v2/patients",
                "summary": "List patients",
                "description": "Retrieve paginated list of patients with filtering",
                "tags": ["Patients"],
                "category": "Patients",
                "requires_auth": True,
                "deprecated": False,
                "parameters": [
                    {"name": "limit", "in": "query", "description": "Page size"}
                ],
                "request_body": None,
                "responses": {
                    "200": {"description": "Successful response"}
                },
                "related_endpoints": [
                    {"method": "GET", "path": "/api/v2/patients/{id}", "summary": "Get patient"}
                ]
            }
        }


class APIEndpointList(BaseModel):
    """List of API endpoints."""

    data: List[APIEndpointResponse] = Field(..., description="Endpoint list")
    by_category: Dict[str, List[APIEndpointResponse]] = Field({}, description="Endpoints grouped by category")
    total: int = Field(..., description="Total endpoint count")
    categories: List[str] = Field(..., description="Available categories")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "by_category": {
                    "Patients": [],
                    "Authentication": []
                },
                "total": 45,
                "categories": ["Patients", "Authentication", "Reports"]
            }
        }


# ==================== Guides & Tutorials ====================

class GuideResponse(BaseModel):
    """Basic guide information."""

    id: str = Field(..., description="Guide ID")
    slug: str = Field(..., description="URL-friendly slug")
    title: str = Field(..., description="Guide title")
    description: str = Field(..., description="Brief description")
    category: str = Field(..., description="Guide category")
    tags: List[str] = Field(..., description="Guide tags")
    order: int = Field(..., description="Display order")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "getting-started",
                "slug": "getting-started",
                "title": "Getting Started",
                "description": "Quick start guide for the Hormonia API",
                "category": "basics",
                "tags": ["basics", "quickstart"],
                "order": 1,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-17T00:00:00Z"
            }
        }


class GuideDetail(GuideResponse):
    """Detailed guide with full content."""

    content: str = Field(..., description="Full guide content in Markdown")
    related_guides: List[Dict[str, str]] = Field([], description="Related guides")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "getting-started",
                "slug": "getting-started",
                "title": "Getting Started",
                "description": "Quick start guide",
                "category": "basics",
                "tags": ["basics"],
                "order": 1,
                "content": "# Getting Started\n\nWelcome to the API...",
                "related_guides": [
                    {"id": "authentication", "slug": "authentication", "title": "Authentication"}
                ],
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-17T00:00:00Z"
            }
        }


class GuideList(BaseModel):
    """List of documentation guides."""

    data: List[GuideResponse] = Field(..., description="Guide list")
    total: int = Field(..., description="Total guide count")
    categories: List[str] = Field(..., description="Available categories")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "total": 5,
                "categories": ["basics", "security", "performance"]
            }
        }


# ==================== Code Examples ====================

class CodeExampleResponse(BaseModel):
    """Basic code example information."""

    id: str = Field(..., description="Example ID")
    title: str = Field(..., description="Example title")
    description: str = Field(..., description="Example description")
    category: str = Field(..., description="Example category")
    language: str = Field(..., description="Programming language")
    tags: List[str] = Field(..., description="Example tags")
    endpoint: Optional[str] = Field(None, description="Related endpoint")
    created_at: str = Field(..., description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "example-001",
                "title": "List Patients with Pagination",
                "description": "Retrieve paginated list of patients",
                "category": "patients",
                "language": "python",
                "tags": ["python", "pagination"],
                "endpoint": "/api/v2/patients",
                "created_at": "2025-01-01T00:00:00Z"
            }
        }


class CodeExampleDetail(CodeExampleResponse):
    """Detailed code example with full source."""

    code: str = Field(..., description="Full source code")
    related_examples: List[Dict[str, str]] = Field([], description="Related examples")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "example-001",
                "title": "List Patients",
                "description": "Retrieve patients",
                "category": "patients",
                "language": "python",
                "tags": ["python"],
                "endpoint": "/api/v2/patients",
                "code": "import requests\n\nresponse = requests.get(...)",
                "related_examples": [
                    {"id": "example-002", "title": "Create Patient", "language": "python"}
                ],
                "created_at": "2025-01-01T00:00:00Z"
            }
        }


class CodeExampleList(BaseModel):
    """List of code examples."""

    data: List[CodeExampleResponse] = Field(..., description="Example list")
    total: int = Field(..., description="Total example count")
    languages: List[str] = Field(..., description="Available languages")
    categories: List[str] = Field(..., description="Available categories")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "total": 10,
                "languages": ["python", "javascript", "curl"],
                "categories": ["patients", "authentication"]
            }
        }


# ==================== Search ====================

class DocumentationSearchResult(BaseModel):
    """Single search result."""

    type: str = Field(..., description="Result type (endpoint, guide, example)")
    id: str = Field(..., description="Result ID")
    title: str = Field(..., description="Result title")
    description: str = Field(..., description="Result description")
    content_preview: str = Field(..., description="Content preview")
    relevance_score: float = Field(..., ge=0, description="Relevance score")
    url: str = Field(..., description="Result URL")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "guide",
                "id": "getting-started",
                "title": "Getting Started",
                "description": "Quick start guide",
                "content_preview": "Welcome to the Hormonia API...",
                "relevance_score": 0.95,
                "url": "/api/v2/docs/guides/getting-started"
            }
        }


class DocumentationSearchResponse(BaseModel):
    """Documentation search results."""

    query: str = Field(..., description="Search query")
    results: List[DocumentationSearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total result count")
    types: List[str] = Field(..., description="Result types found")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "authentication",
                "results": [],
                "total": 15,
                "types": ["guide", "endpoint", "example"]
            }
        }


# ==================== Changelog & Versions ====================

class APIChange(BaseModel):
    """Single API change."""

    type: str = Field(..., description="Change type (added, changed, fixed, removed, deprecated)")
    category: str = Field(..., description="Change category")
    description: str = Field(..., description="Change description")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "added",
                "category": "api",
                "description": "New V2 API with improved performance"
            }
        }


class APIVersion(BaseModel):
    """API version information."""

    version: str = Field(..., description="Version number")
    release_date: str = Field(..., description="Release date")
    status: str = Field(..., description="Version status (stable, deprecated, beta)")
    breaking_changes: bool = Field(..., description="Whether version has breaking changes")
    changes: List[APIChange] = Field(..., description="Version changes")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "2.0.0",
                "release_date": "2025-01-17",
                "status": "stable",
                "breaking_changes": True,
                "changes": [
                    {
                        "type": "added",
                        "category": "api",
                        "description": "New V2 API"
                    }
                ]
            }
        }


class APIChangelogResponse(BaseModel):
    """Complete API changelog."""

    versions: List[APIVersion] = Field(..., description="All API versions")
    current_version: str = Field(..., description="Current API version")
    latest_stable: str = Field(..., description="Latest stable version")
    deprecated_versions: List[str] = Field(..., description="Deprecated versions")

    class Config:
        json_schema_extra = {
            "example": {
                "versions": [],
                "current_version": "2.0.0",
                "latest_stable": "2.0.0",
                "deprecated_versions": ["1.0.0"]
            }
        }


class APIVersionResponse(BaseModel):
    """Current API version information."""

    version: str = Field(..., description="API version")
    release_date: str = Field(..., description="Release date")
    status: str = Field(..., description="Version status")
    documentation_url: str = Field(..., description="Documentation URL")
    openapi_url: str = Field(..., description="OpenAPI spec URL")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "2.0.0",
                "release_date": "2025-01-17",
                "status": "stable",
                "documentation_url": "/api/v2/docs",
                "openapi_url": "/api/v2/openapi.json"
            }
        }


# ==================== Statistics & Metadata ====================

class DocumentationStatsResponse(BaseModel):
    """Documentation statistics."""

    total_endpoints: int = Field(..., description="Total endpoint count")
    total_guides: int = Field(..., description="Total guide count")
    total_examples: int = Field(..., description="Total example count")
    categories: List[str] = Field(..., description="Available categories")
    languages: List[str] = Field(..., description="Available programming languages")
    last_updated: str = Field(..., description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "total_endpoints": 45,
                "total_guides": 5,
                "total_examples": 10,
                "categories": ["Patients", "Authentication"],
                "languages": ["python", "javascript", "curl"],
                "last_updated": "2025-01-17T15:00:00Z"
            }
        }


class OpenAPISchemaResponse(BaseModel):
    """OpenAPI schema response."""

    openapi: str = Field(..., description="OpenAPI version")
    info: Dict[str, Any] = Field(..., description="API info")
    servers: List[Dict[str, str]] = Field(..., description="API servers")
    paths: Dict[str, Any] = Field(..., description="API paths")
    components: Dict[str, Any] = Field(..., description="Reusable components")

    class Config:
        json_schema_extra = {
            "example": {
                "openapi": "3.0.2",
                "info": {
                    "title": "Hormonia API",
                    "version": "2.0.0"
                },
                "servers": [
                    {"url": "https://api.hormonia.com"}
                ],
                "paths": {},
                "components": {}
            }
        }
