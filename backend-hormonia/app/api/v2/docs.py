"""
API Documentation endpoints for V2
Provides comprehensive API documentation with guides, examples, and search capabilities.
Public access endpoints with heavy caching for optimal performance.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import json
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from app.database import get_db
from app.schemas.v2.docs import (
    # API Documentation
    APIEndpointResponse,
    APIEndpointList,
    APIEndpointDetail,

    # Guides
    GuideResponse,
    GuideList,
    GuideDetail,

    # Code Examples
    CodeExampleResponse,
    CodeExampleList,
    CodeExampleDetail,

    # Search & Changelog
    DocumentationSearchResponse,
    APIChangelogResponse,
    APIVersionResponse,

    # Metadata
    DocumentationStatsResponse,
    OpenAPISchemaResponse,
)
from app.schemas.v2.common import ErrorResponse
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configuration (in seconds) - docs rarely change
CACHE_TTL_API_DOCS = 86400  # 24 hours
CACHE_TTL_GUIDES = 43200  # 12 hours
CACHE_TTL_EXAMPLES = 21600  # 6 hours
CACHE_TTL_SEARCH = 3600  # 1 hour

# Rate limits (requests per minute) - public endpoints
RATE_LIMIT_READ = "100/minute"
RATE_LIMIT_SEARCH = "60/minute"


# ==================== Helper Functions ====================

def _get_cache_key(prefix: str, **params) -> str:
    """Generate cache key from prefix and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()
    return f"docs:v2:{prefix}:{param_hash}"


async def _get_cached_result(cache_key: str) -> Optional[Dict]:
    """Get cached result from Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        return None
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


async def _set_cached_result(cache_key: str, data: Dict, ttl: int) -> None:
    """Set cached result in Redis."""
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
        if redis_client is None:
            return
        await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def _extract_openapi_endpoints(app) -> List[Dict[str, Any]]:
    """Extract endpoints from OpenAPI specification."""
    openapi_spec = app.openapi()
    endpoints = []

    for path, methods in openapi_spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                tags = operation.get("tags", ["Uncategorized"])
                tag = tags[0] if tags else "Uncategorized"

                endpoints.append({
                    "id": hashlib.md5(f"{method.upper()}:{path}".encode()).hexdigest()[:16],
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": tags,
                    "category": tag,
                    "requires_auth": "security" in operation,
                    "deprecated": operation.get("deprecated", False),
                    "parameters": operation.get("parameters", []),
                    "request_body": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                })

    return endpoints


def _get_static_guides() -> List[Dict[str, Any]]:
    """Get static documentation guides."""
    return [
        {
            "id": "getting-started",
            "slug": "getting-started",
            "title": "Getting Started",
            "description": "Quick start guide for the Hormonia API",
            "category": "basics",
            "content": """# Getting Started with Hormonia API

## Authentication

The Hormonia API uses session-based authentication with Firebase Auth.

### Steps to Authenticate:
1. Obtain Firebase credentials
2. Create a session via `/api/v2/auth/login`
3. Use session cookie or X-Session-ID header in requests

## Making Your First Request

```bash
curl -X GET "https://api.hormonia.com/api/v2/patients" \\
  -H "X-Session-ID: your-session-id"
```

## Response Format

All responses follow this structure:
- Success: `{"data": [...], "next_cursor": "...", "has_more": true}`
- Error: `{"error": "ErrorType", "message": "Description"}`

## Rate Limits

- Read endpoints: 100 requests/minute
- Write endpoints: 20 requests/minute
- Search endpoints: 60 requests/minute
""",
            "tags": ["basics", "authentication", "quickstart"],
            "order": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-17T00:00:00Z",
        },
        {
            "id": "authentication",
            "slug": "authentication",
            "title": "Authentication Guide",
            "description": "Complete guide to API authentication",
            "category": "security",
            "content": """# Authentication

## Session-Based Authentication

Hormonia uses session-based authentication with Firebase Auth integration.

### Login Flow
1. Authenticate with Firebase
2. POST to `/api/v2/auth/login` with Firebase token
3. Receive session ID in response
4. Use session ID in subsequent requests

### Session Headers
Include session in one of these ways:
- Cookie: `session_id=your-session-id`
- Header: `X-Session-ID: your-session-id`

### Token Expiration
Sessions expire after 7 days of inactivity.

