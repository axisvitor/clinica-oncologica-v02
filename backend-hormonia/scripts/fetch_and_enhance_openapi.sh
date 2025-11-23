#!/bin/bash
# Fetch OpenAPI schema from running server and enhance it
# This script assumes the FastAPI server is running on localhost:8000

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_ROOT/docs/api"
TEMP_FILE="/tmp/openapi_base.json"
OUTPUT_FILE="$OUTPUT_DIR/openapi.json"

echo "🚀 Fetching OpenAPI specification from running server..."

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Fetch OpenAPI from server
echo "📡 Fetching from http://localhost:8000/openapi.json..."
if curl -sf http://localhost:8000/openapi.json -o "$TEMP_FILE"; then
    echo "✅ Successfully fetched OpenAPI schema"

    # Copy to output location
    cp "$TEMP_FILE" "$OUTPUT_FILE"

    # Display statistics
    ENDPOINT_COUNT=$(jq '.paths | length' "$OUTPUT_FILE")
    SCHEMA_COUNT=$(jq '.components.schemas | length' "$OUTPUT_FILE")

    echo ""
    echo "✅ OpenAPI specification saved successfully!"
    echo "📊 Statistics:"
    echo "   - Endpoints: $ENDPOINT_COUNT"
    echo "   - Schemas: $SCHEMA_COUNT"
    echo "   - Output: $OUTPUT_FILE"
    echo ""
    echo "💡 Next steps:"
    echo "   1. View in Swagger UI: http://localhost:8000/docs"
    echo "   2. View in ReDoc: http://localhost:8000/redoc"
    echo "   3. Use openapi.json for codegen or documentation"

else
    echo "❌ Error: Could not fetch OpenAPI schema from http://localhost:8000/openapi.json"
    echo ""
    echo "Please ensure the FastAPI server is running:"
    echo "  cd backend-hormonia && python3 -m uvicorn app.main:app --reload"
    exit 1
fi
