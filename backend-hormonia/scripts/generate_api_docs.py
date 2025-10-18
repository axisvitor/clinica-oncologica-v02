#!/usr/bin/env python3
"""
API Documentation Auto-Generator

Automatically generates comprehensive API documentation from FastAPI routes.
Extracts information from route definitions, docstrings, schemas, and annotations.

Features:
- Markdown documentation generation
- OpenAPI/Swagger export
- Endpoint inventory
- Request/Response examples
- Authentication requirements
- Rate limiting info

Usage:
    python scripts/generate_api_docs.py --output docs/API_REFERENCE.md
    python scripts/generate_api_docs.py --format json --output api-inventory.json
    python scripts/generate_api_docs.py --openapi --output openapi.yaml

Sprint: 3 (Future Enhancement)
Status: Ready for Sprint 4
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import inspect
import importlib
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class APIDocGenerator:
    """Generates API documentation from FastAPI application."""

    def __init__(self, app_module: str = "app.main"):
        self.app_module = app_module
        self.endpoints: List[Dict[str, Any]] = []
        self.app = None

    def load_app(self):
        """Load FastAPI application."""
        try:
            module = importlib.import_module(self.app_module)
            self.app = getattr(module, "app")
            print(f"✅ Loaded application from {self.app_module}")
        except Exception as e:
            print(f"❌ Failed to load app: {e}")
            sys.exit(1)

    def extract_endpoints(self):
        """Extract all endpoints from FastAPI app."""
        if not self.app:
            self.load_app()

        for route in self.app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                endpoint_info = self._extract_endpoint_info(route)
                if endpoint_info:
                    self.endpoints.append(endpoint_info)

        print(f"✅ Extracted {len(self.endpoints)} endpoints")

    def _extract_endpoint_info(self, route) -> Optional[Dict[str, Any]]:
        """Extract detailed information from a single route."""
        try:
            # Basic info
            info = {
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
                "summary": "",
                "description": "",
                "tags": [],
                "deprecated": False,
                "auth_required": False,
                "rate_limited": False,
                "request_body": None,
                "responses": {},
                "parameters": [],
            }

            # Extract from endpoint function
            if hasattr(route, "endpoint"):
                endpoint_func = route.endpoint

                # Docstring
                if endpoint_func.__doc__:
                    info["description"] = inspect.cleandoc(endpoint_func.__doc__)
                    # Extract summary (first line)
                    lines = info["description"].split("\n")
                    info["summary"] = lines[0] if lines else ""

                # Check for authentication decorator
                source = inspect.getsource(endpoint_func)
                if (
                    "Depends(get_current_user)" in source
                    or "Depends(get_current_admin)" in source
                ):
                    info["auth_required"] = True

                # Check for rate limiting
                if "rate_limit" in source.lower():
                    info["rate_limited"] = True

                # Parameters
                sig = inspect.signature(endpoint_func)
                for param_name, param in sig.parameters.items():
                    if param_name not in ["request", "response", "db", "current_user"]:
                        param_info = {
                            "name": param_name,
                            "type": str(param.annotation)
                            if param.annotation != inspect.Parameter.empty
                            else "Any",
                            "required": param.default == inspect.Parameter.empty,
                        }
                        info["parameters"].append(param_info)

            # Extract from OpenAPI schema if available
            if hasattr(route, "response_model"):
                info["response_model"] = str(route.response_model)

            # Determine domain/tags from path
            path_parts = route.path.strip("/").split("/")
            if len(path_parts) >= 3:  # /api/v1/domain
                info["tags"] = [path_parts[2]]

            return info

        except Exception as e:
            print(f"⚠️  Failed to extract info from {route.path}: {e}")
            return None

    def generate_markdown(self) -> str:
        """Generate Markdown documentation."""
        md = []

        # Header
        md.append("# 📚 API Reference Documentation\n")
        md.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        md.append(f"**Version**: 1.0\n")
        md.append(f"**Total Endpoints**: {len(self.endpoints)}\n")
        md.append("\n---\n")

        # Table of Contents
        md.append("\n## 📋 Table of Contents\n")
        domains = self._group_by_domain()
        for domain in sorted(domains.keys()):
            md.append(f"- [{domain.title()}](#{domain.lower()})\n")
        md.append("\n---\n")

        # Statistics
        md.append("\n## 📊 Statistics\n")
        md.append(f"- **Total Endpoints**: {len(self.endpoints)}\n")
        md.append(
            f"- **Authenticated**: {sum(1 for e in self.endpoints if e['auth_required'])}\n"
        )
        md.append(
            f"- **Rate Limited**: {sum(1 for e in self.endpoints if e['rate_limited'])}\n"
        )
        md.append(f"- **Domains**: {len(domains)}\n")
        md.append("\n---\n")

        # Endpoints by domain
        for domain, endpoints in sorted(domains.items()):
            md.append(f"\n## {domain.title()}\n")
            md.append(f"\n**Endpoints**: {len(endpoints)}\n")

            for endpoint in sorted(endpoints, key=lambda x: x["path"]):
                md.append(self._format_endpoint_markdown(endpoint))

        return "".join(md)

    def _format_endpoint_markdown(self, endpoint: Dict[str, Any]) -> str:
        """Format a single endpoint as Markdown."""
        md = []

        # Endpoint header
        methods = ", ".join(endpoint["methods"])
        md.append(f"\n### `{methods}` {endpoint['path']}\n")

        # Summary
        if endpoint["summary"]:
            md.append(f"\n**Summary**: {endpoint['summary']}\n")

        # Description
        if endpoint["description"] and endpoint["description"] != endpoint["summary"]:
            md.append(f"\n{endpoint['description']}\n")

        # Badges
        badges = []
        if endpoint["auth_required"]:
            badges.append("🔒 Auth Required")
        if endpoint["rate_limited"]:
            badges.append("⏱️ Rate Limited")
        if endpoint["deprecated"]:
            badges.append("⚠️ Deprecated")

        if badges:
            md.append(f"\n{' | '.join(badges)}\n")

        # Parameters
        if endpoint["parameters"]:
            md.append("\n**Parameters**:\n")
            for param in endpoint["parameters"]:
                required = "**required**" if param["required"] else "optional"
                md.append(f"- `{param['name']}` ({param['type']}) - {required}\n")

        # Response Model
        if endpoint.get("response_model"):
            md.append(f"\n**Response Model**: `{endpoint['response_model']}`\n")

        md.append("\n---\n")
        return "".join(md)

    def _group_by_domain(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group endpoints by domain."""
        domains = {}

        for endpoint in self.endpoints:
            # Extract domain from path
            path_parts = endpoint["path"].strip("/").split("/")
            if len(path_parts) >= 3:
                domain = path_parts[2]  # /api/v1/domain
            else:
                domain = "core"

            if domain not in domains:
                domains[domain] = []
            domains[domain].append(endpoint)

        return domains

    def generate_json(self) -> str:
        """Generate JSON inventory."""
        inventory = {
            "generated": datetime.now().isoformat(),
            "version": "1.0",
            "total_endpoints": len(self.endpoints),
            "domains": self._group_by_domain(),
            "endpoints": self.endpoints,
        }
        return json.dumps(inventory, indent=2)

    def generate_openapi_yaml(self) -> str:
        """Generate OpenAPI YAML."""
        if not self.app:
            self.load_app()

        # FastAPI has built-in OpenAPI generation
        openapi_schema = self.app.openapi()

        # Convert to YAML-like format
        import yaml

        return yaml.dump(openapi_schema, default_flow_style=False)

    def save_to_file(self, content: str, output_path: str):
        """Save documentation to file."""
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(content, encoding="utf-8")
            print(f"✅ Documentation saved to: {output_path}")
        except Exception as e:
            print(f"❌ Failed to save documentation: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate API documentation from FastAPI application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Markdown documentation
  python scripts/generate_api_docs.py --format markdown --output docs/API_REFERENCE.md

  # Generate JSON inventory
  python scripts/generate_api_docs.py --format json --output api-inventory.json

  # Generate OpenAPI YAML
  python scripts/generate_api_docs.py --format openapi --output openapi.yaml

  # Generate all formats
  python scripts/generate_api_docs.py --all
        """,
    )

    parser.add_argument(
        "--format",
        choices=["markdown", "json", "openapi"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="docs/API_REFERENCE.md",
        help="Output file path (default: docs/API_REFERENCE.md)",
    )

    parser.add_argument(
        "--app",
        type=str,
        default="app.main",
        help="FastAPI app module (default: app.main)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all formats",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("API Documentation Generator")
    print("=" * 80)
    print()

    # Create generator
    generator = APIDocGenerator(app_module=args.app)
    generator.load_app()
    generator.extract_endpoints()

    # Generate documentation
    if args.all:
        # Generate all formats
        formats = [
            ("markdown", "docs/API_REFERENCE.md"),
            ("json", "docs/api-inventory.json"),
            ("openapi", "docs/openapi.yaml"),
        ]

        for fmt, output in formats:
            print(f"\nGenerating {fmt} documentation...")
            if fmt == "markdown":
                content = generator.generate_markdown()
            elif fmt == "json":
                content = generator.generate_json()
            elif fmt == "openapi":
                content = generator.generate_openapi_yaml()

            generator.save_to_file(content, output)
    else:
        # Generate single format
        print(f"\nGenerating {args.format} documentation...")

        if args.format == "markdown":
            content = generator.generate_markdown()
        elif args.format == "json":
            content = generator.generate_json()
        elif args.format == "openapi":
            content = generator.generate_openapi_yaml()

        generator.save_to_file(content, args.output)

    print()
    print("=" * 80)
    print("✅ Documentation generation complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