### Security Best Practices
- Store session IDs securely
- Use HTTPS in production
- Implement token refresh flow
- Handle 401 errors gracefully
""",
            "tags": ["authentication", "security", "sessions"],
            "order": 2,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-17T00:00:00Z",
        },
        {
            "id": "pagination",
            "slug": "pagination",
            "title": "Cursor-Based Pagination",
            "description": "How to paginate through large datasets",
            "category": "basics",
            "content": """# Cursor-Based Pagination

## Overview

All list endpoints use cursor-based pagination for efficient data retrieval.

## Parameters
- `cursor`: Pagination cursor (optional, omit for first page)
- `limit`: Items per page (1-100, default: 20)

## Response Format
```json
{
  "data": [...],
  "next_cursor": "eyJpZCI6MTIzfQ==",
  "has_more": true,
  "total": null
}
```

## Example
```python
import requests

url = "https://api.hormonia.com/api/v2/patients"
params = {"limit": 20}

while True:
    response = requests.get(url, params=params)
    data = response.json()

    # Process data["data"]

    if not data["has_more"]:
        break

    params["cursor"] = data["next_cursor"]
```

## Best Practices
- Use reasonable page sizes (20-50 items)
- Store cursors client-side between requests
- Handle empty results gracefully
""",
            "tags": ["pagination", "basics", "best-practices"],
            "order": 3,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-17T00:00:00Z",
        },
        {
            "id": "error-handling",
            "slug": "error-handling",
            "title": "Error Handling",
            "description": "Understanding API errors and how to handle them",
            "category": "basics",
            "content": """# Error Handling

## Error Response Format

```json
{
  "error": "ValidationError",
  "message": "Human-readable error description",
  "details": {},
  "request_id": "req_123abc"
}
```

## HTTP Status Codes

- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Missing/invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Retry Logic

Implement exponential backoff for failed requests:
```python
import time

def retry_request(func, max_retries=3):
    for i in range(max_retries):
        try:
            return func()
        except RequestException:
            if i == max_retries - 1:
                raise
            time.sleep(2 ** i)
```

## Error Types

- `ValidationError`: Invalid request data
- `AuthenticationError`: Auth failure
- `PermissionError`: Insufficient permissions
- `NotFoundError`: Resource not found
- `RateLimitError`: Too many requests
""",
            "tags": ["errors", "best-practices"],
            "order": 4,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-17T00:00:00Z",
        },
        {
            "id": "rate-limiting",
            "slug": "rate-limiting",
            "title": "Rate Limiting",
            "description": "Understanding API rate limits",
            "category": "performance",
            "content": """# Rate Limiting

## Rate Limits by Endpoint Type

- **Read endpoints**: 100 requests/minute
- **Write endpoints**: 20 requests/minute
- **Search endpoints**: 60 requests/minute

## Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Handling Rate Limits

```python
import time
import requests

def make_request_with_retry(url):
    response = requests.get(url)

    if response.status_code == 429:
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        wait_time = reset_time - time.time()

        if wait_time > 0:
            time.sleep(wait_time)
            return make_request_with_retry(url)

    return response
```

## Best Practices

- Monitor rate limit headers
- Implement request queuing
- Use caching when possible
- Batch operations where supported
""",
            "tags": ["rate-limiting", "performance"],
            "order": 5,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-17T00:00:00Z",
        },
    ]


def _get_static_examples() -> List[Dict[str, Any]]:
    """Get static code examples."""
    return [
        {
            "id": "example-001",
            "title": "List Patients with Pagination",
            "description": "Retrieve paginated list of patients",
            "category": "patients",
            "language": "python",
            "code": """import requests

url = "https://api.hormonia.com/api/v2/patients"
headers = {"X-Session-ID": "your-session-id"}
params = {"limit": 20}

response = requests.get(url, headers=headers, params=params)
data = response.json()

for patient in data["data"]:
    print(f"Patient: {patient['full_name']}")

# Get next page
if data["has_more"]:
    params["cursor"] = data["next_cursor"]
    next_response = requests.get(url, headers=headers, params=params)
""",
            "tags": ["python", "patients", "pagination"],
            "endpoint": "/api/v2/patients",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "id": "example-002",
            "title": "Create New Patient",
            "description": "Create a new patient record",
            "category": "patients",
            "language": "javascript",
            "code": """const axios = require('axios');

