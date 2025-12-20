"""
Application entry point for Railpack/Railway deployment.

This module creates and exposes the FastAPI application instance
for uvicorn to serve. Railpack auto-detects this file and runs:
  uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
"""

from app.core.application_factory import create_application

# Create the FastAPI application instance
# Railpack/uvicorn expects 'app' to be the ASGI application
app = create_application()

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("APP_ENVIRONMENT", "development") == "development",
    )
