#!/usr/bin/env python3
"""
Generate Postman collection from OpenAPI specification.

This script converts the FastAPI OpenAPI schema into a Postman Collection v2.1 format
with complete request examples, authentication, environments, and test scripts.

Usage:
    python scripts/generate_postman_collection.py

Output:
    - backend-hormonia/postman/Backend_Hormonia_API.postman_collection.json
    - backend-hormonia/postman/Development.postman_environment.json
    - backend-hormonia/postman/Production.postman_environment.json

Requirements:
    - FastAPI application must be importable
    - OpenAPI schema must be available from app.openapi()
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import FastAPI app
from app.main import app


def get_openapi_schema() -> Dict[str, Any]:
    """Get OpenAPI schema from FastAPI app."""
    return app.openapi()


def convert_path_to_postman_format(path: str) -> List[str]:
    """
    Convert OpenAPI path to Postman format.

    Example:
        /api/v2/patients/{patient_id} -> ["api", "v2", "patients", ":patient_id"]
    """
    parts = path.strip('/').split('/')
    return [f":{part[1:-1]}" if part.startswith('{') else part for part in parts]


def get_method_description(method: str, details: Dict) -> str:
    """Generate method description from OpenAPI details."""
    summary = details.get('summary', '')
    description = details.get('description', '')

    if summary and description:
        return f"{summary}\n\n{description}"
    return summary or description or f"{method.upper()} request"


def extract_request_body(details: Dict) -> Dict[str, Any]:
    """Extract request body example from OpenAPI schema."""
    if 'requestBody' not in details:
        return {"mode": "raw", "raw": ""}

    content = details['requestBody'].get('content', {})
    json_content = content.get('application/json', {})

    # Try to get example from schema
    example = json_content.get('example')
    if example:
        return {
            "mode": "raw",
            "raw": json.dumps(example, indent=2),
            "options": {
                "raw": {
                    "language": "json"
                }
            }
        }

    # Try to get example from schema examples
    schema = json_content.get('schema', {})
    if 'example' in schema:
        return {
            "mode": "raw",
            "raw": json.dumps(schema['example'], indent=2),
            "options": {
                "raw": {
                    "language": "json"
                }
            }
        }

    return {"mode": "raw", "raw": ""}


def extract_query_parameters(details: Dict) -> List[Dict]:
    """Extract query parameters from OpenAPI schema."""
    parameters = details.get('parameters', [])
    return [
        {
            "key": param['name'],
            "value": param.get('example', ''),
            "description": param.get('description', ''),
            "disabled": not param.get('required', False)
        }
        for param in parameters
        if param.get('in') == 'query'
    ]


def extract_path_parameters(details: Dict) -> List[Dict]:
    """Extract path parameters from OpenAPI schema."""
    parameters = details.get('parameters', [])
    return [
        {
            "key": param['name'],
            "value": param.get('example', ''),
            "description": param.get('description', '')
        }
        for param in parameters
        if param.get('in') == 'path'
    ]


def generate_test_script(method: str, path: str, details: Dict) -> str:
    """Generate Postman test script for endpoint."""
    tests = []

    # Status code test
    expected_status = 200
    if method.lower() == 'post':
        expected_status = 201
    elif method.lower() == 'delete':
        expected_status = 204

    tests.append(f"""
// Test: Status code is {expected_status}
pm.test("Status code is {expected_status}", function () {{
    pm.response.to.have.status({expected_status});
}});
""")

    # Response time test
    tests.append("""