const createPatient = async () => {
  const response = await axios.post(
    'https://api.hormonia.com/api/v2/patients',
    {
      full_name: 'João Silva',
      email: 'joao@example.com',
      birth_date: '1980-01-15',
      phone: '+5511999999999'
    },
    {
      headers: {
        'X-Session-ID': 'your-session-id',
        'Content-Type': 'application/json'
      }
    }
  );

  console.log('Patient created:', response.data);
};

createPatient();
""",
            "tags": ["javascript", "patients", "create"],
            "endpoint": "/api/v2/patients",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "id": "example-003",
            "title": "Authentication Flow",
            "description": "Complete authentication flow with Firebase",
            "category": "authentication",
            "language": "python",
            "code": """import requests
import firebase_admin
from firebase_admin import auth

# Initialize Firebase
cred = firebase_admin.credentials.Certificate('path/to/serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Get Firebase token
firebase_token = auth.create_custom_token('user-uid')

# Login to Hormonia API
response = requests.post(
    'https://api.hormonia.com/api/v2/auth/login',
    json={'firebase_token': firebase_token.decode()}
)

session_id = response.json()['session_id']
print(f"Logged in with session: {session_id}")

# Use session for authenticated requests
headers = {'X-Session-ID': session_id}
patients = requests.get(
    'https://api.hormonia.com/api/v2/patients',
    headers=headers
)
""",
            "tags": ["python", "authentication", "firebase"],
            "endpoint": "/api/v2/auth/login",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "id": "example-004",
            "title": "Search Documentation",
            "description": "Search API documentation and guides",
            "category": "documentation",
            "language": "curl",
            "code": """# Search for authentication-related docs
curl -X GET "https://api.hormonia.com/api/v2/docs/search?q=authentication&limit=10"

# Get specific guide
curl -X GET "https://api.hormonia.com/api/v2/docs/guides/getting-started"

# List all endpoints
curl -X GET "https://api.hormonia.com/api/v2/docs/endpoints?category=patients"
""",
            "tags": ["curl", "documentation", "search"],
            "endpoint": "/api/v2/docs/search",
            "created_at": "2025-01-01T00:00:00Z",
        },
        {
            "id": "example-005",
            "title": "Error Handling Best Practices",
            "description": "Handle API errors gracefully",
            "category": "best-practices",
            "language": "javascript",
            "code": """const axios = require('axios');

async function makeApiRequest(url, options = {}) {
  try {
    const response = await axios.get(url, {
      headers: {
        'X-Session-ID': options.sessionId
      },
      params: options.params
    });

    return { success: true, data: response.data };

  } catch (error) {
    if (error.response) {
      // Server responded with error
      const { status, data } = error.response;

      switch (status) {
        case 401:
          console.error('Authentication failed:', data.message);
          // Trigger re-authentication
          break;
        case 429:
          console.error('Rate limit exceeded');
          // Implement retry with backoff
          break;
        case 500:
          console.error('Server error:', data.message);
          break;
        default:
          console.error('API error:', data.message);
      }

      return { success: false, error: data };
    }

    // Network error
    console.error('Network error:', error.message);
    return { success: false, error: { message: 'Network error' } };
  }
}

// Usage
const result = await makeApiRequest(
  'https://api.hormonia.com/api/v2/patients',
  { sessionId: 'your-session-id' }
);

if (result.success) {
  console.log('Data:', result.data);
} else {
  console.error('Error:', result.error);
}
""",
            "tags": ["javascript", "error-handling", "best-practices"],
            "endpoint": null,
            "created_at": "2025-01-01T00:00:00Z",
        },
    ]


def _get_changelog_data() -> List[Dict[str, Any]]:
    """Get API changelog data."""
    return [
        {
            "version": "2.0.0",
            "release_date": "2025-01-17",
            "status": "stable",
            "breaking_changes": True,
            "changes": [
                {
                    "type": "added",
                    "category": "api",
                    "description": "New V2 API with modern patterns and improved performance",
                },
                {
                    "type": "added",
                    "category": "pagination",
                    "description": "Cursor-based pagination for all list endpoints",
                },
                {
                    "type": "added",
                    "category": "caching",
                    "description": "Redis caching layer for improved response times",
                },
                {
                    "type": "added",
                    "category": "documentation",
                    "description": "Comprehensive API documentation with guides and examples",
                },
                {
                    "type": "changed",
                    "category": "authentication",
                    "description": "Enhanced session-based authentication with better security",
                },
                {
                    "type": "changed",
                    "category": "rbac",
                    "description": "Improved role-based access control system",
                },
            ],
        },
        {
            "version": "1.5.0",
            "release_date": "2024-12-01",
            "status": "deprecated",
            "breaking_changes": False,
            "changes": [
                {
                    "type": "added",
                    "category": "templates",
                    "description": "Flow template versioning system",
                },
                {
                    "type": "fixed",
                    "category": "quiz",
                    "description": "Quiz submission validation improvements",
                },
            ],
        },
        {
            "version": "1.0.0",
            "release_date": "2024-06-01",
            "status": "deprecated",
            "breaking_changes": False,
            "changes": [
                {
                    "type": "added",
                    "category": "api",
                    "description": "Initial API release with core functionality",
                },
            ],
        },
    ]


# ==================== API Endpoints Documentation ====================

@router.get(
    "/endpoints",
    response_model=APIEndpointList,
    summary="List API endpoints",
    description="Get comprehensive list of all API endpoints with filtering and search",
    responses={
        200: {"description": "List of API endpoints"},
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def list_api_endpoints(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category/tag"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    search: Optional[str] = Query(None, description="Search in path or description"),
    deprecated: Optional[bool] = Query(None, description="Filter by deprecated status"),
    requires_auth: Optional[bool] = Query(None, description="Filter by authentication requirement"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all available API endpoints.

    Returns comprehensive information about each endpoint including:
    - HTTP method and path
    - Summary and description
    - Parameters and request body
    - Response schemas
    - Authentication requirements
    - Tags and categories

    Public endpoint with 24-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("endpoints", category=category, method=method,
                                   search=search, deprecated=deprecated,
                                   requires_auth=requires_auth, limit=limit)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Extract endpoints from OpenAPI spec
        endpoints = _extract_openapi_endpoints(request.app)

        # Apply filters
        filtered = endpoints

        if category:
            filtered = [e for e in filtered if category.lower() in [t.lower() for t in e["tags"]]]

        if method:
            filtered = [e for e in filtered if e["method"].lower() == method.lower()]

        if search:
            search_lower = search.lower()
            filtered = [
                e for e in filtered
                if search_lower in e["path"].lower()
                or search_lower in e["summary"].lower()
                or search_lower in e["description"].lower()
            ]

        if deprecated is not None:
            filtered = [e for e in filtered if e["deprecated"] == deprecated]

        if requires_auth is not None:
            filtered = [e for e in filtered if e["requires_auth"] == requires_auth]

        # Limit results
        total = len(filtered)
        filtered = filtered[:limit]

        # Group by category
        by_category = {}
        for endpoint in filtered:
            cat = endpoint["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(endpoint)

        result = {
            "data": filtered,
            "by_category": by_category,
            "total": total,
            "categories": list(by_category.keys()),
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_API_DOCS)

        return result

    except Exception as e:
        logger.error(f"Error listing endpoints: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API endpoints"
        )


@router.get(
    "/endpoints/{method}/{path:path}",
    response_model=APIEndpointDetail,
    summary="Get endpoint documentation",
    description="Get detailed documentation for a specific endpoint",
    responses={
        200: {"description": "Endpoint documentation"},
        404: {"model": ErrorResponse, "description": "Endpoint not found"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def get_endpoint_documentation(
    request: Request,
    method: str,
    path: str,
):
    """
    Get detailed documentation for a specific API endpoint.

    Returns complete information including:
    - Full description and usage notes
    - Request/response schemas
    - Example requests and responses
    - Error codes and handling
    - Related endpoints

    Public endpoint with 24-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("endpoint_detail", method=method, path=path)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        # Normalize path (add leading slash if missing)
        if not path.startswith("/"):
            path = f"/{path}"

        # Extract endpoints from OpenAPI spec
        endpoints = _extract_openapi_endpoints(request.app)

        # Find matching endpoint
        endpoint = None
        for e in endpoints:
            if e["method"].lower() == method.lower() and e["path"] == path:
                endpoint = e
                break

        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Endpoint {method.upper()} {path} not found"
            )

        # Find related endpoints (same category)
        related = [
            {"method": e["method"], "path": e["path"], "summary": e["summary"]}
            for e in endpoints
            if e["category"] == endpoint["category"] and e["id"] != endpoint["id"]
        ][:5]

        result = {
            **endpoint,
            "related_endpoints": related,
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_API_DOCS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting endpoint documentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get endpoint documentation"
        )


