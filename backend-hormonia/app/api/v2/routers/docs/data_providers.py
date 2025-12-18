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
            "endpoint": None,
            "created_at": "2025-01-01T00:00:00Z",
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