// Test: Response time is acceptable
pm.test("Response time is less than 2000ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});
""")

    # JSON response test
    if method.lower() in ['get', 'post', 'patch', 'put']:
        tests.append("""
// Test: Response is JSON
pm.test("Response is JSON", function () {
    pm.response.to.be.json;
});
""")

    # Extract variables from response
    if method.lower() == 'post' and 'id' in path.lower():
        tests.append("""
// Store created resource ID
if (pm.response.code === 201) {
    const jsonData = pm.response.json();
    if (jsonData.id) {
        pm.environment.set("last_created_id", jsonData.id);
    }
}
""")

    # Token extraction for auth endpoints
    if 'auth' in path.lower() and 'login' in path.lower():
        tests.append("""
// Store authentication token
if (pm.response.code === 200) {
    const jsonData = pm.response.json();
    if (jsonData.access_token) {
        pm.environment.set("jwt_token", jsonData.access_token);
        pm.environment.set("refresh_token", jsonData.refresh_token);
    }
}
""")

    return ''.join(tests)


def create_postman_request(path: str, method: str, details: Dict) -> Dict:
    """Create Postman request from OpenAPI path definition."""
    # Generate request name
    name = details.get('summary', f"{method.upper()} {path}")

    # Build request
    request = {
        "name": name,
        "request": {
            "method": method.upper(),
            "header": [
                {
                    "key": "Content-Type",
                    "value": "application/json",
                    "type": "text"
                }
            ],
            "url": {
                "raw": "{{base_url}}" + path,
                "host": ["{{base_url}}"],
                "path": convert_path_to_postman_format(path)
            },
            "description": get_method_description(method, details)
        },
        "response": [],
        "event": [
            {
                "listen": "test",
                "script": {
                    "exec": generate_test_script(method, path, details).split('\n'),
                    "type": "text/javascript"
                }
            }
        ]
    }

    # Add request body if applicable
    if method.upper() in ['POST', 'PUT', 'PATCH']:
        request['request']['body'] = extract_request_body(details)

    # Add query parameters
    query_params = extract_query_parameters(details)
    if query_params:
        request['request']['url']['query'] = query_params

    # Add path variables
    path_params = extract_path_parameters(details)
    if path_params:
        request['request']['url']['variable'] = path_params

    # Add authentication if not a public endpoint
    if not any(tag in path.lower() for tag in ['public', 'health', 'docs']):
        request['request']['auth'] = {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{jwt_token}}",
                    "type": "string"
                }
            ]
        }

    return request


def organize_endpoints_by_folder(schema: Dict) -> Dict[str, List]:
    """Organize endpoints into folders by tag/path."""
    folders: Dict[str, List] = {}

    for path, methods in schema.get('paths', {}).items():
        for method, details in methods.items():
            if method in ['get', 'post', 'put', 'patch', 'delete']:
                # Determine folder name from tags or path
                tags = details.get('tags', [])
                folder_name = tags[0] if tags else path.split('/')[2] if len(path.split('/')) > 2 else 'Other'

                if folder_name not in folders:
                    folders[folder_name] = []

                folders[folder_name].append(
                    create_postman_request(path, method, details)
                )

    return folders


def create_postman_collection() -> Dict:
    """Create complete Postman collection from OpenAPI schema."""
    schema = get_openapi_schema()

    # Create collection info
    collection = {
        "info": {
            "name": "Backend Hormonia API",
            "description": schema.get('info', {}).get('description', 'Complete API collection for Backend Hormonia'),
            "version": schema.get('info', {}).get('version', '2.1.0'),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "_postman_id": "backend-hormonia-api-collection",
            "_exporter_id": "backend-hormonia"
        },
        "item": [],
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{jwt_token}}",
                    "type": "string"
                }
            ]
        },
        "variable": [
            {
                "key": "base_url",
                "value": "http://localhost:8000",
                "type": "string"
            },
            {
                "key": "jwt_token",
                "value": "",
                "type": "string"
            },
            {
                "key": "refresh_token",
                "value": "",
                "type": "string"
            },
            {
                "key": "patient_id",
                "value": "",
                "type": "string"
            },
            {
                "key": "quiz_session_id",
                "value": "",
                "type": "string"
            },
            {
                "key": "last_created_id",
                "value": "",
                "type": "string"
            }
        ]
    }

    # Organize endpoints into folders
    folders = organize_endpoints_by_folder(schema)

    # Sort folders for consistent ordering
    folder_order = [
        'Health', 'Authentication', 'Patients', 'Quiz', 'Messages',
        'Flows', 'Alerts', 'Reports', 'Admin', 'Debug'
    ]

    for folder_name in folder_order:
        if folder_name in folders:
            collection['item'].append({
                "name": folder_name,
                "item": folders[folder_name]
            })

    # Add remaining folders
    for folder_name, items in sorted(folders.items()):
        if folder_name not in folder_order:
            collection['item'].append({
                "name": folder_name,
                "item": items
            })

    return collection


def create_environment(name: str, base_url: str) -> Dict:
    """Create Postman environment file."""
    return {
        "id": f"backend-hormonia-{name.lower()}",
        "name": f"Backend Hormonia - {name}",
        "values": [
            {
                "key": "base_url",
                "value": base_url,
                "type": "default",
                "enabled": True
            },
            {
                "key": "jwt_token",
                "value": "",
                "type": "secret",
                "enabled": True
            },
            {
                "key": "refresh_token",
                "value": "",
                "type": "secret",
                "enabled": True
            },
            {
                "key": "patient_id",
                "value": "",
                "type": "default",
                "enabled": True
            },
            {
                "key": "quiz_session_id",
                "value": "",
                "type": "default",
                "enabled": True
            }
        ],
        "_postman_variable_scope": "environment",
        "_postman_exported_at": datetime.utcnow().isoformat() + 'Z',
        "_postman_exported_using": "Backend Hormonia Generator"
    }


def main():
    """Main execution function."""
    print("🚀 Generating Postman Collection from OpenAPI Schema...")
    print()

    # Create output directory
    output_dir = project_root / "postman"
    output_dir.mkdir(exist_ok=True)

    # Generate Postman collection
    print("📦 Generating Postman collection...")
    collection = create_postman_collection()

    collection_file = output_dir / "Backend_Hormonia_API.postman_collection.json"
    with open(collection_file, 'w', encoding='utf-8') as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)

    print(f"✅ Collection saved: {collection_file}")
    print(f"   Endpoints: {sum(len(folder['item']) for folder in collection['item'])}")

    # Generate environments
    print()
    print("🌍 Generating Postman environments...")

    environments = {
        "Development": "http://localhost:8000",
        "Staging": "https://api-staging.hormonia.example.com",
        "Production": "https://api.hormonia.example.com"
    }

    for env_name, base_url in environments.items():
        env_data = create_environment(env_name, base_url)
        env_file = output_dir / f"{env_name}.postman_environment.json"

        with open(env_file, 'w', encoding='utf-8') as f:
            json.dump(env_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Environment saved: {env_file}")

    # Generate README
    print()
    print("📖 Generating Postman README...")

    readme_content = f"""# Postman Collection - Backend Hormonia API

Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
Version: {collection['info']['version']}

## Files

- `Backend_Hormonia_API.postman_collection.json` - Complete API collection
- `Development.postman_environment.json` - Local development environment
- `Staging.postman_environment.json` - Staging environment
- `Production.postman_environment.json` - Production environment

## Import to Postman

1. Open Postman
2. Click **Import** button
3. Select **Upload Files**
4. Import `Backend_Hormonia_API.postman_collection.json`
5. Import environment file (Development/Staging/Production)

## Usage

### 1. Select Environment

In Postman, select the environment you want to use:
- **Development** - `http://localhost:8000`
- **Staging** - `https://api-staging.hormonia.example.com`
- **Production** - `https://api.hormonia.example.com`

### 2. Authentication

Most endpoints require authentication. Follow these steps:

1. Go to **Authentication** folder
2. Run **Login** request
   - Update email/password in request body
3. JWT token will be automatically saved to `jwt_token` environment variable
4. All subsequent requests will use this token

### 3. Run Requests

Requests are organized by functionality:
- **Health** - Health check endpoints
- **Authentication** - Login, register, refresh token
- **Patients** - Patient CRUD operations
- **Quiz** - Quiz session management
- **Messages** - WhatsApp messaging
- **Flows** - Flow engine operations
- **Alerts** - Alert management
- **Reports** - Medical reports
- **Admin** - Administrative operations

### 4. Test Scripts

All requests include automatic test scripts that:
- Verify status codes
- Check response times
- Validate JSON responses
- Extract and store variables (IDs, tokens, etc.)

### 5. Variables

The following variables are available:
- `{{{{base_url}}}}` - API base URL
- `{{{{jwt_token}}}}` - Authentication token (auto-populated after login)
- `{{{{patient_id}}}}` - Last created patient ID
- `{{{{quiz_session_id}}}}` - Last created quiz session ID
- `{{{{last_created_id}}}}` - Last created resource ID

## CI/CD Integration (Newman)

Run Postman collection in CI/CD pipelines using Newman:

```bash
# Install Newman
npm install -g newman

# Run collection with Development environment
newman run Backend_Hormonia_API.postman_collection.json \\
  -e Development.postman_environment.json \\
  --reporters cli,json \\
  --reporter-json-export results.json

# Run with custom environment variables
newman run Backend_Hormonia_API.postman_collection.json \\
  -e Production.postman_environment.json \\
  --env-var "base_url=https://api.production.com" \\
  --env-var "jwt_token=${{JWT_TOKEN}}"
```

## GitHub Actions Integration

See `.github/workflows/postman-tests.yml` for automated API testing.

## Regenerating Collection

To regenerate this collection from the latest OpenAPI schema:

```bash
cd backend-hormonia
python scripts/generate_postman_collection.py
```

## Support

For API documentation, see:
- Swagger UI: `{{{{base_url}}}}/docs`
- ReDoc: `{{{{base_url}}}}/redoc`
- OpenAPI JSON: `{{{{base_url}}}}/openapi.json`
- API Examples: `docs/api/EXAMPLES.md`
"""

    readme_file = output_dir / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"✅ README saved: {readme_file}")

    print()
    print("=" * 60)
    print("✨ Postman Collection Generated Successfully!")
    print("=" * 60)
    print()
    print(f"📁 Output directory: {output_dir}")
    print(f"📊 Total endpoints: {sum(len(folder['item']) for folder in collection['item'])}")
    print(f"📂 Total folders: {len(collection['item'])}")
    print()
    print("Next steps:")
    print("1. Import collection to Postman")
    print("2. Select environment (Development/Staging/Production)")
    print("3. Run Authentication > Login to get JWT token")
    print("4. Start testing endpoints!")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error generating Postman collection: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
