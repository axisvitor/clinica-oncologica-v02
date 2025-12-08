"""
OpenAPI documentation utilities for Hormonia Backend System.
"""
import json
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def generate_postman_collection(app: FastAPI) -> Dict[str, Any]:
    """
    Generate a Postman collection from FastAPI OpenAPI specification.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Dictionary representing Postman collection v2.1 format
    """
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Base collection structure
    collection = {
        "info": {
            "name": f"{app.title} - API Collection",
            "description": app.description,
            "version": app.version,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{access_token}}",
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
                "key": "access_token",
                "value": "",
                "type": "string"
            },
            {
                "key": "refresh_token",
                "value": "",
                "type": "string"
            }
        ],
        "item": []
    }
    
    # Group endpoints by tags
    folders = {}
    
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                # Get the first tag as folder name
                tags = operation.get("tags", ["Uncategorized"])
                folder_name = tags[0] if tags else "Uncategorized"
                
                if folder_name not in folders:
                    folders[folder_name] = {
                        "name": folder_name,
                        "item": []
                    }
                
                # Create request item
                request_item = _create_postman_request(path, method, operation, openapi_schema)
                folders[folder_name]["item"].append(request_item)
    
    # Add folders to collection
    collection["item"] = list(folders.values())
    
    return collection


def _create_postman_request(path: str, method: str, operation: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Postman request item from OpenAPI operation."""
    
    # Basic request structure
    request = {
        "name": operation.get("summary", f"{method.upper()} {path}"),
        "request": {
            "method": method.upper(),
            "header": [],
            "url": {
                "raw": "{{base_url}}" + path,
                "host": ["{{base_url}}"],
                "path": path.strip("/").split("/") if path != "/" else []
            }
        },
        "response": []
    }
    
    # Add description
    if operation.get("description"):
        request["request"]["description"] = operation["description"]
    
    # Add authentication for protected endpoints
    if "security" in operation or any(tag in ["Patients", "Messages", "Reports"] for tag in operation.get("tags", [])):
        request["request"]["auth"] = {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{access_token}}",
                    "type": "string"
                }
            ]
        }
    
    # Add query parameters
    parameters = operation.get("parameters", [])
    query_params = [p for p in parameters if p.get("in") == "query"]
    
    if query_params:
        request["request"]["url"]["query"] = []
        for param in query_params:
            request["request"]["url"]["query"].append({
                "key": param["name"],
                "value": _get_example_value(param),
                "description": param.get("description", ""),
                "disabled": not param.get("required", False)
            })
    
    # Add path parameters
    path_params = [p for p in parameters if p.get("in") == "path"]
    if path_params:
        request["request"]["url"]["variable"] = []
        for param in path_params:
            request["request"]["url"]["variable"].append({
                "key": param["name"],
                "value": _get_example_value(param),
                "description": param.get("description", "")
            })
    
    # Add request body for POST/PUT/PATCH
    if method.upper() in ["POST", "PUT", "PATCH"] and "requestBody" in operation:
        request_body = operation["requestBody"]
        content = request_body.get("content", {})
        
        if "application/json" in content:
            request["request"]["header"].append({
                "key": "Content-Type",
                "value": "application/json"
            })
            
            # Generate example body from schema
            json_schema = content["application/json"].get("schema", {})
            example_body = _generate_example_from_schema(json_schema, schema)
            
            request["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(example_body, indent=2),
                "options": {
                    "raw": {
                        "language": "json"
                    }
                }
            }
        elif "application/x-www-form-urlencoded" in content:
            request["request"]["header"].append({
                "key": "Content-Type",
                "value": "application/x-www-form-urlencoded"
            })
            
            # For form data (like login)
            form_schema = content["application/x-www-form-urlencoded"].get("schema", {})
            if "properties" in form_schema:
                request["request"]["body"] = {
                    "mode": "urlencoded",
                    "urlencoded": []
                }
                for prop_name, prop_schema in form_schema["properties"].items():
                    request["request"]["body"]["urlencoded"].append({
                        "key": prop_name,
                        "value": _get_example_value({"schema": prop_schema}),
                        "type": "text"
                    })
    
    # Add example responses
    responses = operation.get("responses", {})
    for status_code, response_info in responses.items():
        if status_code.startswith("2"):  # Success responses
            example_response = {
                "name": f"{status_code} - {response_info.get('description', 'Success')}",
                "originalRequest": request["request"].copy(),
                "status": response_info.get("description", "Success"),
                "code": int(status_code),
                "_postman_previewlanguage": "json"
            }
            
            # Add response body example
            content = response_info.get("content", {})
            if "application/json" in content:
                example = content["application/json"].get("example")
                if example:
                    example_response["body"] = json.dumps(example, indent=2)
            
            request["response"].append(example_response)
    
    return request


def _get_example_value(param: Dict[str, Any]) -> str:
    """Get example value for a parameter."""
    param_schema = param.get("schema", {})
    param_type = param_schema.get("type", "string")
    
    # Check for example in parameter
    if "example" in param:
        return str(param["example"])
    
    # Check for example in schema
    if "example" in param_schema:
        return str(param_schema["example"])
    
    # Generate based on type
    examples = {
        "string": "example_string",
        "integer": "1",
        "number": "1.0",
        "boolean": "true",
        "array": "[]",
        "object": "{}"
    }
    
    # Special cases based on parameter name
    param_name = param.get("name", "").lower()
    if "id" in param_name:
        return "123e4567-e89b-12d3-a456-426614174000"
    elif "email" in param_name:
        return "user@example.com"
    elif "phone" in param_name:
        return "+1234567890"
    elif "date" in param_name:
        return "2024-01-01"
    elif "time" in param_name:
        return "2024-01-01T00:00:00Z"
    
    return examples.get(param_type, "example_value")


def _generate_example_from_schema(schema: Dict[str, Any], openapi_schema: Dict[str, Any]) -> Any:
    """Generate example data from JSON schema."""
    
    # Handle $ref
    if "$ref" in schema:
        ref_path = schema["$ref"].replace("#/", "").split("/")
        ref_schema = openapi_schema
        for part in ref_path:
            ref_schema = ref_schema.get(part, {})
        return _generate_example_from_schema(ref_schema, openapi_schema)
    
    schema_type = schema.get("type", "object")
    
    if schema_type == "object":
        result = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for prop_name, prop_schema in properties.items():
            # Include required fields and some optional ones for completeness
            if prop_name in required or len(result) < 5:
                result[prop_name] = _generate_example_from_schema(prop_schema, openapi_schema)
        
        return result
    
    elif schema_type == "array":
        items_schema = schema.get("items", {})
        return [_generate_example_from_schema(items_schema, openapi_schema)]
    
    elif schema_type == "string":
        # Check format for specific examples
        format_type = schema.get("format")
        if format_type == "email":
            return "user@example.com"
        elif format_type == "date":
            return "2024-01-01"
        elif format_type == "date-time":
            return "2024-01-01T00:00:00Z"
        elif format_type == "uuid":
            return "123e4567-e89b-12d3-a456-426614174000"
        elif format_type == "password":
            return "secure_password123"
        
        # Check enum values
        if "enum" in schema:
            return schema["enum"][0]
        
        return "example_string"
    
    elif schema_type == "integer":
        return 1
    
    elif schema_type == "number":
        return 1.0
    
    elif schema_type == "boolean":
        return True
    
    return None


def save_postman_collection(app: FastAPI, filename: str = "hormonia_api_collection.json"):
    """
    Save Postman collection to file.
    
    Args:
        app: FastAPI application instance
        filename: Output filename for the collection
    """
    collection = generate_postman_collection(app)
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)
    
    return filename


def get_api_version_info() -> Dict[str, Any]:
    """
    Get API versioning information.
    
    Returns:
        Dictionary containing version strategy and compatibility info
    """
    return {
        "current_version": "v2",
        "supported_versions": ["v2"],
        "version_strategy": "url_path",
        "deprecation_policy": {
            "notice_period": "6 months",
            "support_period": "12 months",
            "migration_guide": "https://docs.hormonia.com/api/migration"
        },
        "breaking_changes": {
            "v1.0.0": "Initial release",
            "v2.0.0": "Complete API redesign with enhanced endpoints, cursor pagination, and caching"
        },
        "compatibility": {
            "backward_compatible": False,
            "forward_compatible": False,
            "notes": "V1 API has been fully deprecated. System is 100% V2."
        },
        "versioning_guidelines": {
            "major_version": "Breaking changes that require client updates",
            "minor_version": "New features that are backward compatible",
            "patch_version": "Bug fixes and minor improvements"
        },
        "version_header": "API-Version",
        "default_version": "v2",
        "latest_version": "v2"
    }


def validate_openapi_spec(app: FastAPI) -> Dict[str, Any]:
    """
    Validate the OpenAPI specification for completeness and correctness.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Dictionary containing validation results
    """
    try:
        openapi_spec = app.openapi()
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # Check required fields
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            if field not in openapi_spec:
                validation_results["errors"].append(f"Missing required field: {field}")
                validation_results["valid"] = False
        
        # Check info section
        info = openapi_spec.get("info", {})
        required_info_fields = ["title", "version"]
        for field in required_info_fields:
            if field not in info:
                validation_results["errors"].append(f"Missing required info field: {field}")
                validation_results["valid"] = False
        
        # Check paths
        paths = openapi_spec.get("paths", {})
        if not paths:
            validation_results["warnings"].append("No API paths defined")
        
        # Count endpoints
        endpoint_count = 0
        endpoints_with_descriptions = 0
        endpoints_with_examples = 0
        
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoint_count += 1
                    
                    if operation.get("description"):
                        endpoints_with_descriptions += 1
                    
                    # Check for examples in responses
                    responses = operation.get("responses", {})
                    for status, response in responses.items():
                        content = response.get("content", {})
                        if any("example" in media_type for media_type in content.values()):
                            endpoints_with_examples += 1
                            break
        
        # Check security schemes
        components = openapi_spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        
        validation_results["info"] = {
            "openapi_version": openapi_spec.get("openapi"),
            "api_title": info.get("title"),
            "api_version": info.get("version"),
            "total_endpoints": endpoint_count,
            "endpoints_with_descriptions": endpoints_with_descriptions,
            "endpoints_with_examples": endpoints_with_examples,
            "security_schemes_count": len(security_schemes),
            "schemas_count": len(components.get("schemas", {})),
            "servers_count": len(openapi_spec.get("servers", [])),
            "tags_count": len(openapi_spec.get("tags", []))
        }
        
        # Add warnings for missing documentation
        if endpoints_with_descriptions < endpoint_count:
            missing_descriptions = endpoint_count - endpoints_with_descriptions
            validation_results["warnings"].append(
                f"{missing_descriptions} endpoints missing descriptions"
            )
        
        if endpoints_with_examples < endpoint_count * 0.5:  # At least 50% should have examples
            validation_results["warnings"].append(
                "Less than 50% of endpoints have response examples"
            )
        
        if not security_schemes:
            validation_results["warnings"].append("No security schemes defined")
        
        return validation_results
        
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Failed to validate OpenAPI spec: {str(e)}"],
            "warnings": [],
            "info": {}
        }


def generate_api_changelog() -> List[Dict[str, Any]]:
    """
    Generate API changelog based on version history.
    
    Returns:
        List of changelog entries
    """
    return [
        {
            "version": "1.0.0",
            "date": "2024-01-01",
            "type": "major",
            "changes": [
                {
                    "type": "added",
                    "description": "Initial API release with core functionality",
                    "endpoints": [
                        "Authentication endpoints",
                        "Patient management endpoints", 
                        "WhatsApp messaging endpoints",
                        "Conversation flow endpoints",
                        "Quiz and assessment endpoints",
                        "Medical reporting endpoints",
                        "Alert management endpoints",
                        "Real-time WebSocket endpoints"
                    ]
                },
                {
                    "type": "added",
                    "description": "JWT-based authentication system",
                    "details": "Secure token-based authentication with refresh tokens"
                },
                {
                    "type": "added",
                    "description": "WhatsApp Business API integration",
                    "details": "Full integration with Evolution API for WhatsApp messaging"
                },
                {
                    "type": "added",
                    "description": "AI-powered message personalization",
                    "details": "Google Gemini (LangChain) integration for message humanization"
                }
            ],
            "breaking_changes": [],
            "migration_notes": "Initial release - no migration required"
        }
    ]
