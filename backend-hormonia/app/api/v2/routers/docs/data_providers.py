"""
Data providers for documentation content.
Provides static guides, examples, changelog, and OpenAPI extraction.
"""

import hashlib
from typing import List, Dict, Any


def extract_openapi_endpoints(app) -> List[Dict[str, Any]]:
    """
    Extract endpoints from OpenAPI specification.

    Args:
        app: FastAPI application instance

    Returns:
        List of endpoint dictionaries with metadata
    """
    openapi_spec = app.openapi()
    endpoints = []

    for path, methods in openapi_spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                tags = operation.get("tags", ["Uncategorized"])
                tag = tags[0] if tags else "Uncategorized"

                endpoints.append(
                    {
                        "id": hashlib.md5(
                            f"{method.upper()}:{path}".encode()
                        ).hexdigest()[:16],
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
                    }
                )

    return endpoints


def get_static_guides() -> List[Dict[str, Any]]:
    """
    Get static documentation guides.

    Returns:
        List of guide dictionaries with content
    """
    return [
        {
            "id": "getting-started",
            "slug": "getting-started",
            "title": "Getting Started",
            "description": "Quick start guide for the Hormonia API",
            "category": "basics",
            "content": """# Getting Started with Hormonia API

## Authentication

The Hormonia API uses cookie-backed session authentication for operator and admin traffic.

### Steps to Authenticate:
1. POST your credentials to `/api/v2/auth/login`
2. Store the `session_id` cookie returned by the server
3. Send subsequent requests with the same session cookie

## Making Your First Request

```bash
curl -X GET "https://api.hormonia.com/api/v2/patients" \\
  --cookie "session_id=your-session-id"
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
            "created_at": "2025-01-01T00:00:00-03:00",
            "updated_at": "2025-01-17T00:00:00-03:00",
        },
        {
            "id": "authentication",
            "slug": "authentication",
            "title": "Authentication Guide",
            "description": "Complete guide to API authentication",
            "category": "security",
            "content": """# Authentication

## Session-Based Authentication

Hormonia authenticates operator and admin requests with a server-issued `session_id` cookie.

### Login Flow
1. POST credentials to `/api/v2/auth/login`
2. Receive `Set-Cookie: session_id=...` in the response
3. Persist that cookie in your HTTP client
4. Send subsequent requests with the stored cookie

### Session Transport
Authenticated requests rely on the `session_id` cookie set during login.

### Session Expiration
Sessions expire after 7 days of inactivity.

### Security Best Practices
- Let your HTTP client manage the session cookie
- Use HTTPS in production
- Clear the session cookie on logout
- Handle 401 errors gracefully
""",
            "tags": ["authentication", "security", "sessions"],
            "order": 2,
            "created_at": "2025-01-01T00:00:00-03:00",
            "updated_at": "2025-01-17T00:00:00-03:00",
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
            "created_at": "2025-01-01T00:00:00-03:00",
            "updated_at": "2025-01-17T00:00:00-03:00",
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
            "created_at": "2025-01-01T00:00:00-03:00",
            "updated_at": "2025-01-17T00:00:00-03:00",
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
            "created_at": "2025-01-01T00:00:00-03:00",
            "updated_at": "2025-01-17T00:00:00-03:00",
        },
    ]


def get_static_examples() -> List[Dict[str, Any]]:
    """
    Get static code examples.

    Returns:
        List of code example dictionaries
    """
    return [
        {
            "id": "example-001",
            "title": "List Patients with Pagination",
            "description": "Retrieve paginated list of patients",
            "category": "patients",
            "language": "python",
            "code": """import requests

session = requests.Session()
session.cookies.set("session_id", "your-session-id")

url = "https://api.hormonia.com/api/v2/patients"
params = {"limit": 20}

response = session.get(url, params=params)
data = response.json()

for patient in data["data"]:
    print(f"Patient: {patient['full_name']}")

# Get next page
if data["has_more"]:
    params["cursor"] = data["next_cursor"]
    next_response = session.get(url, params=params)
""",
            "tags": ["python", "patients", "pagination"],
            "endpoint": "/api/v2/patients",
            "created_at": "2025-01-01T00:00:00-03:00",
        },
        {
            "id": "example-002",
            "title": "Create New Patient",
            "description": "Create a new patient record",
            "category": "patients",
            "language": "javascript",
            "code": """const axios = require('axios');

const api = axios.create({
  baseURL: 'https://api.hormonia.com',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
});

const createPatient = async () => {
  // Assumes /api/v2/auth/login already established the session cookie.
  const response = await api.post('/api/v2/patients', {
    full_name: 'João Silva',
    email: 'joao@example.com',
    birth_date: '1980-01-15',
    phone: '+5511999999999'
  });

  console.log('Patient created:', response.data);
};

createPatient();
""",
            "tags": ["javascript", "patients", "create"],
            "endpoint": "/api/v2/patients",
            "created_at": "2025-01-01T00:00:00-03:00",
        },
        {
            "id": "example-003",
            "title": "Authentication Flow",
            "description": "Complete cookie-backed session login flow",
            "category": "authentication",
            "language": "python",
            "code": """import requests

session = requests.Session()

login_response = session.post(
    'https://api.hormonia.com/api/v2/auth/login',
    json={'email': 'operator@example.com', 'password': 'S3curePass!123'}
)
login_response.raise_for_status()

print('Session cookie established.')

patients = session.get('https://api.hormonia.com/api/v2/patients')
patients.raise_for_status()

for patient in patients.json()["data"]:
    print(patient["full_name"])
""",
            "tags": ["python", "authentication", "sessions"],
            "endpoint": "/api/v2/auth/login",
            "created_at": "2025-01-01T00:00:00-03:00",
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
            "created_at": "2025-01-01T00:00:00-03:00",
        },
        {
            "id": "example-005",
            "title": "Error Handling Best Practices",
            "description": "Handle API errors gracefully",
            "category": "best-practices",
            "language": "javascript",
            "code": """const axios = require('axios');

const api = axios.create({
  baseURL: 'https://api.hormonia.com',
  withCredentials: true
});

async function makeApiRequest(url, options = {}) {
  try {
    const response = await api.get(url, {
      params: options.params
    });

    return { success: true, data: response.data };

  } catch (error) {
    if (error.response) {
      // Server responded with error
      const { status, data } = error.response;

      switch (status) {
        case 401:
          console.error('Session expired or missing:', data.message);
          break;
        case 429:
          console.error('Rate limit exceeded');
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
  '/api/v2/patients',
  { params: { limit: 20 } }
);

if (result.success) {
  console.log('Data:', result.data);
} else {
  console.error('Error:', result.error);
}
""",
            "tags": ["javascript", "error-handling", "best-practices"],
            "endpoint": None,
            "created_at": "2025-01-01T00:00:00-03:00",
        },
    ]


def get_changelog_data() -> List[Dict[str, Any]]:
    """
    Get API changelog data.

    Returns:
        List of version changelog dictionaries
    """
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