# ==================== Guides & Tutorials ====================

@router.get(
    "/guides",
    response_model=GuideList,
    summary="List documentation guides",
    description="Get list of documentation guides and tutorials",
    responses={
        200: {"description": "List of guides"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def list_guides(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
):
    """
    List all documentation guides and tutorials.

    Guides include:
    - Getting started guides
    - Authentication tutorials
    - Best practices
    - Integration guides
    - Performance optimization tips

    Public endpoint with 12-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("guides_list", category=category, tags=tags)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        guides = _get_static_guides()

        # Apply filters
        if category:
            guides = [g for g in guides if g["category"].lower() == category.lower()]

        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",")]
            guides = [
                g for g in guides
                if any(tag in [t.lower() for t in g["tags"]] for tag in tag_list)
            ]

        # Sort by order
        guides.sort(key=lambda x: x.get("order", 999))

        result = {
            "data": guides,
            "total": len(guides),
            "categories": list(set(g["category"] for g in guides)),
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_GUIDES)

        return result

    except Exception as e:
        logger.error(f"Error listing guides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list guides"
        )


@router.get(
    "/guides/{slug}",
    response_model=GuideDetail,
    summary="Get guide by slug",
    description="Get detailed guide content by slug",
    responses={
        200: {"description": "Guide details"},
        404: {"model": ErrorResponse, "description": "Guide not found"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def get_guide_by_slug(
    request: Request,
    slug: str,
):
    """
    Get detailed guide content by slug.

    Returns guide with full markdown content, metadata, and related guides.

    Public endpoint with 12-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("guide_detail", slug=slug)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        guides = _get_static_guides()

        # Find guide by slug
        guide = None
        for g in guides:
            if g["slug"] == slug:
                guide = g
                break

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guide '{slug}' not found"
            )

        # Find related guides (same category)
        related = [
            {"id": g["id"], "slug": g["slug"], "title": g["title"]}
            for g in guides
            if g["category"] == guide["category"] and g["id"] != guide["id"]
        ]

        result = {
            **guide,
            "related_guides": related,
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_GUIDES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting guide: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get guide"
        )


# ==================== Code Examples ====================

@router.get(
    "/examples",
    response_model=CodeExampleList,
    summary="List code examples",
    description="Get list of code examples for various API operations",
    responses={
        200: {"description": "List of code examples"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def list_code_examples(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    language: Optional[str] = Query(None, description="Filter by programming language"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
):
    """
    List all code examples.

    Examples available for:
    - Python
    - JavaScript/Node.js
    - cURL
    - Multiple API operations

    Public endpoint with 6-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("examples_list", category=category,
                                   language=language, endpoint=endpoint)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        examples = _get_static_examples()

        # Apply filters
        if category:
            examples = [e for e in examples if e["category"].lower() == category.lower()]

        if language:
            examples = [e for e in examples if e["language"].lower() == language.lower()]

        if endpoint:
            examples = [e for e in examples if e.get("endpoint") == endpoint]

        result = {
            "data": examples,
            "total": len(examples),
            "languages": list(set(e["language"] for e in examples)),
            "categories": list(set(e["category"] for e in examples)),
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_EXAMPLES)

        return result

    except Exception as e:
        logger.error(f"Error listing examples: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list code examples"
        )


@router.get(
    "/examples/{example_id}",
    response_model=CodeExampleDetail,
    summary="Get code example by ID",
    description="Get detailed code example by ID",
    responses={
        200: {"description": "Code example details"},
        404: {"model": ErrorResponse, "description": "Example not found"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def get_code_example(
    request: Request,
    example_id: str,
):
    """
    Get detailed code example by ID.

    Returns complete code with:
    - Full source code
    - Explanation and usage notes
    - Related examples
    - Endpoint reference

    Public endpoint with 6-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("example_detail", example_id=example_id)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        examples = _get_static_examples()

        # Find example by ID
        example = None
        for e in examples:
            if e["id"] == example_id:
                example = e
                break

        if not example:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Example '{example_id}' not found"
            )

        # Find related examples (same category or language)
        related = [
            {"id": e["id"], "title": e["title"], "language": e["language"]}
            for e in examples
            if (e["category"] == example["category"] or e["language"] == example["language"])
            and e["id"] != example["id"]
        ][:5]

        result = {
            **example,
            "related_examples": related,
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_EXAMPLES)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting example: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get code example"
        )


# ==================== Search ====================

@router.get(
    "/search",
    response_model=DocumentationSearchResponse,
    summary="Search documentation",
    description="Full-text search across all documentation",
    responses={
        200: {"description": "Search results"},
        400: {"model": ErrorResponse, "description": "Invalid search query"},
    }
)
@limiter.limit(RATE_LIMIT_SEARCH)
async def search_documentation(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type (endpoint, guide, example)"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
):
    """
    Full-text search across all documentation.

    Searches in:
    - API endpoints (path, summary, description)
    - Guides (title, content, tags)
    - Code examples (title, description, code)

    Returns ranked results with relevance scores.

    Public endpoint with 1-hour caching per unique query.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("search", q=q, type=type, limit=limit)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        q_lower = q.lower()
        results = []

        # Search endpoints
        if not type or type == "endpoint":
            endpoints = _extract_openapi_endpoints(request.app)
            for endpoint in endpoints:
                score = 0.0
                if q_lower in endpoint["path"].lower():
                    score += 1.0
                if q_lower in endpoint["summary"].lower():
                    score += 0.8
                if q_lower in endpoint["description"].lower():
                    score += 0.5

                if score > 0:
                    results.append({
                        "type": "endpoint",
                        "id": endpoint["id"],
                        "title": f"{endpoint['method']} {endpoint['path']}",
                        "description": endpoint["summary"],
                        "content_preview": endpoint["description"][:200],
                        "relevance_score": score,
                        "url": f"/api/v2/docs/endpoints/{endpoint['method']}/{endpoint['path']}",
                    })

        # Search guides
        if not type or type == "guide":
            guides = _get_static_guides()
            for guide in guides:
                score = 0.0
                if q_lower in guide["title"].lower():
                    score += 1.0
                if q_lower in guide["description"].lower():
                    score += 0.8
                if q_lower in guide["content"].lower():
                    score += 0.5
                if any(q_lower in tag.lower() for tag in guide["tags"]):
                    score += 0.6

                if score > 0:
                    results.append({
                        "type": "guide",
                        "id": guide["id"],
                        "title": guide["title"],
                        "description": guide["description"],
                        "content_preview": guide["content"][:200],
                        "relevance_score": score,
                        "url": f"/api/v2/docs/guides/{guide['slug']}",
                    })

        # Search examples
        if not type or type == "example":
            examples = _get_static_examples()
            for example in examples:
                score = 0.0
                if q_lower in example["title"].lower():
                    score += 1.0
                if q_lower in example["description"].lower():
                    score += 0.8
                if q_lower in example["code"].lower():
                    score += 0.4

                if score > 0:
                    results.append({
                        "type": "example",
                        "id": example["id"],
                        "title": example["title"],
                        "description": example["description"],
                        "content_preview": example["code"][:200],
                        "relevance_score": score,
                        "url": f"/api/v2/docs/examples/{example['id']}",
                    })

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Limit results
        total = len(results)
        results = results[:limit]

        result = {
            "query": q,
            "results": results,
            "total": total,
            "types": list(set(r["type"] for r in results)),
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_SEARCH)

        return result

    except Exception as e:
        logger.error(f"Error searching documentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documentation"
        )


# ==================== Changelog & Versions ====================

@router.get(
    "/changelog",
    response_model=APIChangelogResponse,
    summary="Get API changelog",
    description="Get complete API version history and changelog",
    responses={
        200: {"description": "API changelog"},
    }
)
@limiter.limit(RATE_LIMIT_READ)
async def get_api_changelog(
    request: Request,
    version: Optional[str] = Query(None, description="Filter by specific version"),
):
    """
    Get API changelog with version history.

    Returns:
    - All API versions
    - Changes for each version
    - Breaking changes
    - Release dates
    - Migration guides

    Public endpoint with 24-hour caching.
    """
    try:
        # Check cache
        cache_key = _get_cache_key("changelog", version=version)
        cached = await _get_cached_result(cache_key)
        if cached:
            return cached

        changelog = _get_changelog_data()

        # Filter by version if specified
        if version:
            changelog = [c for c in changelog if c["version"] == version]
            if not changelog:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {version} not found"
                )

        result = {
            "versions": changelog,
            "current_version": "2.0.0",
            "latest_stable": "2.0.0",
            "deprecated_versions": ["1.0.0", "1.5.0"],
        }

        # Cache result
        await _set_cached_result(cache_key, result, CACHE_TTL_API_DOCS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting changelog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get changelog"
        )
